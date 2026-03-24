# Claude Code Companions (CCC)

External marketplace repository for Claude Code plugins.

## Installation

First, add the marketplace:

```bash
/plugin marketplace add lexfrei/ccc
```

Then install any plugin:

```bash
/plugin install <plugin-name>@claude-code-companions
```

Or browse available plugins interactively via `/plugin` → **Discover** tab.

## Updating

Update all plugins from the marketplace:

```bash
/plugin marketplace update claude-code-companions
```

Update a specific plugin:

```bash
/plugin update <plugin-name>@claude-code-companions
```

Or enable automatic updates: `/plugin` → **Marketplaces** tab → select `claude-code-companions` → **Enable auto-update**.

## Plugins

### Agents

| Plugin | Description |
| --- | --- |
| **task-orchestrator** | Project analysis and planning — decomposes complex tasks, creates implementation plans, identifies risks |
| **tech-oracle** | Technical architect — manages .architecture.yaml, creates ADRs, evaluates technology choices |
| **gopher-builder** | Go developer — TDD specialist for cloud-native apps with Echo, slog, cockroachdb/errors |
| **snake-charmer** | Python developer — TDD specialist treating code as art, with FastAPI, Pydantic, structlog |
| **templ-weaver** | Frontend specialist — Go Templ + HTMX with server-first rendering and WCAG 2.1 AA accessibility |
| **kube-pilot** | Kubernetes specialist — secure, production-ready K8s manifests and ArgoCD with zero-trust networking |
| **chart-builder** | Helm chart TDD specialist — production-ready charts with helm-unittest |
| **docker-smith** | Containerization specialist — optimized, secure Containerfiles with multi-stage builds |
| **code-guardian** | Code quality validation — linters, tests, security checks, .architecture.yaml compliance |
| **doc-curator** | AI artifact cleanup — removes AI-generated comments, excessive docs, non-professional patterns |

### Skills

| Plugin | Description |
| --- | --- |
| **review-toolkit** | Code review pipeline: branch review, PR final review with dual-model analysis (Claude + Codex), and GitHub PR review publishing with evidence-based verification |
| **git-tools** | Git workflow utilities: fork refresh and repo setup with branch protection |
| **genname** | Generate a `/rename` command from type, title, and optional PR number |
| **tldrpr** | Generate plain-text TLDR summaries for PRs, ready for Slack |
| **learn** | Analyze the current session and extract key learnings into CLAUDE.md and memory |
| **renovate-check** | Run Renovate locally in dry-run mode, research migration guides, apply selected updates |
| **agent-father** | Interactive guide for creating Claude Code subagents following official documentation standards |
| **billy** | "Where's the proof, Billy?" — stop and prove a claim with deep investigation |
| **m4b-audiobook** | Assemble m4b audiobook from audio files with chapters, metadata, and cover art |
| **say** | Speak text aloud using macOS TTS with automatic voice selection |

### MCP Servers

| Plugin | Description |
| --- | --- |
| **mcp-loki** | [Grafana Loki](https://github.com/lexfrei/mcp-loki) — LogQL queries, label discovery, series exploration, index statistics |
| **mcp-transmission** | [Transmission](https://github.com/lexfrei/mcp-transmission) — torrent management, session stats, queue and bandwidth control |

## License

[BSD-3-Clause](LICENSE)
