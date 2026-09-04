#!/usr/bin/env python3
"""Runnable check for trailer_guard.py. Run: python3 test_dco_trailer_guard.py"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).with_name("trailer_guard.py")

SIGNOFF = "Signed-off-by: Test User <test@example.com>"

# Hermetic git: no user config (no gpg signing, no hooks), fixed identity.
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test User",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test User",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, env=GIT_ENV,
                   capture_output=True, text=True)


def commit(repo, message, author=None):
    path = Path(repo) / "file.txt"
    with path.open("a") as fh:
        fh.write(message.splitlines()[0] + "\n")
    git(repo, "add", "file.txt")
    args = ["commit", "--quiet", "--message", message]
    if author:
        args.append(f"--author={author}")
    git(repo, *args)


def make_repo(tmp, base_signed=True):
    """Repo with one commit on origin/main and HEAD on a branch above it."""
    repo = str(Path(tmp) / "repo")
    Path(repo).mkdir()
    git(repo, "init", "--quiet", "--initial-branch=main")
    git(repo, "config", "user.email", "test@example.com")
    base = "chore: base commit\n"
    if base_signed:
        base += "\n" + SIGNOFF + "\n"
    commit(repo, base)
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "checkout", "--quiet", "-b", "feature")
    return repo


def run_hook(repo, command="git status", event="PostToolUse"):
    payload = {"hook_event_name": event, "tool_name": "Bash",
               "tool_input": {"command": command}, "cwd": repo}
    done = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )
    return done.returncode, done.stderr


def test_clean_branch_is_silent():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: clean\n\n" + SIGNOFF + "\n")
        commit(repo, "feat: llm trailer\n\nAssisted-by: LLM\n" + SIGNOFF + "\n")
        code, err = run_hook(repo)
        assert code == 0, err
        assert err == ""


def test_non_git_command_is_silent():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: bad\n\nClaude-Session: https://example.com/s/1\n")
        code, err = run_hook(repo, command="ls -la")
        assert code == 0, err


def test_missing_signoff_is_reported():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: forgot signoff\n")
        code, err = run_hook(repo)
        assert code == 2, err
        assert "Signed-off-by" in err
        assert "forgot signoff" in err
        assert "--exec" in err
        assert "git rebase --signoff" not in err


def test_claude_session_trailer_is_reported():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: leaks session\n\n" + SIGNOFF
               + "\nClaude-Session: https://claude.ai/code/session_abc\n")
        code, err = run_hook(repo)
        assert code == 2, err
        assert "Claude-Session" in err
        assert "leaks session" in err
        assert "Signed-off-by trailer" not in err


def test_claude_session_is_reported_even_where_nobody_signs_off():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp, base_signed=False)
        commit(repo, "feat: no dco repo\n\nclaude-session: https://example.com/x\n")
        code, err = run_hook(repo)
        assert code == 2, err
        assert "Claude-Session" in err
        assert "Signed-off-by trailer" not in err


def test_assisted_by_claude_is_reported():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: names the model\n\n"
               "Assisted-By: Claude <noreply@anthropic.com>\n" + SIGNOFF + "\n")
        code, err = run_hook(repo)
        assert code == 2, err
        assert "Assisted-by: LLM" in err
        assert "names the model" in err


def test_assisted_by_other_model_is_reported():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: other model\n\n" + SIGNOFF
               + "\nAssisted-by: GPT-5 <noreply@openai.com>\n")
        code, err = run_hook(repo)
        assert code == 2, err
        assert "Assisted-by: LLM" in err


def test_all_defects_reported_together():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: unsigned\n")
        commit(repo, "feat: session\n\n" + SIGNOFF + "\nClaude-Session: https://x/y\n")
        commit(repo, "feat: model\n\nAssisted-By: Claude <noreply@anthropic.com>\n" + SIGNOFF + "\n")
        code, err = run_hook(repo)
        assert code == 2, err
        for needle in ("unsigned", "session", "model", "Signed-off-by", "Claude-Session", "Assisted-by: LLM"):
            assert needle in err, needle


def test_on_integration_branch_is_silent():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        git(repo, "checkout", "--quiet", "main")
        code, err = run_hook(repo)
        assert code == 0, err


FOREIGN = "Someone Else <else@example.org>"


def test_foreign_commits_are_not_judged():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: theirs unsigned\n", author=FOREIGN)
        commit(repo, "feat: theirs session\n\n" + SIGNOFF + "\nClaude-Session: https://x/y\n", author=FOREIGN)
        commit(repo, "feat: theirs model\n\nAssisted-By: Claude <noreply@anthropic.com>\n" + SIGNOFF + "\n", author=FOREIGN)
        code, err = run_hook(repo)
        assert code == 0, err
        assert err == ""


def test_own_defect_reported_next_to_clean_foreign_commit():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: theirs\n\n" + SIGNOFF + "\n", author=FOREIGN)
        commit(repo, "feat: mine\n\nAssisted-By: Claude <noreply@anthropic.com>\n" + SIGNOFF + "\n")
        code, err = run_hook(repo)
        assert code == 2, err
        assert "feat: mine" in err
        assert "feat: theirs" not in err


def test_author_match_ignores_case():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: shouty\n\nClaude-Session: https://x/y\n" + SIGNOFF + "\n",
               author="Test User <TEST@Example.com>")
        code, err = run_hook(repo)
        assert code == 2, err


def test_without_configured_identity_every_commit_is_judged():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        git(repo, "config", "--unset", "user.email")
        commit(repo, "feat: theirs session\n\n" + SIGNOFF + "\nClaude-Session: https://x/y\n", author=FOREIGN)
        code, err = run_hook(repo)
        assert code == 2, err
        assert "Claude-Session" in err


def recipe_from(err):
    lines = [l for l in err.splitlines() if l.startswith("git rebase ")]
    assert len(lines) == 1, err
    return lines[0]


def test_pre_tool_use_blocks_publishing_with_defects():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: leaks\n\n" + SIGNOFF + "\nClaude-Session: https://x/y\n")
        for cmd in ("git push origin feature", "git push --force-with-lease",
                    "gh pr create --title x --body y", "gh pr ready 7", "gh pr merge 7 --squash"):
            code, err = run_hook(repo, command=cmd, event="PreToolUse")
            assert code == 2, (cmd, err)
            assert "Claude-Session" in err, cmd


def test_pre_tool_use_lets_the_repair_through():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: leaks\n\n" + SIGNOFF + "\nClaude-Session: https://x/y\n")
        for cmd in ("git status", "git log --oneline", "git rebase -i HEAD~1",
                    "git commit --amend --signoff", "gh pr view 7"):
            code, err = run_hook(repo, command=cmd, event="PreToolUse")
            assert code == 0, (cmd, err)


def test_pre_tool_use_allows_a_clean_push():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: clean\n\nAssisted-by: LLM\n" + SIGNOFF + "\n")
        code, err = run_hook(repo, command="git push origin feature", event="PreToolUse")
        assert code == 0, err
        assert err == ""


def test_recipe_rewrites_only_own_commits():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: theirs\n\nClaude-Session: https://x/theirs\n", author=FOREIGN)
        commit(repo, "feat: mine\n\nAssisted-By: Claude <noreply@anthropic.com>\nClaude-Session: https://x/mine\n")
        code, err = run_hook(repo)
        assert code == 2, err
        recipe = recipe_from(err)
        assert "test@example.com" in recipe
        done = subprocess.run(recipe, shell=True, cwd=repo, env=GIT_ENV, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        log = subprocess.run(["git", "-C", repo, "log", "--format=%x1e%an%x1f%B", "origin/main..HEAD"],
                             env=GIT_ENV, capture_output=True, text=True, check=True).stdout
        records = [r.split("\x1f", 1) for r in log.split("\x1e") if r.strip()]
        by_author = {name.strip(): body for name, body in records}
        theirs = by_author["Someone Else"]
        assert "Claude-Session: https://x/theirs" in theirs
        assert "Signed-off-by" not in theirs
        mine = by_author["Test User"]
        assert "Claude-Session" not in mine
        assert "Assisted-by: LLM" in mine
        assert mine.count("Signed-off-by:") == 1
        code, err = run_hook(repo)
        assert code == 0, err


def test_recipe_without_identity_touches_every_commit():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        git(repo, "config", "--unset", "user.email")
        commit(repo, "feat: theirs\n\nClaude-Session: https://x/theirs\n", author=FOREIGN)
        code, err = run_hook(repo)
        assert code == 2, err
        assert "%ae" not in recipe_from(err)



def rev(repo, ref):
    return subprocess.run(["git", "-C", repo, "rev-parse", ref], env=GIT_ENV,
                          capture_output=True, text=True, check=True).stdout.strip()


def make_stack(tmp, lower="feat: lower\n\n" + SIGNOFF + "\n"):
    """make_repo, then part-1 with one commit and part-2 branched off its tip."""
    repo = make_repo(tmp)
    git(repo, "checkout", "--quiet", "-b", "part-1")
    commit(repo, lower)
    git(repo, "checkout", "--quiet", "-b", "part-2")
    return repo


LEAKY = "feat: lower leaks\n\n" + SIGNOFF + "\nClaude-Session: https://x/lower\n"


def test_stacked_branch_is_judged_from_its_parent():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_stack(tmp, lower=LEAKY)
        commit(repo, "feat: upper clean\n\n" + SIGNOFF + "\n")
        code, err = run_hook(repo)
        assert code == 0, err
        assert err == ""
        code, err = run_hook(repo, command="git push origin part-2", event="PreToolUse")
        assert code == 0, err
        git(repo, "checkout", "--quiet", "part-1")
        code, err = run_hook(repo)
        assert code == 2, err
        assert "lower leaks" in err


def test_recipe_on_a_stack_leaves_the_parent_untouched():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_stack(tmp)
        commit(repo, "feat: upper\n\nAssisted-By: Claude <noreply@anthropic.com>\n" + SIGNOFF + "\n")
        parent = rev(repo, "part-1")
        code, err = run_hook(repo)
        assert code == 2, err
        assert "feat: lower" not in err
        recipe = recipe_from(err)
        assert parent in recipe
        done = subprocess.run(recipe, shell=True, cwd=repo, env=GIT_ENV, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        assert rev(repo, "part-1") == parent
        assert rev(repo, "HEAD~1") == parent
        code, err = run_hook(repo)
        assert code == 0, err


def test_parent_tip_at_head_is_not_a_parent():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: leaks\n\n" + SIGNOFF + "\nClaude-Session: https://x/y\n")
        git(repo, "branch", "backup")
        code, err = run_hook(repo)
        assert code == 2, err
        assert "leaks" in err
        git(repo, "checkout", "--quiet", "-b", "part-2")
        code, err = run_hook(repo)
        assert code == 2, err


def test_nearest_parent_wins():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_stack(tmp, lower=LEAKY)
        commit(repo, "feat: mid leaks\n\n" + SIGNOFF + "\nClaude-Session: https://x/mid\n")
        git(repo, "branch", "wip")
        commit(repo, "feat: top\n\n" + SIGNOFF + "\n")
        code, err = run_hook(repo)
        assert code == 0, err


def test_detached_head_on_a_stack():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_stack(tmp, lower=LEAKY)
        commit(repo, "feat: upper clean\n\n" + SIGNOFF + "\n")
        git(repo, "checkout", "--quiet", "--detach")
        code, err = run_hook(repo)
        assert code == 0, err
        commit(repo, "feat: detached leaks\n\n" + SIGNOFF + "\nClaude-Session: https://x/d\n")
        code, err = run_hook(repo)
        assert code == 2, err
        assert "detached leaks" in err
        assert "lower leaks" not in err


def test_squash_merged_parent_stays_out_of_scope():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_stack(tmp, lower=LEAKY)
        commit(repo, "feat: upper clean\n\n" + SIGNOFF + "\n")
        git(repo, "checkout", "--quiet", "main")
        commit(repo, "feat: lower (#1)\n\n" + SIGNOFF + "\n")
        git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(repo, "checkout", "--quiet", "part-2")
        code, err = run_hook(repo)
        assert code == 0, err


def test_override_sets_the_base():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: leaks\n\n" + SIGNOFF + "\nClaude-Session: https://x/y\n")
        leaky = rev(repo, "HEAD")
        commit(repo, "feat: clean\n\n" + SIGNOFF + "\n")
        git(repo, "config", "branch.feature.trailerGuardBase", "no-such-ref")
        code, err = run_hook(repo)
        assert code == 2, err
        git(repo, "config", "branch.feature.trailerGuardBase", leaky)
        code, err = run_hook(repo)
        assert code == 0, err
        git(repo, "config", "branch.feature.trailerGuardBase", "feature")
        code, err = run_hook(repo)
        assert code == 0, err


def test_override_beats_the_nearest_parent():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_stack(tmp, lower=LEAKY)
        commit(repo, "feat: upper clean\n\n" + SIGNOFF + "\n")
        git(repo, "config", "branch.part-2.trailerGuardBase", "origin/main")
        code, err = run_hook(repo)
        assert code == 2, err
        assert "lower leaks" in err


STACK_PUBLISH = ("gh stack submit --auto --open", "gh stack sync", "gh stack push", "gh stack merge 7 --yes --merge")
STACK_LOCAL = ("gh stack rebase", "gh stack view", "gh stack add part-3", "gh stack checkout 3")


def test_pre_tool_use_blocks_stack_publishing_with_defects():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_stack(tmp)
        commit(repo, "feat: upper leaks\n\n" + SIGNOFF + "\nClaude-Session: https://x/y\n")
        for cmd in STACK_PUBLISH:
            code, err = run_hook(repo, command=cmd, event="PreToolUse")
            assert code == 2, (cmd, err)
            assert "the stack" in err, cmd
            assert rev(repo, "part-1") in recipe_from(err), cmd
        for cmd in STACK_LOCAL:
            code, err = run_hook(repo, command=cmd, event="PreToolUse")
            assert code == 0, (cmd, err)


def test_stack_publish_names_the_lower_layer_instead_of_rewriting_it():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_stack(tmp, lower=LEAKY)
        commit(repo, "feat: upper clean\n\n" + SIGNOFF + "\n")
        code, err = run_hook(repo, command="gh stack submit", event="PreToolUse")
        assert code == 2, err
        assert "`part-1`" in err
        assert "lower leaks" in err
        assert not [l for l in err.splitlines() if l.startswith("git rebase ")], err
        code, err = run_hook(repo, command="gh stack sync", event="PreToolUse")
        assert code == 2, err
        git(repo, "checkout", "--quiet", "part-1")
        code, err = run_hook(repo, command="gh stack sync", event="PreToolUse")
        assert code == 2, err
        assert rev(repo, "origin/main") in recipe_from(err)


def test_stack_publish_without_a_local_parent_hints_at_the_override():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: leaks\n\n" + SIGNOFF + "\nClaude-Session: https://x/y\n")
        code, err = run_hook(repo, command="gh stack submit", event="PreToolUse")
        assert code == 2, err
        assert "branch.feature.trailerGuardBase" in err
        code, err = run_hook(repo, command="git push", event="PreToolUse")
        assert code == 2, err
        assert "trailerGuardBase" not in err


def test_post_tool_use_fires_after_gh_stack_commands():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        commit(repo, "feat: leaks\n\n" + SIGNOFF + "\nClaude-Session: https://x/y\n")
        code, err = run_hook(repo, command="gh stack rebase")
        assert code == 2, err
        code, err = run_hook(repo, command="gh pr view 7")
        assert code == 0, err

if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
