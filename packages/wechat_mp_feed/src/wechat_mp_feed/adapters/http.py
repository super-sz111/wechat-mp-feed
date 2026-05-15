"""Small stdlib HTTP client used by service adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class HTTPResponse:
    status: int
    url: str
    headers: dict[str, str]
    body: Any


class HTTPClient:
    def __init__(self, base_url: str, token: str | None = None, timeout_seconds: float = 30):
        self.base_url = base_url.rstrip("/") + "/"
        self.token = token
        self.timeout_seconds = timeout_seconds

    def get(self, path: str, params: dict[str, Any] | None = None) -> HTTPResponse:
        url = self._url(path, params)
        return self._request("GET", url)

    def post(self, path: str, payload: dict[str, Any] | None = None) -> HTTPResponse:
        url = self._url(path)
        data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        return self._request("POST", url, data=data)

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        url = urljoin(self.base_url, path.lstrip("/"))
        if params:
            clean = {key: value for key, value in params.items() if value is not None}
            if clean:
                url = f"{url}?{urlencode(clean)}"
        return url

    def _request(self, method: str, url: str, data: bytes | None = None) -> HTTPResponse:
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
                return HTTPResponse(
                    status=response.status,
                    url=url,
                    headers=dict(response.headers.items()),
                    body=_decode_body(body, response.headers.get("Content-Type")),
                )
        except HTTPError as exc:
            body = exc.read()
            return HTTPResponse(
                status=exc.code,
                url=url,
                headers=dict(exc.headers.items()),
                body=_decode_body(body, exc.headers.get("Content-Type")),
            )
        except URLError as exc:
            raise ConnectionError(f"HTTP request failed for {url}: {exc.reason}") from exc


def _decode_body(body: bytes, content_type: str | None) -> Any:
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    if content_type and "json" in content_type.lower():
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
