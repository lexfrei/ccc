---
name: stale-forks
description: Find personal forks that no longer carry value — their unique commits are already merged upstream, or they hold no unique commits at all — and remove the local clone after approval. Optionally delete the GitHub fork too. TRIGGER when the user wants to clean up dead forks ("remove merged forks", "почисти бесполезные форки", "which forks can I drop"). DO NOT trigger for non-fork repositories or for forks with open PRs / unmerged work.
disable-model-invocation: true
argument-hint: "[path] [--delete-remote]"
---

Find personal forks that are no longer useful and reclaim their space.

Operates in **report → confirm → execute** order. After approval, remove the local clones autonomously. Deleting the **GitHub** fork is a separate, explicit confirmation (it is irreversible and outward-facing).

## Step 0: Determine the scan scope (never hardcode paths)

1. A path in `$ARGUMENTS` → use it.
2. Otherwise infer the hosting root by walking up from the current directory to the common clone root, and **confirm it with the user**.
3. If unresolved → **ask** for the directory to scan. Do not assume a default.

Enumerate repositories under the resolved root (each `.git` directory).

## Step 1: Identify personal forks

Determine the authenticated user once: `gh api user --jq .login` → `$ME`.

A repository is a **personal fork** when:

- it has an `upstream` remote (`git -C "$REPO" remote get-url upstream` succeeds), **or**
- `gh repo view --json isFork,parent,owner,nameWithOwner` (run inside the repo) reports `isFork == true` **and** `owner.login == $ME`.

Skip anything that is not a personal fork. Record the upstream `nameWithOwner` and default branch for each fork.

## Step 2: Assess usefulness

For each fork, refresh refs first: `git -C "$REPO" fetch --all --quiet` (and `git fetch upstream` if that remote exists).

Resolve the upstream default branch (`gh repo view <upstream> --json defaultBranchRef` or `git remote show upstream`). Then evaluate:

- **Dirty** — uncommitted changes (`git status --porcelain` non-empty) → **keep**, flag it.
- **Unique commits** — any commit on any local branch or on `origin/*` that is not reachable from `upstream/<default>`:

  ```bash
  git -C "$REPO" log --oneline --branches --remotes --not upstream/<default> | head
  ```

  If empty → the fork contributes nothing beyond upstream. This compares against the upstream **default** branch only; a fork whose work was merged into a non-default upstream branch (e.g. `release-*`, `develop`) will conservatively show unique commits and be kept — a safe-by-default bias, never a false deletion.
- **Open PRs** — does the fork have an open PR into upstream?

  ```bash
  gh pr list --repo <upstream> --state open --author "$ME" --json headRefName,url
  ```

  If any → **keep**, flag it.

Classify:

- **Dead — already merged / no unique commits**: no unique commits, no open PR, not dirty → removal candidate.
- **Has unique unmerged commits, no open PR**: possible abandoned work → **flag, do not auto-select**. Let the user decide explicitly.
- **Keep**: dirty, or has an open PR.

## Step 3: Report

Table: fork, upstream, classification, reason, local size (`du -sh`). List removal candidates separately from flagged-keep. Show the total reclaimable size of the candidate set. Ask for approval.

## Step 4: Execute (after approval)

For each approved dead fork:

1. Remove the local clone directory tree (the whole repo directory). This reclaims the disk space.
2. **GitHub fork** — only if `--delete-remote` was passed **and** the user confirms again for each fork (it is irreversible):

   ```bash
   gh repo delete <owner>/<repo> --yes
   ```

   This needs the `delete_repo` token scope (`gh auth refresh --scopes delete_repo` if missing). Without `--delete-remote`, leave the GitHub fork untouched and simply note that it can be deleted later.

## Step 5: Report

Report local space reclaimed, clones removed, GitHub forks deleted (if any), and every fork kept/flagged with its reason.
