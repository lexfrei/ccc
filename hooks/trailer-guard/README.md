# trailer-guard

PostToolUse hook that guards the trailers of your own commits on the current branch before CI or a reviewer does. It catches three things: a commit that lost its `Signed-off-by`, a commit carrying a `Claude-Session:` line, and an `Assisted-by:` trailer that names a model instead of the neutral `Assisted-by: LLM`.

## Why these three

Rewriting a commit message replaces it whole, so any path that supplies fresh text — `commit --amend -m`, a rebase reword, a prepared file — drops the sign-off silently, and the failure surfaces in a DCO check hours later. The same paths are where a harness slips a session URL or a model name into the message as a trailer, and nothing in git objects to either.

## How it works

The guard fires on the result rather than on the shape of the command: after any `Bash` tool call containing `git`, it inspects the commits the current branch added over the integration branch. That covers every rewrite mechanism, including ones not invented yet.

Design decisions that keep it quiet in the right places:

- **Judges only your own commits** — those whose author email matches `user.email` as resolved in that repository. A cherry-pick or a co-author's commit on the same branch is not your message to rewrite. Without a configured identity every commit is judged.
- **The sign-off check is silent outside sign-off repositories** — it only speaks up when the upstream base already carries `Signed-off-by` trailers. The `Claude-Session` and `Assisted-by` checks apply everywhere: neither line is ever correct.
- **Judges against the integration branch, not `@{upstream}`** — a branch tracks itself on the remote, so a defective commit that has already been pushed would land inside the base and the guard would report clean on the very branch that is red in CI.

On a hit it lists the offending commits with a repair recipe. For a missing sign-off, `git rebase --signoff <base>` adds the trailer where missing and does not duplicate it where present. For the other two it prints a `git rebase <base> --exec` line that drops the `Claude-Session:` line, rewrites `Assisted-by:` to `LLM` and re-applies the sign-off, leaving exactly one `Signed-off-by` per commit. Rewritten commits lose their original GPG signatures and are re-signed only when `commit.gpgsign` is set or `--gpg-sign` is passed.

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
