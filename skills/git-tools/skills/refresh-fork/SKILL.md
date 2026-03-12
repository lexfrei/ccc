---
name: refresh-fork
description: Refresh fork to match upstream, preparing for new contributions.
disable-model-invocation: true
context: fork
agent: general-purpose
---

Refresh fork to match upstream, preparing for new contributions.

## Process

1. **Check upstream exists**

   ```bash
   git remote get-url upstream
   ```

   If fails: stop with error "No upstream remote configured. This doesn't look like a fork."

2. **Determine default branch**

   ```bash
   git remote show upstream | grep 'HEAD branch' | awk '{print $NF}'
   ```

   Fallback: try `main`, then `master`

3. **Discard local state**

   ```bash
   git checkout <default-branch>
   git reset --hard
   git clean --force -d
   ```

4. **Sync with upstream**

   ```bash
   git fetch upstream
   git reset --hard upstream/<default-branch>
   ```

5. **Push to origin**

   ```bash
   git push origin <default-branch> --force
   ```

6. **Confirm**

   Report: synced to which commit (short sha + message), now on `<default-branch>`
