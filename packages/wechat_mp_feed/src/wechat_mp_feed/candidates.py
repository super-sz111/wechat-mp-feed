"""Normalize source candidates returned by downloader services."""

from __future__ import annotations

from typing import Any

from .name_match import name_similarity, names_equivalent


def normalize_source_candidates(body: Any, query: str) -> list[dict[str, Any]]:
    """Extract candidate records from common response shapes."""
    items = _find_items(body)
    candidates = []
    for item in items:
        if not isinstance(item, dict):
            continue

        name = _first(item, "nickname", "nick_name", "name", "title", "alias")
        fakeid = _first(item, "fakeid", "fake_id", "wechat_fakeid")
        biz = _first(item, "__biz", "biz")
        avatar_url = _first(item, "avatar_url", "head_img", "round_head_img", "cover")
        intro = _first(item, "intro", "signature", "description", "desc")
        score = _score(item, name, query)

        if not name and not fakeid and not biz:
            continue

        candidates.append(
            {
                "candidate_name": name or fakeid or biz or query,
                "wechat_fakeid": fakeid,
                "biz": biz,
                "avatar_url": avatar_url,
                "intro": intro,
                "score": score,
                "raw_payload": item,
            }
        )
    return candidates


def _find_items(body: Any) -> list[Any]:
    if isinstance(body, list):
        return body
    if not isinstance(body, dict):
        return []

    for key in ("items", "list", "data", "results", "records"):
        value = body.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _find_items(value)
            if nested:
                return nested
    return []


def _first(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _score(item: dict[str, Any], name: str | None, query: str) -> float:
    raw_score = item.get("score") or item.get("confidence")
    if raw_score is not None:
        try:
            return max(0.0, min(1.0, float(raw_score)))
        except (TypeError, ValueError):
            pass
    if name and names_equivalent(name, query):
        return 0.92
    if name and query.strip() and query.strip() in name:
        return 0.8
    similarity = name_similarity(name, query)
    if similarity >= 0.86:
        return 0.86
    if similarity >= 0.74:
        return 0.74
    return 0.5
