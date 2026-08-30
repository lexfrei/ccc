#!/usr/bin/env python3
"""PostToolUse guard: catch commits that lost their Signed-off-by trailer.

Rewriting a commit message replaces it whole, so any path that supplies fresh
message text — `commit --amend -m`, a rebase reword driven by GIT_EDITOR, a
prepared file copied over $1 — drops the trailer silently. Nothing in git
objects to it and the failure surfaces in CI hours later.

The guard fires on the RESULT rather than on the shape of the command: after
any git invocation it lists commits on the current branch that carry no
trailer. That covers every mechanism, including ones not invented yet.

It only speaks up in repositories that already sign off (the upstream base
carries trailers), so unrelated repositories stay silent.
"""

import json
import re
import subprocess
import sys

TRAILER = "Signed-off-by"
# Enough history to tell a sign-off repository from a repository that never
# signs off, cheap enough to run after every git command.
BASE_SCAN = 20


def git(args, cwd):
    try:
        done = subprocess.run(
            ["git", "-C", cwd] + args,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip()


def integration_base(cwd):
    """Where this branch left the integration branch, or None.

    Deliberately NOT `@{upstream}`: a branch tracks itself on the remote, so a
    defective commit that has already been pushed lands inside the base and the
    guard reports clean on the very branch that is red in CI.

    Resolved once, never by trying candidates until one yields commits: a
    search that stops at the first ref producing a non-empty answer is a search
    for a reason to fire, and a stale local `main` supplies one every time.
    """
    integration = git(["symbolic-ref", "--short", "--quiet", "refs/remotes/origin/HEAD"], cwd)
    if not integration:
        for candidate in ("origin/main", "origin/master"):
            if git(["rev-parse", "--verify", "--quiet", candidate], cwd):
                integration = candidate
                break
    if not integration:
        return None

    merge_base = git(["merge-base", "HEAD", integration], cwd)
    # merge_base == HEAD means HEAD is an ancestor of the integration branch:
    # nothing of this branch's own to judge.
    if not merge_base or merge_base == git(["rev-parse", "HEAD"], cwd):
        return None
    return merge_base


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    if not re.search(r"\bgit\b", command):
        return 0

    cwd = payload.get("cwd") or "."
    root = git(["rev-parse", "--show-toplevel"], cwd)
    if not root:
        return 0

    base = integration_base(root)
    if not base:
        return 0

    # Silent outside repositories that sign off at all. Plain -N bounds the
    # traversal itself; -N with --grep bounds only the matches printed and
    # walks all reachable history when nothing matches, so the trailer check
    # happens here instead.
    recent_messages = git(
        ["log", "--no-merges", f"-{BASE_SCAN}", "--format=%B", base],
        root,
    )
    if not recent_messages or TRAILER not in recent_messages:
        return 0

    # Judge only commits authored here: a rebase against a stale integration
    # ref pulls other people's upstream history into base..HEAD, and upstream
    # projects that do not require DCO (CLA-based ones) legitimately carry no
    # trailer on those commits.
    author = git(["config", "user.email"], root)
    missing = git(
        [
            "log",
            "--no-merges",
            "--format=%h %s",
            f"--grep={TRAILER}",
            "--invert-grep",
        ]
        + ([f"--author={author}"] if author else [])
        + [f"{base}..HEAD"],
        root,
    )
    if not missing:
        return 0

    count = len(missing.splitlines())
    subject = "commit carries" if count == 1 else "commits carry"
    print(
        f"DCO guard: {count} {subject} no {TRAILER} trailer on this branch.\n"
        f"{missing}\n"
        f"Repair with `git rebase --signoff {base}`: it adds the trailer where it is "
        "missing and does not duplicate it where present. Rewritten commits lose "
        "their original GPG signatures and are re-signed only when `commit.gpgsign` "
        "is set or `--gpg-sign` is passed. "
        "If you rewrite a commit message by any means, the replacement text must "
        "carry the trailer itself, or follow the rewrite with "
        "`git commit --amend --signoff`.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
