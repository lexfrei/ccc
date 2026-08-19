"""The experiment journal: a designed run plan that survives the session.

Usage:
  experiment.py new "flaky lockfile" --factor "os=ubuntu,macos" \
      --factor "node=18,20" --factor "cache=warm,cold" --repeats 2
  experiment.py list
  experiment.py show flaky-lockfile
  experiment.py baseline flaky-lockfile --good pass --bad fail
  experiment.py record flaky-lockfile --run 3 --result fail --covariate region=eu
  experiment.py csv flaky-lockfile | tee results.csv
  experiment.py close flaky-lockfile --verdict "node 18 with a fresh lockfile"

An array is 8-18 runs of CI round-trips: hours, often days, and more than one
session. Everything the analysis needs — the hypothesis, the column
assignment, which rows are done, the covariates, the baselines — lives in
.doe/<slug>.json instead of in a chat log that will be gone by the time the
last row finishes.
"""

import argparse
import csv
import io
import json
import os
import re
import sys
from datetime import datetime

from design import build, parse_spec, select

STORE = ".doe"
COVARIATE_PREFIX = "cov_"


def slugify(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        raise ValueError("title has no usable characters for a slug")
    return slug[:60]


def path_for(slug, store=STORE):
    return os.path.join(store, f"{slug}.json")


def load(slug, store=STORE):
    try:
        with open(path_for(slug, store)) as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise ValueError(f"no experiment {slug!r} in {store}/ — `list` shows them")


def save(state, store=STORE):
    os.makedirs(store, exist_ok=True)
    with open(path_for(state["slug"], store), "w") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")


def now():
    return datetime.now().isoformat(timespec="seconds")


def create(title, specs, hypothesis, repeats, array, store=STORE):
    if repeats < 1:
        raise ValueError("--repeats is runs per row: 1 or more, not 0")
    factors = parse_spec(specs)
    name, placement = select(factors, array)
    runs = build(factors, name, placement)
    state = {
        "slug": slugify(title),
        "title": title,
        "hypothesis": hypothesis or "",
        "created": now(),
        "updated": now(),
        "status": "open",
        "array": name,
        "repeats": repeats,
        "factors": factors,
        "columns": {n: chr(ord("A") + c) for n, (c, _) in placement.items()},
        "dummy_treated": [n for n, (_, dummy) in placement.items() if dummy],
        "baselines": {"good": None, "bad": None},
        "runs": [
            {"run": i, "values": values, "results": [], "covariates": {}}
            for i, values in enumerate(runs, 1)
        ],
        "verdict": None,
    }
    if os.path.exists(path_for(state["slug"], store)):
        raise ValueError(
            f"{path_for(state['slug'], store)} exists — pick another title, or "
            "`show` it: an unfinished experiment is worth resuming, not restarting"
        )
    save(state, store)
    return state


def outstanding(state, repeats=None):
    """Rows that still owe results. `repeats` overrides the journal's own count,
    so `run.py --repeats N` tops a half-filled sheet up to N instead of asking
    the journal how many it once wanted."""
    target = max(1, state.get("repeats", 1) if repeats is None else repeats)
    return [run["run"] for run in state["runs"] if len(run["results"]) < target]


def describe(state):
    lines = [
        f"**{state['title']}** ({state['slug']}) — {state['status']}, "
        f"{state['array']}, {len(state['runs'])} runs x {state['repeats']} repeat(s)",
    ]
    if state["hypothesis"]:
        lines.append(f"Hypothesis: {state['hypothesis']}")
    good, bad = state["baselines"]["good"], state["baselines"]["bad"]
    if good is None or bad is None:
        lines.append(
            "**Baselines not recorded.** Run the known-good config (must pass) "
            "and the known-bad one (must fail) before spending the array: "
            "`baseline <slug> --good pass --bad fail`."
        )
    else:
        lines.append(f"Baselines: good={good}, bad={bad}")
        if good in ("fail", "failed") or bad in ("pass", "passed"):
            lines.append(
                "  A baseline contradicts the setup — the factor list or the "
                "levels are wrong, and the array cannot fix that."
            )
    names = list(state["factors"])
    lines.append("")
    lines.append("| Run | " + " | ".join(names) + " | Results |")
    lines.append("| --- | " + " | ".join("---" for _ in names) + " | --- |")
    for run in state["runs"]:
        results = ", ".join(str(r) for r in run["results"]) or "—"
        lines.append(
            f"| {run['run']} | "
            + " | ".join(run["values"][n] for n in names)
            + f" | {results} |"
        )
    left = outstanding(state)
    lines.append("")
    if left:
        lines.append(
            f"{len(left)} run(s) still open: {', '.join(str(i) for i in left)}. "
            "Record them with `record`, or let `run.py` execute the sheet."
        )
    else:
        lines.append(
            "Every row is in. Next: `csv <slug> | tee results.csv` and "
            "`analyze.py results.csv`."
        )
    if state["verdict"]:
        lines.append(f"Verdict: {state['verdict']}")
    return "\n".join(lines)


def record(state, run_index, results, covariates, replace=False):
    for run in state["runs"]:
        if run["run"] == run_index:
            break
    else:
        raise ValueError(f"run {run_index} is not in this array")
    if replace:
        run["results"] = list(results)
    else:
        run["results"].extend(results)
    for pair in covariates:
        name, _, value = pair.partition("=")
        if not value:
            raise ValueError(f"covariate needs name=value: {pair!r}")
        run["covariates"][name.strip()] = value.strip()
    state["updated"] = now()
    return state


def to_csv(state):
    names = list(state["factors"])
    covariates = covariate_names(state)
    width = max([len(run["results"]) for run in state["runs"]] + [1])
    # Covariates ship prefixed: the journal knows which columns were never
    # assigned to a array column, and analyze.py must not rank them as factors.
    header = (
        ["run"]
        + names
        + [f"result_{i}" for i in range(1, width + 1)]
        + [f"{COVARIATE_PREFIX}{name}" for name in covariates]
    )
    # csv.writer, not ",".join: a level or a covariate holding a comma, a quote
    # or a newline would otherwise emit a row wider than its header, and
    # analyze.py reads the shifted columns as data.
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for run in state["runs"]:
        results = [str(r) for r in run["results"]] + [""] * (width - len(run["results"]))
        writer.writerow(
            [str(run["run"])]
            + [run["values"][n] for n in names]
            + results
            + [run["covariates"].get(c, "") for c in covariates]
        )
    return buffer.getvalue().rstrip("\n")


def covariate_names(state):
    return sorted({key for run in state["runs"] for key in run["covariates"]})


def listing(store=STORE):
    if not os.path.isdir(store):
        return f"no {store}/ directory — nothing designed here yet"
    lines = []
    for entry in sorted(os.listdir(store)):
        if not entry.endswith(".json"):
            continue
        state = load(entry[:-5], store)
        left = outstanding(state)
        lines.append(
            f"{state['slug']:<28} {state['status']:<8} {state['array']:<4} "
            f"{len(state['runs']) - len(left)}/{len(state['runs'])} runs done"
            + (f" — {state['title']}" if state["title"] != state["slug"] else "")
        )
    return "\n".join(lines) or f"{store}/ is empty"


def main(argv):
    parser = argparse.ArgumentParser(description="Persist a designed experiment.")
    parser.add_argument("--store", default=STORE, help=f"journal directory ({STORE})")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="design an array and open the journal")
    new.add_argument("title")
    new.add_argument("--factor", action="append", default=[], required=True)
    new.add_argument("--hypothesis", default="")
    new.add_argument("--repeats", type=int, default=1)
    new.add_argument("--array", help="force an array (L4, L8, L9, L12, L18)")

    sub.add_parser("list", help="every experiment in the journal")

    show = sub.add_parser("show", help="status, sheet, what is still open")
    show.add_argument("slug")

    base = sub.add_parser("baseline", help="record the two mandatory baselines")
    base.add_argument("slug")
    base.add_argument("--good", help="outcome of the known-good config")
    base.add_argument("--bad", help="outcome of the known-bad config")

    rec = sub.add_parser("record", help="record the outcome of one run")
    rec.add_argument("slug")
    rec.add_argument("--run", type=int, required=True)
    rec.add_argument("--result", action="append", default=[], required=True)
    rec.add_argument("--covariate", action="append", default=[])
    rec.add_argument("--replace", action="store_true", help="overwrite, not append")

    csv_cmd = sub.add_parser("csv", help="emit the results for analyze.py")
    csv_cmd.add_argument("slug")

    close = sub.add_parser("close", help="close it out with the verdict")
    close.add_argument("slug")
    close.add_argument("--verdict", required=True)

    opts = parser.parse_args(argv)
    store = opts.store

    if opts.command == "new":
        state = create(
            opts.title, opts.factor, opts.hypothesis, opts.repeats, opts.array, store
        )
        print(f"{path_for(state['slug'], store)}\n")
        print(describe(state))
    elif opts.command == "list":
        print(listing(store))
    elif opts.command == "show":
        print(describe(load(opts.slug, store)))
    elif opts.command == "baseline":
        state = load(opts.slug, store)
        if opts.good is not None:
            state["baselines"]["good"] = opts.good
        if opts.bad is not None:
            state["baselines"]["bad"] = opts.bad
        state["updated"] = now()
        save(state, store)
        print(describe(state))
    elif opts.command == "record":
        state = record(
            load(opts.slug, store),
            opts.run,
            opts.result,
            opts.covariate,
            opts.replace,
        )
        save(state, store)
        print(describe(state))
    elif opts.command == "csv":
        state = load(opts.slug, store)
        print(to_csv(state))
        names = covariate_names(state)
        if names:
            # The journal knows which columns are covariates; the CSV cannot say
            # so, and analyze.py reads an unnamed column as a factor.
            print(
                "note: covariate column(s) "
                + ", ".join(names)
                + " — pass them to analyze.py as "
                + " ".join(f"--covariate {n}" for n in names),
                file=sys.stderr,
            )
    elif opts.command == "close":
        state = load(opts.slug, store)
        state["status"] = "closed"
        state["verdict"] = opts.verdict
        state["updated"] = now()
        save(state, store)
        print(describe(state))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
