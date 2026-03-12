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
- [ ] `description` — contains ALL activation triggers and keywords; written for Claude (the delegator), not for humans; includes "Use proactively" or specific trigger phrases
- [ ] `tools` — explicitly listed (not relying on inheritance); minimal set for the task
- [ ] `permissionMode` — appropriate for the agent's role
- [ ] `model` — set explicitly if agent needs a specific capability level
- [ ] No unnecessary fields (don't add fields just because they exist)

**Body (system prompt):**

- [ ] NO "When to Activate" or "MANDATORY activation for" sections (this info belongs in `description`)
- [ ] NO references to other agents by name (subagents are standalone, cannot communicate)
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
| "Escalate to tech-oracle" | Replace with "Ask the user for guidance" |
| "Pass results to code-guardian" | Remove — agent returns results to Claude directly |
| Inheriting all tools (no `tools` field) | Add explicit `tools` list with minimum necessary |
| `description` is human-readable but not Claude-readable | Rewrite with trigger phrases and keywords |
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
2. **Determine scope**: project (`.claude/agents/`) or user (`~/.claude/agents/`) — ask if unclear
3. **Gather requirements** through conversation:
   - What task does the agent handle?
   - Should it modify files or read-only?
   - What tools does it need? (restrict to minimum necessary)
   - What model? (haiku for fast/cheap, sonnet for balanced, opus for complex)
   - Permission mode?
   - Does it need persistent memory?
   - Any MCP servers or skills to preload?
4. **Write the agent file** using the Write tool following all rules below
5. **Verify** the file was created successfully

### Rules for Writing Good Agents

**Description field (MOST IMPORTANT):**

- The ONLY thing Claude reads when deciding whether to delegate
- Write it for Claude, not humans
- Include trigger phrases: "Use proactively when...", "MUST BE USED for..."
- List specific keywords that should trigger activation
- Be specific about the domain — vague descriptions lead to wrong delegation

**System prompt (body):**

- State the agent's role clearly at the top
- Define a step-by-step workflow
- Specify what to look for or check
- Define output format
- Do NOT include "When to Activate" sections — Claude never sees the body before activation
- Do NOT reference other agents — subagents are standalone

**Tool restrictions — principle of least privilege:**

- Read-only agents: `Read, Grep, Glob, Bash`
- Code modification agents: `Read, Write, Edit, Glob, Grep, Bash`
- Analysis/planning agents: `Read, Glob, Grep, Bash`
- Use `disallowedTools` when you want to inherit most tools but block a few

### Output

After writing, confirm:

```text
Created: .claude/agents/my-agent.md
  Name: my-agent
  Model: sonnet
  Tools: Read, Grep, Glob, Bash
  Permission mode: default
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
| `model` | No | `sonnet`, `opus`, `haiku`, a full model ID (e.g. `claude-opus-4-6`), or `inherit`. Default: `inherit` |
| `permissionMode` | No | `default`, `acceptEdits`, `dontAsk`, `bypassPermissions`, or `plan` |
| `maxTurns` | No | Maximum number of agentic turns before the subagent stops |
| `skills` | No | Skills to load into context at startup. Full content is injected. Subagents do NOT inherit skills from parent |
| `mcpServers` | No | MCP servers available to this subagent. Either a server name (string) or inline definition |
| `hooks` | No | Lifecycle hooks scoped to this subagent (PreToolUse, PostToolUse, Stop) |
| `memory` | No | Persistent memory scope: `user`, `project`, or `local`. Enables cross-session learning |
| `background` | No | `true` to always run as background task. Default: `false` |
| `isolation` | No | `worktree` to run in a temporary git worktree with isolated repo copy |

### Available Tools

Standard: `Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, `WebFetch`, `WebSearch`, `Agent`.

- `Agent` = can spawn any subagent
- `Agent(worker, researcher)` = can only spawn named subagents
- Omitting `Agent` = cannot spawn subagents
- Subagents CANNOT spawn other subagents — `Agent(...)` only works for main thread agents

### Permission Modes

| Mode | Behavior |
| --- | --- |
| `default` | Standard permission checking with prompts |
| `acceptEdits` | Auto-accept file edits |
| `dontAsk` | Auto-deny permission prompts (explicitly allowed tools still work) |
| `bypassPermissions` | Skip all permission checks (dangerous!) |
| `plan` | Plan mode — read-only exploration |

### Memory Scopes

| Scope | Location | Use when |
| --- | --- | --- |
| `user` | `~/.claude/agent-memory/<name>/` | Learnings across all projects (recommended default) |
| `project` | `.claude/agent-memory/<name>/` | Project-specific, shareable via version control |
| `local` | `.claude/agent-memory-local/<name>/` | Project-specific, NOT in version control |

When memory is enabled: Read/Write/Edit tools are auto-enabled, first 200 lines of MEMORY.md are included in context.

### Hooks in Frontmatter

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
