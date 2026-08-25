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

### Skills

The ten standalone agent plugins are gone. Nine of their agents ship inside **become**, renamed to their craft; the tenth was dropped. The old-to-new mapping is in [its README](skills/become/README.md#upgrading-from-the-standalone-agent-plugins).

| Plugin | Description |
| --- | --- |
| **review-toolkit** | Code review pipeline: branch review with merge-base attribution (only defects the diff introduced, worsened, or interacts with block; pre-existing ones are reported separately and never dropped), churn diagnostics for review loops, PR review with a readiness gate (fix-CI / fix-conflicts, no verdict), a value/design gate (should this change exist at all — value vs maintenance cost), dual-model analysis (Claude + Codex), and GitHub PR review publishing with evidence-based verification |
| **address-pr-comments** | Close out unresolved review comments across one or more PRs — verify, fix with auto-pushed signed commits (one per thread), post user-approved replies, restore original branch |
| **git-tools** | Git workflow utilities: fork refresh and repo setup with branch protection |
| **genname** | Generate a `/rename` command from type, title, and optional PR number |
| **tldrpr** | Generate plain-text TLDR summaries for PRs, ready for Slack |
| **learn** | Analyze the current session and extract key learnings into CLAUDE.md and memory |
| **renovate-check** | Run Renovate locally in dry-run mode, research migration guides, apply selected updates |
| **agent-father** | Interactive guide for creating Claude Code subagents following official documentation standards |
| **billy** | "Where's the proof, Billy?" — stop and prove a claim with deep investigation |
| **doe** | Design-of-experiments toolkit for cutting debugging and tuning iterations. Ships **taguchi** (orthogonal arrays L4–L18: minimal run plans, main-effects ranking, accusation/acquittal confirmation), **pairwise** (self-verifying covering-array generator for arbitrary level mixes), **shrink** (group testing / delta debugging for single-culprit hunts among many toggles), **tune** (S/N-ratio knob optimization with confirmation runs) |
| **m4b-audiobook** | Assemble m4b audiobook from audio files with chapters, metadata, and cover art |
| **say** | Speak text aloud using macOS TTS with automatic voice selection |
| **slack-formatter** | Copy markdown to macOS clipboard as rich HTML + plain-text fallback, ready for Cmd+V into Slack with formatting preserved |
| **helm-add-gwapi-route** | Add or modernize Gateway API *Route templates (HTTPRoute/GRPCRoute/TLSRoute/TCPRoute/UDPRoute) in a Helm chart. Auto-detects add vs update mode per route kind; applies current best practices (named rules, typed filters, optional BackendTLSPolicy). File edits only — no git operations |
| **pore-analysis** | Measure porosity, pore size/shape, lattice period and ordering (psi6, Voronoi, radial g(r) + orientational correlation length) from top-view SEM images of porous films such as anodic aluminium oxide. The agent reads the image to calibrate and crop; a Python core does the morphometry and flags results that contradict physics. Vision decides, Python computes — no hardcoded autodetect |
| **cleanup** | Local disk cleanup: stale git worktrees, dead personal forks, Docker prune (incl. non-default buildx builders and VM disk trim), Go caches, and Homebrew — each report → confirm → execute with interactive prompts, plus a `cleanup-all` pipeline. Paths are asked, never hardcoded |
| **lkml** | Linux kernel mailing-list workflow. Ships **lore** (thread fetch, search, and reply monitoring on lore.kernel.org with plain curl, incl. the User-Agent gate), **patch-status** (patchwork state → next action, ping rules), **reply** (in-thread review responses: interleaved trimmed quoting, answer-every-comment, send via `git send-email --in-reply-to`), **submit** (series posting gates: recipients, tree prefixes, changelog under scissors, checkpatch, `Assisted-by:` disclosure, 24-hour rule — every version a new thread), **etiquette** (who to write to via MAINTAINERS, tag permission matrix, timing and tone norms) |
| **become** | Session role switches plus the specialist agents they run. Manager (`/become:manager`): lead of a subagent fleet — brief teammates, delegate whole loops, approve their output inside the delegated scope, integrate by ground truth, report upward in short digests. Bundled workforce, spawnable as teammates or callable as `@agent-become:<name>`: **architecture** (technical decisions, `.architecture.yaml`), **go**, **python**, **templ** (Templ + HTMX), **kubernetes** (manifests, ArgoCD), **helm** (charts), **containers** (image builds), **quality** (lint, tests, security, then commit and push), **hygiene** (AI-artifact cleanup) |

### MCP Servers

| Plugin | Description |
| --- | --- |
| **mcp-loki** | [Grafana Loki](https://github.com/lexfrei/mcp-loki) — LogQL queries, label discovery, series exploration, index statistics |
| **mcp-transmission** | [Transmission](https://github.com/lexfrei/mcp-transmission) — torrent management, session stats, queue and bandwidth control |
| **mcp-tg** | [Telegram](https://github.com/lexfrei/mcp-tg) — MTProto client API, messaging, contacts, groups, channels, media handling |

### Hooks

| Plugin | Description |
| --- | --- |
| **comment-hygiene** | SessionStart hook that injects code-comment discipline into every session — every comment must earn its place: say what the code cannot, never duplicate it; bans narration, changelog comments, reviewer asides, signature-restating docstrings, and leaky provenance |
| **golangci-lint** | Auto-run golangci-lint on package when Go files are edited |
| **md-no-hardwrap** | PreToolUse hook: reject `Write`/`Edit` on markdown files when a paragraph spans more than one line — enforces "one continuous line per paragraph" so renderers wrap to viewer width instead of fighting hardwraps in the source |
| **worksync** | Daily work-sync markdown log — PostToolUse hook captures `gh pr/issue create/merge/close` automatically, companion skill logs research/ops/checkpoint events (prompts for vault path on install, works with Obsidian, Logseq, or plain markdown) |

## License

[BSD-3-Clause](LICENSE)
