---
name: pr-review
description: >
  Draft a GitHub PR review with inline comments. Opens with a readiness gate (stops on merge conflicts or red code-related CI with a fix-it note and no verdict, or NOT LGTM when the diff's mechanism for a red check is established), then runs the five-frame substance pass (problem real & root cause in-repo / approach optimal & worth its permanent cost / tradeoffs & scope / docs sync / code quality), cascades /branch-review, performs sequential Claude+Codex dual-model analysis on the PR diff, cross-validates every finding with explicit evidence, and presents the draft for approval. Process and provenance requirements (commit format, sign-off, AI use and its disclosure) come from the project's published contract — `CONTRIBUTING.md`, `AGENTS.md`, and the policies they link, read at the base branch — and block only on a clause it states; style alone never proves AI authorship. A value/design gate can block a PR even when the code is flawless — root cause upstream, permanent maintenance cost disproportionate to niche value, wrong layer, or scope over-reach. Publishing the review to GitHub is opt-in via `--publish`; without it the draft is the deliverable. Reviews open with an LGTM or NOT LGTM verdict (matching the /branch-review convention); the no-verdict paths are the readiness gate's fix-CI / fix-conflicts note and a review that cannot reach a final verdict. An LGTM is published as APPROVE only when the PR can merge right now; otherwise it goes out as COMMENT naming what the merge waits for.
  TRIGGER: invoke proactively whenever the user asks to review, audit, or quality-check a GitHub Pull Request — whether by URL (github.com/.../pull/N), shorthand (owner/repo#N), bare number (#1234), or a "this PR" / "этот PR" reference resolvable from conversation context. Examples — "review PR 2541", "сделай ревью на https://github.com/foo/bar/pull/123", "оцени этот PR", "что думаешь про #9", "проверь PR от X". DO NOT trigger for — replying to existing review comments (use /address-pr-comments), labeling or triaging issues (use /categorize), generating a TLDR (use /tldrpr), or general code questions about a branch with no associated PR. PR vs issue is detected automatically — for issues without code-review intent, do not invoke.
argument-hint: "[PR number] [--publish] [--approve] [--target branch] [--ticket URL|ID]"
---

**CRITICAL**: When `--publish` is passed, this skill produces a PUBLISHED GitHub review visible to the PR author and all watchers. Every word matters. Every claim must be proven. User MUST approve the text before publishing.

Default behavior is **draft only**: the skill performs the full analysis, presents the review and inline comments to the user, and stops. Nothing is sent to GitHub unless `--publish` is set.

## Arguments

Parse $ARGUMENTS for:

- PR number (positional, optional). If omitted, detect from current branch: `gh pr view --json number --jq .number 2>/dev/null`
- `--publish` — actually post the review to GitHub via the API. Without this flag the skill stops after presenting the draft; the draft is the deliverable. Required separately from `--approve` so that the LGTM/NOT-LGTM decision and the publish action are independent.
- `--approve` — submit as LGTM (APPROVE event) explicitly even when no blockers found (default verdict policy is LGTM without blockers, so this flag is informational). Has no effect unless `--publish` is also set.
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

## Step 1.5: Readiness Gate (CI + Mergeability)

Before spending any effort on substance or code analysis, do a fast pass on whether the PR is even in a reviewable state. This is a quick check, not the review. Two independent conditions send the review into **gate mode** — an early exit that produces a comment-style note with NO `LGTM` / `NOT LGTM` verdict, because a verdict on a PR that cannot merge or does not build is noise, and it wastes the expensive analysis on code the author still has to change.

```bash
# Mergeability — CONFLICTING / DIRTY means the branch conflicts with its base
gh pr view $PR_NUMBER --json mergeable,mergeStateStatus --jq '{mergeable, mergeStateStatus}'

# CI — every check run/context with its conclusion (handles both CheckRun and StatusContext shapes)
gh pr view $PR_NUMBER --json statusCheckRollup \
  --jq '.statusCheckRollup[] | {name: (.name // .context), status: .status, conclusion: (.conclusion // .state)}'

# Required checks only: Step 7 needs them to choose between APPROVE and COMMENT
gh pr checks $PR_NUMBER --required --json name,bucket
```

If `mergeStateStatus` comes back `UNKNOWN`, GitHub has not finished computing it — wait a few seconds and re-query once before deciding.

### 1.5a. Merge conflicts (DIRTY)

If `mergeable == "CONFLICTING"` or `mergeStateStatus == "DIRTY"`, the branch conflicts with its base. The diff cannot be trusted — "what changed" is unstable until the author rebases, and any finding computed against a conflicted tree may be an artifact of the conflict rather than the change. **Do not render a verdict.** Enter gate mode: the deliverable is a short note asking the author to resolve the conflicts and re-request review. Skip the dual analysis entirely. A reviewer with write access to the branch does not ask for a conflict with one obvious mechanical answer: the draft proposes syncing the branch per [`references/maintainer-actions.md`](references/maintainer-actions.md) instead, and the review runs on the synced head.

### 1.5b. Red CI plausibly tied to the code

Consider only checks that actually FAILED — `conclusion` in `FAILURE`, `TIMED_OUT`, `ERROR`, `STARTUP_FAILURE`, or a StatusContext `state` of `FAILURE` / `ERROR`. Checks that are still running (`QUEUED`, `IN_PROGRESS`, `PENDING`) or awaiting manual authorization (`ACTION_REQUIRED` — common for fork PRs and protected-environment / deployment gates) are NOT red: the diff has not failed, so do not gate on them, though you may note that CI has not finished. A reviewer with write access proposes approving `ACTION_REQUIRED` fork runs per [`references/maintainer-actions.md`](references/maintainer-actions.md), which sets the conditions. `NEUTRAL`, `SKIPPED`, `CANCELLED` are not failures. Only genuine failures reach the code-related-vs-not test below — do not let the "if you cannot tell" rule pull a pending or manual-approval check into gating.

Split the failing checks into two buckets:

- **Code-related** — build, compile, unit/integration/e2e tests, lint, type-check, vet, schema/manifest validation, generated-code drift, coverage gate. A failure here means the PR in its current state is broken or unverified, so reviewing it wastes the review. Enter gate mode.
- **Not code-related** — missing secrets on a fork PR, a flaky external service, a rate-limited registry, an unrelated required-check misconfiguration, a DCO/label bot. These do NOT gate; note them and continue the normal review.

The test is: "could this red check plausibly be caused by the diff?" If yes — or if you cannot tell — treat it as code-related and gate. Do not spend a full review proving a defect the CI already caught; hand it back.

A failure log that points at a line the diff changed is a lead, not proof that the diff caused the failure. The gate note carries `NOT LGTM` and publishes as `REQUEST_CHANGES` only when the evidence establishes the mechanism: how the change produces the failure, naming the check and the line. Short of that, it stays a no-verdict `COMMENT` that names the unresolved check and the evidence still missing, and never presents the suspected cause as a confirmed defect. Every other gate case is a no-verdict `COMMENT` too.

### 1.5c. Gate-mode output

When 1.5a or 1.5b fires, STOP before Step 2 — do NOT run `/branch-review`, Codex, or Claude's analysis. This also skips Ticket Compliance (the `--ticket` pass): no code was reviewed against requirements, so the note makes no compliance claim. Produce a comment-style note with no verdict word, covering:

- What blocks readiness: the conflict and/or the specific failing checks, named. For a red check whose cause is not established, the evidence still missing.
- The concrete ask: rebase/resolve conflicts, fix the named checks, then re-request review.
- Nothing about code quality beyond the failing check — you have not reviewed the rest and must not imply you have.

The one exception is a 1.5b failure whose mechanism in the diff is established: the note opens with `NOT LGTM`, names the check, the line, and how the change produces the failure, and stays silent on the rest of the code.

Example note (gate form):

> This PR isn't ready for review yet. CI is red on checks that look code-related — `build`, `test (integration)` — and the branch has merge conflicts with `main`. Please rebase to resolve the conflicts, get those checks green, then re-request review. I haven't looked at the code itself yet.

Then hand off to the normal presentation and publish machinery, in gate form: present the note per Step 8, and if (and only if) `--publish` was passed AND the user approved, post it per Step 9 as a `COMMENT`-event review — never `APPROVE`, and `REQUEST_CHANGES` only when 1.5b established how the diff causes the failure. In default (draft) mode the note is simply reported to the user and the skill stops.

If there are no conflicts and no code-related red CI, proceed to Step 1.6.

## Step 1.6: Check Bot Comments

Read all comments and inline review comments from bots (CodeRabbit, Gemini Code Assist, etc.):

```bash
gh pr view $PR_NUMBER --json comments --jq '.comments[] | select(.author.is_bot == true or (.author.login | test("bot|coderabbit|gemini"; "i"))) | {author: .author.login, body: .body}'
gh api "repos/{owner}/{repo}/pulls/$PR_NUMBER/comments" --jq '.[] | select(.user.login | test("bot|coderabbit|gemini"; "i")) | {author: .user.login, path: .path, line: (.original_line // .line), body: .body}'
```

Note which bot findings are valid and which are noise. Check if the author has responded to bot comments. If valid bot findings remain unaddressed, either incorporate them into the review (with new evidence — never repeat verbatim) or surface a general note asking the author to address them.

## Step 1.7: Contribution Contract and Provenance

Process, style, and provenance requirements come from the project, not from the reviewer. Before applying any of them, load the contract the project published. Read it at the base branch, so the PR cannot rewrite the rules it is judged by:

```bash
git ls-tree -r --name-only "origin/$PR_BASE" | grep -iE '(^|/)(contributing|agents|claude)[^/]*\.(md|rst|adoc|txt)$|copilot-instructions|pull_request_template'
gh api "repos/{owner}/{repo}/pulls/$PR_NUMBER/commits" --jq '.[] | "--- \(.sha[:8]) <\(.commit.author.email)>\n\(.commit.message)"'
gh pr view $PR_NUMBER --json body --jq .body
```

Read every file that applies to the changed paths (`CONTRIBUTING.md`, `AGENTS.md`, the PR template) and the review, testing, compatibility, and AI-use policies they link to. Note what they require of commit messages, sign-off, AI use and its disclosure, tests, and compatibility. The user's explicit instructions for this review count as contract too. Testing and compatibility clauses also feed the tests and no-regression gates in Step 6.

Then hold the commits and the PR body to that contract:

- **A clause the PR violates** is a verdict finding (Step 6, Contract blockers) that quotes the offending line and the clause as its Evidence: a commit format the guide mandates, a missing `Signed-off-by` under a DCO, a disclosure trailer the AI policy requires or forbids.
- **A requirement the contract does not state** never blocks. A message that walks through the diff instead of giving the reason, or a session link standing in for the rationale, may still get a concrete non-blocking comment about clarity.
- **Style does not prove AI authorship.** Narrating comments, section banners, em-dash clusters and similar tells are evidence about clarity, never about authorship: they justify a concrete comment about unnecessary prose, and a comment in the diff that says WHAT instead of WHY stays a code finding through the cascaded `/branch-review`. A disclosure clause blocks only when authorship is established by something other than style: the author's own statement, a tool byline or trailer, a session link.

An empty commit without `Signed-off-by` that GitHub inserted while merging a stack parent is not the author's text: it is mechanical cleanup per [`references/maintainer-actions.md`](references/maintainer-actions.md), not a provenance finding.

## Step 2: Business Context

Before any code reading, frame WHY this PR exists. Read in this order:

1. PR title and full body
2. Linked issues (`closingIssuesReferences` in `gh pr view`) and their acceptance criteria
3. Existing reviews and their findings (do not repeat already-raised points)
4. If `--ticket` provided, fetch ticket content:
   - URL starting with `http`: `gh issue view <number> --repo <owner/repo>` for GitHub URLs, `WebFetch` for external URLs (Jira, Linear, Notion)
   - GitHub shorthand (`#123`): `gh issue view 123` in the current repo
   - Other ID: ask the user for the full URL

Formulate a one-sentence summary of the business problem this PR solves. Every later finding must be evaluated against this context. The summary heads the draft in Step 8 so the user can check the framing; it is not a separate line of the published body, which holds only the verdict sentence and the items without a diff line (Step 7). When the context is the reason for the verdict, the verdict sentence says so.

If `--ticket` was provided, also extract:

- Title and description
- Acceptance criteria (specific requirements, if listed)
- Scope (what is in scope, what is explicitly out of scope)

## Step 3: Five-Frame Substance Pass

Sequentially answer the five questions, taking notes. Frames 1-3 are a maintainer's gate on whether the change SHOULD exist at all — any one of them can independently produce a `NOT LGTM` via the Value/Design blocker category in Step 6, even when the code is correct, tested, and well-written. Do NOT collapse them into "the code works, so it's fine": a flawless PR can still not belong in this repository. Frame 5 delegates code quality to Step 4. The output of this step is a list of preliminary concerns to verify in Step 5 — value/design concerns carry the SAME evidence bar as code findings (a link to where the root cause lives, the deviated spec/contract clause, a concretely-named cleaner alternative), they are not free-form opinion.

**Frame 1 — Is the problem real, and is THIS repo the right place to fix it?** Two parts. (a) Verify the symptom against current code/docs/running behavior, not just the PR description — trace "X causes Y"; if you cannot reproduce the claim from reading the code, that is a finding. (b) Locate the ROOT CAUSE. If the real cause lives upstream, in a dependency, in a consumer's misconfiguration, or in a spec/contract this repo correctly implements, then a fix HERE is a workaround for someone else's bug. Working around an external bug by baking a permanent deviation (from a spec, an API contract, an invariant) into this repo is a Value/Design blocker, not a feature — the fix belongs where the cause is. Name where the root cause actually lives, with evidence (the upstream issue, the spec clause, the misconfigured consumer).

**Frame 2 — Right approach, right layer, worth its permanent cost?** Enumerate 2-3 realistic alternatives (different abstraction layer, different tool, config-only, fix-it-upstream, compose existing components, or do nothing) and say why each is rejected or accepted. Then weigh **value against maintenance cost explicitly**: value = what this gives and to how many users (a broad need vs a niche or single-consumer case); cost = this code is maintained FOREVER — new surface area, new failure modes, new docs to keep in sync, new invariants constraining future changes, added security/attack surface, and any spec/contract deviation every future maintainer inherits. If a cleaner solution exists that needs less code or no code in this repo (a config pattern, an upstream fix, composing existing pieces), the heavier in-repo approach is a Value/Design blocker even when it works — "it works and has tests" does not justify taking on permanent cost. To block on this, name the cleaner alternative concretely and, ideally, show it works; a bare "not worth it" without a demonstrated alternative is speculation — downgrade it to a non-blocking design note. If you cannot list alternatives or articulate the value/cost balance, the substance work is not done.

**Frame 3 — Tradeoffs acknowledged, and is the scope minimal?** Two parts. (a) Tradeoffs: storage cost, performance, security, operational burden, lock-in, default-vs-recommended mismatch, migration cost — the PR (description, README, comments) should name the tradeoffs it accepts; if it doesn't, raise them. (b) Scope: is this the minimal honest change for the stated problem, or does it over-reach? A PR that also ships convenience layers, behavior that sounds authoritative but cannot be truly guaranteed, or "while I'm here" additions beyond the core need has a scope ceiling — identify the minimal acceptable subset and flag the rest as over-reach.

**Frame 4 — Is the documentation in sync?** Look for a sibling docs PR (typical pattern: code in this repo + docs in a `*-website` repo, linked from the PR body or with a matching slug). Verify it exists, is OPEN, and matches what the code ships now (flag names, defaults, prerequisites, examples). Also check in-repo docs (`README.md`, `docs/`, package READMEs).

When the docs search returns empty, that is ambiguous — it can mean either (a) the change is plumbing/internal and legitimately needs no docs, or (b) the change is user-facing but the docs gap predates this PR. To resolve, open the relevant existing user-facing doc page and read it as a user would. Ask: does the documented workflow rely on the behavior this PR changes? Does it currently misrepresent reality (if a bug was latent)? Does it omit a now-relevant capability?

For pre-existing cross-repo docs gaps, prepare a tracking-issue draft (title + body) now; it will be filed in Step 9 after user approval, and its URL spliced into the review under non-blocking follow-ups. Do not block the PR on a pre-existing cross-repo gap. In-repo docs follow the cascaded `/branch-review` (Step 4a) attribution rules: docs the diff made wrong are blockers there; docs already wrong at the merge base arrive in its "Found outside this diff" section and are routed to action items / tracking issues here — do not duplicate that logic.

**Frame 5 — Is the code quality solid?** This frame is satisfied by the dual analysis in Step 4 (cascaded `/branch-review` + Codex + Claude). Note here whether any business-context concerns from Frames 1-3 need explicit cross-validation by the models, and forward those as hints into the dual analysis.

## Step 4: Dual Analysis

Run two analyses in sequence, then merge.

### 4a. Cascade `/branch-review`

Invoke the `/branch-review` skill with `--target $PR_BASE` (and `--ticket <ticket>` if provided; on a re-review round also `--round1-head <sha>` from the first round's output header — the `Reviewed <branch> at <sha>` line — and include the prior round's origin ratio in the invocation context so its convergence rule can fire). It owns its own rules — LGTM/NOT LGTM verdict, merge-base attribution (introduced / worsened / interacted-with defects block; purely pre-existing ones go to its "Found outside this diff" section), comments-as-fixes are blockers, remedy proportionality (changed logic needs a test in the existing test surface; a new checker, linter rule, CI job, or guard script is never a required remedy), doc accuracy for docs the diff made wrong. Do NOT duplicate those rules here. Capture its verdict and BOTH of its finding sections.

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
- **Regressions**: behavior that worked before this change and is now altered or removed — check ALL config variants, defaults, and flags, not just the common path. A narrow blast radius is not a reason to skip this; a path used by few is still a path that worked
- **Security**: injection (SQL, command, template), auth bypass, secrets in code, unsafe deserialization, path traversal
- **Data integrity**: missing transactions, partial writes, inconsistent state on failure, TOCTOU races
- **Documentation drift**: behavior changes not reflected in existing docs
- **Comment hygiene**: a comment that says WHAT the code does (narrates the next line, restates a signature, banners a section, logs a change) instead of WHY it is this way

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

Each finding in the draft must carry an `**Evidence**:` line; the published item compresses it per Step 7. Example:

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
- **Tests gate** — the changed area already has tests, but new or changed code ships without tests, or with happy-path-only tests that never exercise rejected/invalid/boundary behavior. Tests in a tested area must define the full contract — what is allowed AND what is rejected — so they read as executable documentation. Shallow or absent tests where a test convention already exists = NOT LGTM, never an action item.
- **No-regression gate** — any behavior that worked before this PR and no longer works, across every config variant, default, and flag, not just the common path. "Affects few users", "edge case", "rare config", "deprecated anyway" are NOT valid reasons to accept a regression. The only non-blocking path is an intentional breaking change the PR explicitly declares with a migration note — and even then it is surfaced in the verdict, never passed silently.
- Missing error handling that causes silent failures
- Resource leaks under normal operation (not just edge cases)
- Behavior changes with stale documentation in the area being changed
- Missing `--ticket` requirements when `--ticket` was provided
- Findings the cascaded `/branch-review` raised as verdict findings (merge-base attribution, comments-as-fixes, docs the diff made wrong, etc.)

**Value/Design blockers (from Frames 1-3)** — the change should not merge in its current form for reasons independent of code correctness. Each still requires Step 5 evidence — a link to where the root cause lives, the specific spec/contract clause deviated from, or a concretely-named (ideally demonstrated) cleaner alternative. Without that evidence it is a non-blocking design note, not a blocker.

- Root cause lives upstream / outside this repo and the PR works around it by baking a permanent deviation (spec, contract, invariant) into this codebase.
- Permanent maintenance cost disproportionate to value — niche or single-consumer benefit versus forever-maintained surface area — when a cleaner solution (a config pattern, an upstream fix, composing existing components, or doing nothing) exists.
- Wrong layer / wrong abstraction: the change solves the problem where it misrepresents state or violates the component's contract (e.g. synthesizing a success response the component cannot actually guarantee).
- Scope over-reach: the PR ships materially more than the minimal honest change the problem requires; the verdict names the minimal acceptable subset and blocks the rest.

**Contract blockers (from Step 1.7)** — a commit, the PR body, or the change violates a clause of the project's published contract or of the user's explicit instructions for this review. Each quotes the offending line and the clause as Evidence. A requirement neither source states is at most a non-blocking comment, and style alone never establishes AI authorship.

### Action items (non-blocking)

Real concerns worth surfacing but not blocking this merge:

- Tech debt introduced (acceptable now, follow-up worth tracking)
- Adding tests to an area that has NO existing test convention (recommend, do not block — the tests gate above applies only where tests already exist)
- Naming or abstraction improvements
- Performance concerns that are not urgent
- Internal-only documentation gaps
- Non-critical refactoring opportunities
- Pre-existing issues in code adjacent to but NOT touched by this PR, including everything from `/branch-review`'s "Found outside this diff" section — carry each into the review with its severity, and make sure each gets a home (a filed issue, a parked branch, or a project-memory entry); the gate is not closed until every one has one
- Pre-existing cross-repo docs gaps (file a tracking issue per Step 8/9 and reference its URL)

## Step 7: Draft the Review with Verdict Gate

**Gate mode (Step 1.5) skips this step entirely** — it produced no findings beyond the one an established-mechanism note carries and, outside that case of 1.5b, no verdict; its deliverable is the readiness note from Step 1.5c, presented in Step 8. Everything below applies only to a full review.

The review opens with a textual verdict line. The verdict text and the GitHub API event are two distinct layers:

| Textual verdict (first line of body) | Merge state | GitHub API event |
| --- | --- | --- |
| `LGTM` | mergeable now: every required check green on the exact head, no independent prerequisite open | `APPROVE` |
| `LGTM` | not mergeable now: a required check pending or red for a reason outside the diff, or an independent prerequisite (companion PR, joint test, maintainer-side setup) still open | `COMMENT`, the body naming what the merge waits for |
| `NOT LGTM` | any | `REQUEST_CHANGES` |

Use **LGTM** when there are no blockers, **NOT LGTM** when there is at least one — and a Value/Design blocker (Step 6) counts, so a PR with perfect code still gets `NOT LGTM` when Frames 1-3 reject it. Red CI the diff causes is a blocker like any other proven defect.

`APPROVE` means "this can merge now", not "the code looks fine". There is no approve-with-hold: an approval on a PR that cannot merge is read as permission to merge it, and branch protection counts it the moment the blocking condition clears. The one exception is a real stack: a PR whose base is its parent's branch may be approved while it waits only for that parent, when its own part is ready.

`COMMENT` carries a verdict word in the merge-state case above and in a user-requested comment-only review. It carries none in gate mode (Step 1.5), whose established-mechanism case is `REQUEST_CHANGES`, and whenever the review cannot reach a final verdict, for example when a blocker-sized question stays UNVERIFIABLE — then the body says what is missing. A `COMMENT` never clears an earlier `APPROVE` or `CHANGES_REQUESTED` (see 9b).

Every finding — blocker or follow-up — is written as one item in the same shape, readable in 30 seconds:

- **What** is wrong: one sentence that carries the mechanism.
- **Where**: `file:line`, `commit <sha>`, a PR body section, or a check name.
- **Fix**: the concrete action.

No narration of what the reviewer checked ("I traced X, then ran Y"), no inventory of tests inside an item. The Step 5 `**Evidence**` line belongs to the draft the user sees in Step 8; the published item keeps only the proof the author needs to believe the mechanism. Mark items that do not block with `(non-blocking)`.

A finding on a line that exists in the PR diff goes only into an inline comment on that line. The body never repeats it. The body holds the verdict sentence plus the items that have no diff line: commit messages, the PR body, CI, branch history, code outside the diff, cross-repo docs gaps (with the tracking-issue URL filed in Step 9). When every finding went inline, the body is the verdict line alone. An `APPROVE` body is one line, plus optional asks in the same item shape.

Body structure:

```text
<LGTM | NOT LGTM> — <one-sentence why>

<If items without a diff line exist:>
1. <what, with the mechanism> — <where>. Fix: <action>.
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
- **Inline or body, never both**: a finding on a line in the PR diff is an inline comment and nothing else; commit message, PR body, CI, and outside-the-diff findings go in the body and never inline.
- **One review, not a wall of text**: the author should be able to act on each item independently, without reading an essay first.

## Step 8: Present the Draft

Present:

1. Textual verdict (LGTM / NOT LGTM) and the API event (APPROVE / COMMENT / REQUEST_CHANGES) the published version would carry, chosen per the Step 7 table — both, so the user sees the body opener and the GitHub UI label. For an LGTM posted as COMMENT, name the blocking merge condition.
2. Full review body
3. Each inline comment with file path and line number
4. List of DISPROVEN findings (so the user can verify dismissals)
5. Drafts of any tracking issues (title + body) that publish-mode would file in Step 9 — title, target repo, and full body
6. Maintainer actions Step 9 would perform per [`references/maintainer-actions.md`](references/maintainer-actions.md): a branch sync, fork-run approvals

**Gate mode (Step 1.5):** present only the readiness note and the concrete ask — there are no inline comments, DISPROVEN list, or tracking issues, and no findings beyond the one an established-mechanism note carries, because no code review was performed. The approval gate below still applies before any `--publish`.

If `--publish` was **not** passed, this is the deliverable — STOP here. Do not call `gh api`, do not file tracking issues, do not invoke any write-side GitHub API. The user can re-run with `--publish` after reviewing.

If `--publish` **was** passed: this output is now an approval gate. Wait for explicit confirmation before continuing to Step 9. If the user requests changes, apply them and re-present. **Never** call the publish steps without that explicit confirmation — `--publish` enables the option, the user's approval triggers the action.

## Step 9: Publish (only when `--publish` was passed AND user approved in Step 8)

**Gate mode (Step 1.5):** skip 9a (no tracking issues). POST a new `COMMENT`-event review carrying the readiness note — no inline comments, no verdict word. 9b's lingering-verdict check still applies (a prior `APPROVED` or `CHANGES_REQUESTED` survives this comment). A 1.5b failure whose mechanism in the diff is established posts `REQUEST_CHANGES` instead, its note opening with `NOT LGTM`.

Approved maintainer actions (Step 8 item 6) run first, per [`references/maintainer-actions.md`](references/maintainer-actions.md).

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

### 9b. Read your prior reviews on this PR

Every publish POSTs a NEW review; a submitted one is never edited (see **Never update a published review** below). Prior reviews are still read here because a lingering approval or change request needs surfacing.

```bash
ME=$(gh api user --jq .login)
# --paginate --slurp so a PR with >30 reviews does not silently truncate to page 1. `gh api` rejects --slurp together with --jq, so filter with a separate jq; .[][] flattens the array-of-pages into a flat, chronologically-ordered list.
MY_REVIEWS=$(gh api --paginate --slurp "repos/{owner}/{repo}/pulls/$PR_NUMBER/reviews" | jq -c "[.[][] | select(.user.login == \"$ME\") | select(.state != \"DISMISSED\")]")

# EFFECTIVE verdict on GitHub ignores COMMENTED — it is the latest APPROVED /
# CHANGES_REQUESTED, which can be OLDER than the latest review of any state. Used only to
# detect a lingering approval a COMMENT would not dismiss.
EFFECTIVE_VERDICT=$(jq -r '[.[] | select(.state == "APPROVED" or .state == "CHANGES_REQUESTED")] | last | .state // empty' <<<"$MY_REVIEWS")
```

Older reviews stay in the timeline as history — the new one becomes the effective verdict. One caveat GitHub imposes: a `COMMENT` review never dismisses a prior `APPROVED` or `CHANGES_REQUESTED` state, and that state can sit several reviews back, which is why `EFFECTIVE_VERDICT` scans the whole list rather than the latest entry. When this run publishes a `COMMENT` (any of the Step 7 cases) over a non-empty `EFFECTIVE_VERDICT`, that earlier state keeps counting: a stale approval still satisfies branch protection, a stale change request still blocks. Surface this to the user so they can decide whether to dismiss it — do not dismiss it silently. (`APPROVE` supersedes a prior change request and `REQUEST_CHANGES` a prior approval, so neither needs a dismissal.)

### 9c. Create the review

Always POST, never PUT. Use python3 + `json.dumps` (shell escaping of complex review bodies is unreliable):

```python
import json, subprocess

review = {
    "commit_id": "<latest PR head SHA>",
    "event": "APPROVE",  # Per the Step 7 table: APPROVE only for a mergeable-now LGTM, REQUEST_CHANGES for NOT LGTM, COMMENT otherwise.
    "body": "<review body — first line is `LGTM — ...` or `NOT LGTM — ...`; EXCEPT in gate mode, where the body is the readiness note: no verdict word under COMMENT, opening with `NOT LGTM` under REQUEST_CHANGES when the 1.5b mechanism is established>",
    "comments": [
        {
            "path": "path/to/file.ext",
            "line": 42,
            "side": "RIGHT",
            "body": "<one item in the Step 7 shape — the line must exist in the PR diff, otherwise the item goes to the body>"
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

- **Publish is opt-in**: nothing is sent to GitHub unless the invocation included `--publish` AND the user approved the draft in Step 8. The default mode is local draft only.
- **Readiness gate first**: before any substance or code analysis, check mergeability and CI (Step 1.5). Merge conflicts (DIRTY) or red CI plausibly caused by the diff → gate mode: a `COMMENT` note asking the author to fix conflicts / CI, no `LGTM` / `NOT LGTM` verdict unless the diff's mechanism for a red check is established, and NO dual analysis. A red check becomes `NOT LGTM` / `REQUEST_CHANGES` only when the evidence shows how the diff causes it; a log pointing at a changed line is a lead, and without the mechanism the note names the unresolved check and the missing evidence. Red CI that clearly cannot be caused by the diff (missing fork secrets, flaky external service) does not gate.
- **Value/Design gate is a real verdict**: Frames 1-3 can produce `NOT LGTM` on their own — root cause upstream, permanent maintenance cost disproportionate to niche value, wrong layer, or scope over-reach — even when the code is correct and tested. These blockers carry the same evidence bar as code findings (where the root cause lives, the deviated spec/contract clause, a concretely-named cleaner alternative); without evidence they are non-blocking design notes.
- **Verdict mandatory**: every review opens with `LGTM` or `NOT LGTM` as the first word of the body. The no-verdict paths are gate mode (Step 1.5, except a red check whose mechanism in the diff is established) and a review that cannot reach a final verdict; both post a `COMMENT` that says what is missing.
- **APPROVE means mergeable now**: every required check green on the exact head and no independent prerequisite open; a real stack's child waiting only for its parent is the one exception. A clean LGTM that cannot merge yet posts as `COMMENT` naming what it waits for — never approve-with-hold. Red CI the diff causes is `REQUEST_CHANGES`.
- **Five-frame substance pass is mandatory**, even on small PRs. A trivial PR collapses Frames 1-3 to the obvious, but Frame 4 (docs sync) and Frame 5 (dual-model code-quality) still apply.
- **Tests gate (mandatory)**: in any area that already has tests, changed or new code ships with tests, and those tests must cover the full contract — valid use AND rejected/invalid use — not just the happy path. Shallow or absent tests in a tested area = NOT LGTM. (An area with no existing tests gets a recommendation, not a block.)
- **No-regression gate (mandatory)**: what worked must keep working. A small blast radius is never a license to break it — "few users", "edge case", "rare config" are not acceptable justifications. Only an explicitly declared, migration-documented breaking change may pass, and it is surfaced in the verdict, never silent.
- **No speculation**: every finding must have an `**Evidence**:` line. Without evidence, drop.
- **Contract, not reviewer taste**: process, style, and provenance requirements (commit format, sign-off, AI use and disclosure) block only on a clause of the project's published contract, read at the base branch, or on the user's explicit instructions; the violated clause is quoted as Evidence. Style tells justify a clarity comment and never prove AI authorship.
- **No-docs-found ≠ docs-OK**: open the relevant existing user-facing doc page and read it before declaring docs in sync.
- **Pre-existing in cross-repo docs**: file a tracking issue (after user approval), reference it under non-blocking follow-ups, do not block.
- **Pre-existing defects**: cascaded `/branch-review` routes them by merge-base attribution — a defect the diff worsened, hid, or built on blocks; a purely pre-existing one arrives in its "Found outside this diff" section and becomes an action item that must get a home (filed issue, parked branch, or project-memory entry). Do not soften the former into the latter at this layer.
- **Language**: ALL review content MUST be in English.
- **No AI attribution in published text**: the review is from the user's GitHub account. Tags like `[Claude + Codex]` are internal — strip before publishing.
- **Respect existing reviews**: read existing review comments. Do not repeat points already raised by other reviewers unless adding new evidence.
- **No private infrastructure details**: never mention cluster names, client names, internal IPs, or environment identifiers.
- **No internal tool names**: do not name slash commands, skills, or plugin paths in the published body.
- **Never update a published review**: `PUT .../reviews/{id}` is forbidden in every mode, including a re-review that lands the same verdict as the last one. A submitted review is a dated statement someone already read and possibly replied to; rewriting its body edits that history and, because the endpoint cannot change the event, can leave the body and the GitHub verdict label disagreeing. Every publish POSTs a new review, which becomes the effective verdict and leaves each earlier round readable in the timeline.
- **Always use `origin/` refs**: when computing diffs locally, ALWAYS use `origin/<branch>`. Bare branch names go stale and produce phantom diffs.
