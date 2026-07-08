---
name: tldrpr
description: Generate plain-text TLDR for PRs (for Slack, copied to clipboard). Each entry includes change scope (+N/-M lines, K files), a 1-5 star review-effort rating (time to review) and a 1-5 star outcome rating whose axis depends on the change — Pain relieved for fixes, Joy for features, Impact for internal work — so the reader can both budget time and prioritise before opening the PR.
argument-hint: "<pr-url-or-ref> [pr-url-or-ref] ... [--lang <language>] [--no-copy]"
---

Generate a plain-text TLDR summary of one or more Pull Requests for pasting into Slack. No markdown formatting — just plain text. Result is copied to clipboard by default; pass `--no-copy` to print the text only and leave the clipboard untouched (useful when another tool consumes the output).

## Arguments

Parse `$ARGUMENTS` for:

- One or more PR references in any of these formats:
  - Full URL: `https://github.com/owner/repo/pull/123`
  - Short ref: `owner/repo#123`
- `--lang <language>` — language for the TLDR line (e.g. `en`, `ru`, `de`). If omitted, use the same language the user communicates in during this conversation.
- `--no-copy` — do not copy the result to the clipboard; print the text only. Default (flag absent) copies to clipboard as before.

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

4. Assign the **outcome** rating — a 1-5 star score on a single axis whose *label* depends on what the PR does for the people who use the product. First pick the axis, then rate on it. The outcome axis is orthogonal to review effort: a one-line fix can relieve ★★★★★ pain while being ★ to review; a 2000-line refactor can be ★ internal Impact while being ★★★★ to review. Judge by user-facing outcome, not size.

   ### Pick the axis

   Default to the PR's Conventional-Commit type in the title, then override by the actual diff when the title lies — a `feat:` whose diff only fixes a regression is Pain; a `fix:` that mostly ships a new capability is Joy. The type is a signal, not a verdict.

   - **Pain relieved** — `fix`, `revert`, a `perf` that removes a regression or slowness users feel, a `docs` change that documents a footgun or silent-failure prerequisite. Rates how much hurt the PR takes away.
   - **Joy** — `feat`, a `perf` that delivers a wanted speedup, a `docs` change that ships a genuinely new guide or capability. Rates how much the PR delights or empowers users.
   - **Impact (internal)** — `chore`, `ci`, `test`, `build`, `refactor`, `style`. Maintainer-only plumbing a user cannot observe; almost always ★.

   ### Pain-relieved scale (how strong a painkiller the fix is)

   - **★ aspirin** — a trivial, barely-felt annoyance; an edge case almost no one hits.
   - **★★ ibuprofen** — a small but real irritation a modest slice of users feel.
   - **★★★ codeine** — a genuine bug a meaningful subset of users hit or have reported.
   - **★★★★ oxycodone** — a frequent, painful blocker; most active users feel the relief.
   - **★★★★★ morphine** — severe or widespread agony: a security / data-loss fix users are exposed to, or a crash / outage / hang many hit.

   ### Joy scale

   - **★ negligible** — a capability almost no one will notice.
   - **★★ nice** — a pleasant quality-of-life or DX nicety.
   - **★★★ useful** — a useful, wanted feature a meaningful subset of users will reach for.
   - **★★★★ wanted** — a widely-wanted capability most active users benefit from.
   - **★★★★★ delight** — a long-requested or workflow-unlocking capability that makes a previously-impossible thing possible.

   ### Impact (internal) scale

   - **★ internal** — invisible plumbing (refactor, CI, tests, build, chore). The default for this axis.
   - **★★ internal+** — internal work with an indirect user upside (reliability or maintainability that unblocks later fixes). Use sparingly; never higher — if a user can observe it, it belongs on Pain or Joy instead.

   ### Outcome signals

   - **Up** on Pain when the PR fixes a crash / hang / data-loss / security issue users actually hit, resolves a (repeatedly-)reported community issue, or removes a documented footgun. User-facing docs that prevent a silent hang count as real Pain relief even though they are ★ to review.
   - **Up** on Joy when the PR ships a capability users asked for, removes a long-standing limitation, or unlocks a workflow that was impossible before.
   - **Down** to Impact ★ for internal refactors, test-only changes, CI/build, generated-file regeneration, or dependency bumps with no behavior change — regardless of size.
   - Judge for the product's *users*, not its maintainers. When in doubt between two adjacent ratings, pick the **lower** one — over-claiming outcome is noisier than under-claiming (the opposite bias from review effort, where you round up).
   - Cap at ★★★★★, never below ★ (Impact caps at ★★).

5. Generate the TLDR block in this exact format (plain text, no markdown):

   ```text
   https://github.com/owner/repo/pull/123 -- PR title as-is
   Scope: +N/-M lines, K files, C commits
   Review effort: ★★★☆☆ (medium) | Pain relieved: ★★★★☆ (oxycodone)
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
   - On the ratings line render `Review effort: <stars> (<word>) | <outcome-axis>: <stars> (<word>)`, where `<outcome-axis>` is exactly one of `Pain relieved`, `Joy`, or `Impact` per the axis picked in step 4. Review-effort words are `(trivial)`, `(small)`, `(medium)`, `(large)`, `(huge)`; Pain-relieved words are `(aspirin)`, `(ibuprofen)`, `(codeine)`, `(oxycodone)`, `(morphine)`; Joy words are `(negligible)`, `(nice)`, `(useful)`, `(wanted)`, `(delight)`; Impact words are `(internal)`, `(internal+)`.
   - Always include the literal-word bucket in parentheses after each star group — the stars communicate at a glance; the word is for screen-reader and search-friendliness.
   - The stars and words are in English regardless of `--lang`; only the TLDR sentence follows `--lang`, and the scope counts are locale-neutral.
   - The two axes are independent: a one-line `fix` can be `★☆☆☆☆ (trivial)` to review yet `★★★★★ (morphine)` Pain relieved, and a huge `refactor` can be `★★★★☆ (large)` to review yet `★☆☆☆☆ (internal)` Impact. Rate each on its own merits, never copy one onto the other.

   Example ratings lines, one per outcome axis:

   ```text
   Review effort: ★☆☆☆☆ (trivial) | Pain relieved: ★★★★★ (morphine)
   Review effort: ★★★☆☆ (medium) | Joy: ★★★☆☆ (useful)
   Review effort: ★★★★☆ (large) | Impact: ★☆☆☆☆ (internal)
   ```

## Output

- If multiple PRs: separate each block with an empty line.
- If `--no-copy` is set: print the complete text only, skip every clipboard step, and confirm with "Done" — do not attempt `pbcopy`/`wl-copy`/`xclip` and do not print a clipboard-failure note.
- Otherwise, after generating all TLDRs, copy the complete text to clipboard:
  - macOS: pipe to `pbcopy`
  - Linux (Wayland): pipe to `wl-copy`
  - Linux (X11): pipe to `xclip -selection clipboard` or `xsel --clipboard --input`
  - If no clipboard tool available: print the text and note that clipboard copy failed.
- Confirm to user: "Done, copied to clipboard".
