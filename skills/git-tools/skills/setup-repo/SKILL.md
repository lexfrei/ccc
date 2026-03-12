---
name: setup-repo
description: Configure GitHub repo settings and branch protection with auto-detected required CI checks from workflow files
disable-model-invocation: true
argument-hint: "[branch-name] [--checks name1,name2]"
---

## Arguments

Parse $ARGUMENTS for:

- Positional argument: default branch name override (e.g. `main`, `master`)
- `--checks <name1,name2,...>`: explicitly specify required status checks (skip auto-detection)

Examples:

- `/setup-repo` → auto-detect everything
- `/setup-repo main` → protect the `main` branch
- `/setup-repo --checks "Lint,Test,Notify PR"` → explicit checks, skip auto-detection

## Step 1: Identify repo and default branch

Run:

```bash
gh repo view --json nameWithOwner,defaultBranchRef --jq '{repo: .nameWithOwner, branch: .defaultBranchRef.name}'
```

- Extract `REPO` (e.g. `lexfrei/kuberture`) and `BRANCH` (e.g. `master`)
- If a positional argument was provided, use it as `BRANCH` instead

Report to the user: "Configuring {REPO}, protecting branch {BRANCH}"

## Step 2: Configure repo merge settings

Run:

```bash
gh api --method PATCH repos/{REPO} \
  --field allow_squash_merge=true \
  --field allow_merge_commit=false \
  --field allow_rebase_merge=false \
  --field delete_branch_on_merge=true
```

Report: "Repo settings: squash-only merges, auto-delete branches"

## Step 3: Detect required status checks

**If `--checks` was provided**: parse the comma-separated list and skip to Step 4.

**Otherwise, auto-detect from workflow files**:

1. Find all workflow files: `.github/workflows/*.yml` and `.github/workflows/*.yaml`

2. For each workflow file, read it and check if it has a `pull_request` trigger in the `on:` section. Skip workflows that only trigger on `push`, `release`, `schedule`, etc.

3. For each PR-triggered workflow, analyze the `jobs:` section:
   - Build a map of `job_key → { name: <display name>, needs: [<dependencies>] }`
   - If a job has no `name:` field, use the job key as the display name
   - Collect all job keys that appear in ANY other job's `needs:` list — these are "depended-upon" jobs
   - "Terminal jobs" are jobs whose key does NOT appear in any other job's `needs:` list
   - The required check names are the `name:` fields of the terminal jobs

4. Present the detected checks to the user using AskUserQuestion:
   - Show the list of detected terminal jobs and their display names
   - Ask: "These terminal CI jobs were detected. Use them as required status checks?"
   - Options: "Yes, apply these" / "Let me customize"
   - If the user wants to customize, ask them to provide the check names

## Step 4: Set branch protection

Run:

```bash
gh api --method PUT repos/{REPO}/branches/{BRANCH}/protection \
  --input - <<'PAYLOAD'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [<CHECKS_JSON_ARRAY>]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null
}
PAYLOAD
```

Where `<CHECKS_JSON_ARRAY>` is the JSON array of check name strings, e.g. `["Notify PR", "E2E Tests"]`.

## Step 5: Summary

Print a summary:

```
Repository: {REPO}
Protected branch: {BRANCH}

Merge settings:
  - Squash merge: enabled
  - Merge commit: disabled
  - Rebase merge: disabled
  - Auto-delete branches: enabled

Branch protection:
  - Required checks: {comma-separated list}
  - Strict status checks: enabled (branch must be up-to-date)
  - Enforce for admins: enabled
```
