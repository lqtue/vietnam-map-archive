#!/usr/bin/env python3
"""Refit each side of a scanned L7014 neatline from the rules actually under it.

`l7014_neatline_profile.find` fits a line through six windows and can lock onto a grid line or the
collar on one side, which leaves four corners that are not a parallelogram (50-70 m on a bent scan,
where the GeoPDFs fit to a few metres). This takes 14 stations along each side, keeps the three
strongest rules in a band round the current line at each, and RANSACs the line that the most
stations agree on within 3 px -- a rule that runs the whole side beats a stronger one that does not.

    python3 scripts/l7014_scan_refine.py            # refine the scan sheets in hand-corners.json
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import l7014_autoplace as A  # noqa: E402
from l7014_scan_corners import JPGS, SHEETS  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
BAND = 90      # px either side of the current line
STATIONS = 14
AGREE = 3.0    # px


def stations(im, p0, p1, axis):
    """Strong rules across the band at STATIONS points along the segment p0->p1 (axis 0: a top/bottom
    side, rules are y(x); axis 1: a left/right side, rules are x(y))."""
    pts = []
    for t in np.linspace(0.08, 0.92, STATIONS):
        x, y = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
        if axis == 0:
            lo = int(max(y - BAND, 0)); seg = 255 - im[lo:int(y + BAND), int(x - 100):int(x + 100)].mean(1); along = x
        else:
            lo = int(max(x - BAND, 0)); seg = 255 - im[int(y - 100):int(y + 100), lo:int(x + BAND)].mean(0); along = y
        seg = seg - np.convolve(seg, np.ones(41) / 41, mode="same")
        for i in np.argsort(seg)[::-1][:6]:
            if seg[i] > 25 and i > 4 and i < len(seg) - 5:
                pts.append((along, lo + i, seg[i]))
    return np.array(pts)


def ransac(pts, rng=np.random.default_rng(0)):
    best, bs = None, -1
    for _ in range(1500):
        a, b = pts[rng.choice(len(pts), 2, replace=False)]
        if abs(a[0] - b[0]) < 0.3 * (pts[:, 0].max() - pts[:, 0].min()):
            continue
        m = (b[1] - a[1]) / (b[0] - a[0])
        if abs(m) > 0.02:
            continue
        c = a[1] - m * a[0]
        inl = np.abs(pts[:, 1] - (m * pts[:, 0] + c)) < AGREE
        # one inlier per station, the strongest: count distinct stations by along-coordinate
        score = sum(pts[inl & (pts[:, 0] == u)][:, 2].max() for u in np.unique(pts[inl][:, 0]))
        if score > bs:
            bs, best = score, (m, c, inl)
    m, c, inl = best
    q = pts[inl]
    m, c = np.polyfit(q[:, 0], q[:, 1], 1)
    return m, c, len(np.unique(q[:, 0]))


def cross(v, h):  # v: x = m*y + c ; h: y = m*x + c
    y = (h[0] * v[1] + h[1]) / (1 - h[0] * v[0])
    return [round(v[0] * y + v[1], 1), round(y, 1)]


def refine(s, rec):
    c = rec["corners"]
    im = np.asarray(Image.open(JPGS / f"txu-pclmaps-oclc-21713238-{s}.jpg").convert("L")).astype(float)
    top = ransac(stations(im, c["NW"], c["NE"], 0)); bot = ransac(stations(im, c["SW"], c["SE"], 0))
    left = ransac(stations(im, c["NW"], c["SW"], 1)); right = ransac(stations(im, c["NE"], c["SE"], 1))
    out = {"NW": cross(left, top), "NE": cross(right, top), "SE": cross(right, bot), "SW": cross(left, bot)}
    return out, [top[2], bot[2], left[2], right[2]]


def fit_m(c, g):
    px = np.array([c[k] for k in ("NW", "NE", "SE", "SW")]); g = np.array(g)
    A_ = np.c_[px, np.ones(4)]
    co, *_ = np.linalg.lstsq(A_, g, rcond=None)
    r = (A_ @ co - g) * [111320 * math.cos(math.radians(g[:, 1].mean())), 110540]
    return float(np.sqrt((r ** 2).sum(1).mean()))


def main():
    path = A.REGEN / "hand-corners.json"
    d = json.loads(path.read_text())
    for s in SHEETS:
        rec = d[s]
        new, votes = refine(s, rec)
        old, nw = fit_m(rec["corners"], rec["ground"]), fit_m(new, rec["ground"])
        print(f"{s} fit {old:5.1f} -> {nw:5.1f} m  stations agreeing t/b/l/r {votes}", flush=True)
        if nw < old:
            rec["corners"] = {k: [float(x) for x in v] for k, v in new.items()}
            rec["refined"] = True
    path.write_text(json.dumps(d, indent=1))


if __name__ == "__main__":
    main()
