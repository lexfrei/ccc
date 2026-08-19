"""Runnable with pytest or directly: python3 test_pairwise.py"""

import re

from pairwise import generate, parse_excludes, parse_spec, render, verify

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


CONSTRAINED = {
    "browser": ["chrome", "firefox", "safari"],
    "os": ["linux", "macos"],
    "net": ["fast", "slow", "flaky"],
}
NO_SAFARI_ON_LINUX = [{"browser": "safari", "os": "linux"}]


def test_restarts_never_lose_to_a_single_pass():
    for spec in (MIXED, CONSTRAINED, {f"f{i}": ["0", "1"] for i in range(11)}):
        assert len(generate(spec)) <= len(generate(spec, restarts=1))


def test_excluded_combination_never_runs():
    rows = generate(CONSTRAINED, NO_SAFARI_ON_LINUX)
    assert verify(rows, CONSTRAINED, NO_SAFARI_ON_LINUX) == []
    assert not [r for r in rows if r["browser"] == "safari" and r["os"] == "linux"]
    # Everything the constraint does not forbid is still covered.
    assert {(r["browser"], r["net"]) for r in rows} == {
        (b, n) for b in CONSTRAINED["browser"] for n in CONSTRAINED["net"]
    }


def test_verify_flags_an_illegal_row():
    rows = generate(CONSTRAINED, NO_SAFARI_ON_LINUX)
    rows[0] = dict(rows[0], browser="safari", os="linux")
    assert verify(rows, CONSTRAINED, NO_SAFARI_ON_LINUX) != []


def test_parse_excludes():
    assert parse_excludes(["browser=safari & os=linux"], CONSTRAINED) == [
        {"browser": "safari", "os": "linux"}
    ]
    for bad in (
        ["browser=safari"],
        ["browser=opera & os=linux"],
        ["shell=zsh & os=linux"],
        ["browser=safari & browser=chrome"],
        ["browser & os=linux"],
    ):
        try:
            parse_excludes(bad, CONSTRAINED)
        except ValueError:
            continue
        raise AssertionError(f"accepted invalid exclude: {bad}")


def test_impossible_constraints_are_rejected():
    spec = {"a": ["1", "2"], "b": ["x", "y"]}
    forbidden = parse_excludes(
        ["a=1 & b=x", "a=1 & b=y", "a=2 & b=x", "a=2 & b=y"], spec
    )
    try:
        generate(spec, forbidden)
    except ValueError:
        return
    raise AssertionError("accepted constraints with no runnable combination")


def test_render_escapes_pipes():
    spec = {"a": ["x|y", "z"], "b": ["1", "2"]}
    sheet = render(generate(spec), spec)
    assert "x\\|y" in sheet
    for line in sheet.splitlines():
        if line.startswith("|"):
            # Run + factors + Result columns, so one more pipe than columns.
            assert len(re.findall(r"(?<!\\)\|", line)) == len(spec) + 3


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: ok")
