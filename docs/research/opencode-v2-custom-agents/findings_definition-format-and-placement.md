# Findings: OpenCode v2 custom agent definition format and placement

**Subtopic question:** How do you author custom agent definitions in OpenCode v2 — file format, directories, schema, required/optional fields, and project vs global vs home config?

**Research as of:** 2026-11-09 (live fetch). Official docs pages did not expose a last-updated date.

**Tooling note:** Five Exa `web_search_exa` calls succeeded. The first Exa `web_fetch_exa` batch failed with rate limit: `Streamable HTTP error: Error POSTing to endpoint: {"jsonrpc":"2.0","error":{"code":-32004,"message":"Too many requests. Please try again later."}}`. Cited page bodies were then fetched with Cursor `WebFetch`. `https://opencode.ai/v2/docs/customization` returned HTTP 404.

---

## Direct answer

OpenCode v2 custom agents are named profiles (system prompt + optional model, permissions, and display fields). You author them as Markdown files with YAML frontmatter, or as entries under the `agents` object in `opencode.json` / `opencode.jsonc`. Preferred Markdown paths are `~/.config/opencode/agents/<name>.md` (global) and `.opencode/agents/<name>.md` (project). Native V2 JSON uses plural `agents`, `system`, `permissions`, `disabled`, and `steps`. V1 `agent/`, `mode/`, `prompt`, `permission`, `tools`, `temperature`, and `maxSteps` still load when a file is entirely V1, but the docs tell you not to use them in new V2 definitions. `AGENTS.md` is not an agent definition file; it is ambient instruction text loaded alongside an agent's system prompt.

---

## 1. File formats

Two formats are documented. Frontmatter on a Markdown agent accepts the same fields as an `agents` configuration entry. The Markdown body becomes the agent's `system` prompt.

Quote from [Agents](https://opencode.ai/v2/docs/agents): "Frontmatter accepts the same fields as an `agents` configuration entry. The Markdown body becomes the agent's `system` prompt"

Quote from the same page: "In a Markdown agent, put this text in the document body instead of a `system` frontmatter field."

JSONC definitions live under `agents` in any OpenCode configuration file (`opencode.json` or `opencode.jsonc`). Add `"$schema": "https://opencode.ai/config.json"` for editor validation.

V1 vs V2 file detection (Markdown), quote from [Migrate from V1](https://opencode.ai/v2/docs/migrate-v1): "Each file is read as one format. A file that uses any of `permissions`, `request`, `system`, or `disabled` is read as V2, and V1 fields in it, such as `name`, `tools`, `permission`, or `temperature`, are ignored with a warning in the log. Other files that use V1 fields are read as V1. Convert a file's frontmatter all at once rather than mixing the two formats."

The GitHub loader matches that rule. In `packages/core/src/config/plugin/agent.ts` (anomalyco/opencode `dev`, last commit fetched 2026-11-07), native V2 keys are `permissions`, `request`, `system`, and `disabled`. If a file has unknown keys and none of those native keys, it is decoded as V1 and migrated. If it is V2 and has extra keys, those fields are ignored with a warning.

---

## 2. Exact file paths and directories

### Preferred V2 Markdown agent files

Documented on [Agents](https://opencode.ai/v2/docs/agents):

```text
~/.config/opencode/agents/<name>.md
.opencode/agents/<name>.md
```

Preferred project location, quote from [Migrate from V1](https://opencode.ai/v2/docs/migrate-v1):

```text
.opencode/agents/<name>.md
```

Nested project paths become the agent ID. Quote from [Agents](https://opencode.ai/v2/docs/agents):

```text
.opencode/agents/team/reviewer.md  →  team/reviewer
```

The ID is the path under `agents/` (or legacy `agent/`) with `.md` removed. The loader strips a leading `agent/`, `agents/`, `mode/`, or `modes/` prefix from the relative path.

### Still-discovered V1 directories

Quote from [Migrate from V1](https://opencode.ai/v2/docs/migrate-v1): "V1 agent files may use `agent/`, `agents/`, `mode/`, or `modes/`. V2 still discovers all four directories."

That implies these still work (global and project, same layout as other `.opencode` content):

```text
.opencode/agent/<name>.md
.opencode/agents/<name>.md
.opencode/mode/<name>.md
.opencode/modes/<name>.md
~/.config/opencode/agent/<name>.md
~/.config/opencode/agents/<name>.md
~/.config/opencode/mode/<name>.md
~/.config/opencode/modes/<name>.md
```

Files under `mode/` or `modes/` represent primary agents. Quote from migrate-v1: "When moving one into `agents/`, add `mode: primary` to its frontmatter. Files under `agent/` can move to `agents/` without changing their path-derived ID."

GitHub loader globs (not in the prose docs, from `packages/core/src/config/plugin/agent.ts` on `dev`):

- `{agent,agents}/**/*.md` — recursive; nested folders are part of the ID
- `{mode,modes}/*.md` — non-recursive; those files are forced to `mode: "primary"`

### System (machine-wide) agent files

[Config](https://opencode.ai/v2/docs/config) says the system directory loads `agents/` for every user:

| Platform | Directory |
| --- | --- |
| macOS | `/Library/Application Support/opencode` |
| Linux | `/etc/opencode` |
| Windows | `%ProgramData%\opencode` |

Documented example:

```text
/etc/opencode/
├── opencode.json
├── agents/review.md
├── commands/release.md
└── skills/deploy/SKILL.md
```

### JSON / JSONC config files (where `agents` maps live)

From [Config](https://opencode.ai/v2/docs/config) and [Migrate from V1](https://opencode.ai/v2/docs/migrate-v1):

```text
/Library/Application Support/opencode/opencode.json(c)
/etc/opencode/opencode.json(c)
%ProgramData%\opencode\opencode.json(c)
/Library/Managed Preferences/<user>/ai.opencode.managed.plist
/Library/Managed Preferences/ai.opencode.managed.plist
~/.config/opencode/opencode.json(c)
<project>/opencode.json(c)
<project>/.opencode/opencode.json(c)
```

Config docs example project paths:

```text
/home/user/projects/my-app/opencode.json(c)
/home/user/projects/my-app/.opencode/opencode.json(c)
```

JSON and JSONC are both supported. Quote from [Config](https://opencode.ai/v2/docs/config): "Use JSONC when you want comments or trailing commas."

### `AGENTS.md` (instructions, not agent definitions)

These are ambient instruction files, not custom agent profiles:

```text
~/.config/opencode/AGENTS.md
<project>/AGENTS.md
<nested-package>/AGENTS.md
```

Quote from [Instructions](https://opencode.ai/v2/docs/instructions): "OpenCode V2 recognizes `AGENTS.md` only. It does not use `CLAUDE.md` as a fallback."

Quote from [Migrate from V1](https://opencode.ai/v2/docs/migrate-v1): "V2 discovers the global `~/.config/opencode/AGENTS.md` and ambient `AGENTS.md` files from the current directory up to home. For projects outside home, discovery stops at the project root."

They are combined with the selected agent's system prompt; they do not create a named agent ID.

### Not a docs page

`https://opencode.ai/v2/docs/customization` — 404 on 2026-11-09.

---

## 3. Schema: fields, types, required vs optional

Native V2 agent object in published schema [`https://opencode.ai/config.json`](https://opencode.ai/config.json) is `$defs/Config.AgentEncoded`. Top-level config key is `agents`: object of string → `Config.AgentEncoded`. Description: "Named built-in agent overrides and custom agent definitions".

**Required agent-object properties:** none. `Config.AgentEncoded` lists properties but no `required` array. The agent ID is the JSON key or the Markdown path, not a `name` field.

**`additionalProperties`:** `false` on `Config.AgentEncoded`. Extra native-V2 keys are not valid in JSON schema.

Matching TypeScript on GitHub `dev` (`packages/schema/src/config/agent.ts`, last commit fetched 2026-10-22, "fix(core): ignore unsupported agent colors (#57910)"):

```ts
export class Info extends Schema.Class("Config.Agent")({
  model: ConfigModel.Selection.pipe(optional),
  request: ConfigProvider.Request.pipe(optional),
  system: Schema.String.pipe(optional),
  description: Schema.String.pipe(optional),
  mode: Schema.Literals(["subagent", "primary", "all"]).pipe(optional),
  hidden: Schema.Boolean.pipe(optional),
  color: Color.pipe(/* unsupported colors become none */, optional),
  steps: PositiveInt.pipe(optional),
  disabled: Schema.Boolean.pipe(optional),
  permissions: Permission.Ruleset.pipe(optional),
}) {}
```

### Native V2 fields (use these)

| Field | Type (schema / docs) | Required? | Meaning |
| --- | --- | --- | --- |
| *(identity)* | JSON map key, or Markdown path under `agent(s)/` | Yes, but not a frontmatter field | Agent ID. Nested `.opencode/agents/team/reviewer.md` → `team/reviewer`. V2 ignores a `name` frontmatter field (with a warning) when the file is read as V2. |
| `description` | `string` | Optional | "explains the agent's purpose. Add it to subagents because OpenCode shows it to the model choosing which agent to launch" ([Agents](https://opencode.ai/v2/docs/agents)). |
| `mode` | `"primary" \| "subagent" \| "all"` | Optional; default **`primary`** for a new custom agent | `primary`: main session agent. `subagent`: child session via the `subagent` tool only. `all`: either. Docs: "When omitted on a new custom agent, it defaults to `primary`". |
| `model` | string `provider/model` optional `#variant`, **or** object `{ providerID, model, variant? }` | Optional | String pattern in schema: `^[^/#]+\/[^#]+(?:#[^#]+)?$`. Object requires `providerID` and `model`. Subagent uses its model, or inherits the parent session model when none is set. Selecting a primary agent by ID does not change the session's stored model. |
| `system` | `string` | Optional in JSON; Markdown body is used as `system` | Non-empty value "replaces the provider's base prompt for that agent". Project instructions, skills, references, and other instruction sources are still added. |
| `permissions` | array of `{ action, resource, effect }` | Optional | Ordered matching rules. Last match wins. Each rule **requires** `action` (string), `resource` (string), `effect` (`"allow" \| "ask" \| "deny"`). |
| `steps` | positive integer (`exclusiveMinimum: 0`) | Optional | Max model steps. "On the final step, OpenCode removes tools and asks the model to summarize in text. New user input resets the allowance." |
| `hidden` | `boolean` | Optional | "removes an agent from normal listings, interactive discovery, and the subagent catalog". "This controls visibility, not security." |
| `color` | string matching `^#[0-9a-fA-F]{6}$` in published V2 schema | Optional | UI color. Docs: "six-digit hex value". GitHub decoder ignores unsupported colors (including old V1 theme names) instead of dropping the agent. |
| `disabled` | `boolean` | Optional | "removes a built-in or custom agent at that point in configuration loading". Loader: if `item.disabled`, the agent ID is removed. |
| `request` | `{ headers?: Record<string,string>, body?: object }` | Optional | Per-agent header and JSON body overlays. Docs: "The V2 session runner preserves these values but does not yet send them with model requests. Configure active request settings on the provider, model, or model variant instead." |

Related **top-level** config (not inside an agent object): `default_agent` (`string`) — primary agent when a session has not selected one. It "must exist, be visible, and support primary use. Otherwise OpenCode uses `build`, then the first visible primary-capable agent."

### Permission rule fields

From [Permissions](https://opencode.ai/v2/docs/permissions) and schema `$defs/Permission.Rule`:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `action` | string (wildcards ok) | Yes | Tool/permission action. Built-ins include `shell`, `edit`, `subagent`, `read`, `glob`, `grep`, `webfetch`, `websearch`, `skill`, `question`, `external_directory`, `experimental_image_generate`, MCP helpers, `execute`. `*` allowed. |
| `resource` | string (wildcards ok) | Yes | Path, command, agent ID, URL, query, skill ID, etc. For `read`, `edit`, and `external_directory`, `~` and `$HOME` expand. Shell resources stay raw command text. |
| `effect` | `"allow" \| "ask" \| "deny"` | Yes | Last matching rule wins. If no rule matches, OpenCode uses `ask`. |

Every agent starts with this base policy (quote is the published example array on [Permissions](https://opencode.ai/v2/docs/permissions)):

```jsonc
[
  { "action": "*", "resource": "*", "effect": "allow" },
  { "action": "read", "resource": "*.env", "effect": "ask" },
  { "action": "read", "resource": "*.env.*", "effect": "ask" },
  { "action": "read", "resource": "*.env.example", "effect": "allow" },
]
```

Agent `permissions` **append** after global `permissions`; they do not replace them. Quote from [Agents](https://opencode.ai/v2/docs/agents): "Global `permissions` apply before agent-specific rules, so later agent rules can refine them." Quote from [Permissions](https://opencode.ai/v2/docs/permissions): "A custom subagent uses its own permissions, not a subset of its parent's permissions."

V1 action renames (migrate-v1): `bash` → `shell`, `task` → `subagent`, `write`/`patch` → `edit`.

### Fields **not** to use in new V2 agent config

Quote from [Agents](https://opencode.ai/v2/docs/agents): "Do not use legacy top-level fields such as `temperature`, `top_p`, `prompt`, `permission`, `tools`, `disable`, or `maxSteps` in new V2 agent configuration."

| Legacy V1 field | V2 replacement | Notes |
| --- | --- | --- |
| `prompt` | `system` (JSON) or Markdown body | File bodies do not need a `system` field. |
| `permission` (object by tool) | `permissions` (ordered array) | |
| `tools` (name → boolean) | `permissions` with `allow`/`deny` | Schema still describes V1 `tools` as "@deprecated Use 'permission' field instead" on `AgentConfig`. |
| `disable` | `disabled` | |
| `maxSteps` | `steps` | |
| `variant` as a sibling of `model` | `provider/model#variant` or `model.variant` in the object form | Native `Config.AgentEncoded` has **no** standalone `variant`. The Markdown loader still treats `variant` as a known key and joins it onto a string `model` that does not already contain `#`. |
| `temperature`, `top_p`, `options` | model/provider `variants[].body` / `settings` | Agent `request.body` is kept but not sent to the model in V2. |
| `name` | filename / JSON key | "Agent `name` inside V1 JSON configuration" is listed as accepted but unsupported. In V2 Markdown it is ignored with a warning when the file is native V2. |
| `color` theme names (`primary`, `secondary`, …) | six-digit hex | Still present on deprecated V1 `AgentConfig` in `config.json`. Native V2 schema is hex-only. |

### `maxTokens`

**Not an agent definition field.** In `https://opencode.ai/config.json`, `maxTokensField` is under `Provider.Compatibility` and only names which JSON key a provider uses (`max_completion_tokens` vs `max_tokens`). No agent-level `maxTokens` appears in `Config.AgentEncoded` or the Agents docs.

---

## 4. Complete examples copied from docs

Quotes below are copied from the official pages fetched 2026-11-09.

### Markdown agent (Agents page, first example)

Quote from [Agents](https://opencode.ai/v2/docs/agents):

```md
---
description: Reviews changes for correctness and regressions
mode: subagent
model: anthropic/claude-sonnet-5-5#high
permissions:
  - action: edit
    resource: "*"
    effect: deny
  - action: shell
    resource: "*"
    effect: deny
---

Review the current changes. List findings in severity order with file and line references.
```

### Markdown agent (minimal frontmatter)

Quote from [Agents](https://opencode.ai/v2/docs/agents):

```md
---
description: Explains code without changing it
mode: subagent
---

Explain the relevant code with short examples. Do not edit files.
```

### JSONC `agents` map (Agents page)

Quote from [Agents](https://opencode.ai/v2/docs/agents):

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "agents": {
    "reviewer": {
      "description": "Reviews current changes",
      "mode": "subagent",
      "system": "Report findings in severity order.",
      "permissions": [
        { "action": "edit", "resource": "*", "effect": "deny" },
      ],
    },
  },
}
```

### JSONC `agents` map (Config page)

Quote from [Config](https://opencode.ai/v2/docs/config):

```jsonc
{
  "agents": {
    "reviewer": {
      "description": "Review changes without editing files",
      "mode": "subagent",
      "system": "Focus on correctness, security, and missing tests.",
      "permissions": [{ "action": "edit", "resource": "*", "effect": "deny" }],
    },
  },
}
```

### V1 → V2 JSON rename (Migrate from V1)

Quote from [Migrate from V1](https://opencode.ai/v2/docs/migrate-v1):

```jsonc
// V1
{
  "agent": {
    "reviewer": {
      "prompt": "Review for correctness and missing tests.",
      "model": "anthropic/claude-sonnet-5-5",
      "variant": "high",
      "disable": false,
      "permission": {
        "edit": "deny"
      }
    }
  }
}

// V2
{
  "agents": {
    "reviewer": {
      "system": "Review for correctness and missing tests.",
      "model": "anthropic/claude-sonnet-5-5#high",
      "disabled": false,
      "permissions": [
        { "action": "edit", "resource": "*", "effect": "deny" }
      ]
    }
  }
}
```

### Expanded `model` object

Quote from [Agents](https://opencode.ai/v2/docs/agents):

```jsonc
{
  "agents": {
    "reviewer": {
      "model": {
        "providerID": "anthropic",
        "model": "claude-sonnet-5-5",
        "variant": "high",
      },
    },
  },
}
```

### `request` (documented, not yet sent)

Quote from [Agents](https://opencode.ai/v2/docs/agents):

```jsonc
{
  "agents": {
    "reviewer": {
      "request": {
        "headers": { "x-agent": "reviewer" },
        "body": { "temperature": 0.1 },
      },
    },
  },
}
```

### Sampling on a model variant instead of the agent (Migrate from V1)

Quote from [Migrate from V1](https://opencode.ai/v2/docs/migrate-v1):

```jsonc
{
  "providers": {
    "opencode": {
      "models": {
        "deepseek-v4.1-flash": {
          "variants": [{ "id": "review", "body": { "thinking": { "type": "disabled" }, "temperature": 0.2 } }],
        },
      },
    },
  },
  "agents": {
    "reviewer": { "model": "opencode/deepseek-v4.1-flash#review" },
  },
}
```

---

## 5. Project vs global vs home / system precedence

Official V2 docs do **not** use a layer named "home config" for agent definitions. They document **managed → system → global (`~/.config/opencode`) → project**, plus a special merge rule for `.opencode` JSON files. `AGENTS.md` separately walks toward the home directory.

### Config file merge (settings, including `agents` maps)

Quote from [Config](https://opencode.ai/v2/docs/config): "Managed settings have the highest precedence, so users and projects cannot override the values they set, and managed preferences override the system directory."

Quote from the same page: "OpenCode searches from the current directory to the filesystem root. It first merges direct `opencode.json(c)` files from the farthest directory to the closest, then merges files inside `.opencode` directories in the same order. This means every discovered `.opencode` config overrides every direct config. Use one form throughout a directory tree unless you need that behavior."

Worked example from that page (start in `/home/user/projects/acme/packages/web`), **lowest to highest**:

1. `~/.config/opencode/opencode.json`
2. `/home/user/projects/acme/opencode.json`
3. `/home/user/projects/acme/packages/web/opencode.json`
4. `/etc/opencode/opencode.json`

Quote: "The package config overrides matching settings from the repository config, which overrides the global config. The system config overrides all of them. Settings that do not conflict are preserved."

Implication: **system/managed outranks project and global**. Project nearer files outrank farther project files, which outrank `~/.config/opencode`. A `.opencode/opencode.json(c)` anywhere in the search outranks every *direct* `opencode.json(c)` (including global), because `.opencode` files are merged in a second pass.

`OPENCODE_DISABLE_PROJECT_CONFIG=1` skips project `AGENTS.md` discovery (and, for configured `instructions` globs, resolves relative paths against the global config directory). Documented on [Instructions](https://opencode.ai/v2/docs/instructions); not confirmed on the Agents page as disabling Markdown agent files.

### Agent-definition merge

Quote from [Agents](https://opencode.ai/v2/docs/agents): "Agent definitions merge in configuration order. Later scalar values replace earlier values, request maps merge by key, and permission rules append."

Override a built-in by reusing its ID (`build`, `plan`, `general`, `explore`). Hidden built-ins `compaction`, `title`, and `summary` "cannot be selected directly."

### Markdown agent discovery vs JSON

Docs state Markdown agents are saved globally (`~/.config/opencode/agents/`) or in the project (`.opencode/agents/`), and "OpenCode discovers project `.opencode` directories from the current directory up to the project root." System dirs also load `agents/`. Exact merge order when the **same agent ID** exists as both a Markdown file and an `agents` JSON entry is **not spelled out** beyond "configuration order."

### `AGENTS.md` order (instructions only)

Quote from [Instructions](https://opencode.ai/v2/docs/instructions). Example load set:

```text
~/.config/opencode/AGENTS.md
~/code/my-project/AGENTS.md
~/code/my-project/packages/AGENTS.md
~/code/my-project/packages/web/AGENTS.md  ← current workspace
```

Combined as:

```text
~/.config/opencode/AGENTS.md
packages/web/AGENTS.md
packages/AGENTS.md
AGENTS.md
```

Quote: "OpenCode combines the files and does not resolve conflicts between them."

Instruction stack around agents, quote:

```text
1. Agent or provider system prompt
2. Code Mode tool guidance, when enabled
3. MCP server, reference, and skill guidance
4. Global and project AGENTS.md files, then configured instructions
5. Built-in date and environment context
6. Session-specific instruction entries supplied through the API
```

---

## 6. Published schema still ships deprecated V1 keys

`https://opencode.ai/config.json` still defines:

- `agent` (singular) — `deprecated: true`, items are `$defs/AgentConfig` (V1: `prompt`, `permission`, `tools`, `disable`, `temperature`, `top_p`, `maxSteps`, theme `color` names)
- `mode` — `deprecated: true`, description "@deprecated Use `agent` field instead."
- Native V2: `agents` → `Config.AgentEncoded`

Migrate-v1 says both `agent` and `mode` maps become `agents`, and that V2 still reads existing V1 config without rewriting files. Prefer `agents` for new work. The deprecated `mode` description that points at `agent` rather than `agents` disagrees with the V2 migrate guide.

---

## 7. Sources

| Title | URL | Date / last-updated |
| --- | --- | --- |
| Agents | https://opencode.ai/v2/docs/agents | No last-updated on page. Fetched 2026-11-09. Same body as https://opencode.ai/docs/agents |
| Config | https://opencode.ai/v2/docs/config | No last-updated on page. Fetched 2026-11-09 |
| Migrate from V1 | https://opencode.ai/v2/docs/migrate-v1 | No last-updated on page. Fetched 2026-11-09 |
| Instructions | https://opencode.ai/v2/docs/instructions | No last-updated on page. Fetched 2026-11-09 |
| Permissions | https://opencode.ai/v2/docs/permissions | No last-updated on page. Fetched 2026-11-09 |
| OpenCode configuration schema | https://opencode.ai/config.json | `$id` `https://opencode.ai/config.json`. No date field. Fetched 2026-11-09 |
| `packages/schema/src/config/agent.ts` | https://github.com/anomalyco/opencode/blob/dev/packages/schema/src/config/agent.ts (raw fetched) | Last commit on path: 2026-10-22, `6a5f15ad` "fix(core): ignore unsupported agent colors (#57910)" |
| `packages/core/src/config/plugin/agent.ts` | https://github.com/anomalyco/opencode/blob/dev/packages/core/src/config/plugin/agent.ts (raw fetched) | Last commit on path: 2026-11-07, `6a89e9f2` "fix(core): skip node_modules when discovering markdown agents (#62571)" |
| Older `packages/core/src/config/agent.ts` (still had `variant` + theme colors) | https://github.com/anomalyco/opencode/blob/846d5481/packages/core/src/config/agent.ts | Historical blob; current `dev` schema dropped standalone `variant` and theme color enums |

Repo note: searches also hit `sst/opencode`; current GitHub sources used here are `anomalyco/opencode`.

---

## 8. What could not be confirmed

- **Last-updated dates** for opencode.ai docs pages (not present in fetched HTML/markdown).
- **`https://opencode.ai/v2/docs/customization`** — 404. No separate official "customization" page found in this pass.
- **`maxTokens` on agents** — not in Agents docs or `Config.AgentEncoded`. Only provider compatibility `maxTokensField`.
- **Exact merge order** when the same agent ID is defined both as Markdown under `~/.config/opencode/agents/` / `.opencode/agents/` **and** as `agents` in JSONC (docs say "configuration order" without listing Markdown vs JSON).
- Whether **global** nested IDs work the same as project nested IDs (`~/.config/opencode/agents/team/reviewer.md` → `team/reviewer`). Only the project `.opencode/agents/...` nested example is documented.
- Whether **`OPENCODE_DISABLE_PROJECT_CONFIG=1`** also skips project Markdown agents (documented for `AGENTS.md` and relative `instructions` entries only).
- **XDG_CONFIG_HOME** / `~/.opencode` / `OPENCODE_CONFIG` / remote `/.well-known/opencode` as extra layers — **not** in the V2 Config page fetched here. A third-party writeup (TurboAI) and older GitHub `packages/opencode/src/config/config.ts` snippets from search mentioned them; those were **not** treated as V2-official because the live Config page does not list them.
- **Required `description`** — AgentAtlas and some third-party pages called it required; official schema and Agents page treat it as optional (recommended for subagents).
- **Default `mode` in runtime code vs docs** — docs say omitted custom agents default to `primary`. An older GitHub `AgentV2.Info.empty` snippet from search used `mode: "all"`. Current `Config.Agent` schema leaves `mode` optional. Authoring should follow the docs default (`primary`).
- **GitHub `packages/web/src/content/docs/agents.mdx` on `dev`** — fetch returned an empty file (0 lines). Live site docs were used instead.
- **Whether `color` theme names still apply in V2 UI** — native schema is hex-only; V1 `AgentConfig` still allows theme enums; GitHub comments say unsupported colors should not drop the agent.
- **`opencode agent create` / `agent list` CLI** — mentioned in stale GitHub mdx search snippets; this subtopic excluded CLI invocation.
- **sst vs anomalyco default branch docs drift** — not fully mapped; live `opencode.ai` pages were treated as canonical.
