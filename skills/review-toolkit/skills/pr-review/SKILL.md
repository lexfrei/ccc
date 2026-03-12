---
name: pr-review
description: Post a GitHub PR review with inline comments. Runs dual analysis (/branch-review + /final-review in parallel), cross-validates every finding against actual code/docs/running systems, presents draft to user for approval, then publishes via GitHub API. Designed to catch AI hallucinations — every claim must have evidence.
argument-hint: "[PR number] [--approve] [--target branch]"
---

**CRITICAL**: This skill produces a PUBLISHED GitHub review visible to the PR author and all watchers. Every word matters. Every claim must be proven. User MUST approve the text before publishing.

## Arguments

Parse $ARGUMENTS for:

- PR number (positional, optional). If omitted, detect from current branch: `gh pr view --json number --jq .number 2>/dev/null`
- `--approve` — submit as APPROVE instead of REQUEST_CHANGES (only if no blockers found)
- `--target` — target branch override (passed through to sub-reviews)

If no PR number and no PR exists for current branch, report error and stop.

## Step 1: Sync to Remote

Before any analysis, ensure local branch matches the remote PR head:

```bash
# Get PR head ref
PR_BRANCH=$(gh pr view $PR_NUMBER --json headRefName --jq .headRefName)

# Fetch and reset to remote
git fetch origin $PR_BRANCH
git reset --hard origin/$PR_BRANCH
```

Print the current commit hash and message so the user can confirm this is the right state.

## Step 2: Parallel Analysis

Launch BOTH skills simultaneously using the Agent tool:

1. `/branch-review --target <target>` — branch-level analysis with full codebase context
2. `/final-review $PR_NUMBER` — PR-focused review with business context and dual-model (Claude + Codex)

Wait for both to complete. Collect all findings from both.

## Step 3: Deduplicate and Merge Findings

Build a unified list of all unique findings from both analyses. For each finding, record:

- **Source**: which analysis found it (review-branch, final-review/Claude, final-review/Codex, or multiple)
- **Claim**: what the finding asserts
- **Severity**: blocker vs observation vs suggestion
- **File and line**: exact location in the diff

Deduplicate findings that describe the same issue from different angles — keep the most precise description.

## Step 4: Verify Every Finding (MANDATORY)

**CRITICAL**: AI models hallucinate. Blind trust in AI findings destroys reviewer credibility. Every claim must be proven with evidence before inclusion.

For EACH finding, perform mandatory verification:

### 4a. Code verification

- Read the actual source files (not just the diff) to confirm the claimed behavior
- Trace execution paths to prove the problem manifests
- Check for existing mitigations, guards, or design decisions that address the concern
- Check upstream documentation for libraries/tools mentioned in the finding

### 4b. Cross-reference verification

- If a finding claims "X doesn't work with Y" — search for evidence: upstream docs, compatibility matrices, changelogs, GitHub issues
- If a finding claims "this will crash/fail" — find the specific code path or documented behavior that proves it
- If a finding is about configuration — search upstream docs and examples for the correct usage pattern. Do NOT attempt to connect to live clusters or infrastructure to verify

### 4c. Verdict per finding

After verification, each finding gets one of:

- **CONFIRMED**: Evidence supports the claim. Include the evidence summary.
- **DISPROVEN**: Evidence contradicts the claim. Drop the finding entirely. Note in internal log why it was dropped.
- **UNVERIFIABLE**: Cannot confirm or deny with available information. Downgrade to observation/question, not a blocker.

**Only CONFIRMED findings proceed to the review.**

## Step 5: Classify Confirmed Findings

Each confirmed finding becomes one of:

### Blocker (REQUEST_CHANGES)

Will cause real problems if merged:

- Runtime failures (crashes, CrashLoopBackOff, silent misconfiguration)
- Security vulnerabilities
- Data loss or corruption
- Breaking changes to existing functionality
- Broken variants/environments (e.g., works in variant A but breaks variant B)

### Observation (non-blocking)

Real issues worth noting but not blocking:

- Dead code / unused values
- Code duplication that could be DRY-ed
- Missing future-proofing
- Design decisions worth documenting
- Potential issues in edge cases that don't affect current usage

### Suggestion (non-blocking)

Improvements the author could consider:

- Alternative approaches
- Helper extraction opportunities
- Naming improvements

## Step 6: Draft the Review

Compose the review for user approval. The review consists of:

### Review body (top-level comment)

Short summary: what the PR does well, what needs attention. No fluff. 2-3 sentences max.

If there are blockers: state how many and that they need fixing.
If no blockers: acknowledge the good work briefly.

### Inline comments

Each finding becomes an inline comment on the specific file and line. Format:

**For blockers:**

```text
[description of the problem]

[evidence: why this is a real issue — specific code paths, docs, or system behavior that proves it]

[suggested fix or approach]
```

**For observations:**

```text
Observation (non-blocking): [description]
```

**For suggestions:**

```text
Suggestion (non-blocking): [description]
```

### Review event type

- If ANY blockers exist: `REQUEST_CHANGES`
- If `--approve` flag AND no blockers: `APPROVE`
- Otherwise (no blockers, no --approve): `COMMENT`

## Step 7: User Approval (MANDATORY)

**CRITICAL**: NEVER publish without user approval. This is a public action visible to the PR author.

Present the complete review to the user:

1. Review event type (REQUEST_CHANGES / APPROVE / COMMENT)
2. Review body text
3. Each inline comment with file path and line number
4. List of findings that were DISPROVEN and dropped (so user can verify the dismissal)

Ask: "Publish this review?" and wait for explicit confirmation.

If the user requests changes to the review text — apply them and re-present.

## Step 8: Publish

Use the GitHub API to submit the review. Use `python3` with `json` module to properly serialize the payload (shell escaping of complex review bodies is unreliable):

```python
import json, subprocess

review = {
    "commit_id": "<latest PR head SHA>",
    "event": "REQUEST_CHANGES",  # or APPROVE or COMMENT
    "body": "<review body>",
    "comments": [
        {
            "path": "path/to/file.ext",
            "line": 42,
            "body": "<comment text>"
        }
    ]
}

subprocess.run(
    ["gh", "api", f"repos/{owner}/{repo}/pulls/{pr_number}/reviews",
     "--method", "POST", "--input", "-"],
    input=json.dumps(review), text=True
)
```

After publishing, print the review URL so the user can verify it rendered correctly.

## Important Rules

- **Language**: ALL review content MUST be in English.
- **No AI attribution**: Do not mention Claude, Codex, AI, or automated review in the published review. The review is from the user's GitHub account.
- **No speculation**: If you cannot prove a finding, do not include it. "Might cause issues" is not acceptable — either prove it or drop it.
- **Respect existing reviews**: Read existing review comments on the PR. Do not repeat points already made by other reviewers unless adding new evidence.
- **One review, not a wall of text**: Keep inline comments focused and concise. The PR author should be able to act on each comment independently.
- **No private infrastructure details**: Never mention cluster names, client names, internal IPs, or environment identifiers in public reviews.
