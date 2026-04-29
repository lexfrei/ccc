---
name: tldrpr
description: Generate plain-text TLDR for PRs (for Slack, copied to clipboard). Each entry includes change scope (+N/-M lines, K files) and a 1-5 star review-effort rating so the reader can budget time before opening the PR.
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

1. Fetch PR metadata, scope, and file list:

   ```bash
   gh pr view <NUMBER> --repo <OWNER>/<REPO> --json title,body --jq '{title, body: .body[:2000]}'
   gh api "repos/<OWNER>/<REPO>/pulls/<NUMBER>" --jq '{additions, deletions, changed_files, commits}'
   gh api "repos/<OWNER>/<REPO>/pulls/<NUMBER>/files" --jq '.[] | "\(.status) +\(.additions)/-\(.deletions) \(.filename)"'
   ```

2. Compute the **scope** line from the metadata: `+N/-M lines, K files, C commits` (one space between fields, no rounding).

3. Assign a **review-effort** rating from 1 to 5 stars (`★` filled, `☆` empty — render as `★★★☆☆`). The rating is a judgment call informed by the file list and diff, NOT a pure mechanical line count. Use the heuristic below:

   ### Star scale

   - **★ trivial** — docs-only, comments, version bump, single-line fix, generated-file regeneration. Reviewer needs ~5 minutes.
   - **★★ small** — localized bug fix, single-component change, mechanical refactor with no behavior change. Reviewer needs ~15 minutes.
   - **★★★ medium** — bounded feature or refactor in one component, multi-file but contained scope. Reviewer needs ~30-60 minutes.
   - **★★★★ large** — cross-cutting change touching multiple subsystems, non-trivial refactor, breaking-change candidate, OR security-sensitive (auth, RBAC, secrets, crypto). Reviewer needs 1-2 hours.
   - **★★★★★ huge** — architectural reshape, new subsystem, major API/contract change, runtime-critical (controllers, schedulers, storage paths). Reviewer needs ≥ 2 hours and may need follow-up sessions.

   ### Rating signals

   Apply these adjustments on top of a baseline derived from line count:

   - Baseline by net code lines (additions + deletions, excluding lockfiles, vendored deps, generated code):
     - `< 20` → ★
     - `20-100` → ★★
     - `100-500` → ★★★
     - `500-2000` → ★★★★
     - `≥ 2000` → ★★★★★
   - **+1 star** if the PR touches RBAC manifests (`*.rbac.yaml`, `clusterrolebinding-*.yaml`, anything granting permissions to groups/SAs), authentication code, secrets handling, crypto, or admission webhooks.
   - **+1 star** if the PR touches Go controllers, reconcilers, REST registries, schedulers, or other runtime-critical paths in `pkg/` / `internal/` / `cmd/`.
   - **+1 star** if the PR is marked breaking (`feat!:`, `fix!:`, `BREAKING CHANGE:` footer, or a labeled major-version bump).
   - **−1 star** (cap at ★) if the PR is purely docs (`*.md`, `docs/`), generated regeneration (`zz_generated.*`, `*.pb.go`), or vendored-dependency deletion.
   - Cap the result at ★★★★★. Never go below ★.

   When in doubt between two adjacent ratings, pick the higher one — the rating is meant to budget review time, and over-budgeting is cheaper than under-budgeting.

4. Generate the TLDR block in this exact format (plain text, no markdown):

   ```text
   https://github.com/owner/repo/pull/123 -- PR title as-is
   Scope: +N/-M lines, K files, C commits | Review effort: ★★★☆☆ (medium)
   TLDR: one sentence explaining WHY this PR exists (motivation, not technical details). Written in the resolved language.
   ```

   Guidelines for TLDR line:

   - Focus on WHY (motivation), not WHAT (implementation details)
   - One sentence, concise
   - No markdown, no formatting, no emoji
   - Do not repeat the PR title — add context beyond it

   Guidelines for the Scope/Effort line:

   - Always render the scope as `+<additions>/-<deletions> lines, <files> files, <commits> commits` even when one of the numbers is 0 — the consistent shape is easier to scan in Slack.
   - Always include the literal-word complexity bucket in parentheses after the stars (`(trivial)`, `(small)`, `(medium)`, `(large)`, `(huge)`). The stars communicate at a glance; the word is for screen-reader and search-friendliness.
   - The stars-and-word are in English regardless of `--lang` — the rest of the line is locale-neutral counts.

## Output

- If multiple PRs: separate each block with an empty line.
- After generating all TLDRs, copy the complete text to clipboard:
  - macOS: pipe to `pbcopy`
  - Linux: pipe to `xclip -selection clipboard` or `xsel --clipboard --input`
  - If no clipboard tool available: print the text and note that clipboard copy failed.
- Confirm to user: "Done, copied to clipboard".
