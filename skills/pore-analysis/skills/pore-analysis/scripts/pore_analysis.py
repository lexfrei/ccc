#!/usr/bin/env python3
"""Pore morphometry for SEM images — the deterministic compute core.

This script does NOT try to recognise the image. Recognition (finding the scale
bar and its pixel length, deciding what to crop, the pore contrast polarity) is
the caller's job — a vision-capable agent handles it per image, because those
things vary wildly between instruments and are brittle to hardcode. Here we only
do the maths that cannot be eyeballed: segment with the given parameters, then
measure porosity, pore size/shape, lattice period, and ordering (psi6, Voronoi
coordination), and flag results that contradict physics.

All calibration and region inputs are EXPLICIT and required where it matters:

    pore_analysis.py img.png --scale-px 68.5 --scale-nm 200 \
        --bottom 71 --pore-polarity dark --outdir out

Exit codes: 0 = ok; 2 = trust check failed (numbers contradict physics —
caller should stop and confirm, not report them); 1 = usage/segmentation error.

Dependencies: numpy, scipy, scikit-image; matplotlib optional (figures).
"""

import argparse
import csv
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree, Delaunay, Voronoi
try:  # QhullError moved to scipy.spatial in newer SciPy
    from scipy.spatial import QhullError
except ImportError:  # pragma: no cover - old SciPy
    from scipy.spatial.qhull import QhullError
from skimage import io, color, util
from skimage.filters import threshold_otsu
from skimage.measure import label, regionprops


def load_gray(path):
    """Load an image as float grayscale in [0, 1]."""
    img = io.imread(path)
    if img.ndim == 3:
        if img.shape[2] == 4:
            img = img[:, :, :3]
        img = color.rgb2gray(img)
    return util.img_as_float(img)


def crop_region(gray, top, bottom, left, right):
    """Crop the analysis region by pixel margins (each defaults to 0)."""
    h, w = gray.shape
    r0, r1 = top, h - bottom
    c0, c1 = left, w - right
    if r1 <= r0 or c1 <= c0:
        raise ValueError("Crop margins leave an empty region.")
    return gray[r0:r1, c0:c1]


def segment(work, polarity, threshold):
    """Binarise pores and label them. polarity: 'dark' or 'light' pores."""
    thr = threshold if threshold is not None else threshold_otsu(work)
    mask = work < thr if polarity == "dark" else work > thr
    mask = ndi.binary_fill_holes(mask)
    return label(mask), thr


def pore_table(labels, shape, nm_per_px, min_px, max_px):
    """Per-pore geometry; excludes components touching the region edge."""
    H, W = shape
    rows = []
    for rp in regionprops(labels):
        if rp.area < min_px or (max_px is not None and rp.area > max_px):
            continue
        minr, minc, maxr, maxc = rp.bbox
        if minr == 0 or minc == 0 or maxr == H or maxc == W:
            continue
        rows.append({
            "cx": rp.centroid[1], "cy": rp.centroid[0],
            "d_nm": rp.equivalent_diameter_area * nm_per_px,
            "major_nm": rp.axis_major_length * nm_per_px,
            "minor_nm": rp.axis_minor_length * nm_per_px,
            "ecc": rp.eccentricity,
            "orient_deg": np.degrees(rp.orientation),
            "area_nm2": rp.area * nm_per_px ** 2,
            "area_px": rp.area,
        })
    return rows


def psi6(points):
    """Per-point bond-orientational order |psi6| via Delaunay neighbours.

    Returns all-zero arrays (ordering unavailable) for fewer than 4 points or a
    degenerate/collinear set that Qhull cannot triangulate, rather than raising.
    """
    n = len(points)
    if n < 4:
        return np.zeros(n), np.zeros(n, complex)
    try:
        tri = Delaunay(points)
    except QhullError:
        return np.zeros(n), np.zeros(n, complex)
    neigh = [set() for _ in range(n)]
    for s in tri.simplices:
        for i in s:
            for j in s:
                if i != j:
                    neigh[i].add(j)
    psi = np.zeros(n, complex)
    for i in range(n):
        nb = list(neigh[i])
        ang = np.arctan2(points[nb, 1] - points[i, 1],
                         points[nb, 0] - points[i, 0])
        psi[i] = np.mean(np.exp(6j * ang))
    return np.abs(psi), psi


def voronoi_coordination(points):
    """Number of sides of each finite Voronoi cell (coordination number).

    Returns all -1 (no finite cell) for fewer than 4 points or a degenerate set
    Qhull cannot tessellate, rather than raising.
    """
    n = len(points)
    if n < 4:
        return np.full(n, -1)
    try:
        vor = Voronoi(points)
    except QhullError:
        return np.full(n, -1)
    ns = np.full(n, -1)
    for i, ridx in enumerate(vor.point_region):
        reg = vor.regions[ridx]
        if -1 in reg or len(reg) == 0:
            continue
        ns[i] = len(reg)
    return ns


def pair_correlation(points, shape, rmax_px, nbins=120):
    """Radial distribution function g(r): positional/translational ordering.

    Distinct from the orientational g6(r) in correlation_length(). g(r) peaks at
    successive coordination shells; the number of resolved peaks measures how
    far translational order persists. Returns (r_px, g, peak_idx) or None.
    """
    n = len(points)
    if n < 2:
        return None
    h, w = shape
    tree = cKDTree(points)
    pairs = tree.query_pairs(r=rmax_px, output_type="ndarray")
    if len(pairs) == 0:
        return None
    dr = np.linalg.norm(points[pairs[:, 0]] - points[pairs[:, 1]], axis=1)
    hist, edges = np.histogram(dr, bins=nbins, range=(0, rmax_px))
    r = (edges[:-1] + edges[1:]) / 2
    rho = n / (h * w)
    with np.errstate(divide="ignore", invalid="ignore"):
        g = hist / (rho * n * 2 * np.pi * r * (edges[1] - edges[0]))
    g = np.nan_to_num(g)
    from scipy.signal import find_peaks
    peaks, _ = find_peaks(g, height=1.1)
    return r, g, peaks


def correlation_length(points, psi, a0_px):
    """Orientational correlation length (where g6 drops below 1/e), in px."""
    if len(points) < 4 or not np.any(psi):
        return None
    tree = cKDTree(points)
    pairs = tree.query_pairs(r=8 * a0_px, output_type="ndarray")
    if len(pairs) == 0:
        return None
    dr = np.linalg.norm(points[pairs[:, 0]] - points[pairs[:, 1]], axis=1)
    corr = np.real(psi[pairs[:, 0]] * np.conj(psi[pairs[:, 1]]))
    bins = np.arange(0, 8 * a0_px, a0_px * 0.5)
    idx = np.digitize(dr, bins)
    rb = (bins[:-1] + bins[1:]) / 2
    for k in range(1, len(bins)):
        m = idx == k
        if m.any() and corr[m].mean() < 1 / np.e:
            return rb[k - 1]
    return None


def main(argv=None):
    p = argparse.ArgumentParser(description="Pore morphometry compute core.")
    p.add_argument("image")
    p.add_argument("--scale-px", type=float, required=True,
                   help="Scale-bar length in pixels (measured by the caller).")
    p.add_argument("--scale-nm", type=float, required=True,
                   help="Scale-bar value in nanometres.")
    p.add_argument("--top", type=int, default=0)
    p.add_argument("--bottom", type=int, default=0,
                   help="Pixels to crop from the bottom (e.g. info panel).")
    p.add_argument("--left", type=int, default=0)
    p.add_argument("--right", type=int, default=0)
    p.add_argument("--pore-polarity", choices=["dark", "light"], default="dark",
                   help="Are pores darker or brighter than the matrix.")
    p.add_argument("--threshold", type=float, default=None,
                   help="Manual brightness threshold [0-1]; default Otsu.")
    p.add_argument("--min-pore-px", type=int, default=10)
    p.add_argument("--max-pore-px", type=int, default=None)
    p.add_argument("--kp", type=float, default=2.5,
                   help="AAO interpore/voltage coefficient nm/V (default 2.5).")
    p.add_argument("--outdir", default=".")
    p.add_argument("--no-figures", action="store_true")
    p.add_argument("--zones", action="store_true")
    args = p.parse_args(argv)

    if args.scale_px <= 0:
        print("--scale-px must be positive.", file=sys.stderr)
        return 1
    nm_per_px = args.scale_nm / args.scale_px

    gray = load_gray(args.image)
    os.makedirs(args.outdir, exist_ok=True)
    try:
        work = crop_region(gray, args.top, args.bottom, args.left, args.right)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    labels, thr = segment(work, args.pore_polarity, args.threshold)
    rows = pore_table(labels, work.shape, nm_per_px,
                      args.min_pore_px, args.max_pore_px)
    if not rows:
        print("No pores found — check polarity/threshold/crop or calibration.",
              file=sys.stderr)
        return 1

    d = np.array([r["d_nm"] for r in rows])
    major = np.array([r["major_nm"] for r in rows])
    minor = np.array([r["minor_nm"] for r in rows])
    ecc = np.array([r["ecc"] for r in rows])
    orient = np.array([r["orient_deg"] for r in rows])
    pts = np.array([[r["cx"], r["cy"]] for r in rows])
    pts_y = np.array([r["cy"] for r in rows])
    n = len(rows)

    H, W = work.shape
    area_um2 = (H * W) * (nm_per_px / 1000) ** 2
    keep_ids = [rp.label for rp in regionprops(labels)
                if rp.area >= args.min_pore_px
                and (args.max_pore_px is None or rp.area <= args.max_pore_px)]
    porosity = 100.0 * np.isin(labels, keep_ids).sum() / labels.size

    if n < 2:
        print("Too few pores for lattice statistics (need >= 2).",
              file=sys.stderr)
        return 1
    nn = cKDTree(pts).query(pts, k=2)[0][:, 1] * nm_per_px
    period = float(np.median(nn))
    period_px = period / nm_per_px
    wall = period - float(np.median(d))

    local6, psi = psi6(pts)
    coord = voronoi_coordination(pts)
    inner = coord > 0
    # Ordering metrics need a non-degenerate point set; psi6/Voronoi return
    # zeros/-1 otherwise. Report them only when actually available.
    ordering_ok = bool(np.any(psi)) and bool(inner.any())
    glob6 = abs(psi.mean()) if ordering_ok else float("nan")
    hex_frac = 100.0 * (coord[inner] == 6).mean() if ordering_ok else float("nan")
    xi_px = correlation_length(pts, psi, period_px) if ordering_ok else None
    xi_nm = xi_px * nm_per_px if xi_px is not None else None
    gr = pair_correlation(pts, (H, W), 6 * period_px)

    # Pore-axis orientation is only meaningful for non-circular pores; for
    # near-circular blobs the orientation is numerical noise, so do not infer
    # tilt from it.
    if ecc.mean() < 0.35:
        tilt_line = ("pores near-circular — axis orientation not meaningful, "
                     "no tilt inference")
    else:
        ang2 = np.radians(orient * 2)
        R = np.hypot(np.mean(np.cos(ang2)), np.mean(np.sin(ang2)))
        tilt_line = ("random -> real pore shape, not sample tilt" if R < 0.5
                     else f"aligned (R={R:.2f}) -> possible sample tilt/astigmatism")
    volt = period / args.kp

    # Trust checks: surface results that contradict physics or themselves.
    warnings = []
    if period < 50:
        warnings.append(
            f"Interpore distance {period:.0f} nm is below the ~50 nm physical "
            "floor for self-organised AAO — calibration is very likely WRONG. "
            "Re-check the scale-bar pixel length.")
    if period > 600:
        warnings.append(f"Interpore distance {period:.0f} nm is unusually "
                        "large — verify the scale bar.")
    if d.std() / d.mean() > 0.5:
        warnings.append(
            f"Diameter spread is very broad (CV {100*d.std()/d.mean():.0f} %) — "
            "usually means non-pore objects were segmented (debris, merged "
            "pores, panel not cropped). Inspect the overlay; tune crop / "
            "--min-pore-px / polarity.")
    if porosity > 60 or porosity < 2:
        warnings.append(f"Porosity {porosity:.0f} % is outside the plausible "
                        "2-60 % range — check segmentation and calibration.")
    if period < float(np.median(d)):
        warnings.append(
            f"Interpore distance ({period:.0f} nm) below pore diameter "
            f"({np.median(d):.0f} nm) — geometrically impossible; segmentation "
            "or calibration is broken.")

    L = []
    L.append("=" * 60)
    L.append("PORE ANALYSIS")
    L.append("=" * 60)
    L.append(f"Calibration:        {nm_per_px:.4f} nm/px "
             f"({args.scale_nm:g} nm = {args.scale_px:g} px)")
    L.append(f"Field of view:      {W*nm_per_px/1000:.2f} x "
             f"{H*nm_per_px/1000:.2f} um  (analysed region)")
    L.append(f"Segmentation:       {args.pore_polarity} pores, "
             f"threshold {thr:.3f}")
    L.append("-" * 60)
    L.append(f"Porosity:           {porosity:.1f} %")
    L.append(f"Pore count:         {n} (edge pores excluded)")
    L.append(f"Pore density:       {n/area_um2:.1f} pores/um^2")
    L.append("-" * 60)
    L.append("Pore diameter (equivalent circle):")
    L.append(f"  mean +/- sd:      {d.mean():.1f} +/- {d.std():.1f} nm")
    L.append(f"  median:           {np.median(d):.1f} nm")
    L.append(f"  P10 / P90:        {np.percentile(d,10):.1f} / "
             f"{np.percentile(d,90):.1f} nm")
    L.append("Pore shape (ellipse):")
    L.append(f"  major / minor:    {major.mean():.1f} / {minor.mean():.1f} nm")
    L.append(f"  eccentricity:     {ecc.mean():.2f}")
    L.append("  axis orientation: " + tilt_line)
    L.append("-" * 60)
    L.append("Lattice:")
    L.append(f"  interpore dist.:  {period:.0f} nm (CV "
             f"{nn.std()/nn.mean()*100:.0f} %)")
    L.append(f"  wall thickness:   {wall:.0f} nm")
    L.append("Ordering:")
    if ordering_ok:
        L.append(f"  hexagonal (6 nb): {hex_frac:.0f} %")
        L.append(f"  local |psi6|:     {local6.mean():.2f} (1=perfect hexagon)")
        L.append(f"  global |<psi6>|:  {glob6:.2f}")
        L.append("  orient. corr. xi: " + (
            f"{xi_nm:.0f} nm (~{xi_nm/period:.1f} periods)" if xi_nm
            else f"> {8*period:.0f} nm (beyond window)"))
    else:
        L.append("  unavailable — degenerate/too-few pore centroids")
    if gr is not None:
        r_gr, g_gr, peaks_gr = gr
        shells = ", ".join(f"{r_gr[p]*nm_per_px:.0f}" for p in peaks_gr[:4])
        L.append(f"  g(r) shells:      {len(peaks_gr)} resolved"
                 + (f" at {shells} nm" if peaks_gr.size else ""))
    L.append("-" * 60)
    L.append("Process (AAO inference):")
    L.append(f"  est. voltage:     ~{volt:.0f} V (interpore {period:.0f} nm / "
             f"{args.kp:g} nm/V)")
    L.append("  note: current is a process response, NOT in the image; only "
             "voltage follows from geometry.")
    L.append("-" * 60)
    L.append("Limits (NOT from a top-view image): membrane thickness, pore "
             "depth/aspect, barrier layer (need cross-section); composition "
             "(need EDX/XPS).")
    if args.zones and ordering_ok:
        L.append("-" * 60)
        L.append("Ordering by horizontal third (|psi6| / hex%):")
        for name, lo_x, hi_x in [("left", 0, W/3), ("center", W/3, 2*W/3),
                                 ("right", 2*W/3, W)]:
            m = (pts[:, 0] >= lo_x) & (pts[:, 0] < hi_x)
            mi = m & inner
            if mi.any():
                L.append(f"  {name:7s}: {local6[m].mean():.2f} / "
                         f"{100*(coord[mi]==6).mean():.0f} %")
    if warnings:
        L.append("=" * 60)
        L.append("!! TRUST CHECK FAILED — results may be invalid, confirm "
                 "before use:")
        for wmsg in warnings:
            L.append("  - " + wmsg)
    L.append("=" * 60)
    report = "\n".join(L)
    print(report)
    with open(os.path.join(args.outdir, "pore_report.txt"), "w") as f:
        f.write(report + "\n")

    with open(os.path.join(args.outdir, "pores.csv"), "w", newline="") as f:
        wri = csv.writer(f)
        wri.writerow(["id", "diameter_nm", "major_axis_nm", "minor_axis_nm",
                      "eccentricity", "area_nm2"])
        for i, r in enumerate(rows, 1):
            wri.writerow([i, f"{r['d_nm']:.2f}", f"{r['major_nm']:.2f}",
                          f"{r['minor_nm']:.2f}", f"{r['ecc']:.3f}",
                          f"{r['area_nm2']:.1f}"])

    if not args.no_figures:
        try:
            write_figures(work, labels, pts, pts_y, local6, coord, d, nn,
                          nm_per_px, H, args.outdir, gr, ordering_ok)
        except ImportError:
            print("matplotlib not installed — skipping figures.",
                  file=sys.stderr)

    print(f"\nOutputs in: {os.path.abspath(args.outdir)}")
    return 2 if warnings else 0


def write_figures(work, labels, pts, pts_y, local6, coord, d, nn,
                  nm_per_px, H, outdir, gr=None, ordering_ok=True):
    """Histograms, g(r), segmentation overlay, defect map, |psi6| order map."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from skimage.color import label2rgb

    cols = 3 if gr is not None else 2
    fig, ax = plt.subplots(1, cols, figsize=(5.5 * cols, 4))
    ax[0].hist(d, bins=25, color="#33aa77", edgecolor="k", alpha=0.85)
    ax[0].axvline(np.median(d), color="r", ls="--",
                  label=f"median {np.median(d):.0f} nm")
    ax[0].set_xlabel("Pore diameter, nm"); ax[0].set_ylabel("Count")
    ax[0].legend(); ax[0].set_title(f"Diameter (N={len(d)})")
    ax[1].hist(nn, bins=25, color="#3377bb", edgecolor="k", alpha=0.85)
    ax[1].axvline(np.median(nn), color="r", ls="--",
                  label=f"median {np.median(nn):.0f} nm")
    ax[1].set_xlabel("Interpore distance, nm"); ax[1].set_ylabel("Count")
    ax[1].legend(); ax[1].set_title("Nearest-neighbour distance")
    if gr is not None:
        r_gr, g_gr, peaks_gr = gr
        ax[2].plot(r_gr * nm_per_px, g_gr, "-")
        ax[2].axhline(1, color="gray", ls=":")
        ax[2].plot(r_gr[peaks_gr] * nm_per_px, g_gr[peaks_gr], "rv")
        ax[2].set_xlabel("r, nm"); ax[2].set_ylabel("g(r)")
        ax[2].set_title("Pair correlation g(r)")
    plt.tight_layout(); plt.savefig(os.path.join(outdir, "histograms.png"), dpi=110)
    plt.close()

    ov = label2rgb(labels, image=work, bg_label=0, alpha=0.4)
    io.imsave(os.path.join(outdir, "overlay.png"),
              util.img_as_ubyte(np.clip(ov, 0, 1)))

    if not ordering_ok:
        return  # coordination / psi6 maps are meaningless on a degenerate set

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.imshow(work, cmap="gray")
    for k, c in {5: "#2255ff", 6: "#888888", 7: "#ff2222",
                 4: "#00cccc", 8: "#ffaa00"}.items():
        m = coord == k
        if m.any():
            ax.scatter(pts[m, 0], pts_y[m], s=14, c=c,
                       label=f"{k} nb ({m.sum()})", edgecolors="none")
    ax.legend(loc="upper right", framealpha=0.9, fontsize=9)
    ax.set_title("Coordination map: grey=6 (hex), blue=5 / red=7 = defects")
    ax.axis("off"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "defect_map.png"), dpi=110); plt.close()

    fig, ax = plt.subplots(figsize=(10, 7))
    sc = ax.scatter(pts[:, 0] * nm_per_px / 1000, (H - pts_y) * nm_per_px / 1000,
                    c=local6, cmap="RdYlGn", s=16, vmin=0.3, vmax=1)
    ax.set_aspect("equal"); ax.set_xlabel("um"); ax.set_ylabel("um")
    ax.set_title("Local orientational order |psi6| (green = hexagonal)")
    plt.colorbar(sc, ax=ax, fraction=0.046); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "order_map.png"), dpi=110); plt.close()


if __name__ == "__main__":
    sys.exit(main())
