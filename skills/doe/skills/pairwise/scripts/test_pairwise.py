"""Runnable with pytest or directly: python3 test_pairwise.py"""

from pairwise import generate, parse_spec, verify

MIXED = {
    "net": ["fast", "slow", "flaky", "off"],
    "browser": ["chrome", "firefox", "safari"],
    "os": ["linux", "macos"],
    "cache": ["cold", "warm"],
}


def test_covers_all_pairs():
    assert verify(generate(MIXED), MIXED) == []


def test_row_count_bounds():
    rows = generate(MIXED)
    # Lower bound: the two largest factors alone need 4*3 rows.
    assert 12 <= len(rows) < 48


def test_deterministic():
    assert generate(MIXED) == generate(MIXED)


def test_every_level_appears():
    rows = generate(MIXED)
    for name, levels in MIXED.items():
        assert {row[name] for row in rows} == set(levels)


def test_verify_detects_gap():
    rows = generate(MIXED)
    assert verify(rows[:-1], MIXED) != []


def test_two_factors_is_full_factorial():
    spec = {"a": ["1", "2"], "b": ["x", "y", "z"]}
    rows = generate(spec)
    assert len(rows) == 6
    assert verify(rows, spec) == []


def test_parse_spec():
    parsed = parse_spec(["os=linux,macos", "node=18,20,22"])
    assert parsed == {"os": ["linux", "macos"], "node": ["18", "20", "22"]}
    for bad in (
        ["os=linux"],
        ["os=linux,macos"],
        ["os=linux,macos", "os=a,b"],
        ["os=linux,macos", "node=18,18"],
        ["=a,b", "os=linux,macos"],
    ):
        try:
            parse_spec(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted invalid spec: {bad}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: ok")
