"""Utilities for parsing WeChat Official Account article URLs."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class WeChatArticleURL:
    raw_url: str
    biz: str | None
    mid: str | None
    idx: str | None
    sn: str | None
    host: str
    path: str

    @property
    def has_biz(self) -> bool:
        return bool(self.biz)


def parse_article_url(url: str) -> WeChatArticleURL:
    """Parse a WeChat article URL and extract stable query identifiers."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must start with http:// or https://")
    if not parsed.netloc:
        raise ValueError("URL must include a host")

    query = parse_qs(parsed.query, keep_blank_values=False)

    def first(name: str) -> str | None:
        values = query.get(name)
        return values[0] if values else None

    return WeChatArticleURL(
        raw_url=url.strip(),
        biz=first("__biz"),
        mid=first("mid"),
        idx=first("idx"),
        sn=first("sn"),
        host=parsed.netloc.lower(),
        path=parsed.path,
    )
