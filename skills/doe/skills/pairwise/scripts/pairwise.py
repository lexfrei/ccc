"""Greedy pairwise covering array generator.

Usage: pairwise.py "os=linux,macos" "node=18,20,22" "cache=cold,warm"

Prints a markdown run sheet in which every pair of factor levels appears
in at least one row. Deterministic: the same spec always yields the same
array. The result is verified before printing; an uncovered pair is a
crash, never a silent gap.
"""

import sys
from itertools import combinations


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
        factors[name] = levels
    if len(factors) < 2:
        raise ValueError("need at least 2 factors")
    return factors


def _pair_key(idx, f1, v1, f2, v2):
    if idx[f1] > idx[f2]:
        f1, v1, f2, v2 = f2, v2, f1, v1
    return (f1, v1, f2, v2)


def _all_pairs(factors, idx):
    pairs = set()
    for a, b in combinations(factors, 2):
        for va in factors[a]:
            for vb in factors[b]:
                pairs.add(_pair_key(idx, a, va, b, vb))
    return pairs


def generate(factors):
    idx = {name: i for i, name in enumerate(factors)}
    fill_order = sorted(factors, key=lambda n: (-len(factors[n]), idx[n]))
    uncovered = _all_pairs(factors, idx)
    rows = []
    while uncovered:
        # Seeding from an uncovered pair guarantees progress every row;
        # a purely greedy row can come out fully covered and loop forever.
        f1, v1, f2, v2 = min(uncovered)
        row = {f1: v1, f2: v2}
        for name in fill_order:
            if name in row:
                continue
            row[name] = max(
                factors[name],
                key=lambda lv: sum(
                    1
                    for other, value in row.items()
                    if _pair_key(idx, name, lv, other, value) in uncovered
                ),
            )
        uncovered -= {
            _pair_key(idx, a, row[a], b, row[b])
            for a, b in combinations(row, 2)
        }
        rows.append({name: row[name] for name in factors})
    return rows


def verify(rows, factors):
    idx = {name: i for i, name in enumerate(factors)}
    missing = _all_pairs(factors, idx)
    for row in rows:
        missing -= {
            _pair_key(idx, a, row[a], b, row[b])
            for a, b in combinations(row, 2)
        }
    return sorted(missing)


def main(argv):
    factors = parse_spec(argv)
    rows = generate(factors)
    missing = verify(rows, factors)
    if missing:
        raise AssertionError(f"generator bug, uncovered pairs: {missing}")
    names = list(factors)
    print("| Run | " + " | ".join(names) + " | Result |")
    print("| --- | " + " | ".join("---" for _ in names) + " | --- |")
    for i, row in enumerate(rows, 1):
        print(f"| {i} | " + " | ".join(row[n] for n in names) + " | |")
    full = 1
    for levels in factors.values():
        full *= len(levels)
    print(f"\n{len(rows)} runs, all pairs covered (full factorial: {full})")


if __name__ == "__main__":
    main(sys.argv[1:])
