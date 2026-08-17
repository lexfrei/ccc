# taguchi

Plan a minimal set of debugging or testing runs with Taguchi orthogonal arrays instead of changing one factor at a time. An orthogonal array covers every pair of factor levels in a handful of runs — 11 binary factors take 12 runs instead of 2048 — so any behavior driven by one factor or a two-factor interaction is guaranteed to appear in at least one run.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install taguchi@claude-code-companions
```

## Skills

### taguchi

Invoked automatically when a debugging, tuning, or repro plan involves three or more independent candidate factors and each run is expensive (slow build, CI round-trip, flaky repro, hardware cycle). Also on explicit ask: `/taguchi`, "orthogonal array", "design of experiments", "reduce iterations".

The workflow:

1. **Gate** — checks the problem actually fits: 3+ factors, expensive runs, independently settable levels. Single factor → bisection; cheap runs → full factorial; more than ~11 factors → shrink the list first.
2. **Factors and levels** — every factor forced to 2 or 3 discrete levels; observable-but-unsettable factors are recorded as covariates and checked at analysis time.
3. **Array selection** — smallest of L4, L8, L9, L12, L18 that fits; dummy-treatment trick for mixed 2/3-level factor sets.
4. **Run sheet** — the plan rendered with concrete values, plus repetition sizing and run-order rules for flaky bugs and drifting environments.
5. **Outcome recording** — one outcome per run, numeric preferred over binary (a continuous response discriminates in a single pass, binary pays the repetition tax), covariates logged alongside.
6. **Main-effects analysis** — outcomes averaged per factor level, factors ranked by effect size, verdicts for clean splits and muddy signals, covariate balance checked before any verdict.
7. **Confirmation runs** — an accusation run and an acquittal run before any root-cause claim.
8. **Interaction fallback** — full factorial on the top-2 suspects when main effects are confounded.

## Extending

The embedded arrays (L4, L8, L9, L12, L18) are pairwise-balanced. To add a larger array (L16, L27, ...), verify it before embedding: for every pair of columns, every combination of levels must appear equally often. A one-off script that counts pair combinations across columns is enough — do not trust a table pasted from memory or from an unverified web page.
