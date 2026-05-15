"""Normalize article metadata returned by downloader services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def normalize_article_items(body: Any) -> list[dict[str, Any]]:
    """Extract article metadata from common response shapes."""
    items = _find_items(body)
    articles = []
    for item in items:
        if not isinstance(item, dict):
            continue

        flattened = _flatten_article_item(item)
        url = _first(flattened, "url", "link", "content_url")
        title = _first(flattened, "title")
        if not url or not title:
            continue

        articles.append(
            {
                "title": title,
                "url": url.replace("\\/", "/"),
                "digest": _first(flattened, "digest", "summary", "desc"),
                "cover_url": _first(flattened, "cover_url", "cover", "thumb_url"),
                "publish_time": _publish_time(flattened),
                "raw_payload": item,
            }
        )
    return articles


def _find_items(body: Any) -> list[Any]:
    if isinstance(body, list):
        return body
    if not isinstance(body, dict):
        return []

    for key in ("app_msg_list", "articles", "items", "list", "data", "results", "records"):
        value = body.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _find_items(value)
            if nested:
                return nested
    return []


def _flatten_article_item(item: dict[str, Any]) -> dict[str, Any]:
    flattened = dict(item)
    for key in ("app_msg_ext_info", "comm_msg_info"):
        value = item.get(key)
        if isinstance(value, dict):
            flattened.update({nested_key: nested_value for nested_key, nested_value in value.items() if nested_key not in flattened})
    return flattened


def _first(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _publish_time(item: dict[str, Any]) -> str | None:
    value = item.get("publish_time") or item.get("update_time") or item.get("datetime") or item.get("create_time")
    if value is None:
        return None
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or None

    if timestamp > 10_000_000_000:
        timestamp = timestamp // 1000
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(microsecond=0).isoformat()
