# trailer-guard

Guards the trailers of your own commits on the current branch before CI or a reviewer does. It catches three things: a commit that lost its `Signed-off-by`, a commit carrying a `Claude-Session:` line, and an `Assisted-by:` trailer that names a model instead of the neutral `Assisted-by: LLM`. It reports them after every git command and blocks the commands that would publish the branch while they remain.

## Why these three

Rewriting a commit message replaces it whole, so any path that supplies fresh text (`commit --amend -m`, a rebase reword, a prepared file) drops the sign-off silently, and the failure surfaces in a DCO check hours later. The same paths are where a harness slips a session URL or a model name into the message as a trailer, and nothing in git objects to either.

## How it works

One script, two hook events. As a `PostToolUse` hook it runs after any `Bash` tool call containing `git`, inspects the commits the current branch added over the integration branch, and reports defects so the model sees them at once. As a `PreToolUse` hook it runs before `git push`, `gh pr create`, `gh pr ready` and `gh pr merge`, and denies the command while defects remain. Amend, rebase, status and log are never blocked, so the guard never stands between you and the fix. Both fire on the result rather than on the shape of the command, which covers every rewrite mechanism, including ones not invented yet.

Three decisions keep it quiet in the right places.

- Only your own commits are judged, meaning those whose author email matches `user.email` as resolved in that repository. A cherry-pick or a co-author's commit on the same branch is not your message to rewrite. Without a configured identity every commit is judged.
- The sign-off check speaks up only when the upstream base already carries `Signed-off-by` trailers. The `Claude-Session` and `Assisted-by` checks apply everywhere, since neither line is ever correct.
- The branch is judged against the integration branch, not `@{upstream}`. A branch tracks itself on the remote, so a defective commit that has already been pushed would land inside the base and the guard would report clean on the very branch that is red in CI.

On a hit it lists the offending commits with one repair recipe: a `git rebase <base> --exec` line that, for each commit whose author email is yours, drops the `Claude-Session:` line, rewrites `Assisted-by:` to `LLM` and re-applies the sign-off, leaving exactly one `Signed-off-by` per commit. Other authors' commits pass through the rebase untouched; a plain `git rebase --signoff` would have signed them off in your name. Rewritten commits lose their original GPG signatures and are re-signed only when `commit.gpgsign` is set or `--gpg-sign` is passed.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install trailer-guard@claude-code-companions
```

This plugin used to be `dco-guard`; the marketplace records the rename, so an existing installation migrates to the new name on the next start. Requires `python3` on PATH; there is nothing to configure.

## Tests

```bash
python3 hooks/trailer-guard/scripts/test_trailer_guard.py
```
