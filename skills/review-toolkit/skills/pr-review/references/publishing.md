# Drafting and publishing

Read in Step 5.

## Verdict and event

| Verdict | Merge state | Event |
| --- | --- | --- |
| `LGTM` | mergeable now: every required check green on the exact head, GitHub's merge state clean or blocked only by the approval this review would give, no independent prerequisite open | `APPROVE` |
| `LGTM` | not mergeable now: a required check pending, or red for a reason outside the diff; GitHub still `DIRTY` after a clean local merge; a companion PR, a pending rerun or sync, an owner's answer to a card, or maintainer-side setup still open | `COMMENT`, the body naming what the merge waits for; for a card, one line per owner it waits for, right after the verdict line, exactly `Waits for an owner's decision: @<owner>`, and nothing of the card's content |
| `NOT LGTM` | any | `REQUEST_CHANGES` |

`APPROVE` means "this can merge now": branch protection counts it the moment the blocking condition clears, so there is no approve-with-hold. The one exception is a real stack, a PR based on its parent's branch, approved while it waits only for that parent. A `COMMENT` carries a verdict word only in the merge-state row; without a verdict it is the gate note of `preparation.md`, or a review that cannot reach a verdict, whose body says what is missing.

## Body and inline comments

Each finding is one item, readable in thirty seconds: what is wrong, in one sentence that carries the mechanism; where (`file:line`, a commit, a check name); the fix. Optional notes are marked `(non-blocking)`. No narration of what was checked, no praise, no AI attribution, no names of tools or skills, no private infrastructure, English only.

A finding on a line that exists in the PR diff goes into an inline comment on that line and nowhere else. The body holds the verdict sentence and the items without a diff line: commit messages, the PR body, CI, code outside the diff. When every finding went inline, the body is the verdict line alone.

```text
<LGTM | NOT LGTM> — <one-sentence why>

1. <what, with the mechanism> — <where>. Fix: <action>.

<with --ticket:>
## Ticket Compliance
- [done|partial|missing] <requirement>
```

A card is never part of the body; it reaches its owner as Card delivery below says. Tracking issues (a rule the base must fix, a defect found outside the diff) are drafted with title, target repository and body, and filed only on approval; their URLs go into the body.

## Card delivery

Applies when an owner of the card is someone other than the user. Without `--publish`, the draft shows the card ready to forward and names each owner it goes to. With `--publish`, once the user approves the card text like any other public text, write it to `<PR_TMP>/card.md`, check right before posting that the PR head is still the pinned SHA (restart the review if it moved), and post it before the review with `gh pr comment $PR_NUMBER --body-file "$PR_TMP/card.md"`. Its first line is `@<owner>` once per owner followed by `question for the owner, not a request to the author:`, then the five lines, and nothing from the verdict or the review. Then publish the review for `sound` as below, and nothing else for `doubt`.

The owner's answer to the card counts the same as `--owner-answer`. In a later run, first find the card and its time: `gh api --paginate --slurp "repos/{owner}/{repo}/issues/$PR_NUMBER/comments" | jq -r --arg me "$(gh api user --jq .login)" '[.[][] | select(.user.login == $me and (.body | contains("question for the owner, not a request to the author:")))] | last | .created_at // "none"'`. With `none` there is no card and no answer. Otherwise read what each owner posted after that time, both PR comments and review bodies: `gh api --paginate --slurp "repos/{owner}/{repo}/issues/$PR_NUMBER/comments" | jq -r --arg t "<CARD_AT>" '.[][] | select(.created_at > $t) | "\(.user.login): \(.body)"'` and the same over `pulls/$PR_NUMBER/reviews` with `.submitted_at`. Only a reply that addresses the card counts; anything else from the owner is not an answer. With several owners, or a team counted through its members, any refusal stands as a refusal and an acceptance needs at least one owner's yes and no owner's no.

## Prior reviews

```bash
ME=$(gh api user --jq .login)
MY_REVIEWS=$(gh api --paginate --slurp "repos/{owner}/{repo}/pulls/$PR_NUMBER/reviews" | jq -c --arg me "$ME" '[.[][] | select(.user.login == $me) | select(.state != "DISMISSED")]')
EFFECTIVE_VERDICT=$(jq -r '[.[] | select(.state == "APPROVED" or .state == "CHANGES_REQUESTED")] | last | .state // empty' <<<"$MY_REVIEWS")
```

`--paginate --slurp` keeps a PR with more than thirty reviews from truncating to page one; `gh api` rejects `--slurp` with `--jq`, hence the separate `jq`. A `COMMENT` never dismisses an earlier `APPROVED` or `CHANGES_REQUESTED`, and that state can sit several reviews back. When this run publishes a `COMMENT` over a non-empty `EFFECTIVE_VERDICT`, tell the user the old state still counts; do not dismiss it silently.

## Publish

Approved maintainer actions run first, per `maintainer-actions.md`. Then write the payload to a file with `json.dump`, never through stdin or shell quoting: a hook that inspects outgoing text reads the file named by `--input`.

```python
import json
review = {
    "commit_id": "<full 40-character PR_HEAD_SHA the review was computed on, never a head a sync produced>",
    "event": "APPROVE | REQUEST_CHANGES | COMMENT",
    "body": "<body>",
    "comments": [{"path": "path/to/file", "line": 42, "side": "RIGHT", "body": "<item>"}],
}
with open("<PR_TMP>/review.json", "w") as f:
    json.dump(review, f)
```

```bash
test "$(gh pr view $PR_NUMBER --json headRefOid --jq .headRefOid)" = "$PR_HEAD_SHA" || { echo "head moved"; exit 1; }
gh api "repos/{owner}/{repo}/pulls/$PR_NUMBER/reviews" --method POST --input "$PR_TMP/review.json" --jq '{id, html_url, commit_id}'
gh api "repos/{owner}/{repo}/pulls/$PR_NUMBER/reviews/<id>" --jq '.body, .state, .commit_id'
gh api --paginate "repos/{owner}/{repo}/pulls/$PR_NUMBER/reviews/<id>/comments" --jq '.[] | {path, line, body}'
```

If the head moved since Step 0, publish nothing and start again from Step 0. Read the published review back and compare body, state, commit and inline comments with the approved draft; a mismatch is reported, not patched over. Always POST a new review, never `PUT` a published one: a submitted review is a dated statement someone may have read, and the endpoint cannot change its event.
