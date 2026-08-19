"""Execute a designed run sheet and fill the journal in as results land.

Usage:
  run.py flaky-lockfile --cmd 'make test OS={os} NODE={node} CACHE={cache}'
  run.py latency --cmd './bench --pool {pool} --batch {batch}' \
      --metric 'p95=([0-9.]+)' --repeats 3 --randomize

When a run is a command rather than a human errand, the array is one
invocation instead of 8-18 manual round-trips. Each result is written to the
journal the moment it lands, so a crash, a timeout or a Ctrl-C costs the
current run and nothing before it.

Repeats sweep the whole array, not one row at a time — that is what keeps the
repetition count balanced across levels, and it is why a drifting environment
does not masquerade as a factor effect. Without --metric the exit code is the
outcome (0 = pass); with it, the first capture group of the regex is read from
the output as a number.
"""

import argparse
import os
import random
import re
import shlex
import subprocess
import sys

import experiment


def substitute(template, values, use_shell):
    quoted = {
        name: value if use_shell else shlex.quote(value)
        for name, value in values.items()
    }
    try:
        return template.format(**quoted)
    except KeyError as missing:
        raise ValueError(
            f"--cmd references {missing} but the factors are: "
            + ", ".join(values)
        )


def extract(pattern, text):
    match = re.search(pattern, text)
    if not match:
        return None
    group = match.group(1) if match.groups() else match.group(0)
    try:
        return float(group)
    except ValueError:
        raise ValueError(f"--metric captured {group!r}, which is not a number")


def execute(command, use_shell, timeout, log_path):
    try:
        completed = subprocess.run(
            command if use_shell else shlex.split(command),
            shell=use_shell,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = completed.stdout + completed.stderr
        code = completed.returncode
    except subprocess.TimeoutExpired as expired:
        output = (expired.stdout or "") + (expired.stderr or "")
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        output += f"\n[timed out after {timeout}s]"
        code = None
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w") as handle:
            handle.write(f"$ {command}\n\n{output}")
    return code, output


def pending(state, only, redo, repeats=None):
    runs = [run["run"] for run in state["runs"]]
    if only:
        unknown = [i for i in only if i not in runs]
        if unknown:
            raise ValueError(f"run(s) not in this array: {unknown}")
        return list(only)
    if redo:
        return runs
    return experiment.outstanding(state, repeats)


def main(argv):
    parser = argparse.ArgumentParser(description="Run a designed sheet.")
    parser.add_argument("slug")
    parser.add_argument("--cmd", required=True, help="command template, {factor} substituted")
    parser.add_argument("--store", default=experiment.STORE)
    parser.add_argument("--repeats", type=int, help="sweeps of the whole array")
    parser.add_argument("--metric", help="regex whose first group is the numeric outcome")
    parser.add_argument(
        "--metric-missing",
        choices=["error", "fail"],
        default="error",
        help="no match for --metric: stop (default), or record the run as a fail",
    )
    parser.add_argument("--randomize", action="store_true", help="shuffle order per sweep")
    parser.add_argument("--seed", type=int, help="fix the shuffle for reproducibility")
    parser.add_argument("--timeout", type=float, help="seconds per run; a timeout is a fail")
    parser.add_argument("--shell", action="store_true", help="run through the shell")
    parser.add_argument("--only", type=int, action="append", help="run just these rows")
    parser.add_argument("--redo", action="store_true", help="rerun rows that already have results")
    parser.add_argument("--dry-run", action="store_true", help="print the commands, run nothing")
    opts = parser.parse_args(argv)

    state = experiment.load(opts.slug, opts.store)
    good, bad = state["baselines"]["good"], state["baselines"]["bad"]
    if (good is None or bad is None) and not opts.dry_run:
        raise ValueError(
            "baselines are not recorded — the known-good config must pass and "
            "the known-bad one must fail before the array is worth running "
            f"(`experiment.py baseline {opts.slug} --good ... --bad ...`)"
        )

    repeats = max(1, opts.repeats or state.get("repeats", 1))
    order = pending(state, opts.only, opts.redo, repeats)
    if not order:
        print("nothing left to run — every row has its results")
        return
    if opts.redo or opts.only:
        for run in state["runs"]:
            if run["run"] in order:
                run["results"] = []
        experiment.save(state, opts.store)

    rnd = random.Random(opts.seed)
    by_index = {run["run"]: run for run in state["runs"]}
    # What a row still owes, not what the sheet asks for as a whole: a resumed
    # array holds results already, and running the full count for every
    # selected row again is what unbalances the repetition count the whole-array
    # sweep exists to keep even.
    done = {run["run"]: len(run["results"]) for run in state["runs"]}
    for sweep in range(1, repeats + 1):
        sequence = [index for index in order if done[index] < sweep]
        if not sequence:
            continue
        if opts.randomize:
            rnd.shuffle(sequence)
        for index in sequence:
            done[index] += 1
            values = by_index[index]["values"]
            command = substitute(opts.cmd, values, opts.shell)
            label = f"sweep {sweep}/{repeats} run {index}"
            if opts.dry_run:
                print(f"{label}: {command}")
                continue
            log_path = os.path.join(
                opts.store, f"{opts.slug}-logs", f"run-{index}-sweep-{sweep}.log"
            )
            code, output = execute(command, opts.shell, opts.timeout, log_path)
            if opts.metric:
                value = extract(opts.metric, output)
                if value is None and opts.metric_missing == "error":
                    raise ValueError(
                        f"{label}: --metric matched nothing in the output — see "
                        f"{log_path}. A run that legitimately produces no "
                        "measurement is data: pass --metric-missing fail."
                    )
                result = "fail" if value is None else f"{value:g}"
            else:
                result = "pass" if code == 0 else "fail"
            state = experiment.record(
                experiment.load(opts.slug, opts.store), index, [result], []
            )
            experiment.save(state, opts.store)
            print(f"{label}: {result}")

    if not opts.dry_run:
        print()
        print(experiment.describe(experiment.load(opts.slug, opts.store)))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
