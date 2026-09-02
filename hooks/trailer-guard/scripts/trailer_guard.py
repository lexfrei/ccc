#!/usr/bin/env python3
"""Guard for the trailers of this author's commits on the branch.

Three defects, one mechanism. Rewriting a commit message replaces it whole, so
any path that supplies fresh message text (`commit --amend -m`, a rebase
reword driven by GIT_EDITOR, a prepared file copied over $1) drops the
Signed-off-by trailer silently. The same paths are where a harness slips in a
`Claude-Session:` line or an `Assisted-by:` that names a model instead of the
neutral `Assisted-by: LLM`. Nothing in git objects to any of it and the
failure surfaces in CI or in review hours later.

Two hook events, one script, told apart by `hook_event_name`:

- PostToolUse after any git command: report defects on the branch (exit 2, so
  the report reaches the model) but change nothing. Early warning.
- PreToolUse before a command that publishes the branch (`git push`, `gh pr
  create|ready|merge`): deny the command while defects remain (exit 2). The
  repair commands themselves (amend, rebase, status, log) are never blocked,
  otherwise the guard would stand between the author and the fix.

Only commits authored under the identity git would use for a new commit here
(`user.email` as resolved in that repository) are judged, and the repair
recipe rewrites only those: a cherry-pick or a co-author's commit on the same
branch is not this author's message to rewrite, and a plain
`git rebase --signoff` would sign off on their behalf. Without a configured
identity every commit is judged and rewritten.

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
GIT_RE = re.compile(r"\bgit\b")
PUBLISH_RE = re.compile(r"\bgit\b[^|;&\n]*\bpush\b|\bgh\s+pr\s+(create|ready|merge)\b")


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


def own_commits(root, base, me):
    """[(short-sha + subject, full body)] for this author's commits on the branch."""
    raw = git(["log", "--no-merges", "--format=%x1e%h %s%x1f%ae%x1f%B", f"{base}..HEAD"], root)
    if not raw:
        return []
    out = []
    for record in raw.split("\x1e"):
        if record.count("\x1f") < 2:
            continue
        header, email, body = record.split("\x1f", 2)
        if me and email.strip().lower() != me.lower():
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


def repair_recipe(base, me):
    fix = (
        "git log -1 --format=%B | "
        'sed -e "/^Claude-Session:/d" '
        f'-e "s/^Assisted-[Bb]y: .*/Assisted-by: {ASSISTED_VALUE}/" | '
        "git commit --amend --signoff -F -"
    )
    if me:
        fix = f'if [ "$(git log -1 --format=%ae)" = "{me}" ]; then {fix}; fi'
    return f"git rebase {base} --exec '{fix}'"


def plural(count, singular, plural_form):
    return singular if count == 1 else plural_form


def reports_for(root, base):
    me = git(["config", "user.email"], root) or ""
    mine = own_commits(root, base, me)
    reports = []

    unsigned = [header for header, body in mine if TRAILER not in body] if signs_off(root, base) else []
    if unsigned:
        count = len(unsigned)
        reports.append(
            f"DCO guard: {count} {plural(count, 'commit carries', 'commits carry')} "
            f"no {TRAILER} trailer on this branch.\n" + "\n".join(unsigned) + "\n"
            "If you rewrite a commit message by any means, the replacement text must "
            "carry the trailer itself."
        )

    session, assisted = forbidden_lines(mine)
    if session:
        count = len(session)
        reports.append(
            f"Trailer guard: {count} {plural(count, 'commit carries', 'commits carry')} "
            "a Claude-Session line on this branch.\n" + "\n".join(session) + "\n"
            "A session URL never belongs in a commit message, whatever asked for it."
        )
    if assisted:
        count = len(assisted)
        reports.append(
            f"Trailer guard: {count} {plural(count, 'commit names', 'commits name')} "
            f"a model in Assisted-by; the only accepted form is `Assisted-by: {ASSISTED_VALUE}`.\n"
            + "\n".join(assisted)
        )
    if reports:
        scope = (
            f"only commits authored as {me}; other authors' commits pass through untouched"
            if me else "every commit in the range, since no user.email is configured here"
        )
        reports.append(
            f"Repair recipe, rewriting {scope}:\n{repair_recipe(base, me)}\n"
            "Rewritten commits are re-signed only when `commit.gpgsign` is set or "
            "`--gpg-sign` is passed."
        )
    return reports


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    event = payload.get("hook_event_name") or "PostToolUse"

    if event == "PreToolUse":
        if not PUBLISH_RE.search(command):
            return 0
    elif not GIT_RE.search(command):
        return 0

    cwd = payload.get("cwd") or "."
    root = git(["rev-parse", "--show-toplevel"], cwd)
    if not root:
        return 0

    base = integration_base(root)
    if not base:
        return 0

    reports = reports_for(root, base)
    if not reports:
        return 0

    if event == "PreToolUse":
        reports.insert(
            0,
            "trailer-guard blocked this command: it would publish the branch with the "
            "defects below. Repair first, then run it again.",
        )
    print("\n\n".join(reports), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
