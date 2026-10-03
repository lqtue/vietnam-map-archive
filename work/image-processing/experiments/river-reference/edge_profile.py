"""Where a road mask's edge sits against the ink stroke it follows (calibrate / seen windows only).

    work/ocr/.venv/bin/python work/image-processing/experiments/river-reference/edge_profile.py 1882 MASK.png [--windows ID,ID] [--all]

For each straight stretch of the mask's edge (the mask's smoothed normal agrees at 4 and 10 px) the ink
density 1 - grey / local paper is sampled along the normal, t = 0 at the edge, t > 0 into the road. The stroke
the edge follows is the ink run just outside it (t in -8..+1); its centre is the ink-weighted mean of the run
above half its peak. Side: the road lies lower-right of the wall (the block's lower-right side, drawn thick) or
upper-left of it (the block's upper-left side, a thin shadow line). Prints, per side: stretches, stroke width
(FWHM), centre offset from the edge, and the offset of the stroke's road-side half-max face. Refuses a window
that touches an unseen heldout box (view.py's rule). Default: the road windows that are calibrate or seen:true;
--all: every such window of either layer (a water window shows the road mask's edge against a quay or creek).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as nd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "work" / "image-processing" / "scripts"))
from sheet_features import paper_at  # noqa: E402
from view import touches  # noqa: E402

S = np.arange(-14, 14.01, 0.5)          # px along the normal
MARGIN = 40


def profiles(rgb, paper, road, y0, x0):
    """rgb / paper / road cover a window plus MARGIN; returns the arrays of one profile per straight edge pixel."""
    p = paper_at(paper, np.arange(y0, y0 + rgb.shape[0]) + 0.5, np.arange(x0, x0 + rgb.shape[1]) + 0.5)
    ink = np.clip(1 - (rgb.astype(np.float32) / p).mean(2), 0, 1)
    f = road.astype(np.float32)
    g1 = [nd.gaussian_filter(f, 4, order=o) for o in ((1, 0), (0, 1))]
    g2 = [nd.gaussian_filter(f, 10, order=o) for o in ((1, 0), (0, 1))]
    n1, n2 = np.hypot(*g1), np.hypot(*g2)
    edge = road & ~nd.binary_erosion(road, np.ones((3, 3), bool), border_value=1) & (n1 > 0.03)
    edge[:MARGIN], edge[-MARGIN:], edge[:, :MARGIN], edge[:, -MARGIN:] = False, False, False, False
    ys, xs = np.nonzero(edge)
    ny, nx = g1[0][ys, xs] / n1[ys, xs], g1[1][ys, xs] / n1[ys, xs]          # unit normal into the road
    my, mx = g2[0][ys, xs] / np.maximum(n2[ys, xs], 1e-9), g2[1][ys, xs] / np.maximum(n2[ys, xs], 1e-9)
    straight = (ny * my + nx * mx) > np.cos(np.radians(8))
    ys, xs, ny, nx = ys[straight], xs[straight], ny[straight], nx[straight]
    # the edge pixel's centre is 0.5 px inside the edge line, so t = s + 0.5
    yy = ys[:, None] + ny[:, None] * S[None, :]
    xx = xs[:, None] + nx[:, None] * S[None, :]
    prof = nd.map_coordinates(ink, [yy.ravel(), xx.ravel()], order=1, mode="nearest").reshape(yy.shape)
    return prof, S + 0.5, nx, ny


def stroke(prof, t):
    """Per profile: the ink run just outside the edge. Returns (centre, fwhm, face, peak, ok) arrays."""
    zone = (t >= -8) & (t <= 1)
    k = np.argmax(np.where(zone, prof, -1), 1)
    peak = prof[np.arange(len(prof)), k]
    out = np.full((len(prof), 3), np.nan)
    for i in np.nonzero(peak >= 0.12)[0]:
        a, h = prof[i], peak[i] / 2
        lo = hi = k[i]
        while lo > 0 and a[lo - 1] > h:
            lo -= 1
        while hi < len(a) - 1 and a[hi + 1] > h:
            hi += 1
        w = a[lo:hi + 1]
        out[i] = ((w * t[lo:hi + 1]).sum() / w.sum(), t[hi] - t[lo] + 0.5, t[hi] + 0.25)   # centre, width, road-side face
    return out, peak


def main(sheet, mask_path, only=None, every=False):
    spec = json.loads((HERE / "windows.json").read_text())
    pin = json.loads((HERE / "native.json").read_text())[sheet]
    Image.MAX_IMAGE_PIXELS = None
    rgb = np.asarray(Image.open(ROOT / pin["path"]).convert("RGB"))
    mask = np.asarray(Image.open(mask_path)) == 255
    paper = np.load(ROOT / "work" / "image-processing" / "results" / spec["sheets"][sheet]["map_id"] / "features" / "paper.npy")
    rows = {"lower-right (thick)": [], "upper-left (thin)": [], "other": []}
    per = []
    for w in spec["windows"]:
        if w["sheet"] != sheet or (w.get("layer") != "road" and not every) or (only and w["id"] not in only):
            continue
        if not (w["split"] == "calibrate" or w["seen"]):
            continue
        x, y, bw, bh = w["box"]
        if touches([x - MARGIN, y - MARGIN, bw + 2 * MARGIN, bh + 2 * MARGIN], sheet):
            print("skip (margin touches an unseen box):", w["id"])
            continue
        sl = (slice(y - MARGIN, y + bh + MARGIN), slice(x - MARGIN, x + bw + MARGIN))
        prof, t, nx, ny = profiles(rgb[sl], paper, mask[sl], y - MARGIN, x - MARGIN)
        st, peak = stroke(prof, t)
        d = (nx + ny) / np.sqrt(2)                       # > 0: the road lies lower-right of its wall
        side = np.where(d > 0.5, 0, np.where(d < -0.5, 1, 2))
        ok = ~np.isnan(st[:, 0])
        per.append((w["id"], len(prof), int(ok.sum())))
        for j, name in enumerate(rows):
            rows[name].append(st[ok & (side == j)])
    print("window, straight edge px, with a stroke:", per)
    for name, v in rows.items():
        v = np.concatenate(v)
        if not len(v):
            continue
        q = lambda c, p: np.percentile(v[:, c], p)
        print(f"{name:20s} n={len(v):6d}  width {q(1, 50):.1f} [{q(1, 25):.1f}-{q(1, 75):.1f}]  centre {q(0, 50):+.2f} [{q(0, 25):+.2f} to {q(0, 75):+.2f}]  road-side face {q(2, 50):+.2f} [{q(2, 25):+.2f} to {q(2, 75):+.2f}]")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[a.index("--windows") + 1].split(",") if "--windows" in a else None, "--all" in a)
