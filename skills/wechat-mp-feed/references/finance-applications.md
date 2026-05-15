# Finance Research Applications

The first finance application layer is a research inbox built from feed outputs.

## Research Inbox V0

Inputs:

- `feed-items`
- article content and fetch status
- source classification: `inclusion_tier + primary_domain + source_attribute`
- article LLM jobs/results

Outputs:

- high-signal article list;
- low-signal suppression reasons;
- Chinese summaries;
- theme tags;
- importance score and reason;
- manual-review flags.

## Scoring Guidance

Raise priority for:

- durable deep research;
- policy interpretation with asset implications;
- earnings or company updates with clear marginal changes;
- industry tracking with data, price, supply-demand, or competitive structure;
- risk events;
- cross-asset macro or strategy pieces.

Lower priority for:

- recruiting, internships, job collections;
- events, courses, webinars, roadshow marketing;
- product sales and account promotion;
- generic market wrap with no reusable analysis;
- deleted/restricted articles with insufficient evidence.

Use source context as a prior. Core sources can still publish low-signal articles.

## User Feedback Loop

After producing a first inbox:

1. Ask which high-score articles were low value.
2. Ask which missed articles should have been included.
3. Update taxonomy, tags, prompts, or thresholds.
4. Track whether the importance score needs adjustment over time.

Keep scoring rules auditable. If an LLM changes importance, require a short reason that can be reviewed later.
