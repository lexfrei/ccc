---
name: agent-father
description: Create or review/rewrite Claude Code subagents. Guides through configuration for new agents; audits and fixes existing agents against official documentation standards.
---

Create new or review and rewrite existing Claude Code subagents.

## Mode Detection

- **If the user provides an existing agent file path or pastes agent content** → Review mode
- **If the user asks to create a new agent** → Create mode
- **If unclear** → ask the user

---

## Review Mode: Audit and Rewrite an Existing Agent

Read the agent file and audit it against every rule below. Fix ALL issues found.

### Visibility Model (CRITICAL — most common mistake)

Claude sees TWO separate things at TWO separate times:

1. **BEFORE delegation**: Claude reads ONLY the `description` field from frontmatter. Nothing else. The body is invisible.
2. **AFTER delegation**: The subagent receives ONLY the body as its system prompt, plus basic env details (working directory, platform). It does NOT get the full Claude Code system prompt.

**Consequences:**

- "When to Activate" / "MANDATORY activation for" sections in the body are WASTED — Claude never sees them before delegating
- Activation triggers, keywords, and conditions MUST be in `description`
- The body should contain ONLY what the agent needs DURING execution: role, workflow, patterns, constraints, checklists
- If useful trigger info is in the body but not in `description` — move it to `description`

### Audit Checklist

**Frontmatter:**

- [ ] `name` — lowercase, hyphens only
- [ ] `description` — contains ALL activation triggers and keywords; written for Claude (the delegator), not for humans; states plainly when to delegate instead of shouting "Use proactively" / "MUST BE USED"
- [ ] `description` — quoted when it contains a colon followed by a space, otherwise the YAML fails to parse (this rule is stated again under Create mode on purpose: each mode is a separate firing moment, and a check absent where it must fire does not fire)
- [ ] `tools` — omitted unless there is a concrete reason to restrict, and the reason is written down. Per-agent allowlists cost more in maintenance than they return: every tool the agent turns out to need has to be added later, and the list is the first thing to go stale
- [ ] `permissionMode` — set only on project and user agents; a plugin-shipped agent drops it, along with `hooks` and `mcpServers`
- [ ] `model` — set explicitly if agent needs a specific capability level
- [ ] `effort` — set only when the work needs a different reasoning level than the session's
- [ ] No unnecessary fields (don't add fields just because they exist)

**Body (system prompt):**

- [ ] NO "When to Activate" or "MANDATORY activation for" sections (this info belongs in `description`)
- [ ] NO references to other agents by name (topology is a runtime decision, not a property of the persona)
- [ ] NO flow mechanics: HANDOFF, WORK_COMPLETE, TodoWrite, BatchTool, next_agent, escalation chains
- [ ] NO personal information leaks (emails, usernames in URLs)
- [ ] Role is stated clearly at the top
- [ ] Workflow/process is defined step-by-step
- [ ] Constraints and prohibitions are explicit
- [ ] Quality criteria / checklist is present
- [ ] Content is focused — only what the agent needs DURING work

**Common anti-patterns to fix:**

| Anti-pattern | Fix |
| --- | --- |
| "When to Activate" section in body | Delete from body, ensure triggers are in `description` |
| "MANDATORY activation for: kubernetes, k8s, deployment" in body | Move keywords to `description` |
| "Escalate to tech-oracle" | Replace with "ask whoever spawned you for guidance" - the caller is the main session for a subagent and the manager for a teammate |
| "Pass results to code-guardian" | Remove — an agent returns its results to whoever spawned it |
| A `tools` allowlist with no stated reason | Remove the field — inheritance is the default, and an unexplained list is one nobody will dare change |
| `hooks`, `mcpServers`, or `permissionMode` on a plugin-shipped agent | Remove — the loader warns and drops all three; the definition it builds never carries them |
| `description` is human-readable but not Claude-readable | Rewrite for the delegator: state when to delegate, with the keywords that should match |
| Body contains info Claude needs before delegation | Move to `description` |
| Body repeats the description | Remove duplication |

### Review Output Format

Show findings grouped by severity, then apply fixes:

```text
CRITICAL (breaks functionality):
- [issue and fix]

WARNING (reduces effectiveness):
- [issue and fix]

SUGGESTION (improvement):
- [issue and fix]
```

Apply all fixes using Edit tool, then show the updated frontmatter summary.

---

## Create Mode: Build a New Agent

### Process

1. **Ask the user** what the agent should do, its specialty, and constraints
2. **Determine scope**: project (`.claude/agents/`), user (`~/.claude/agents/`), or inside a plugin (`<plugin>/agents/`) — ask if unclear. Scope decides which fields do anything, so settle it first
3. **Gather requirements** through conversation:
   - What task does the agent handle?
   - Should it modify files or read-only?
   - Is there a concrete reason to restrict `tools`? Without one, leave it out and inherit
   - What model? (haiku for fast/cheap, sonnet for balanced, opus for complex)
   - Does the work need a different reasoning `effort` than the session's?
   - Permission mode — project and user scope only; a plugin agent drops it
   - Does it need persistent memory?
   - Any skills to preload?
4. **Write the agent file** using the Write tool following all rules below
5. **Verify** the file was created successfully

### Rules for Writing Good Agents

**Description field (MOST IMPORTANT):**

- The ONLY thing Claude reads when deciding whether to delegate
- Write it for Claude, not humans
- State plainly when to delegate. The official guide suggests phrases like "use proactively" to encourage delegation; this repository deliberately does not, because the shouting adds no signal a plain condition lacks
- List specific keywords that should trigger activation
- Be specific about the domain — vague descriptions lead to wrong delegation
- Quote the value when it contains a colon followed by a space, or the frontmatter will not parse

**System prompt (body):**

- State the agent's role clearly at the top
- Define a step-by-step workflow
- Specify what to look for or check
- Define output format
- Do NOT include "When to Activate" sections — Claude never sees the body before activation
- Do NOT reference other agents — topology is a runtime decision, not a property of the persona

**Tool restrictions — restrict for a reason, not by default:**

- Inheritance is the default and usually the right one: omitting `tools` gives the agent every tool available to subagents
- An allowlist has to enumerate everything the agent will ever need, so it fails by omission — and it fails silently, as a capability the agent simply does not have
- On the fleet-teammate path the reference states that coordination tools stay available even under an allowlist. An observed case on Claude Code 2.1.226 contradicts it: a named plugin teammate carrying an allowlist got `not enabled in this context` from `SendMessage` and could only report by writing to a file. One observation on one version says the documented guarantee did not hold there, not that it never holds — and nothing in this guide depends on which side is authoritative, because the argument above is about the list, not about the harness
- When a restriction is genuinely needed, prefer `disallowedTools` to deny a few tools over an allowlist that has to enumerate everything the agent will ever need

### Output

After writing, confirm:

```text
Created: .claude/agents/my-agent.md
  Name: my-agent
  Model: sonnet
  Tools: inherited (no allowlist)
  Permission mode: default (project scope)
```

---

## Reference: Subagent File Format

Subagent files use YAML frontmatter for configuration, followed by the system prompt in Markdown.

### Supported Frontmatter Fields

| Field | Required | Description |
| --- | --- | --- |
| `name` | Yes | Unique identifier using lowercase letters and hyphens |
| `description` | Yes | When Claude should delegate to this subagent. Claude reads this to decide when to use the agent — write it for Claude, not for humans |
| `tools` | No | Tools the subagent can use. Inherits ALL tools if omitted |
| `disallowedTools` | No | Tools to deny, removed from inherited or specified list |
| `model` | No | A family alias (`sonnet`, `opus`, `haiku`, `fable`), a full model ID, or `inherit`. Default: `inherit`. Prefer the alias — a pinned ID goes stale on the next release |
| `permissionMode` | No | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan`, or `manual` (an alias for `default`). Dropped for plugin-shipped agents |
| `maxTurns` | No | Maximum number of agentic turns before the subagent stops |
| `effort` | No | Reasoning effort while this subagent is active: `low`, `medium`, `high`, `xhigh`, `max`. Overrides the session level |
| `skills` | No | Skills to load into context at startup. Full content is injected. Subagents do NOT inherit skills from parent |
| `mcpServers` | No | MCP servers available to this subagent. Either a server name (string) or inline definition. Dropped for plugin-shipped agents |
| `hooks` | No | Lifecycle hooks scoped to this subagent (PreToolUse, PostToolUse, Stop). Dropped for plugin-shipped agents |
| `memory` | No | Persistent memory scope: `user`, `project`, or `local`. Enables cross-session learning |
| `background` | No | `true` to always run as background task. Default: `false` |
| `isolation` | No | `worktree` to run in a temporary git worktree with isolated repo copy |

### Available Tools

Standard: `Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, `WebFetch`, `WebSearch`, `Agent`.

- `Agent` = can spawn any subagent
- `Agent(worker, researcher)` = can only spawn named subagents
- Omitting `Agent` = cannot spawn subagents
- A subagent that has `Agent` can spawn further subagents, up to three layers below the main conversation by default (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`); at the limit the tool is withheld. An agent running as a fleet teammate cannot spawn teammates at all

### Permission Modes

Project and user agents only — Claude Code ignores this field on plugin-shipped agents.

| Mode | Behavior |
| --- | --- |
| `default` | Standard permission checking with prompts |
| `acceptEdits` | Auto-accept file edits |
| `dontAsk` | Auto-deny permission prompts (explicitly allowed tools still work) |
| `bypassPermissions` | Skip all permission checks (dangerous!) |
| `auto` | A background classifier reviews commands and protected-directory writes |
| `plan` | Plan mode — read-only exploration |
| `manual` | Alias for `default` |

### Memory Scopes

| Scope | Location | Use when |
| --- | --- | --- |
| `user` | `~/.claude/agent-memory/<name>/` | Learnings across all projects (recommended default) |
| `project` | `.claude/agent-memory/<name>/` | Project-specific, shareable via version control |
| `local` | `.claude/agent-memory-local/<name>/` | Project-specific, NOT in version control |

When memory is enabled: Read/Write/Edit tools are auto-enabled, first 200 lines of MEMORY.md are included in context.

### Hooks in Frontmatter

Project and user agents only — Claude Code ignores this field on plugin-shipped agents.

```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate.sh"
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "./scripts/lint.sh"
```

### MCP Servers in Frontmatter

Project and user agents only. A plugin-shipped agent loses this field: the loader warns about it and then builds the agent definition from an explicit field list that does not include `mcpServers`, so nothing downstream ever sees it. The same loop and the same omission cover `hooks` and `permissionMode`, which is why all three get one answer rather than three.

```yaml
mcpServers:
  # Inline definition (scoped to this subagent only)
  - playwright:
      type: stdio
      command: npx
      args: ["-y", "@playwright/mcp@latest"]
  # Reference by name (reuses already-configured server)
  - github
```

### Subagent Scope (File Locations)

| Location | Scope | Priority |
| --- | --- | --- |
| `--agents` CLI flag | Current session | 1 (highest) |
| `.claude/agents/` | Current project | 2 |
| `~/.claude/agents/` | All your projects | 3 |
| Plugin `agents/` directory | Where plugin is enabled | 4 (lowest) |
