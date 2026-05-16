---
name: wechat-mp-feed
description: Operate the wechat-mp-feed local-first WeChat Official Account source registry and article feed toolkit. Use when an agent needs to import/review WeChat Official Account sources, run the first-layer feed, inspect feed health/failures, export article LLM jobs, validate agent integration, or build finance research inbox/digest workflows from mpfeed outputs.
---

# WeChat MP Feed

Use this skill to operate the `wechat-mp-feed` project through its CLI. This is the primary agent-facing interface for the project.

The agent's job is to onboard large account lists, run the feed layer, inspect outputs, explain failures, prepare LLM jobs, and build finance research workflows while keeping private runtime data in the user's configured local paths.

## Core Rules

- Treat `mpfeed` as the operational interface. Edit SQLite directly only when the user asks for database surgery.
- Store account lists, recordings, screenshots, downloader credentials, raw article archives, and personal digests only in user-controlled local paths.
- Describe this as a local feed toolkit that works with user-operated downloader services.
- Use conservative delays for real downloader runs. Reserve `--no-delay` for small local tests.
- For identity matching, only accepted/reviewed sources should enter feed collection. Keep distinct accounts separate unless the user explicitly asks for a merge.
- If downloader health/auth fails, report the login URL or required user action instead of aggressive retries.

## Quick Decision

Use `mpfeed` when it is on `PATH`. In virtualenv-based workspaces, `.venv/bin/mpfeed` is the fallback command.

1. **Agent integration test**: run `mpfeed run agent-smoke --work-dir ./work/agent-smoke`.
2. **First-time source onboarding**: use `run onboarding` for large account lists, recordings, screenshots, or article URL batches.
3. **Real feed run**: run `mpfeed run feed --config ./work/feed-config.json`.
4. **Article semantic analysis**: use `llm export-jobs --entity-type article` and import results with `llm import-results`.
5. **Finance research application**: read the feed outputs first, then build a research inbox/digest above the feed layer.

## Required Agent Flow

1. Run `mpfeed run agent-smoke --work-dir ./work/agent-smoke` for first validation.
2. For first-run account setup, run staged onboarding and export the review table.
3. Ask the user to review only unresolved identity rows, uncertain classifications, or manual corrections.
4. For real feed runs, use `mpfeed run feed --config ./work/feed-config.json`.
5. Read `feed-summary.json` before reporting health.
6. Read `feed-failures.csv` before recommending retries or login refresh.
7. Export `article-llm-jobs.json` before article-level semantic analysis.
8. Use the finance taxonomy references when building inbox or digest output.

## Essential Commands

```bash
mpfeed --help
mpfeed run agent-smoke --work-dir ./work/agent-smoke
mpfeed run onboarding --work-dir ./work/onboarding --source-type onboarding
mpfeed run feed --config ./work/feed-config.json
mpfeed export feed-summary --format json
mpfeed export feed --format json --limit 100
mpfeed llm export-jobs --entity-type article --output ./work/article-llm-jobs.json
```

Virtualenv fallback command:

```bash
.venv/bin/mpfeed run agent-smoke --work-dir ./work/agent-smoke
```

Offline validation output:

```text
feed-items.csv
feed-summary.json
feed-failures.csv
article-llm-jobs.json
agent-smoke-report.md
```

When reporting results to the user, mention:

- source/article/digest counts from `feed-summary`;
- failed content rows and `fetch_error`;
- whether article LLM jobs are ready;
- concrete next step, such as login refresh, retry later, or run finance inbox analysis.

## References

Read only the reference needed for the task:

- Platform installation and compatibility: `references/platforms.md`
- Feed/onboarding operations: `references/feed-workflows.md`
- Finance research inbox and digest layer: `references/finance-applications.md`
