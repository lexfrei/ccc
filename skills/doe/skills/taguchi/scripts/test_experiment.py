"""Runnable with pytest or directly: python3 test_experiment.py"""

import csv
import tempfile

import experiment
from experiment import (
    create,
    describe,
    listing,
    load,
    outstanding,
    record,
    save,
    slugify,
    to_csv,
)

FACTORS = ["os=ubuntu,macos", "node=18,20", "cache=warm,cold"]


def fresh(store, repeats=1):
    return create("flaky lockfile", FACTORS, "a hypothesis", repeats, None, store)


def test_slugify():
    assert slugify("Flaky lockfile — CI only") == "flaky-lockfile-ci-only"
    assert len(slugify("x" * 200)) == 60
    try:
        slugify("!!!")
    except ValueError:
        return
    raise AssertionError("accepted a title with no usable characters")


def test_create_writes_the_sheet():
    with tempfile.TemporaryDirectory() as store:
        state = fresh(store)
        assert state["array"] == "L4"
        assert len(state["runs"]) == 4
        assert load("flaky-lockfile", store) == state
        assert {run["values"]["os"] for run in state["runs"]} == {"ubuntu", "macos"}


def test_second_experiment_with_the_same_title_is_refused():
    with tempfile.TemporaryDirectory() as store:
        fresh(store)
        try:
            fresh(store)
        except ValueError:
            return
        raise AssertionError("overwrote an existing experiment")


def test_record_appends_then_replaces():
    with tempfile.TemporaryDirectory() as store:
        state = fresh(store, repeats=2)
        record(state, 1, ["fail"], ["region=eu"])
        record(state, 1, ["pass"], [])
        assert state["runs"][0]["results"] == ["fail", "pass"]
        assert state["runs"][0]["covariates"] == {"region": "eu"}
        record(state, 1, ["fail"], [], replace=True)
        assert state["runs"][0]["results"] == ["fail"]
        for bad in ((9, ["fail"], []), (1, ["fail"], ["region"])):
            try:
                record(state, *bad)
            except ValueError:
                continue
            raise AssertionError(f"accepted {bad}")


def test_outstanding_counts_repeats():
    with tempfile.TemporaryDirectory() as store:
        state = fresh(store, repeats=2)
        assert outstanding(state) == [1, 2, 3, 4]
        record(state, 1, ["pass"], [])
        assert outstanding(state) == [1, 2, 3, 4]
        record(state, 1, ["pass"], [])
        assert outstanding(state) == [2, 3, 4]


def test_csv_pads_repeats_and_carries_covariates():
    with tempfile.TemporaryDirectory() as store:
        state = fresh(store, repeats=2)
        record(state, 1, ["120", "125"], ["region=eu"])
        record(state, 2, ["130"], [])
        lines = to_csv(state).splitlines()
        assert lines[0] == "run,os,node,cache,result_1,result_2,region"
        assert lines[1].endswith("120,125,eu")
        assert lines[2].endswith("130,,")


def test_describe_demands_baselines_then_stops():
    with tempfile.TemporaryDirectory() as store:
        state = fresh(store)
        assert "Baselines not recorded" in describe(state)
        state["baselines"] = {"good": "pass", "bad": "fail"}
        assert "Baselines not recorded" not in describe(state)
        state["baselines"] = {"good": "fail", "bad": "fail"}
        assert "contradicts the setup" in describe(state)


def test_listing_and_close():
    with tempfile.TemporaryDirectory() as store:
        state = fresh(store)
        assert "0/4 runs done" in listing(store)
        state["status"] = "closed"
        save(state, store)
        assert "closed" in listing(store)
        assert listing(store + "/nowhere").startswith("no ")


def test_missing_experiment_is_a_clear_error():
    with tempfile.TemporaryDirectory() as store:
        try:
            load("nope", store)
        except ValueError as error:
            assert "no experiment" in str(error)
            return
        raise AssertionError("loaded an experiment that does not exist")


def test_csv_quotes_a_value_holding_a_comma():
    with tempfile.TemporaryDirectory() as store:
        state = fresh(store)
        record(state, 1, ["fail"], ["region=eu,west"])
        rows = list(csv.reader(to_csv(state).splitlines()))
        assert len({len(row) for row in rows}) == 1
        assert rows[1][-1] == "eu,west"


def test_repeats_below_one_is_refused():
    with tempfile.TemporaryDirectory() as store:
        try:
            create("zero repeats", FACTORS, "", 0, None, store)
        except ValueError:
            return
        raise AssertionError("opened an experiment no row can ever finish")


def test_outstanding_takes_a_repeat_override():
    with tempfile.TemporaryDirectory() as store:
        state = fresh(store)
        record(state, 1, ["pass"], [])
        assert outstanding(state) == [2, 3, 4]
        assert outstanding(state, 2) == [1, 2, 3, 4]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: ok")
