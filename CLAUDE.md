# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Claude Code Companions (CCC) — an external marketplace repository for Claude Code plugins. It contains no application code; only plugin definitions (agents, skills, MCP servers) distributed via the Claude Code plugin marketplace system.

## Repository Structure

Top-level directories group plugins by their primary component type, and one plugin may ship several types. There is no top-level `agents/` directory: agents are always a directory inside a plugin, so a plugin that ships only agents lives under `skills/` as well.

- **`skills/`** — Skill definitions (markdown prompts in `skills/<name>/skills/<skill>/SKILL.md`, metadata in `skills/<name>/.claude-plugin/plugin.json`). A single skill plugin can bundle multiple skills (e.g., `review-toolkit` contains `branch-review`, `pr-review`), and it can also ship agents in `skills/<name>/agents/<agent>.md` — `become` bundles a set of specialist agents next to its roles. Claude Code scans that directory automatically
- **`mcp/`** — MCP server definitions (server config in `mcp/<name>/.mcp.json`, metadata in `mcp/<name>/.claude-plugin/plugin.json`)
- **`hooks/`** — Hook plugins (hook config in `hooks/<name>/hooks/hooks.json`, scripts in `hooks/<name>/scripts/`, metadata in `hooks/<name>/.claude-plugin/plugin.json`)

The marketplace registry is `.claude-plugin/marketplace.json` — it indexes all plugins with names, descriptions, source paths, and categories.

## Adding a New Plugin

1. Create the directory under the appropriate type (`skills/`, `mcp/`, or `hooks/`)
2. Add `.claude-plugin/plugin.json` with name, version, description, author
3. Add the content file(s): `skills/<skill>/SKILL.md` for skills, `agents/<agent>.md` for agents, `.mcp.json` for MCP servers, `hooks/hooks.json` + scripts for hooks — all relative to the plugin root
4. Add a `README.md` in the plugin directory: what the plugin does, installation commands, a section per bundled skill/agent, and how to extend it if applicable (convention applies to new plugins; older plugins are backfilled opportunistically)
5. Register the plugin in `.claude-plugin/marketplace.json` under the `plugins` array
6. Update `README.md` to include the new plugin in the appropriate table

## Validation

No build system, linters, or tests. Two validator invocations, and they check different things: `claude plugin validate .` at the repo root covers manifests, `source` path syntax, and `renames` chains but never opens an agent file, while `claude plugin validate ./<path-to-plugin>` also parses each agent's frontmatter and fails on YAML that would load with every field silently dropped. Run the root form after editing `marketplace.json` and the per-plugin form after touching an agent.

Know the gaps, because each one is a place the validator says "passed" over a broken tree. A `source` pointing at a directory that does not exist passes — only malformed paths are rejected — so a deleted or renamed plugin directory is caught by nothing but a manual check. Field values are never checked either: an invalid `color`, an unknown model, or a `permissionMode` that plugin agents silently ignore all pass. The rest is manual: entries match the actual directory structure, plugin.json metadata is correct, a plugin's description is identical in `plugin.json` and its marketplace entry, and every plugin whose content changed carries a version bump before the branch is published — one bump per branch covering all of its commits, not one per commit. `claude plugin validate` checks neither of those two.

## Content Guidelines

- Agent prompts are standalone markdown files — they define persona, workflow, and constraints. Keep the frontmatter minimal: a plugin-shipped agent drops `hooks`, `mcpServers`, and `permissionMode`, and `tools` is omitted so an agent inherits the full toolset, because a per-agent allowlist fails by omission and silently
- Skill prompts use SKILL.md with frontmatter (name, description, triggers)
- MCP plugins reference external Docker images via `.mcp.json` config
- Hook plugins define lifecycle hooks in `hooks/hooks.json` with optional scripts
- All content in English
