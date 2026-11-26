# Second model and bot comments

Read in Step 4, after your own reading of the code.

## Codex

```bash
command -v codex && codex --version
cd "$PR_WORKTREE" || exit 1
if [ "$PR_IS_FORK" = "false" ]; then
  codex review --base "origin/$PR_BASE" --config 'sandbox_mode="danger-full-access"' < /dev/null > "$PR_TMP/codex.txt" 2>&1
else
  codex review --base "origin/$PR_BASE" --config 'sandbox_mode="workspace-write"' --config 'sandbox_workspace_write.network_access=false' < /dev/null > "$PR_TMP/codex.txt" 2>&1
fi
echo "exit $?"
```

- Run it in the foreground with a ten-minute timeout, never in the background, and read the saved output before going on.
- `--base` and a prompt argument are mutually exclusive: pass only `--base`.
- Without `< /dev/null` the CLI can wait on stdin forever; exit 144 with empty output and stdin left open is that wait. Exit 144 with stdin already redirected means something outside killed the process.
- An exhausted usage limit prints a normal message ("You've hit your usage limit …") and exits 0. A run counts only when its output holds a review; otherwise the draft says the second model did not run.
- A fork PR is code from someone without write access. Its build scripts and tests run with every credential in the environment once the sandbox is off, so the sandbox stays on for forks unless the user approves lifting it for this PR after the diff was read for anything that reaches for the network, secrets or obfuscated content.

Without `codex`, or when it fails, say so in the draft and continue with your own reading alone.

## Bot comments

```bash
gh pr view $PR_NUMBER --json comments --jq '.comments[] | select(.author.login | test("bot|coderabbit|gemini"; "i")) | {author: .author.login, body}'
gh api --paginate "repos/{owner}/{repo}/pulls/$PR_NUMBER/comments" --jq '.[] | select(.user.login | test("bot|coderabbit|gemini"; "i")) | {author: .user.login, path, line: (.original_line // .line), body}'
```

Bot findings are raw findings like the second model's. A suggestion the author applied is part of the diff, not a closed thread: a bot that tightened a check pushes it toward completeness, past the real invariant. Read the other reviewers' comments as well, and do not repeat a point already raised without new evidence.

Leave lock files, vendored and generated code out of the reading.
