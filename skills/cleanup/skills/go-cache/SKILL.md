---
name: go-cache
description: Reclaim Go disk by clearing the build, test, fuzz, and module caches. Measures each cache first, then cleans the user-chosen scope after approval. TRIGGER when the user wants to free Go cache space ("clean go cache", "почисти go кеши", "reclaim GOMODCACHE"). DO NOT trigger for cleaning a specific module or running go mod tidy.
disable-model-invocation: true
---

Reclaim Go cache disk space, then report what was freed.

Operates in **report → confirm → execute** order. The scope is chosen through an interactive question, not flags. After approval, run the cleanup autonomously.

## Step 1: Locate and measure the caches

```bash
go env GOCACHE GOMODCACHE
```

- `GOCACHE` holds the build, test, and fuzz caches — fully regenerated on the next build.
- `GOMODCACHE` holds downloaded module sources — re-downloaded on the next `go build`/`go mod download`. It is usually the largest, often tens of GB.

Measure both: `du -sh "$GOCACHE"` and `du -sh "$GOMODCACHE"`. If `go` is not installed, stop and say so.

## Step 2: Report and ask (interactive)

Show the size of each cache and the total reclaimable, then **ask the user** (interactive question) which scope to clear:

- **build + test + fuzz only** — keeps the module cache, so the next build does not re-download dependencies.
- **everything, including the module cache** — frees the most, but the next build re-downloads all modules.

Note that either way the next build is slower while caches repopulate.

## Step 3: Execute (after approval)

Build, test, and fuzz caches:

```bash
go clean -cache -testcache -fuzzcache
```

Module cache (only if the user chose to include it):

```bash
go clean -modcache
```

`go clean -modcache` handles the read-only permission bits that Go sets on cached module files — no manual `chmod` needed.

## Step 4: Report

Re-measure `GOCACHE` and `GOMODCACHE` and report the space reclaimed, plus what was kept (the module cache, if the user kept it).
