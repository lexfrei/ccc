# become

Session role switches for Claude Code, plus the specialist agents those roles put to work. Each skill in this plugin turns the current session into a specific role that holds for the rest of the session; each agent is a worker that role delegates to. Roles are invoked as `/become:<role>`, agents as `@agent-become:<agent>`.

The two halves ship together on purpose: `become:manager` spawns teammates, and the agents below are the workforce it spawns. Installing the role without the workers, or the workers without the role, leaves half a system.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install become@claude-code-companions
```

## Skills

### `/become:manager`

Turns the session into the manager of a subagent fleet instead of an executor: it briefs teammates, delegates whole loops, approves their output inside the delegated scope, integrates results by ground truth, and reports upward in short digests.

What the role enforces:

- **Entry gates** — first, whether the task needs a team at all (a fleet costs several times a single session and pays off only for context isolation, real parallelism, or specialization); second, that the manager seat runs on the strongest available model while teammates get an explicit cost-scaled model per task.
- **Decomposition** — split at context boundaries rather than work types, disjoint file ownership per teammate, tasks sized to self-contained deliverables.
- **Team topology** — one standing investigator per session, fix-review loops owned end-to-end by the implementing teammate (one gate at a time), one-shot workers killed after their work is saved, teammates retired at the first opportunity rather than reused (a "finished" report is about the task, not the agent's exit — only a verified stop frees the seat), capped concurrency.
- **Briefing** — success criteria, essential context only, a fixed per-situation gate set before the work starts (for code: an independent review run to consecutive clean verdicts on the same frozen commit, reset only by a false claim or a code defect; for non-code work: an observable world-state predicate named in advance; for mutation testing: proof that each mutation applied, hit its claimed scope, and left the artifact valid), pre-registered success criteria in the PR body, a bounded SHA-first report format with mandatory fields (gate count, claim locations, measurement base with its because-clause), a comms contract that treats the channel as lossy in both directions and decaying with distance (contract lines re-attached to later messages, not assumed from the brief), hard boundaries; plan approval for risky workstreams.
- **Gate conduct** — a churn-vs-feature meta-counter with a stop flag for rounds that break previously correct text, a frozen surface scoped to what the round reads (the tree and its diff, not gitignored drafts), LGTMs burned for false claims rather than true-but-unpinned ones, findings classified by their defect rather than their cure, criteria conflicts resolved by subject (describes the world vs changes it), cures approved only when red on the finding's scenario, section placement read as the reviewer's blocking assessment rather than truth, manager decisions bound to their premises, deletions that name what the removed fragment asserted, reviewer corrections verified like findings.
- **Integration** — frozen SHAs pushed at freeze time, push only an explicitly stated final SHA, run the session's own quality gate on the assembled result, verify by ground truth rather than notifications, treat a clean merge as textual rather than semantic evidence, distrust agent listings after a context compaction, add an adversarial blackbox verifier when stakes warrant it.
- **Findings bookkeeping** — every out-of-scope finding gets a home (an issue, a registry entry, or a written disposition) before its gate closes; duplicate checks run over the registry and the public tracker both; records carry proportion alongside mechanism; a defect-class registry the manager reads before approving techniques.
- **Approval boundary** — agent output inside the delegated scope is approved by the manager; anything leaving it (messages to people, other repositories, external services) waits for the user. Publication runs a checklist on the full text (premises against origin/main, quotes diffed against source after global replacements, totals recomputed with their excluded terms, links opened), retracted claims are swept across an enumerated surface list including commit bodies and out-of-tree working files, and published lists keep their entries as addresses rather than category names.
- **Claim verification** — recompute rather than recognize result-shaped claims, compare numbers only after establishing a shared denominator (run the original author's formula), verify with your own method and tooling from main, relay foreign numbers with attribution that keeps them checkable, return report-derived generalizations as hypotheses to check against the full set, treat two identical observations at different tracks as a base rate, derive filing actions from world state, treat a threshold raise as widening what can hide under it.
- **Carriers** — every rule adopted mid-session names the mechanism that executes it instead of memory (a machine check, a mandatory report field, the grammar of the required phrase), bound to an action rather than a state of mind; rules ship with the input on which they break; issued carriers are tested on divergent states and a past defect before going out; threshold carriers catch accumulation and advisory carriers narrow searches without ruling; a finding stays open until a carrier exists for it.

## Agents

Specialist agents, each a standalone persona with its own standards and prohibitions. Spawn one as a fleet teammate, or call it directly with `@agent-become:<name>`. The names are deliberately plain, which means a bare `--agent go` can become ambiguous if another installed plugin ever ships its own `go`; the scoped form always resolves.

| Agent | What it does |
| --- | --- |
| **architecture** | Technical architect and repository knowledge keeper — library and framework choice, design patterns, ADRs, owns `.architecture.yaml` as the single source of truth |
| **go** | Go implementation, test-first — cloud-native services with Echo, slog, and cockroachdb/errors |
| **python** | Python implementation, test-first — FastAPI, Pydantic, structlog, strict typing, code treated as craft |
| **templ** | Web UI in Go Templ and HTMX — server-side rendering, progressive enhancement, WCAG 2.1 AA accessibility as a hard requirement |
| **kubernetes** | Kubernetes manifests and ArgoCD applications — production-ready, zero-trust networking, GitOps conventions |
| **helm** | Helm charts, test-first — helm-unittest tests written before the templates they cover |
| **containers** | Container images — multi-stage builds, distroless bases, minimal attack surface |
| **quality** | Validation and delivery — linters, tests, security checks, `.architecture.yaml` compliance, then the git commit and push once everything passes |
| **hygiene** | AI-artifact cleanup — removes narrating comments, verbose documentation, and naming that reads as generated |

### Upgrading from the standalone agent plugins

These agents used to ship as ten separate plugins. Installing `become` replaces nine of them and drops the tenth, and the marketplace migrates the old plugin names automatically on Claude Code v2.1.193 or newer — earlier versions ignore the migration map and report `plugin-not-found` for the old names. Either way the invocation names changed, so `@agent-kube-pilot` no longer resolves to anything:

| Was | Now |
| --- | --- |
| `chart-builder` | `@agent-become:helm` |
| `code-guardian` | `@agent-become:quality` |
| `doc-curator` | `@agent-become:hygiene` |
| `docker-smith` | `@agent-become:containers` |
| `gopher-builder` | `@agent-become:go` |
| `kube-pilot` | `@agent-become:kubernetes` |
| `snake-charmer` | `@agent-become:python` |
| `tech-oracle` | `@agent-become:architecture` |
| `templ-weaver` | `@agent-become:templ` |
| `task-orchestrator` | removed — `/become:manager` decomposes work at the fleet level |

Frontmatter is deliberately minimal: `name`, `description`, `model`, `color`. No `tools` allowlist, so every agent inherits the full toolset. Per-agent filtering was dropped because it never paid for itself: the list has to enumerate everything the agent will ever need, and it fails by omission, silently, as a capability the agent turns out not to have. Where a restriction is genuinely wanted, `disallowedTools` denies a few tools without enumerating the rest. It was considered for `quality`, the one agent here that commits and pushes, and declined: `Bash` stays inherited either way, so denying `Write` and `Edit` removes the direct route to a file and leaves the indirect one, and a file that reads as guarded while a shell redirect walks around the guard is worse than one that states its rule. The constraint it would have expressed is carried in that agent's own prompt instead — it is the gate, not the author, and it reports a failing check rather than editing the code to make it pass, because an edit of its own would ship under a report saying only that validation passed. No `hooks`, `mcpServers`, or `permissionMode` either: the loader warns about all three and then builds the agent definition without them, so a plugin-shipped agent never carries any of the three whatever the file says. The `model` value is only a default: an explicit model on the spawn call overrides it, and `become:manager` passes one on every call. It matters when you invoke an agent directly — `architecture` defaults to `opus` because the role is judgment-heavy, every other agent to `sonnet`.

## Extending

Add a new role as `skills/<role>/SKILL.md` inside this plugin and list it in the plugin description. It becomes available as `/become:<role>` with no other changes.

Add a new agent as `agents/<name>.md` with the same four frontmatter fields. Claude Code scans `agents/` automatically, so the file is the whole change — but list the agent in the plugin description and in the table above, and keep the description identical in `plugin.json` and the marketplace entry.
