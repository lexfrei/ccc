"""Greedy pairwise covering array generator with restarts and constraints.

Usage: pairwise.py "os=linux,macos" "node=18,20,22" "cache=cold,warm"
       pairwise.py "browser=chrome,firefox,safari" "os=linux,macos" \
           --exclude "browser=safari & os=linux"

Prints a markdown run sheet in which every reachable pair of factor levels
appears in at least one row. Deterministic: the same spec always yields the
same array. A single greedy pass overshoots the minimum by 10-30%, so the
generator runs it from several seeds and keeps the shortest array; the runs
it saves are the expensive thing here, the seeds cost milliseconds.

Rows that violate an --exclude constraint are never emitted, and pairs that
no legal row can contain are dropped from the target set instead of being
chased forever. The result is verified before printing; an uncovered
reachable pair is a crash, never a silent gap.
"""

import argparse
import random
import sys
from itertools import combinations

DEFAULT_RESTARTS = 64


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


def parse_excludes(args, factors):
    """"a=1 & b=2" -> {"a": "1", "b": "2"}: a combination that cannot be run."""
    forbidden = []
    for arg in args:
        clause = {}
        for term in arg.split("&"):
            name, sep, level = term.partition("=")
            name, level = name.strip(), level.strip()
            if not sep or not name or not level:
                raise ValueError(f"exclude term needs factor=level: {term!r}")
            if name not in factors:
                raise ValueError(f"exclude names unknown factor: {name!r}")
            if level not in factors[name]:
                raise ValueError(f"exclude names unknown level: {name}={level!r}")
            if name in clause:
                raise ValueError(f"factor twice in one exclude: {name!r}")
            clause[name] = level
        if len(clause) < 2:
            raise ValueError(
                f"exclude needs 2+ terms: {arg!r} — a single forbidden level is "
                "not a constraint, drop the level from the factor instead"
            )
        forbidden.append(clause)
    return forbidden


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


def _violates(assignment, forbidden):
    return any(
        all(assignment.get(name) == level for name, level in clause.items())
        for clause in forbidden
    )


def _complete(assignment, factors, order, forbidden):
    """Extend a partial row to a full legal one, or return None if impossible."""
    if _violates(assignment, forbidden):
        return None
    rest = [name for name in order if name not in assignment]
    if not rest:
        return dict(assignment)
    name, rest = rest[0], rest[1:]
    for level in factors[name]:
        candidate = dict(assignment, **{name: level})
        filled = _complete(candidate, factors, [name] + rest, forbidden)
        if filled is not None:
            return filled
    return None


def _reachable_pairs(factors, idx, forbidden):
    order = list(factors)
    return {
        pair
        for pair in _all_pairs(factors, idx)
        if _complete({pair[0]: pair[1], pair[2]: pair[3]}, factors, order, forbidden)
        is not None
    }


def _greedy(factors, idx, targets, forbidden, seed, shuffle):
    rnd = random.Random(seed)
    order = sorted(factors, key=lambda n: (-len(factors[n]), idx[n]))
    if shuffle:
        rnd.shuffle(order)
    uncovered = set(targets)
    rows = []
    while uncovered:
        # Seeding from an uncovered pair guarantees progress every row;
        # a purely greedy row can come out fully covered and loop forever.
        f1, v1, f2, v2 = rnd.choice(sorted(uncovered))
        row = {f1: v1, f2: v2}
        for name in order:
            if name in row:
                continue
            legal = [
                lv
                for lv in factors[name]
                if _complete(dict(row, **{name: lv}), factors, order, forbidden)
                is not None
            ]
            row[name] = max(
                legal,
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


def generate(factors, forbidden=(), restarts=DEFAULT_RESTARTS):
    idx = {name: i for i, name in enumerate(factors)}
    targets = _reachable_pairs(factors, idx, forbidden)
    if not targets:
        raise ValueError("constraints leave no runnable combination")
    best = None
    for seed in range(max(1, restarts)):
        rows = _greedy(factors, idx, targets, forbidden, seed, shuffle=bool(seed % 2))
        if best is None or len(rows) < len(best):
            best = rows
    return best


def verify(rows, factors, forbidden=()):
    """Reachable pairs no row covers, plus any row a constraint forbids."""
    idx = {name: i for i, name in enumerate(factors)}
    missing = _reachable_pairs(factors, idx, forbidden)
    illegal = []
    for i, row in enumerate(rows, 1):
        if _violates(row, forbidden):
            illegal.append(f"row {i} violates an exclude: {row}")
        missing -= {
            _pair_key(idx, a, row[a], b, row[b])
            for a, b in combinations(row, 2)
        }
    return illegal + sorted(missing)


def _cell(value):
    return value.replace("\\", "\\\\").replace("|", "\\|")


def render(rows, factors, forbidden=()):
    names = list(factors)
    full = 1
    for levels in factors.values():
        full *= len(levels)
    out = [
        "| Run | " + " | ".join(_cell(n) for n in names) + " | Result |",
        "| --- | " + " | ".join("---" for _ in names) + " | --- |",
    ]
    for i, row in enumerate(rows, 1):
        out.append(f"| {i} | " + " | ".join(_cell(row[n]) for n in names) + " | |")
    note = " (before constraints)" if forbidden else ""
    out.append(
        f"\n{len(rows)} runs, all reachable pairs covered "
        f"(full factorial: {full}{note})"
    )
    return "\n".join(out)


def main(argv):
    parser = argparse.ArgumentParser(
        description="Generate a pairwise covering array run sheet."
    )
    parser.add_argument("spec", nargs="+", metavar="factor=l1,l2,...")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar='"a=1 & b=2"',
        help="a combination that cannot be run; repeatable",
    )
    parser.add_argument(
        "--restarts",
        type=int,
        default=DEFAULT_RESTARTS,
        help=f"greedy restarts, shortest array wins (default {DEFAULT_RESTARTS})",
    )
    parser.add_argument("--json", action="store_true", help="emit rows as JSON")
    opts = parser.parse_args(argv)

    factors = parse_spec(opts.spec)
    forbidden = parse_excludes(opts.exclude, factors)
    rows = generate(factors, forbidden, opts.restarts)
    problems = verify(rows, factors, forbidden)
    if problems:
        raise AssertionError(f"generator bug: {problems}")
    if opts.json:
        import json

        print(json.dumps({"factors": factors, "runs": rows}, indent=2))
    else:
        print(render(rows, factors, forbidden))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (ValueError, AssertionError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
