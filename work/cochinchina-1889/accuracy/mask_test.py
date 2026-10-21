"""Test B: mask along the printed line, half resolution. Rule: README.md (fixed before any run).

    python mask_test.py --half mytho=half_mytho.jpg vl=half_vl.jpg gc=half_gc.jpg bt=half_bt.jpg
Writes plates/masks/<plate>.json (new outline, full-res px), overlay JPEGs, summary.json.
"""
import argparse
import csv
import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
CC = HERE.parent
PLATES = {"mytho": ("ff6489cd-b5fe-4dea-9513-5468f5972eb3", CC / "river-match/points/fit.csv"),
          "vl": ("8653da35-0366-49d3-b8e5-3f2512dcc84b", CC / "river-match/plates/vinh-long/points/fit.csv"),
          "bt": ("e9fc1c66-a004-414e-8e17-4599445662fd", CC / "river-match/plates/bentre/points/fit.csv"),
          "gc": ("62a29997-a0d3-433d-aeab-a40552d3f2b3", CC / "river-match/plates/gocong/points/fit.csv")}
LAT0 = 10.4
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110574


def pink(a):                                    # as cc_mask.py
    r, g, b = [a[..., i].astype(int) for i in range(3)]
    return (r > 190) & (r - g > 40) & (r - b > 30) & (g < 200) & (abs(g - b) < 45)


def old_poly(mid):
    svg = json.load(open(CC / "allmaps-drafts" / f"{mid}.json"))["items"][0]["target"]["selector"]["value"]
    return [tuple(map(float, p.split(","))) for p in re.search(r'points="([^"]+)"', svg).group(1).split()]


def new_mask(a, old_full, step=2):
    """Half-res RGB array and the pushed outline (full-res px) -> new outline (full-res px)."""
    H, W = a.shape[:2]
    im = Image.new("L", (W, H), 0)
    ImageDraw.Draw(im).polygon([(x / 2, y / 2) for x, y in old_full], fill=1)
    old = np.asarray(im, bool)
    ring = old & ~ndi.binary_erosion(old, iterations=4)
    thick = ndi.binary_opening(pink(a), np.ones((3, 3)), iterations=4)      # the wash, not the red village lines
    lab, n = ndi.label(thick)
    touch = np.unique(lab[ring & thick]); touch = touch[touch > 0]
    wash = np.isin(lab, touch)
    q = old & ~ndi.binary_dilation(wash, iterations=2)
    q = ndi.binary_opening(q, np.ones((3, 3)), iterations=2)
    lab, n = ndi.label(q)
    m = ndi.binary_fill_holes(lab == (1 + int(np.argmax(ndi.sum(q, lab, range(1, n + 1))))))
    sm = m[::step, ::step]
    boxes = []
    for y, row in enumerate(sm):
        xs = np.flatnonzero(np.diff(np.r_[0, row.astype(int), 0]))
        for x0, x1 in zip(xs[::2], xs[1::2]):
            boxes.append(box(x0 * step, y * step, x1 * step, (y + 1) * step))
    poly = unary_union(boxes)
    if poly.geom_type != "Polygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    poly = poly.simplify(2).exterior
    return [(2 * x, 2 * y) for x, y in poly.coords[:-1]], float(old.sum()), float(m.sum()), float(wash.sum())


def line_support(a, pts_full):
    """Share of points with ink darker than the paper median by 60 grey levels within 3 half-res px."""
    g = a.astype(float).mean(-1)
    ink = g < np.median(g) - 60
    near = ndi.binary_dilation(ink, iterations=3)
    h, w = near.shape
    ok = [near[min(h - 1, max(0, int(round(y / 2)))), min(w - 1, max(0, int(round(x / 2))))] for x, y in pts_full]
    return float(np.mean(ok))


def resample(poly, every=100):
    p = Polygon(poly).exterior
    n = max(8, int(p.length // every))
    return [p.interpolate(i / n, normalized=True).coords[0] for i in range(n)]


def ground(plate, pts):
    mid, fit = PLATES[plate]
    rows = [r for r in csv.DictReader(open(fit)) if r["role"] == "fit"]
    P = np.array([[float(r["px"]), float(r["py"])] for r in rows])
    G = np.array([((float(r["lon"]) - 106) * KX, (float(r["lat"]) - LAT0) * KY) for r in rows])
    M = np.linalg.lstsq(np.c_[P, np.ones(len(P))], G, rcond=None)[0]
    pp = np.array(pts)
    return Polygon(np.c_[pp, np.ones(len(pp))] @ M).buffer(0)


def overlap_sum(polys):
    names = list(polys)
    tot, per = 0.0, {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            o = polys[names[i]].intersection(polys[names[j]]).area / 1e6
            per[f"{names[i]}/{names[j]}"] = round(o, 1)
            tot += o
    return tot, per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--half", nargs="+", required=True, help="plate=path")
    ap.add_argument("--out", default=str(HERE / "plates" / "masks"))
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    old_g, new_g, res = {}, {}, {}
    for spec in args.half:
        plate, path = spec.split("=")
        mid = PLATES[plate][0]
        a = np.asarray(Image.open(path).convert("RGB"))
        old = old_poly(mid)
        new, a_old, a_new, a_wash = new_mask(a, old)
        json.dump(new, open(out / f"{plate}.json", "w"))
        old_g[plate], new_g[plate] = ground(plate, old), ground(plate, new)
        res[plate] = dict(vertices=dict(old=len(old), new=len(new)), area_ratio=round(a_new / a_old, 3), wash_px_removed=int(a_wash),
                          support_vertices=dict(old=round(line_support(a, old), 3), new=round(line_support(a, new), 3)),
                          support_every_100px=dict(old=round(line_support(a, resample(old)), 3), new=round(line_support(a, resample(new)), 3)))
        im = Image.fromarray(a); d = ImageDraw.Draw(im)
        d.line([(x / 2, y / 2) for x, y in old + [old[0]]], fill=(255, 0, 0), width=5)
        d.line([(x / 2, y / 2) for x, y in new + [new[0]]], fill=(0, 90, 255), width=5)
        im.thumbnail((1800, 1800)); im.save(out / f"{plate}-overlay.jpg", quality=85)
        print(plate, res[plate])
    o_old, p_old = overlap_sum(old_g)
    o_new, p_new = overlap_sum(new_g)
    drop = 1 - o_new / o_old
    sup_ok = all(r["support_vertices"]["new"] >= r["support_vertices"]["old"] for r in res.values())
    ok = drop >= 1 / 3 and sup_ok
    print(f"overlap km2 old {o_old:.1f} {p_old}\n            new {o_new:.1f} {p_new}\n drop {drop:.0%}; line support not lower on any plate: {sup_ok} -> {'PASS' if ok else 'FAIL'}")
    json.dump(dict(plates=res, overlap_km2=dict(old=round(o_old, 1), new=round(o_new, 1), old_pairs=p_old, new_pairs=p_new, drop=round(drop, 3)),
                   line_support_not_lower_anywhere=sup_ok, verdict="pass" if ok else "fail"), open(out / "summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
