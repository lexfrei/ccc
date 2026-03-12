---
name: tldrpr
description: Generate plain-text TLDR for PRs (for Slack, copied to clipboard)
argument-hint: "<pr-url-or-ref> [pr-url-or-ref] ... [--lang <language>]"
---

Generate a plain-text TLDR summary of one or more Pull Requests for pasting into Slack. No markdown formatting — just plain text. Result is copied to clipboard.

## Arguments

Parse `$ARGUMENTS` for:

- One or more PR references in any of these formats:
  - Full URL: `https://github.com/owner/repo/pull/123`
  - Short ref: `owner/repo#123`
- `--lang <language>` — language for the TLDR line (e.g. `en`, `ru`, `de`). If omitted, use the same language the user communicates in during this conversation.

If no PR references provided, look in the conversation context for recently mentioned PR URLs or refs.

## For each PR

1. Fetch PR details:

   ```bash
   gh pr view <NUMBER> --repo <OWNER>/<REPO> --json title,body --jq '{title, body: .body[:2000]}'
   ```

2. Generate TLDR in this exact format (plain text, no markdown):

   ```text
   https://github.com/owner/repo/pull/123 -- PR title as-is
   TLDR: one sentence explaining WHY this PR exists (motivation, not technical details). Written in the resolved language.
   ```

   Guidelines for TLDR line:

   - Focus on WHY (motivation), not WHAT (implementation details)
   - One sentence, concise
   - No markdown, no formatting, no emoji
   - Do not repeat the PR title — add context beyond it

## Output

- If multiple PRs: separate each block with an empty line
- After generating all TLDRs, copy the complete text to clipboard:
  - macOS: pipe to `pbcopy`
  - Linux: pipe to `xclip -selection clipboard` or `xsel --clipboard --input`
  - If no clipboard tool available: print the text and note that clipboard copy failed
- Confirm to user: "Done, copied to clipboard"
