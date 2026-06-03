---
name: cleanup-all
description: Run the full local cleanup pipeline — stale git worktrees, dead personal forks, Docker prune, Go caches, and Homebrew — in one pass, each stage report → confirm → execute, then a combined reclaimed-space summary. TRIGGER when the user wants a broad disk cleanup ("free up disk space", "почисти всё", "run the cleanup pipeline"). DO NOT trigger when the user clearly wants only one specific cleaner — invoke that skill instead.
disable-model-invocation: true
argument-hint: "[path]"
---

Orchestrate the cleanup skills end to end and report total disk reclaimed.

Each stage keeps its own **report → confirm → execute** gate, and each gathers its own options through interactive questions — this orchestrator passes no flags. The user approves (or skips) each stage independently.

## Step 0: Resolve shared inputs (never hardcode paths)

- **Scan root** for the filesystem stages (worktrees, forks): resolve from `$ARGUMENTS`, else infer the hosting root by walking up from the current directory and **ask the user** to confirm or correct it, else **ask** outright. Do not assume a default. Resolve this once and reuse it for both filesystem stages.
- **Which stages to run**: **ask the user** (interactive, multi-select) which of the five stages to include — worktrees, forks, docker, go, brew. Default to all available ones.

Announce the plan: which stages will run, in what order, with the resolved scan root.

## Stages (run the selected ones in order)

Run each by following the corresponding sibling skill in this plugin. Each sibling asks its own scope questions (volumes, modcache, delete-remote, etc.) — do not try to pre-answer them here. Carry the running total of reclaimed space across stages.

1. **worktrees** → `worktree-sweep` on the resolved scan root (all-repos scope). Remove safe worktrees; triage dirty ones.
2. **forks** → `stale-forks` on the resolved scan root. Remove dead/reclonable local clones; the sibling asks per-fork about deleting the GitHub fork.
3. **docker** → `docker-prune`. The sibling asks which scopes (images/cache, volumes, non-default buildx builders).
4. **go** → `go-cache`. The sibling asks whether to include the module cache.
5. **brew** → `brew-cleanup`. The sibling asks which scopes (cleanup, autoremove, full cache scrub).

If a stage's prerequisite is absent (no Docker daemon, no `go`, no `brew`, no repositories under the root), report that and continue to the next stage instead of failing the pipeline.

## Final report

A single table: stage, items removed, space reclaimed, and anything intentionally kept (with reasons — dirty-real-work, live-locked worktrees, forks with open PRs or local-only commits, preserved volumes, kept modcache, kept brew formulae). End with the combined total reclaimed across all stages.
