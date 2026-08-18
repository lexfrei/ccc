"""The Taguchi arrays, verified rather than trusted.

Every array below is checked for pairwise balance at import time: for each
pair of columns, every level combination appears equally often. A transposed
digit — the failure mode a hand-copied table has — raises on import instead
of quietly destroying the balance the whole main-effects analysis rests on.
"""

from collections import Counter
from itertools import combinations

ARRAYS = {
    "L4": """
        1 1 1
        1 2 2
        2 1 2
        2 2 1
    """,
    "L8": """
        1 1 1 1 1 1 1
        1 1 1 2 2 2 2
        1 2 2 1 1 2 2
        1 2 2 2 2 1 1
        2 1 2 1 2 1 2
        2 1 2 2 1 2 1
        2 2 1 1 2 2 1
        2 2 1 2 1 1 2
    """,
    "L9": """
        1 1 1 1
        1 2 2 2
        1 3 3 3
        2 1 2 3
        2 2 3 1
        2 3 1 2
        3 1 3 2
        3 2 1 3
        3 3 2 1
    """,
    "L12": """
        1 1 1 1 1 1 1 1 1 1 1
        1 1 1 1 1 2 2 2 2 2 2
        1 1 2 2 2 1 1 1 2 2 2
        1 2 1 2 2 1 2 2 1 1 2
        1 2 2 1 2 2 1 2 1 2 1
        1 2 2 2 1 2 2 1 2 1 1
        2 1 2 2 1 1 2 2 1 2 1
        2 1 2 1 2 2 2 1 1 1 2
        2 1 1 2 2 2 1 2 2 1 1
        2 2 2 1 1 1 1 2 2 1 2
        2 2 1 2 1 2 1 1 1 2 2
        2 2 1 1 2 1 2 1 2 2 1
    """,
    "L18": """
        1 1 1 1 1 1 1 1
        1 1 2 2 2 2 2 2
        1 1 3 3 3 3 3 3
        1 2 1 1 2 2 3 3
        1 2 2 2 3 3 1 1
        1 2 3 3 1 1 2 2
        1 3 1 2 1 3 2 3
        1 3 2 3 2 1 3 1
        1 3 3 1 3 2 1 2
        2 1 1 3 3 2 2 1
        2 1 2 1 1 3 3 2
        2 1 3 2 2 1 1 3
        2 2 1 2 3 1 3 2
        2 2 2 3 1 2 1 3
        2 2 3 1 2 3 2 1
        2 3 1 3 2 3 1 2
        2 3 2 1 3 1 2 3
        2 3 3 2 1 2 3 1
    """,
}


def parse(text):
    return [[int(x) for x in line.split()] for line in text.strip().splitlines()]


def levels_per_column(rows):
    return [len({row[c] for row in rows}) for c in range(len(rows[0]))]


def imbalance(rows):
    """Column pairs whose level combinations are not equally frequent."""
    bad = []
    n = len(rows)
    for i, j in combinations(range(len(rows[0])), 2):
        seen = Counter((row[i], row[j]) for row in rows)
        li = len({row[i] for row in rows})
        lj = len({row[j] for row in rows})
        expected = n / (li * lj)
        if len(seen) != li * lj or any(v != expected for v in seen.values()):
            bad.append((i, j, dict(seen)))
    return bad


TABLES = {name: parse(text) for name, text in ARRAYS.items()}

for _name, _rows in TABLES.items():
    _bad = imbalance(_rows)
    if _bad:  # pragma: no cover - a corrupted table must never load
        raise AssertionError(f"{_name} is not pairwise balanced: {_bad[:3]}")
