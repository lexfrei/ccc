---
name: pr-review
description: Post a GitHub PR review with inline comments. Runs the five-frame substance pass (problem real / approach optimal / tradeoffs / docs sync / code quality), cascades /branch-review, performs sequential Claude+Codex dual-model analysis on the PR diff, cross-validates every finding with explicit evidence, presents draft for approval, then publishes via GitHub API. Reviews open with an LGTM or NOT LGTM verdict (matching the /branch-review convention) — never observation-only.
  TRIGGER: invoke proactively whenever the user asks to review, audit, or quality-check a GitHub Pull Request — whether by URL (github.com/.../pull/N), shorthand (owner/repo#N), bare number (#1234), or a "this PR" / "этот PR" reference resolvable from conversation context. Examples: "review PR 2541", "сделай ревью на https://github.com/foo/bar/pull/123", "оцени этот PR", "что думаешь про #9", "проверь PR от X". DO NOT trigger for: replying to existing review comments (use /address-pr-comments), labeling or triaging issues (use /categorize), generating a TLDR (use /tldrpr), or general code questions about a branch with no associated PR. PR vs issue is detected automatically — for issues without code-review intent, do not invoke.
argument-hint: "[PR number] [--approve] [--target branch] [--ticket URL|ID]"
---

**CRITICAL**: This skill produces a PUBLISHED GitHub review visible to the PR author and all watchers. Every word matters. Every claim must be proven. User MUST approve the text before publishing.

## Arguments

Parse $ARGUMENTS for:

- PR number (positional, optional). If omitted, detect from current branch: `gh pr view --json number --jq .number 2>/dev/null`
- `--approve` — submit as LGTM (APPROVE event) explicitly even when no blockers found (default behavior is LGTM without blockers, so this flag is informational)
- `--target` — target branch override (passed through to `/branch-review`)
- `--ticket` — external ticket reference (URL or ID) for cross-referencing requirements beyond the PR description; activates the Ticket Compliance section in the output

If no PR number and no PR exists for current branch, report error and stop.

## Step 1: Sync to Remote and Verify PR Scope

Before any analysis, fetch ALL remote refs and verify the PR scope via GitHub API.

**CRITICAL**: Local branches go stale. NEVER use bare `main`/`master`/base-branch in `git diff` — ALWAYS use `origin/<branch>`. A stale local branch produces phantom diffs that include already-merged commits, leading to false findings (e.g., claiming a PR needs rebasing when it doesn't).

```bash
# Fetch everything so origin/* refs are current
git fetch origin

# Get PR metadata from the API — this is the ONLY authoritative source for PR scope
PR_BRANCH=$(gh pr view $PR_NUMBER --json headRefName --jq .headRefName)
PR_BASE=$(gh pr view $PR_NUMBER --json baseRefName --jq .baseRefName)

# Checkout and reset to remote head
git checkout $PR_BRANCH
git reset --hard origin/$PR_BRANCH

# Verify PR scope via API — do NOT trust local git diff for file count
gh api "repos/{owner}/{repo}/pulls/$PR_NUMBER" --jq '{commits: .commits, changed_files: .changed_files}'
gh api "repos/{owner}/{repo}/pulls/$PR_NUMBER/files" --jq '.[].filename'
gh api "repos/{owner}/{repo}/pulls/$PR_NUMBER/commits" --jq '.[] | "\(.sha[:8]) \(.commit.message | split("\n")[0])"'
```

Print the current commit hash, commit count, file count, and file list so the user can confirm this is the right state. If the local `git diff origin/$PR_BASE...$PR_BRANCH --stat` shows different files than the API, **trust the API** and investigate the local discrepancy before proceeding.

## Step 1.5: Check Bot Comments

Read all comments and inline review comments from bots (CodeRabbit, Gemini Code Assist, etc.):

```bash
gh pr view $PR_NUMBER --json comments --jq '.comments[] | select(.author.is_bot == true or (.author.login | test("bot|coderabbit|gemini"; "i"))) | {author: .author.login, body: .body}'
gh api "repos/{owner}/{repo}/pulls/$PR_NUMBER/comments" --jq '.[] | select(.user.login | test("bot|coderabbit|gemini"; "i")) | {author: .user.login, path: .path, line: (.original_line // .line), body: .body}'
```

Note which bot findings are valid and which are noise. Check if the author has responded to bot comments. If valid bot findings remain unaddressed, either incorporate them into the review (with new evidence — never repeat verbatim) or surface a general note asking the author to address them.

## Step 2: Business Context

Before any code reading, frame WHY this PR exists. Read in this order:

1. PR title and full body
2. Linked issues (`closingIssuesReferences` in `gh pr view`) and their acceptance criteria
3. Existing reviews and their findings (do not repeat already-raised points)
4. If `--ticket` provided, fetch ticket content:
   - URL starting with `http`: `gh issue view <number> --repo <owner/repo>` for GitHub URLs, `WebFetch` for external URLs (Jira, Linear, Notion)
   - GitHub shorthand (`#123`): `gh issue view 123` in the current repo
   - Other ID: ask the user for the full URL

Formulate a one-sentence summary of the business problem this PR solves. Every later finding must be evaluated against this context. The summary will appear in the published review under `**Business context**:`.

If `--ticket` was provided, also extract:

- Title and description
- Acceptance criteria (specific requirements, if listed)
- Scope (what is in scope, what is explicitly out of scope)

## Step 3: Five-Frame Substance Pass

Sequentially answer the five questions, taking notes. The output of this step is a list of preliminary concerns to verify in Step 5. Substance findings are NOT to be confused with code-quality findings — Frame 5 delegates the latter to Step 4.

**Frame 1 — Is the stated problem real and well-scoped?** Verify the symptom against current code/docs/running behavior, not just the PR description. If the description says "X causes Y" trace it: does X actually cause Y in the current codebase? If you cannot reproduce the claim from reading the code, that is a finding.

**Frame 2 — Is the chosen approach optimal among realistic alternatives?** Actively enumerate at least 2-3 other approaches that could solve the same problem (different abstraction layer, different tool, stateless vs stateful, different default, different repo location). Explain why each was rejected or accepted in this context. If you cannot list alternatives, the substance work is not done.

**Frame 3 — Are the design tradeoffs acknowledged?** Storage cost, performance, security, operational burden, lock-in, default-vs-recommended mismatch, migration cost. The PR (description, README, comments) should name the tradeoffs it accepts. If it doesn't, raise them.

**Frame 4 — Is the documentation in sync?** Look for a sibling docs PR (typical pattern: code in this repo + docs in a `*-website` repo, linked from the PR body or with a matching slug). Verify it exists, is OPEN, and matches what the code ships now (flag names, defaults, prerequisites, examples). Also check in-repo docs (`README.md`, `docs/`, package READMEs).

When the docs search returns empty, that is ambiguous — it can mean either (a) the change is plumbing/internal and legitimately needs no docs, or (b) the change is user-facing but the docs gap predates this PR. To resolve, open the relevant existing user-facing doc page and read it as a user would. Ask: does the documented workflow rely on the behavior this PR changes? Does it currently misrepresent reality (if a bug was latent)? Does it omit a now-relevant capability?

For pre-existing cross-repo docs gaps, prepare a tracking-issue draft (title + body) now; it will be filed in Step 9 after user approval, and its URL spliced into the review under non-blocking follow-ups. Do not block the PR on a pre-existing cross-repo gap. For pre-existing in-repo docs that describe the area being changed, the cascaded `/branch-review` (Step 4a) treats them as blockers per its own rules — do not duplicate that logic here.

**Frame 5 — Is the code quality solid?** This frame is satisfied by the dual analysis in Step 4 (cascaded `/branch-review` + Codex + Claude). Note here whether any business-context concerns from Frames 1-3 need explicit cross-validation by the models, and forward those as hints into the dual analysis.

## Step 4: Dual Analysis

Run two analyses in sequence, then merge.

### 4a. Cascade `/branch-review`

Invoke the `/branch-review` skill with `--target $PR_BASE` (and `--ticket <ticket>` if provided). It owns its own rules — LGTM/NOT LGTM verdict, "pre-existing in the neighborhood = own it", comments-as-fixes are blockers, tests-for-every-issue, doc accuracy. Do NOT duplicate those rules here. Capture its verdict and findings.

If `/branch-review` is invoked from a directory whose active branch is not the PR branch, it creates a temporary worktree internally — see its SKILL.md for the worktree workflow.

### 4b. Codex review (synchronous, blocking)

Check that the `codex` CLI is available:

```bash
command -v codex && codex --version
```

If available, run `codex review` against the PR's base branch **synchronously** (NOT in background). Use a 10-minute timeout. The `--base` flag and `[PROMPT]` argument are **mutually exclusive** — pass only `--base`:

```bash
codex review --base $PR_BASE --config 'sandbox_mode="danger-full-access"'
```

The sandbox is fully disabled so Codex can run build tools, tests, and access the network without restrictions.

**CRITICAL**: Do NOT use `run_in_background`. The Bash call MUST block until Codex completes. Save the full Codex output before proceeding.

If `codex` is not installed: warn the user (`codex CLI not found — running Claude-only review. Install it to enable dual-model verification.`) and continue.

If `codex review` fails: warn and continue with Claude-only.

### 4c. Claude's own analysis

After 4a and 4b complete, perform Claude's independent analysis of `gh pr diff $PR_NUMBER`. Build an exclude list based on detected project type:

- Lock files (`go.sum`, `package-lock.json`, `yarn.lock`, `Cargo.lock`, `poetry.lock`)
- Vendored dependencies (`vendor/`, `node_modules/`, `third_party/`)
- Generated code (`*.generated.*`, `*_generated.*`, `zz_generated.*`, `*.pb.go`)

For each changed file, when the diff alone is insufficient: read the full file for surrounding context, read tests/configs/related files, use web search for unfamiliar libraries or APIs.

Examine for:

- **Race conditions**: concurrent access to shared state, missing synchronization, goroutine leaks
- **Edge cases**: nil/null handling, empty collections, boundary values, integer overflow, unicode
- **Error handling**: swallowed errors, missing cleanup in error paths, panic/throw in library code, error wrapping losing context
- **Resource leaks**: unclosed files/connections/channels, missing defer/finally, context cancellation not propagated
- **Naming and abstractions**: misleading names, wrong abstraction level, leaky abstractions, god functions
- **API contracts**: breaking changes to public interfaces, missing input validation, undocumented behavior changes
- **Security**: injection (SQL, command, template), auth bypass, secrets in code, unsafe deserialization, path traversal
- **Data integrity**: missing transactions, partial writes, inconsistent state on failure, TOCTOU races
- **Documentation drift**: behavior changes not reflected in existing docs

Cross-reference business context from Step 2 — concerns flagged in Frames 1-3 should get a focused look here.

Produce a RAW list of potential findings — do NOT verify them yet. Verification happens in Step 5.

## Step 5: Verify Every Finding

**CRITICAL**: AI models hallucinate. Blind trust destroys reviewer credibility. Every claim must be proven with evidence before inclusion.

Merge the raw finding lists from `/branch-review`, Codex, and Claude. Then verify EVERY finding.

### 5a. Verification

For each finding:

1. **Locate the evidence**: read the actual source code, not just the diff. Identify the specific lines that demonstrate the problem.
2. **Trace the execution path**: follow the code flow to prove the problem actually manifests. If a "missing error check" is actually handled upstream, it is not a finding.
3. **Check for mitigations**: search the codebase for existing guards, fallbacks, or design decisions that intentionally address the concern. Read related files, configs, dependencies.
4. **Prove, don't speculate**: each finding must include concrete evidence — file paths, line numbers, code snippets, or external documentation references.
5. **Disprove if wrong**: if investigation shows a finding is invalid, log it as DISPROVEN with the reason — these will be shown to the user in Step 8 so the dismissal can be cross-checked.

### 5b. Per-finding verdict

Each finding gets exactly one of:

- **CONFIRMED**: evidence supports the claim. Include an `**Evidence**:` line summarizing what was checked, what was found, and why it proves the issue.
- **DISPROVEN**: evidence contradicts the claim. Drop the finding from the review; log it internally for Step 8.
- **UNVERIFIABLE**: cannot confirm or deny with available information. Downgrade to a question/observation, never a blocker.

Only CONFIRMED findings proceed to the review.

### 5c. Cross-model merge rules

After verification, label findings by source:

- Both models found the issue AND verification confirmed it → high confidence, tag `[Claude + Codex]`
- Only Codex found it AND Claude verified → tag `[Codex]`
- Only Codex found it AND Claude could not verify → EXCLUDE from the review; note in the Summary that it was investigated and dismissed
- Only Claude found it AND verification confirmed → include normally (no tag)
- Models contradict each other → investigate deeper; present the evidence-backed conclusion

### 5d. Evidence format

Each finding in the published review must carry an `**Evidence**:` line. Example:

> cert-manager `values.yaml:3` sets `enableGatewayAPI: true` unconditionally. **Evidence**: cert-manager source (link) shows the gateway-shim controller discovers CRDs only at startup; `cozystack.cert-manager` PackageSource has no `dependsOn` for `cozystack.gateway-api-crds`; therefore on fresh install cert-manager starts before CRDs exist → gateway support silently non-functional.

Counter-example (rejected as speculation):

> "enableGatewayAPI is set but Gateway API CRDs might not be installed yet" — no evidence of startup behavior, no dependency check.

## Step 6: Classify Confirmed Findings

Two categories. If a finding fits neither, drop it.

### Blockers (NOT LGTM verdict, REQUEST_CHANGES event)

The PR MUST NOT merge with any of these present:

- Bugs that will manifest in production
- Security vulnerabilities
- Data loss or corruption risks
- Broken API contracts (existing consumers will break)
- Broken variants/environments (works in variant A but breaks variant B)
- Missing error handling that causes silent failures
- Resource leaks under normal operation (not just edge cases)
- Behavior changes with stale documentation in the area being changed
- Missing `--ticket` requirements when `--ticket` was provided
- Findings the cascaded `/branch-review` raised as blockers (LGTM bar, comments-as-fixes, in-repo doc accuracy, etc.)

### Action items (non-blocking)

Real concerns worth surfacing but not blocking this merge:

- Tech debt introduced (acceptable now, follow-up worth tracking)
- Missing test coverage on non-critical paths
- Naming or abstraction improvements
- Performance concerns that are not urgent
- Internal-only documentation gaps
- Non-critical refactoring opportunities
- Pre-existing issues in code adjacent to but NOT touched by this PR
- Pre-existing cross-repo docs gaps (file a tracking issue per Step 8/9 and reference its URL)

## Step 7: Draft the Review with Verdict Gate

The review opens with a textual verdict line. The verdict text and the GitHub API event are two distinct layers:

| Textual verdict (first line of body) | GitHub API event |
| --- | --- |
| `LGTM` | `APPROVE` |
| `NOT LGTM` | `REQUEST_CHANGES` |

Use **LGTM** when there are no blockers, **NOT LGTM** when there is at least one. `COMMENT` event is forbidden by default; only allowed if the user explicitly requests a comment-only review (and even then the body should still open with a clear verdict word).

Output structure:

```text
<LGTM | NOT LGTM> — <one-sentence why>

**Business context**: <one sentence from Step 2>

<If blockers exist:>
## Blockers

### B1: <concise title>
**File**: path/to/file.ext:LINE
**Issue**: <description>
**Evidence**: <what was checked, what proves the issue> [Codex] [Claude + Codex]
**Impact**: <what happens if this ships>
**Fix**: <specific actionable suggestion>

### B2: ...

<If non-blocking follow-ups exist:>
## Non-blocking follow-ups

1. <description with file:line; if cross-repo docs gap, include the tracking-issue URL filed in Step 9>
2. ...

<If --ticket provided:>
## Ticket Compliance

**Ticket**: <title + link/ID>
- [done|partial|missing] <requirement 1>
- [done|partial|missing] <requirement 2>
...

**Verdict**: All requirements met | Missing: <list>
```

Style rules:

- **No praise**: no "great work", "overall looks good", "nice refactor", filler. Findings only.
- **No AI attribution**: no "Claude says", "Codex flagged", "automated review found". The `[Claude + Codex]` / `[Codex]` tags after the Evidence line stay internal — strip them before publishing if the PR's audience is external.
- **No private infrastructure**: never mention cluster names, client names, internal IPs, or environment identifiers in public reviews.
- **No internal tool names**: do not name custom skills, slash commands, or tooling (`/pr-review`, `/branch-review`, plugin names) in the published body. Reviewers can be referenced as "Opus" / "Codex" generically if needed; never by tool path.
- **Inline comments**: only for findings on lines that exist in the PR diff. Findings outside the diff go in the review body.
- **One review, not a wall of text**: keep blockers focused and concise. The author should be able to act on each one independently.

## Step 8: User Approval (MANDATORY)

NEVER publish without user approval. This is a public action visible to the PR author.

Present:

1. Textual verdict (LGTM / NOT LGTM) and the corresponding API event (APPROVE / REQUEST_CHANGES) — both, so the user sees the body opener and the GitHub UI label.
2. Full review body
3. Each inline comment with file path and line number
4. List of DISPROVEN findings (so the user can verify dismissals)
5. Drafts of any tracking issues (title + body) to be filed in Step 9 — title, target repo, and full body

Wait for explicit confirmation. If the user requests changes, apply them and re-present.

## Step 9: Publish

### 9a. File tracking issues (if any were prepared in Step 3)

For each approved tracking issue:

```python
import json, subprocess

issue = {"title": "<title>", "body": "<body>"}
result = subprocess.run(
    ["gh", "api", "repos/<owner>/<docs-repo>/issues",
     "--method", "POST", "--input", "-"],
    input=json.dumps(issue), text=True, capture_output=True
)
data = json.loads(result.stdout)
print("Issue URL:", data["html_url"])
```

Capture each URL and splice it into the review body under the relevant non-blocking follow-up.

### 9b. Check for existing review by current user

Multiple reviews from the same user clutter the timeline. If an active review with the same event type exists, UPDATE its body (the body should still open with the LGTM / NOT LGTM word); otherwise POST a new one.

```bash
EXISTING_REVIEW_ID=$(gh api "repos/{owner}/{repo}/pulls/$PR_NUMBER/reviews" \
  --jq "[.[] | select(.user.login == \"$(gh api user --jq .login)\") | select(.state != \"DISMISSED\")] | last | .id // empty")
```

### 9c. Update or create

If updating:

```bash
gh api --method PUT "repos/{owner}/{repo}/pulls/$PR_NUMBER/reviews/$EXISTING_REVIEW_ID" \
  --field body="<new review body>"
```

If creating, use python3 + `json.dumps` (shell escaping of complex review bodies is unreliable):

```python
import json, subprocess

review = {
    "commit_id": "<latest PR head SHA>",
    "event": "APPROVE",  # APPROVE for LGTM, REQUEST_CHANGES for NOT LGTM. Never COMMENT by default.
    "body": "<review body — first line is `LGTM — ...` or `NOT LGTM — ...`>",
    "comments": [
        {
            "path": "path/to/file.ext",
            "line": 42,
            "body": "<comment text — for findings on lines that exist in the diff>"
        }
    ]
}

subprocess.run(
    ["gh", "api", f"repos/{owner}/{repo}/pulls/{pr_number}/reviews",
     "--method", "POST", "--input", "-"],
    input=json.dumps(review), text=True
)
```

After publishing or updating, print the review URL so the user can verify it rendered correctly.

## Important Rules

- **Verdict mandatory**: every review opens with `LGTM` or `NOT LGTM` as the first word of the body, and the corresponding API event is APPROVE or REQUEST_CHANGES. COMMENT is forbidden by default (unless the user explicitly asked for comment-only).
- **Five-frame substance pass is mandatory**, even on small PRs. A trivial PR collapses Frames 1-3 to the obvious, but Frame 4 (docs sync) and Frame 5 (dual-model code-quality) still apply.
- **No speculation**: every finding must have an `**Evidence**:` line. Without evidence, drop.
- **No-docs-found ≠ docs-OK**: open the relevant existing user-facing doc page and read it before declaring docs in sync.
- **Pre-existing in cross-repo docs**: file a tracking issue (after user approval), reference it under non-blocking follow-ups, do not block.
- **Pre-existing in code touched by the PR**: cascaded `/branch-review` treats these as blockers per its own rules. Do not soften them at this layer.
- **Language**: ALL review content MUST be in English.
- **No AI attribution in published text**: the review is from the user's GitHub account. Tags like `[Claude + Codex]` are internal — strip before publishing.
- **Respect existing reviews**: read existing review comments. Do not repeat points already raised by other reviewers unless adding new evidence.
- **No private infrastructure details**: never mention cluster names, client names, internal IPs, or environment identifiers.
- **No internal tool names**: do not name slash commands, skills, or plugin paths in the published body.
- **Update, don't duplicate**: if you have an active review on this PR, UPDATE it rather than creating a new one.
- **Always use `origin/` refs**: when computing diffs locally, ALWAYS use `origin/<branch>`. Bare branch names go stale and produce phantom diffs.
