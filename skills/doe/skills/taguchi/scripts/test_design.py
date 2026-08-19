"""Runnable with pytest or directly: python3 test_design.py"""

import os
import re
from itertools import combinations

from arrays import TABLES, imbalance, parse
from design import COVARIATE_PREFIX, assign, build, parse_spec, select

SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "SKILL.md")


def test_arrays_are_pairwise_balanced():
    for name, rows in TABLES.items():
        assert imbalance(rows) == [], name


def test_skill_tables_match_the_arrays():
    """The prompt shows the arrays; the script uses them. They must not drift."""
    text = open(SKILL).read()
    blocks = re.findall(r"### (L\d+).*?```text\n(.*?)```", text, re.S)
    assert {name for name, _ in blocks} == set(TABLES)
    for name, body in blocks:
        rows = parse("\n".join(line.split(maxsplit=1)[1] for line in body.strip().splitlines()[1:]))
        assert rows == TABLES[name], name


def test_array_selection_takes_the_smallest_that_fits():
    cases = {
        "L4": {f"f{i}": ["a", "b"] for i in range(3)},
        "L8": {f"f{i}": ["a", "b"] for i in range(5)},
        "L9": {f"f{i}": ["a", "b", "c"] for i in range(4)},
        "L12": {f"f{i}": ["a", "b"] for i in range(11)},
        "L18": dict(
            {f"f{i}": ["a", "b", "c"] for i in range(7)}, flag=["on", "off"]
        ),
    }
    for expected, factors in cases.items():
        assert select(factors)[0] == expected


def test_mixed_levels_land_in_one_array():
    factors = {"gc": ["on", "off"], "pool": ["8", "16", "32"], "batch": ["1", "10", "100"]}
    name, placement = select(factors)
    assert name == "L9"
    runs = build(factors, name, placement)
    assert len(runs) == 9
    for factor, levels in factors.items():
        assert {run[factor] for run in runs} == set(levels)


def test_dummy_treatment_repeats_the_first_level():
    factors = {"gc": ["on", "off"], "pool": ["8", "16", "32"], "batch": ["1", "10", "100"]}
    name, placement = select(factors)
    assert placement["gc"][1] is True
    runs = build(factors, name, placement)
    counts = {level: sum(1 for r in runs if r["gc"] == level) for level in factors["gc"]}
    assert counts == {"on": 6, "off": 3}


def test_every_factor_pair_is_covered():
    factors = {f"f{i}": ["a", "b"] for i in range(7)}
    name, placement = select(factors)
    runs = build(factors, name, placement)
    for a, b in combinations(factors, 2):
        seen = {(run[a], run[b]) for run in runs}
        assert len(seen) == 4, (a, b, seen)


def test_columns_are_never_shared():
    factors = dict({f"f{i}": ["a", "b", "c"] for i in range(7)}, flag=["on", "off"])
    placement = assign(factors, "L18")
    columns = [column for column, _ in placement.values()]
    assert len(columns) == len(set(columns))


def test_rejected_specs():
    for bad in (
        ["a=1,2,3,4", "b=1,2", "c=1,2"],
        ["a=1,2", "b=1,2"],
        ["a=1", "b=1,2", "c=1,2"],
        ["a=1,2", "a=3,4", "c=1,2"],
    ):
        try:
            parse_spec(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted invalid spec: {bad}")


def test_too_many_factors_is_refused():
    factors = {f"f{i}": ["a", "b"] for i in range(12)}
    try:
        select(factors)
    except ValueError:
        return
    raise AssertionError("accepted 12 two-level factors")


def test_forced_array_too_small_names_the_array():
    factors = {f"f{i}": ["a", "b"] for i in range(4)}
    try:
        select(factors, "L4")
    except ValueError as error:
        assert "L4" in str(error)
        return
    raise AssertionError("L4 accepted 4 factors")


def test_factor_named_like_a_covariate_is_refused():
    """analyze.py reads the prefix as a covariate, so the name has to be free."""
    try:
        parse_spec([f"{COVARIATE_PREFIX}mode=a,b", "b=1,2", "c=1,2"])
    except ValueError as error:
        assert COVARIATE_PREFIX in str(error)
        return
    raise AssertionError(f"accepted a factor named {COVARIATE_PREFIX}mode")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: ok")
