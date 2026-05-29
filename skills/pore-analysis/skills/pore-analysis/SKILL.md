---
name: pore-analysis
description: Measure porosity, pore size/shape, lattice period and ordering (psi6, Voronoi coordination, radial g(r) and orientational correlation length) from a top-view SEM image of a porous film such as anodic aluminium oxide (AAO). You (the agent) read the image to calibrate and decide what to crop; a Python core does the heavy morphometry and flags results that contradict physics. Trigger when given a pore/membrane/AAO SEM micrograph and asked for porosity, pore diameter, interpore distance, or ordering. See "When to invoke".
argument-hint: "<image-path> [scale value if not 200 nm] [notes]"
---

# pore-analysis

Quantify a porous film from one top-view SEM micrograph: porosity, pore diameter and shape, interpore distance, wall thickness, lattice ordering, and — for anodic aluminium oxide — the inferred anodizing voltage.

## Design: vision decides, Python computes

The work splits in two, deliberately. **You** do everything that varies between instruments and cannot be hardcoded: look at the image, find the scale bar and measure its pixel length, read its nm value, decide what to crop out (info panel, label, debris), judge pore contrast polarity, and sanity-check the result with your eyes. **The Python core** (`scripts/pore_analysis.py`) does only the deterministic maths you cannot eyeball: segment with the parameters you give it, then compute porosity, per-pore size/shape over hundreds of pores, lattice period, and ordering (psi6, Voronoi, radial g(r) and orientational correlation length), and raise a physics-based trust check.

This split is the point. Do not look for an autodetect flag — there isn't one, on purpose. The next image may come from a different microscope with the scale bar elsewhere, a panel on a different edge, bright-on-dark pores, or a different label format. Your eyes adapt to that; a hardcoded detector would not.

## When to invoke

Invoke when the user provides a top-view SEM image of a porous/membrane structure and wants any of: porosity, pore size/diameter, pore shape, interpore distance, wall thickness, lattice ordering/regularity, or AAO process inference. Trigger phrases include "анализ пор", "пористость", "размер пор", "pore analysis", "AAO", "анодный оксид", "porous membrane SEM".

Do not invoke for cross-section/tilted SEM where pores are seen from the side (this core assumes top-view), non-porous imagery, or generic image editing.

## Dependencies

`pip install numpy scipy scikit-image matplotlib`. Reuse the user's venv if there is one; otherwise create one. matplotlib is optional — without it, figures are skipped but the report and CSV are still produced.

## Step 1 — Read the image and describe what you see

Open the image with the Read tool and state, explicitly, before doing anything else:

- The scale bar: where it is, its printed value (e.g. "200 nm"), and whether it is a thin measurement line (often with end ticks) or just a text label. A filled text-label plate is NOT a scale bar — measuring its width is the classic calibration error that halves every diameter.
- Any region to exclude: instrument info panel, label boxes, watermarks, charging artefacts, debris — and on which edge.
- Pore contrast: are pores darker or brighter than the matrix (`--pore-polarity dark|light`).
- Obvious tilt or astigmatism (pores all stretched the same way).

If the image was pasted inline and you have no file path, ask for a path on disk — the core reads a file.

## Step 2 — Measure the scale-bar length in pixels (precisely, then verify)

Find the bar with your eyes, then measure it precisely — do not eyeball the pixel count. A reliable way is to crop a tight strip around the bar and find the longest continuous run of bar-coloured pixels (or the distance between its end ticks). Adapt this to the image; it is an example, not a fixed method:

```python
# Example only — adjust rows/columns/threshold to the actual bar.
import numpy as np; from skimage import io, util
g = util.img_as_float(io.imread(PATH))
g = g if g.ndim == 2 else g[..., :3].mean(2)
row = g[BAR_ROW]                      # a row passing through the bar
white = row > 0.7                     # bar brightness; invert for a dark bar
idx = np.where(white)[0]
print("bar pixel span:", idx.min(), idx.max(), "len", idx.max() - idx.min())
```

Verify the number makes sense before trusting it: a 200 nm bar that comes out as a third of the pore spacing is wrong. If the bar is ambiguous (label vs line) or you cannot measure it confidently, STOP and ask the user for the bar length in pixels or for the original micrograph — never guess.

## Step 3 — Run the compute core with explicit parameters

```
python scripts/pore_analysis.py <image> --scale-px <N> --scale-nm <V> \
    [--bottom N] [--top N] [--left N] [--right N] \
    [--pore-polarity dark|light] [--threshold T] \
    [--min-pore-px N] [--max-pore-px N] [--zones] --outdir <dir>
```

Translate your Step 1/2 findings into flags: the crop margins remove the panel/label region; `--pore-polarity` matches the contrast; `--scale-px`/`--scale-nm` are your measured calibration. `--threshold` overrides Otsu only if segmentation is poor. `--zones` reports ordering per horizontal third (useful when one side genuinely looks more ordered — it quantifies that impression).

## Step 4 — Honour the trust check

The core returns exit code **2** when results contradict physics or themselves (interpore distance below the ~50 nm AAO floor, diameter spread implying non-pore objects, porosity out of 2–60 %, or interpore distance below pore diameter). On exit 2: do NOT report the numbers as findings. State the failing check, give the likely cause (usually a mis-measured scale bar or an uncropped panel), and ask the user how to proceed or fix the input and re-run. Exit 1 is a usage/segmentation error. Exit 0 means the checks passed.

## Step 5 — Verify the overlay, then report

Read `overlay.png`: every pore should be coloured and nothing spurious (panel text, debris, merged blobs) should be. If pores are missed or junk is caught, adjust polarity / threshold / crop / `--min-pore-px` and re-run. Only after the overlay looks right, quote absolute sizes.

Report from `pore_report.txt`. Separate what the image gives (porosity, diameter, shape, period, ordering, inferred voltage) from what it cannot. If the user expects a different size convention (equivalent-circle diameter vs ellipse major axis vs max feret), say which one you quoted and offer the others — they can differ by tens of percent for elliptical pores.

## Outputs

`pore_report.txt`, `pores.csv` (per-pore diameter, axes, eccentricity, area), and figures `histograms.png`, `overlay.png`, `defect_map.png` (Voronoi coordination), `order_map.png` (local |psi6|).

## Limits (state these, do not invent)

A top-view image cannot give membrane thickness, pore depth / aspect ratio, or barrier-layer thickness (need a cross-section SEM), nor elemental composition (need EDX/XPS), nor the anodizing current. Current at constant voltage is a process response, not encoded in the image; only the voltage follows from geometry (~2.5 nm/V interpore distance for AAO).
