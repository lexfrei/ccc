# review-toolkit

Two review skills that share one verdict model. A review opens with **LGTM** or **NOT LGTM**, and the verdict is decided only by defects the diff introduced, worsened, or interacts with — attribution is computed from git at the merge base, never taken from anyone's claim. Pre-existing defects are still reported in full, in a separate section, and routed to an issue, a parked branch, or a memory entry instead of blocking. Remedies stay in the defect's layer: changed logic needs a test in the existing test surface, fixed prose is its own deliverable, and a new checker or guard script is never a merge condition. On re-review rounds every finding carries a git-computed origin (feature or churn) so a review loop that has started reviewing its own output is diagnosed instead of spinning.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install review-toolkit@claude-code-companions
```

## Skills

### branch-review

Review the current branch (or a named path or branch) in isolation against the branch it merges into, without switching the user's checkout — a temporary worktree is used when the active branch is not the target. Diff scope is the merge base, excluding lock files, vendored and generated code. Criteria cover bugs, security, leaked secrets, error handling, tests as an executable contract (valid and rejected use both), comments that stand in for fixes, comments that say WHAT instead of WHY, regressions of any size, and documentation the diff made wrong; a recommendation that names a helper or API has to quote that symbol's definition, a name alone is not advice. `--ticket` adds a compliance section against a GitHub issue, Jira, Linear, or Notion ticket; `--round1-head` enables churn diagnostics on later rounds; `--nitpick` turns on pedantic mode. `--type kernel` switches to patch-series mode: each commit is reviewed on its own, and a checklist of what mailing-list reviewers actually bounce applies — WHY-only commit bodies, one-line in-code comments, no invented vocabulary, no universal claims without a grep, only reachable failure modes described, error strings that name the case the user hits. Invoked as `/branch-review`.

### pr-review

Draft a GitHub PR review with inline comments. A readiness gate first: merge conflicts or red code-related CI stop the review with a fix-it note and no verdict, or with `NOT LGTM` when the mechanism by which the diff breaks a red check is established. Then a five-frame substance pass (is the problem real and rooted in this repo, is the approach worth its permanent cost, tradeoffs and scope, docs in sync, code quality), a cascade into `branch-review`, a sequential Claude plus Codex analysis of the PR diff with every finding cross-verified, and a draft presented for approval. Process and provenance requirements (commit format, sign-off, AI use and its disclosure) come from the project's published contract — `CONTRIBUTING.md`, `AGENTS.md`, and the policies they link, read at the base branch — and block only on a clause it states; style alone never proves AI authorship. A value/design gate can block a PR even when the code is flawless — wrong layer, root cause upstream, maintenance cost out of proportion to the value. Publishing to GitHub is opt-in via `--publish`; without it the draft is the deliverable. A published LGTM is an `APPROVE` only when the PR can merge right now, otherwise a `COMMENT` naming what it waits for; each finding is one item (what, where, fix) that lives either inline on its diff line or in the body, never both. A reviewer with write access syncs a branch mechanically and approves fork CI runs per `references/maintainer-actions.md` instead of sending the author back for it. Invoked as `/pr-review` on a PR URL, `owner/repo#N`, a bare number, or "this PR".

## Extending

Project-specific criteria belong under a `--type` value with its own gated section in `branch-review/SKILL.md`, written from bounces that actually happened rather than from style guides; the `kernel` section is the template, each of its items traceable to a reviewer's reply. Keep the verdict model untouched when adding criteria: new items decide what counts as a finding, never how attribution or the origin mark work.
