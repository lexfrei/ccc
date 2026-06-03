---
name: brew-cleanup
description: Reclaim Homebrew disk by removing old formula/cask versions, pruning the download cache, and uninstalling orphaned dependencies (brew autoremove). Shows a dry-run estimate first, then runs the user-chosen scope after approval. TRIGGER when the user wants to free Homebrew space ("brew cleanup", "почисти brew", "remove orphaned brew packages"). DO NOT trigger for uninstalling a specific named formula.
disable-model-invocation: true
---

Reclaim Homebrew disk space, then report what was freed.

Operates in **report → confirm → execute** order. The scope is chosen through an interactive question, not flags. After approval, run the cleanup autonomously.

## Step 1: Check Homebrew

```bash
command -v brew >/dev/null 2>&1
```

If `brew` is not installed, stop and say so. Otherwise note the cache location: `brew --cache`.

## Step 2: Dry-run report

Gather what each scope would do, without changing anything:

```bash
brew autoremove -n   # orphaned dependencies that would be uninstalled
brew cleanup -n      # old versions + stale cache; prints "This operation would free approximately N"
```

Report the orphan list from `autoremove -n` and the freed-space estimate from `cleanup -n`. Record baseline sizes of **every** location these scopes touch — not just the cache. `brew cleanup` removes old versions from the Cellar/Caskroom, and `brew autoremove` uninstalls formulae from the Cellar with little or no cache impact, so a cache-only measurement under-reports (and reads as 0 for autoremove). Capture all three:

```bash
du -sh "$(brew --cache)" "$(brew --cellar)" "$(brew --prefix)/Caskroom" 2>/dev/null
```

## Step 3: Ask what to run (interactive)

Explain each scope, then **ask the user** (interactive, multi-select) which to run:

- **Remove old versions + stale cache** — `brew cleanup`: deletes superseded versions of installed formulae/casks and cache older than the default retention. Safe; nothing currently installed is removed.
- **Uninstall orphaned dependencies** — `brew autoremove`: uninstalls formulae that were pulled in only as dependencies and are no longer required by anything. Review the dry-run list — a formula you use directly but never `brew install`ed explicitly would be removed (re-install with `brew install <name>` if needed).
- **Scrub the entire download cache** — `brew cleanup --prune=all`: also removes the latest cached downloads, not just stale ones. Frees more; the next `brew install`/upgrade re-downloads.

## Step 4: Execute (after approval)

Run the selected actions. If **autoremove** is selected, run it first, so the freshly-orphaned versions are then swept by the cleanup pass:

```bash
brew autoremove
```

For the cleanup pass, use the full-scrub variant if the user selected it, otherwise the standard one — selecting both the standard cleanup and the full scrub collapses to a single `--prune=all` run:

```bash
brew cleanup              # standard: old versions + stale cache
brew cleanup --prune=all  # full scrub: also removes the latest cached downloads
```

## Step 5: Report

Re-measure the same locations recorded in Step 2 — cache, Cellar, and Caskroom — and report the space reclaimed from the before/after delta, not the cache alone (old-version removal and `autoremove` free Cellar/Caskroom space with little or no cache impact). Prefer any explicit freed-space figure brew prints. List the formulae uninstalled by `autoremove` (if run) and what was kept.
