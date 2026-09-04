# trailer-guard

Guards the trailers of your own commits on the current branch before CI or a reviewer does. It catches three things: a commit that lost its `Signed-off-by`, a commit carrying a `Claude-Session:` line, and an `Assisted-by:` trailer that names a model instead of the neutral `Assisted-by: LLM`. It reports them after every git command and blocks the commands that would publish the branch while they remain.

## Why these three

Rewriting a commit message replaces it whole, so any path that supplies fresh text (`commit --amend -m`, a rebase reword, a prepared file) drops the sign-off silently, and the failure surfaces in a DCO check hours later. The same paths are where a harness slips a session URL or a model name into the message as a trailer, and nothing in git objects to either.

## How it works

One script, two hook events. As a `PostToolUse` hook it runs after any `Bash` tool call containing `git` or `gh stack`, inspects the commits the current branch added over its base, and reports defects so the model sees them at once. As a `PreToolUse` hook it runs before `git push`, `gh pr create`, `gh pr ready`, `gh pr merge`, `gh stack submit`, `gh stack sync`, `gh stack push` and `gh stack merge`, and denies the command while defects remain. Amend, rebase, status, log and `gh stack rebase` are never blocked, so the guard never stands between you and the fix. Both fire on the result rather than on the shape of the command, which covers every rewrite mechanism, including ones not invented yet.

Three decisions keep it quiet in the right places.

- Only your own commits are judged, meaning those whose author email matches `user.email` as resolved in that repository. A cherry-pick or a co-author's commit on the same branch is not your message to rewrite. Without a configured identity every commit is judged.
- The sign-off check speaks up only when the upstream base already carries `Signed-off-by` trailers. The `Claude-Session` and `Assisted-by` checks apply everywhere, since neither line is ever correct.
- The branch is judged against its base, never against `@{upstream}`. A branch tracks itself on the remote, so a defective commit that has already been pushed would land inside the base and the guard would report clean on the very branch that is red in CI. The base is the integration branch unless the branch sits on another local branch, see below.

On a hit it lists the offending commits with one repair recipe: a `git rebase <base> --exec` line that, for each commit whose author email is yours, drops the `Claude-Session:` line, rewrites `Assisted-by:` to `LLM` and re-applies the sign-off, leaving exactly one `Signed-off-by` per commit. Other authors' commits pass through the rebase untouched; a plain `git rebase --signoff` would have signed them off in your name. Rewritten commits lose their original GPG signatures and are re-signed only when `commit.gpgsign` is set or `--gpg-sign` is passed.

## Stacked branches

A branch that sits on another local branch, whether a native GitHub stack (`gh stack`) or a hand-chained set of PRs, is judged from that branch's tip rather than from the integration branch. Without this, a defective commit on `part-1` would block pushing `part-2`, and the repair recipe run from `part-2` would rewrite `part-1`'s commits inside `part-2`, so the two branches would diverge and the stack would no longer sync. The same rule keeps a squash-merged parent out of scope: its commits never reach the integration branch, but they stay behind the parent's tip until you rebase.

The base is resolved in a fixed order, and never by trying candidates until one produces commits.

1. `git config branch.<name>.trailerGuardBase <revision>`, if set for the current branch. The base is the merge-base of HEAD and that revision. A value that does not resolve is ignored rather than trusted, so a typo cannot switch the guard off. The key is per branch because a repo-wide value fits one layer of a stack only, and pointed at the parent it would silence the guard on the parent itself.
2. The nearest local branch tip on the branch's first-parent line above the integration fork. A branch pointing at HEAD itself does not count: a parent lies strictly below, otherwise a fresh layer and a backup branch at HEAD would each take the other for its base and both would go quiet. A backup branch you made mid-layer does hide the commits beneath it; delete it or set the override.
3. The integration branch (`origin/HEAD`, else `origin/main` or `origin/master`), which is the non-stacked case.

Only local branches are candidates. A remote-tracking ref would put the branch's own pushed copy on the line, which is the `@{upstream}` hazard again. In a fresh clone where only the upper branch is checked out, create the parent branch locally or set the override. A parent that gained commits after the layer was cut, or was rewritten, leaves the line until the layer is rebased onto it (`gh stack rebase`, `gh stack sync`, or `git rebase <parent>`); until then the branch is judged from the integration fork, as before.

Commands that publish a whole stack (`gh stack submit`, `sync`, `push`, `merge`) push every branch in it, so before them the guard judges every layer beneath HEAD. Defects in this branch get the usual recipe. Defects in a lower layer are listed under the branch that owns them, with no recipe: switch to that branch, where the guard prints the recipe for exactly those commits, then rebase the branches above it. Layers above HEAD cannot be seen, since stack membership lives on GitHub, so run stack commands from the top layer.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install trailer-guard@claude-code-companions
```

This plugin used to be `dco-guard`; the marketplace records the rename, so an existing installation migrates to the new name on the next start. Requires `python3` on PATH. Nothing needs configuring; `branch.<name>.trailerGuardBase` is optional and described above.

## Tests

```bash
python3 hooks/trailer-guard/scripts/test_trailer_guard.py
```
