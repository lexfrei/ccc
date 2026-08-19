"""Runnable with pytest or directly: python3 test_analyze.py"""

import math

from analyze import (
    analyze,
    classify,
    false_split_odds,
    level_means,
    permutation_p,
    read_outcomes,
    signal_to_noise,
)

L4 = [
    {"os": "ubuntu", "node": "18", "lockfile": "frozen"},
    {"os": "ubuntu", "node": "20", "lockfile": "fresh"},
    {"os": "macos", "node": "18", "lockfile": "fresh"},
    {"os": "macos", "node": "20", "lockfile": "frozen"},
]
FACTORS = ["os", "node", "lockfile"]


def rows_with(results):
    return [dict(row, result=value) for row, value in zip(L4, results)]


def test_signal_to_noise_matches_the_definitions():
    assert math.isclose(signal_to_noise([2, 4], "minimize"), -10.0, abs_tol=1e-9)
    assert math.isclose(
        signal_to_noise([2, 4], "maximize"), -10 * math.log10(0.15625), abs_tol=1e-9
    )
    assert math.isclose(
        signal_to_noise([10, 12], "target"), 10 * math.log10(121 / 2), abs_tol=1e-9
    )


def test_target_needs_repeats():
    for values, goal in (([5], "target"), ([7, 7], "target"), ([0, 1], "maximize")):
        try:
            signal_to_noise(values, goal)
        except ValueError:
            continue
        raise AssertionError(f"accepted {goal} on {values}")


def test_outcomes_read_words_and_numbers():
    assert read_outcomes({"result": "fail"}, ["result"]) == [1.0]
    assert read_outcomes({"result": "PASS"}, ["result"]) == [0.0]
    assert read_outcomes({"y1": "1.5", "y2": "2"}, ["y1", "y2"]) == [1.5, 2.0]
    assert read_outcomes({"result": ""}, ["result"]) is None
    try:
        read_outcomes({"result": "maybe"}, ["result"])
    except ValueError:
        return
    raise AssertionError("accepted a non-numeric, non-binary outcome")


def test_numeric_levels_stay_in_numeric_order():
    rows = [{"pool": v} for v in ("32", "8", "16")]
    assert list(level_means(rows, "pool", [1.0, 2.0, 3.0])) == ["8", "16", "32"]


def test_clean_split_is_reported_with_its_odds():
    report = analyze(rows_with(["pass", "pass", "fail", "fail"]), FACTORS, ["result"], [], None, None)
    assert "os=macos" in report
    # In an L4 with two failures some factor always splits cleanly.
    assert math.isclose(false_split_odds(L4, FACTORS, 2), 1.0, abs_tol=1e-9)


def test_all_pass_and_all_fail_are_called_out():
    assert "Nothing failed anywhere" in analyze(
        rows_with(["pass"] * 4), FACTORS, ["result"], [], None, None
    )
    assert "Everything failed" in analyze(
        rows_with(["fail"] * 4), FACTORS, ["result"], [], None, None
    )


def test_unfinished_array_is_refused():
    rows = rows_with(["fail", "pass", "", "pass"])
    try:
        analyze(rows, FACTORS, ["result"], [], None, None)
    except ValueError:
        return
    raise AssertionError("analyzed an array with a missing outcome")


def test_permutation_p_is_deterministic_and_ordered():
    scores = [0.0, 0.0, 1.0, 1.0]
    strong = permutation_p(L4, "os", scores)
    weak = permutation_p(L4, "node", scores)
    assert strong == permutation_p(L4, "os", scores)
    assert strong < weak
    assert weak == 1.0


def test_classify_finds_outcomes_and_keeps_factors():
    columns = ["run", "os", "node", "y1", "y2", "region"]
    factors, outcomes, covariates = classify(columns, [], ["region"])
    assert factors == ["os", "node"]
    assert outcomes == ["y1", "y2"]
    assert covariates == ["region"]
    try:
        classify(["run", "os", "node"], [], [])
    except ValueError:
        return
    raise AssertionError("classified a CSV with no outcome column")


def test_covariate_tracking_the_outcome_is_flagged():
    rows = [dict(row, region="eu" if row["os"] == "ubuntu" else "us") for row in L4]
    rows = [dict(row, result=value) for row, value in zip(rows, ["pass", "pass", "fail", "fail"])]
    report = analyze(rows, FACTORS, ["result"], ["region"], None, None)
    assert "Covariate `region`" in report
    assert "hole in the balance" in report


L9_ROWS = [
    {"a": a, "b": b}
    for a in ("1", "2", "3")
    for b in ("1", "2", "3")
]


def test_censored_runs_are_reported_and_ranked():
    rows = [
        dict(row, result="fail" if row["a"] == "3" else "10")
        for row in L9_ROWS
    ]
    report = analyze(rows, ["a", "b"], ["result"], [], "minimize", None)
    assert "3 of 9 runs produced no measurement" in report
    assert "Ranked by how strongly a level predicts failure: a" in report
    # The survivors still get a main-effects pass, flagged as unbalanced.
    assert "no longer a balanced array" in report
    assert "S/N ratio per run" in report


def test_mostly_censored_array_stops_before_the_means():
    rows = [
        dict(row, result="12" if row == L9_ROWS[0] else "fail")
        for row in L9_ROWS
    ]
    report = analyze(rows, ["a", "b"], ["result"], [], "minimize", None)
    assert "Too few rows measured anything" in report
    assert "S/N ratio per run" not in report


def test_pass_fail_only_array_stays_binary():
    rows = [dict(row, result="fail" if row["a"] == "1" else "pass") for row in L9_ROWS]
    report = analyze(rows, ["a", "b"], ["result"], [], None, None)
    assert "Binary outcome: 3 of 9 runs failed" in report
    assert "produced no measurement" not in report



def test_zero_one_reads_the_same_as_pass_fail():
    """The same experiment written twice has to accuse the same level."""
    words = analyze(
        rows_with(["pass", "pass", "fail", "fail"]), FACTORS, ["result"], [], None, None
    )
    digits = analyze(
        rows_with(["1", "1", "0", "0"]), FACTORS, ["result"], [], None, None
    )
    assert "os=macos" in words
    assert words == digits


def test_binary_outcome_gets_no_optimum_from_a_goal():
    report = analyze(
        rows_with(["pass", "pass", "fail", "fail"]),
        FACTORS,
        ["result"],
        [],
        "minimize",
        None,
    )
    assert "Predicted optimum" not in report
    assert "os=macos" in report
    assert "accusation run" in report
    everything = analyze(
        rows_with(["fail"] * 4), FACTORS, ["result"], [], "minimize", None
    )
    assert "Everything failed" in everything
    assert "Predicted optimum" not in everything


# `a` moves the mean and nothing else: its spread scales with its own level, so
# every run has the same S/N and only `b` ranks on stability. That is the sheet
# the two-step exists for — the S/N table cannot tell the three `a` levels apart.
TARGET_SHEET = [
    {
        "a": a,
        "b": b,
        "y1": f"{float(a) * (1 - k):g}",
        "y2": f"{float(a) * (1 + k):g}",
    }
    for a in ("100", "200", "300")
    for b, k in (("tight", 0.001), ("loose", 0.01), ("wild", 0.05))
]


def test_target_goal_steers_onto_the_target():
    low = analyze(TARGET_SHEET, ["a", "b"], ["y1", "y2"], [], "target", 100.0)
    high = analyze(TARGET_SHEET, ["a", "b"], ["y1", "y2"], [], "target", 300.0)
    assert "Two-step answer for target=100" in low
    assert "Predicted optimum: a=100" in low
    assert "Predicted optimum: a=300" in high
    # Step one is the stability factor, step two the knob that is flat on S/N.
    assert "1. Stability: b=tight" in low
    assert "2. Steering: a=100" in low
    assert "predicted mean 100 against a target of 100" in low


def test_target_outside_the_measured_range_is_flagged():
    report = analyze(TARGET_SHEET, ["a", "b"], ["y1", "y2"], [], "target", 900.0)
    assert "outside the range this array measured" in report


def test_target_without_a_value_is_refused():
    try:
        analyze(TARGET_SHEET, ["a", "b"], ["y1", "y2"], [], "target", None)
    except ValueError:
        return
    raise AssertionError("analyzed a target sheet with no target to steer onto")


def test_table_widens_for_a_four_level_factor():
    rows = [
        {"pool": pool, "gc": gc, "result": result}
        for pool, gc, result in zip("1234", "abab", ("10", "20", "30", "40"))
    ]
    report = analyze(rows, ["pool", "gc"], ["result"], [], None, None)
    table = [line for line in report.splitlines() if line.startswith("| ")]
    assert "level 4" in table[0]
    assert len({line.count("|") for line in table}) == 1


def test_pipes_in_levels_do_not_break_the_table():
    rows = [
        {"filter": "a|b", "result": "10"},
        {"filter": "c", "result": "20"},
    ]
    assert r"a\|b" in analyze(rows, ["filter"], ["result"], [], None, None)


def test_large_means_print_as_numbers_not_exponents():
    """1002 ms is a lap time; 1e+03 is a number nobody can act on."""
    rows = [
        {"pool": pool, "batch": str(i), "y1": str(base), "y2": str(base + 4)}
        for pool, base in (("8", 200.0), ("16", 1000.0))
        for i in (0, 1)
    ]
    report = analyze(rows, ["pool", "batch"], ["y1", "y2"], [], "target", 1000.0)
    assert "predicted mean 1002" in report
    assert "1e+03" not in report


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: ok")
