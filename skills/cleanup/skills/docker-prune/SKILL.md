---
name: docker-prune
description: Reclaim Docker disk by pruning unused images, containers, networks, and build cache. Shows reclaimable size first, then prunes after approval. Volumes are opt-in via --volumes (they may hold data). TRIGGER when the user wants to free Docker space ("docker prune", "почисти docker", "reclaim image cache"). DO NOT trigger for removing specific named containers/images.
disable-model-invocation: true
argument-hint: "[--volumes]"
---

Reclaim Docker disk space, then report what was freed.

Operates in **report → confirm → execute** order. After approval, run the prune autonomously.

## Step 1: Check the daemon

```bash
docker info >/dev/null 2>&1
```

If it fails, the Docker daemon is not reachable. On a Colima/Lima or other VM-backed setup, tell the user how to start it (e.g. `colima start`) and stop — do not guess.

With the daemon up, record the engine version: `docker version --format '{{.Server.Version}}'`. It determines `--volumes` behavior (see Step 2) — Docker ≥ 23 limits it to anonymous volumes, older engines do not.

## Step 2: Report reclaimable size

```bash
docker system df
```

Show the breakdown (images, containers, local volumes, build cache) and the reclaimable column. Make clear what the chosen scope will and will not touch:

- **default** (`docker system prune -a`): all stopped containers, all networks not used by a container, the entire build cache, and unused images. The `-a` flag is what widens image removal from dangling-only to **all** unused images; stopped containers, unused networks, and build cache are pruned with or without `-a`. **Volumes are NOT touched.**
- **with `--volumes`** (opt-in): behavior depends on the engine version. On Docker **≥ 23** it additionally removes **anonymous** volumes only — named volumes are left in place (removing unused named volumes needs a separate `docker volume prune --all`). On **older** engines, `docker system prune --volumes` removes *any* unused volume, **including named volumes that hold data**. Either way anonymous-volume data is lost, so warn explicitly and require a clear confirmation.

## Step 3: Confirm

Ask for approval. If `--volumes` was passed, restate what will be deleted based on the recorded engine version: on Docker ≥ 23 only **anonymous** volumes (named untouched); on older engines, **any** unused volume including named ones. Confirm that specifically.

## Step 4: Execute (after approval)

Default:

```bash
docker system prune -a -f
```

With the opt-in flag:

```bash
docker system prune -a --volumes -f
```

## Step 5: Report

Run `docker system df` again and report the space reclaimed (before vs after), plus what was deliberately preserved (named volumes on Docker ≥ 23; anonymous volumes unless `--volumes` was used).
