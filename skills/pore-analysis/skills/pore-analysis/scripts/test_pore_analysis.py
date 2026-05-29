"""Tests for pore_analysis.py.

Pins the contracts that are easy to break: the radial distribution g(r) is a
real translational metric distinct from the orientational correlation length;
degenerate/collinear centroid sets that Qhull cannot tessellate degrade to
empty ordering instead of raising; the tilt verdict does not fire on
near-circular pores where orientation is numerical noise; and the end-to-end
exit-code contract holds (0 ok / 2 trust-check failed).
"""

import importlib.util
import os

import numpy as np
import pytest
from skimage import io, draw, util

HERE = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location(
    "pore_analysis", os.path.join(HERE, "pore_analysis.py"))
pa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pa)


def hex_points(nx=12, ny=12, a=20.0):
    """Ideal hexagonal lattice of points."""
    pts = []
    for j in range(ny):
        for i in range(nx):
            pts.append((i * a + (j % 2) * a / 2, j * a * np.sqrt(3) / 2))
    return np.array(pts, dtype=float)


def make_image(path, a_px=24, r_px=6, nx=22, ny=22, margin=20):
    """Synthetic SEM-like image: dark circular pores on a hexagonal lattice."""
    h = int(margin * 2 + (ny - 1) * a_px * np.sqrt(3) / 2) + r_px
    w = margin * 2 + nx * a_px + r_px
    img = np.full((h, w), 0.8)
    for j in range(ny):
        for i in range(nx):
            x = margin + i * a_px + (j % 2) * a_px / 2
            y = margin + j * a_px * np.sqrt(3) / 2
            rr, cc = draw.disk((y, x), r_px, shape=img.shape)
            img[rr, cc] = 0.05
    io.imsave(path, util.img_as_ubyte(img))
    return w, h


# --- ordering: hexagonal lattice scores near 1 ----------------------------- #
def test_psi6_hexagonal_is_ordered():
    pts = hex_points()
    local6, _ = pa.psi6(pts)
    # Interior points (away from the boundary) should be near-perfect hexagons.
    cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
    interior = (np.abs(pts[:, 0] - cx) < 60) & (np.abs(pts[:, 1] - cy) < 60)
    assert local6[interior].mean() > 0.9


# --- QhullError hardening: degenerate sets must not crash ------------------ #
def test_psi6_collinear_does_not_crash():
    pts = np.array([[0, 0], [1, 0], [2, 0], [3, 0], [4, 0]], dtype=float)
    local6, psi = pa.psi6(pts)  # would raise QhullError before the fix
    assert local6.shape == (5,)
    assert not np.any(psi)


def test_voronoi_collinear_does_not_crash():
    pts = np.array([[0, 0], [1, 0], [2, 0], [3, 0], [4, 0]], dtype=float)
    coord = pa.voronoi_coordination(pts)  # would raise QhullError before
    assert coord.shape == (5,)
    assert np.all(coord == -1)


def test_geometry_few_points():
    pts = np.array([[0.0, 0.0], [1.0, 1.0]])
    assert not np.any(pa.psi6(pts)[0])
    assert np.all(pa.voronoi_coordination(pts) == -1)


# --- g(r) is a real radial distribution, distinct from g6 ------------------ #
def test_pair_correlation_first_peak_at_lattice_constant():
    a = 20.0
    pts = hex_points(a=a)
    span = pts.max(axis=0) - pts.min(axis=0)
    r, g, peaks = pa.pair_correlation(pts, (span[1] + a, span[0] + a), 6 * a)
    assert peaks.size >= 1
    first_peak_r = r[peaks[0]]
    assert abs(first_peak_r - a) < 0.25 * a  # first shell at the lattice const


def test_gr_and_correlation_length_are_distinct_quantities():
    pts = hex_points(a=20.0)
    gr = pa.pair_correlation(pts, (260, 260), 120)
    local6, psi = pa.psi6(pts)
    xi = pa.correlation_length(pts, psi, 20.0)
    # g(r) returns (r, g, peaks) — translational; correlation_length returns a
    # scalar/None — orientational. They are not the same object or type.
    assert isinstance(gr, tuple) and len(gr) == 3
    assert xi is None or np.isscalar(xi)


def test_correlation_length_guards_degenerate():
    pts = np.array([[0, 0], [1, 0], [2, 0]], dtype=float)
    assert pa.correlation_length(pts, np.zeros(3, complex), 1.0) is None


# --- end-to-end: clean image, exit 0, no tilt claim on round pores --------- #
def test_main_clean_image_exit0(tmp_path):
    img = tmp_path / "clean.png"
    make_image(str(img))
    out = tmp_path / "out"
    rc = pa.main([str(img), "--scale-px", "50", "--scale-nm", "200",
                  "--no-figures", "--outdir", str(out)])
    assert rc == 0
    report = (out / "pore_report.txt").read_text()
    # Round pores: tilt must NOT be inferred from orientation noise.
    assert "near-circular" in report
    assert "sample tilt" not in report.split("near-circular")[0][-200:]


def test_main_bad_scale_triggers_trust_check(tmp_path):
    img = tmp_path / "bad.png"
    make_image(str(img))
    out = tmp_path / "out"
    # scale-px far too large -> interpore distance below the 50 nm floor.
    rc = pa.main([str(img), "--scale-px", "200", "--scale-nm", "200",
                  "--no-figures", "--outdir", str(out)])
    assert rc == 2
    assert "TRUST CHECK FAILED" in (out / "pore_report.txt").read_text()


def test_gr_reported_in_output(tmp_path):
    img = tmp_path / "c.png"
    make_image(str(img))
    out = tmp_path / "out"
    pa.main([str(img), "--scale-px", "50", "--scale-nm", "200",
             "--no-figures", "--outdir", str(out)])
    assert "g(r) shells:" in (out / "pore_report.txt").read_text()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
