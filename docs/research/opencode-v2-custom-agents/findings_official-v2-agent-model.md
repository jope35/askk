# Findings: official OpenCode v2 agent model

- **Subtopic question:** What does OpenCode v2 call an agent, how does that differ from v1, where do official docs live, and how do built-in agents, custom agent files, and `AGENTS.md` relate conceptually?
- **As-of:** 2026-11-09 (live search/fetch). Do not treat this file as current after that date.
- **Scope:** Product identity, v2 meaning, official docs URLs, what an agent is, built-in vs custom, `AGENTS.md` vs agent markdown files conceptually, v2 announcement. File schema/frontmatter fields and CLI/invocation are out of scope.
- **Method:** `user-exa.web_search_exa` (5 calls) then `user-exa.web_fetch_exa` on cited pages. The fourth Exa search (GitHub org / changelog / 2.0 date) failed with Exa’s free MCP rate limit (`You've hit Exa's free MCP rate limit`). Fallback: `cursor.WebSearch` and `cursor.WebFetch` for that gap. Snippets were leads only; quotes below come from fetched pages.

## Key facts (with dates)

### Product identity

- OpenCode is an open-source AI coding agent (terminal UI, desktop app, web app; press also lists mobile and an SDK). MIT licensed. Canonical site: `https://opencode.ai`. Press page (fetched 2026-11-09) states the current version is OpenCode v2 and that `opencode.ai` is the source of truth for apps, install commands, docs, and releases.
- The company behind OpenCode is **Anomaly** (`https://anoma.ly`). Press lists SST as a *separate* Anomaly project (full-stack infra framework), not as the OpenCode product name. GitHub source of truth is [`anomalyco/opencode`](https://github.com/anomalyco/opencode) (homepage `https://opencode.ai`; created 2025-04-30; MIT; default branch `dev`). Docker example in v2 intro docs: `ghcr.io/anomalyco/opencode:2.0.0`.
- [`github.com/sst/opencode`](https://github.com/sst/opencode) still resolves. The fetched GitHub page is a thin landing that says “Contribute to anomalyco/opencode development” and reports 0 stars. That is consistent with an org move/redirect, but the fetch did not include an explicit “renamed from sst/opencode” notice.
- Press milestones (page dated by “Nov 2026: 220,000+ GitHub stars” and latest release 2026-11-06): first release Apr 2025 (`v0.0.1`); OpenCode 1.0 Oct 2025; OpenCode 2.0 **Sep 2026**. Latest release on the same page: **v2.2.6, 2026-11-06**.

### Where official docs live

Canonical docs (current product = v2), from `https://opencode.ai/llms.txt` and `https://opencode.ai/docs/llms.txt` (fetched 2026-11-09):

| Topic | Canonical HTML URL |
| --- | --- |
| Docs index / intro | https://opencode.ai/docs/ |
| Agents (built-in and custom) | https://opencode.ai/docs/agents/ |
| Instructions / `AGENTS.md` | https://opencode.ai/docs/instructions/ |
| Config (`agents`, `default_agent`) | https://opencode.ai/docs/config/ |
| Migrate from V1 | https://opencode.ai/docs/migrate-v1/ |
| Changelog | https://opencode.ai/changelog |
| Press kit | https://opencode.ai/press |
| Site/docs machine index | https://opencode.ai/llms.txt and https://opencode.ai/docs/llms.txt |
| Source | https://github.com/anomalyco/opencode |
| V2 changelog in repo | https://github.com/anomalyco/opencode/blob/dev/CHANGELOG.md |

Parallel `/v2/docs/...` URLs (e.g. `https://opencode.ai/v2/docs/agents`) served the same v2 content when fetched. `llms.txt` tells citers to use canonical HTML without `.md` and without requiring the `/v2/` prefix. Install still uses `https://opencode.ai/v2/install`. GitHub README install snippet (fetched 2026-11-09) uses that v2 install URL and `brew install anomalyco/tap/opencode-v2`.

### What “v2” means

- Product-level: OpenCode 2 is a **major overhaul**, not a docs-only bump. Official announcement: [OpenCode 2.0](https://anoma.ly/notes/opencode-2-0/) on Anomaly’s notes site (no publication date in the fetched HTML). User-facing 2.0 themes there: one auto-started local **background service** shared by TUI, web, and desktop; a **rewritten server API** and `@opencode/client`; **Code Mode** (`@opencode/codemode`); **background subagents** and background shell; plugins rewritten as 80+ internal plugins; `@opencode/sdk` to embed the same engine.
- Release engineering: GitHub PR [#48546](https://github.com/anomalyco/opencode/pull/48546) merged **2026-09-11** into the `v2` branch: isolated V2 stable publishing **starting at 2.0.0**, `@opencode/*` npm packages on `latest`, V1 `dev` branch left untouched. Press milestone is “Sep 2026: OpenCode 2.0”. Issue [#52184](https://github.com/anomalyco/opencode/issues/52184) (opened 2026-09-29) already refers to running `opencode v2.0.20`, so a 2.0 line existed in September 2026. Maintainer comment on that issue (2026-10-20): V2 notes live at `https://opencode.ai/changelog` and in the repo changelog, with website support in **2.0.28**.
- Runtime compatibility (migrate guide, fetched 2026-11-09): OpenCode 1 and 2 both use the `opencode` command and are **no longer installed side by side by default**. Three **intentional** breaking changes: new plugin API; new server API/clients; TUI config `tui.json(c)` → one global `cli.json`. Supported V1 agent definitions and `.opencode/` files are **intended to keep working**; converting to native v2 shape is optional.
- Agent-model config deltas (same migrate guide): singular `agent` and deprecated `mode` maps become `agents`; `prompt` → `system`; `disable` → `disabled`; `permission` → ordered `permissions`; `maxSteps` → `steps`; `task` permission action → `subagent`; `bash` → `shell`. Old `mode` map entries become **primary** agents.

### What an agent is in v2

Official Agents page definition: an agent is a **named assistant profile** that combines a system prompt, model preference, permissions, and display details.

Custom agents are first-class configuration, not only chat personas:

- Markdown files (global `~/.config/opencode/agents/<name>.md` or project `.opencode/agents/<name>.md`), body = system prompt; and/or
- JSONC `agents` entries in OpenCode config.

`mode` is conceptual placement, not a separate product: `primary` (main session agent; **default for a new custom agent**), `subagent` (child session via the `subagent` tool), or `all` (either). Subagents run with fresh context in foreground or **background** child sessions (v2 announcement + Agents page). Parent `subagent` permissions control who may be launched; the child uses its own permissions.

`default_agent` selects the primary agent when a session has not chosen one; if invalid, OpenCode uses `build`, then the first visible primary-capable agent. Sessions keep their stored agent; changing the setting does not rewrite existing sessions.

The selected **agent (or provider) system prompt is assembled first**; project `AGENTS.md` and other instruction sources are **added later**, not used as a substitute for the agent profile (Instructions page ordering).

### Built-in vs custom

Visible built-ins on the official v2 Agents page (fetched 2026-11-09):

| ID | Mode | Official purpose (paraphrase of table) |
| --- | --- | --- |
| `build` | `primary` | Default coding agent; tools and access outside the workspace allowed by default; sensitive env-file reads ask for approval |
| `plan` | `primary` | Explore/plan without editing normal project files; may write OpenCode plan files; shell remains permission-controlled |
| `general` | `subagent` | Research and multi-step work with broad tool access; **cannot launch more subagents** |
| `explore` | `subagent` | Search/read code or web sources without editing files |

Hidden built-ins: `compaction`, `title`, `summary` (maintenance; not user-selectable). Official statement: **“V2 has no built-in `scout` agent.”**

Custom agents: any additional named profile (Markdown and/or `agents` config). You can **override a built-in by reusing its ID**, or `disabled: true` to remove a built-in or custom agent from that layer of config. Config Agents section: override built-ins or define specialized agents with their own model, instructions, mode, and permissions.

**Conflict:** GitHub README (fetched 2026-11-09) documents only **two** Tab-switchable built-ins (`build`, `plan`) plus a `general` subagent, and does not mention `explore`. Prefer the v2 Agents doc table over the README for the v2 agent model.

### `AGENTS.md` vs agent markdown files (conceptual)

These are different artifacts in official v2 docs:

1. **Agent markdown files** (`.opencode/agents/<name>.md` or `~/.config/opencode/agents/<name>.md`) **are agents**: a reusable named profile. Preferred v2 location per migrate guide; v1 also discovered `agent/`, `mode/`, `modes/` (still discovered). Markdown body = that agent’s system prompt. Nested path becomes part of the agent ID (`team/reviewer.md` → `team/reviewer`).
2. **`AGENTS.md`** is **project/global instruction text**, not a named agent. Instructions page: persistent project guidance (build commands, architecture, conventions, verification). Loaded with other instruction sources after the agent’s system prompt. V2 discovers `AGENTS.md` only (no `CLAUDE.md` fallback). Migrate guide: existing `AGENTS.md` files stay in place as instruction files.

They stack: custom/built-in agent prompt first; `AGENTS.md` still applies to the session.

### V2 announcement

Primary announcement page: [OpenCode 2.0](https://anoma.ly/notes/opencode-2-0/) (Anomaly notes). Agent-relevant claim: **background subagents** so the primary agent can spawn work (including another model) and keep going. Breaking changes listed there match migrate: 1.0 plugins do not run; server API is different; `tui.json` moved. Upgrade path in the note: latest 1.x then `opencode upgrade --major`.

Press kit lists OpenCode 2.0 as a **Sep 2026** milestone. Site changelog (`https://opencode.ai/changelog`) and repo `CHANGELOG.md` (dev branch) are labeled as OpenCode V2 release notes; the fetched changelog HTML started at **v2.2.6 (2026-11-06)** and the fetched GitHub `CHANGELOG.md` excerpt went back to **v2.0.26 (2026-10-08)**, not to 2.0.0.

## Short exact quotes

> An agent combines a system prompt, model preference, permissions, and display details into a named assistant profile.

— [Agents](https://opencode.ai/v2/docs/agents), OpenCode v2 docs (fetched 2026-11-09)

> Hidden `compaction`, `title`, and `summary` agents perform maintenance and cannot be selected directly. V2 has no built-in `scout` agent.

— same page

> When omitted on a new custom agent, it defaults to `primary`

— same page, Modes / Mode option

> Override built-in agents or define specialized agents with their own model, instructions, mode, and permissions.

— [Config](https://opencode.ai/v2/docs/config), Agents section (fetched 2026-11-09)

> Add an `AGENTS.md` file to give OpenCode persistent project guidance.

— [Instructions](https://opencode.ai/v2/docs/instructions/) (fetched 2026-11-09)

> OpenCode V2 recognizes `AGENTS.md` only. It does not use `CLAUDE.md` as a fallback.

— same page

> The selected agent or provider system prompt is sent first. OpenCode then assembles initial instructions in this order:  
> 1. Agent or provider system prompt  
> …  
> 4. Global and project AGENTS.md files, then configured instructions

— same page, Ordering (whitespace collapsed)

> OpenCode 1 and OpenCode 2 both use the `opencode` command and are no longer installed side by side by default.

— [Migrate from V1](https://opencode.ai/v2/docs/migrate-v1/) (fetched 2026-11-09)

> Existing supported server config fields, agent definitions, command definitions, skills, and other files in `.opencode/` should continue to work without changes.

— same page

> The singular `agent` and deprecated `mode` maps become `agents`.

— same page, Agents and modes

> The preferred V2 location is: `.opencode/agents/<name>.md`

— same page, Agent files

> Existing `AGENTS.md` files stay in place.

— same page, Instruction files

> OpenCode is an open source AI coding agent. It’s available as a terminal-based interface, desktop app, or web app.

— [Intro](https://opencode.ai/v2/docs/) (fetched 2026-11-09)

> opencode.ai is the source of truth for OpenCode, the open source coding agent, including its apps, install commands, docs and releases. The current version is OpenCode v2.

— [Press](https://opencode.ai/press) (fetched 2026-11-09)

> OpenCode is an open source coding agent by Anomaly

— same page, short version

> Anomaly is the company behind OpenCode. It builds open source tools for developers. Other projects include SST and OpenTUI, all open source on GitHub.

— same page, About Anomaly (two adjacent paragraphs joined)

> Sep 2026: OpenCode 2.0

— same page, Milestones

> OpenCode 2.0 is a major overhaul.

— [OpenCode 2.0](https://anoma.ly/notes/opencode-2-0/) (fetched 2026-11-09)

> First, we've added background subagents. This allows the primary agent to kick off some work to another one while it continues.

— same page, Background Tasks

> Adds an isolated V2 stable release path starting at 2.0.0. V2 publishes the `@opencode/*` npm packages to `latest`, syncs release versions only to `v2`, and keeps V1's `dev` branch and package namespaces untouched.

— [feat(release): isolate v2 stable publishing #48546](https://github.com/anomalyco/opencode/pull/48546), merged 2026-09-11

> OpenCode includes two built-in agents you can switch between with the `Tab` key.

— [anomalyco/opencode README](https://github.com/anomalyco/opencode) (fetched 2026-11-09) — conflicts with the Agents doc’s four visible agents

> The source code is on GitHub under the MIT License.

— [llms.txt](https://opencode.ai/llms.txt) (fetched 2026-11-09); the same paragraph links GitHub to `https://github.com/anomalyco/opencode`

## Source URLs (page titles)

| Title | URL | Fetched | Role |
| --- | --- | --- | --- |
| Agents | https://opencode.ai/v2/docs/agents (canonical: https://opencode.ai/docs/agents/) | 2026-11-09 | Definition, built-ins, custom Markdown/JSONC, modes |
| Instructions | https://opencode.ai/v2/docs/instructions/ (canonical: https://opencode.ai/docs/instructions/) | 2026-11-09 | `AGENTS.md` vs agent prompt |
| Migrate from V1 | https://opencode.ai/v2/docs/migrate-v1/ (canonical: https://opencode.ai/docs/migrate-v1/) | 2026-11-09 | v1→v2 agent maps, agent files vs instruction files |
| Config | https://opencode.ai/v2/docs/config (canonical: https://opencode.ai/docs/config/) | 2026-11-09 | `default_agent`, `agents` config |
| Intro | https://opencode.ai/v2/docs/ (canonical: https://opencode.ai/docs/) | 2026-11-09 | Product one-liner; `ghcr.io/anomalyco/opencode` |
| Press | https://opencode.ai/press | 2026-11-09 | Anomaly/SST identity, v2 current, Sep 2026 2.0 milestone |
| OpenCode (llms.txt) | https://opencode.ai/llms.txt | 2026-11-09 | Canonical URLs, GitHub, “current version is OpenCode v2” |
| OpenCode V2 Documentation (docs llms.txt) | https://opencode.ai/docs/llms.txt | 2026-11-09 | Full v2 docs index |
| OpenCode 2.0 | https://anoma.ly/notes/opencode-2-0/ | 2026-11-09 | Official 2.0 announcement (background subagents, service, API) |
| anomalyco/opencode | https://github.com/anomalyco/opencode | 2026-11-09 | Official repo; README built-ins (partial vs docs) |
| Changelog | https://opencode.ai/changelog | 2026-11-09 | V2 release notes; v2.2.6 on 2026-11-06 |
| CHANGELOG.md | https://github.com/anomalyco/opencode/blob/dev/CHANGELOG.md | 2026-11-09 | “Release notes for OpenCode V2”; excerpt back to v2.0.26 (2026-10-08) |
| feat(release): isolate v2 stable publishing #48546 | https://github.com/anomalyco/opencode/pull/48546 | 2026-11-09 | 2.0.0 publishing path, merged 2026-09-11 |
| changelog: v2 releases have no published release notes #52184 | https://github.com/anomalyco/opencode/issues/52184 | 2026-11-09 | v2.0.20 existed by 2026-09-29; notes added ~2.0.28 |
| sst/opencode | https://github.com/sst/opencode | 2026-11-09 | Thin GitHub page pointing at anomalyco/opencode |
| v2.2.6 release | https://github.com/anomalyco/opencode/releases/tag/v2.2.6 | 2026-11-09 | Latest GitHub release 2026-11-06 |

Third-party pages (OpenCode School, BSWEN, gists, aggregators) appeared in search and were **not** used as evidence.

## What you could not confirm

- **Exact public tag/date of `v2.0.0`:** `https://github.com/anomalyco/opencode/releases/tag/v2.0.0` and `.../v2.0.1` returned **404**. Publishing PR #48546 (2026-09-11) plus press “Sep 2026” plus issue #52184 citing `v2.0.20` on 2026-09-29 show a 2.0 line in September 2026, not a calendar day for 2.0.0.
- **Publication date of** `https://anoma.ly/notes/opencode-2-0/` (no date in fetched HTML). Aggregators dated it around 2026-10-12; that is not a primary-source date.
- **Whether `sst/opencode` is an official rename** vs a stub/redirect. Fetched page is too thin to quote a rename. Official identity in 2026 is Anomaly / `anomalyco/opencode`; SST is a sibling Anomaly project on the press page.
- **A living, distinct v1 Agents document.** `https://opencode.ai/docs/agents/` search hits matched v2 content (including “V2 has no built-in scout”). Did not retrieve a frozen v1 agents page. V1 agent *shape* is documented on Migrate from V1, not a separate current agents guide.
- **Whether v1 officially shipped a built-in `scout`.** Only official fetched sentence is that v2 has none. Third-party claims that v1 included `scout` were not verified on a fetched official v1 page.
- **Why GitHub README omits `explore`.** Possible stale README vs docs; not explained on fetched pages.
- **Default custom-agent `mode` in v1.** v2 docs say new custom agents default to `primary`. A third-party gist claimed v1 defaulted to `all`; not confirmed on official pages.
- **Full official changelog back to 2.0.0.** Fetched `CHANGELOG.md` excerpt ended at v2.0.26 (2026-10-08). Issue #52184 states early v2 GitHub releases had empty notes until ~2.0.28.

## Tooling note

Exa `web_search_exa` call for GitHub org / changelog / 2.0 date failed with free MCP rate limit. That lookup used Cursor `WebSearch`/`WebFetch`. All quotes above still come from fetched page bodies, not from search snippets.
