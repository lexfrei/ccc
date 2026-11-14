# Maintainer actions around a review

Applies when the reviewer has write access to the repository and to the PR branch (for a fork, the PR allows maintainer edits). Each action below is a write to someone else's branch or to the CI system: in this skill it is listed in the Step 8 draft and runs only in Step 9, after the user approved it.

## Mechanical branch sync

Never ask the author for a purely mechanical rebase, base sync, or history cleanup (dropping superseded commits, an empty commit GitHub inserted). Do it yourself:

1. Locally, in a worktree, with your own signed commits and `--signoff`. Never the server-side "Update branch" button or `gh pr update-branch`: both create commits without your signature.
2. Before pushing, check that `git rev-parse HEAD^{tree}` equals the first line of `git merge-tree --write-tree origin/<base> refs/pr-review/<N>`. A fork's branch is not on origin; the PR head ref from Step 1 is. A difference means the sync changed content and is no longer mechanical.
3. Push with `--force-with-lease=<branch>:<old head sha>` after a rebase, plain push after a merge of the base.
4. Verify `git range-diff` shows the author's commits as `=`, and that the new commits are signed and signed off.
5. Tell the author the branch was updated.

When a conflict needs a decision about code or prose, stop and ask the author; a maintainer resolves only conflicts with one obvious mechanical answer.

## Fork CI awaiting approval

Approve `action_required` runs (`POST /repos/{owner}/{repo}/actions/runs/{id}/approve`) only after reading the diff of the exact head those runs belong to, and only when the PR touches none of: CI workflow files, root build files, scripts that CI executes, the privileged e2e harness. When it does, or anything in the diff reaches for the network, secrets, or obfuscated content, ask the human. A new head needs a new read before a new approval.

Do not approve old `action_required` runs on a stale base: a run built from an old merge ref can fail on drift that is not the PR's fault. Sync the branch first (above), then approve the fresh runs on the new head.

## Stacked PRs after a parent merges

Merging the parent of a native GitHub stack retargets and rewrites every child branch. For each child, check:

1. `git range-diff <old-base>..<old-head> <new-base>..<new-head>`: the author's commits stay `=`.
2. No unexpected commit was inserted under them, such as an empty commit carrying the parent's title and body without `Signed-off-by`, which turns a required DCO check red.
3. Signatures on every commit.

A changed child head is not an author edit until the range-diff says so. An inserted commit is mechanical cleanup per the sync rules above, not a finding against the author.
