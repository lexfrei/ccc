---
name: series-review
description: >
  Review what a subsystem has become across a series of merged PRs, not one PR: one page for the subsystem's owner with the subsystem in plain words, the growth of machinery, contradictions with its theory note, and candidates for removal. Run by whoever manages the review queue, on a schedule, never during a PR review.
  TRIGGER: invoke when the user asks for a series review, a subsystem review, or "what has <subsystem> become". DO NOT trigger for a single PR (use pr-review).
argument-hint: "--paths <path,path> [--commit <sha>] [--since YYYY-MM-DD] [--note <path>]"
---

Input: the subsystem's paths, a commit that fixes the state to judge (default `origin/<default branch>`), the start of the period (default fourteen days before that commit's date), and the subsystem's theory note if there is one (default: `THEORY.md` in the subsystem's directory; format in [`references/theory-note.md`](references/theory-note.md)). Nothing is published.

## 1. Collect

Work in a detached worktree at the commit, so nothing later is visible. A local clone with full history suffices; offline, skip the fetch:

```bash
git fetch --quiet origin
WT=$(mktemp -d)/series; git worktree add --detach "$WT" "<commit>"
git -C "$WT" log --first-parent --merges --since="<since>" --format='%H %s' -- <paths>
```

This lists the period's merges, newest first; the first parent of the oldest is the state before the series. Read each merge as `git -C "$WT" diff <merge>^1 <merge> -- <paths>`; where the project squashes or rebases, drop `--merges` and diff each commit against its parent.

Do not read PR descriptions, commit bodies, review threads or anything after the commit: they carry the authors' framing, and a past state must not see its future. Commit titles only identify changes.

## 2. Read

Read the subsystem at the commit as a whole, then the diffs in order, then the state before the series. Ask of the whole, not of each step, what a maintainer who knew only today's code would take out.

## 3. Write one page for the owner

At most 600 words.


1. **What it has become**, in plain words: what the subsystem does now, and what it did before the series.
2. **Growth of machinery** in the period, each item with the merge that added it: hooks and Jobs; state kept in annotations; waits, retries and refusals; names of other components (kinds, API groups, label keys, paths) inside it. Note where a change repairs something an earlier change in the same series did.
3. **Contradictions with the note**, each quoting the decision or the "does not know" line it breaks. Without a note, say so and list the decisions the series seems to have taken without writing them down.
4. **Candidates for removal**, each with what it would give up, and each marked "not verified by execution": first whole mechanisms (what happens, and to whom, if the mechanism is removed or moved elsewhere), then at most five smaller ones.

No verdict, no blockers, no issues filed: the owner decides.

Remove the worktree at the end: `git worktree remove --force "$WT"`.
