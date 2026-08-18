---
name: taguchi
description: Plan a minimal set of debugging or testing runs with a Taguchi orthogonal array instead of changing one factor at a time. TRIGGER — invoke proactively whenever a debugging, tuning, or repro plan involves 3+ independent candidate factors (flags, versions, environments, config values) and each run is expensive (slow build, CI round-trip, flaky repro, hardware cycle); the moment the plan starts to look like "try A, then B, then A+B" this skill replaces it. Also on explicit ask - "taguchi", "orthogonal array", "DOE", "design of experiments", "plan the runs", "reduce iterations". DO NOT TRIGGER for a single suspected factor (bisect it), runs cheap enough to brute-force the full factorial, factors that cannot be set independently, or pure code-reading investigation with no experiment loop.
argument-hint: "[factor=level1/level2 ...]"
---

Replace one-factor-at-a-time debugging with a designed experiment. An orthogonal array covers **every pair of factor levels** in a handful of runs, so any behavior caused by one factor or by a two-factor interaction is guaranteed to show up in at least one run. 11 binary factors need 12 runs instead of 2048.

Every run changes several factors at once. That feels wrong to debugging intuition — resist the urge to "change only one thing". The analysis is column-wise (compare all runs where factor X was at level 1 vs level 2), not row-wise, and the balance of the array is what makes that comparison fair.

## Step 0 — gate

Confirm all of these before proceeding; otherwise use the cheaper tool and say so:

- **3+ candidate factors.** One factor → plain bisection. Two factors → just run the 2×2 (4 runs).
- **Runs are expensive.** If a run is seconds, brute-force the full factorial instead.
- **Factors are independently settable.** If setting A=2 forces B=2, merge them into one factor.
- **At most ~11 factors** — that is the 2-level ceiling; 3-level factors cap out at 7 (plus one 2-level) in L18. More than that means the suspect list was never narrowed — shrink it first (the shrink skill in this plugin), then design the array for the survivors.
- **The array has to be meaningfully cheaper than the factorial.** Three 2-level factors are 4 runs against 8 — a 2x saving that does not pay for the ceremony or for confounding interactions. Below roughly 3x, run the factorial and read the interactions directly; `design.py` prints the ratio and says so.

Sibling skills cover the neighboring shapes: an expected single culprit among many boolean toggles → shrink; level counts that fit no array below → pairwise; optimizing knobs rather than hunting a culprit → tune.

## Step 1 — factors and levels

Build the factor table with the user (or from the debugging context). Force every factor to 2 or 3 discrete levels:

- Boolean or on/off → 2 levels.
- Versions → current vs suspected-bad (2 levels), add a third only if a middle version genuinely discriminates.
- Continuous values (timeout, batch size, memory limit) → the two extremes of the plausible range; a midpoint only as a third level.
- A factor nobody can articulate a level for is not a factor — drop it or fix it at its current value.
- A factor you can observe but not set (region, node shape, neighbor load) is a covariate, not a column: record its value for every run and check it during analysis (step 5).

## Step 2 — pick the array

Smallest array that fits all factors:

| Factors | Array | Runs | Full factorial would be |
| --- | --- | --- | --- |
| ≤3 × 2-level | L4 | 4 | 8 |
| ≤7 × 2-level | L8 | 8 | 128 |
| ≤4 × 3-level | L9 | 9 | 81 |
| ≤11 × 2-level | L12 | 12 | 2048 |
| 1 × 2-level + ≤7 × 3-level | L18 | 18 | 4374 |

Mixed 2- and 3-level factors: dummy treatment — a 2-level factor sits in a 3-level column with level 3 repeating level 1 (coverage holds, the repeated level just gets more runs). Its level means stay unbiased but rest on unequal run counts, so its Δ is noisier than the rest of the table — rank a dummy-treated factor against the others only when its effect clears the noise floor by a margin. Up to 4 factors total fit L9 this way at 9 runs; bigger mixes take L18. Extra columns beyond your factor count are simply left unassigned. Level counts that fit none of these shapes (a 4-level factor, uneven mixes) → the pairwise skill generates a covering array for arbitrary levels.

Do not assemble the sheet by hand. `scripts/design.py` picks the array, assigns the columns, applies the dummy treatment and prints the run sheet with concrete values:

```bash
python3 scripts/design.py "os=ubuntu,macos" "node=18,20" "lockfile=frozen,fresh"
python3 scripts/design.py "gc=on,off" "pool=8,16,32" "batch=1,10,100" --json
```

## The arrays

These tables are pairwise-balanced, and `scripts/arrays.py` re-checks that at import — a transposed digit raises instead of silently destroying the balance the analysis relies on. They are printed here to be read, not to be retyped: transcribing an L12 by hand is exactly the step the script exists to remove.

### L4 (3 factors × 2 levels, 4 runs)

```text
run  A B C
1    1 1 1
2    1 2 2
3    2 1 2
4    2 2 1
```

### L8 (7 factors × 2 levels, 8 runs)

```text
run  A B C D E F G
1    1 1 1 1 1 1 1
2    1 1 1 2 2 2 2
3    1 2 2 1 1 2 2
4    1 2 2 2 2 1 1
5    2 1 2 1 2 1 2
6    2 1 2 2 1 2 1
7    2 2 1 1 2 2 1
8    2 2 1 2 1 1 2
```

### L9 (4 factors × 3 levels, 9 runs)

```text
run  A B C D
1    1 1 1 1
2    1 2 2 2
3    1 3 3 3
4    2 1 2 3
5    2 2 3 1
6    2 3 1 2
7    3 1 3 2
8    3 2 1 3
9    3 3 2 1
```

### L12 (11 factors × 2 levels, 12 runs)

```text
run  A B C D E F G H I J K
1    1 1 1 1 1 1 1 1 1 1 1
2    1 1 1 1 1 2 2 2 2 2 2
3    1 1 2 2 2 1 1 1 2 2 2
4    1 2 1 2 2 1 2 2 1 1 2
5    1 2 2 1 2 2 1 2 1 2 1
6    1 2 2 2 1 2 2 1 2 1 1
7    2 1 2 2 1 1 2 2 1 2 1
8    2 1 2 1 2 2 2 1 1 1 2
9    2 1 1 2 2 2 1 2 2 1 1
10   2 2 2 1 1 1 1 2 2 1 2
11   2 2 1 2 1 2 1 1 1 2 2
12   2 2 1 1 2 1 2 1 2 2 1
```

### L18 (1 factor × 2 levels + 7 factors × 3 levels, 18 runs)

```text
run  A B C D E F G H
1    1 1 1 1 1 1 1 1
2    1 1 2 2 2 2 2 2
3    1 1 3 3 3 3 3 3
4    1 2 1 1 2 2 3 3
5    1 2 2 2 3 3 1 1
6    1 2 3 3 1 1 2 2
7    1 3 1 2 1 3 2 3
8    1 3 2 3 2 1 3 1
9    1 3 3 1 3 2 1 2
10   2 1 1 3 3 2 2 1
11   2 1 2 1 1 3 3 2
12   2 1 3 2 2 1 1 3
13   2 2 1 2 3 1 3 2
14   2 2 2 3 1 2 1 3
15   2 2 3 1 2 3 2 1
16   2 3 1 3 2 3 1 2
17   2 3 2 1 3 1 2 3
18   2 3 3 2 1 2 3 1
```

## Step 3 — run sheet

Assign each factor to a column and render the plan with concrete values, not level numbers:

| Run | OS | Node | Lockfile | Result |
| --- | --- | --- | --- | --- |
| 1 | ubuntu | 18 | frozen | |
| 2 | ubuntu | 20 | fresh | |
| 3 | macos | 18 | fresh | |
| 4 | macos | 20 | frozen | |

Open the journal before the first run. An array is 8-18 CI round-trips — hours or days, and more than one session; a plan that lives only in the chat is gone by the time the last row lands:

```bash
python3 scripts/experiment.py new "flaky lockfile" \
    --factor "os=ubuntu,macos" --factor "node=18,20" --factor "cache=warm,cold" \
    --repeats 2 --hypothesis "the fresh lockfile only breaks on node 18"
```

It designs the array, writes `.doe/<slug>.json`, and prints the sheet. `show` re-prints the state and what is still open, `record <slug> --run 3 --result fail --covariate region=eu` files an outcome, `csv <slug>` emits the file `analyze.py` reads, `close <slug> --verdict ...` ends it. **A session that finds an open experiment resumes it instead of designing a new one** — `experiment.py list`.

When a run is a command rather than a human errand, execute the sheet instead of shepherding it:

```bash
python3 scripts/run.py flaky-lockfile --cmd 'make test OS={os} NODE={node} CACHE={cache}'
python3 scripts/run.py latency --cmd './bench --pool {pool}' --metric 'p95=([0-9.]+)' --randomize
```

Exit code is the outcome unless `--metric` names a regex whose first group is a number. Repeats sweep the whole array rather than one row at a time, `--randomize` shuffles each sweep against environment drift, every result is written to the journal the moment it lands, and each run's output is kept under `.doe/<slug>-logs/`.

**Two baseline runs before the array, always.** All factors at their known-good levels must pass; all at their suspected-bad levels must fail. A failing good-baseline means the difference lives outside the factor list; a passing bad-baseline means the levels are not extreme enough or the repro needs repeats. Either way the array is about to be spent on a phantom — the shrink skill makes the same two runs mandatory for the same reason, and an array costs more than a bisection does. Record them with `experiment.py baseline <slug> --good pass --bad fail`; `run.py` refuses to execute a sheet whose baselines are missing.

Execution notes:

- Deterministic software: run in any order, once per row.
- Flaky or nondeterministic bug: repeat the whole array N times rather than repeating single rows — repetition count per row stays balanced. Size N from the repro probability p observed on the known-bad config: N ≥ ln(0.05)/ln(1−p) gives 95% confidence that a guilty row fails at least once (p=0.5 → 5, p=0.3 → 9, p=0.1 → 29). Total cost is rows × N — when that number comes out absurd, the response is wrong, not the array: switch to a numeric outcome (step 4).
- Environment that drifts between runs (hardware warm-up, cache state, quota): randomize run order so drift doesn't masquerade as a factor effect.

## Step 4 — record outcomes

One outcome per run: binary (fail/pass) or numeric (latency, RSS, error count). For flaky repros with repeats, record the failure count per row.

Prefer a numeric outcome over binary whenever one exists (latency, retry count, time-to-first-error): a continuous response discriminates levels in a single pass of the array, while a binary one pays the ×N repetition tax from step 3. Record the covariates from step 1 alongside the outcome of every run.

## Step 5 — main-effects analysis

Feed the finished sheet to `scripts/analyze.py` rather than averaging by hand — one CSV row per run, the factor columns from the sheet, a `result` column (numeric, or pass/fail), `result_1..n` for repeats, covariates in their own columns. `experiment.py csv` emits exactly that shape:

```bash
python3 scripts/experiment.py csv flaky-lockfile > results.csv
python3 scripts/analyze.py results.csv --covariate region
```

It prints the table below, ranks the factors, scores each one with a permutation test, computes the noise floor from the repeats, and flags the two outcomes that end the experiment early:

- **Nothing failed anywhere.** No listed factor drives the bug, the levels are not extreme enough, or the repro needs repeats. Back to step 1; another array will not help.
- **Everything failed.** A factor outside the list drives it, or the level you called innocent is not. Re-check the baselines from step 3.

For each factor, average the outcome over all runs at each level — the array's balance guarantees every other factor contributed equally to both sides:

| Factor | Level 1 mean | Level 2 mean | Effect (Δ) |
| --- | --- | --- | --- |
| OS | 0/2 fail | 2/2 fail | 1.00 |
| Node | 1/2 fail | 1/2 fail | 0.00 |
| Lockfile | 1/2 fail | 1/2 fail | 0.00 |

With repeats, establish the noise floor before ranking: the typical spread between repeats of the same row. A Δ below that spread separates nothing — the factor stays unranked until more repeats say otherwise.

Rank factors by Δ. Reading the verdict:

- **Clean split** (one level holds all failures, the other none) → prime suspect, but score it before believing it. With few failures spread over few runs, clean splits happen by luck: two failures in an L4 always split some factor cleanly, and 11 factors on an L12 with three failures produce about two innocent clean splits per array. `analyze.py` prints that expectation next to a permutation p per factor — use them to rank suspects, never to convict one.
- **Δ ≈ 0** → factor is innocent at these levels — stop iterating on it.
- **Two factors split cleanly at once, or all Δ are mid-range** → an interaction or a confound; go to step 7.

Before believing a clean split, check the recorded covariates: one that tracks the outcome is both a suspect in its own right and a hole in the balance the array guarantees only for assigned columns. A covariate implicated this way graduates to a real factor — find a way to set it and rerun.

## Step 6 — confirmation run

The analysis produces a hypothesis, not a verdict. Run two extra configurations before declaring root cause:

1. **Accusation**: suspect factor at its guilty level, everything else at innocent levels → must fail.
2. **Acquittal**: suspect factor at its innocent level, everything else exactly as in a failing run → must pass.

If either run contradicts the prediction, the effect is an interaction — go to step 7. A main-effects table alone is never sufficient proof of root cause.

## Step 7 — when effects are muddy

Orthogonal arrays confound interactions with main effects — that is the price of the run savings. When the signal is not clean, two exits:

- Two factors stand out → run their full factorial (4 or 9 runs) with everything else fixed and read the interaction directly.
- Several factors look muddy at once on L8 or L12 → fold the design over: rerun the same array with the two levels swapped everywhere and analyze all 16 or 24 runs together. Main effects come out clean of every two-factor interaction, for double the runs.

If it is still muddy after that, the factor list is missing the real variable — go back to step 1 rather than adding runs.
