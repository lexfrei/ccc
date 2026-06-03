---
name: docker-prune
description: Reclaim Docker disk by pruning unused images, containers, networks, build cache, optionally volumes, and the build cache of non-default buildx builders. Shows reclaimable size first, then prunes the user-chosen scope after approval. TRIGGER when the user wants to free Docker space ("docker prune", "почисти docker", "reclaim image cache"). DO NOT trigger for removing specific named containers/images.
disable-model-invocation: true
---

Reclaim Docker disk space, then report what was freed.

Operates in **report → confirm → execute** order. The scope is chosen through an interactive question, not flags. After approval, run the prune autonomously.

## Step 1: Check the daemon

```bash
docker info >/dev/null 2>&1
```

If it fails, the Docker daemon is not reachable. On a Colima/Lima or other VM-backed setup, tell the user how to start it (e.g. `colima start`) and stop — do not guess.

With the daemon up, record the engine version: `docker version --format '{{.Server.Version}}'`. It determines volume-prune behavior (see Step 3).

## Step 2: Report reclaimable size

```bash
docker system df
docker buildx ls
```

Show the `docker system df` breakdown (images, containers, local volumes, build cache) with the reclaimable column.

**Critically, account for non-default buildx builders.** `docker system prune` only prunes the build cache of the *default* builder. A `docker-container`-driver builder (common with multi-arch / Colima setups) keeps its cache inside an **in-use** state volume named after the builder's **node** — `buildx_buildkit_<node>_state` (e.g. builder `multi` with node `multi0` → `buildx_buildkit_multi0_state`; a multi-node builder has one such volume per node). That volume shows as active in `docker system df`, so **neither `docker system prune` nor `docker volume prune` reclaims it** — only `docker buildx prune` does. This is frequently the single largest reclaimable item. For each non-default builder from `docker buildx ls`, note its cache (the size of its `buildx_buildkit_*_state` volume(s) in `docker system df -v` is a good proxy).

## Step 3: Ask what to prune (interactive)

Spell out each scope's exact effect, then **ask the user** (interactive, multi-select) which to run:

- **Images, containers, networks, build cache** — `docker system prune -a`: all stopped containers, unused networks, the default builder's build cache, and all unused images (`-a` widens images from dangling-only to all unused). Volumes are NOT touched.
- **Unused volumes** — `docker volume prune --all`: removes unused volumes. On Docker ≥ 23, `docker system prune --volumes` would only catch *anonymous* volumes, so `docker volume prune --all` is used to also remove unused *named* volumes. **Volumes may hold data** (databases, caches) — list the dangling volumes and their sizes so the user sees exactly what goes, and confirm.
- **Non-default buildx builder cache** — `docker buildx prune -a` per non-default builder: reclaims the in-use builder-state cache that the two prunes above cannot. Often the biggest win.

## Step 4: Execute (after approval)

Run only the selected scopes:

```bash
# images / containers / networks / default build cache
docker system prune -a -f

# unused volumes (named + anonymous)
docker volume prune --all --force

# each selected non-default builder
docker buildx prune --all --force --builder <name>
```

## Step 5: Report

Run `docker system df` again and report space reclaimed per scope (use each command's "Total reclaimed space" line — it is dedup-aware, unlike the nominal `df` reclaimable column) and the combined total. State what was deliberately preserved (active images/containers, in-use volumes, and — if not selected — volumes or non-default builder caches).
