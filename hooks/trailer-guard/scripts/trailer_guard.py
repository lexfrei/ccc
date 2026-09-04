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

- PostToolUse after any git or `gh stack` command: report defects on the
  branch (exit 2, so the report reaches the model) but change nothing. Early
  warning.
- PreToolUse before a command that publishes commits (`git push`, `gh pr
  create|ready|merge`, `gh stack submit|sync|push|merge`): deny the command
  while defects remain (exit 2). The repair commands themselves (amend,
  rebase, status, log, `gh stack rebase`) are never blocked, otherwise the
  guard would stand between the author and the fix.

Only commits authored under the identity git would use for a new commit here
(`user.email` as resolved in that repository) are judged, and the repair
recipe rewrites only those: a cherry-pick or a co-author's commit on the same
branch is not this author's message to rewrite, and a plain
`git rebase --signoff` would sign off on their behalf. Without a configured
identity every commit is judged and rewritten.

The judged range is what the command publishes. A branch that sits on another
local branch (a stacked PR, native or hand-chained) is judged from that
branch's tip, so the layer below is neither judged nor rewritten from here.
Commands that push a whole stack are judged from the integration branch, and
defects in a lower layer are attributed to the branch that owns them instead
of getting a recipe that would rewrite that layer inside this one.

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
# Per-branch override of the base: `git config branch.<name>.trailerGuardBase
# <revision>`. Repo-wide would fit one layer of a stack only, and set to the
# parent it would silence the guard on the parent itself.
OVERRIDE_KEY = "trailerGuardBase"

SESSION_RE = re.compile(r"claude-session", re.IGNORECASE)
ASSISTED_RE = re.compile(r"^assisted-by:\s*(?P<value>.*?)\s*$", re.IGNORECASE | re.MULTILINE)
LOCAL_RE = re.compile(r"\bgit\b|\bgh\s+stack\b")
# Native-stack commands that push every branch of the stack; sync does so with
# --force-with-lease and is the main push path of a stack. `gh stack rebase`
# is local and is the stack's repair step.
STACK_PUBLISH_RE = re.compile(r"\bgh\s+stack\s+(submit|sync|push|merge)\b")
PUBLISH_RE = re.compile(
    r"\bgit\b[^|;&\n]*\bpush\b|\bgh\s+pr\s+(create|ready|merge)\b|" + STACK_PUBLISH_RE.pattern
)


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


def integration_fork(cwd):
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


def override(cwd):
    """(merge-base with the configured revision, its name), or None.

    A value that does not resolve, or shares no history with HEAD, is ignored
    rather than trusted: a typo must not switch the guard off.
    """
    branch = git(["symbolic-ref", "--short", "--quiet", "HEAD"], cwd)
    if not branch:
        return None
    value = git(["config", "--get", f"branch.{branch}.{OVERRIDE_KEY}"], cwd)
    if not value:
        return None
    merge_base = git(["merge-base", "HEAD", value], cwd)
    return (merge_base, value) if merge_base else None


def first_parent_line(cwd, fork):
    """[(sha, [local branch names])] from HEAD down to (excluding) the fork.

    One call, decorations restricted to local branches: remote-tracking refs
    would put this branch's own pushed copy on the line, which is the
    `@{upstream}` hazard again, and tags say nothing about ownership. Branches
    above HEAD are not ancestors of HEAD and never appear.
    """
    raw = git(
        ["log", "--first-parent", "--decorate-refs=refs/heads/", "--format=%H%x1f%D", f"{fork}..HEAD"],
        cwd,
    )
    line = []
    for record in (raw or "").splitlines():
        sha, _, decoration = record.partition("\x1f")
        names = []
        for name in decoration.split(","):
            name = name.strip()
            if name.startswith("HEAD -> "):
                name = name[len("HEAD -> "):]
            if name and name != "HEAD":
                names.append(name)
        line.append((sha, names))
    return line


def layers(cwd):
    """Partition of this branch's history into [(lower, upper, owner)], nearest first.

    The first entry is this branch's own layer: from the nearest local branch
    tip on the first-parent line (or the configured override) up to HEAD. Each
    further entry is a layer beneath it, named after the branch whose tip
    closes it. With nothing beneath, the single layer runs from the
    integration fork, which is the non-stacked case and today's behavior.

    A branch whose tip is HEAD is not a parent: a parent lies strictly below.
    Otherwise a fresh layer and a backup branch at HEAD would each treat the
    other as the base and both would go quiet.

    Returns (layers, signs_off_base); ([], None) when there is nothing to judge.
    """
    head = git(["rev-parse", "HEAD"], cwd)
    fork = integration_fork(cwd)
    forced = override(cwd)

    if forced:
        base, name = forced
        if base == head:
            return [], None
        if not fork:
            return [(base, "HEAD", None)], base
    elif not fork:
        return [], None

    line = first_parent_line(cwd, fork)
    boundaries = [(sha, names) for sha, names in line[1:] if names]
    if forced:
        # The override is this layer's base whatever the line says; branches
        # beneath it keep their attribution, anything else is dropped.
        base, name = forced
        position = {sha: index for index, (sha, _) in enumerate(line)}
        at = position.get(base)
        beneath = [(sha, names) for sha, names in boundaries if at is not None and position[sha] > at]
        boundaries = [] if base == fork else [(base, [name])] + beneath

    out = []
    upper, owner = "HEAD", None
    for sha, names in boundaries:
        out.append((sha, upper, owner))
        upper, owner = sha, ", ".join(names)
    out.append((fork, upper, owner))
    return out, fork


def signs_off(root, base):
    """Whether the integration history carries sign-offs at all.

    Plain -N bounds the traversal itself; -N with --grep bounds only the
    matches printed and walks all reachable history when nothing matches, so
    the trailer check happens here instead.
    """
    recent = git(["log", "--no-merges", f"-{BASE_SCAN}", "--format=%B", base], root)
    return bool(recent) and TRAILER in recent


def own_commits(root, lower, upper, me):
    """[(short-sha + subject, full body)] for this author's commits in the layer."""
    raw = git(["log", "--no-merges", "--format=%x1e%h %s%x1f%ae%x1f%B", f"{lower}..{upper}"], root)
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


def defects(root, lower, upper, me, dco):
    """(unsigned, session, assisted) headers for this author's commits in the layer."""
    mine = own_commits(root, lower, upper, me)
    unsigned = [header for header, body in mine if TRAILER not in body] if dco else []
    session, assisted = forbidden_lines(mine)
    return unsigned, session, assisted


def own_layer_reports(root, base, me, dco, hint):
    unsigned, session, assisted = defects(root, base, "HEAD", me, dco)
    reports = []
    if unsigned:
        count = len(unsigned)
        reports.append(
            f"DCO guard: {count} {plural(count, 'commit carries', 'commits carry')} "
            f"no {TRAILER} trailer on this branch.\n" + "\n".join(unsigned) + "\n"
            "If you rewrite a commit message by any means, the replacement text must "
            "carry the trailer itself."
        )
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
            "`--gpg-sign` is passed." + hint
        )
    return reports


def lower_layer_report(root, lower, upper, owner, me, dco):
    """Defects beneath this branch, attributed to the branch that owns them.

    No recipe: a rebase from here would rewrite that branch's commits inside
    this one and the two would diverge. The guard on that branch prints the
    recipe for exactly these commits.
    """
    unsigned, session, assisted = defects(root, lower, upper, me, dco)
    tagged = {}
    for header in unsigned:
        tagged.setdefault(header, []).append(f"no {TRAILER}")
    for header in session:
        tagged.setdefault(header, []).append("Claude-Session line")
    for header in assisted:
        tagged.setdefault(header, []).append("Assisted-by names a model")
    if not tagged:
        return None
    count = len(tagged)
    lines = [f"{header} ({'; '.join(why)})" for header, why in tagged.items()]
    return (
        f"Trailer guard: {count} defective {plural(count, 'commit', 'commits')} "
        f"below this branch {plural(count, 'belongs', 'belong')} to `{owner}`.\n" + "\n".join(lines) + "\n"
        f"Switch to `{owner}` and repair there (the guard prints the recipe), then rebase the "
        "branches above it (`gh stack rebase`, or `git rebase --onto`)."
    )


def reports_for(root, whole_stack):
    me = git(["config", "user.email"], root) or ""
    partition, dco_base = layers(root)
    if not partition:
        return []
    dco = signs_off(root, dco_base)

    own = partition[0]
    if not whole_stack:
        return own_layer_reports(root, own[0], me, dco, "")

    hint = ""
    if len(partition) == 1:
        branch = git(["symbolic-ref", "--short", "--quiet", "HEAD"], root) or "<branch>"
        hint = (
            "\nNo local branch lies beneath this one, so the whole range counts as this branch. "
            "If it sits on another branch, rebase onto that branch first (`gh stack rebase` or "
            f"`git rebase <parent>`), or record it: `git config branch.{branch}.{OVERRIDE_KEY} <parent>`."
        )
    reports = own_layer_reports(root, own[0], me, dco, hint)
    for lower, upper, owner in partition[1:]:
        report = lower_layer_report(root, lower, upper, owner, me, dco)
        if report:
            reports.append(report)
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

    whole_stack = False
    if event == "PreToolUse":
        if not PUBLISH_RE.search(command):
            return 0
        whole_stack = bool(STACK_PUBLISH_RE.search(command))
    elif not LOCAL_RE.search(command):
        return 0

    cwd = payload.get("cwd") or "."
    root = git(["rev-parse", "--show-toplevel"], cwd)
    if not root:
        return 0

    reports = reports_for(root, whole_stack)
    if not reports:
        return 0

    if event == "PreToolUse":
        what = "the stack" if whole_stack else "the branch"
        reports.insert(
            0,
            f"trailer-guard blocked this command: it would publish {what} with the "
            "defects below. Repair first, then run it again.",
        )
    print("\n\n".join(reports), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
