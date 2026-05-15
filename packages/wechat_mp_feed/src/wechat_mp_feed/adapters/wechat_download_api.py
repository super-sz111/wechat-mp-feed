"""Adapter for the external wechat-download-api HTTP service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .http import HTTPClient

BASE_URL_ENV = "WECHAT_DOWNLOAD_API_BASE_URL"
TOKEN_ENV = "WECHAT_DOWNLOAD_API_TOKEN"


@dataclass(frozen=True)
class WeChatDownloadAPIConfig:
    base_url: str
    token: str | None = None
    timeout_seconds: float = 30

    @classmethod
    def from_env(cls, base_url: str | None = None, timeout_seconds: float = 30) -> "WeChatDownloadAPIConfig":
        resolved_base_url = base_url or os.environ.get(BASE_URL_ENV)
        if not resolved_base_url:
            raise ValueError(f"Missing base URL. Set {BASE_URL_ENV} or pass --base-url.")
        return cls(
            base_url=resolved_base_url,
            token=os.environ.get(TOKEN_ENV),
            timeout_seconds=timeout_seconds,
        )


class WeChatDownloadAPIAdapter:
    """Thin client for wechat-download-api.

    The external service owns WeChat login state and crawling mechanics. This
    adapter only normalizes HTTP calls for mpfeed workflows.
    """

    def __init__(self, config: WeChatDownloadAPIConfig):
        self.config = config
        self.client = HTTPClient(config.base_url, token=config.token, timeout_seconds=config.timeout_seconds)

    def health(self) -> dict[str, Any]:
        response = self.client.get("/api/health")
        return _envelope("health", response.status, response.url, response.body)

    def auth_status(self) -> dict[str, Any]:
        response = self.client.get("/api/admin/status")
        return _envelope("auth_status", response.status, response.url, response.body)

    def search_sources(self, query: str) -> dict[str, Any]:
        response = self.client.get("/api/public/searchbiz", {"query": query})
        return _envelope("search_sources", response.status, response.url, response.body)

    def list_articles(
        self,
        fakeid: str,
        begin: int = 0,
        count: int = 10,
        keyword: str | None = None,
    ) -> dict[str, Any]:
        response = self.client.get(
            "/api/public/articles",
            {"fakeid": fakeid, "begin": begin, "count": count, "keyword": keyword},
        )
        return _envelope("list_articles", response.status, response.url, response.body)

    def fetch_article(self, url: str) -> dict[str, Any]:
        response = self.client.post("/api/article", {"url": url})
        return _envelope("fetch_article", response.status, response.url, response.body)


def _envelope(operation: str, status: int, url: str, body: Any) -> dict[str, Any]:
    ok = 200 <= status < 300
    if isinstance(body, dict) and body.get("success") is False:
        ok = False
    return {
        "ok": ok,
        "operation": operation,
        "status": status,
        "url": url,
        "body": body,
    }
