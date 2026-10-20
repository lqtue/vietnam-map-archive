#!/usr/bin/env python3
"""Check the Tan An graticule georeference against rivers that are NOT in the fit.

Reads only (one Overpass query to OpenStreetMap, cached). Writes local files.

    python3 work/cochinchina-1889/river_check.py --jpeg <p-013.jpg> --cache <dir> --out work/cochinchina-1889

Why rivers and not points: the sheet has no towns or junctions that survive a century of
canals in a way I could match to OpenStreetMap without eyeballing. A river's bank line is
matched automatically instead:

  * the plate's rivers are dark blue lines (mask of blue, darkish pixels at 1/4 scale);
  * OpenStreetMap riverbank polygons are projected through the graticule model;
  * for each 1500 x 1500 px window, slide the OSM lines over the plate mask and keep the
    shift that puts the most OSM points on mask pixels (mean distance of the best 40 %).

The shift at a window is that window's error. A river only fixes the shift ACROSS itself,
so each shift is split into a cross-river and an along-river part (PCA of the matched OSM
points) and the cross-river part is the number that means something.

Honest limits, printed in the CSV and the README: a modern river has moved since 1887; the
along-river part is unconstrained; windows beyond the last parallel (y > 7600) or on the
left page (swamp, channels re-cut) are not used.
"""
import argparse
import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.interpolate import RBFInterpolator
from scipy.ndimage import distance_transform_edt

Image.MAX_IMAGE_PIXELS = None
KX = 111320 * np.cos(np.radians(10.7))
KY = 110574.0
LON0 = 106.70
S = 4            # mask downscale
CAL = (12600, 6400, 14400, 7800)   # the one calibration window; it set the meridian shift
CELL = 1500
BBOX = (10.35, 106.00, 11.05, 106.80)  # S, W, N, E


def fetch_osm(cache: Path):
    f = cache / "osm_water.json"
    if f.exists():
        return json.load(open(f))["elements"]
    q = ('[out:json][timeout:90];(way["waterway"~"^(river|canal)$"]({b});'
         'way["natural"="water"]["water"="river"]({b}););out geom;').format(b=",".join(map(str, BBOX)))
    req = urllib.request.Request("https://overpass-api.de/api/interpreter",
                                 data=urllib.parse.urlencode({"data": q}).encode(),
                                 headers={"User-Agent": "VMA-georef-research/1.0"})
    data = urllib.request.urlopen(req, timeout=120).read()
    f.write_bytes(data)
    return json.loads(data)["elements"]


def bank_points(osm, step=12.0):
    out = []
    for w in osm:
        if w.get("tags", {}).get("natural") != "water":
            continue
        ll = np.array([[g["lon"], g["lat"]] for g in w["geometry"]])
        m = np.c_[(ll[:, 0] - LON0) * KX, ll[:, 1] * KY]
        cum = np.r_[0, np.cumsum(np.hypot(*np.diff(m, axis=0).T))]
        if cum[-1] < step:
            continue
        t = np.arange(0, cum[-1], step)
        out.append(np.c_[np.interp(t, cum, m[:, 0]), np.interp(t, cum, m[:, 1])])
    return np.vstack(out)


def window_search(g2px, dt, bp, win, rng=500, step=20, cap=100, frac=0.4):
    x0, y0, x1, y1 = win
    pix = g2px(bp)
    sel = (pix[:, 0] > x0) & (pix[:, 0] < x1) & (pix[:, 1] > y0) & (pix[:, 1] < y1)
    n = int(sel.sum())
    if n < 150:
        return None
    gm, pix = bp[sel], pix[sel]
    c, e = gm.mean(0), 50.0
    J = np.c_[(g2px(c[None] + [e, 0]) - g2px(c[None] - [e, 0]))[0] / (2 * e),
              (g2px(c[None] + [0, e]) - g2px(c[None] - [0, e]))[0] / (2 * e)]
    out = {}
    for dx in range(-rng, rng + 1, step):
        for dy in range(-rng, rng + 1, step):
            q = pix + J @ np.array([dx, dy])
            ii = np.clip((q[:, 1] / S).astype(int), 0, dt.shape[0] - 1)
            jj = np.clip((q[:, 0] / S).astype(int), 0, dt.shape[1] - 1)
            d = np.sort(np.minimum(dt[ii, jj] * S, cap))
            out[(dx, dy)] = float(d[:max(10, int(frac * len(d)))].mean())
    arr = np.array([(k[0], k[1], v) for k, v in out.items()])
    i = int(np.argmin(arr[:, 2]))
    return dict(n=n, dx=float(arr[i, 0]), dy=float(arr[i, 1]), best=float(arr[i, 2]),
                median=float(np.median(arr[:, 2])), gm=gm, pix=pix, J=J)


def cross_along(r, dt):
    q = r["pix"] + r["J"] @ np.array([r["dx"], r["dy"]])
    ii = np.clip((q[:, 1] / S).astype(int), 0, dt.shape[0] - 1)
    jj = np.clip((q[:, 0] / S).astype(int), 0, dt.shape[1] - 1)
    m = dt[ii, jj] * S < 40
    pts = r["gm"][m] - r["gm"][m].mean(0)
    _, sv, vt = np.linalg.svd(pts, full_matrices=False)
    sh = np.array([r["dx"], r["dy"]])
    return abs(sh @ vt[1]), abs(sh @ vt[0]), float(sv[1] / sv[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jpeg", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", default="work/cochinchina-1889")
    args = ap.parse_args()
    out = Path(args.out)
    fit = [r for r in csv.DictReader(open(out / "points" / "p-013-tan-an-fit.csv"))]
    PX = np.array([[float(r["px"]), float(r["py"])] for r in fit])
    G = np.array([[(float(r["lon"]) - LON0) * KX, float(r["lat"]) * KY] for r in fit])
    g2px = RBFInterpolator(G, PX, kernel="thin_plate_spline")
    px2g = RBFInterpolator(PX, G, kernel="thin_plate_spline")
    im = Image.open(args.jpeg).convert("RGB")
    W_, H_ = im.size
    sm = np.asarray(im.resize((W_ // S, H_ // S), Image.BOX)).astype(np.int16)
    r_, g_, b_ = sm[..., 0], sm[..., 1], sm[..., 2]
    mask = ((b_ - r_) > 5) & ((r_ + g_ + b_) / 3 < 200)
    dt = distance_transform_edt(~mask).astype(np.float32)
    bp = bank_points(fetch_osm(Path(args.cache)))

    cal = window_search(g2px, dt, bp, CAL, rng=300, step=10)
    print(f"calibration window {CAL}: residual shift ({cal['dx']:.0f}, {cal['dy']:.0f}) m east/north  [circular]")

    rows = []
    for x0 in range(900, 15900, CELL):
        for y0 in range(900, 9000, CELL):
            win = (x0, y0, x0 + CELL, y0 + CELL)
            cx, cy = x0 + CELL / 2, y0 + CELL / 2
            if CAL[0] - CELL / 2 < cx < CAL[2] + CELL / 2 and CAL[1] - CELL / 2 < cy < CAL[3] + CELL / 2:
                continue                    # overlaps the calibration window
            if cy > 7600 or cx > 14600:
                continue                    # beyond the last parallel / past the 0d10 meridian
            r = window_search(g2px, dt, bp, win)
            if r is None or r["n"] < 300:
                continue
            ratio = r["best"] / max(r["median"], 1e-6)
            if ratio >= 0.5 or r["best"] < 0.5 or abs(r["dx"]) >= 500 or abs(r["dy"]) >= 500:
                continue                    # no sharp optimum, a degenerate one (score ~0), or pinned at the edge
            xt, al, aniso = cross_along(r, dt)
            lon, lat = px2g(np.array([[cx, cy]]))[0]
            rows.append(dict(win=win, cx=cx, cy=cy, lon=LON0 + lon / KX, lat=lat / KY, n=r["n"],
                             dx=r["dx"], dy=r["dy"], total=float(np.hypot(r["dx"], r["dy"])),
                             cross=float(xt), along=float(al), aniso=aniso, ratio=ratio))
            print(win, f"cross {xt:.0f} m  along {al:.0f} m  total {rows[-1]['total']:.0f} m  ratio {ratio:.2f}", flush=True)
    xt = np.array([r["cross"] for r in rows])
    tot = np.array([r["total"] for r in rows])
    summary = dict(n_windows=len(rows), cross_median_m=float(np.median(xt)), cross_max_m=float(xt.max()),
                   total_median_m=float(np.median(tot)), total_max_m=float(tot.max()),
                   calibration_window=CAL, calibration_residual_m=[cal["dx"], cal["dy"]])
    print(json.dumps(summary, indent=1))
    with open(out / "points" / "p-013-tan-an-check.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["role", "id", "px", "py", "lon", "lat", "residual_total_m", "residual_cross_river_m",
                    "residual_along_river_m", "n_osm_points", "note"])
        for r in rows:
            w.writerow(["check", "win_%d_%d" % (r["win"][0], r["win"][1]), f"{r['cx']:.0f}", f"{r['cy']:.0f}",
                        f"{r['lon']:.6f}", f"{r['lat']:.6f}", f"{r['total']:.0f}", f"{r['cross']:.0f}",
                        f"{r['along']:.0f}", r["n"],
                        f"river-registration window {r['win']}; river anisotropy {r['aniso']:.2f}"])
    (out / "points" / "p-013-tan-an-check-summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
