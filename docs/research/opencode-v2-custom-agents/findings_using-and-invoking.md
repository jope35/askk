# Findings: using and invoking custom agents in OpenCode v2

**Subtopic question:** How do you use and invoke custom agents in OpenCode v2 at runtime (TUI, CLI, switching agents, @mentions, default agent, primary vs subagent, Task tool / delegation)?

**As-of date:** 2026-11-09. Product version advertised on the Terminal page: OpenCode v2.2.6 (changelog dated 2026-11-06).

**Method:** Live search/fetch only. Primary sources: `opencode.ai/v2/docs/*` and GitHub `anomalyco/opencode`. One Exa search call failed on the free MCP rate limit (named below); remaining gaps used Cursor `WebSearch` / `WebFetch`.

---

## How to switch / select an agent

### Full-screen TUI (interactive)

Launch the TUI with `opencode` from a project directory. Agent selection is a session-level primary-agent choice, not a per-message picker of subagents.

Documented ways to change the **primary** agent:

| Mechanism | What the v2 docs say |
| --- | --- |
| **Shift+Tab** | Cycle agents. TUI: “Press Shift+Tab to cycle agents.” Keybinds: `agent.cycle` default `shift+tab` (“Next agent”). Reverse cycle (`agent.cycle.reverse`) defaults to `none` (unbound). |
| **Ctrl+X then A** | Open the agent picker. TUI: “Press Ctrl+X, then A to choose an agent.” Leader key defaults to Ctrl+X. Keybinds: `agent.list` default `<leader>a`. |
| **`/agents`** | TUI lists `/agents` among common slash commands, alongside `/models`. Type `/` to filter and Enter to run. |
| **Ctrl+P command palette** | “Press Ctrl+P to open the command palette for every action available in the current view.” |

**Tab is not the agent-cycle key in v2.** Keybinds bind `prompt.autocomplete.complete` to `tab` (complete autocomplete, documented as file `@` context) and `session.tab.next` to `ctrl+tab`. Bare Tab is therefore autocomplete, not agent switching. Older v1 / community writeups that say “press Tab to cycle agents” do not match the v2 TUI and keybinds pages.

The Terminal product page (v2) independently states: “Switch agents with shift+tab and open every command with ctrl+p.”

Session **tabs** (Ctrl+Tab / Ctrl+Shift+Tab) are unrelated: they move between open session tabs, not agents.

### Child / subagent navigation (after a subagent is already running)

These do not select the session’s primary agent. They move among parent and child sessions:

| Keybind ID | Default | Description (v2 Keybinds) |
| --- | --- | --- |
| `session.child.first` | `down` | Toggle subagent picker |
| `session.child.next` | `right` | Go to next child session |
| `session.child.previous` | `left` | Go to previous child session |
| `session.parent` | `up` | Go to parent session |
| `composer.subagent.up` / `.down` | `up` / `down` | Previous / next subagent |
| `composer.subagent.select` | `return` | Navigate to subagent |
| `composer.subagent.interrupt` | `ctrl+d` | Interrupt subagent |

### Slash commands that pin an agent for a prompt

Custom `/commands` can set `agent` in frontmatter or JSON. When you run the command, OpenCode may switch the current session to that agent, or spawn a child, depending on `subagent` and the agent’s `mode` (see Delegation below).

Example from the Commands guide:

```md
---
agent: plan
---

Plan $ARGUMENTS.
```

“Running `/plan migration` switches the current session to `plan` before submitting the prompt.”

### CLI flags (`--agent`)

| Entry point | Official v2 docs | Extra evidence |
| --- | --- | --- |
| **`opencode run --agent <id>`** | Documented. Example: `opencode run --agent build "Fix the failing test"`. | GitHub `packages/cli/src/commands/commands.ts` on `dev` (Exa snippet, 2026-11-09): `agent: Flag.String("agent")` on `run`. |
| **`opencode mini --agent <id>`** | Intro: “Run `opencode mini --help` to see its session, model, **agent**, prompt, and replay options.” The Commands page’s mini examples show `--continue`, `--model`, `--prompt`, `--session` but not `--agent`; help is the documented source for the flag. | Same `commands.ts` snippet: `mini` also has `agent: Flag.String("agent")`. GitHub issue #56842 (2026-10-18): `opencode mini --agent plan` is accepted. |
| **Root TUI `opencode --agent <id>`** | **Not documented** on the v2 CLI Intro or TUI pages. Those pages document `opencode`, `opencode ~/code/my-project`, `--standalone`, and `--server` only. | GitHub issue [v2: root TUI no longer accepts --agent](https://github.com/anomalyco/opencode/issues/56842) (opened 2026-10-18, last activity in the fetched page 2026-10-21, still **open** in that snapshot). Reporter on **2.0.32**: `opencode --agent plan` is rejected; `opencode mini --agent plan` works. Bot confirmed only `run` and `mini` define `agent`. Workaround quoted: `opencode mini --agent <id> --prompt "…"`. |
| **`--auto`** | Commands: `opencode run --auto "Fix the failing test"` — “Auto-approve permissions that are not explicitly denied.” Terminal page: “Run with `--auto` to allow every action you haven’t denied.” | |

**`--agent` requires a primary-capable agent.** GitHub issue #44751 quotes run-mode output:

```text
! agent "probe-sub" is a subagent, not a primary agent. Falling back to default agent
```

An Exa snippet of `packages/opencode/src/cli/cmd/run.ts` (dev, 2026-11-09) showed the same two warnings: agent not found → fall back; `entry.mode === "subagent"` → fall back. A later direct fetch of that blob URL returned **404**, so treat the file path as possibly moved; the fallback *behavior* is independently quoted in issue #44751.

### Other CLI discovery

v2 Commands documents `opencode debug agents` (no description beyond the heading “Provides debugging and troubleshooting tools”). The v2 Commands page does **not** list a user-facing `opencode agent create` / `opencode agent list` command. Those appear on older `dev.opencode.ai/docs/cli/` pages (v1-style) and should not be assumed present in v2.

---

## Primary vs subagent mode (how it affects usage)

From [Agents](https://opencode.ai/v2/docs/agents/):

| Mode | Behavior | Who invokes it |
| --- | --- | --- |
| `primary` | “Runs as the main agent for a session. This is the default for a new custom agent.” | User: Shift+Tab / `/agents` / Ctrl+X A / `default_agent` / `opencode run --agent` / command `agent:` that stays in the current session. |
| `subagent` | “Runs only in a child session through the `subagent` tool.” | The **main (parent) agent** via the `subagent` tool, or a slash command that selects that agent (child session unless `subagent: false`). The user cannot make it the session primary via Tab cycle. |
| `all` | “Runs either as a primary agent or a subagent.” | Both paths. |

Supporting rules from the same page:

- “Subagents run with fresh context in foreground or background child sessions.”
- “The parent agent's `subagent` permissions control which agents it may launch; the child uses its own configured permissions.”
- Built-in **visible** agents: `build` (primary), `plan` (primary), `general` (subagent), `explore` (subagent).
- Hidden maintenance agents `compaction`, `title`, and `summary` “cannot be selected directly.”
- “A session stores its selected model separately. Selecting a primary agent by ID does not change that model.”
- A subagent uses its configured model, or inherits the parent session’s model when none is configured.

**User-facing consequence:** Shift+Tab / the agent list cycle **primary-capable, visible** agents (`primary` or `all`, not `hidden`). Subagents (`general`, `explore`, and custom `mode: subagent`) are not the thing you Tab onto; the primary agent launches them.

**Conflict to flag:** the Tools page says of the `subagent` tool, “Only subagent-mode agents can be used.” The Agents page says `mode: all` can also run as a subagent. Official docs disagree on whether `all` is legal input to the `subagent` tool.

---

## How to @mention or delegate to a custom agent

### What v2 officially documents (use these)

**1. Ask the primary agent in natural language.** Agents page example after defining a `reviewer` subagent:

```text
Use the reviewer subagent to review my current changes.
```

`description` on the subagent matters because “OpenCode shows it to the model choosing which agent to launch.”

**2. The parent model calls the `subagent` tool (v1 name: Task).** Tools page, “Automation → Subagent”:

- Tool name: **`subagent`** (v1 `task` / Task tool was renamed; Permissions: “In V2, use `permissions`, `shell`, and `subagent` instead of `permission`, `bash`, and `task`.”).
- Inputs: agent ID, short `description`, complete `prompt`.
- Foreground waits; `background: true` returns immediately and notifies the parent.
- Pass returned `sessionID` to continue that child.
- “Only subagent-mode agents can be used, and the default nesting depth is one.”
- Permission action: `subagent` with the selected agent ID as resource.

Example prompt from Tools: “Ask the explore subagent to map the authentication flow and return the key files.”

**3. Slash command with `agent` / `subagent` fields.** Commands guide:

| `subagent` value | Behavior |
| --- | --- |
| `true` | Always a child session, even if the selected agent is `mode: primary`. |
| `false` | Always the current session, even if the selected agent is `mode: subagent`. |
| omitted | Child **only when** the selected agent has `mode: subagent`. |

Example: `agent: general` plus `subagent: true` runs `/audit` in a background child; parent keeps its agent and model; child’s result is sent back to the parent.

Legacy field `subtask` is a deprecated alias for `subagent`; if both are set, `subagent` wins.

**4. Restrict which agents the parent may launch:**

```jsonc
{
  "agents": {
    "orchestrator": {
      "permissions": [
        { "action": "subagent", "resource": "*", "effect": "deny" },
        { "action": "subagent", "resource": "reviewer", "effect": "allow" }
      ]
    }
  }
}
```

Built-in `general` “cannot launch more subagents.” Permissions defaults: `general` “Denies questions and launching subagents.”

### @mentions — not confirmed as a v2 TUI feature

**v2 TUI docs document `@` only as file context**, not agent mention:

> Type `@` to search for a file, then select it to attach that file to the prompt.

Commands guide: stored templates do not expand `@path`; `@README.md` “remains ordinary prompt text.”

**v1 behavior (do not treat as v2):** GitHub sst/opencode#3715 (2025-11-01) quotes older docs: subagents can be invoked “Manually by @ mentioning a subagent in your message.” That issue also says `@` is **user** syntax; primary-agent system prompts should name the subagent **without** `@`. GitHub anomalyco/opencode#19538 (fetched via search snippet, not re-fetched in full) claimed even in that era `@mention` only injected a suggestion; the primary could ignore it and not spawn a child.

**Third-party (2026-11-03):** getagenttools still writes “Or you type `@` and its name” / `@general`, mixing 1.x and 2, and the author states they did not run OpenCode.

**This research could not confirm that typing `@reviewer` in the v2 TUI still opens an agent autocomplete or forces a child session.** If that path still exists in code, it is not on the v2 TUI, Agents, or Tools pages fetched on 2026-11-09.

Practical v2 delegation for a custom agent named `reviewer`:

1. Set `mode: subagent` (or `all` if you also want it Tab-selectable — see the Tools vs Agents conflict above).
2. Give a clear `description`.
3. Allow the parent `subagent` permission for resource `reviewer`.
4. Either tell the primary “use the reviewer subagent to …”, or ship a `/review` command with `agent: reviewer`.

---

## Default agent configuration

From Agents “Selection” and Config “Agent”:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "default_agent": "writer",
  "agents": {
    "writer": { "mode": "primary" }
  }
}
```

Config’s own example uses `"default_agent": "build"`.

**Resolution rules (Agents page, quoted):**

> The selected default must exist, be visible, and support primary use. Otherwise OpenCode uses `build`, then the first visible primary-capable agent. Changing this setting does not replace the agent stored on an existing session.

Implications:

- A `mode: subagent` id is invalid as `default_agent`.
- A `hidden: true` agent is invalid as `default_agent` (“must … be visible”).
- Existing sessions keep the agent they already stored; `default_agent` applies when a session has not selected one.
- Built-in fallback is `build` (also the default coding agent in the built-ins table).

Selecting a primary agent does not change the session model (Agents → Model). Command execution has its own model override order (command `model`, then the command agent’s model, then the current session model).

---

## Limitations, hidden agents, permission prompts

### Hidden and unselectable agents

Agents → Hidden:

> `hidden` removes an agent from normal listings, interactive discovery, and the subagent catalog.
>
> This controls visibility, not security. Use permissions to restrict behavior.

Built-ins: “Hidden `compaction`, `title`, and `summary` agents perform maintenance and cannot be selected directly. V2 has no built-in `scout` agent.”

Issue #44751 (closed 2026-10-20) records that v1 docs wrongly said `hidden` was subagent-only; v2 docs dropped that restriction. Comment on 2026-10-20: “The V2 agents documentation now describes `hidden` as controlling agent visibility without the incorrect subagent-only restriction.” Same issue: `opencode run --agent` still resolved a hidden `mode: all` agent on 1.18.22 (v1-era verification). **v2 docs do not restate whether `run --agent` bypasses `hidden`.**

`disabled: true` “removes a built-in or custom agent at that point in configuration loading” (stronger than hidden).

### Permission prompts

- Effects: `allow` / `ask` / `deny`. “If no rule matches, OpenCode uses `ask`.”
- Last matching rule wins; agent rules append after global rules.
- `--auto` auto-approves anything not explicitly denied; denials still apply.
- TUI `cli.json`: `session.permissions` is `prompt` (default in the example) or `autoaccept` (“accepts every request automatically”).
- Approval UI (Permissions → Approvals): Allow once (`once`), Allow always (`always`, saves proposed patterns for the project), Reject (`reject` rejects this and every other pending request in the session). “skills and subagents propose their IDs.”
- Saved approvals never override a configured `deny`.
- Default base policy for every agent, including custom ones: allow `*`, then ask on `*.env` / `*.env.*`, allow `*.env.example`.
- `plan` denies edits except under `~/.opencode/plan`. `explore` denies everything except a read/search/web/shell subset. `general` denies questions and launching subagents.

### Delegation limits

- Default nesting depth is **one** (Tools). Nested `subagent` calls fail at that depth unless a higher limit exists (see Unconfirmed).
- `general` cannot launch further subagents.
- Custom children use their own permission lists, not a subset of the parent’s.
- `mode: subagent` agents cannot be the target of `opencode run --agent` / `mini --agent`; the CLI falls back to the default agent.
- Root TUI historically had no `--agent` (issue #56842, still open in the 2026-10-21 snapshot). Not re-verified on v2.2.6.
- Command templates: `@path` in the stored markdown is **not** an attachment.

### Tool / Task rename

Do not look for a v2 tool named `task` / Task in current docs. v2 name is `subagent`; v1 `permission.task` becomes `permissions` entries with `"action": "subagent"`. Older GitHub `packages/opencode/src/tool/task.ts` is the 1.x implementation.

---

## What you could not confirm

1. **Whether v2 TUI `@agentname` still mentions/invokes agents.** Official v2 TUI page documents `@` for files only. v1 docs and a 2026-11-03 third-party post still describe `@`. No v2 Agents/Tools/TUI sentence confirms agent @autocomplete.
2. **Whether `@mention` (if present) hard-spawns a child** vs suggesting the parent model call `subagent` (v1 issue #19538). Not re-tested on v2.
3. **Whether `mode: all` agents are valid `subagent` tool targets.** Agents: yes. Tools: “Only subagent-mode agents can be used.”
4. **Whether root `opencode --agent` was restored by v2.2.6.** Issue #56842 was open as of 2026-10-21 against 2.0.32; PRs #56848 / #58662 are referenced but their merge state was not fetched. Current CLI Intro still omits the flag.
5. **Config key `experimental.subagent_depth`.** Tools confirms default depth 1. getagenttools (source read 2026-10-31 at tag v2.2.5) claims the v2 key is `experimental.subagent_depth`. That key did not appear in the fetched Config page (page also truncated before any `experimental` section).
6. **Concurrent subagent count.** No official limit found. Third-party author found none in source.
7. **`opencode agent create` / `list` in v2.** Present on older `dev.opencode.ai` CLI docs; absent from v2 Commands. Not confirmed removed vs undocumented.
8. **GitHub path of run-mode `--agent` validation.** Exa returned `packages/opencode/src/cli/cmd/run.ts` on `dev`; a subsequent fetch of that URL was 404. Fallback messages are quoted in issue #44751.
9. **GitHub issue #37225** (“default_agent ignored on startup in V2”) was mentioned inside #53728 search snippets and was **not** fetched; do not treat it as confirmed.
10. **Live TUI behavior** was not executed; this file is docs/GitHub only.

### Tooling failure

Exa `web_search_exa` call 4 failed:

```text
You've hit Exa's free MCP rate limit. Create a free Exa account...
```

Fallback: Cursor `WebSearch` and `WebFetch` for keybinds, tools, @mention, and the keybinds page body. All other searches and the cited `opencode.ai` / GitHub issue fetches used Exa successfully.

---

## Source URLs (title, URL, date)

| Title | URL | Date / freshness |
| --- | --- | --- |
| Agents | https://opencode.ai/v2/docs/agents/ | Fetched 2026-11-09; page has no last-updated stamp |
| TUI | https://opencode.ai/v2/docs/cli/tui/ | Fetched 2026-11-09 |
| Commands (CLI) | https://opencode.ai/v2/docs/cli/commands/ | Fetched 2026-11-09 |
| Intro (CLI) | https://opencode.ai/v2/docs/cli/ | Fetched 2026-11-09 |
| Config | https://opencode.ai/v2/docs/config | Fetched 2026-11-09 |
| Settings (CLI `cli.json`) | https://opencode.ai/v2/docs/cli/config/ | Fetched 2026-11-09 |
| Keybinds | https://opencode.ai/v2/docs/cli/keybinds/ | Fetched 2026-11-09 |
| Tools (includes Subagent tool) | https://opencode.ai/v2/docs/tools/ | Fetched 2026-11-09 |
| Commands (slash `/commands`) | https://opencode.ai/v2/docs/commands/ | Fetched 2026-11-09 |
| Permissions | https://opencode.ai/v2/docs/permissions/ | Fetched 2026-11-09 |
| Terminal (product page, v2.2.6) | https://opencode.ai/terminal | Fetched 2026-11-09; changelog entries 2026-11-06 (v2.2.6) and 2026-10-30 (v2.2.5) |
| v2: root TUI no longer accepts `--agent` · Issue #56842 | https://github.com/anomalyco/opencode/issues/56842 | Created 2026-10-18; fetched timeline through 2026-10-21 |
| Docs: hidden is documented as subagent-only… · Issue #44751 | https://github.com/anomalyco/opencode/issues/44751 | Created 2026-08-24; closed 2026-10-20; comment linking v2 Hidden docs 2026-10-20 |
| [FEATURE]: Improve Subagent Invocation Documentation · Issue #3715 | https://github.com/sst/opencode/issues/3715 | Created 2025-11-01 (v1 @mention docs; search snippet only) |
| `packages/cli/src/commands/commands.ts` (dev) | https://github.com/anomalyco/opencode/blob/dev/packages/cli/src/commands/commands.ts | Exa snippet 2026-11-09 (`mini`/`run` `--agent` flags) |
| opencode subagents: config, model and limits (secondary) | https://getagenttools.com/blog/opencode-subagents/ | Published 2026-11-03; author read docs/source 2026-10-31 at tags v1.19.5 and v2.2.5; **did not run OpenCode** |

Older/v1 pages seen in search but **not** used as v2 authority: `https://dev.opencode.ai/docs/cli/`, `https://opencode.ai/docs/agents/` (content often mirrors v2 when fetched, but v1 quotes in GitHub issues differ), `https://dev.opencode.ai/docs/permissions/`.
