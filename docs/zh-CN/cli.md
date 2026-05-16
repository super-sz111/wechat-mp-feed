# CLI 参考

命令名：`mpfeed`。

## 基本原则

- 命令可组合，默认写入本地文件和 SQLite。
- 导入、搜索、审核、采集分步骤执行，方便用户检查不确定匹配。
- 需要登录态的 downloader adapter 由用户显式配置。
- 大批量真实运行使用保守限频。

## 全局参数

```bash
mpfeed --db ./data/mpfeed.sqlite <command>
```

部分命令支持配置文件，例如 `run feed --config` 会读取 feed JSON 配置。

## `demo`

生成合成示例数据并离线导出 feed：

```bash
mpfeed --db ./work/demo-feed.sqlite demo seed-feed --work-dir ./work/demo-feed
mpfeed run feed --config ./work/demo-feed/feed-config.demo.json
```

输出：

```text
feed-items.csv
feed-summary.json
feed-failures.csv
```

## `import`

导入公众号线索。

```bash
mpfeed import csv accounts.csv --name-column name
mpfeed import json accounts.json --name-field name
mpfeed import urls article_urls.txt
mpfeed import url 'https://mp.weixin.qq.com/s?...'
```

截图/录屏 OCR：

```bash
mpfeed import images screenshots/*.png --ocr paddle
mpfeed import video wechat_accounts.mp4 --fps 2 --ocr paddle --min-occurrences 2 --names-output accounts.txt --raw-output ocr.json
mpfeed import video following.mp4 --fps 0.5 --ocr paddle --crop 220,0,900,2556 --scale-width 480 --names-output accounts.txt --raw-output ocr.json
```

OCR/视频依赖按需安装：

```bash
python3 -m pip install -e "packages/wechat_mp_feed[ocr]"
```

手机录屏 OCR 建议裁剪账号文字区域并降低帧图宽度：

```bash
--crop x,y,w,h
--scale-width 480
```

`--scale-width 480` 适合容器或 agent 运行时的快速验证；`--scale-width 720` 保留更多细节，适合正式全量接入。

## `resolve`

把导入名称或 URL 解析为公众号候选。

```bash
mpfeed resolve imports --source-type csv --limit 100
mpfeed resolve imports --source-type recording --query-variants --retry-empty
mpfeed resolve search '第一财经'
```

`--query-variants` 会追加规范化查询，用于处理 OCR 空格、标点、繁简或轻微字形差异。

## `review`

审核搜索候选并写入正式来源库。

```bash
mpfeed review list
mpfeed review accept <candidate_id> --tier core
mpfeed review reject <candidate_id>
mpfeed review apply reviewed.csv
mpfeed review auto-exact --source-type recording --finance-only --taxonomy finance
```

`review auto-exact --finance-only` 只自动提升名称严格匹配且金融相关的候选。其他行保留给 LLM 或人工审核。

## `export onboarding`

导出首次批量接入审核表。

```bash
mpfeed export onboarding --source-type recording --taxonomy finance --format csv > work/onboarding.csv
mpfeed export onboarding --source-type recording --view compact --taxonomy finance --format csv > work/onboarding-review.csv
```

审核表包含：

- OCR/list 名称；
- 匹配账号；
- 候选账号；
- 匹配类型；
- 简介和最新文章证据；
- 金融分类；
- 是否需要人工确认；
- 人工确认账号名、文章链接、分类和备注列。

## `llm`

导出/导入 agent-agnostic LLM jobs。

```bash
mpfeed llm export-onboarding-jobs --source-type recording --taxonomy finance --output work/onboarding-jobs.json
mpfeed llm import-results work/onboarding-results.json --model llm:agent

mpfeed llm export-jobs --entity-type article --taxonomy finance --output work/article-llm-jobs.json
mpfeed llm import-results work/article-llm-results.json --model llm:agent
```

账号分类输出应包含：

- `inclusion_tier`
- `classification.category`
- `source_attribute`
- `tags`
- `needs_manual_review`

文章分析输出应包含分类、摘要、重要性分数和原因。

## `collect`

采集文章列表和正文。

```bash
mpfeed collect latest --tier core --count 10 --delay-min 3 --delay-max 8
mpfeed collect content --tier core --limit 20 --delay-min 3 --delay-max 8
```

正文抓取会保存 text/html/markdown、正文结构、图片 URL 和图片在正文中的位置。

## `run onboarding`

首次批量接入的统一入口。

```bash
mpfeed run onboarding \
  --work-dir ./work/onboarding \
  --source-type onboarding \
  --video-file following.mp4 \
  --crop 220,0,900,2556 \
  --scale-width 480
```

流程：

```text
导入
-> 多轮搜索
-> 慢速重试空候选
-> latest article evidence
-> 导出 LLM onboarding jobs
-> 导入 LLM 结果
-> 导出 compact review table
```

审核表完成修改后，使用 review/apply 或后续 resolver 处理改动部分。

## `run feed`

第一层 feed 运行入口。

```bash
mpfeed run feed --config ./work/feed-config.json
```

`full: true` 会刷新文章列表、评分、抓取 retained 正文并导出：

```text
feed-items.csv/json
feed-summary.json/csv
feed-failures.csv/json
```

## `run agent-smoke`

离线验证 agent 是否能够运行 feed 层并读取输出。

```bash
mpfeed run agent-smoke --work-dir ./work/agent-smoke
```

输出：

```text
agent-smoke.sqlite
feed-items.csv
feed-summary.json
feed-failures.csv
article-llm-jobs.json
agent-smoke-report.md
```
