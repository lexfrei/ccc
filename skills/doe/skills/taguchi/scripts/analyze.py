"""Main-effects analysis of a finished run sheet: level means, deltas, S/N.

Usage: analyze.py results.csv
       analyze.py results.csv --goal minimize
       analyze.py results.csv --goal target=200 --covariate region

The CSV carries one row per run: the factor columns from the run sheet, one
or more outcome columns (`result`, or `result_1..n` / `y1..n` for repeats),
and any covariate columns. Outcomes may be numeric or binary
(pass/fail, ok/bad, 0/1, true/false). A sheet is binary when every recorded
outcome is one of those words; `0`/`1` are `false`/`true` spelled as digits, so
`0` is a failure and `1` is a pass in both spellings of the same experiment.

The arithmetic here is the part a model should not do in its head: level
means over the whole array, the noise floor between repeats, S/N ratios in
decibels, and the odds that a clean-looking split is coincidence.
"""

import argparse
import csv
import math
import random
import sys
from collections import defaultdict
from itertools import product

FAIL_WORDS = {"fail", "failed", "bad", "broken", "red", "no", "false", "0"}
PASS_WORDS = {"pass", "passed", "ok", "good", "green", "yes", "true", "1"}
BINARY_WORDS = FAIL_WORDS | PASS_WORDS
OUTCOME_HINTS = ("result", "outcome", "y", "value", "latency", "time", "duration")


def read_rows(path):
    with open(path, newline="") as handle:
        rows = [
            {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            for row in csv.DictReader(handle)
        ]
    if not rows:
        raise ValueError("no data rows in the CSV")
    return rows


def classify(columns, outcomes, covariates):
    """Split the header into factor, outcome and covariate columns."""
    if not outcomes:
        outcomes = [
            c
            for c in columns
            if c.lower().split("_")[0].rstrip("0123456789") in OUTCOME_HINTS
        ]
    missing = [c for c in outcomes + covariates if c not in columns]
    if missing:
        raise ValueError(f"column not in the CSV: {', '.join(missing)}")
    if not outcomes:
        raise ValueError(
            "no outcome column found — name it `result` or pass --outcome"
        )
    factors = [
        c
        for c in columns
        if c not in outcomes and c not in covariates and c.lower() != "run"
    ]
    if not factors:
        raise ValueError("no factor columns left after removing outcomes")
    return factors, outcomes, covariates


def to_number(text):
    try:
        return float(text)
    except ValueError:
        return None


def is_binary(rows, outcomes):
    """True when every recorded outcome is a pass/fail word.

    The test has to be the vocabulary, not "does the cell parse as a number":
    `0` and `1` are in that vocabulary, and reading them as measurements made
    the verdict come out inverted against the same experiment spelled
    pass/fail — 1 means pass, and a score of 1.0 means failed.
    """
    cells = [row[c] for row in rows for c in outcomes if row[c] != ""]
    return bool(cells) and all(v.lower() in BINARY_WORDS for v in cells)


def read_outcomes(row, outcomes, numeric=None):
    """Per-run repeats, as failure flags in binary mode and as numbers in
    numeric mode. In numeric mode a pass/fail word becomes None: the run
    produced no measurement, which is data about the levels, not a number."""
    raw = [row[c] for c in outcomes if row[c] != ""]
    if not raw:
        return None
    if numeric is None:
        numeric = not all(v.lower() in BINARY_WORDS for v in raw)
    values = []
    for value in raw:
        word = value.lower()
        number = to_number(value)
        if not numeric:
            if word not in BINARY_WORDS:
                raise ValueError(
                    f"outcome {value!r} is neither a number nor pass/fail"
                )
            values.append(1.0 if word in FAIL_WORDS else 0.0)
        elif number is not None:
            values.append(number)
        elif word in BINARY_WORDS:
            values.append(None)
        else:
            raise ValueError(f"outcome {value!r} is neither a number nor pass/fail")
    return values


def _cell(value):
    return str(value).replace("\\", "\\\\").replace("|", "\\|")


def censored_report(rows, factors, censored, n):
    """Which levels the runs that produced no measurement are sitting on."""
    lines = [
        f"**{sum(censored)} of {n} runs produced no measurement** — they failed, "
        "timed out or were disqualified. That is data, not a gap: the levels "
        "they share are the ones driving the failure.\n",
        "| Factor | failure rate per level | Δ | p |",
        "| --- | --- | --- | --- |",
    ]
    scores = [1.0 if flag else 0.0 for flag in censored]
    ranked = []
    for factor in factors:
        means = level_means(rows, factor, scores)
        delta = max(means.values()) - min(means.values())
        p_value = permutation_p(rows, factor, scores)
        ranked.append((delta, factor))
        cells = ", ".join(f"{_cell(lv)}: {value:.2f}" for lv, value in means.items())
        lines.append(f"| {_cell(factor)} | {cells} | {delta:.3g} | {p_value:.3f} |")
    ranked.sort(reverse=True)
    lines.append("")
    lines.append(
        "Ranked by how strongly a level predicts failure: "
        + ", ".join(f for _, f in ranked)
        + "."
    )
    lines.append(
        "The surviving rows are no longer a balanced array — dropping runs "
        "breaks exactly the property the level means rely on — so read what "
        "follows as a lead, and re-run a tightened array: pull the levels that "
        "fail out of the ranges (a zoom round), rather than averaging around "
        "the hole they left.\n"
    )
    return lines


def signal_to_noise(values, goal):
    """Taguchi S/N in decibels; higher is better for every goal.

    The target ratio is nominal-the-best, mean over variance, and it is blind
    to the target value by construction: it scores stability alone. What a
    stated target is for is `steer_to_target` — step two of the answer.
    """
    n = len(values)
    if goal == "minimize":
        return -10 * math.log10(sum(v * v for v in values) / n)
    if goal == "maximize":
        if any(v == 0 for v in values):
            raise ValueError("maximize S/N is undefined for a zero outcome")
        return -10 * math.log10(sum(1 / (v * v) for v in values) / n)
    if goal == "target":
        if n < 2:
            raise ValueError(
                "target S/N needs 2+ repeats per run — it is a mean-over-variance "
                "ratio, and one measurement has no variance"
            )
        mean = sum(values) / n
        var = sum((v - mean) ** 2 for v in values) / (n - 1)
        if var == 0:
            raise ValueError("target S/N is undefined for zero variance in a run")
        return 10 * math.log10(mean * mean / var)
    raise ValueError(f"unknown goal: {goal}")


def level_means(rows, factor, scores):
    """Level means, kept in level order — numeric when the values are numbers."""
    per_level = defaultdict(list)
    for row, score in zip(rows, scores):
        per_level[row[factor]].append(score)
    keys = list(per_level)
    numbers = [to_number(k) for k in keys]
    if all(n is not None for n in numbers):
        keys = [k for _, k in sorted(zip(numbers, keys))]
    return {lv: sum(per_level[lv]) / len(per_level[lv]) for lv in keys}


PERMUTATIONS = 2000


def permutation_p(rows, factor, scores, seed=0):
    """How often a random relabelling beats the observed delta.

    The array is balanced, so shuffling the outcomes across runs is the exact
    null: any delta the shuffle reproduces was never evidence. Deterministic
    by seed, so two analyses of the same CSV agree.
    """
    observed = max(level_means(rows, factor, scores).values()) - min(
        level_means(rows, factor, scores).values()
    )
    rnd = random.Random(seed)
    pool = list(scores)
    hits = 0
    for _ in range(PERMUTATIONS):
        rnd.shuffle(pool)
        means = level_means(rows, factor, pool)
        if max(means.values()) - min(means.values()) >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (PERMUTATIONS + 1)


def false_split_odds(rows, factors, fired):
    """Expected number of innocent factors showing a clean split by chance.

    With k failures spread at random over N balanced runs, one factor level
    holding all of them is a coincidence with probability
    L * C(N/L, k) / C(N, k). Summed over factors, that is how many clean
    splits to expect from noise alone.
    """
    n = len(rows)
    if not 0 < fired < n:
        return None
    expected = 0.0
    for factor in factors:
        counts = defaultdict(int)
        for row in rows:
            counts[row[factor]] += 1
        sizes = list(counts.values())
        if len(sizes) < 2:
            continue
        expected += sum(
            math.comb(size, fired) / math.comb(n, fired)
            for size in sizes
            if size >= fired
        )
    return expected


FLAT_P = 0.2
STEER_COMBOS = 20000

NEXT_CONFIRMATION = (
    "Next: run the predicted optimum as a confirmation. Matching or "
    "beating the best array row ends it; falling clearly short means "
    "additivity broke — run the full factorial on the two highest-Δ "
    "knobs, or re-centre the levels and zoom."
)


def steer_to_target(rows, factors, ranked, per_run, target):
    """The two-step answer for a nominal-the-best goal.

    Step one sets every factor that moves S/N — stability — to its best level.
    Step two steers the mean onto the target with what is left, the factors
    whose S/N is flat: moving those costs no stability, which is the whole
    reason the steps run in that order (tune/SKILL.md step 5). The S/N ratio
    is blind to the target value, so this is where the number is read; ranking
    by S/N alone recommended a level five times off a stated target.
    """
    run_means = [sum(v) / len(v) for v in per_run]
    grand = sum(run_means) / len(run_means)
    mean_effects = {f: level_means(rows, f, run_means) for f in factors}
    best_sn = {
        factor: max(means.items(), key=lambda item: item[1])[0]
        for _, factor, means, _ in ranked
    }
    flat = [factor for _, factor, _, p_value in ranked if p_value > FLAT_P]
    flat.sort(
        key=lambda f: max(mean_effects[f].values()) - min(mean_effects[f].values()),
        reverse=True,
    )

    # Search the flat knobs exhaustively; an array holds few enough of them
    # that this is a handful of combinations, and the cap keeps a hand-written
    # CSV with many columns from turning it into a sweep.
    steering, combos = [], 1
    for factor in flat:
        if combos * len(mean_effects[factor]) > STEER_COMBOS:
            break
        steering.append(factor)
        combos *= len(mean_effects[factor])

    best = None
    for levels in product(*(list(mean_effects[f]) for f in steering)):
        trial = dict(best_sn)
        trial.update(zip(steering, levels))
        predicted = grand + sum(
            mean_effects[factor][level] - grand for factor, level in trial.items()
        )
        miss = abs(predicted - target)
        if best is None or miss < best[0]:
            best = (miss, predicted, trial)
    miss, predicted, choice = best

    stable = [f for f in factors if f not in steering]
    lines = [
        f"Two-step answer for target={target:g} — stability first, mean second: "
        "a knob that steers the mean and moves S/N as well bakes the noise in.\n",
        "1. Stability: "
        + (
            ", ".join(f"{f}={choice[f]}" for f in stable)
            if stable
            else "nothing — every factor is flat on S/N"
        )
        + " — highest-S/N level of each.",
        "2. Steering: "
        + (
            ", ".join(f"{f}={choice[f]}" for f in steering)
            if steering
            else "no knob left"
        )
        + f" — flat on S/N (p > {FLAT_P}), so these move the mean at no cost in "
        "stability; set to land on the target.\n",
        "Predicted optimum: "
        + ", ".join(f"{f}={choice[f]}" for f in factors)
        + f" — predicted mean {predicted:.3g} against a target of {target:g} "
        f"(miss {miss:.3g}). It is usually not a row of the array — the array "
        "sampled, the analysis extrapolated.",
    ]
    if not steering:
        lines.append(
            "Every factor moves S/N, so nothing steers the mean for free: the "
            "setting above is the stability optimum and the miss above is what "
            "it costs. Closing it means trading S/N for the target, or adding a "
            "knob that moves the mean without moving the variance."
        )
    low, high = min(run_means), max(run_means)
    if not low <= target <= high:
        lines.append(
            f"The target is outside the range this array measured "
            f"({low:.3g}..{high:.3g}), so the prediction extrapolates the "
            "additive model instead of interpolating it. Re-centre the levels "
            "around the target and run a zoom round."
        )
    return lines


def noise_floor(per_run):
    spreads = [max(v) - min(v) for v in per_run if len(v) > 1]
    return sum(spreads) / len(spreads) if spreads else None


def analyze(rows, factors, outcomes, covariates, goal, target):
    if goal == "target" and target is None:
        raise ValueError(
            "target mode steers onto a number — pass --goal target=VALUE"
        )
    binary = is_binary(rows, outcomes)
    raw_runs = []
    for i, row in enumerate(rows, 1):
        values = read_outcomes(row, outcomes, numeric=not binary)
        if values is None:
            raise ValueError(f"run {i} has no outcome recorded — finish the array")
        raw_runs.append(values)

    censored = [any(value is None for value in values) for values in raw_runs]
    lines = []
    n = len(rows)

    if any(censored):
        lines.extend(censored_report(rows, factors, censored, n))
        if sum(censored) > n - 4:
            lines.append(
                "Too few rows measured anything for a main-effects pass on the "
                "survivors. Tighten the levels and run the array again."
            )
            return "\n".join(lines)
        keep = [i for i, flag in enumerate(censored) if not flag]
        rows = [rows[i] for i in keep]
        raw_runs = [[v for v in raw_runs[i] if v is not None] for i in keep]

    per_run = raw_runs
    n = len(rows)

    if binary:
        fired = sum(1 for v in per_run if max(v) == 1.0)
        lines.append(f"Binary outcome: {fired} of {n} runs failed.\n")
        if fired == 0:
            lines.append(
                "**Nothing failed anywhere in the array.** The array cannot rank "
                "what never happened. Either no listed factor drives the bug, the "
                "levels are not extreme enough, or the repro needs repeats "
                "(N >= ln(0.05)/ln(1-p)). Re-check the known-bad baseline before "
                "spending another array.\n"
            )
        elif fired == n:
            lines.append(
                "**Everything failed.** Either a factor outside the list drives "
                "the bug, or what you called the innocent level is not innocent. "
                "Re-check the known-good baseline before spending another array.\n"
            )
        scores = [max(v) for v in per_run]
        if goal:
            lines.append(
                "`--goal` optimizes an S/N ratio over a measured number, and "
                "this sheet recorded pass/fail: the table below is failure rate "
                "per level — lower is better — and no optimum is predicted from "
                "it. Taking the best level off a failure-rate table recommends "
                "the level holding the failures, and on an all-passed or "
                "all-failed sheet there is nothing to recommend at all. Re-run "
                "with a numeric outcome (`run.py --metric ...`) to rank levels "
                "by how good they are rather than by how often they broke.\n"
            )
            goal = None
    else:
        scores = None
        if goal:
            scores = [signal_to_noise(v, goal) for v in per_run]
            lines.append(f"S/N ratio per run ({goal}, higher is better):\n")
            lines.append("| Run | repeats | S/N (dB) |")
            lines.append("| --- | --- | --- |")
            for i, (values, sn) in enumerate(zip(per_run, scores), 1):
                shown = ", ".join(f"{v:g}" for v in values)
                lines.append(f"| {i} | {shown} | {sn:.2f} |")
            lines.append("")
        else:
            scores = [sum(v) / len(v) for v in per_run]
        floor = noise_floor(per_run)
        if floor is not None:
            lines.append(
                f"Noise floor: mean spread between repeats of the same run is "
                f"{floor:.3g}. A delta below that separates nothing.\n"
            )
        else:
            lines.append(
                "No repeats recorded, so there is no noise floor to compare "
                "deltas against — a small delta may be pure measurement noise.\n"
            )

    unit = "failure rate" if binary else ("S/N (dB)" if goal else "mean outcome")
    ranked = []
    for factor in factors:
        means = level_means(rows, factor, scores)
        delta = max(means.values()) - min(means.values())
        p_value = permutation_p(rows, factor, scores)
        ranked.append((delta, factor, means, p_value))
    width = max(len(means) for _, _, means, _ in ranked)
    lines.append(f"Main effects ({unit}):\n")
    lines.append(
        "| Factor | "
        + " | ".join(f"level {i}" for i in range(1, width + 1))
        + " | Δ | p |"
    )
    lines.append("| --- | " + " | ".join("---" for _ in range(width + 2)) + " |")
    for delta, factor, means, p_value in ranked:
        cells = [f"{_cell(lv)}: {value:.3g}" for lv, value in means.items()]
        cells += [""] * (width - len(cells))
        lines.append(
            f"| {_cell(factor)} | "
            + " | ".join(cells)
            + f" | {delta:.3g} | {p_value:.3f} |"
        )
    lines.append("")
    expected_lucky = 0.05 * len(factors)
    lines.append(
        f"`p` is a permutation test: the share of random relabellings of the same "
        f"outcomes that produce a delta this large. With {len(factors)} factors, "
        f"about {expected_lucky:.1f} of them are expected to land under p=0.05 by "
        "luck alone, so a small p ranks suspects — it does not convict one.\n"
    )

    ranked.sort(reverse=True, key=lambda item: item[0])
    lines.append(
        "Ranked by effect size: " + ", ".join(f for _, f, _, _ in ranked) + ".\n"
    )

    if binary:
        fired = sum(scores)
        clean = [
            (factor, means)
            for _, factor, means, _ in ranked
            if sum(1 for v in means.values() if v > 0) == 1 and fired > 0
        ]
        for factor, means in clean:
            guilty = [lv for lv, v in means.items() if v > 0][0]
            lines.append(
                f"Clean split: every failure sits at **{factor}={guilty}**."
            )
        odds = false_split_odds(rows, factors, int(fired))
        if odds is not None and clean:
            lines.append(
                f"With {int(fired)} failures over {n} runs and {len(factors)} "
                f"factors, chance alone produces about {odds:.2f} clean splits. "
                + (
                    "That is comparable to what you are seeing — treat the split "
                    "as a lead, not a verdict, and let the confirmation runs decide."
                    if odds >= 0.5
                    else "A coincidence at that rate is unlikely, but the "
                    "confirmation runs still decide."
                )
            )
        lines.append("")

    for covariate in covariates:
        groups = defaultdict(list)
        for row, score in zip(rows, scores):
            groups[row[covariate]].append(score)
        means = {k: sum(v) / len(v) for k, v in sorted(groups.items())}
        spread = max(means.values()) - min(means.values())
        biggest = max(delta for delta, _, _, _ in ranked)
        lines.append(
            f"Covariate `{covariate}`: "
            + ", ".join(f"{k}={v:.3g}" for k, v in means.items())
            + f" (spread {spread:.3g})."
        )
        if spread >= biggest * 0.5:
            lines.append(
                f"  It tracks the outcome about as strongly as the ranked factors "
                "do — a hole in the balance the array guarantees only for assigned "
                "columns. Find a way to set it and rerun before believing any "
                "verdict."
            )
    if covariates:
        lines.append("")

    if goal == "target":
        lines.extend(steer_to_target(rows, factors, ranked, per_run, target))
        lines.append(NEXT_CONFIRMATION)
    elif goal:
        optimum = {
            factor: max(means.items(), key=lambda item: item[1])[0]
            for _, factor, means, _ in ranked
        }
        flat = [factor for _, factor, _, p_value in ranked if p_value > FLAT_P]
        lines.append(
            "Predicted optimum: "
            + ", ".join(f"{k}={v}" for k, v in optimum.items())
            + ". It is usually not a row of the array — the array sampled, the "
            "analysis extrapolated."
        )
        if flat:
            lines.append(
                f"Indistinguishable from noise (p > {FLAT_P}), so free to set by "
                "cost or convenience: " + ", ".join(flat) + "."
            )
        lines.append(NEXT_CONFIRMATION)
    else:
        lines.append(
            "Next: the accusation run (suspect at its guilty level, everything "
            "else innocent — must fail) and the acquittal run (a failing "
            "configuration with the suspect moved to its innocent level — must "
            "pass). A main-effects table is a hypothesis, never a root cause."
        )
    return "\n".join(lines)


def main(argv):
    parser = argparse.ArgumentParser(
        description="Main-effects and S/N analysis of a Taguchi run sheet."
    )
    parser.add_argument("csv", help="results CSV, one row per run")
    parser.add_argument(
        "--outcome", action="append", default=[], help="outcome column; repeatable"
    )
    parser.add_argument(
        "--covariate", action="append", default=[], help="covariate column; repeatable"
    )
    parser.add_argument(
        "--goal",
        help="minimize | maximize | target=VALUE — switches the analysis to S/N",
    )
    opts = parser.parse_args(argv)

    goal, target = opts.goal, None
    if goal and goal.startswith("target"):
        _, _, value = goal.partition("=")
        target = to_number(value)
        if target is None:
            raise ValueError(
                "target mode steers onto a number — pass --goal target=VALUE "
                f"(got {opts.goal!r})"
            )
        goal = "target"
    if goal and goal not in ("minimize", "maximize", "target"):
        raise ValueError(f"unknown goal: {opts.goal}")

    rows = read_rows(opts.csv)
    factors, outcomes, covariates = classify(
        list(rows[0]), opts.outcome, opts.covariate
    )
    print(analyze(rows, factors, outcomes, covariates, goal, target))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
