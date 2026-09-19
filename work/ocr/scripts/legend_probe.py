#!/usr/bin/env python3
"""Measure each legend swatch's texture, to see what the sheet's own key can teach.

The idea under test was step (a) of the 2026-09-19 plan: read `LEGEND_SWATCHES`
off the sheet's own legend box instead of hand-sampling them, and widen the
prototype from `(r - g, r - b)` to include texture, so a class is matched by how
it is drawn as well as by what colour it is. The legend is the only labelled
sample of each symbol at the sheet's own scale and hand, so it is free
per-sheet supervision and the obvious generalisation mechanism to other styles.

**Measured on the 1882 Plan Cadastral, and the texture half of that plan is
dead.** Legend box [9681, 6961, 1754, 988] at *native* source resolution:

    class    n_int  n_use   use%     coh     ink
    blue      9200   8971  97.5%   0.854   0.165
    admin     8955   8906  99.5%   0.925   0.566
    cream     9200   1384  15.0%   0.110   0.002
    green     9154   8654  94.5%   0.795   0.003
    salmon    8955   8812  98.4%   0.827   0.077

Coherence separates printed-anything from bare paper and nothing else. Only
cream is low; the other four sit in a 0.79-0.93 band. Green is the proof —
0.795 coherence on 0.3% ink density, because the green *tint* is not a wash at
all but a fine diagonal ruling, and so are salmon and blue. Every pigment class
on this sheet is engraved as ruled line work, which is exactly why how-ruled-it-
is cannot tell them apart. The admin-vs-blue gap of 0.072 is smaller than the
0.13 spread across four unmistakable classes; green-vs-blue would "separate" by
0.059 on the same logic. No threshold belongs on this axis.

Ink density does ladder cleanly — admin 0.566 > blue 0.165 > salmon 0.077 >
green 0.003 ~ cream 0.002 — hatch, ruling, tint, paper in one number, agreeing
with the 59.6 / 21.6 / 10.6 figures in the `LEGEND_SWATCHES` comment to within
3-5pp. (That residual is unexplained and probably a render-scale difference in
the original sampling; reconcile it before deriving any threshold.) Green and
cream are indistinguishable on it, so the hue terms stay load-bearing. The
surviving prototype is therefore `(r - g, r - b, ink_density)`, and coherence
stays where it already earns its place: the paper/not-paper and ripple/stipple
gate in `ruling_mask`.

Read at native resolution deliberately — `HATCH_COHERENCE` records that the
hatch aliases away as the sheet is shrunk.

    python work/ocr/scripts/iiif_tiles.py  # (or, inline:)
    python -c "from iiif_tiles import fetch_crop; \
      fetch_crop('https://iiif.maparchive.vn/iiif/0e02b9d9-9d40-4cca-8e41-8c8373d54d3b', \
                 9681, 6961, 1754, 988, size=1754, fit=True).save('legend.png')"
    python work/ocr/scripts/legend_probe.py legend.png

Exits non-zero if the detected swatches disagree with `LEGEND_SWATCHES`, which
is the whole check: the medians are known, so they prove the five rectangles
were found and ordered correctly before any texture number is believed.

ponytail: one sheet's legend box, and the five class names in source order.
Ceiling: every other sheet. The run now reads the largest `legend` triage box under
`--legend-swatches auto`; this standalone texture probe still takes a crop.
Reading class names off the adjacent lettering remains unbuilt, so both paths
still assume the 1882 class order and reject colours outside its fixed-key gate.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from colour_blocks import find_swatches, groups, longest_run

# Source order, top to bottom, in the 1882 legend box.
NAMES = ["blue", "admin", "cream", "green", "salmon"]
# colour_blocks.LEGEND_SWATCHES, as (r - g, r - b). Not fitted to — asserted against.
KNOWN = np.array([(0.000, 0.008), (0.039, 0.067), (0.059, 0.149),
                  (0.016, 0.122), (0.165, 0.263)])
INK_V = 0.55        # colour_blocks.INK_V
MIN_GRAD = 0.02     # colour_blocks.ink_coherence


def coherence(rgb):
    """Structure-tensor coherence, `ink_coherence` read on a rectangle.

    Measured on the gradient rather than on thresholded ink, for the reason in
    `colour_blocks.ink_coherence` — a one-pixel line comes back broken and a
    broken line has no direction left. Returns the pixel count that cleared
    `MIN_GRAD` alongside the ratio, because a high score on a handful of pixels
    is noise and the count is the only thing that says which one you have.
    """
    grey = rgb.mean(axis=2) / 255
    gy, gx = np.gradient(grey)
    use = np.hypot(gx, gy) > MIN_GRAD
    if use.sum() < 200:
        return float("nan"), int(use.sum())
    jxx, jyy = (gx[use] ** 2).sum(), (gy[use] ** 2).sum()
    jxy = (gx[use] * gy[use]).sum()
    return float(np.hypot(jxx - jyy, 2 * jxy) / (jxx + jyy)), int(use.sum())


def main(path):
    rgb = np.asarray(Image.open(path).convert("RGB"))
    print(f"{'class':<7}{'n_int':>7}{'n_use':>7}{'use%':>7}{'r-g':>8}{'r-b':>8}"
          f"{'ink':>8}{'coh':>8}")
    medians = []
    for name, (t, b, left, right) in zip(NAMES, find_swatches(rgb)):
        sw = rgb[t + 4:b + 1 - 4, left + 4:right + 1 - 4]    # 4 px in, past the border
        flat = sw.reshape(-1, 3) / 255
        med = np.median(flat, axis=0)
        ink = float((flat.max(axis=1) < INK_V).mean())
        coh, n_use = coherence(sw)
        medians.append((med[0] - med[1], med[0] - med[2]))
        print(f"{name:<7}{len(flat):7d}{n_use:7d}{100 * n_use / len(flat):6.1f}%"
              f"{med[0] - med[1]:8.3f}{med[0] - med[2]:8.3f}{ink:8.3f}{coh:8.3f}")

    delta = np.abs(np.array(medians) - KNOWN)
    print("max median delta vs LEGEND_SWATCHES:", f"{delta.max():.3f}")
    if delta.max() > 0.04:
        worst = NAMES[int(delta.max(axis=1).argmax())]
        sys.exit(f"swatch detection disagrees with the key (worst: {worst}) — "
                 "the rectangles are wrong or out of order, so the texture "
                 "numbers above mean nothing")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip().splitlines()[0] + "\n\nusage: legend_probe.py <legend.png>")
    main(Path(sys.argv[1]))
