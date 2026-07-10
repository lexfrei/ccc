---
name: docker-prune
description: Reclaim Docker disk by pruning unused images, containers, networks, build cache, optionally volumes, and the build cache of non-default buildx builders; on VM-backed daemons (Colima/Lima) also offers a guest fstrim so the host-side sparse disk image actually shrinks. Shows reclaimable size first, then prunes the user-chosen scope after approval. TRIGGER when the user wants to free Docker space ("docker prune", "почисти docker", "reclaim image cache"). DO NOT trigger for removing specific named containers/images.
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

Also note whether the daemon is **VM-backed** (Colima/Lima, or any setup where the daemon runs inside a VM whose disk is a file on the host — `colima status` succeeding is the common signal). This enables the trim scope (Steps 2–4).

## Step 2: Report reclaimable size

```bash
docker system df
docker buildx ls
```

Show the `docker system df` breakdown (images, containers, local volumes, build cache) with the reclaimable column.

**On a VM-backed daemon, also account for the host-side disk image.** Everything `docker system df` shows lives inside a VM disk that is a **sparse file** on the host (Colima: `~/.colima/_lima/_disks/<profile>/datadisk`). Blocks freed by pruning *inside* the guest are NOT returned to the host until the guest filesystem issues discards — so the host file's allocated size keeps the high-water mark of every past build. Measure both sides: apparent size (`ls -lh <disk>`) vs actually allocated (`du -sh <disk>`), and compare the allocated size with what the guest really uses (`colima ssh -- df -h /var/lib/docker`). A large gap means the trim scope alone can return that space to the host, even with nothing left to prune. Record the allocated size as the baseline for Step 5.

**Critically, account for non-default buildx builders.** `docker system prune` only prunes the build cache of the *default* builder. A `docker-container`-driver builder (common with multi-arch / Colima setups) keeps its cache inside an **in-use** state volume named after the builder's **node** — `buildx_buildkit_<node>_state` (e.g. builder `multi` with node `multi0` → `buildx_buildkit_multi0_state`; a multi-node builder has one such volume per node). That volume shows as active in `docker system df`, so **neither `docker system prune` nor `docker volume prune` reclaims it** — only `docker buildx prune` does. This is frequently the single largest reclaimable item. For each non-default builder from `docker buildx ls`, note its cache (the size of its `buildx_buildkit_*_state` volume(s) in `docker system df -v` is a good proxy).

## Step 3: Ask what to prune (interactive)

Spell out each scope's exact effect, then **ask the user** (interactive, multi-select) which to run:

- **Images, containers, networks, build cache** — `docker system prune -a`: all stopped containers, unused networks, the default builder's build cache, and all unused images (`-a` widens images from dangling-only to all unused). Volumes are NOT touched.
- **Unused volumes** — `docker volume prune --all`: removes unused volumes. On Docker ≥ 23, `docker system prune --volumes` would only catch *anonymous* volumes, so `docker volume prune --all` is used to also remove unused *named* volumes. **Volumes may hold data** (databases, caches) — list the dangling volumes and their sizes so the user sees exactly what goes, and confirm.
- **Non-default buildx builder cache** — `docker buildx prune -a` per non-default builder: reclaims the in-use builder-state cache that the two prunes above cannot. Often the biggest win.
- **Trim the VM disk** (VM-backed daemons only) — `fstrim` inside the guest: non-destructive, touches no Docker data; the guest filesystem sends discards for its free blocks and the hypervisor punches holes in the host-side sparse file. Without it, none of the prunes above free a single host byte. Also reclaims space left over from prunes and image deletions done long before this run.

## Step 4: Execute (after approval)

Run only the selected scopes:

```bash
# images / containers / networks / default build cache
docker system prune -a -f

# unused volumes (named + anonymous)
docker volume prune --all --force

# each selected non-default builder
docker buildx prune --all --force --builder <name>

# trim the VM disk — run LAST, so blocks freed by the prunes above are included
colima ssh -- sudo fstrim -a -v
```

For non-Colima VMs, run `sudo fstrim -a -v` inside the guest by whatever access the setup provides (`limactl shell <name>`, SSH). If `fstrim` reports the discard operation is not supported, the VM's disk is attached without discard support — report that and move on; nothing is lost.

## Step 5: Report

Run `docker system df` again and report space reclaimed per scope (use each command's "Total reclaimed space" line — it is dedup-aware, unlike the nominal `df` reclaimable column) and the combined total. If the trim scope ran, measure its effect on the **host** side — `du -sh` on the disk image before vs after (the guest's `df` does not change) — and report that delta separately; it is the number the user actually gets back. State what was deliberately preserved (active images/containers, in-use volumes, and — if not selected — volumes, non-default builder caches, or the untrimmed VM disk).
