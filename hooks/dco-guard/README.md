# dco-guard

PostToolUse hook that catches commits missing the `Signed-off-by` trailer before CI does. Rewriting a commit message replaces it whole, so any path that supplies fresh text — `commit --amend -m`, a rebase reword, a prepared file — drops the trailer silently, and the failure surfaces in a DCO check hours later.

## How it works

The guard fires on the result rather than on the shape of the command: after any `Bash` tool call containing `git`, it lists commits on the current branch that carry no trailer. That covers every rewrite mechanism, including ones not invented yet.

Design decisions that keep it quiet in the right places:

- **Silent outside sign-off repositories** — it only speaks up when the upstream base already carries `Signed-off-by` trailers, so repositories that never sign off are untouched.
- **Judges against the integration branch, not `@{upstream}`** — a branch tracks itself on the remote, so a defective commit that has already been pushed would land inside the base and the guard would report clean on the very branch that is red in CI.
- **Judges only commits authored here** — a rebase against a stale integration ref pulls other people's history into the range, and upstream projects without DCO legitimately carry no trailer on those commits.

On a hit it flags the offending commits and the repair recipe: `git rebase --signoff <base>` adds the trailer where missing and does not duplicate it where present. Rewritten commits lose their original GPG signatures and are re-signed only when `commit.gpgsign` is set or `--gpg-sign` is passed.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install dco-guard@claude-code-companions
```

Requires `python3` on PATH and git 2.35 or newer (older git inverts `--author` together with `--grep` under `--invert-grep`, which silences the guard on exactly the commits it should catch); there is nothing to configure.
