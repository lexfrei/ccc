---
name: pairwise
description: Generate a minimal pairwise covering array for factors with arbitrary mixed level counts, using the bundled deterministic generator. TRIGGER — invoke when a debugging or testing plan has 3+ independent factors whose level counts do not fit the fixed taguchi arrays (a 4-level factor, a 5-value enum, uneven mixes like 4x3x2x2) and each run is expensive. DO NOT TRIGGER when every factor has 2-3 levels (use the taguchi skill - balanced arrays support effect ranking), for a single factor (bisect it), or when runs are cheap enough to brute-force the full factorial.
argument-hint: "[factor=level1,level2,... ...]"
---

A pairwise covering array guarantees every combination of levels of every factor pair appears in at least one run, in close to the minimal number of runs. Any behavior driven by one factor or a two-factor interaction is guaranteed to fire somewhere in the array — that is the same trigger guarantee the taguchi arrays give, without their fixed 2-3-level shapes.

The tradeoff: covering arrays are not balanced. Levels appear unequal numbers of times, so averaging outcomes per level is not a fair comparison between factors. Use this skill to make the bug fire and to shortlist suspects; rank and confirm with balanced follow-ups.

## Step 1 — factors and levels

Same rules as the taguchi skill: factors must be independently settable, every level discrete and articulable, observable-but-unsettable factors recorded as covariates. Level counts are unrestricted — that is the point of this skill.

## Step 2 — generate the run sheet

Run the bundled generator (relative to this skill's base directory):

```bash
python3 scripts/pairwise.py "net=fast,slow,flaky,off" "browser=chrome,firefox,safari" "os=linux,macos"
```

It prints a markdown run sheet plus the run count against the full factorial. The output is self-verified: the script crashes rather than print an array with an uncovered pair. It restarts the greedy search from 64 seeds and keeps the shortest array — the seeds cost milliseconds, the runs they save cost CI round-trips (`--restarts` trades one for the other, `--json` emits the rows for a driver script).

**Combinations that cannot be run go in as constraints, not as rows you quietly skip.** Safari does not run on Linux; version X does not build against Y. Dropping such a row by hand takes its pairs down with it and the coverage guarantee is gone without a word:

```bash
python3 scripts/pairwise.py "browser=chrome,firefox,safari" "os=linux,macos" "net=fast,slow" \
    --exclude "browser=safari & os=linux"
```

Excluded rows are never generated, pairs that no legal row can contain leave the target set, and everything still reachable stays covered.

Present the sheet with concrete values and execute like the taguchi skill's run plan (randomize order under environment drift; for flaky bugs repeat the whole array N times, N ≥ ln(0.05)/ln(1−p) from the observed repro probability p).

## Step 3 — analyze by failure pattern, not by means

Because the array is unbalanced, skip level means. Work from the failing rows directly:

- For each factor, intersect its values across all failing rows. A factor stuck on one level in every failing row is a prime suspect.
- A factor that spans most of its levels across failing rows is likely innocent.
- Two factors jointly constant across failures point at their interaction — the pair guarantee ensured at least one such row existed.

## Step 4 — confirm

Same discipline as the taguchi skill: an accusation run (suspect levels on an otherwise-innocent config, must fail) and an acquittal run (a failing row with the suspect moved to an innocent level, must pass). If the shortlist has 2-3 suspect factors and the pattern is unclear, run their full factorial, or re-encode just the suspects at 2-3 levels and hand them to the taguchi skill for a balanced ranking pass.
