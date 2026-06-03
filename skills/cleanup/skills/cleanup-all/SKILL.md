---
name: cleanup-all
description: Run the full local cleanup pipeline — stale git worktrees, dead personal forks, Docker prune, and Go caches — in one pass, each stage report → confirm → execute, then a combined reclaimed-space summary. TRIGGER when the user wants a broad disk cleanup ("free up disk space", "почисти всё", "run the cleanup pipeline"). DO NOT trigger when the user clearly wants only one specific cleaner — invoke that skill instead.
disable-model-invocation: true
argument-hint: "[path] [--skip worktrees,forks,docker,go] [--volumes] [--keep-modcache] [--delete-remote]"
---

Orchestrate the cleanup skills end to end and report total disk reclaimed.

Each stage keeps its own **report → confirm → execute** gate — the user approves (or skips) each one independently. After each stage's approval, perform that stage's removals autonomously.

## Step 0: Resolve shared inputs once (never hardcode paths)

- **Scan root** for the filesystem stages (worktrees, forks): resolve from `$ARGUMENTS`, else infer the hosting root by walking up from the current directory and **confirm with the user**, else **ask**. Do not assume a default. Resolve this once and reuse it for both filesystem stages.
- Parse stage flags: `--skip` (comma list of `worktrees`, `forks`, `docker`, `go`), and the pass-through flags `--volumes`, `--keep-modcache`, `--delete-remote`.

Announce the plan: which stages will run, in what order, with the resolved scan root.

## Stages (run in order, skip any listed in `--skip`)

Run each by following the corresponding sibling skill in this plugin. Carry the running total of reclaimed space across stages.

1. **worktrees** → `worktree-sweep` on the resolved scan root (`--all-repos` scope). Remove safe worktrees; triage dirty ones.
2. **forks** → `stale-forks` on the resolved scan root. Remove dead local clones; honor `--delete-remote` for GitHub forks.
3. **docker** → `docker-prune`. Honor `--volumes` (opt-in).
4. **go** → `go-cache`. Honor `--keep-modcache` (opt-in; default clears the module cache too).

If a stage's prerequisite is absent (no Docker daemon, no `go`, no repositories under the root), report that and continue to the next stage instead of failing the pipeline.

## Final report

A single table: stage, items removed, space reclaimed, and anything intentionally kept (with reasons — dirty-real-work, live-locked worktrees, forks with open PRs, preserved volumes, kept modcache). End with the combined total reclaimed across all stages.
