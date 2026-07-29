---
name: branch-review
description: Review current branch changes in isolation. Output starts with LGTM verdict — if no LGTM, the code is not ready to merge. The verdict is decided ONLY by defects the diff introduced, worsened, or interacts with (merge-base attribution, computed from git); pre-existing defects are reported in full in a separate "Found outside this diff" section and never block. LGTM is compatible with a non-empty recommendations list. IMPORTANT — always pass all flags you already know from context (target branch, project type, ticket, round-1 head, etc.). Do not rely on auto-detection when the answer is known. Pass --target to set which branch the changes are going INTO. Pass --ticket with a URL or ID to validate against requirements. On re-review rounds pass --round1-head with the SHA from round 1's printed review header to enable churn diagnostics.
argument-hint: "[path] [--target branch] [--nitpick] [--type go|node|python|rust] [--exclude pattern,pattern] [--ticket URL|ID] [--round1-head sha]"
context: fork
agent: general-purpose
---

**Important**: If the current directory is not a git repository, ask the user where the target repository is located before proceeding.

**CRITICAL**: Do not switch branches in the user's repo. If the active branch is the one to review, analyze it in place using `git diff`, `git log`, `git show`. If the active branch is NOT the target (for example when this skill is cascaded from `/pr-review` and the active branch is `master`/`main` while the target is a feature branch), create a temporary git worktree pinned to the target branch and run all analysis there:

```bash
WORKTREE_DIR=$(mktemp -d -t branch-review-XXXX)
trap 'git worktree remove --force "$WORKTREE_DIR" 2>/dev/null' EXIT INT TERM
git worktree add "$WORKTREE_DIR" <target-branch>
# All git operations use: git -C "$WORKTREE_DIR" diff/log/show ...
# All file reads are relative to "$WORKTREE_DIR"
# The trap above removes the worktree on every exit path (success, error, interrupt)
```

Rationale: switching branches in the user's main repo would clobber their working state. A worktree gives an isolated checkout of the target branch without disturbing the active one. The "stay on the active branch" intent is preserved — the active branch is never touched.

## Arguments

Parse $ARGUMENTS for:

- Path to repository directory (positional, an existing directory path — e.g. `~/git/github.com/org/repo` or `../my-worktree`). If provided, ALL git and file operations must run inside this directory
- `--target` the branch this PR is merging INTO (e.g. `next`, `develop`, `main`). This is the most important parameter for determining the correct diff scope
- `--nitpick` flag for pedantic mode
- `--type` project type (e.g. `go`, `node`, `python`, `rust`) — skips auto-detection
- `--exclude` additional exclude patterns, comma-separated (e.g. `docs/,*.gen.go`)
- `--ticket` ticket reference — URL (GitHub issue, Jira, Linear, Notion, etc.) or ID (e.g. `#123`, `PROJ-456`). When provided, the review includes a **Ticket Compliance** section that validates whether the changes fulfil the ticket requirements
- `--round1-head` the head SHA the FIRST review round of this gate ran on — copy it from that round's output header (the `Reviewed <branch> at <sha>` line). Used only to compute finding-origin labels (feature vs churn, see "Finding origin and the churn mark"); it never affects severity or the verdict, so it is an auditable record of a past run, not a scope declaration. Omit on the first round

Examples:

- `/review-branch` → auto-detect everything in current directory
- `/review-branch ~/git/github.com/org/repo` → review in that directory
- `/review-branch --target next` → review changes going into `next`
- `/review-branch --nitpick` → pedantic mode
- `/review-branch --type go --exclude "api/generated/"` → Go project, extra excludes
- `/review-branch --ticket https://github.com/org/repo/issues/42` → validate against GitHub issue
- `/review-branch --ticket PROJ-456` → validate against ticket ID (fetched via appropriate tool)
- `/review-branch ~/worktrees/feature --target develop --nitpick --type node` → all combined
- `/review-branch --target main --ticket #123 --nitpick` → target main, validate against ticket, pedantic mode
- `/review-branch --target main --round1-head 1a2b3c4` → re-review round with churn diagnostics

## Setup

**If a path argument was provided**, use it as the working directory for ALL git and file operations throughout the review. Pass `-C <path>` to every `git` command, and use the path as the base for all file reads. When a path is provided, assume the user has pointed at the right tree — do not create a worktree even if the active branch differs from the target.

**First, record the current branch** (you will need it throughout):

```bash
# Without path argument:
REVIEW_BRANCH=$(git branch --show-current)
# With path argument:
REVIEW_BRANCH=$(git -C <path> branch --show-current)
```

Determine target branch (the branch this PR is merging INTO):

1. If `--target` argument provided: use it
2. Otherwise: check if an open PR exists for the current branch and use its base:
   ```bash
   gh pr view --json baseRefName --jq .baseRefName 2>/dev/null
   ```
3. If no PR found: detect via `git rev-parse --abbrev-ref @{upstream}` (tracking branch), stripping the remote prefix (e.g. `origin/next` → `next`)
4. If no tracking branch: try `main`, fallback to `master`
5. If neither exists: report error and stop

**Decide whether a worktree is needed.** Compare `REVIEW_BRANCH` to the branch being reviewed:

- If a path argument was provided: trust it, no worktree.
- Else if `REVIEW_BRANCH` matches the branch to review: analyze in place, no worktree.
- Else (active branch is different — typical when cascaded from `/pr-review`): create a worktree at the branch to review per the worktree block in the CRITICAL section above. From this point on, `<path>` refers to that worktree path. Cleanup runs via the `trap` on exit.

Find the merge base (the point where the branch being reviewed diverged from the target) and record the head being reviewed:

```bash
MERGE_BASE=$(git -C <path> merge-base $REVIEW_BRANCH <target-branch>)
REVIEW_HEAD=$(git -C <path> rev-parse HEAD)
```

**Print the review header** so the user can verify the scope: `Reviewing <REVIEW_BRANCH> at <REVIEW_HEAD> against <target-branch>` (short SHA is fine). The output header restates the same SHA as `Reviewed <REVIEW_BRANCH> at <REVIEW_HEAD>` — that output line is the auditable record `--round1-head` refers to on later rounds, so the round-1 ref can always be recovered from the round-1 review output.

## Loading the ticket

<if --ticket>
If `--ticket` is provided, fetch the ticket content BEFORE reviewing the diff:

- **URL** (starts with `http://` or `https://`): use `gh` CLI for GitHub URLs (e.g. `gh issue view <number> --repo <owner/repo>`), or `WebFetch` for other URLs (Jira, Linear, Notion, etc.)
- **GitHub shorthand** (`#123`): use `gh issue view 123` in the repository being reviewed
- **Other ID** (`PROJ-456`): attempt to resolve via web search or ask the user for the full URL

Extract from the ticket:
1. **Title and description** — what was requested
2. **Acceptance criteria** — specific requirements, if listed
3. **Scope** — what is in scope and what is explicitly out of scope

If the ticket cannot be fetched (404, auth required, etc.), warn the user and continue the review without ticket validation.
</if>

## Getting the diff

1. If `--type` provided, use it. Otherwise detect the project type (Go, Node, Python, Rust, etc.) and build an exclude list dynamically:
   - Lock files (go.sum, package-lock.json, yarn.lock, Cargo.lock, poetry.lock, etc.)
   - Vendored dependencies (vendor/, node_modules/, third_party/, .vendor/)
   - Generated code (*.generated.*, *_generated.*, zz_generated.*, *.pb.go, etc.)
   - Build artifacts, minified files, etc.

2. Append any `--exclude` patterns from arguments.

3. Run the diff excluding those patterns:

   ```bash
   git diff <MERGE_BASE> -- . ':!<pattern1>' ':!<pattern2>' ...
   ```

   (Note: no HEAD — this compares the working tree against the merge base, capturing all changes including uncommitted ones. The merge base is the point where the current branch diverged from the target branch.)

## Understanding the changes

You are NOT limited to the diff. When the diff alone is not enough to understand the change:

- Read full files to see surrounding context
- Read project documentation, READMEs, or comments
- Use web search to understand libraries, APIs, or patterns you don't recognize
- Check tests, configs, or related files that help clarify intent

Do whatever is needed to review competently. The diff is the starting point, not the boundary.

## Review criteria

Review the diff for:

- Bugs and logic errors
- Security issues
- Leaked secrets (tokens, API keys, passwords, private keys, credentials, hardcoded connection strings, .env values)
- Error handling gaps
- Code clarity and maintainability
- Naming and structure
- Test coverage: if the area being changed already has tests, new or changed code MUST come with tests, and those tests must define the full contract — valid use AND rejected/invalid use (error paths, boundaries, invalid inputs) — so they read as executable documentation of what is allowed and what is not. Happy-path-only tests in a tested area do not satisfy this and block (NOT LGTM). If the area has no tests at all, recommend adding them but do not block on that alone
- Where a code defect is found: suggest a specific test in the existing test surface that would demonstrate the problem (e.g. "a test that calls X with empty input would expose this nil pointer")
- Adjacent issues: if you find a problem, look at the surrounding code in the same area — related issues nearby are worth surfacing (not a full codebase audit, just the vicinity of the changes). Report everything you find; attribution (below) decides which section each finding lands in
- Comments as fixes: if a change "addresses" a problem by adding a comment (TODO, FIXME, HACK, explanatory note, warning comment) instead of actually fixing the code — this is NOT a fix. Flag it explicitly: a comment documents a known problem but does not solve it. Nobody reads comments in the heat of the moment, and the problem will bite someone eventually. The actual code must be changed. This is always a blocking issue (NOT LGTM)
- No regression from laziness: any behavior that worked before this change and stops working is a blocking issue (NOT LGTM). "Affects only a minority of users", "edge case", "rare config", "deprecated anyway" are NOT acceptable justifications — a path used by few is still a path that worked. Check all config variants, defaults, and flags, not just the common path. The only allowed break is an intentional breaking change the PR explicitly declares with a migration path; surface it in the review, never let it pass silently
- Documentation accuracy: if the diff changes behavior, existing documentation (README, DESIGN.md, docs/, inline doc comments, Helm values descriptions, CLAUDE.md, etc.) that still describes the old behavior is a verdict finding and blocks — as are examples the diff broke and references to entities the diff removed or renamed. Documentation that was already wrong at the merge base goes to "Found outside this diff" with severity, per attribution below

## Finding attribution

Every finding — from the diff or from the surrounding code — gets one mechanical question, answered from git, not from anyone's claim: **does this defect exist at the merge base?** Check with `git show $MERGE_BASE:<file>` and `git -C <path> blame`.

- Absent at merge base, present at head → the diff introduced it. **Verdict finding, blocks.**
- Worked at merge base, broken at head → regression. **Verdict finding, blocks** (same test, reversed).
- Already present at merge base, and the diff does not change its behavior → pre-existing. **Reported in full in "Found outside this diff"** with severity — routed out of the verdict, never dropped.
- Present at merge base, but the diff **interacts** with it — worsens it, hides it, builds on it, or deletes a mitigation that made it harmless → the state at head differs from the state at base, so the same test catches it. **Verdict finding, blocks.** Example: a guide installed a legacy tool long before the PR (pre-existing, routed out), but the PR deleted the compatibility tip that made that install work (interaction, blocks).

The PR owns what it changed and what its changes interact with — nothing more. There is no "the PR touched this area, so the PR owns the area". Attribution is computed by the reviewer from git; the authoring session has no channel to influence it.

## Remedy proportionality

The remedy lives in the same layer as the defect:

- **Changed logic in code**: a test in the **existing** test surface, per the test-coverage criterion above. Absent test blocks.
- **Fixed wording in docs or comments**: the fix is the deliverable. No test demanded.
- **Never propose a new checker, linter rule, CI job, or guard script as the required remedy for a finding.** If the existing test surface cannot express the check, "not machine-checkable here" is a complete answer. A new guard may be suggested only in "Found outside this diff" as its own future work — never as a condition for this PR's verdict.

## Finding origin and the churn mark

A review gate is a control loop. While findings come from the feature, the loop converges: each fix shrinks what can be found. When each finding spawns a guard and the guard spawns new findings, the loop grows the code it is reviewing and diverges — while from inside, every round looks identical ("N findings, fix, re-run"). The origin mark is the instrument that distinguishes the two regimes.

Three origins, all computed from git, zero declarations:

| Origin | Definition | Role |
| --- | --- | --- |
| pre-existing | line exists at merge base | "Found outside this diff" section |
| feature | line absent at merge base, present at the round-1 head | normal verdict finding |
| churn | line introduced after the round-1 head, i.e. by the gate loop itself | normal verdict finding, plus loop diagnostics |

Mechanics: `git blame` the finding's line, take the commit, check `git merge-base --is-ancestor <commit> <round1-head>`. The unit of attribution is the line — blame survives line moves; file-level heuristics do not. Blame per finding is cheap (findings number in the dozens). A line not yet committed has no blame commit and counts as introduced after the round-1 head — churn on a re-review round.

Without `--round1-head` (first round, or the record is unavailable): every non-pre-existing finding is `feature`; skip churn diagnostics.

What the mark does:

1. Every verdict finding carries its origin.
2. The review header states the ratio: `6 findings: 1 feature, 5 churn`.
3. **Convergence rule**: churn in the majority for two consecutive rounds (the prior round's ratio comes from its review record, passed in the invocation context by the caller) means the review must OPEN with a process recommendation — "the loop is reviewing its own output; recommend freezing the guard surface or splitting it to its own branch" — before any NOT LGTM. The operator decides; the reviewer reports the regime.

**The mark never touches verdict logic.** Severity and blocking are computed blind to origin; the label exists only in the header diagnostics. A bug in review-added code is a bug and blocks — "it came from review, so it's not a bug" is not derivable anywhere. A fix to feature code made during the gate is churn by mechanics, and that is correct semantics (second-generation work); that is why the trigger is majority-for-two-rounds, not mere presence.

A majority-churn state has exactly three legal exits, none of which skips a bug:

1. **Fix and continue** — the default; findings block as usual.
2. **Carve out** — the churn-generating code moves to its own branch together with its open findings, which become that branch's starting backlog; that branch gets its own gate before it can merge. The bug is not forgiven; it moved with its carrier.
3. **Delete** — the review-added code is removed entirely and its findings close as "code removed" (verified removed, not "won't fix"). No carrier, no bug to ship.

Explicitly illegal: merging with an open churn finding in code that remains in the PR. Backstop the mark never touches: the terminal gate condition is LGTM on the final tree, computed origin-blind — for the final reviewer the churn category does not exist. Labels influence the route, never the exit check.

<if --ticket>
### Ticket compliance

Compare the changes against the ticket requirements:

- **Completeness**: Do the changes fully implement what the ticket describes? List each requirement/acceptance criterion and whether it is addressed
- **Scope creep**: Are there changes that go beyond what the ticket asks for? Flag them (not necessarily blocking, but worth noting)
- **Missing pieces**: Are there requirements from the ticket that are NOT addressed by the changes? These are blocking issues
- **Intent match**: Does the implementation approach match the spirit of the ticket, or does it solve a different problem?

Ticket compliance issues are blocking (NOT LGTM) when requirements are missing or the implementation contradicts the ticket.
</if>

<if --nitpick>
Pedantic mode: include style nitpicks, naming suggestions, minor improvements. Leave no stone unturned.
</if>

<if not --nitpick>
Be direct. If something is fine, don't mention it. Focus on what matters, skip nitpicks.
</if>

## Output format

Open with the review header, in this order:

1. If the convergence rule fired (churn majority for two consecutive rounds): the process recommendation line FIRST, before the verdict.
2. The verdict: **LGTM** or **NOT LGTM**.
3. The review record: `Reviewed <REVIEW_BRANCH> at <REVIEW_HEAD> against <target-branch>`.
4. When churn diagnostics are on: the origin ratio, e.g. `6 findings: 1 feature, 5 churn (+ 2 outside this diff)`.

Verdict semantics:

- **NOT LGTM** — at least one verdict finding is open: a defect the diff introduced, worsened, or interacts with (bugs, logic errors, security issues, regressions, error-handling gaps, comments-as-fixes, docs the diff made wrong), missing tests for changed logic in a tested area, or missing `--ticket` requirements when `--ticket` was provided.
- **LGTM** — no open verdict findings. **LGTM is compatible with a non-empty "Recommended" list** (naming, style, minor improvements, suggestions) and with a non-empty "Found outside this diff" section. When every finding is either recommended or outside the diff, the verdict is LGTM.

Then two sections, same quality bar, same evidence discipline:

### Verdict findings

Findings attributed to the diff (introduced / worsened / interacts with), written as free-form text like a human reviewer would write. Only these decide the verdict. Each carries its origin mark when churn diagnostics are on. Non-blocking suggestions go under a **Recommended** subheading here — they do not flip the verdict.

### Found outside this diff

Everything discovered that already existed at the merge base, with full severity — a security hole found here is still reported as a security hole. Nothing is dropped; it is just not held hostage by this PR. When this section is non-empty, end it with the operator obligation: the gate is not closed until every finding here has a home — a filed issue, a parked branch, or a project-memory entry.

<if --ticket>
Include a **Ticket Compliance** section after the main review with:
- Ticket reference (title + link/ID)
- Checklist of ticket requirements with status (done / not done / partially done)
- Overall verdict: "All requirements met" or "Missing requirements: ..."
</if>

Close with a short reminder of the three routing rules (adapt the wording to context; do not inflate it):

- Attribution decides the section: the diff owns what it changed and what its changes interact with — nothing more, nothing less.
- The remedy lives in the defect's layer: changed logic gets a test in the existing surface, prose gets the fix itself, and a new guard or checker is never a merge condition.
- Outside findings need homes: a filed issue, a parked branch, or a memory entry — before the gate closes, not before this PR merges.
