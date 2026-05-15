# Feed Config

`run feed --config` reads a JSON file for first-layer feed runs. The example file is:

```text
examples/feed-config.example.json
```

CLI flags override config values. This makes the config suitable as a stable daily-run file while still allowing small one-off changes from the command line.

## Shape

```json
{
  "storage": {
    "path": "./data/mpfeed.sqlite"
  },
  "downloader": {
    "base_url": "http://127.0.0.1:5001",
    "timeout": 30
  },
  "feed": {
    "tier": "all",
    "max_sources": 0,
    "count": 5,
    "full": true,
    "work_dir": "./work/feed"
  }
}
```

Top-level keys matching CLI option names are also accepted, but the grouped shape above is preferred for user-facing configs.

## Storage

| key | meaning |
|---|---|
| `storage.path` | SQLite database path. Equivalent to `--db`. For real runs, point it at a user-controlled local data path. |

## Downloader

| key | meaning |
|---|---|
| `downloader.base_url` | External downloader service URL. Equivalent to `--base-url`. |
| `downloader.timeout` | HTTP timeout in seconds. Equivalent to `--timeout`. |

The downloader service is user-operated. Keep login state outside the repository; `wechat-mp-feed` only calls the configured service URL.

## Feed

### Source Refresh

| key | default | meaning |
|---|---:|---|
| `tier` | `all` | Source tier to refresh: `all`, `core`, `normal`, or `long_tail`. |
| `max_sources` | `0` | Maximum active sources to refresh. `0` means all matching sources. |
| `count` | `5` | Article list count requested per source. |
| `begin` | `0` | Article list offset. |
| `retries` | `2` | Retries for article-list calls. |
| `backoff_seconds` | `3.0` | Backoff between article-list retries. |
| `delay_min` | `1.0` | Minimum delay between source-list calls. |
| `delay_max` | `3.0` | Maximum delay between source-list calls. |
| `no_delay` | `false` | Disable delays for local tests only. |

### Run Mode

| key | default | meaning |
|---|---:|---|
| `full` | `false` | Refresh article metadata, score articles, fetch retained content, then export files. |
| `skip_refresh` | `false` | Export from existing SQLite rows without calling the downloader. |
| `score_articles` | `false` | Run rules-based article scoring before export. |
| `fetch_retained_content` | `false` | Fetch content for retained articles. |

Use `full: true` for normal production-like feed runs. Use `skip_refresh: true` for offline inspection after a previous run.

### Scoring

| key | default | meaning |
|---|---:|---|
| `taxonomy` | `finance` | Taxonomy used for article scoring. |
| `score_limit` | `0` | Maximum articles to score. `0` means all current articles. |
| `min_score` | `0.0` | Minimum score required to save a rules digest. |

Current scoring is `rules_v1`. It provides initial retention decisions. Tune thresholds with real feedback.

### Content Fetch

| key | default | meaning |
|---|---:|---|
| `content_limit` | `0` | Maximum retained articles to fetch. `0` means all eligible articles. |
| `content_retention` | `content_or_archive` | Eligible retention levels: `content_or_archive`, `content`, `full_archive`, or `all`. |
| `content_retries` | `2` | Retries per content fetch. |
| `content_backoff_seconds` | `3.0` | Backoff between content retries. |
| `content_delay_min` | `3.2` | Minimum delay between content fetches. |
| `content_delay_max` | `6.0` | Maximum delay between content fetches. |
| `content_passes` | `3` | Internal passes over the same retained-content queue. |
| `content_pass_cooldown_seconds` | `30.0` | Cooldown between content passes. |

Content fetching uses a fixed queue and multiple passes. If the downloader returns a body-level retry hint such as `请 N 秒后重试`, the retry loop honors that hint.

## Outputs

| key | default | meaning |
|---|---|---|
| `work_dir` | `work/feed` | Directory for default outputs. |
| `feed_output` | `<work_dir>/feed-items.<format>` | Article-level feed rows. |
| `feed_format` | `csv` | `csv` or `json`. |
| `summary_output` | `<work_dir>/feed-summary.<format>` | Aggregate status summary. |
| `summary_format` | `json` | `json` or `csv`. |
| `failures_output` | `<work_dir>/feed-failures.<format>` | Rows where `crawl_status=content_failed`. |
| `failures_format` | `csv` | `csv` or `json`. |
| `feed_limit` | `3000` | Maximum exported feed rows. |

`feed-failures` is part of the normal workflow. It lets users distinguish temporary limits, deleted/restricted articles, and parser failures without digging into SQLite.

## Common Runs

Offline demo:

```bash
PYTHONPATH=packages/wechat_mp_feed/src python3 -m wechat_mp_feed.cli \
  --db ./work/demo-feed.sqlite \
  demo seed-feed \
  --work-dir ./work/demo-feed

PYTHONPATH=packages/wechat_mp_feed/src python3 -m wechat_mp_feed.cli \
  run feed \
  --config ./work/demo-feed/feed-config.demo.json
```

Real feed:

```bash
cp examples/feed-config.example.json ./work/feed-config.json

PYTHONPATH=packages/wechat_mp_feed/src python3 -m wechat_mp_feed.cli \
  run feed \
  --config ./work/feed-config.json
```

Override only the source count for a test run:

```bash
PYTHONPATH=packages/wechat_mp_feed/src python3 -m wechat_mp_feed.cli \
  run feed \
  --config ./work/feed-config.json \
  --max-sources 10
```
