---
name: tune
description: Optimize a numeric outcome (latency, throughput, memory, cost) over 3+ knobs with a Taguchi designed experiment and S/N-ratio analysis instead of tweaking one knob at a time. TRIGGER — invoke when the task is picking values for several potentially interacting knobs (resource limits, timeouts, pool sizes, batch sizes, kernel or runtime parameters) and each measurement is expensive. DO NOT TRIGGER for finding the culprit behind a failure (use the taguchi or shrink skills), for a single knob (sweep it), or for measurements cheap enough to grid-search.
argument-hint: "[knob=low/mid/high ... goal=minimize|maximize|target]"
---

Tuning is the taguchi skill pointed at optimization instead of blame: same arrays, same run sheets, but the outcome is a number to improve and the analysis picks the best level of every knob at once. One L9 pass over four 3-level knobs reads out all four response curves in 9 runs; one-knob-at-a-time needs 12 runs and still misses interactions.

## Step 1 — design via the taguchi skill

Use the taguchi skill's steps 1-4 for factor definition, array selection, and the run sheet, with two tuning-specific defaults:

- Prefer 3 levels per knob — low, mid, high of the plausible range. Two levels see only a line; three see curvature, which is where optima live. L9 fits four 3-level knobs, L18 fits seven plus one binary.
- Run every row 2+ times. Variance per row is data here, not noise to average away — the S/N analysis below needs it.

Generate the sheet with the taguchi skill's `scripts/design.py` (`../taguchi/scripts/design.py` from here) — the array, the columns and the dummy treatment are mechanical, and a hand-built sheet is where a silent transcription error enters.

Keep it in the journal (`../taguchi/scripts/experiment.py new ... --repeats 3`) and let `../taguchi/scripts/run.py` execute the sheet — a benchmark is a command, so the array is one invocation with `--metric 'p95=([0-9.]+)'` instead of a dozen hand-run measurements, and the per-row repeats the S/N ratio needs come out balanced.

Measure the current configuration first, before the array. It is the reference every S/N number is judged against, and it is the cheapest check that the measurement harness reports what you think it does.

## Step 2 — pick the S/N ratio for the goal

Taguchi's signal-to-noise ratio folds "good on average" and "stable" into one number computed per row from its repeats y1..yn. Higher is always better:

| Goal | S/N per row |
| --- | --- |
| Minimize (latency, RSS, cost) | −10·log10(mean(y²)) |
| Maximize (throughput, hit rate) | −10·log10(mean(1/y²)) |
| Hit a target (offset, utilization) | 10·log10(ȳ²/s²) |

## Step 3 — main effects on S/N

Exactly the taguchi skill's column-wise analysis, applied to S/N: for each knob, average the S/N over all rows at each level; the best level is the highest mean; Δ between best and worst level ranks how much each knob matters. Knobs with flat Δ are free — set them by cost or convenience.

Do not compute decibels by hand. The taguchi skill's `scripts/analyze.py` takes the goal and does the whole pass — per-row S/N, level means, ranking, the permutation p that says which Δ is noise, and the predicted optimum:

```bash
python3 ../taguchi/scripts/experiment.py csv latency > results.csv
python3 ../taguchi/scripts/analyze.py results.csv --goal minimize
python3 ../taguchi/scripts/analyze.py results.csv --goal target=200
```

One CSV row per array row, repeats in `y1..yn` columns — the repeats are what the S/N ratio is computed from, so a single-column sheet only supports minimize and maximize.

The predicted optimum is the combination of every knob's best level. It is usually not a row of the array — that is expected, the array sampled the space, the analysis extrapolated.

`--goal target=VALUE` does not rank on S/N alone: the nominal-the-best ratio scores stability and is blind to the value you are aiming at, so ranking by it recommends the most stable knob setting regardless of where the mean lands. The script prints step 5's two-step answer instead — stability knobs at their highest-S/N level, the knobs flat on S/N set to land the mean on the target, and the predicted mean printed next to the target so the miss is visible.

A pass/fail sheet has no S/N at all. `analyze.py` says so and reads it as blame rather than optimization: the best level of a failure-rate table is the level holding the failures, which is a recommendation pointing exactly backwards.

## Step 4 — confirmation run, mandatory

Run the predicted optimum. Matches or beats the best array row → done. Falls clearly short of the prediction → the additivity assumption broke, interactions dominate. On a 2-level array, fold the design over per the taguchi skill's step 7; on L9 or L18 fold-over de-aliases nothing (its guarantee is a 2-level construction), so run the full factorial on the two highest-Δ knobs, or re-center with a zoom round.

## Step 5 — two refinements when it matters

- **Variance first, mean second**: when the goal is a target value, first set the knobs that move S/N (stability), then steer onto the target with a knob that moves the mean but barely moves S/N. Chasing the mean first bakes the noise in.
- **A knob range wide enough to break the run is normal on the first pass**: rows that crash or time out come back as failures rather than numbers, and the first array's job is then to say which levels are unrunnable. Narrow to the survivable range and run the array again — that is a zoom round with a different reason.
- **Zoom rounds for continuous knobs**: re-center the three levels around the winner with half the range and rerun the array. Iterate while the confirmation run keeps improving; two or three rounds usually land within measurement noise of the optimum.
