# review-toolkit

Three review skills. `pr-review` reviews a GitHub PR, `series-review` reviews what a subsystem has become across many merged PRs, and `branch-review` reviews a local branch. In `pr-review`, judging whether a change should exist is the owner's decision: the agent prepares it as a short card and blocks only on what it can show in the sources.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install review-toolkit@claude-code-companions
```

## Skills

### branch-review

Review the current branch (or a named path or branch) in isolation against the branch it merges into, without switching the user's checkout — a temporary worktree is used when the active branch is not the target. Diff scope is the merge base, excluding lock files, vendored and generated code. Criteria cover bugs, security, leaked secrets, error handling, tests as an executable contract (valid and rejected use both), comments that stand in for fixes, comments that say WHAT instead of WHY, regressions of any size, and documentation the diff made wrong; a recommendation that names a helper or API has to quote that symbol's definition, a name alone is not advice. `--ticket` adds a compliance section against a GitHub issue, Jira, Linear, or Notion ticket; `--round1-head` enables churn diagnostics on later rounds; `--nitpick` turns on pedantic mode. `--type kernel` switches to patch-series mode: each commit is reviewed on its own, and a checklist of what mailing-list reviewers actually bounce applies — WHY-only commit bodies, one-line in-code comments, no invented vocabulary, no universal claims without a grep, only reachable failure modes described, error strings that name the case the user hits. Invoked as `/branch-review`.

### pr-review

Draft a GitHub PR review in five steps. Preparation pins the PR head in a detached worktree and runs a readiness gate: merge conflicts or red code-related CI stop the review with a fix-it note and no verdict, or with `NOT LGTM` when the mechanism by which the diff breaks a red check is established; a head that only gained a base merge since an LGTM gets the readiness checks only. The reviewer then judges the change from the diff and the tree alone, before the description, the bots and the project contract, and writes one word, `sound` or `doubt`; reads the context, including a subsystem theory note if the project keeps one and five worked cases, and revises the word once. A `doubt`, or a mechanical sign in the project's own code (a new hook, Job or ClusterRole, a new controller or package, state in annotations, a new check that can fail other changes, a new field on an API type or a new vocabulary other components read, a test reading another component's sources instead of going through its interface, code that serves every application gaining or extending knowledge of one particular application or third-party component), produces a five-line card for the owner: the owners the project names for the touched paths other than the reviewer and the author, or the user where it names no one else. On `doubt` nothing is published and the code pass waits for the owner's answer; on a sign with `sound` the review is published and an LGTM goes out as a `COMMENT` until the owner answers. The answer comes back through `--owner-answer`: a confirmed doubt becomes a blocker quoting it, a rejected one lifts the wait. The code pass is the reviewer's own reading plus one Codex pass in the same worktree, and every finding is checked against the sources before it enters the draft. A blocker is a path shown through the sources from a diff line to a wrong result, a quoted item the project wrote down that the diff contradicts, or, where the project tests the touched area, a behaviour change without a test that fails without it at the layer that owns the behaviour; when that layer cannot exercise the change in the PR, the draft names where the test belongs instead of blocking. Publishing is opt-in via `--publish`; an LGTM goes out as `APPROVE` only when the PR can merge now, otherwise as a `COMMENT` naming what it waits for. Invoked as `/pr-review` on a PR URL, `owner/repo#N`, a bare number, or "this PR".

Changed in 4.0.0. A doubt about design or value is no longer an agent blocker: it is a card for the owner, and becomes a blocker only when the owner agrees the change should not go in as it is; the published text then quotes the owner's answer in English or restates it, in a body the user approves. Removed: the five-frame substance pass, the parallel blocker lists (tests gate, no-regression gate, contract, value/design), the "Important Rules" restatement, the defect-class checklist, the cross-model merge tags, the cascade into `branch-review`, and the `--target` flag. Procedure lives in `references/` and is loaded only by the step that needs it.

### series-review

A pass over one subsystem, run by whoever manages the review queue rather than during a PR review. It takes the subsystem's paths, a commit and a period, reads the merged changes together without their descriptions, and writes one page for the owner: what the subsystem has become, the machinery it grew, contradictions with its theory note, and candidates for removal, each marked as not verified by execution. Because it works from a commit, it runs on any past state. The theory-note format, with an unapproved sample, is in `series-review/references/theory-note.md`.

## Extending

Project-specific criteria belong under a `--type` value with its own gated section in `branch-review/SKILL.md`, written from bounces that actually happened rather than from style guides; the `kernel` section is the template, each of its items traceable to a reviewer's reply. Keep the verdict model untouched when adding criteria: new items decide what counts as a finding, never how attribution or the origin mark work.
