# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Claude Code Companions (CCC) — an external marketplace repository for Claude Code plugins. It contains no application code; only plugin definitions (agents, skills, MCP servers) distributed via the Claude Code plugin marketplace system.

## Repository Structure

Three plugin types, each in its own top-level directory:

- **`agents/`** — Agent definitions (markdown prompts in `agents/<name>/agents/<name>.md`, metadata in `agents/<name>/.claude-plugin/plugin.json`)
- **`skills/`** — Skill definitions (markdown prompts in `skills/<name>/skills/<skill>/SKILL.md`, metadata in `skills/<name>/.claude-plugin/plugin.json`). A single skill plugin can bundle multiple skills (e.g., `review-toolkit` contains `branch-review`, `final-review`, `pr-review`)
- **`mcp/`** — MCP server definitions (server config in `mcp/<name>/.mcp.json`, metadata in `mcp/<name>/.claude-plugin/plugin.json`)

The marketplace registry is `.claude-plugin/marketplace.json` — it indexes all plugins with names, descriptions, source paths, and categories.

## Adding a New Plugin

1. Create the directory under the appropriate type (`agents/`, `skills/`, or `mcp/`)
2. Add `.claude-plugin/plugin.json` with name, version, description, author
3. Add the content file(s): `.md` for agents, `SKILL.md` for skills, `.mcp.json` for MCP servers
4. Register the plugin in `.claude-plugin/marketplace.json` under the `plugins` array
5. Update `README.md` to include the new plugin in the appropriate table

## Validation

No build system, linters, or tests. Validation is manual: ensure `marketplace.json` entries match actual directory structure, and plugin.json files have correct metadata.

## Content Guidelines

- Agent prompts are standalone markdown files — they define persona, tools, workflow, and constraints
- Skill prompts use SKILL.md with frontmatter (name, description, triggers)
- MCP plugins reference external Docker images via `.mcp.json` config
- All content in English
