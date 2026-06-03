---
name: worktree-sweep
description: Find and remove stale git worktrees across one or many repositories. Classifies each extra worktree as clean / dirty / locked, measures reclaimable space, then removes the safe ones after approval. TRIGGER when the user wants to clean up, prune, or audit git worktrees ("remove old worktrees", "почисти worktree", "what worktrees can I delete"). DO NOT trigger for deleting whole repositories or non-worktree directories.
disable-model-invocation: true
argument-hint: "[path] [--all-repos]"
---

Find and remove stale git worktrees, then report reclaimed space.

Operates in **report → confirm → execute** order. Nothing is removed until the user approves the plan. After approval, perform the removals autonomously.

## Step 0: Determine the scan scope (never hardcode paths)

Resolve where to look, in this priority order:

1. A path passed in `$ARGUMENTS` — use it verbatim.
2. If the current working directory is inside a git repository and `--all-repos` was **not** passed — scope to that single repository.
3. If `--all-repos` was passed — find the hosting root by walking up from the current directory to the common clone root (the ancestor that contains many `<owner>/<repo>` directories). Confirm the resolved root with the user before scanning.
4. If none of the above resolves unambiguously — **ask the user** for the directory to scan. Do not assume a default like `~/git`.

For multi-repo scope, enumerate repositories by locating each `.git` directory (a directory, not a gitdir file) under the resolved root.

## Step 1: Enumerate worktrees

For each in-scope repository:

```bash
git -C "$REPO" worktree list --porcelain
```

The first entry is the main checkout — never a removal candidate. Every additional entry is a candidate. Also note the **current** worktree (the one this session runs in, if any) and exclude it.

## Step 2: Classify each candidate

For every candidate worktree path `$WT`:

- **Dirty** — uncommitted or untracked changes:

  ```bash
  git -C "$WT" status --porcelain
  ```

  A non-empty result means dirty. Inspect *what* changed before judging (see Step 4).

- **Locked** — `git worktree list --porcelain` prints a `locked` line. Read the lock reason. If it embeds a PID (e.g. `pid 29180`), check whether that process is still alive:

  ```bash
  ps -p "$PID" >/dev/null 2>&1 && echo live || echo stale
  ```

  A **stale** lock (dead PID) is safe to clear. A **live** lock means a process is actively using the worktree — never remove it.

- **Prunable** — the entry carries a `prunable` line. The `gitdir file points to non-existent location` reason (the working directory is gone) is reported immediately by plain `git worktree list --porcelain`; purely age-based prunability is instead gated by `gc.worktreePruneExpire` (default 3 months) unless `--expire` is passed. Either way, `git worktree prune` (Step 5) is the authoritative cleanup.

- **Clean** — none of the above. Safe to remove.

Measure reclaimable size per candidate with `du -sk "$WT"` and total it.

## Step 3: Report

Present a table: repository, worktree path, branch (or `detached HEAD`), classification, size. Sum the reclaimable total for the clean + stale-locked set. Call out separately:

- worktrees in **detached HEAD** with commits not reachable from any branch (removal orphans those commits — recoverable only via reflog until gc),
- dirty worktrees (held back pending Step 4),
- live-locked worktrees (skipped).

Ask for approval to remove the safe set.

## Step 4: Triage dirty worktrees

Do not blanket-remove dirty worktrees. Show the diff/stat and decide per item:

- **Trivial drift** — regenerated lockfiles (`package-lock.json`, `go.sum`), generated code (`zz_generated.*`), editor cruft, stray binaries not in git. Safe to discard with approval.
- **Real work** — hand-written source changes, an uncommitted refactor. Offer to keep the worktree, or commit/stash the change first, before removing. Never silently discard real work.

## Step 5: Execute (after approval)

For each approved worktree:

1. Stale lock → clear it first: `git -C "$REPO" worktree unlock "$WT"`.
2. **Restore the write bit before removing.** Build/module caches inside a worktree are often read-only directories. A plain remove can deregister the worktree from git's metadata and *then* fail mid-delete on the read-only directory, leaving an orphaned tree that git no longer tracks. Pre-empt it:

   ```bash
   chmod -R u+w "$WT"
   git -C "$REPO" worktree remove --force "$WT"
   ```

3. After processing a repo: `git -C "$REPO" worktree prune` to clear prunable and any stale admin refs.

If a worktree was already deregistered but its directory remains on disk (orphaned), remove the directory tree directly — `git worktree remove` no longer applies to it.

## Step 6: Report reclaimed space

Re-measure and report total space freed, the count removed, and anything intentionally kept (dirty-real-work, live-locked) with the reason.
