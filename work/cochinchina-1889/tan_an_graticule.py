#!/usr/bin/env python3
"""Tan An (1887) plate: read the printed graticule and build the georeference.

Reads only. Writes local files: the fit-point CSV and the Allmaps annotation JSON.
Nothing here touches the database, R2 or Allmaps.

    python3 work/cochinchina-1889/tan_an_graticule.py --jpeg <p-013.jpg> --out work/cochinchina-1889

What the plate prints: a full lat/long grid, every 10 minutes, ruled across the whole sheet.
Latitude labels (11°00' ... 10°30') run north-up and are true latitude. Longitude labels
(1°10' ... 0°10') FALL from left to right: they count WEST of a meridian that lies just east
of the sheet. That is neither Paris nor Greenwich; solved against rivers it is ~106.693 E
Greenwich (Saigon meridian). See README.md.

Method (graticule only; no landmark enters this script):
  1. vertical lines: trace each in 120-row windows, robust line fit.
  2. horizontal lines: per half (the sheet is a two-page spread; the gutter is ~x 8200),
     Hough over (slope, intercept) of candidate peaks.
  3. each intersection is then re-measured locally (+-150 px window), because the paper
     is not flat and the lines are not straight to better than ~10 px over a half.
  4. 24 intersections (6 meridians x 4 parallels; the 0 deg 40' line sits in the gutter
     and is dropped) become thin-plate-spline GCPs.

The reference-meridian shift (L0_SHIFT_M, LAT_SHIFT_M) is NOT measured here. It comes from
river_check.py's calibration window and is applied below as a constant.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks

Image.MAX_IMAGE_PIXELS = None
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from lib import georef_annotation as G  # noqa: E402

UUID = "bfc043c5-9023-4182-aa4e-807f4bffe762"
IIIF = f"https://iiif.maparchive.vn/iiif/{UUID}"
W, H = 16692, 10052  # info.json width/height, identical to the JPEG

# Labels as printed. Longitude: degrees WEST of the reference meridian. Latitude: degrees N.
V_LINES = {"1d10": 1 + 10 / 60, "1d00": 1.0, "0d50": 50 / 60, "0d30": 30 / 60, "0d20": 20 / 60, "0d10": 10 / 60}
H_LINES = {"11d00": 11.0, "10d50": 10 + 50 / 60, "10d40": 10 + 40 / 60, "10d30": 10.5}
LEFT = {"1d10", "1d00", "0d50"}
# rough (top x, bottom x) of each meridian and rough y of each parallel, read once off the sheet
V_INIT = {"1d10": (1805, 1758), "1d00": (3944, 3892), "0d50": (6082, 6033),
          "0d30": (10263, 10314), "0d20": (12400, 12453), "0d10": (14540, 14584)}
H_NOM = {"11d00": 952, "10d50": 3160, "10d40": 5385, "10d30": 7612}
SLOPE = {"L": (0.0045, 0.0080), "R": (-0.0085, -0.0050)}  # the spread's two pages tilt opposite ways
HALF_X = {"L": (1100, 7900), "R": (8500, 15800)}

# From river_check.py (calibration window A only): printed coordinates minus true.
L0_SHIFT_M = 800.0   # east: printed longitude = true + this, so the reference meridian is 106.6927 E
LAT_SHIFT_M = 100.0  # north
KX = 111320 * np.cos(np.radians(10.7))
KY = 110574.0
L0_NOMINAL = 106.70  # arbitrary anchor; the shift below moves it
L0 = L0_NOMINAL - L0_SHIFT_M / KX


def centroid(prof, i):
    j0, j1 = max(i - 2, 0), min(i + 3, len(prof))
    w = np.clip(prof[j0:j1], 0, None)
    return (np.arange(j0, j1) * w).sum() / w.sum()


def robust_line(t, v, k=2.5):
    t, v = np.asarray(t, float), np.asarray(v, float)
    m = np.ones(len(t), bool)
    for _ in range(6):
        c = np.polyfit(t[m], v[m], 1)
        r = v - np.polyval(c, t)
        m2 = np.abs(r) < k * max(np.std(r[m]), 0.6)
        if m2.sum() < 5 or (m2 == m).all():
            break
        m = m2
    return c, m


def trace_vertical(a, xt, xb, win=120, half=30):
    ts, vs = [], []
    for y in range(1000, 9100 - win, win):
        xe = xt + (xb - xt) * (y + win / 2 - 1000) / 8100
        lo = int(xe - half)
        hp = a[y:y + win, lo:int(xe + half)].mean(0)
        hp = hp - np.median(hp)
        i = int(np.argmax(hp))
        if hp[i] >= 12:
            ts.append(y + win / 2)
            vs.append(lo + centroid(hp, i))
    return robust_line(ts, vs)[0]  # x = c0*y + c1


def candidates_h(a, yn, x0, x1, win=100, band=90):
    pts = []
    for x in range(x0, x1 - win, win // 2):
        lo = int(yn - band)
        hp = a[lo:int(yn + band), x:x + win].mean(1)
        hp = hp - np.median(hp)
        p, _ = find_peaks(hp, height=14, distance=4)
        pts += [(x + win / 2, lo + centroid(hp, i)) for i in p]
    return np.array(pts)


def hough_h(pts, x0, x1, srange):
    xm = (x0 + x1) / 2
    best = (-1, 0, 0)
    for s in np.arange(srange[0], srange[1], 0.0001):
        b = pts[:, 1] - s * (pts[:, 0] - xm)
        h, e = np.histogram(b, bins=np.arange(b.min(), b.max() + 1, 1.0))
        hh = np.convolve(h, np.ones(3), "same")
        i = int(np.argmax(hh))
        if hh[i] > best[0]:
            best = (hh[i], s, e[i] + 0.5)
    _, s, b0 = best
    m = np.abs(pts[:, 1] - (b0 + s * (pts[:, 0] - xm))) < 2
    c = np.polyfit(pts[m, 0] - xm, pts[m, 1], 1)
    return c[0], c[1], xm  # slope, y at xm, xm


def refine(a, x, y, kind, band, w=300):
    """Re-measure one line near (x, y); `kind` 'y' returns y of a horizontal, 'x' of a vertical."""
    if kind == "y":
        lo = int(y - band)
        hp = a[lo:int(y + band), int(x - w / 2):int(x + w / 2)].mean(1)
    else:
        lo = int(x - band)
        hp = a[int(y - w / 2):int(y + w / 2), lo:int(x + band)].mean(0)
    hp = hp - np.median(hp)
    p, _ = find_peaks(hp, height=10, distance=4)
    if len(p) == 0:
        return None
    j = p[np.argmax(hp[p] - 0.15 * np.abs(p - band))]
    return lo + centroid(hp, j)


def intersections(a):
    vlines = {k: trace_vertical(a, *V_INIT[k]) for k in V_LINES}
    out = []
    for hk, lat in H_LINES.items():
        for half in "LR":
            x0, x1 = HALF_X[half]
            pts = candidates_h(a, H_NOM[hk], x0, x1)
            s, b, xm = hough_h(pts, x0, x1, SLOPE[half])
            for vk, west in V_LINES.items():
                if (vk in LEFT) != (half == "L"):
                    continue
                vs, vc = vlines[vk]
                x = vc + vs * b  # first guess: the vertical at the parallel's height
                y = b + s * (x - xm)
                for _ in range(3):
                    ny = refine(a, x, y, "y", 45)
                    nx = refine(a, x, y, "x", 25)
                    y = ny if ny is not None else y
                    x = nx if nx is not None else x
                out.append(dict(v=vk, h=hk, half=half, px=x, py=y, west_deg=west, lat_deg=lat))
    return out


def true_lonlat(west_deg, lat_deg):
    """Printed (west of the reference meridian, latitude) -> WGS84-ish lon/lat after the shift."""
    return L0 - west_deg, lat_deg - LAT_SHIFT_M / KY


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jpeg", required=True)
    ap.add_argument("--out", default="work/cochinchina-1889")
    args = ap.parse_args()
    im = Image.open(args.jpeg).convert("L")
    assert im.size == (W, H), im.size
    a = 255 - np.asarray(im).astype(np.float32)
    pts = intersections(a)
    out = Path(args.out)
    (out / "annotations").mkdir(parents=True, exist_ok=True)
    (out / "points").mkdir(parents=True, exist_ok=True)
    gcps = []
    with open(out / "points" / "p-013-tan-an-fit.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["role", "id", "px", "py", "lon", "lat", "printed_west_deg", "printed_lat_deg", "note"])
        for p in pts:
            lon, lat = true_lonlat(p["west_deg"], p["lat_deg"])
            gcps.append(((p["px"], p["py"]), (lon, lat)))
            w.writerow(["fit", f"{p['v']}x{p['h']}", f"{p['px']:.1f}", f"{p['py']:.1f}", f"{lon:.6f}", f"{lat:.6f}",
                        f"{p['west_deg']:.5f}", f"{p['lat_deg']:.5f}", f"graticule intersection, {p['half']} page"])
    # neatline: the inner frame, a little inside it
    mask = [(960, 750), (15700, 750), (15700, 9260), (960, 9260)]
    ann = G.annotation(IIIF, W, H, gcps, mask, transformation={"type": "thinPlateSpline"}, ndigits=1)
    (out / "annotations" / f"{UUID}.json").write_text(json.dumps(ann, indent=1))
    print(f"{len(gcps)} GCPs; reference meridian {L0:.4f} E; wrote annotation for {UUID}")


if __name__ == "__main__":
    main()
