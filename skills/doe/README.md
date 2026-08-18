# doe

Design-of-experiments skills for cutting debugging and tuning iterations. Four methods ship today, each behind its own auto-triggering skill: `taguchi` (balanced orthogonal arrays, factor ranking), `pairwise` (covering arrays for arbitrary level mixes), `shrink` (group testing for single-culprit hunts), and `tune` (S/N-ratio knob optimization). The skills route to each other: the taguchi gate hands boolean single-culprit hunts to shrink, odd level counts to pairwise, and optimization to tune.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install doe@claude-code-companions
```

### Upgrading from taguchi

This plugin was previously published as `taguchi`. The marketplace renames map migrates an installed copy automatically on Claude Code v2.1.193 or later; on older versions run `/plugin install doe@claude-code-companions` once. The skill invocation changed from `/taguchi:taguchi` to `/doe:taguchi`.

## Skills

### taguchi

Plan a minimal set of debugging or testing runs with Taguchi orthogonal arrays. An orthogonal array covers every pair of factor levels in a handful of runs — 11 binary factors take 12 runs instead of 2048 — so any behavior driven by one factor or a two-factor interaction is guaranteed to appear in at least one run.

Invoked automatically when a debugging, tuning, or repro plan involves three or more independent candidate factors and each run is expensive (slow build, CI round-trip, flaky repro, hardware cycle). Also on explicit ask: `/doe:taguchi`, "orthogonal array", "design of experiments", "reduce iterations".

The workflow:

1. **Gate** — checks the problem actually fits: 3+ factors, expensive runs, independently settable levels, and an array meaningfully cheaper than the factorial (below ~3x, just run the factorial). Single factor → bisection; cheap runs → full factorial; more than ~11 factors → shrink the list first.
2. **Factors and levels** — every factor forced to 2 or 3 discrete levels; observable-but-unsettable factors are recorded as covariates and checked at analysis time.
3. **Array selection** — smallest of L4, L8, L9, L12, L18 that fits; dummy-treatment trick for mixed 2/3-level factor sets. `scripts/design.py` does the picking, the column assignment and the dummy treatment; `scripts/arrays.py` re-verifies every table's pairwise balance at import, so a corrupted array raises instead of loading.
4. **Run sheet** — the plan rendered with concrete values, two mandatory baseline runs (known-good must pass, known-bad must fail) before the array is spent, plus repetition sizing and run-order rules for flaky bugs and drifting environments.
5. **Outcome recording** — one outcome per run, numeric preferred over binary (a continuous response discriminates in a single pass, binary pays the repetition tax), covariates logged alongside.
6. **Main-effects analysis** — `scripts/analyze.py` reads the finished sheet as CSV: level means, ranking by effect size, noise floor from repeats, a permutation p per factor, the odds that a clean split is coincidence, covariate balance, and the two early exits (nothing failed / everything failed).
7. **Confirmation runs** — an accusation run and an acquittal run before any root-cause claim.
8. **Interaction fallback** — full factorial on the top-2 suspects when main effects are confounded.

### pairwise

Covering arrays for factors whose level counts fit none of the fixed taguchi shapes — a 4-level factor, a 5-value enum, uneven mixes like 4×3×2×2. A bundled deterministic generator (`skills/pairwise/scripts/pairwise.py`, stdlib-only, self-verifying) emits a near-minimal run sheet in which every pair of factor levels appears at least once. It restarts the greedy search from several fixed seeds and keeps the shortest array (3^4 takes 9 runs instead of 12, 2^11 takes 8 instead of 12), and `--exclude "browser=safari & os=linux"` keeps combinations that cannot be run out of the sheet without tearing a hole in the coverage, so anything driven by one factor or a two-factor interaction is guaranteed to fire. Covering arrays are not balanced, so the analysis works from failure patterns (levels constant across failing rows) instead of level means, and hands shortlisted suspects back to `taguchi` for balanced ranking.

### shrink

Group testing and delta debugging for the "which of these 30 toggles breaks it" shape: an expected single culprit (or small set) among many boolean suspects. Split-half finds one culprit in log2 n to 2·log2 n runs; the ddmin scheme handles multiple culprits; mandatory baseline runs (all-innocent must pass, all-suspect must fail) catch a wrong suspect list before the search starts. For flaky bugs the skill treats pass and fail asymmetrically — a fail is certain, a pass needs repeats before it can steer the search.

### tune

The taguchi machinery pointed at optimization: pick values for several interacting knobs (limits, timeouts, pool sizes) in one designed experiment instead of one-knob-at-a-time sweeps. Prefers 3-level knobs to capture curvature, computes Taguchi S/N ratios per goal (minimize, maximize, hit-a-target) through the same `analyze.py`, picks each knob's best level column-wise, and requires a confirmation run of the predicted optimum — with a top-2 factorial (or fold-over, on 2-level arrays only) when interactions break additivity, and zoom rounds for continuous knobs.

## Tests

Stdlib only, no runner required:

```bash
for t in skills/*/scripts/test_*.py; do (cd "$(dirname "$t")" && python3 "$(basename "$t")"); done
```

`test_design.py` also pins the arrays printed in `taguchi/SKILL.md` to the ones `arrays.py` uses, so the prompt and the code cannot drift apart.

## Extending

To add a larger array (L16, L27, ...), put it in `skills/taguchi/scripts/arrays.py`: the balance check runs at import, so an unbalanced table fails immediately rather than after a wasted experiment. Then add it to `CANDIDATES` in `design.py` and to the tables in `taguchi/SKILL.md` — the test that compares the two will tell you if you forgot one. Never trust a table pasted from memory or from an unverified web page.

New methods belong here as sibling skills under `skills/`, each with its own SKILL.md and a section in this README. A skill that needs real computation ships it as a tested stdlib-only script next to the prompt (see `pairwise` for the pattern), never as shell embedded in the prompt — and that includes arithmetic the model would otherwise do in its head: level means, decibels, run counts.
