# Architecture

`wechat-mp-feed` is the orchestration layer for a local, reviewable WeChat Official Account feed. It calls a user-operated downloader service through an adapter, normalizes account and article data, and stores feed data in SQLite.

## Layered Shape

```mermaid
flowchart TB
  User["User / Agent"] --> CLI["mpfeed CLI"]
  CLI --> Package["wechat_mp_feed package"]

  Package --> Importers["Importers<br/>CSV / JSON / URL / OCR"]
  Package --> Resolver["Resolver + Review Queue"]
  Package --> Registry["Source Registry"]
  Package --> Feed["Feed Runner"]
  Package --> Storage[("SQLite")]
  Package --> Classifier["Taxonomy + Scoring"]

  Feed --> Adapter["HTTP Adapter"]
  Adapter --> Downloader["User-operated downloader service"]
  Downloader --> WeChat["WeChat MP backend / article pages"]

  Importers --> Storage
  Resolver --> Storage
  Registry --> Storage
  Classifier --> Storage
  Feed --> Storage

  Storage --> Exports["feed-items / feed-summary / feed-failures"]
```

## Responsibilities

| layer | responsibility |
|---|---|
| Importers | Preserve raw account names, article URLs, screenshots, or recording OCR output. |
| Resolver | Search account candidates through the configured adapter and keep ambiguous matches reviewable. |
| Review Queue | Promote only confirmed candidates into the long-term `sources` registry. |
| Source Registry | Store canonical account identity, tier, status, fakeid, `__biz`, and optional classification. |
| Feed Runner | Refresh article metadata, run scoring, fetch retained content, and export feed files. |
| Storage | Keep source imports, candidates, sources, articles, content, assets, classifications, and digests in local SQLite. |
| Finance Pack | Provide the default taxonomy: `inclusion_tier + primary_domain + source_attribute`. |
| Adapters | Hide downloader-specific HTTP details behind stable internal calls. |

## Feed Layer Flow

```mermaid
flowchart LR
  A["Reviewed sources"] --> B["Refresh article metadata"]
  B --> C["Upsert articles"]
  C --> D["Score articles with taxonomy"]
  D --> E["Choose retention level"]
  E --> F["Fetch retained content"]
  F --> G["Store text, HTML, structure, image URLs"]
  G --> H["Export feed-items"]
  G --> I["Export feed-summary"]
  G --> J["Export feed-failures"]
```

The first-layer feed produces structured article rows, content availability status, failure reasons, and retention metadata. Application layers can use these outputs for digests, alerts, or research inboxes.

## Adapter Principle

Keep WeChat-specific access mechanisms behind adapters. The package exposes stable internal models; backend adapters use user-provided session credentials and conservative rate limits.

For the first production path, prefer a long-running HTTP downloader service adapter. The service owns login state, cookies, queueing, cache behavior, and backend-specific operational burden. `wechat-mp-feed` owns source registry, normalized storage, scheduling policy, classification, feed exports, and agent workflow integration.

Services such as `wechat-download-api` stay external. The package accesses them through a base URL and optional token.

## Review Boundary

```mermaid
flowchart TB
  Raw["Raw imported name or URL"] --> Search["Search candidates"]
  Search --> Strict{"Strict name match?"}
  Strict -->|yes| Confirmed["Can be accepted or classified"]
  Strict -->|no| Review["Manual/LLM review table"]
  Review --> Manual["User correction or article URL evidence"]
  Manual --> Search
  Confirmed --> Sources["sources registry"]
```

Search handles account identity matching. Account intros and latest articles provide classification evidence after identity is reviewed.

## Default Crawl Policy

- Core pool: smaller set, higher priority, more frequent checks.
- Normal pool: broader set, lower frequency.
- Long-tail pool: occasional checks.
- Full content extraction is triggered by source priority or article scoring.
- Failed content fetches are exported as a normal review artifact.

## Data Boundary

The package keeps source registry, article metadata, content records, classifications, and feed exports in local files chosen by the user. In production, account lists, screenshots or recordings, downloader credentials, article archives, SQLite databases, and generated `work/` outputs are private runtime data.
