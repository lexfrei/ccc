"""Runnable with pytest or directly: python3 test_run.py"""

import os
import tempfile

import experiment
import run as runner


def opened(store, repeats=1, baselines=True):
    state = experiment.create(
        "flaky lockfile",
        ["os=ubuntu,macos", "node=18,20", "cache=warm,cold"],
        "",
        repeats,
        None,
        store,
    )
    if baselines:
        state["baselines"] = {"good": "pass", "bad": "fail"}
        experiment.save(state, store)
    return state


def test_substitute_quotes_unless_shell():
    values = {"os": "ubuntu 24", "node": "18"}
    assert runner.substitute("t {os} {node}", values, False) == "t 'ubuntu 24' 18"
    assert runner.substitute("t {os}", values, True) == "t ubuntu 24"
    try:
        runner.substitute("t {missing}", values, False)
    except ValueError as error:
        assert "os, node" in str(error)
        return
    raise AssertionError("accepted a template naming an unknown factor")


def test_extract_reads_the_first_group():
    assert runner.extract(r"p95=([0-9.]+)", "noise\np95=12.5ms\n") == 12.5
    assert runner.extract(r"[0-9]+", "answer 42") == 42.0
    assert runner.extract(r"p99=([0-9.]+)", "p95=1") is None
    try:
        runner.extract(r"(p95)", "p95=1")
    except ValueError:
        return
    raise AssertionError("accepted a non-numeric capture")


def test_execute_records_code_and_log():
    with tempfile.TemporaryDirectory() as store:
        log = os.path.join(store, "logs", "one.log")
        code, output = runner.execute("echo hello", False, None, log)
        assert code == 0 and "hello" in output
        assert "hello" in open(log).read()
        code, _ = runner.execute("false", False, None, None)
        assert code != 0


def test_timeout_is_reported_not_raised():
    code, output = runner.execute("sleep 5", False, 0.2, None)
    assert code is None
    assert "timed out" in output


def test_pending_respects_only_and_redo():
    with tempfile.TemporaryDirectory() as store:
        state = opened(store)
        experiment.record(state, 1, ["pass"], [])
        assert runner.pending(state, None, False) == [2, 3, 4]
        assert runner.pending(state, None, True) == [1, 2, 3, 4]
        assert runner.pending(state, [2], False) == [2]
        try:
            runner.pending(state, [9], False)
        except ValueError:
            return
        raise AssertionError("accepted a row outside the array")


def test_run_without_baselines_is_refused():
    with tempfile.TemporaryDirectory() as store:
        opened(store, baselines=False)
        try:
            runner.main(
                ["flaky-lockfile", "--cmd", "true", "--store", store]
            )
        except ValueError as error:
            assert "baselines" in str(error)
            return
        raise AssertionError("ran an array with no baselines")


def test_end_to_end_fills_the_journal():
    with tempfile.TemporaryDirectory() as store:
        opened(store, repeats=2)
        runner.main(
            [
                "flaky-lockfile",
                "--cmd",
                "echo p95={node}",
                "--metric",
                r"p95=([0-9.]+)",
                "--store",
                store,
                "--randomize",
                "--seed",
                "3",
            ]
        )
        state = experiment.load("flaky-lockfile", store)
        assert experiment.outstanding(state) == []
        for row in state["runs"]:
            assert row["results"] == [row["values"]["node"]] * 2
        assert os.path.isdir(os.path.join(store, "flaky-lockfile-logs"))


def test_binary_outcome_comes_from_the_exit_code():
    with tempfile.TemporaryDirectory() as store:
        opened(store)
        runner.main(
            [
                "flaky-lockfile",
                "--cmd",
                "test {node} = 18",
                "--store",
                store,
            ]
        )
        state = experiment.load("flaky-lockfile", store)
        for row in state["runs"]:
            expected = "pass" if row["values"]["node"] == "18" else "fail"
            assert row["results"] == [expected]


def test_metric_missing_can_be_recorded_as_a_fail():
    with tempfile.TemporaryDirectory() as store:
        opened(store)
        runner.main(
            [
                "flaky-lockfile",
                "--cmd",
                "echo lap={node}",
                "--metric",
                r"p95=([0-9.]+)",
                "--metric-missing",
                "fail",
                "--store",
                store,
            ]
        )
        state = experiment.load("flaky-lockfile", store)
        assert all(row["results"] == ["fail"] for row in state["runs"])


def test_metric_missing_defaults_to_stopping():
    with tempfile.TemporaryDirectory() as store:
        opened(store)
        try:
            runner.main(
                ["flaky-lockfile", "--cmd", "true", "--metric", r"p95=([0-9.]+)",
                 "--store", store]
            )
        except ValueError as error:
            assert "--metric-missing fail" in str(error)
            return
        raise AssertionError("silently accepted a run with no measurement")


def test_resume_tops_up_every_row_to_the_repeat_count():
    """The reason repeats sweep the whole array is a balanced repetition count;
    a resumed sheet used to re-run the full count on top of what it already
    held, which unbalances exactly that."""
    with tempfile.TemporaryDirectory() as store:
        state = opened(store, repeats=3)
        experiment.record(state, 1, ["pass"], [])
        experiment.record(state, 2, ["pass"], [])
        experiment.save(state, store)
        runner.main(["flaky-lockfile", "--cmd", "true", "--store", store])
        state = experiment.load("flaky-lockfile", store)
        assert [len(row["results"]) for row in state["runs"]] == [3, 3, 3, 3]
        assert experiment.outstanding(state) == []


def test_repeats_flag_tops_a_finished_sheet_up():
    with tempfile.TemporaryDirectory() as store:
        opened(store, repeats=1)
        runner.main(["flaky-lockfile", "--cmd", "true", "--store", store])
        runner.main(
            ["flaky-lockfile", "--cmd", "true", "--store", store, "--repeats", "2"]
        )
        state = experiment.load("flaky-lockfile", store)
        assert [len(row["results"]) for row in state["runs"]] == [2, 2, 2, 2]


def test_redo_replaces_rather_than_adds():
    with tempfile.TemporaryDirectory() as store:
        opened(store, repeats=2)
        runner.main(["flaky-lockfile", "--cmd", "true", "--store", store])
        runner.main(["flaky-lockfile", "--cmd", "true", "--store", store, "--redo"])
        state = experiment.load("flaky-lockfile", store)
        assert [len(row["results"]) for row in state["runs"]] == [2, 2, 2, 2]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: ok")
