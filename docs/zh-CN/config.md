# Feed 配置说明

`run feed --config` 使用 JSON 配置文件运行第一层文章流。示例文件是：

```text
examples/feed-config.example.json
```

命令行参数优先级高于配置文件。也就是说，日常运行可以固定用一份配置，临时测试时只在命令行覆盖少量参数。

## 基本结构

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

代码也支持把 CLI 参数名直接放在顶层，但面向用户的配置建议使用上面这种分组结构。

## 存储

| 字段 | 含义 |
|---|---|
| `storage.path` | SQLite 数据库路径，等价于 `--db`。真实数据库应放在仓库外或被 `.gitignore` 排除。 |

## Downloader

| 字段 | 含义 |
|---|---|
| `downloader.base_url` | 外部 downloader 服务地址，等价于 `--base-url`。 |
| `downloader.timeout` | HTTP 超时时间，单位秒，等价于 `--timeout`。 |

downloader 由用户自行部署和登录。登录态由 downloader 或用户配置的本地环境管理；`wechat-mp-feed` 通过 base URL 和可选 token 调用已配置的服务。

## Feed 阶段

### 刷新文章列表

| 字段 | 默认值 | 含义 |
|---|---:|---|
| `tier` | `all` | 要刷新的来源层级：`all`、`core`、`normal`、`long_tail`。 |
| `max_sources` | `0` | 最多刷新多少个 active source，`0` 表示全部。 |
| `count` | `5` | 每个公众号拉取多少篇文章元数据。 |
| `begin` | `0` | 文章列表起始偏移。 |
| `retries` | `2` | 文章列表请求重试次数。 |
| `backoff_seconds` | `3.0` | 文章列表重试间隔。 |
| `delay_min` | `1.0` | 公众号之间的最小等待秒数。 |
| `delay_max` | `3.0` | 公众号之间的最大等待秒数。 |
| `no_delay` | `false` | 仅用于本地测试，关闭等待。 |

### 运行模式

| 字段 | 默认值 | 含义 |
|---|---:|---|
| `full` | `false` | 刷新文章列表、评分、抓取 retained 正文、导出文件。 |
| `skip_refresh` | `false` | 不调用 downloader，只从现有数据库导出。 |
| `score_articles` | `false` | 只额外执行文章评分。 |
| `fetch_retained_content` | `false` | 只额外抓取 retained 正文。 |

完整 feed 运行使用 `full: true`。已有抓取结果、仅需重新导出时，使用 `skip_refresh: true`。

### 评分

| 字段 | 默认值 | 含义 |
|---|---:|---|
| `taxonomy` | `finance` | 文章评分使用的分类体系。 |
| `score_limit` | `0` | 最多评分多少篇文章，`0` 表示全部。 |
| `min_score` | `0.0` | 保存 rules digest 的最低分数。 |

当前评分是 `rules_v1`，用于初始保存层级。重要性分数和阈值后续需要结合误收、漏收、存储成本和用户反馈持续调整。

### 正文抓取

| 字段 | 默认值 | 含义 |
|---|---:|---|
| `content_limit` | `0` | 最多抓取多少篇 retained 文章，`0` 表示全部。 |
| `content_retention` | `content_or_archive` | 可抓取的保存层级：`content_or_archive`、`content`、`full_archive`、`all`。 |
| `content_retries` | `2` | 单篇正文抓取重试次数。 |
| `content_backoff_seconds` | `3.0` | 正文抓取重试间隔。 |
| `content_delay_min` | `3.2` | 正文请求之间的最小等待秒数。 |
| `content_delay_max` | `6.0` | 正文请求之间的最大等待秒数。 |
| `content_passes` | `3` | 对同一批待抓取文章做几轮 pass。 |
| `content_pass_cooldown_seconds` | `30.0` | 两轮 pass 之间的等待秒数。 |

正文抓取使用固定队列和多轮 pass。遇到正文接口返回类似 `请 N 秒后重试` 的提示时，会按提示等待后再继续。

## 输出

| 字段 | 默认值 | 含义 |
|---|---|---|
| `work_dir` | `work/feed` | 默认输出目录。 |
| `feed_output` | `<work_dir>/feed-items.<format>` | 文章流明细。 |
| `feed_format` | `csv` | `csv` 或 `json`。 |
| `summary_output` | `<work_dir>/feed-summary.<format>` | 汇总统计。 |
| `summary_format` | `json` | `json` 或 `csv`。 |
| `failures_output` | `<work_dir>/feed-failures.<format>` | 正文失败文章表。 |
| `failures_format` | `csv` | `csv` 或 `json`。 |
| `feed_limit` | `3000` | 最多导出多少行 feed。 |

`feed-failures` 是正式输出的一部分，用来区分临时限流、文章删除/受限、解析失败等情况。

## 常用运行方式

离线 demo：

```bash
PYTHONPATH=packages/wechat_mp_feed/src python3 -m wechat_mp_feed.cli \
  --db ./work/demo-feed.sqlite \
  demo seed-feed \
  --work-dir ./work/demo-feed

PYTHONPATH=packages/wechat_mp_feed/src python3 -m wechat_mp_feed.cli \
  run feed \
  --config ./work/demo-feed/feed-config.demo.json
```

真实 feed：

```bash
cp examples/feed-config.example.json ./work/feed-config.json

PYTHONPATH=packages/wechat_mp_feed/src python3 -m wechat_mp_feed.cli \
  run feed \
  --config ./work/feed-config.json
```

临时只测 10 个 source：

```bash
PYTHONPATH=packages/wechat_mp_feed/src python3 -m wechat_mp_feed.cli \
  run feed \
  --config ./work/feed-config.json \
  --max-sources 10
```
