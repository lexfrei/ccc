---
name: pr-review
description: >
  Draft a GitHub PR review: an own judgement of the change before the author's framing, a five-line card for the owner when that judgement doubts the change, a code pass by two models with every finding checked against the sources, and an LGTM or NOT LGTM verdict; publish only with `--publish` after the user approves the draft. An LGTM goes out as APPROVE only when the PR can merge right now.
  TRIGGER: invoke whenever the user asks to review, audit, or quality-check a GitHub Pull Request — by URL, `owner/repo#N`, bare number, or a "this PR" / "этот PR" reference resolvable from context. Examples — "review PR 2541", "сделай ревью на https://github.com/foo/bar/pull/123", "оцени этот PR". DO NOT trigger for replying to existing review comments, labeling or triaging, a TLDR, or questions about a branch with no PR.
argument-hint: "[PR number] [--publish] [--ticket URL|ID] [--owner-answer TEXT]"
---

Three roles: the user invokes this skill and approves any publication; the owner decides whether the change belongs in the project, found per `references/preparation.md`; the caller receives the result in draft mode, and is the user or the agent that invoked the skill.

Default mode is draft: the result goes to the caller and nothing is sent to GitHub. `--publish` allows publication after the user approves the draft. `--owner-answer` carries the owner's answer to a card; an answer to that card already in the conversation counts the same. The answer stays valid for a later head while that head does not change what the card was about: the own diff is unchanged as the base-merge short path of `references/preparation.md` checks it, or the card's sign still fires on the same lines; otherwise the card is raised again.

## Step 0: Preparation

Follow [`references/preparation.md`](references/preparation.md). A gate exit or the short path goes straight to Step 5. Later steps work inside the worktree.

## Step 1: Own reading

Input: `git diff origin/<base>...<head>` and the changed files at head, plus whatever files in the worktree you need to understand what the change does and where it sits. Not yet: the PR title and body, commit messages (`git log` shows them; do not read it), bot and review comments, linked issues and designs, the project's contributing contract, the cases file. They carry the author's framing, and a judgement formed after them checks the frame instead of the change.

Judge the change as an engineer who will have to maintain this code, not as a checker of correctness. Say `doubt` when you would not take it as it is into a project you maintain, for one of these reasons: the mechanism sits in the wrong place (another component owns the fact, or the cause could be fixed where it arises); it carries far more machinery than the problem needs; it repairs something this project itself did a step earlier; or it is built on something that is not yet decided or has no consumer. Say `sound` when it is a proportionate change in a reasonable place; most changes are. Bugs, style, naming and missing tests are not reasons for `doubt`. Do not soften a doubt because the code is correct and tested, and do not invent one: a wrong `doubt` costs a maintainer thirty seconds of reading, a wrong `sound` costs a merge.

Write down exactly three lines before reading anything else:

```text
WHAT: <one sentence, in plain words, what this change is>
WORD: <sound or doubt>
WHY: <one sentence: for doubt, the simpler or better-placed alternative and what it gives up; for sound, why nothing simpler would do>
```

## Step 2: Context and one revision

Read, in order: the theory note of the touched subsystem at the base branch (where it lives, and why the base: [`../series-review/references/theory-note.md`](../series-review/references/theory-note.md)); [`references/cases.md`](references/cases.md); the project's contract (found and read per `references/preparation.md`); the PR title and body, its commits, linked issues, the ticket if given, and any design the PR or its commits cite. A ticket requirement the change does not meet is an item of type (b) in Step 5.

Revise the word once, and write one line: `stayed` or `changed`, and why. An accepted design is input, not authority: a clause of it counts under (b) only if this revision keeps it, a clash between a clause and a stated project principle goes on the card, and a PR that does not name each deviation from the design it implements gets an optional note asking it to.

## Step 3: The fork

A card goes to the owner when the word is `doubt`, or when a sign fires. The signs, from the diff of the project's own code, not vendored or generated files: a new hook, Job, one-off migration script, or role or permission set (a ClusterRole, an IAM policy); a new controller, service or package; state kept in annotations, labels or other metadata instead of a declared field; a new check that can fail other changes (a pinned count, a naming or layout convention, a lint or test constraining files it does not own); a new field on an API type, or a new vocabulary other components read (label, annotation, configuration or quota keys, value keys shared beyond one chart or module, a string field evaluated as a language); a test or lint that reads another component's sources instead of going through its interface (building or rendering it, calling its API, loading an artifact generated from the code under test); code that serves every application or consumer (a controller, an API type, a shared package or library, a framework layer, the platform's own chart, packaging or monitoring) gaining or extending knowledge of one particular application, plugin, provider or third-party component: its kinds or types, API groups, labels, value keys, formats, image or artifact names, or files. This counts even where the file already held such knowledge before the change. An application's own chart or package and its own test suite are not such code, nor is a list whose job is to enumerate components unless an entry carries behaviour beyond being listed.

The card is five lines, in plain words:

1. What it is.
2. What the project itself did to need it.
3. The simplest alternative, and what it gives up.
4. What every upgrade or bump will have to do because of it.
5. The word, and what has not been verified by execution.

The card is addressed to its owner by name and is a hypothesis for a human, not a finding. On `doubt`, no review is published and Step 4 does not run until the owner answers. On a sign with `sound`, Step 4 runs and the review does not wait for the answer: with `--publish` it goes out, an LGTM as a `COMMENT` until the owner answers (`references/publishing.md`). Without an answer nothing changes; the LGTM stays `COMMENT` and this skill publishes no reminder.

An owner other than the user gets the card as a PR comment posted before any review, or, without `--publish`, forwarded by the user (`references/publishing.md`, Card delivery). That owner's later PR comment counts as `--owner-answer`.

An answer that arrives after that `COMMENT` went out starts a new run with `--owner-answer`; its verdict and event follow `references/publishing.md` as usual, and a published review goes over the `COMMENT`. With the owner's answer, the card is not raised again, and Steps 1 and 2 still run and go into the draft. If the owner agrees the change should not go in as it is, that answer blocks under (b), quoted. If the owner accepts it, nothing waits, the draft quotes the answer in one line and asks where the acceptance is written down (the theory note's "Known debts", a decision record the theory note or the contract links, the contract). Once written, a later review of the same files or the same subsystem the acceptance names quotes it as the owner's recorded decision instead of raising the card again, and blocks under (b) only a diff that contradicts it; an acceptance written nowhere covers this PR only and is not precedent. Either way, Step 4 and the verdict run as usual.

## Step 4: Code pass

1. Your own reading of the diff against the sources at head: what the change breaks, on which input, in which variant or default.
2. One pass by a second model in the same worktree, per [`references/code-pass.md`](references/code-pass.md).
3. Every finding, yours or the second model's or a bot's, is traced through the sources, guards included, before it enters the draft. One that does not survive is listed as dismissed, with the reason.
4. A test added or changed in the PR is code under review, not evidence: for each expected value, say where it comes from — a specification, another implementation run on the same input, or the author's hand.

## Step 5: Verdict and publication

The blocker rule:

> Blocks only what is shown: (a) a path through the sources at head from a line of the diff to a wrong result — for a regression, together with the state at the merge base; (b) a quoted item the project itself wrote down (contract, theory note, a clause of an accepted design that Step 2 kept, the owner's answer to a card) that the diff contradicts; (c) in a project that tests the area it touches, a change of behaviour without a test that fails without it, at the layer that owns the behaviour; a test at another layer that restates another component's values or reads its sources does not count, and when the owning layer cannot exercise the change in this PR, (c) does not block and the draft names where the test belongs, for the maintainer to accept or refuse. A doubt about meaning without (a), (b) or (c) goes on the card, never into the published body. Everything else is an optional note.

The verdict is `NOT LGTM` when any blocker stands, `LGTM` otherwise. The GitHub event, findings, inline comments and publication are in [`references/publishing.md`](references/publishing.md); maintainer actions in [`references/maintainer-actions.md`](references/maintainer-actions.md).

The draft carries: the three lines of Step 1, the line of Step 2, the card if raised, the verdict and its event, the body, each inline comment with path and line, and the dismissed findings. After a gate exit or the short path it is the note `references/preparation.md` describes. Without `--publish`, stop there; with it, never publish a review while a `doubt` card is waiting for the owner.
