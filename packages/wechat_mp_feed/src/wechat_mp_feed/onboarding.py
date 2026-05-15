"""Source onboarding review-table helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .analysis import classify_source
from .llm_jobs import ONBOARDING_REVIEW_CATEGORIES
from .name_match import name_similarity, names_equivalent
from .storage import Store
from .taxonomy import Taxonomy


FINANCE_CATEGORIES = {
    "macro_policy",
    "strategy",
    "quant",
    "fixed_income",
    "industry_research",
    "company_research",
    "market_infra",
    "finance_thinktank",
    "industrial",
    "news",
    "opinion_kol",
}


def build_onboarding_rows(
    store: Store,
    taxonomy: Taxonomy,
    source_type: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    imports = store.list_imports(limit=limit, source_type=source_type)
    candidates = store.list_candidates(decision=None, limit=max(limit * 10, 1000))
    sources = store.list_sources(limit=max(limit * 2, 1000))
    articles = store.list_articles(limit=max(limit * 10, 1000))
    classifications = store.list_classifications(limit=max(limit * 4, 1000), entity_type="source", taxonomy=taxonomy.name)

    candidates_by_import: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        candidates_by_import[candidate["import_id"]].append(candidate)

    source_by_fakeid = {source.get("wechat_fakeid"): source for source in sources if source.get("wechat_fakeid")}
    source_by_biz = {source.get("biz"): source for source in sources if source.get("biz")}
    source_by_name = {source["name"]: source for source in sources}

    latest_article_by_source: dict[str, dict[str, Any]] = {}
    for article in articles:
        source_id = article.get("source_id")
        if source_id and source_id not in latest_article_by_source:
            latest_article_by_source[source_id] = article

    classification_by_source: dict[str, dict[str, Any]] = {}
    for classification in classifications:
        classification_by_source.setdefault(classification["entity_id"], classification)

    rows = []
    for item in imports:
        best_candidate = pick_best_candidate(item, candidates_by_import.get(item["id"], []))
        source = find_source(item, best_candidate, source_by_fakeid, source_by_biz, source_by_name)
        latest_article = latest_article_by_source.get(source["id"]) if source else latest_probe_article(best_candidate)
        classification = pick_classification(item, best_candidate, source, classification_by_source, taxonomy)
        rows.append(format_onboarding_row(item, best_candidate, source, latest_article, classification))

    return rows


def build_compact_onboarding_rows(
    store: Store,
    taxonomy: Taxonomy,
    source_type: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    return [compact_onboarding_row(row) for row in build_onboarding_rows(store, taxonomy, source_type, limit)]


def pick_best_candidate(import_row: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    match_name = effective_match_name(import_row)
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.get("candidate_name") == match_name,
            names_equivalent(candidate.get("candidate_name"), match_name),
            name_similarity(candidate.get("candidate_name"), match_name),
            float(candidate.get("score") or 0),
            candidate.get("created_at") or "",
        ),
        reverse=True,
    )[0]


def manual_review_for_import(import_row: dict[str, Any]) -> dict[str, Any]:
    review = (import_row.get("raw_payload") or {}).get("manual_onboarding_review") or {}
    return review if isinstance(review, dict) else {}


def manual_account_name_for_import(import_row: dict[str, Any]) -> str | None:
    name = manual_review_for_import(import_row).get("manual_account_name")
    if name is None:
        return None
    text = str(name).strip()
    return text or None


def effective_match_name(import_row: dict[str, Any]) -> str | None:
    return manual_account_name_for_import(import_row) or import_row.get("raw_name")


def names_match_manual_or_raw(import_row: dict[str, Any], candidate_name: object) -> bool:
    match_name = effective_match_name(import_row)
    return bool(candidate_name and match_name and names_equivalent(candidate_name, match_name))


def find_source(
    import_row: dict[str, Any],
    candidate: dict[str, Any] | None,
    source_by_fakeid: dict[str, dict[str, Any]],
    source_by_biz: dict[str, dict[str, Any]],
    source_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if candidate:
        fakeid = candidate.get("wechat_fakeid")
        biz = candidate.get("biz")
        name = candidate.get("candidate_name")
        return source_by_fakeid.get(fakeid) or source_by_biz.get(biz) or source_by_name.get(name)
    raw_name = import_row.get("raw_name")
    return source_by_name.get(raw_name)


def latest_probe_article(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    probe = candidate_article_probe(candidate)
    if not isinstance(probe, dict):
        return None
    articles = probe.get("articles") or []
    if not articles:
        return None
    for article in articles:
        if isinstance(article, dict) and article.get("content_fetch_ok") is True:
            return article
    return articles[0]


def candidate_article_probe(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if not candidate:
        return None
    probe = (candidate.get("raw_payload") or {}).get("article_probe")
    return probe if isinstance(probe, dict) else None


def latest_probe_status(candidate: dict[str, Any] | None, latest_article: dict[str, Any] | None) -> str:
    probe = candidate_article_probe(candidate)
    if probe:
        if probe.get("ok") is False:
            return "candidate_latest_failed"
        if probe.get("articles"):
            return "candidate_latest_ok"
        return "candidate_latest_empty"
    if latest_article:
        return "source_latest_ok"
    return "missing"


def pick_classification(
    import_row: dict[str, Any],
    candidate: dict[str, Any] | None,
    source: dict[str, Any] | None,
    classification_by_source: dict[str, dict[str, Any]],
    taxonomy: Taxonomy,
) -> dict[str, Any]:
    if source and source["id"] in classification_by_source:
        classification = classification_by_source[source["id"]]
        return {**classification, "method": classification.get("method") or "stored"}

    name = (candidate or {}).get("candidate_name") or import_row.get("raw_name")
    intro = (candidate or {}).get("intro")
    pseudo_source = {
        "id": (candidate or import_row)["id"],
        "name": name,
        "intro": intro,
        "source_type": import_row.get("source_type"),
    }
    return classify_source(pseudo_source, taxonomy)


def format_onboarding_row(
    import_row: dict[str, Any],
    candidate: dict[str, Any] | None,
    source: dict[str, Any] | None,
    latest_article: dict[str, Any] | None,
    classification: dict[str, Any],
) -> dict[str, Any]:
    import_status = import_row.get("status") or ""
    llm_review = (import_row.get("raw_payload") or {}).get("llm_onboarding_review") or {}
    manual_review = manual_review_for_import(import_row)
    match_name = effective_match_name(import_row)
    source_status = source.get("status") if source else None
    category = classification.get("category")
    confidence = float(classification.get("confidence") or 0)
    is_finance = category in FINANCE_CATEGORIES and category != "low_signal" and confidence >= 0.35
    display_exact_match = bool(candidate and candidate.get("candidate_name") == match_name)
    normalized_match = bool(candidate and names_equivalent(candidate.get("candidate_name"), match_name))
    similarity = name_similarity((candidate or {}).get("candidate_name"), match_name)
    match_type = account_match_type(display_exact_match, normalized_match, similarity)
    probe_status = latest_probe_status(candidate, latest_article)
    evidence_needs_review = (
        source is None
        or match_type not in {"exact", "normalized"}
        or category in {"uncategorized", "low_signal"}
        or confidence < 0.35
    )
    requires_user_action = import_status == "needs_review"
    recommended_action = recommend_action(import_status, source, candidate, is_finance, evidence_needs_review)

    return {
        "import_id": import_row["id"],
        "batch_id": import_row["batch_id"],
        "source_type": import_row["source_type"],
        "import_status": import_status,
        "identity_match_name": match_name or "",
        "manual_account_name": manual_review.get("manual_account_name") or "",
        "manual_article_url": manual_review.get("manual_article_url") or "",
        "manual_account_category": manual_review.get("manual_account_category") or "",
        "manual_decision": manual_review.get("decision") or "",
        "manual_notes": manual_review.get("notes") or "",
        "system_decision": system_decision(import_status, source, is_finance),
        "requires_user_action": requires_user_action,
        "ocr_name": import_row.get("raw_name") or "",
        "best_candidate_name": (candidate or {}).get("candidate_name") or "",
        "candidate_score": (candidate or {}).get("score", ""),
        "exact_match": normalized_match,
        "display_exact_match": display_exact_match,
        "match_type": match_type,
        "name_similarity": similarity,
        "candidate_decision": (candidate or {}).get("decision") or "",
        "candidate_intro": (candidate or {}).get("intro") or "",
        "wechat_fakeid": (candidate or {}).get("wechat_fakeid") or (source or {}).get("wechat_fakeid") or "",
        "biz": (candidate or {}).get("biz") or (source or {}).get("biz") or "",
        "source_id": (source or {}).get("id") or "",
        "source_name": (source or {}).get("name") or "",
        "source_status": source_status or "",
        "is_active": source_status == "active",
        "tier": (source or {}).get("tier") or "",
        "latest_publish_time": (latest_article or {}).get("publish_time") or "",
        "latest_article_title": (latest_article or {}).get("title") or "",
        "latest_article_digest": (latest_article or {}).get("digest") or "",
        "latest_article_url": (latest_article or {}).get("url") or "",
        "latest_probe_status": probe_status,
        "latest_probe_refreshed": probe_status != "missing",
        "classification_category": category or "",
        "classification_confidence": confidence,
        "classification_method": classification.get("method") or "",
        "llm_review_category": display_review_category(llm_review.get("review_category")),
        "llm_review_action": llm_review.get("action") or "",
        "llm_review_confidence": llm_review.get("confidence", ""),
        "llm_review_method": llm_review.get("method") or "",
        "llm_review_reason": llm_review.get("reason") or "",
        "llm_requires_user_confirmation": bool(llm_review.get("requires_user_confirmation")),
        "is_finance_candidate": is_finance,
        "needs_manual_review": requires_user_action,
        "evidence_needs_review": evidence_needs_review,
        "recommended_action": recommended_action,
        "user_decision": "",
        "user_selected_candidate_id": "",
        "user_tier": "",
        "user_note": "",
    }


def account_match_type(display_exact_match: bool, normalized_match: bool, similarity: float) -> str:
    if display_exact_match:
        return "exact"
    if normalized_match:
        return "normalized"
    if similarity >= 0.86:
        return "similar"
    if similarity > 0:
        return "different"
    return "unresolved"


def recommend_action(
    import_status: str,
    source: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    is_finance: bool,
    needs_manual_review: bool,
) -> str:
    if import_status == "ignored":
        return "ignored_non_finance"
    if import_status == "rejected":
        return "rejected_noise"
    if import_status == "needs_review":
        return "needs_user_review"
    if source and is_finance and not needs_manual_review:
        return "accepted_finance"
    if source and not is_finance:
        return "review_existing_non_finance"
    if not candidate:
        return "review_unresolved"
    if needs_manual_review:
        return "review_candidate"
    if is_finance:
        return "accept_finance_candidate"
    return "ignore_non_finance"


def system_decision(import_status: str, source: dict[str, Any] | None, is_finance: bool) -> str:
    if import_status == "resolved" and source and is_finance:
        return "accepted_finance"
    if import_status == "resolved" and source:
        return "accepted"
    if import_status == "ignored":
        return "ignored"
    if import_status == "rejected":
        return "rejected"
    if import_status == "needs_review":
        return "needs_review"
    return import_status or "pending"


def display_review_category(category: Any) -> str:
    if not category:
        return ""
    value = str(category)
    return ONBOARDING_REVIEW_CATEGORIES.get(value, value)


def compact_onboarding_row(row: dict[str, Any]) -> dict[str, Any]:
    resolved_name = row.get("best_candidate_name") or row.get("source_name") or ""
    has_strict_match = row["match_type"] in {"exact", "normalized"}
    matched_account = resolved_name if has_strict_match else ""
    candidate_account = row["best_candidate_name"] if (not has_strict_match or row["requires_user_action"]) else ""
    has_llm_review = bool(row.get("llm_review_action") or row.get("llm_review_category") or row.get("llm_review_reason"))
    if has_llm_review:
        requires_manual_confirmation = row["llm_requires_user_confirmation"] or not has_strict_match
    else:
        requires_manual_confirmation = row["requires_user_action"] or row["evidence_needs_review"] or not has_strict_match
    return {
        "ocr_account": row["ocr_name"],
        "matched_account": matched_account,
        "candidate_account": candidate_account,
        "account_category": row["llm_review_category"] or row["classification_category"],
        "system_decision": row["llm_review_action"] or row["system_decision"],
        "requires_manual_confirmation": requires_manual_confirmation,
        "match_type": row["match_type"],
        "latest_probe_status": row["latest_probe_status"],
        "evidence_summary": compact_evidence(row),
        "manual_account_name": row.get("manual_account_name") or "",
        "manual_article_url": row.get("manual_article_url") or "",
        "manual_account_category": row.get("manual_account_category") or "",
        "manual_decision": row.get("manual_decision") or "",
        "notes": row.get("manual_notes") or row["llm_review_reason"] or compact_notes(row),
    }


def compact_evidence(row: dict[str, Any]) -> str:
    parts = []
    intro = str(row.get("candidate_intro") or "").strip()
    if intro:
        parts.append(intro[:90])
    latest_title = str(row.get("latest_article_title") or "").strip()
    if latest_title:
        parts.append(f"最新文章: {latest_title[:80]}")
    return " | ".join(parts)


def compact_notes(row: dict[str, Any]) -> str:
    if row["requires_user_action"]:
        if not row.get("best_candidate_name"):
            return "未找到可用候选，请人工补充账号名或文章链接。"
        if row["match_type"] not in {"exact", "normalized"}:
            return "候选名称和 OCR 名称不完全一致，请确认是否同一账号。"
        return "系统证据不足，请人工确认是否纳入金融管理。"
    if row["system_decision"] == "ignored":
        return "系统判断为非金融或低相关账号。"
    if row["system_decision"] == "rejected":
        return "系统判断为 OCR 噪声或无效账号。"
    if row["system_decision"] in {"accepted", "accepted_finance"}:
        return "系统已纳入管理。"
    return ""
