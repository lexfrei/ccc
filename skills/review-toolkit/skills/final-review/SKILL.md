---
name: final-review
description: PR-focused final review before merge. Strict PR diff scope via gh, business context analysis, dual-model review (Claude + Codex in parallel), mandatory evidence-based verification of every finding. Outputs MERGE or DO NOT MERGE verdict.
argument-hint: "[PR number] [--ticket URL|ID]"
context: fork
agent: general-purpose
---

**CRITICAL**: This is a PR review, not a branch review. ALL code changes come from `gh pr diff`. Do NOT use `git diff` against branches.

## Arguments

Parse $ARGUMENTS for:

- PR number (positional, optional). If omitted, detect from current branch: `gh pr view --json number --jq .number 2>/dev/null`
- `--ticket` external ticket reference (URL or ID) for cross-referencing requirements beyond the PR description

If no PR number provided and no PR exists for current branch, report error and stop.

## Step 1: Gather PR Context

Fetch all PR data upfront. **Print the PR number and title so the user can verify.**

```bash
# PR metadata (title, description, labels, linked issues, existing reviews)
gh pr view $PR_NUMBER --json title,body,labels,baseRefName,headRefName,author,url,comments,reviews,closingIssuesReferences

# PR diff — the ONLY source of code changes for this review
gh pr diff $PR_NUMBER
```

If `--ticket` is provided, fetch ticket content:

- URL (starts with `http`): use `gh issue view` for GitHub URLs, `WebFetch` for external URLs (Jira, Linear, Notion)
- GitHub shorthand (`#123`): `gh issue view 123`
- Other ID: ask user for the full URL

## Step 2: Understand Business Context

Before looking at ANY code, understand WHY this change exists:

1. Read PR title and full description
2. Read linked issues and their acceptance criteria
3. Read existing review comments (what other reviewers already flagged)
4. If `--ticket` provided, read ticket requirements

Formulate a one-sentence summary of the business problem this PR solves. This frames the entire review — every finding must be evaluated against this context.

## Step 3: Independent Reviews (Codex then Claude)

Run Codex first (blocking), then Claude's own analysis. Each model analyzes the diff independently. Verification happens AFTER both complete (Step 4).

### Launch Codex review (blocking)

Check that `codex` CLI is available:

```bash
command -v codex && codex --version
```

If available, run `codex review` against the PR's base branch **synchronously** (NOT in background). Use a 10-minute timeout. The `--base` flag and `[PROMPT]` argument are **mutually exclusive** — do NOT pass both:

```bash
codex review --base $BASE_BRANCH --config 'sandbox_mode="danger-full-access"'
```

Where `$BASE_BRANCH` is the PR's base ref obtained from `gh pr view` in Step 1 (e.g., `main`). The sandbox is fully disabled so Codex can run build tools, tests, and access the network without restrictions.

**CRITICAL**: Do NOT use `run_in_background`. The Bash call MUST block until Codex completes. Save the full Codex output before proceeding.

If `codex` is not installed: warn the user ("codex CLI not found — running Claude-only review. Install it to enable dual-model review.") and continue with Claude analysis alone.

If the `codex review` command fails: warn and continue with Claude-only review.

### Claude's own analysis

After Codex completes (or if Codex is unavailable), perform Claude's independent analysis of the diff. At this stage, produce a RAW list of potential findings — do NOT verify them yet. Just identify concerns.

### Diff scope

Get the full diff from `gh pr diff`. Build an exclude list based on detected project type:

- Lock files (go.sum, package-lock.json, yarn.lock, Cargo.lock, poetry.lock)
- Vendored dependencies (vendor/, node_modules/, third_party/)
- Generated code (*.generated.*, *_generated.*, zz_generated.*, *.pb.go)

For each changed file, when the diff alone is insufficient to understand correctness:

- Read the full file for surrounding context
- Read tests, configs, or related files referenced by the change
- Use web search to understand unfamiliar libraries, APIs, or patterns

### Review criteria

Examine the code thoroughly for:

- **Race conditions**: concurrent access to shared state, missing synchronization, goroutine leaks
- **Edge cases**: nil/null handling, empty collections, boundary values, integer overflow, unicode
- **Error handling**: swallowed errors, missing cleanup in error paths, panic/throw in library code, error wrapping losing context
- **Resource leaks**: unclosed files/connections/channels, missing defer/finally, context cancellation not propagated
- **Naming and abstractions**: misleading names, wrong abstraction level, leaky abstractions, god functions
- **API contracts**: breaking changes to public interfaces, missing input validation, undocumented behavior changes
- **Security**: injection (SQL, command, template), auth bypass, secrets in code, unsafe deserialization, path traversal
- **Data integrity**: missing transactions, partial writes, inconsistent state on failure, TOCTOU races
- **Documentation**: if the PR changes behavior, existing documentation (README, CLAUDE.md, API docs, comments, Helm values descriptions) MUST be updated. Stale docs are a blocker.

## Step 4: Verify All Findings (after BOTH reviews complete)

**CRITICAL**: Do NOT proceed to this step until BOTH Claude's raw analysis AND Codex results are available. Since Codex runs synchronously, both should be available at this point.

Merge the raw finding lists from both models, then verify EVERY finding. An unverified claim is worse than no claim.

For each potential finding:

1. **Locate the evidence**: Read the actual source code, not just the diff. Show the specific lines that demonstrate the problem.
2. **Trace the execution path**: Follow the code flow to prove the problem actually manifests. If a "missing error check" is actually handled upstream, it's not a finding.
3. **Check for mitigations**: Search the codebase for existing guards, fallbacks, or design decisions that intentionally address the concern. Read related files, configs, dependencies.
4. **Prove, don't speculate**: Each finding must include concrete evidence — file paths, line numbers, code snippets, or external documentation references that prove the issue is real.
5. **Disprove if wrong**: If investigation shows a finding is invalid (e.g., Codex flagged something that is actually safe), explicitly note it was investigated and dismissed, with the reason.

**Evidence format** for each finding:

```
**Evidence**: [What was checked, what was found, why this proves the issue]
```

Example of a GOOD finding:
> cert-manager values.yaml:3 sets `enableGatewayAPI: true` unconditionally. Checked cert-manager source (link to docs/code): gateway-shim controller discovers CRDs only at startup. Checked PackageSource dependencies: `cozystack.cert-manager` has no `dependsOn` for `cozystack.gateway-api-crds`. Therefore on fresh install, cert-manager starts before CRDs exist → gateway support silently non-functional.

Example of a BAD finding (would be rejected):
> "enableGatewayAPI is set but Gateway API CRDs might not be installed yet" — no evidence of startup behavior, no dependency check, pure speculation.

### Merge findings from both models

After verification:

- **Both models found the same issue AND evidence confirms it**: high confidence — mark with `[Claude + Codex]`
- **Only Codex found it AND Claude verified it**: include with `[Codex]` tag
- **Only Codex found it BUT Claude could not verify**: EXCLUDE from report, note in Summary that it was investigated and dismissed
- **Only Claude found it AND evidence supports it**: include normally (no tag needed)
- **Models contradict each other**: investigate deeper, present the evidence-backed conclusion

## Step 5: Classify Findings

Every finding goes into exactly one of two categories. If it does not fit either — do not mention it.

### Blockers

The PR MUST NOT merge with any of these present:

- Bugs that will manifest in production
- Security vulnerabilities
- Data loss or corruption risks
- Broken API contracts (existing consumers will break)
- Missing error handling that causes silent failures or data loss
- Resource leaks under normal (not just edge-case) operation
- Behavior changes with stale documentation

### Action Items

Real problems worth tracking, but they do not block this merge:

- Tech debt introduced (acceptable now, needs a follow-up ticket)
- Missing test coverage for non-critical paths
- Naming or abstraction improvements
- Performance concerns that are not urgent
- Documentation gaps for internal-only features
- Non-critical refactoring opportunities
- Pre-existing issues in adjacent code (unlike /review-branch, this review does NOT adopt ownership of pre-existing problems outside the diff — but it DOES flag them as action items if they affect the changed code)

## Output Format

No praise. No "great work." No "overall the code looks good." No filler. Findings only.

Start with:

```
## Verdict: MERGE

or

## Verdict: DO NOT MERGE
```

Then:

```
**Business context**: [one sentence — what problem this PR solves]
**PR**: [URL]
**Files changed**: [count] | **Additions**: +N | **Deletions**: -N
```

### Blockers section

If none: `## Blockers\n\nNone.`

For each blocker:

```
## Blockers

### B1: [concise title]
**File**: path/to/file.ext:LINE
**Issue**: [clear description of the bug/vulnerability/problem]
**Impact**: [what happens if this ships as-is]
**Fix**: [specific, actionable suggestion]
```

### Action Items section

If none: `## Action Items\n\nNone.`

For each action item:

```
## Action Items

### A1: [concise title]
**File**: path/to/file.ext:LINE
**Issue**: [description of the problem]
**Ticket suggestion**: [one-line title for a follow-up ticket]
```

### Summary

```
## Summary
[2-3 sentences: scope of what was reviewed, verdict reasoning]
[If dual-model review: note which findings were confirmed by both models, which were model-specific]
[If Codex was unavailable: note "Claude-only review — codex CLI not available"]
```

<if --ticket>
Add after Summary:

```
## Ticket Compliance
**Ticket**: [title + link/ID]

- [ ] Requirement 1 — done / not done / partially done
- [ ] Requirement 2 — done / not done / partially done
- ...

**Verdict**: All requirements met / Missing: [list]
```

Missing ticket requirements are blockers (DO NOT MERGE).
</if>
