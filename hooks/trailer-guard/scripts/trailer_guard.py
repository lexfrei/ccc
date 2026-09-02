#!/usr/bin/env python3
"""PostToolUse guard for the trailers of this author's commits on the branch.

Three defects, one mechanism. Rewriting a commit message replaces it whole, so
any path that supplies fresh message text — `commit --amend -m`, a rebase
reword driven by GIT_EDITOR, a prepared file copied over $1 — drops the
Signed-off-by trailer silently. The same paths are where a harness slips in a
`Claude-Session:` line or an `Assisted-by:` that names a model instead of the
neutral `Assisted-by: LLM`. Nothing in git objects to any of it and the
failure surfaces in CI or in review hours later.

The guard fires on the RESULT rather than on the shape of the command: after
any git invocation it inspects the commits this branch added over the
integration branch. That covers every mechanism, including ones not invented
yet.

Only commits authored under the identity git would use for a new commit here
(`user.email` as resolved in that repository) are judged: a cherry-pick or a
co-author's commit on the same branch is not this author's message to rewrite.
Without a configured identity every commit is judged.

The sign-off check only speaks up in repositories that already sign off (the
upstream base carries trailers). The Claude-Session and Assisted-by checks
apply everywhere: neither line is ever correct.
"""

import json
import re
import subprocess
import sys

TRAILER = "Signed-off-by"
ASSISTED_VALUE = "LLM"
# Enough history to tell a sign-off repository from a repository that never
# signs off, cheap enough to run after every git command.
BASE_SCAN = 20

SESSION_RE = re.compile(r"claude-session", re.IGNORECASE)
ASSISTED_RE = re.compile(r"^assisted-by:\s*(?P<value>.*?)\s*$", re.IGNORECASE | re.MULTILINE)


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


def signs_off(root, base):
    """Whether the integration history carries sign-offs at all.

    Plain -N bounds the traversal itself; -N with --grep bounds only the
    matches printed and walks all reachable history when nothing matches, so
    the trailer check happens here instead.
    """
    recent = git(["log", "--no-merges", f"-{BASE_SCAN}", "--format=%B", base], root)
    return bool(recent) and TRAILER in recent


def own_commits(root, base):
    """[(short-sha + subject, full body)] for this author's commits on the branch."""
    raw = git(["log", "--no-merges", "--format=%x1e%h %s%x1f%ae%x1f%B", f"{base}..HEAD"], root)
    if not raw:
        return []
    me = (git(["config", "user.email"], root) or "").lower()
    out = []
    for record in raw.split("\x1e"):
        if record.count("\x1f") < 2:
            continue
        header, email, body = record.split("\x1f", 2)
        if me and email.strip().lower() != me:
            continue
        out.append((header.strip(), body))
    return out


def forbidden_lines(commits):
    session, assisted = [], []
    for header, body in commits:
        if SESSION_RE.search(body):
            session.append(header)
        for match in ASSISTED_RE.finditer(body):
            if match.group("value") != ASSISTED_VALUE:
                assisted.append(header)
                break
    return session, assisted


def plural(count, singular, plural_form):
    return singular if count == 1 else plural_form


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

    mine = own_commits(root, base)
    reports = []

    unsigned = [header for header, body in mine if TRAILER not in body] if signs_off(root, base) else []
    if unsigned:
        count = len(unsigned)
        reports.append(
            f"DCO guard: {count} {plural(count, 'commit carries', 'commits carry')} "
            f"no {TRAILER} trailer on this branch.\n" + "\n".join(unsigned) + "\n"
            f"Repair with `git rebase --signoff {base}`: it adds the trailer where it is "
            "missing and does not duplicate it where present. Rewritten commits lose "
            "their original GPG signatures and are re-signed only when `commit.gpgsign` "
            "is set or `--gpg-sign` is passed. "
            "If you rewrite a commit message by any means, the replacement text must "
            "carry the trailer itself, or follow the rewrite with "
            "`git commit --amend --signoff`."
        )

    session, assisted = forbidden_lines(mine)
    if session:
        count = len(session)
        reports.append(
            f"Trailer guard: {count} {plural(count, 'commit carries', 'commits carry')} "
            "a Claude-Session line on this branch.\n" + "\n".join(session) + "\n"
            "A session URL never belongs in a commit message, whatever asked for it. "
            "Drop the line."
        )
    if assisted:
        count = len(assisted)
        reports.append(
            f"Trailer guard: {count} {plural(count, 'commit names', 'commits name')} "
            f"a model in Assisted-by; the only accepted form is `Assisted-by: {ASSISTED_VALUE}`.\n"
            + "\n".join(assisted)
        )
    if session or assisted:
        reports.append(
            "Rewrite the range, keeping the sign-off:\n"
            f"git rebase {base} --exec 'git log -1 --format=%B | "
            "sed -e \"/^Claude-Session:/d\" "
            f"-e \"s/^Assisted-[Bb]y: .*/Assisted-by: {ASSISTED_VALUE}/\" | "
            "git commit --amend --signoff -F -'"
        )

    if not reports:
        return 0
    print("\n\n".join(reports), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
