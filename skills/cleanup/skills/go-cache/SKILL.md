---
name: go-cache
description: Reclaim Go disk by clearing the build, test, fuzz, and module caches. Measures each cache first, then cleans after approval. TRIGGER when the user wants to free Go cache space ("clean go cache", "почисти go кеши", "reclaim GOMODCACHE"). DO NOT trigger for cleaning a specific module or running go mod tidy.
disable-model-invocation: true
argument-hint: "[--keep-modcache]"
---

Reclaim Go cache disk space, then report what was freed.

Operates in **report → confirm → execute** order. After approval, run the cleanup autonomously.

## Step 1: Locate and measure the caches

```bash
go env GOCACHE GOMODCACHE
```

- `GOCACHE` holds the build, test, and fuzz caches — fully regenerated on the next build.
- `GOMODCACHE` holds downloaded module sources — re-downloaded on the next `go build`/`go mod download`. It is usually the largest, often tens of GB.

Measure both: `du -sh "$GOCACHE"` and `du -sh "$GOMODCACHE"`. If `go` is not installed, stop and say so.

## Step 2: Report

Show the size of each cache and the total reclaimable. State the scope:

- **default**: clears build + test + fuzz **and** the module cache.
- **with `--keep-modcache`**: clears build + test + fuzz only, leaving downloaded modules in place (avoids a large re-download on the next build).

## Step 3: Confirm

Ask for approval. Note that the next build will be slower while caches repopulate (and, unless `--keep-modcache`, will re-download dependencies).

## Step 4: Execute (after approval)

Build, test, and fuzz caches:

```bash
go clean -cache -testcache -fuzzcache
```

Module cache (unless `--keep-modcache`):

```bash
go clean -modcache
```

`go clean -modcache` handles the read-only permission bits that Go sets on cached module files — no manual `chmod` needed.

## Step 5: Report

Re-measure `GOCACHE` and `GOMODCACHE` and report the space reclaimed, plus what was kept (`--keep-modcache`, if used).
