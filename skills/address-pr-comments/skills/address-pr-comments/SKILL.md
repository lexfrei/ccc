---
name: address-pr-comments
description: End-to-end closeout of unresolved review comments across one or more GitHub PRs. For each PR checks out the branch, fetches unresolved threads, verifies against current code, fixes legitimate findings (one signed-off commit + push per thread), asks approval on reply drafts, posts replies, then moves to the next PR. Returns to the original branch at the end.
argument-hint: "[PR number or owner/repo#N] [more PRs...]"
---

**CRITICAL**: This skill makes PUBLIC changes — commits pushed to the PR branch and replies visible to the PR author, reviewers, and all watchers. Every commit must follow project conventions (signed off, GPG-signed where configured, conventional message). Every reply must be accurate, justified, and in English.

## Arguments

Parse `$ARGUMENTS` as a space-separated list of PR refs.

- Each ref: bare number (e.g. `2395`, uses the repo from `gh repo view --json owner,name`) OR `owner/repo#N` (e.g. `cozystack/cozystack#2395`).
- If no args: fall back to detection from the current branch via `gh pr view --json number,headRepositoryOwner,headRepository --jq '.headRepositoryOwner.login + "/" + .headRepository.name + "#" + (.number|tostring)'` — single-PR mode.
- If no args and no PR can be inferred: report the error and stop.

Normalize each ref into `OWNER`, `REPO`, `PR_NUMBER`.

## Step 0: Record the starting state

Before touching any PR branch:

```bash
ORIGINAL_REF=$(git symbolic-ref --quiet --short HEAD || git rev-parse HEAD)
if [ -z "$(git status --porcelain)" ]; then CLEAN_START=1; else CLEAN_START=0; fi
```

- `ORIGINAL_REF` is the branch to return to at the end.
- `CLEAN_START == 1` means the working tree was clean — safe to restore later.
- If the working tree is dirty, ask the user how to handle it (abort, stash, or proceed without final restore) BEFORE doing any `git checkout`.

## Step 1: Outer loop over PR refs

For each PR ref in the parsed list, execute Steps 2–10 in order. Between PRs, print a visible separator (e.g. `────── PR #N ──────`) so progress is easy to follow.

On a per-PR unrecoverable error (PR not found, branch push rejected and user chose not to force, etc.): print the error, skip the remaining steps for that PR, continue with the next ref. Do not abort the whole run.

## Step 2: Check out the PR branch

```bash
PR_BRANCH=$(gh pr view $PR_NUMBER --repo $OWNER/$REPO --json headRefName --jq .headRefName)
git fetch origin "$PR_BRANCH"
git checkout "$PR_BRANCH"
git log --oneline -5
```

**Worktree guard**: if `git checkout` fails with `fatal: '<branch>' is already used by worktree at <path>`, parse the path, `cd` into that worktree, and run the rest of the PR's steps there. Do not delete or force anything.

## Step 3: Read project agent docs

Scan the repo for agent-facing contribution rules and follow them exactly. Common locations:

- `AGENTS.md`, `docs/agents/contributing.md`, `docs/agents/*.md`
- `CONTRIBUTING.md` (look for "review comments" / "AI bot" / "commit format" sections)

Project rules OVERRIDE this skill's defaults — e.g. commit message format, reply etiquette, threads to ignore, whether a separate commit per thread is required.

## Step 4: Fetch unresolved review threads

Use GraphQL — REST does not expose `isResolved`. Capture `threadId` (needed for replies) and the diff position fields.

```bash
gh api graphql -F owner="$OWNER" -F repo="$REPO" -F pr=$PR_NUMBER -f query='
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          comments(first: 100) {
            nodes {
              id
              path
              line
              originalLine
              author { login }
              bodyText
              url
              createdAt
            }
          }
        }
      }
    }
  }
}' --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)'
```

Also fetch top-level issue comments for bot summaries:

```bash
gh api "repos/$OWNER/$REPO/issues/$PR_NUMBER/comments" --jq '.[] | {id, author: .user.login, body, url}'
```

For each unresolved thread, record: `threadId`, `path`, `line` (or `originalLine` when `line` is null), `author.login`, `bodyText`, `url`, and `isOutdated`.

**Pagination guard**: if the query returns exactly 100 review threads or any thread has exactly 100 comments, the data was truncated. Either paginate via `pageInfo.hasNextPage`/`endCursor` or warn the user and ask whether to proceed on partial data.

## Step 5: Verify each thread against CURRENT code

**MANDATORY — do not skip.** Reviewer bots hallucinate. Code often evolved after a comment was posted. Blindly applying suggestions or replying "fixed" without checking damages trust.

For each thread:

1. Read the file at the referenced path and line in the current working tree. If `line` is null (outdated), use `originalLine` as a starting point and locate the relevant code by context.
2. Trace the claim — find the code path that proves or disproves the concern.
3. Check whether the issue is already fixed by a later commit on the branch.
4. Check project conventions (agent docs, CONTRIBUTING.md, existing patterns). A suggestion that violates project style should NOT be applied.

Assign one verdict per thread:

- **FIX** — legitimate issue, fix is clear and aligned with project conventions.
- **ALREADY FIXED** — the code already handles it; reply confirms and points to the relevant lines.
- **WONTFIX** — the reviewer's premise is wrong OR the trade-off was intentional OR the suggestion contradicts a documented decision. The reply must explain why.
- **DEFER** — valid point but out of scope for this PR. The reply acknowledges and links to a follow-up if one exists.
- **ASK** — verdict is non-obvious: the suggestion is a judgment call, reasonable people disagree, the trade-off isn't clear-cut, or the fix would touch something sensitive (public API, migrations, performance-critical path, stylistic preference without project precedent). Do NOT pick FIX/WONTFIX unilaterally in these cases.

For every **ASK** thread: pause before Step 6 and ask the user via `AskUserQuestion` — present the thread (author + quote), your evidence, and the candidate verdicts. Let the user decide. Proceed only after the user's answer.

Keep an internal table of `(threadId, verdict, evidence)` — the user will see it during the approval step.

## Step 6: Apply fix + commit + push, PER THREAD

For each `FIX` verdict, in the order threads were fetched:

1. **Edit** the file(s) needed to address THIS one thread only.
2. **Fast checks**: if the project has a fast command (`go build ./...`, `tsc --noEmit`, `cargo check`, `markdownlint`, etc.), run it. Run relevant tests if they are cheap.
3. **Stage** only the files touched for this thread: `git add <paths>`.
4. **Commit** with project conventions discovered in Step 3. Default template when the project uses Conventional Commits:

   ```text
   <type>(<scope>): <short summary tied to the thread>

   Address review feedback from <author.login> on <path>:<line>:
   <one-sentence description of the fix>
   ```

   Use `git commit --signoff` with full-flag form. If the repository has GPG signing configured, respect it — NEVER pass `--no-gpg-sign` or otherwise bypass signing. If signing prompts for a PIN, WAIT for the user rather than working around it.
5. **Push** immediately: `git push origin <branch>`. If the push is rejected (branch diverged, non-fast-forward), stop this PR, report the error, and ask the user how to proceed (rebase, force-push, or skip). Do not force-push without explicit approval.
6. **Record the commit SHA** returned by `git rev-parse HEAD` — the reply draft will reference it.

For `ALREADY FIXED`, `WONTFIX`, `DEFER`: no commit, no push — only a reply draft.

If commit or push fails in a way that cannot be recovered (signing timeout, conflict, rejected push with user declining a fix): print a clear error and skip to the next PR.

## Step 7: Draft replies

One reply per thread. Rules:

- **English only.** Public content on GitHub must be in English regardless of chat language.
- **Be specific.** Reference the actual function / line / mechanism (e.g. `ConvertHelmReleaseToApplicationWithMonitor`, not "the conversion function").
- **FIX replies**: state what was changed and how it addresses the concern, and include the commit SHA recorded in Step 6 (short form, e.g. `90a9d6e9`). One short paragraph.
- **ALREADY FIXED**: point to the existing code that handles it (file + function name).
- **WONTFIX**: explain the reason succinctly and link to the documented rationale if present. Be respectful.
- **DEFER**: acknowledge, explain why it is not in this PR, reference a follow-up if one exists.
- **No AI attribution.** Do not say "AI reviewer", "Claude", "bot", "automated agent", etc. Replies read as the user.
- **No internal tool names.** No slash-command names, skill names, or workflow shorthand.
- **No private infrastructure details.** No cluster names, client names, internal IPs, or ticket IDs.
- **Keep it short.** 2–4 sentences is usually right. Long replies invite bikeshedding.

## Step 8: Present drafts for approval (MANDATORY, after commit+push)

Show the user, in a single message:

1. A summary table — thread index, file:line, author, verdict, commit SHA (if FIX).
2. The full draft reply for each thread.
3. `git log <base>..HEAD --oneline` showing the commits just pushed.
4. Any threads dropped (never-applied) and why.

Ask explicitly: "Post all replies for PR #N?". Wait for confirmation. If the user asks for changes to specific drafts, edit only those and re-present before posting.

Commits have already been pushed by this point — the approval gate is specifically for the public reply text.

## Step 9: Post replies via GraphQL

Use `addPullRequestReviewThreadReply` — it keeps each reply attached to the correct thread. Write each reply body to a temp file first to avoid shell-escaping issues:

```bash
cat > /tmp/reply.txt << 'EOF'
<reply body — EOF-quoted so no interpolation>
EOF

gh api graphql \
  -f threadId="<PRRT_…>" \
  -F body="@/tmp/reply.txt" \
  -f query='
mutation($threadId: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $threadId, body: $body}) {
    comment { url }
  }
}' --jq '.data.addPullRequestReviewThreadReply.comment.url'

rm -f /tmp/reply.txt
```

Post replies sequentially (not in parallel — parallel posts can race and hit rate limits). Collect the returned URLs for the final report.

## Step 10: End-of-PR summary

Print for this PR:

- Counts: FIX / ALREADY FIXED / WONTFIX / DEFER / ASK.
- Commits pushed (SHA + one-line subject).
- Reply URLs (numbered).
- Any errors encountered.

Then proceed to the next PR ref (back to Step 2).

## Step 11: Restore the original ref

After the final PR:

```bash
if [ "$CLEAN_START" = "1" ]; then
  git checkout "$ORIGINAL_REF"
else
  echo "Staying on current branch — working tree was dirty at start."
fi
```

Print the multi-PR final summary: one block per PR with its counts, pushed commits, and reply URLs. Close with a reminder of the current branch.

Do not resolve threads automatically. The reviewer (human or bot) decides whether a thread is resolved based on the reply and pushed commits.

## Hard rules

- **Commits are mandatory for FIX threads** — one commit per thread, signed off, signed with GPG where configured, project-conventional message, pushed to the PR branch. No uncommitted leftovers.
- **Never bypass signing.** If GPG signing is configured, respect it. Do not pass `--no-gpg-sign` or disable `commit.gpgsign`. If signing prompts for a PIN, WAIT — do not work around it.
- **Approval gate before public replies.** Commits are auto-pushed, but reply comments REQUIRE user approval before posting.
- **Language**: replies are ALWAYS English. Chat with the user is in whatever language the user uses.
- **Verify before replying**: never post "fixed" without checking that the fix is in place AND pushed.
- **No blind apply**: evaluate every suggestion. A reviewer bot proposing the wrong pattern must get a WONTFIX reply with reasoning — not a lazy apply or a silent dismissal.
- **Ask when uncertain**: if the verdict is a judgment call or the fix touches something sensitive, use `AskUserQuestion` before committing anything. Do not guess on contested threads.
- **No thread resolution**: do not call `resolveReviewThread`. That is the reviewer's prerogative.
- **Show evidence**: the user must be able to audit any thread quickly from the approval message.
- **Return to the original branch** at the end when safe (working tree was clean at start).
