# Feed Workflows

## Offline Agent Smoke Test

Run:

```bash
mpfeed run agent-smoke --work-dir ./work/agent-smoke
```

Inside a virtualenv-based workspace, the fallback command is:

```bash
.venv/bin/mpfeed run agent-smoke --work-dir ./work/agent-smoke
```

Expected outputs:

```text
agent-smoke.sqlite
feed-items.csv
feed-summary.json
feed-failures.csv
article-llm-jobs.json
agent-smoke-report.md
```

Agent checklist:

1. Read `agent-smoke-report.md`.
2. Confirm counts in `feed-summary.json`.
3. Explain each row in `feed-failures.csv`.
4. Confirm `article-llm-jobs.json` is suitable for article-level semantic analysis.
5. Tell the user this is synthetic data and real deployment needs a private reviewed source registry.

## Real Feed Run

Use a config file:

```bash
mpfeed run feed --config ./work/feed-config.json
```

Virtualenv fallback:

```bash
.venv/bin/mpfeed run feed --config ./work/feed-config.json
```

The config should point to the user's private SQLite database and downloader base URL. Keep generated feed outputs under `work/` or another ignored/private directory.

Expected outputs:

```text
feed-items.csv/json
feed-summary.json/csv
feed-failures.csv/json
```

If the command reports downloader auth failure:

1. Show the login URL if present.
2. Ask the user to scan the QR code.
3. Retry the same command after login.

## Onboarding

For first-time account setup:

```bash
mpfeed import csv accounts.csv --name-column name
mpfeed resolve imports --source-type csv --limit 100
mpfeed export candidates --format csv
mpfeed review accept <candidate_id> --tier core
```

For larger runs with recordings or names:

```bash
mpfeed run onboarding --work-dir ./work --source-type onboarding
```

Identity rule:

- The final matched account in the user-reviewed table is the source of truth.
- OCR names are audit evidence only.
- Keep distinct account names separate unless the user explicitly requests an alias merge.

## Article LLM Jobs

Export article jobs:

```bash
mpfeed llm export-jobs \
  --entity-type article \
  --taxonomy finance \
  --output ./work/article-llm-jobs.json
```

Import results:

```bash
mpfeed llm import-results ./work/article-llm-results.json --model llm:agent
```

Agent results should include classification, digest, importance score, and reason. Low-signal articles such as recruiting, events, product marketing, and boilerplate market wrap text should stay below normal digest thresholds unless they contain reusable research logic.
