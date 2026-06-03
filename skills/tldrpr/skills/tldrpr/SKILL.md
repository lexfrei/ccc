---
name: tldrpr
description: Generate plain-text TLDR for PRs (for Slack, copied to clipboard). Each entry includes change scope (+N/-M lines, K files), a 1-5 star review-effort rating (time to review) and a 1-5 star user-value rating (how much it matters to users) so the reader can both budget time and prioritise before opening the PR.
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

   ### Review-effort scale

   - **★ trivial** — docs-only, comments, version bump, single-line fix, generated-file regeneration. Reviewer needs ~5 minutes.
   - **★★ small** — localized bug fix, single-component change, mechanical refactor with no behavior change. Reviewer needs ~15 minutes.
   - **★★★ medium** — bounded feature or refactor in one component, multi-file but contained scope. Reviewer needs ~30-60 minutes.
   - **★★★★ large** — cross-cutting change touching multiple subsystems, non-trivial refactor, breaking-change candidate, OR security-sensitive (auth, RBAC, secrets, crypto). Reviewer needs 1-2 hours.
   - **★★★★★ huge** — architectural reshape, new subsystem, major API/contract change, runtime-critical (controllers, schedulers, storage paths). Reviewer needs ≥ 2 hours and may need follow-up sessions.

   ### Review-effort signals

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

4. Assign a **user-value** rating from 1 to 5 stars — how much this PR matters to the people who *use* the product (end users, operators), independent of how hard it is to review. The two axes are orthogonal: a one-line fix can be ★★★★★ user value (it stops a crash everyone hits) while being ★ to review; a 2000-line refactor can be ★ user value (invisible internal cleanup) while being ★★★★ to review. Judge by user-facing impact, not size.

   ### User-value scale

   - **★ none/invisible** — internal refactor, CI/build, test-only, chore, comment or typo fix. Nothing a user can observe.
   - **★★ minor** — small quality-of-life or DX nicety, a cosmetic tweak, or an edge-case fix few users hit.
   - **★★★ moderate** — a real bug fix or useful feature that a meaningful subset of users will notice or have asked for.
   - **★★★★ high** — fixes a painful, common bug / removes a frequent blocker / ships a widely-wanted capability; most active users benefit.
   - **★★★★★ critical** — relieves severe or widespread pain: a security or data-loss fix users are exposed to, a crash or outage many hit, or an unblock for a previously-impossible workflow.

   ### User-value signals

   - **Up** if the PR fixes a crash / hang / data-loss / security issue users actually hit, resolves a reported (or repeatedly-reported) community issue, removes a documented footgun or silent-failure mode, or unblocks a common workflow. User-facing docs count here too — documenting a prerequisite that otherwise causes a silent hang is real user value even though it is ★ to review.
   - **Down** for internal refactors, test-only changes, CI/build, generated-file regeneration, or dependency bumps with no behavior change — low user value regardless of size.
   - Judge for the product's *users*, not its maintainers. When in doubt between two adjacent ratings, pick the **lower** one — over-claiming value is noisier than under-claiming (the opposite bias from review effort, where you round up).
   - Cap at ★★★★★, never below ★.

5. Generate the TLDR block in this exact format (plain text, no markdown):

   ```text
   https://github.com/owner/repo/pull/123 -- PR title as-is
   Scope: +N/-M lines, K files, C commits
   Review effort: ★★★☆☆ (medium) | User value: ★★★★☆ (high)
   TLDR: one sentence explaining WHY this PR exists (motivation, not technical details). Written in the resolved language.
   ```

   Guidelines for TLDR line:

   - Focus on WHY (motivation), not WHAT (implementation details)
   - One sentence, concise
   - No markdown, no formatting, no emoji
   - Do not repeat the PR title — add context beyond it

   Guidelines for the Scope and ratings lines:

   - Put the scope on its own line and the two ratings on the next line — keeps each line short and scannable in Slack.
   - Always render the scope as `+<additions>/-<deletions> lines, <files> files, <commits> commits` even when one of the numbers is 0 — the consistent shape is easier to scan in Slack.
   - On the ratings line render `Review effort: <stars> (<word>) | User value: <stars> (<word>)`. Review-effort words are `(trivial)`, `(small)`, `(medium)`, `(large)`, `(huge)`; user-value words are `(none)`, `(minor)`, `(moderate)`, `(high)`, `(critical)`.
   - Always include the literal-word bucket in parentheses after each star group — the stars communicate at a glance; the word is for screen-reader and search-friendliness.
   - The stars and words are in English regardless of `--lang`; only the TLDR sentence follows `--lang`, and the scope counts are locale-neutral.
   - The two axes are independent: a one-line fix can be `★☆☆☆☆ (trivial)` to review yet `★★★★★ (critical)` for users, and a huge refactor the reverse. Rate each on its own merits, never copy one onto the other.

## Output

- If multiple PRs: separate each block with an empty line.
- After generating all TLDRs, copy the complete text to clipboard:
  - macOS: pipe to `pbcopy`
  - Linux (Wayland): pipe to `wl-copy`
  - Linux (X11): pipe to `xclip -selection clipboard` or `xsel --clipboard --input`
  - If no clipboard tool available: print the text and note that clipboard copy failed.
- Confirm to user: "Done, copied to clipboard".
