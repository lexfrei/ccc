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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: ok")
