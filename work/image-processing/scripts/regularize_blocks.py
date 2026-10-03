#!/usr/bin/env python3
"""regularize_blocks.py — straighten the outlines on a sheet's cleaned colour-block layer.

`clean_blocks.py` decides which features exist; this decides what shape they have. A concave
hull over pixels leaves bumps along an edge and a small chamfer where two edges should meet.
For each feature, in source pixels:

  1. simplify  — Douglas-Peucker at 5% of sqrt(area): absorbs bumps; a real L-notch is far bigger
  2. cut       — a short edge between two long ones is a chamfer: drop it and meet the neighbours
                 at a sharp corner, if that costs under 3% of sqrt(area)^2. A notch costs more.
  3. snap      — slide each edge up to 10% of sqrt(area) (max 14 px) onto the strongest ink line
                 beside it, then re-cut the corners where the moved edges meet
  4. guard     — a snap that changes the plot by more than 15% IoU falls back to step 2's outline

Nothing is squared: a plot with an irregular boundary stays irregular. The input file is never
edited; the output sits beside it as `blocks.regularized.geojson`, same features, same order, same
`source_index`, plus `reg` (kept | cut | snap) and `iou_orig`. Holes are dropped (ten polygons
carry one; the queue stores none) and the audit counts them.

  python3 work/image-processing/scripts/regularize_blocks.py --sheet 1882
  python3 work/image-processing/scripts/regularize_blocks.py --self-check

Reviewed by eye on 17 hand-kept 1882 cream parcels only. Buildings, the other pigment classes and
the 1898 sheet are unreviewed.

ponytail: the ink map is a background-subtracted grey, so a thick stroke (a road edge, the shadow of a
printed diamond) pulls an edge as hard as a thin plot line. A stroke-width cap is the upgrade path.
"""
import argparse, json, sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy import ndimage
from shapely.geometry import Polygon, shape, mapping

from clean_blocks import ROOT, SHEETS
sys.path.insert(0, str(ROOT / "work" / "ocr" / "scripts"))

SIMPLIFY, CUT_LEN, CUT_LOSS, SNAP_FRAC, SNAP_MAX, GUARD = .05, .3, .03, .10, 14, .85
MAP_IDS = {"1882": "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b", "1898": "20ec4f9a-16bd-4895-a593-40c6ed9c9555"}


def meet(p, d, q, e):
    """Intersection of the lines p + t*d and q + s*e, or None if they are parallel."""
    A = np.array([d, -e]).T
    if abs(np.linalg.det(A)) < 1e-6 * np.linalg.norm(d) * np.linalg.norm(e):
        return None
    return p + np.linalg.solve(A, q - p)[0] * d


def cut_corners(P, r):
    P = [np.asarray(v, float) for v in P]
    while len(P) > 3:
        n = len(P)
        L = [np.linalg.norm(P[(i + 1) % n] - P[i]) for i in range(n)]
        i = int(np.argmin(L))
        if L[i] >= CUT_LEN * r:
            break
        a, b, c, d = P[i - 1], P[i], P[(i + 1) % n], P[(i + 2) % n]
        x = meet(a, b - a, d, c - d)
        if x is None or abs(Polygon([b, c, x]).area) > CUT_LOSS * r * r:
            break
        P = [v for j, v in enumerate(P) if j not in (i, (i + 1) % n)]
        P.insert(i if i < len(P) else 0, x)
    return np.array(P)


def ink(rgb):
    g = np.asarray(rgb.convert("L"), float)
    return ndimage.gaussian_filter(np.clip(ndimage.median_filter(g, size=25) - g, 0, None), .8)


def snap_edges(P, I):
    """P in crop pixels, I the ink map. Returns the re-cut vertices."""
    n = len(P)
    R = min(SNAP_FRAC * Polygon(P).area ** .5, SNAP_MAX)
    ds = np.arange(-R, R + .5, .5)
    lines = []
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        v = b - a
        L = np.linalg.norm(v)
        u = v / L
        nm = np.array([-u[1], u[0]])
        pts = a[None] + np.linspace(.15, .85, max(8, int(L * .35)))[:, None] * v[None]
        sc = np.array([ndimage.map_coordinates(I, [(pts + d * nm)[:, 1], (pts + d * nm)[:, 0]],
                                               order=1, mode="nearest").mean() for d in ds])
        sc = sc - .03 * np.abs(ds) * sc.max()  # prefer to stay put
        k = int(sc.argmax())
        d = ds[k] if sc[k] > 1.5 * np.median(sc) and sc.max() > 4 else 0
        lines.append((a + d * nm, u))
    out = []
    for i in range(n):
        x = meet(*lines[i - 1], *lines[i])
        out.append(x if x is not None and np.linalg.norm(x - P[i]) < 2 * R else P[i])
    return np.array(out)


def iou(a, b):
    return a.intersection(b).area / a.union(b).area if a.union(b).area else 0.0


def regularize(geom, rgb=None, origin=(0, 0)):
    """geom: shapely polygon in source px. rgb: crop whose top-left is `origin`. -> (polygon, how)."""
    g = geom if geom.geom_type == "Polygon" else max(geom.geoms, key=lambda p: p.area)
    g = Polygon(g.exterior)
    if g.area <= 0:
        return g, "kept"
    r = g.area ** .5
    s = g.simplify(SIMPLIFY * r)
    if s.geom_type != "Polygon" or s.is_empty or len(s.exterior.coords) < 4:
        return g, "kept"
    ox, oy = origin
    P = cut_corners(np.array(s.exterior.coords)[:-1] - [ox, oy], r)
    cut = Polygon(P + [ox, oy])
    if not cut.is_valid or cut.is_empty or iou(cut, g) < GUARD:
        return g, "kept"
    if rgb is None:
        return cut, "cut"
    out = Polygon(snap_edges(P, ink(rgb)) + [ox, oy])
    if not out.is_valid or out.is_empty or iou(out, cut) < GUARD:
        return cut, "cut"
    return out, "snap"


def crop_for(base, W, H, geom, fetch_crop):
    x0, y0, x1, y1 = geom.bounds
    m = int(.3 * max(x1 - x0, y1 - y0)) + 20
    x0, y0 = max(0, int(x0) - m), max(0, int(y0) - m)
    x1, y1 = min(W, int(x1) + m), min(H, int(y1) + m)
    return fetch_crop(base, x0, y0, x1 - x0, y1 - y0, size=x1 - x0), (x0, y0)


def run(tag):
    from iiif_tiles import fetch_crop, get_image_info, get_iiif_base_from_supabase
    src = (ROOT / SHEETS[tag][0]).with_name("blocks.clean.geojson")
    feats = json.loads(src.read_text())["features"]
    base = get_iiif_base_from_supabase(MAP_IDS[tag])
    info = get_image_info(base)
    W, H = info["width"], info["height"]

    def one(f):
        g = shape(f["geometry"])
        try:
            rgb, origin = crop_for(base, W, H, g, fetch_crop)
            return regularize(g, rgb, origin)
        except Exception as e:  # a failed fetch must not silently skip the snap
            print(f"  {f['properties'].get('source_index')}: {type(e).__name__}: {e}", file=sys.stderr)
            return regularize(g)[0], "cut-nofetch"

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, feats))
    out, audit = [], {"sheet": tag, "source": str(src.relative_to(ROOT)), "n": len(feats),
                      "how": {}, "by_class": {}, "holes_dropped": 0, "min_iou": 1.0, "low_iou": []}
    for f, (q, how) in zip(feats, res):
        g = shape(f["geometry"])
        io = iou(Polygon(g.exterior if g.geom_type == "Polygon" else max(g.geoms, key=lambda p: p.area).exterior), q)
        audit["holes_dropped"] += len(g.interiors) if g.geom_type == "Polygon" else sum(len(p.interiors) for p in g.geoms)
        audit["how"][how] = audit["how"].get(how, 0) + 1
        cls = f["properties"].get("source_class", "?")
        audit["by_class"].setdefault(cls, {}).setdefault(how, 0)
        audit["by_class"][cls][how] += 1
        audit["min_iou"] = min(audit["min_iou"], round(io, 3))
        if io < .85:
            audit["low_iou"].append({"source_index": f["properties"].get("source_index"), "iou": round(io, 3), "how": how})
        out.append({"type": "Feature", "geometry": mapping(q),
                    "properties": {**f["properties"], "reg": how, "iou_orig": round(io, 3)}})
    dst = src.with_name("blocks.regularized.geojson")
    dst.write_text(json.dumps({"type": "FeatureCollection", "features": out}, separators=(",", ":")))
    dst.with_name("regularize_audit.json").write_text(json.dumps(audit, indent=2))
    print(f"{tag}: {len(feats)} features  {audit['how']}  min IoU {audit['min_iou']}  "
          f"holes dropped {audit['holes_dropped']}  -> {dst.relative_to(ROOT)}")


def self_check():
    # a 100x100 square with a bump on one edge and a chamfered corner -> a clean 4-gon
    sq = Polygon([(0, 0), (40, 0), (45, 3), (60, 0), (100, 0), (100, 90), (90, 100), (0, 100)])
    q, how = regularize(sq)
    assert how == "cut" and len(q.exterior.coords) - 1 == 4, (how, list(q.exterior.coords))
    assert iou(q, sq) > .95
    # an L is not squared: its notch is far too big to cut
    L = Polygon([(0, 0), (100, 0), (100, 40), (40, 40), (40, 100), (0, 100)])
    q, how = regularize(L)
    assert len(q.exterior.coords) - 1 == 6, list(q.exterior.coords)
    # a snap with nothing to snap to keeps the cut outline
    from PIL import Image
    q2, how2 = regularize(sq, Image.new("RGB", (160, 160), (225, 210, 180)), (-20, -20))
    assert how2 == "snap" and len(q2.exterior.coords) - 1 == 4 and iou(q2, sq) > .95, (how2, list(q2.exterior.coords))
    print("self-check ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", choices=[*SHEETS, "all"], default="all")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        self_check(); sys.exit()
    for tag in (SHEETS if a.sheet == "all" else [a.sheet]):
        run(tag)
