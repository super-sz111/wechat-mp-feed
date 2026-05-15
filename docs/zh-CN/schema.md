# 存储 Schema

`wechat-mp-feed` 默认使用本地 SQLite。后续如需更重的分析工作流，可以再增加 DuckDB 等分析型存储。

## 设计目标

- 原始导入数据和确认后的规范数据分开保存。
- 不确定账号匹配保留审核记录。
- 文章元数据和正文/图片资产分开保存。
- 通用 feed 字段和金融增强字段分层保存。

## 核心表

### `sources`

确认后的微信公众号来源。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | text pk | 内部稳定 id |
| `platform` | text | 默认 `wechat_mp` |
| `name` | text | 规范账号名 |
| `wechat_fakeid` | text nullable | downloader 使用的 fakeid/base64 id |
| `biz` | text nullable | 文章 URL 中的 `__biz` |
| `avatar_url` | text nullable | 头像 URL |
| `intro` | text nullable | 账号简介 |
| `status` | text | `active`、`inactive`、`archived`、`needs_review` |
| `tier` | text | `core`、`normal`、`long_tail` |
| `source_type` | text | `ocr`、`csv`、`json`、`article_url`、`manual`、`api` |

### `source_imports`

账号解析前的原始导入行。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | text pk | 导入项 id |
| `batch_id` | text | 导入批次 |
| `raw_name` | text nullable | OCR/CSV/list 名称 |
| `raw_url` | text nullable | 文章或账号 URL |
| `raw_payload` | json | 原始行、OCR 元数据或其他证据 |
| `source_type` | text | `ocr`、`csv`、`json`、`article_url`、`manual` |
| `status` | text | `pending`、`resolved`、`ignored`、`error` |

### `source_candidates`

搜索返回的候选公众号。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | text pk | 候选 id |
| `import_id` | text fk | 对应 `source_imports.id` |
| `candidate_name` | text | 候选账号名 |
| `wechat_fakeid` | text nullable | 候选 fakeid |
| `biz` | text nullable | 候选 `__biz` |
| `avatar_url` | text nullable | 头像 URL |
| `intro` | text nullable | 简介/签名 |
| `score` | real | 0-1 匹配分 |
| `decision` | text | `auto_accept`、`manual_accept`、`reject`、`pending` |
| `raw_payload` | json nullable | 原始 adapter payload |

### `articles`

文章元数据。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | text pk | 稳定文章 id |
| `source_id` | text fk | 对应来源 |
| `title` | text | 标题 |
| `url` | text unique | 原文链接 |
| `digest` | text nullable | 列表摘要 |
| `cover_url` | text nullable | 封面 URL |
| `publish_time` | timestamp nullable | 发布时间 |
| `crawl_status` | text | `metadata_only`、`content_ok`、`content_failed`、`deleted` |
| `retention_level` | text | `metadata`、`content`、`full_archive` |
| `archive_status` | text | `not_requested`、`pending`、`cached`、`failed` |

### `article_contents`

正文提取结果。

| 字段 | 类型 | 说明 |
|---|---|---|
| `article_id` | text pk/fk | 对应文章 |
| `content_html` | text nullable | 清洗后的 HTML |
| `content_text` | text nullable | 纯文本 |
| `content_markdown` | text nullable | Markdown |
| `content_structure` | json nullable | 按原文顺序排列的 text/image/video blocks |
| `fetch_error` | text nullable | 抓取失败原因 |
| `extracted_at` | timestamp | 提取时间 |

### `article_assets`

正文中的图片、视频和其他资产。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | text pk | 资产 id |
| `article_id` | text fk | 对应文章 |
| `asset_type` | text | `image`、`video`、`audio`、`iframe`、`file` |
| `url` | text | 远程 URL |
| `block_index` | integer nullable | 在 `content_structure` 中的位置 |
| `content_ref` | text nullable | 稳定引用，例如 `block:12` |
| `local_path` | text nullable | 本地缓存路径 |
| `metadata` | json nullable | 尺寸、封面、平台等元数据 |
| `download_status` | text | `url_only`、`cached`、`failed`、`unsupported` |

### `classifications`

账号或文章分类结果。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | text pk | 分类记录 id |
| `entity_type` | text | `source` 或 `article` |
| `entity_id` | text | source/article id |
| `taxonomy` | text | 例如 `default`、`finance` |
| `category` | text | 主分类 |
| `tags` | json | 多标签 |
| `confidence` | real | 0-1 置信度 |
| `method` | text | `rules_v1`、`llm:<agent-or-model>`、`manual` |

### `digests`

摘要和评分结果。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | text pk | digest id |
| `article_id` | text fk | 对应文章 |
| `summary` | text | 摘要 |
| `key_points` | json nullable | 要点 |
| `importance_score` | real | 0-1 重要性分数 |
| `reason` | text nullable | 重要性理由 |
| `model` | text nullable | 模型或 agent 标识 |

`importance_score` 用于文章保存层级和 digest 选择。阈值应结合误收、漏收、存储成本和用户反馈持续调整。

## 审核策略

- 原始名称先进入 `source_imports`。
- 搜索候选进入 `source_candidates`。
- 只有审核通过或严格匹配的账号进入 `sources`。
- 金融 onboarding 中，`review auto-exact --finance-only` 同时要求名称严格匹配和金融分类证据。
- 非严格匹配、低置信度、非金融或未解析行保留给 LLM/人工审核。

## Onboarding 导出

`export onboarding` 是基于导入项、候选、来源、文章证据和分类结果生成的审核视图。

关键规则：

- 最终 `matched_account` / `匹配账号` 是后续抓取的账号身份依据。
- `ocr_account` 只作为审计证据。
- `similar`、`different`、`unresolved` 行进入候选账号列，等待人工确认。
- 简介和最新文章用于分类证据，不放宽账号身份匹配。
