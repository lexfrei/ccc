---
name: stale-forks
description: Find personal forks that no longer carry value — their unique commits are already merged upstream, or they hold no unique commits at all — and remove the local clone after approval. Optionally delete the GitHub fork too. TRIGGER when the user wants to clean up dead forks ("remove merged forks", "почисти бесполезные форки", "which forks can I drop"). DO NOT trigger for non-fork repositories or for forks with open PRs / unmerged work.
disable-model-invocation: true
argument-hint: "[path]"
---

Find personal forks that are no longer useful and reclaim their space.

Operates in **report → confirm → execute** order. After approval, remove the local clones autonomously. Deleting the **GitHub** fork is a separate interactive confirmation (it is irreversible and outward-facing). Choices are gathered through interactive questions, not flags.

## Step 0: Determine the scan scope (never hardcode paths)

1. A path in `$ARGUMENTS` → use it.
2. Otherwise infer the hosting root by walking up from the current directory to the common clone root, and **ask the user** to confirm or correct it (interactive question).
3. If unresolved → **ask** for the directory to scan. Do not assume a default.

Enumerate repositories under the resolved root (each `.git` directory).

## Step 1: Identify personal forks

Determine the authenticated user once: `gh api user --jq .login` → `$ME`.

A repository is a **personal fork** when:

- it has an `upstream` remote (`git -C "$REPO" remote get-url upstream` succeeds), **or**
- `gh repo view --json isFork,parent,owner,nameWithOwner` (run inside the repo) reports `isFork == true` **and** `owner.login == $ME`.

Skip anything that is not a personal fork. Record the upstream `nameWithOwner` and default branch for each fork.

A fast inventory shortcut for many forks: `gh repo list "$ME" --fork --limit 300 --json name,parent,defaultBranchRef`, then intersect with local clones present under the root.

## Step 2: Assess usefulness

Removing a local clone while keeping the GitHub fork is reversible (re-clone later), so the **only irrecoverable risk is local-only work**. Check it first, cheaply, with no network:

- **Dirty** — uncommitted changes (`git status --porcelain` non-empty) → **keep**, flag it.
- **Local-only commits** — commits on any local branch not present on any remote: `git -C "$REPO" log --oneline --branches --not --remotes`. Non-empty → **keep**, flag it (removing the clone would lose them).

Then assess whether the fork itself is still useful (this is what makes it a *candidate*, vs just reclonable):

- **Unique commits vs upstream** — `git -C "$REPO" log --oneline --branches --remotes --not upstream/<default>` (resolve the upstream default branch first). Empty → contributes nothing beyond upstream. This compares against the **default** branch only; work merged into a non-default upstream branch will conservatively show as unique and be kept — safe-by-default, never a false deletion.
- **Open PRs** — `gh pr list --repo <upstream> --state open --author "$ME"` (or one cross-repo pass: `gh search prs --author=@me --state=open`). An open PR means the fork is active → flag.

Classify:

- **Dead / reclonable** — no local-only work (everything pushed). The clone can be removed and re-cloned on demand. Strongest candidates are those that are also merged/no-unique-commits with no open PR.
- **Keep** — dirty, local-only commits, or an open PR you are actively driving.

## Step 3: Report and ask

Table: fork, upstream, classification, reason, local size (`du -sh`). Group removal candidates separately from keep/flagged, with the total reclaimable size. Then **ask the user** (interactive question) which set of local clones to remove — e.g. only dead-and-reclonable, or all reclonable (including active-PR clones, which would then need a re-clone to resume).

## Step 4: Execute (after approval)

For each approved fork, remove the local clone directory tree (the whole repo directory) to reclaim the disk. If read-only cache directories block removal, restore the write bit first (`chmod -R u+w`).

Then, for the **GitHub** fork, **ask the user** (interactive question) whether to also delete it on GitHub — default **no**. Only on an explicit yes, per fork:

```bash
gh repo delete <owner>/<repo> --yes
```

This needs the `delete_repo` token scope (`gh auth refresh --scopes delete_repo` if missing). If the user declines, leave the GitHub fork untouched and note it can be deleted later.

## Step 5: Report

Report local space reclaimed, clones removed, GitHub forks deleted (if any), and every fork kept/flagged with its reason.
