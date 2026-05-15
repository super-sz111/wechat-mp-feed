"""Agent-agnostic LLM job export/import helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .name_match import name_similarity, names_equivalent
from .storage import Store
from .taxonomy import Taxonomy, TaxonomyEntry


LLM_JOB_VERSION = 1
ONBOARDING_JOB_ENTITY_TYPE = "source_onboarding"
ONBOARDING_REVIEW_CATEGORIES = {
    "finance_research": "金融投研",
    "finance_related": "金融相关",
    "finance_career": "金融招聘/职业服务",
    "industry_tech": "产业/科技相关",
    "recruiting": "招聘求职",
    "non_finance": "非金融",
    "uncertain": "不确定",
}

SOURCE_ATTRIBUTE_TAGS = {
    "sell_side",
    "buy_side",
    "product_provider",
    "market_infrastructure",
    "media",
    "kol",
    "recruiting",
    "academic_alumni",
    "non_finance_org",
}

ONBOARDING_SEMANTIC_GUIDANCE = [
    (
        "First classify inclusion_tier, then primary research domain, then source_attribute. "
        "Do not use sell_side or buy_side as the primary category; they are source attributes."
    ),
    (
        "Treat sell-side signals as a strong prior when the account name or recurring article titles contain a "
        "securities-house/research-team pattern, for example bracketed prefixes like 【中金策略】, 【天风固收】, "
        "【华泰金工】, 【招商电子】, 【东吴交运】, or recurring words such as 证券研究, 研究所, 宏观团队, "
        "策略团队, 固收团队, 金工, 行业周报, 公司点评, 深度报告, 晨会, 早间速递."
    ),
    (
        "Common sell-side institution cues include 中金, 华泰, 国泰海通/国君, 申万宏源/申万, 广发, 兴证, "
        "东吴, 招商, 华创, 国投/安信, 开源, 国联民生, 华福, 西部, 天风, 光大, 国盛, 华源, "
        "财通, 长江, 国金, 浙商, 银河, 中信/中信建投, 东方, 平安, 东北, 中银, 中泰, 国信, "
        "信达, 西南, 太平洋. Use the coverage words to choose the primary domain."
    ),
    (
        "Map coverage words to primary domains: 宏观/经济/央行/财政/货币/大类资产 -> macro_policy; "
        "策略/权益/A股/港股/美股/市场风格/金股 -> strategy; 固收/债市/利率/信用/转债/FICC/REITs -> "
        "fixed_income; 金工/量化/ETF/FOF/LOF/指数/基金评价/衍生品/CTA/因子 -> quant; "
        "电子/计算机/通信/医药/地产/交运/汽车/非银/银行/商贸零售/机械/新能源/化工等 -> industry_research."
    ),
    (
        "Financial data, research tooling, fund sales, and product-service accounts such as Tushare-like APIs, "
        "Ricequant-like platforms, third-party fund research, or wealth/fund product channels are usually "
        "finance_related or core_finance with primary_domain=quant and source_attribute=product_provider, "
        "unless their evidence is mainly independent research."
    ),
    (
        "Recruiting/career accounts should be recruiting_career with source_attribute=recruiting. Even financial "
        "recruiting is not core digest material unless the user explicitly promotes it."
    ),
    (
        "Strong non-finance accounts should be excluded before keyword matching: schools/alumni/event groups, "
        "public-service accounts, hospitals, sports, entertainment, lifestyle, culture, local guides, exam/civil-service "
        "prep, generic tech/programming accounts, and consumer/marketing accounts. Do not promote them merely because "
        "a recent article mentions a company, AI, economy, recruitment, or a finance employer."
    ),
    (
        "Use latest articles as evidence of recurring editorial focus, not as one-off keyword triggers. If evidence is "
        "stale, empty, migrated, or dominated by notices, lower confidence or request review."
    ),
    (
        "When latest article evidence includes content_fetch_ok=false, treat that article as unavailable, deleted, "
        "restricted, or backend-stale for freshness/classification. Prefer the newest article whose content_fetch_ok is true; "
        "if none is fetchable, lower confidence and request review."
    ),
]


def build_llm_jobs(
    store: Store,
    taxonomy: Taxonomy,
    entity_type: str = "all",
    limit: int = 100,
    source_id: str | None = None,
    content_chars: int = 6000,
) -> dict[str, Any]:
    jobs: list[dict[str, Any]] = []

    if entity_type in {"all", "source"}:
        for source in store.list_sources(limit=limit):
            jobs.append(
                {
                    "job_id": f"source:{source['id']}",
                    "entity_type": "source",
                    "entity_id": source["id"],
                    "taxonomy": taxonomy.name,
                    "source": source,
                    "task": "Decide whether this account belongs in the managed finance-source registry.",
                    "expected_result": source_expected_result(taxonomy),
                }
            )

    if entity_type in {"all", "article"}:
        for article in store.list_articles_with_content(limit=limit, source_id=source_id):
            jobs.append(
                {
                    "job_id": f"article:{article['id']}",
                    "entity_type": "article",
                    "entity_id": article["id"],
                    "taxonomy": taxonomy.name,
                    "article": compact_article(article, content_chars=content_chars),
                    "task": "Classify this article and produce a reviewable finance digest if useful.",
                    "expected_result": article_expected_result(taxonomy),
                }
            )

    return {
        "version": LLM_JOB_VERSION,
        "taxonomy": taxonomy_to_dict(taxonomy),
        "instructions": [
            "Prioritize finance/investment/research usefulness.",
            "For sources, keep finance-related accounts active and put unrelated or stale accounts into inactive/archived status.",
            "For articles, summarize only material content; score low-signal marketing, recruiting, or event notices below normal digest thresholds.",
            "For article scoring, treat securities/fund recruiting, product sales, event invitations, account promotion, course promotion, and generic market wrap text as low-signal unless the article contains reusable research logic, data, or original analysis.",
            "Recommended article importance bands: 0.75+ for durable research/decision-useful analysis; 0.45-0.75 for useful but routine tracking; below 0.45 for notices, recruiting, product marketing, events, reposts, or mostly boilerplate content.",
            "Use source context as prior evidence, but do not let a core_finance source automatically promote a low-signal article.",
            "Return JSON only, shaped as {'results': [...]} where every result references job_id, entity_type, and entity_id.",
        ]
        + ONBOARDING_SEMANTIC_GUIDANCE,
        "result_schema": {
            "classification": {
                "taxonomy": taxonomy.name,
                "category": "one taxonomy category id",
                "tags": ["taxonomy tag ids"],
                "confidence": "0.0-1.0",
                "method": "llm:<agent-or-model-name>",
            },
            "source_update": {"status": "active|inactive|archived|needs_review", "tier": "core|normal|long_tail"},
            "digest": {
                "summary": "short Chinese summary",
                "key_points": ["1-5 concise points"],
                "importance_score": "0.0-1.0",
                "reason": "why this matters or why it is low signal",
                "model": "llm:<agent-or-model-name>",
            },
        },
        "count": len(jobs),
        "jobs": jobs,
    }


def build_onboarding_llm_jobs(
    store: Store,
    taxonomy: Taxonomy,
    source_type: str | None = None,
    decision: str | None = "pending",
    limit: int = 100,
    candidate_limit: int = 5,
    article_limit: int = 3,
    strict_match_only: bool = False,
) -> dict[str, Any]:
    imports = store.list_imports(limit=limit, source_type=source_type)
    candidate_read_limit = max(limit * max(candidate_limit, 10), 1000)
    candidates = store.list_candidates(decision=decision, limit=candidate_read_limit)
    sources = store.list_sources(limit=max(limit * 2, 1000))

    candidates_by_import: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        candidates_by_import[candidate["import_id"]].append(candidate)

    source_by_fakeid = {source.get("wechat_fakeid"): source for source in sources if source.get("wechat_fakeid")}
    source_by_biz = {source.get("biz"): source for source in sources if source.get("biz")}
    source_by_name = {source["name"]: source for source in sources}

    jobs = []
    for import_row in imports:
        raw_name = import_row.get("raw_name")
        if not raw_name:
            continue
        manual_review = manual_onboarding_review(import_row)
        match_name = manual_review.get("manual_account_name") or raw_name

        ranked_candidates = sorted(
            candidates_by_import.get(import_row["id"], []),
            key=lambda candidate: (
                names_equivalent(candidate.get("candidate_name"), match_name),
                name_similarity(candidate.get("candidate_name"), match_name),
                float(candidate.get("score") or 0),
                candidate.get("created_at") or "",
            ),
            reverse=True,
        )[:candidate_limit]
        if strict_match_only and not any(
            names_equivalent(candidate.get("candidate_name"), match_name) for candidate in ranked_candidates
        ):
            continue
        compact_candidates = [
            compact_onboarding_candidate(
                candidate,
                raw_name=match_name,
                source=source_by_fakeid.get(candidate.get("wechat_fakeid"))
                or source_by_biz.get(candidate.get("biz"))
                or source_by_name.get(candidate.get("candidate_name")),
                article_limit=article_limit,
            )
            for candidate in ranked_candidates
        ]

        jobs.append(
            {
                "job_id": f"onboarding:{import_row['id']}",
                "entity_type": ONBOARDING_JOB_ENTITY_TYPE,
                "entity_id": import_row["id"],
                "taxonomy": taxonomy.name,
                "import": {
                    "id": import_row["id"],
                    "raw_name": raw_name,
                    "manual_review": manual_review,
                    "identity_match_name": match_name,
                    "raw_url": import_row.get("raw_url"),
                    "source_type": import_row.get("source_type"),
                    "status": import_row.get("status"),
                },
                "candidates": compact_candidates,
                "task": (
                    "Decide whether this imported WeChat account should enter the managed finance-source registry. "
                    "Use semantic judgment over the OCR/list name, candidate match quality, intro, and latest article evidence. "
                    "Classify the primary research domain separately from source attributes such as sell_side or buy_side. "
                    "Prefer accepting clear finance/research/investment accounts, rejecting clear non-finance accounts, "
                    "and leaving only genuinely ambiguous cases for manual review. Do not rely on keyword matches alone."
                ),
                "expected_result": onboarding_expected_result(taxonomy),
            }
        )

    return {
        "version": LLM_JOB_VERSION,
        "taxonomy": taxonomy_to_dict(taxonomy),
        "instructions": [
            "Return JSON only, shaped as {'results': [...]} where every result references job_id, entity_type, and entity_id.",
            "For source onboarding, choose at most one selected_candidate_id per imported account.",
            "Use action='accept_source' only when the selected candidate is finance-related and the match is plausible.",
            "Use action='ignore_non_finance' for clear non-finance accounts, action='reject_all' for false/noise imports, and action='needs_manual_review' for ambiguous cases.",
            "Always set review_category to one of the coarse onboarding categories; this is shown to the user in the review table.",
            "Classify accepted finance accounts by primary research domain in classification.category; put source attributes such as sell_side, buy_side, media, kol, or recruiting into classification.tags.",
            "Financial recruiting/career accounts should normally be review_category='finance_career' or 'recruiting' and should not enter the core digest tier.",
            "Clear exams, sports, entertainment, lifestyle, or marketing accounts should normally be ignored even if their latest article mentions a finance employer or business term.",
        ]
        + ONBOARDING_SEMANTIC_GUIDANCE,
        "result_schema": {
            ONBOARDING_JOB_ENTITY_TYPE: onboarding_expected_result(taxonomy),
        },
        "count": len(jobs),
        "jobs": jobs,
    }


def manual_onboarding_review(import_row: dict[str, Any]) -> dict[str, Any]:
    review = (import_row.get("raw_payload") or {}).get("manual_onboarding_review") or {}
    return review if isinstance(review, dict) else {}


def apply_llm_results(
    store: Store,
    payload: dict[str, Any] | list[Any],
    default_taxonomy: str,
    default_model: str,
) -> dict[str, Any]:
    results = payload.get("results") if isinstance(payload, dict) else payload
    if not isinstance(results, list):
        raise ValueError("LLM result JSON expects a list or an object with a 'results' list")

    saved_classifications = []
    saved_digests = []
    source_updates = []
    skipped = []

    for item in results:
        if not isinstance(item, dict):
            skipped.append({"reason": "result_not_object", "value": item})
            continue

        entity_type = item.get("entity_type")
        entity_id = item.get("entity_id")
        if not entity_type or not entity_id:
            skipped.append({"reason": "missing_entity", "result": item})
            continue

        if entity_type == ONBOARDING_JOB_ENTITY_TYPE:
            onboarding_result = apply_onboarding_result(store, item, default_taxonomy, default_model)
            if onboarding_result.get("classification"):
                saved_classifications.append(onboarding_result["classification"])
            if onboarding_result.get("source_update"):
                source_updates.append(onboarding_result["source_update"])
            if onboarding_result.get("skipped"):
                skipped.append(onboarding_result["skipped"])
            continue

        classification = normalize_classification(item, default_taxonomy, default_model)
        if classification:
            saved_classifications.append(store.save_classification(classification))

        if entity_type == "source":
            source_update = item.get("source_update") if isinstance(item.get("source_update"), dict) else item
            status = source_update.get("status") or source_update.get("source_status")
            tier = source_update.get("tier") or source_update.get("source_tier")
            if status or tier:
                source_updates.append(store.update_source(entity_id, status=status, tier=tier))

        digest = normalize_digest(item, default_model)
        if digest:
            saved_digests.append(store.save_digest(digest))

    return {
        "ok": True,
        "results_seen": len(results),
        "classifications_saved": len(saved_classifications),
        "digests_saved": len(saved_digests),
        "source_updates": len(source_updates),
        "skipped": skipped,
        "items": {
            "classifications": saved_classifications,
            "digests": saved_digests,
            "source_updates": source_updates,
        },
    }


def apply_onboarding_result(
    store: Store,
    item: dict[str, Any],
    default_taxonomy: str,
    default_model: str,
) -> dict[str, Any]:
    import_id = item["entity_id"]
    action = str(item.get("action") or item.get("decision") or "").strip().lower()
    candidate_id = item.get("selected_candidate_id") or item.get("candidate_id")
    source_update = item.get("source_update") if isinstance(item.get("source_update"), dict) else {}
    store.record_import_review(import_id, normalize_onboarding_review(item, default_model))

    if action in {"accept", "accept_source", "active"}:
        if not candidate_id:
            return {"skipped": {"reason": "missing_selected_candidate_id", "result": item}}
        tier = source_update.get("tier") or item.get("tier") or "normal"
        accepted = store.accept_candidate(candidate_id, tier=tier)
        status = source_update.get("status")
        if status and status != "active":
            store.update_source(accepted["source_id"], status=status, tier=tier)

        saved_classification = None
        classification = normalize_onboarding_classification(item, accepted["source_id"], default_taxonomy, default_model)
        if classification:
            saved_classification = store.save_classification(classification)
        return {
            "classification": saved_classification,
            "source_update": {
                "ok": True,
                "action": "accept_source",
                "candidate_id": candidate_id,
                "source_id": accepted["source_id"],
                "tier": tier,
                "status": status or "active",
            },
        }

    if action in {"ignore", "ignore_non_finance", "reject_all", "reject", "archive"}:
        rejected = store.reject_all_candidates_for_import(import_id)
        archived = store.archive_sources_for_import(import_id)
        status = "ignored" if action in {"ignore", "ignore_non_finance"} else "rejected"
        store.update_import_status(import_id, status)
        return {
            "source_update": {
                "ok": True,
                "action": action,
                "import_id": import_id,
                "candidates_rejected": rejected["count"],
                "sources_archived": archived["count"],
            }
        }

    if action in {"needs_manual_review", "manual_review", "review", "uncertain"}:
        store.update_import_status(import_id, "needs_review")
        return {"source_update": {"ok": True, "action": "needs_manual_review", "import_id": import_id}}

    return {"skipped": {"reason": "unknown_onboarding_action", "result": item}}


def normalize_onboarding_review(item: dict[str, Any], default_model: str) -> dict[str, Any]:
    nested = item.get("classification") if isinstance(item.get("classification"), dict) else {}
    return {
        "action": str(item.get("action") or item.get("decision") or "").strip().lower(),
        "selected_candidate_id": item.get("selected_candidate_id") or item.get("candidate_id"),
        "review_category": item.get("review_category") or item.get("coarse_category"),
        "inclusion_tier": item.get("inclusion_tier") or item.get("inclusion"),
        "source_attribute": item.get("source_attribute"),
        "primary_domain": nested.get("category") or item.get("primary_domain") or item.get("category"),
        "requires_user_confirmation": bool(item.get("requires_user_confirmation", False)),
        "reason": item.get("reason") or item.get("notes") or "",
        "confidence": nested.get("confidence", item.get("confidence", 0)),
        "method": nested.get("method") or item.get("method") or item.get("model") or default_model,
    }


def normalize_onboarding_classification(
    item: dict[str, Any],
    source_id: str,
    default_taxonomy: str,
    default_model: str,
) -> dict[str, Any] | None:
    nested = item.get("classification") if isinstance(item.get("classification"), dict) else {}
    category = nested.get("category") or item.get("category")
    if not category:
        return None
    tags = nested.get("tags", item.get("tags") or [])
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.split(",") if part.strip()]
    source_attribute = item.get("source_attribute")
    if source_attribute and source_attribute not in tags:
        tags.append(source_attribute)
    return {
        "entity_type": "source",
        "entity_id": source_id,
        "taxonomy": nested.get("taxonomy") or item.get("taxonomy") or default_taxonomy,
        "category": category,
        "tags": tags,
        "confidence": nested.get("confidence", item.get("confidence", 0)),
        "method": nested.get("method") or item.get("method") or default_model,
    }


def normalize_classification(item: dict[str, Any], default_taxonomy: str, default_model: str) -> dict[str, Any] | None:
    nested = item.get("classification") if isinstance(item.get("classification"), dict) else {}
    category = nested.get("category") or item.get("category")
    if not category:
        return None
    tags = nested.get("tags", item.get("tags") or [])
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.split(",") if part.strip()]
    return {
        "entity_type": item["entity_type"],
        "entity_id": item["entity_id"],
        "taxonomy": nested.get("taxonomy") or item.get("taxonomy") or default_taxonomy,
        "category": category,
        "tags": tags,
        "confidence": nested.get("confidence", item.get("confidence", 0)),
        "method": nested.get("method") or item.get("method") or default_model,
    }


def normalize_digest(item: dict[str, Any], default_model: str) -> dict[str, Any] | None:
    digest = item.get("digest")
    if not isinstance(digest, dict):
        return None
    article_id = digest.get("article_id") or (item.get("entity_id") if item.get("entity_type") == "article" else None)
    summary = digest.get("summary")
    if not article_id or not summary:
        return None
    return {
        "article_id": article_id,
        "summary": summary,
        "key_points": digest.get("key_points") or [],
        "importance_score": digest.get("importance_score") or 0,
        "reason": digest.get("reason"),
        "model": digest.get("model") or default_model,
    }


def compact_article(article: dict[str, Any], content_chars: int) -> dict[str, Any]:
    item = {
        key: article.get(key)
        for key in (
            "id",
            "source_id",
            "source_name",
            "source_status",
            "source_tier",
            "source_category",
            "source_tags",
            "title",
            "url",
            "digest",
            "publish_time",
            "crawl_status",
            "fetch_error",
        )
    }
    text = article.get("content_text") or article.get("content_markdown") or strip_html(article.get("content_html"))
    if text:
        item["content_excerpt"] = str(text)[:content_chars]
    return item


def compact_onboarding_candidate(
    candidate: dict[str, Any],
    raw_name: str,
    source: dict[str, Any] | None,
    article_limit: int,
) -> dict[str, Any]:
    probe = (candidate.get("raw_payload") or {}).get("article_probe")
    probe_articles = probe.get("articles") if isinstance(probe, dict) else []
    if not isinstance(probe_articles, list):
        probe_articles = []

    return {
        "candidate_id": candidate["id"],
        "candidate_name": candidate.get("candidate_name"),
        "wechat_fakeid": candidate.get("wechat_fakeid"),
        "biz": candidate.get("biz"),
        "intro": candidate.get("intro"),
        "score": candidate.get("score"),
        "decision": candidate.get("decision"),
        "display_exact_match": candidate.get("candidate_name") == raw_name,
        "normalized_match": names_equivalent(candidate.get("candidate_name"), raw_name),
        "name_similarity": name_similarity(candidate.get("candidate_name"), raw_name),
        "existing_source": compact_source(source),
        "latest_articles": [compact_probe_article(article) for article in probe_articles[:article_limit]],
    }


def compact_source(source: dict[str, Any] | None) -> dict[str, Any] | None:
    if not source:
        return None
    return {
        "source_id": source.get("id"),
        "name": source.get("name"),
        "status": source.get("status"),
        "tier": source.get("tier"),
        "intro": source.get("intro"),
    }


def compact_probe_article(article: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": article.get("title"),
        "digest": article.get("digest"),
        "publish_time": article.get("publish_time"),
        "url": article.get("url"),
        "content_fetch_ok": article.get("content_fetch_ok"),
        "content_fetch_error": article.get("content_fetch_error"),
    }


def taxonomy_to_dict(taxonomy: Taxonomy) -> dict[str, Any]:
    return {
        "name": taxonomy.name,
        "source_categories": [entry_to_dict(entry) for entry in taxonomy.source_categories],
        "article_categories": [entry_to_dict(entry) for entry in taxonomy.article_categories],
        "tag_groups": [
            {"id": group.id, "name_zh": group.name_zh, "tags": [entry_to_dict(tag) for tag in group.tags]}
            for group in taxonomy.tag_groups
        ],
    }


def source_expected_result(taxonomy: Taxonomy) -> dict[str, Any]:
    return {
        "entity_type": "source",
        "classification.category": [entry.id for entry in taxonomy.source_categories],
        "source_update.status": ["active", "inactive", "archived", "needs_review"],
        "source_update.tier": ["core", "normal", "long_tail"],
    }


def article_expected_result(taxonomy: Taxonomy) -> dict[str, Any]:
    return {
        "entity_type": "article",
        "classification.category": [entry.id for entry in taxonomy.article_categories],
        "digest.required": ["summary", "key_points", "importance_score", "reason", "model"],
    }


def onboarding_expected_result(taxonomy: Taxonomy) -> dict[str, Any]:
    return {
        "entity_type": ONBOARDING_JOB_ENTITY_TYPE,
        "action": ["accept_source", "ignore_non_finance", "reject_all", "needs_manual_review"],
        "selected_candidate_id": "candidate id, required only for accept_source",
        "review_category": list(ONBOARDING_REVIEW_CATEGORIES.keys()),
        "review_category_names": ONBOARDING_REVIEW_CATEGORIES,
        "inclusion_tier": ["core_finance", "finance_related", "exclude", "needs_review"],
        "source_attribute": sorted(SOURCE_ATTRIBUTE_TAGS),
        "requires_user_confirmation": "true only when the account or category needs human confirmation",
        "classification.category": [entry.id for entry in taxonomy.source_categories],
        "classification.tags": "taxonomy tag ids, including source_attribute tags when known",
        "classification.confidence": "0.0-1.0",
        "source_update.status": ["active", "inactive", "archived", "needs_review"],
        "source_update.tier": ["core", "normal", "long_tail"],
        "reason": "short Chinese explanation",
    }


def entry_to_dict(entry: TaxonomyEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "name_zh": entry.name_zh,
        "aliases_zh": list(entry.aliases_zh),
        "description_zh": entry.description_zh,
    }


def strip_html(value: Any) -> str | None:
    if not value:
        return None
    import html
    import re

    return html.unescape(re.sub(r"<[^>]+>", " ", str(value)))
