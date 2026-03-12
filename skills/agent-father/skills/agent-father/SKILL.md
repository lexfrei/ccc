---
name: agent-father
description: Create a new Claude Code subagent. Guides through all configuration options and writes the agent file.
---

Create a new Claude Code subagent by gathering requirements from the user and writing a well-structured agent markdown file.

## Reference: Subagent File Format

Subagent files use YAML frontmatter for configuration, followed by the system prompt in Markdown. The frontmatter defines metadata and configuration. The body becomes the system prompt. Subagents receive ONLY this system prompt plus basic environment details (working directory, platform) — NOT the full Claude Code system prompt.

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
| `skills` | No | Skills to load into the subagent's context at startup. Full content is injected. Subagents do NOT inherit skills from parent |
| `mcpServers` | No | MCP servers available to this subagent. Either a server name (string) or inline definition |
| `hooks` | No | Lifecycle hooks scoped to this subagent (PreToolUse, PostToolUse, Stop) |
| `memory` | No | Persistent memory scope: `user`, `project`, or `local`. Enables cross-session learning |
| `background` | No | `true` to always run as background task. Default: `false` |
| `isolation` | No | `worktree` to run in a temporary git worktree with isolated repo copy |

### Available Tools

Standard tools: `Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, `WebFetch`, `WebSearch`, `Agent`.

- `Agent` without parentheses = can spawn any subagent
- `Agent(worker, researcher)` = can only spawn named subagents
- Omitting `Agent` entirely = cannot spawn subagents
- Note: subagents CANNOT spawn other subagents — `Agent(...)` only works for agents running as main thread with `claude --agent`

MCP tools are also available if MCP servers are configured.

### Permission Modes

| Mode | Behavior |
| --- | --- |
| `default` | Standard permission checking with prompts |
| `acceptEdits` | Auto-accept file edits |
| `dontAsk` | Auto-deny permission prompts (explicitly allowed tools still work) |
| `bypassPermissions` | Skip all permission checks (dangerous!) |
| `plan` | Plan mode — read-only exploration |

If the parent uses `bypassPermissions`, it takes precedence and cannot be overridden.

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

## Process

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
4. **Write the agent file** using the Write tool. Include:
   - All relevant frontmatter fields
   - A focused system prompt in the body that tells the agent WHO it is, WHAT to do, and HOW to do it
5. **Verify** the file was created successfully

## Critical Rules for Writing Good Agents

### Description field (MOST IMPORTANT)

The `description` is the ONLY thing Claude reads when deciding whether to delegate. The body/system prompt is NOT visible to Claude until after delegation.

- Write it for Claude, not humans
- Include trigger phrases: "Use proactively when...", "MUST BE USED for..."
- List specific keywords that should trigger activation
- Be specific about the domain — vague descriptions lead to incorrect delegation

### System prompt (body)

- State the agent's role clearly
- Define a step-by-step workflow
- Specify what to look for or check
- Define output format
- Do NOT include "When to Activate" sections — Claude never sees the body before activation
- Do NOT reference other agents — subagents are standalone and cannot communicate

### Tool restrictions

- Grant ONLY necessary tools — principle of least privilege
- Read-only agents: `Read, Grep, Glob, Bash`
- Code modification agents: `Read, Write, Edit, Glob, Grep, Bash`
- Analysis/planning agents: `Read, Glob, Grep, Bash`
- Use `disallowedTools` when you want to inherit most tools but block a few

### Design principles (from official docs)

- **Design focused subagents**: each should excel at ONE specific task
- **Write detailed descriptions**: Claude uses description to decide when to delegate
- **Limit tool access**: grant only necessary permissions
- **Check into version control**: share project subagents with your team

## Output

After gathering requirements, write the agent file and confirm:

```text
Created: .claude/agents/my-agent.md
  Name: my-agent
  Model: sonnet
  Tools: Read, Grep, Glob, Bash
  Permission mode: default
```
