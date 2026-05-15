# Platform Compatibility

The canonical skill package is:

```text
skills/wechat-mp-feed/
```

It follows the common Agent Skills shape:

```text
wechat-mp-feed/
├── SKILL.md
├── agents/openai.yaml
└── references/
```

## Claude Code

Claude Code discovers skills from:

```text
~/.claude/skills/
.claude/skills/
```

Install by copying or symlinking the canonical folder:

```bash
mkdir -p .claude/skills
cp -R skills/wechat-mp-feed .claude/skills/wechat-mp-feed
```

Use a project-scoped install (`.claude/skills`) when the skill should travel with this repository. Use a personal install (`~/.claude/skills`) when the user wants the skill available across projects.

## Codex

Codex discovers user skills from the configured Codex skills directory, commonly:

```text
~/.codex/skills/
```

Install by copying or symlinking:

```bash
mkdir -p ~/.codex/skills
cp -R skills/wechat-mp-feed ~/.codex/skills/wechat-mp-feed
```

The `agents/openai.yaml` file provides UI-facing metadata for Codex-style skill lists.

## Other Agents

If the agent supports `SKILL.md` discovery, copy the canonical folder into that agent's skill directory.

For agents with manual skill registration, register `SKILL.md` as the tool/workflow instruction document and expose the repository path plus `mpfeed` CLI in the agent's environment.

Minimum requirement for any agent:

1. It can run shell commands in the project environment.
2. It can read generated files under `work/`.
3. It can preserve private paths and credentials outside the public repo.
4. It reports failures with enough context for review.

## First Validation

After installing into any agent system, ask the agent to:

```text
Use the wechat-mp-feed skill to run the offline smoke test and summarize the report.
```

The agent should run:

```bash
mpfeed run agent-smoke --work-dir ./work/agent-smoke
```

Then it should read:

```text
work/agent-smoke/agent-smoke-report.md
work/agent-smoke/feed-summary.json
work/agent-smoke/feed-failures.csv
work/agent-smoke/article-llm-jobs.json
```
