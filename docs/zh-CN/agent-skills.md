# Agent Skill 包

`wechat-mp-feed` 现在有一个正式的通用 agent skill 包：

```text
skills/wechat-mp-feed/
```

适用对象包括 Claude Code、Codex 风格 skill loader，以及其他可以注册 markdown workflow instructions 的 agent 系统。

Skill 是这个项目的一等入口。CLI 负责执行，Skill 负责告诉 agent 操作顺序：跑什么命令、读哪些输出、遇到登录失效如何处理，以及如何从 feed 数据进入金融投研工作流。

## Skill 做什么

这个 skill 告诉 agent 如何：

- 运行离线 feed smoke test；
- 从名单、截图、录屏或文章链接批量接入首次公众号列表；
- 调用 `mpfeed run feed --config`；
- 读取 feed 健康状态和失败表；
- 导出文章级 LLM jobs；
- 使用用户配置的本地路径保存公众号名单、录屏、downloader 凭据和数据库；
- 在 feed 层之上构建金融研究 inbox / digest。

## Agent 操作约定

使用这个 skill 的 agent 应当：

- 把 `mpfeed` 作为主要操作入口；
- 使用 `agent-smoke` 验证运行环境；
- 首次接入时使用分阶段审核表处理账号身份和分类；
- 以审核后的来源库作为账号身份依据；
- 基于 `feed-summary` 汇报 feed 健康状态；
- 基于 `feed-failures` 判断重试范围；
- 使用 article LLM jobs 执行文章语义分析；
- downloader 登录失效时清楚提示扫码需求；
- 把生成文件保存在用户控制的本地路径。

## 包结构

```text
skills/wechat-mp-feed/
├── SKILL.md
├── agents/openai.yaml
└── references/
```

`SKILL.md` 保持简洁，细节放在 `references/` 里，agent 需要时再读取。

## 不同平台

- Claude Code：复制到 `.claude/skills/wechat-mp-feed/` 或 `~/.claude/skills/wechat-mp-feed/`。
- Codex 风格 loader：复制到 `~/.codex/skills/wechat-mp-feed/` 或配置的 skills 目录。
- 其他 agent：支持 `SKILL.md` 的系统可直接复制目录；手动注册型系统可把 `SKILL.md` 注册成工作流说明，并确保 agent 能运行 `mpfeed`。

## 第一次验证

让 agent 执行：

```text
Use the wechat-mp-feed skill to run the offline smoke test and summarize the report.
```

agent 应该运行：

```bash
mpfeed run agent-smoke --work-dir ./work/agent-smoke
```

然后读取：

```text
work/agent-smoke/agent-smoke-report.md
work/agent-smoke/feed-summary.json
work/agent-smoke/feed-failures.csv
work/agent-smoke/article-llm-jobs.json
```
