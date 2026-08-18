"""Pick the smallest Taguchi array that fits the factors and render the run sheet.

Usage: design.py "os=ubuntu,macos" "node=18,20" "lockfile=frozen,fresh"
       design.py "gc=on,off" "pool=8,16,32" --json

Every factor takes 2 or 3 levels. A 2-level factor placed in a 3-level column
is dummy-treated (level 3 repeats level 1); the sheet says which factors that
happened to, because their level means rest on unequal run counts.

The point of the script is that nobody retypes an array by hand: the tables
self-check for pairwise balance at import (arrays.py), the assignment is
mechanical, and the sheet comes out with concrete values already substituted.
"""

import argparse
import sys

from arrays import TABLES, levels_per_column

# Smallest first; the first array that fits wins.
CANDIDATES = ["L4", "L8", "L9", "L12", "L18"]


def parse_spec(args):
    factors = {}
    for arg in args:
        name, _, rest = arg.partition("=")
        name = name.strip()
        levels = [lv.strip() for lv in rest.split(",") if lv.strip()]
        if not name or len(levels) < 2:
            raise ValueError(f"factor needs a name and 2+ levels: {arg!r}")
        if name in factors:
            raise ValueError(f"duplicate factor: {name}")
        if len(set(levels)) != len(levels):
            raise ValueError(f"duplicate level in factor: {arg!r}")
        if len(levels) > 3:
            raise ValueError(
                f"{name} has {len(levels)} levels; Taguchi arrays take 2 or 3 — "
                "drop a level or use the pairwise skill for arbitrary mixes"
            )
        factors[name] = levels
    if len(factors) < 3:
        raise ValueError(
            "need 3+ factors; one factor is a bisection, two are a 4-run factorial"
        )
    return factors


def assign(factors, array_name):
    """Map factors onto columns, or return None if the array cannot hold them.

    3-level factors take 3-level columns. 2-level factors prefer a real
    2-level column and fall back to dummy treatment in a 3-level one.
    """
    columns = levels_per_column(TABLES[array_name])
    free2 = [i for i, lv in enumerate(columns) if lv == 2]
    free3 = [i for i, lv in enumerate(columns) if lv == 3]
    placement = {}
    for name, levels in factors.items():
        if len(levels) == 3:
            if not free3:
                return None
            placement[name] = (free3.pop(0), False)
    for name, levels in factors.items():
        if len(levels) == 2:
            if free2:
                placement[name] = (free2.pop(0), False)
            elif free3:
                placement[name] = (free3.pop(0), True)
            else:
                return None
    return placement


def select(factors, forced=None):
    for name in [forced] if forced else CANDIDATES:
        if name not in TABLES:
            raise ValueError(f"unknown array: {name}")
        placement = assign(factors, name)
        if placement:
            return name, placement
    if forced:
        raise ValueError(
            f"{forced} has no room for these factors — drop --array and the "
            "smallest one that fits is picked for you"
        )
    raise ValueError(
        "no array below L18 fits these factors — shrink the suspect list first "
        "(the shrink skill), or split the factors across two experiments"
    )


def value_of(levels, dummy, level):
    """Level index from the array to a concrete value; dummy 3 repeats level 1."""
    if dummy and level == 3:
        return levels[0]
    return levels[level - 1]


def build(factors, array_name, placement):
    runs = []
    for row in TABLES[array_name]:
        runs.append(
            {
                name: value_of(factors[name], dummy, row[column])
                for name, (column, dummy) in placement.items()
            }
        )
    return runs


def _cell(value):
    return value.replace("\\", "\\\\").replace("|", "\\|")


def render(factors, array_name, placement, runs):
    names = list(factors)
    full = 1
    for levels in factors.values():
        full *= len(levels)
    out = [
        f"**{array_name}** — {len(runs)} runs "
        f"(full factorial: {full}), columns "
        + ", ".join(f"{n}={chr(ord('A') + placement[n][0])}" for n in names),
        "",
        "| Run | " + " | ".join(_cell(n) for n in names) + " | Result |",
        "| --- | " + " | ".join("---" for _ in names) + " | --- |",
    ]
    for i, run in enumerate(runs, 1):
        out.append(f"| {i} | " + " | ".join(_cell(run[n]) for n in names) + " | |")
    dummies = [n for n in names if placement[n][1]]
    if dummies:
        out += [
            "",
            "Dummy-treated (2 levels in a 3-level column, first level repeated): "
            + ", ".join(dummies)
            + ". Coverage holds and the level means stay unbiased, but they rest "
            "on unequal run counts — rank those factors against the others only "
            "when their effect clears the noise floor by a margin.",
        ]
    savings = full / len(runs)
    if savings < 3:
        out += [
            "",
            f"Only {savings:.1f}x cheaper than the full factorial ({full} runs). "
            "If a run is not genuinely expensive, run the factorial instead and "
            "read the interactions directly.",
        ]
    return "\n".join(out)


def main(argv):
    parser = argparse.ArgumentParser(
        description="Render a Taguchi run sheet for 2- and 3-level factors."
    )
    parser.add_argument("spec", nargs="+", metavar="factor=l1,l2[,l3]")
    parser.add_argument("--array", help="force an array (L4, L8, L9, L12, L18)")
    parser.add_argument("--json", action="store_true", help="emit runs as JSON")
    opts = parser.parse_args(argv)

    factors = parse_spec(opts.spec)
    array_name, placement = select(factors, opts.array)
    runs = build(factors, array_name, placement)
    if opts.json:
        import json

        print(
            json.dumps(
                {
                    "array": array_name,
                    "factors": factors,
                    "dummy_treated": [n for n, (_, d) in placement.items() if d],
                    "runs": runs,
                },
                indent=2,
            )
        )
    else:
        print(render(factors, array_name, placement, runs))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (ValueError, AssertionError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
