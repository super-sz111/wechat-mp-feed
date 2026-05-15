"""Normalize article content returned by downloader services."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any


def normalize_article_content(body: Any) -> dict[str, Any]:
    """Extract content and asset metadata from common response shapes."""
    payload = _payload(body)
    content_html = _first(payload, "content_html", "html", "content", "content_noencode")
    assets = _assets(payload)
    structure = _content_structure(content_html, assets)
    return {
        "content_html": content_html,
        "content_text": _first(payload, "content_text", "text", "plain_text", "plain_content"),
        "content_markdown": _first(payload, "content_markdown", "markdown", "md"),
        "assets": assets,
        "content_structure": structure,
        "raw_payload": body,
    }


def _payload(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {}
    for key in ("data", "article", "content", "result"):
        value = body.get(key)
        if isinstance(value, dict):
            merged = dict(body)
            merged.update(value)
            return merged
    return body


def _assets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for key in ("assets", "images", "image_urls", "imgs"):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                asset = _asset_from_item(item)
                if asset:
                    assets.append(asset)
    return assets


def _asset_from_item(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        return {"asset_type": "image", "url": item, "metadata": {}}
    if not isinstance(item, dict):
        return None
    url = _first(item, "url", "src", "link")
    if not url:
        return None
    return {
        "asset_type": _first(item, "asset_type", "type") or "image",
        "url": url,
        "metadata": item,
    }


def _content_structure(content_html: str | None, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if content_html:
        parser = ArticleHTMLBlockParser()
        parser.feed(content_html)
        parser.close()
        return parser.blocks
    return [
        {
            "type": asset.get("asset_type", "image"),
            "url": asset["url"],
            "asset_index": index,
        }
        for index, asset in enumerate(assets)
        if asset.get("url")
    ]


class ArticleHTMLBlockParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict[str, Any]] = []
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value for key, value in attrs}
        if tag == "img":
            self._flush_text()
            url = _first(attr, "data-src", "src", "data-original", "data-url")
            if url:
                self.blocks.append(
                    {
                        "type": "image",
                        "url": url,
                        "alt": attr.get("alt") or "",
                    }
                )
        elif tag in {"p", "section", "div", "br", "li", "tr"}:
            self._flush_text()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "section", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._flush_text()

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self._text_parts.append(text)

    def _flush_text(self) -> None:
        text = "".join(self._text_parts).strip()
        self._text_parts = []
        if text:
            self.blocks.append({"type": "text", "text": text})


def _first(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None
