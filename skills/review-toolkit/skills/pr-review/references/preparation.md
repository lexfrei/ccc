# Preparation, readiness gate, base-merge short path

Read in Step 0. Nothing here may print the PR title or body, the head branch name or commit subjects before Step 1: keep `gh pr view` to the `--json` fields shown, and keep git quiet. Never `checkout` or `reset` in the user's repository; work in the worktree this file creates.

## Pin the head

With no PR number given, take it from `gh pr view --json number --jq .number`; with none for the current branch, report it and stop.

```bash
git fetch --quiet origin
PR_BASE=$(gh pr view $PR_NUMBER --json baseRefName --jq .baseRefName)
PR_HEAD_SHA=$(gh pr view $PR_NUMBER --json headRefOid --jq .headRefOid)
PR_IS_FORK=$(gh pr view $PR_NUMBER --json isCrossRepository --jq .isCrossRepository)
# The base repo serves every PR head at pull/<N>/head, fork or not
git fetch --quiet origin "+pull/$PR_NUMBER/head:refs/pr-review/$PR_NUMBER"
test "$(git rev-parse "refs/pr-review/$PR_NUMBER")" = "$PR_HEAD_SHA" || { echo "PR head mismatch"; exit 1; }
PR_TMP=$(mktemp -d); PR_WORKTREE="$PR_TMP/pr-$PR_NUMBER"
git worktree add --quiet --detach "$PR_WORKTREE" "$PR_HEAD_SHA"
gh api --paginate "repos/{owner}/{repo}/pulls/$PR_NUMBER/files" --jq '.[].filename'
echo "PR_NUMBER=$PR_NUMBER PR_BASE=$PR_BASE PR_HEAD_SHA=$PR_HEAD_SHA PR_IS_FORK=$PR_IS_FORK PR_TMP=$PR_TMP PR_WORKTREE=$PR_WORKTREE"
```

Shell state does not survive between tool calls: every later step substitutes the literal values from that `echo` line for these variables.

A head mismatch means a push landed in between, or `origin` is not the base repository: re-read once, stop if it persists. Always diff against `origin/<base>`, never a local branch: a stale local base produces phantom diffs. When the local `git diff --stat` and the API file list disagree, trust the API and find out why before going on.

When the run ends, in every mode: `git worktree remove --force "$PR_WORKTREE"`, `git update-ref -d "refs/pr-review/$PR_NUMBER"`, `rm -r "$PR_TMP"`.

## Readiness gate

```bash
gh pr view $PR_NUMBER --json mergeable,mergeStateStatus
gh pr view $PR_NUMBER --json statusCheckRollup --jq '.statusCheckRollup[] | {name: (.name // .context), status, conclusion: (.conclusion // .state)}'
gh pr checks $PR_NUMBER --required --json name,bucket
gh api --paginate "repos/{owner}/{repo}/actions/runs?head_sha=$PR_HEAD_SHA&status=action_required" --jq '.workflow_runs[] | {id, name}'
```

`UNKNOWN` merge state means GitHub has not computed it: re-query once. List every `action_required` run in the draft; a new head, a base merge included, starts its runs over.

**Conflicts.** GitHub's merge state lags. Confirm locally: `git merge-tree --write-tree "origin/$PR_BASE" "$PR_HEAD_SHA"; echo "exit $?"`. Exit 1 with a `CONFLICT` line confirms the conflict; exit 1 without one, or any status other than 0 and 1, is an error to report, not a verdict. Exit 0 means GitHub is stale: continue, and an LGTM cannot go out as `APPROVE` until GitHub clears.

**Red checks.** Only `FAILURE`, `TIMED_OUT`, `ERROR`, `STARTUP_FAILURE` (or a status context in `FAILURE`/`ERROR`) are red. Pending, `ACTION_REQUIRED`, `NEUTRAL`, `SKIPPED` and `CANCELLED` are not. A red check is code-related when the diff could plausibly cause it (build, tests, lint, vet, schema, generated-code drift); when you cannot tell, treat it as code-related. Missing fork secrets, a flaky external service or a label bot are not, and do not gate. Read a CI log only for a red code-related check, to decide whether the gate stops the review: a log can carry commit subjects and the branch name.

A code-related red check leaves the gate on evidence only:

- the diff provably cannot reach the failing step (it failed before anything the diff changes ran, or its input renders byte-identical): propose one rerun;
- the base is stale and the failure matches what the base has since changed: propose a sync;
- a rule the base added under the PR: the commit on `origin/<base>` that introduced or tightened the rule, named by SHA, and proof the offending lines were in the PR before that commit reached the base (an earlier green run of the same check on a head that already had them). Then run the full review, never the short path. If the PR breaks the real invariant, that is a finding against the diff; if the rule is stricter than the invariant, the defect is in the base: draft a tracking issue for it, ask nothing of the author, and while the check is required an LGTM goes out as `COMMENT` naming the issue.

Reruns and syncs run only at publication, per `maintainer-actions.md`, so an LGTM on the current head goes out as `COMMENT` naming the pending run.

**Gate mode.** A confirmed conflict or a code-related red check that did not leave the gate stops the review here: no Step 1 to 4, no `--ticket` compliance. The deliverable is a short note without a verdict word: what blocks (the conflict, the named checks, for a red check the evidence still missing), the ask (resolve, fix, re-request review), and nothing about the rest of the code. A log pointing at a changed line is a lead, not a cause. Only when the failure is a blocker under (a) of the Step 5 rule does the note open with `NOT LGTM` and publish as `REQUEST_CHANGES`; otherwise it publishes as a `COMMENT`. A reviewer with write access proposes the sync for a conflict with one obvious mechanical answer instead of asking the author.

## Base-merge short path

On a re-review, `PRIOR_SHA` is the head of your latest verdict, and only when that verdict is LGTM. A `NOT LGTM`, a reply in a thread, or a gate note never qualifies; an approval dismissed by a push still does, and only then: its `review_dismissed` timeline event carries a `dismissal_commit_id`, the commit that dismissed it; a dismissal without one is not counted. When the user names the head of an earlier unpublished verdict, set `PRIOR` to `none <that SHA>`, which leaves `PRIOR_AT` empty; with no published LGTM and no named head there is no short path.

```bash
ME=$(gh api user --jq .login)
TL=$(gh api --paginate --slurp "repos/{owner}/{repo}/issues/$PR_NUMBER/timeline")
AUTO=$(jq -c '[.[][] | select(.event == "review_dismissed" and ((.dismissed_review.dismissal_commit_id // "") != "")) | .dismissed_review.review_id | tostring]' <<<"$TL")
PRIOR=$(gh api --paginate --slurp "repos/{owner}/{repo}/pulls/$PR_NUMBER/reviews" | jq -r --arg me "$ME" --argjson auto "$AUTO" '[.[][] | select(.user.login == $me) | select(.state == "APPROVED" or .state == "CHANGES_REQUESTED" or ((.state == "COMMENTED" or .state == "DISMISSED") and ((.body // "") | test("^(NOT )?LGTM"))))] | last // empty | select(.state != "DISMISSED" or ((.id | tostring) as $i | any($auto[]; . == $i))) | select(.state == "APPROVED" or ((.body // "") | test("^LGTM"))) | "\(.id) \(.commit_id) \(.submitted_at)"')
read -r PRIOR_ID PRIOR_SHA PRIOR_AT <<<"$PRIOR"
RETARGETS=$(jq --arg t "$PRIOR_AT" '[.[][] | select(.event == "base_ref_changed" and .created_at > $t)] | length' <<<"$TL")
git fetch --quiet origin "$PRIOR_SHA" 2>/dev/null
[ -n "$PRIOR_SHA" ] && [ "$RETARGETS" = 0 ] &&
  mb=$(git merge-base "origin/$PR_BASE" "$PR_HEAD_SHA") &&
  expected=$(git merge-tree --write-tree "$mb" "$PRIOR_SHA") &&
  [ "$expected" = "$(git rev-parse "$PR_HEAD_SHA^{tree}")" ] &&
  echo "own diff unchanged" || echo "full review"
echo "PRIOR_ID=$PRIOR_ID PRIOR_SHA=$PRIOR_SHA"
```

Trees are compared, not diffs: a diff misses a moved line and a changed binary. Every failure path prints `full review`. With an empty `PRIOR_AT` the retarget check sees the whole history, so any retarget forces a full review.

On `own diff unchanged`, run the readiness gate on the new head and go to Step 5. Whether the earlier LGTM waited for an owner's decision is decided by one command on that same review, with the literal `PRIOR_ID` from the `echo` line: `B=$(gh api "repos/{owner}/{repo}/pulls/$PR_NUMBER/reviews/<PRIOR_ID>" --jq '.body') || { echo "lookup failed"; exit 1; }; grep -q "^Waits for an owner's decision: " <<<"$B" && echo "owner wait" || echo "no wait"`. On `lookup failed`, run the full review. With `PRIOR_ID` `none` there is no recorded wait; a card still waiting in the conversation counts the same. On `owner wait` the wait carries over: without the owner's answer (Step 3 of `SKILL.md` says where it comes from) the event stays `COMMENT` and its body repeats the same lines; with the answer, run the full review. A red check traced to a rule the base added under the PR cancels the short path. The body says the diff is unchanged since the review at `PRIOR_SHA` and that the earlier verdict stands on that basis alone; it does not present anything as re-verified.

## Signs

Last, note which signs of Step 3 the diff shows; that list closes Step 0.

## Contract files

For Step 2: the files that state the project's contract, each read with `git show "origin/$PR_BASE:<path>"`, so the PR cannot rewrite the rules it is judged by.

```bash
git ls-tree -r --name-only "origin/$PR_BASE" | grep -iE '(^|/)(contributing|agents|claude)[^/]*\.(md|rst|adoc|txt)$|copilot-instructions|pull_request_template'
git show "origin/$PR_BASE:<entry file>" | grep -oE '\]\([^)]+\)'
```

The first command finds only entry files. Read every document they route to whose stated scope or condition covers the changed paths, at the base branch too, and follow its routes the same way; the second command lists an entry file's markdown links, relative to its directory.

## Owners

For the card: the owners the project names for the changed paths, at the base branch.

```bash
for f in CODEOWNERS .github/CODEOWNERS docs/CODEOWNERS; do git show "origin/$PR_BASE:$f" 2>/dev/null; done
```

For each changed path the last matching pattern wins. An owners list the contract names for an area (API owners, maintainers of a subsystem) counts the same. The card is addressed to the named owners other than the user running the review and the PR's author. A team counts through its members other than the user and the author, and a team with no such member names no one (`gh api --paginate orgs/<org>/teams/<slug>/members --jq '.[].login'` lists them; without access, treat the team as unresolved and say so in the draft). Where the project names no one else, the owner is the user, or whom the user names, and only then does the user's own `--owner-answer` count. An owners list kept in CI configuration (an API-review gate, for example) is found only through a pointer in the contract, so look for one.
