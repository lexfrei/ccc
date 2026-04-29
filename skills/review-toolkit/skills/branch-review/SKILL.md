---
name: branch-review
description: Review current branch changes in isolation. Output starts with LGTM verdict — if no LGTM, the code is not ready to merge. IMPORTANT — always pass all flags you already know from context (target branch, project type, ticket, etc.). Do not rely on auto-detection when the answer is known. Pass --target to set which branch the changes are going INTO. Pass --ticket with a URL or ID to validate against requirements.
argument-hint: "[path] [--target branch] [--nitpick] [--type go|node|python|rust] [--exclude pattern,pattern] [--ticket URL|ID]"
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

**Print the resolved target branch** so the user can verify it is correct (e.g. "Reviewing against target branch: `next`").

**Decide whether a worktree is needed.** Compare `REVIEW_BRANCH` to the branch being reviewed:

- If a path argument was provided: trust it, no worktree.
- Else if `REVIEW_BRANCH` matches the branch to review: analyze in place, no worktree.
- Else (active branch is different — typical when cascaded from `/pr-review`): create a worktree at the branch to review per the worktree block in the CRITICAL section above. From this point on, `<path>` refers to that worktree path. Cleanup runs via the `trap` on exit.

Find the merge base (the point where the branch being reviewed diverged from the target):

```bash
MERGE_BASE=$(git -C <path> merge-base $REVIEW_BRANCH <target-branch>)
```

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
- Tests coverage (if applicable)
- Where issues are found: suggest specific tests that would prove/demonstrate the problem exists (e.g. "a test that calls X with empty input would expose this nil pointer")
- Adjacent issues: if you find a problem, look at the surrounding code in the same area. If there are related issues nearby that are worth fixing in the same PR, flag them (not a full codebase audit — just the neighborhood of the changes)
- No "pre-existing" excuse: if a problem is mentioned in the review, it IS the review's problem. There is no such thing as "pre-existing issue, out of scope." If you see it, if it affects the code being changed, if it's in the neighborhood of the diff — it blocks. The PR touched this area, the PR owns fixing it. Do not dismiss issues as "already existed before this PR"
- Comments as fixes: if a change "addresses" a problem by adding a comment (TODO, FIXME, HACK, explanatory note, warning comment) instead of actually fixing the code — this is NOT a fix. Flag it explicitly: a comment documents a known problem but does not solve it. Nobody reads comments in the heat of the moment, and the problem will bite someone eventually. The actual code must be changed. This is always a blocking issue (NOT LGTM)
- Documentation accuracy: if the project has ANY documentation (README, DESIGN.md, docs/, inline doc comments, Helm values descriptions, CLAUDE.md, etc.), it MUST be verified against the actual code — regardless of whether the PR touches documentation or not. Stale, misleading, or contradictory documentation is a blocking issue. Specifically check: documented APIs/flags/config match the implementation, examples actually work with the current code, no references to removed or renamed entities, version numbers and defaults match reality. If the PR changes behavior but existing documentation still describes the old behavior — blocking. If existing documentation was already wrong before this PR but describes the area being changed — also blocking (the PR touched this area, the PR owns fixing the docs)

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
Pedantic mode: include style nitpicks, naming suggestions, minor improvements.
Leave no stone unturned.
</if>

<if not --nitpick>
Be direct. If something is fine, don't mention it.
Focus on what matters, skip nitpicks.
</if>

## Output format

Start your review with one of:

- **LGTM** — code is correct, safe, clear, and well-tested. May have minor cosmetic notes (listed as recommendations, not blockers)
- **NOT LGTM** — there are issues that must be addressed before merging

LGTM is a high bar. It means: no bugs, no security issues, no missing error handling, no logic gaps, no untested paths. The ONLY things allowed to pass with LGTM are cosmetic issues (naming style, minor formatting) — and even those must be listed as "Recommended to fix" in the review. Everything else blocks. When in doubt, do not LGTM.

Then provide the review as free-form text, like a human reviewer would write.

<if --ticket>
Include a **Ticket Compliance** section after the main review with:
- Ticket reference (title + link/ID)
- Checklist of ticket requirements with status (done / not done / partially done)
- Overall verdict: "All requirements met" or "Missing requirements: ..."
</if>

End every review with this reminder (verbatim):

> **Reminder:** "Pre-existing" is not a thing. If a problem is flagged in this review, it must be fixed in this PR — no exceptions.
>
> **Every issue listed above must have a corresponding test.** No matter the severity — bug, logic error, security issue, error handling gap, documentation drift — each one must be covered by a test that fails without the fix and passes with it. Untested fixes are not fixes.
