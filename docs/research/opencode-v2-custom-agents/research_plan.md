# Research plan: OpenCode v2 custom agent definitions

## Main question

How do you define and use custom agents in OpenCode v2 (file format, location, fields, and invocation)?

## As-of date

2026-11-09. OpenCode v2 is recent; prefer current official docs over older v1 blog posts.

## Tool mapping

- search: `user-exa.web_search_exa` (question-style queries, `numResults` 5–10)
- read: `user-exa.web_fetch_exa` (fetch pages that will be cited; snippets are leads only)
- fallback: `cursor.WebSearch` / `cursor.WebFetch` only if Exa fails on auth, quota, or rate limit (name the failure once)

## Subtopics (investigation order)

1. **Official v2 agent model** — What OpenCode v2 calls an agent, how it differs from v1, and where official docs live.
   - Evidence required: product/docs URLs, version notes, the official name for custom agents, built-in vs custom agents, markdown vs JSON config.

2. **Definition format and placement** — How to author a custom agent file (schema, required/optional fields, directories, project vs global).
   - Evidence required: file paths (`AGENTS.md`, `.opencode/agent/`, `opencode.json`), frontmatter fields (`mode`, `model`, `tools`, `permission`, `temperature`, `description`, `color`), examples from primary docs.

3. **Using and invoking custom agents** — How a user actually runs, switches, or delegates to a custom agent in v2 (TUI, CLI flags, `@` mentions, default agent, primary vs subagent).
   - Evidence required: invocation commands/keys, when an agent is primary vs subagent, how the main agent calls custom agents, limitations.

Do not overlap: (1) is conceptual/versioning, (2) is file/schema authoring, (3) is runtime usage.

## Synthesis

Combine into a practical how-to: where to put files, what to put in them, and how to invoke the resulting agents. Prefer OpenCode official docs (`opencode.ai`, GitHub `sst/opencode` or `anomalyco/opencode`) over third-party blogs. When sources disagree, report both and prefer the current official docs page.
