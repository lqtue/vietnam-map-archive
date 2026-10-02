#!/usr/bin/env python3
"""Neatline corners from darkness profiles, for the sheets `l7014_neatline.py` cannot read.

That detector walks in from the paper margin and needs the margin to be blank. On the
sheets where it fails (coordinate labels or a tint right against the neatline) the line
itself is still the strongest long dark rule near each side. So: take the row/column
darkness profile, remove its slow trend, and pick the strongest spike in the band where
the side must be (top / left / right: the outer fifth or third; bottom: where the cell's
own aspect puts it). Fit each side as a line through six windows so a skewed scan is
followed, and refuse when the windows disagree.

    python3 scripts/l7014_neatline_profile.py check     # the 26 autoplace candidates, against their detected corners
    python3 scripts/l7014_neatline_profile.py find      # the other 48 -> work/l7014/regen/profile-detect.json
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from osgeo import gdal
from scipy.ndimage import median_filter

sys.path.insert(0, str(Path(__file__).parent))
import l7014_autoplace as A  # noqa: E402
from l7014_neatline import quad_ok  # noqa: E402

gdal.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")
WIDTH = 2000
OUT = A.REGEN / "profile-detect.json"


def load(pdf):
    ds = gdal.Open(str(pdf))
    W, H = ds.RasterXSize, ds.RasterYSize
    h = round(H * WIDTH / W)
    img = gdal.Translate("", ds, format="MEM", width=WIDTH, height=h, bandList=[1, 2, 3],
                         resampleAlg="average").ReadAsArray().astype(float)
    return 255 - img.mean(0), W / WIDTH


def spike(p):
    return p - median_filter(p, size=25)


def peak(s, lo, hi):
    lo, hi = max(int(lo), 0), min(int(hi), len(s))
    i = lo + int(np.argmax(s[lo:hi]))
    w = np.clip(s[max(i - 2, 0):i + 3], 0, None)  # centroid of the 5 samples around it
    return (np.arange(max(i - 2, 0), max(i - 2, 0) + len(w)) * w).sum() / w.sum() if w.sum() else float(i)


def nth_peak(s, band, n):
    """The n-th strongest rule in the band (n=1: second), at least 8 samples from the stronger ones."""
    lo, hi = max(int(band[0]), 0), min(int(band[1]), len(s))
    seg = s[lo:hi].copy()
    for _ in range(n):
        i = int(np.argmax(seg))
        seg[max(i - 8, 0):i + 9] = -1e9
    return peak(s, lo + int(np.argmax(seg)) - 1, lo + int(np.argmax(seg)) + 2)


def line(d, axis, band, along=(.12, .88), n=6, pick=0):
    """Position of one side as (m, c): across = m * along + c, in pixels. `d` is darkness;
    axis 0 = a horizontal side (rows), 1 = vertical. `band` is where the side can be."""
    L = d.shape[1 - axis]
    lo, hi = int(along[0] * L), int(along[1] * L)
    full = spike(d[:, lo:hi].mean(1) if axis == 0 else d[lo:hi].mean(0))
    first = peak(full, *band) if pick == 0 else nth_peak(full, band, pick)  # the strongest narrow rule in the band
    pts = []
    for k in range(n):
        a0, a1 = int((along[0] + (along[1] - along[0]) * k / n) * L), int((along[0] + (along[1] - along[0]) * (k + 1) / n) * L)
        s = spike(d[:, a0:a1].mean(1) if axis == 0 else d[a0:a1].mean(0))
        guess = np.polyval(np.polyfit(*zip(*pts), 1), (a0 + a1) / 2) if len(pts) > 2 else first
        pts.append(((a0 + a1) / 2, peak(s, guess - 12, guess + 12)))
    a, b = np.array(pts).T
    m, c = np.polyfit(a, b, 1)
    for _ in range(2):  # a window that locked onto a grid line is an outlier, not part of the side
        r = np.abs(b - (m * a + c))
        keep = r <= max(3.0, 2.5 * np.median(r))
        if keep.all() or keep.sum() < 4:
            break
        a, b = a[keep], b[keep]
        m, c = np.polyfit(a, b, 1)
    return m, c, float(np.abs(b - (m * a + c)).max())


def _cross(v, hz):  # v: x = m*y + c ; hz: y = m*x + c
    y = (hz[0] * v[1] + hz[1]) / (1 - hz[0] * v[0])
    return [v[0] * y + v[1], y]


def find(pdf, expect, rough=None, search=False):
    """`rough` = (left, right, top, bottom) read off a 1200-px-wide preview, +-6 px. With it the
    band for each side is +-15 px (of 2000) around that; without it, the sides' usual places."""
    d, sc = load(pdf)
    h, w = d.shape
    if rough and search:
        # Three candidate rules per side; take the combination that is most nearly a parallelogram of
        # the right shape. A wrong rule (a grid line, the collar) fails one of those two tests.
        k = WIDTH / 1200
        l_, r_, t_, b_ = (v * k for v in rough)
        sides = {"t": [line(d, 0, (t_ - 40, t_ + 40), pick=i) for i in range(4)],
                 "b": [line(d, 0, (b_ - 40, b_ + 40), pick=i) for i in range(4)],
                 "l": [line(d, 1, (l_ - 40, l_ + 40), along=(.15, .6), pick=i) for i in range(4)],
                 "r": [line(d, 1, (r_ - 40, r_ + 40), along=(.15, .6), pick=i) for i in range(4)]}
        best = None
        for t in sides["t"]:
            for b in sides["b"]:
                for l_i in sides["l"]:
                    for r in sides["r"]:
                        cs = [_cross(l_i, t), _cross(r, t), _cross(r, b), _cross(l_i, b)]
                        wd = (cs[1][0] - cs[0][0] + cs[2][0] - cs[3][0]) / 2
                        ht = (cs[3][1] - cs[0][1] + cs[2][1] - cs[1][1]) / 2
                        para = np.hypot(*(np.array(cs[0]) + cs[2] - cs[1] - cs[3])) / 2
                        score = para / wd * 100 + abs(wd / ht - expect) / expect * 100
                        if best is None or score < best[0]:
                            best = (score, t, b, l_i, r)
        _, top, bot, left, right = best
    elif rough:
        k = WIDTH / 1200
        l_, r_, t_, b_ = (v * k for v in rough)
        top = line(d, 0, (t_ - 15, t_ + 15))
        left = line(d, 1, (l_ - 15, l_ + 15), along=(.15, .6))
        right = line(d, 1, (r_ - 15, r_ + 15), along=(.15, .6))
        bot = line(d, 0, (b_ - 15, b_ + 15))
    else:
        top = line(d, 0, (0, .2 * h))
        left = line(d, 1, (0, .3 * w), along=(.15, .6))
        right = line(d, 1, (.7 * w, w), along=(.15, .6))
        pred = top[1] + (right[1] - left[1]) / expect  # where the cell's aspect puts the bottom
        bot = line(d, 0, (pred - .04 * h, pred + .04 * h))
    res = max(top[2], left[2], right[2], bot[2])

    def cross(v, hz):  # v: x = m*y + c ; hz: y = m*x + c
        y = (hz[0] * v[1] + hz[1]) / (1 - hz[0] * v[0])
        return [round((v[0] * y + v[1]) * sc, 1), round(y * sc, 1)]
    cs = {"NW": cross(left, top), "NE": cross(right, top), "SE": cross(right, bot), "SW": cross(left, bot)}
    ok, why = quad_ok({k: {"px": v} for k, v in cs.items()}, expect)
    return {"corners": cs, "quad_ok": ok, "quad_why": why, "wobble_px": round(res * sc, 1),
            "size": [round(w * sc), round(h * sc)]}


def main(mode):
    cells = A.lattice_cells()
    rows = {r["sheet"]: r for r in A.M.load_sheets() if r["kind"] == "pdf"}
    det = json.loads(A.DETECT_JSON.read_text())
    summ = json.loads(A.SUMMARY_JSON.read_text())
    sheets = sorted(summ["candidates"]) if mode == "check" else sorted(s for s in det if s not in summ["candidates"])
    out = {}
    for s in sheets:
        pdf = A.WORK / "pdfs" / (Path(rows[s]["file"]).stem.strip() + ".pdf")
        try:
            r = find(pdf, A.expect_aspect(s, cells))
        except Exception as e:  # noqa: BLE001
            r = {"error": str(e)[:100]}
        out[s] = r
        if "error" in r:
            print(s, "ERROR", r["error"]); continue
        note = ""
        if mode == "check" and det[s].get("quad_ok"):
            diff = max(math.dist(r["corners"][k], det[s]["corners"][k]) for k in r["corners"])
            note = f"  vs detector {diff:5.1f} px"
        print(f"{s} quad_ok={r['quad_ok']!s:5} wobble {r['wobble_px']:5.1f}px {r['quad_why']}{note}")
    if mode == "find":
        OUT.write_text(json.dumps(out, indent=1))
        print(sum(1 for r in out.values() if r.get("quad_ok")), "of", len(out), "quad_ok ->", OUT)


if __name__ == "__main__":
    main(sys.argv[1])
