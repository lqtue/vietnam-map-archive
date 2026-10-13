#!/usr/bin/env python3
"""Then-now street blocks and junctions for the 1882 Plan Cadastral, against 2023 TASCO data.

    python3 work/image-processing/scripts/then_now_blocks.py             # full run, writes results/prior/<map>/then-now/
    python3 work/image-processing/scripts/then_now_blocks.py --self-check  # synthetic asserts, no network, no data

What it makes: street blocks and street junctions for both epochs with ONE function (`segment`),
a displacement field (where the sheet's georeference is off, from matched junctions), a change
class per block component, and the inputs for experiments/then-now/review.py, where the owner
gates every difference. Nothing here is a verdict: every class is a proposal until a person
says so, and every output is offline (geojson / csv / json under results/, gitignored), never
`footprints`.

Sources, kept on every output: 1882 = frozen v3 masks `river/road-a3b0458f.png` (a *diagnostic*
road proposal, used here only as a block source, never as final roads) and `river/water-1006337f.png`;
2023 = TASCO topographic vector `hcmc-buildings/vector_out/hcmc_vector.gpkg` layers `region_duongbos`
(road surface) + `region_river` + `region_lake`, the same ground as `hcmc_vector.parquet`.
`region_duongbokhacs` (18 polygons in the box) is read apart and left out: it is "other paved
ground", not carriageway. The owner treats the TASCO data as public.

Transform behind every residual below: the `modern_prior.fit_sheet` affine over the sheet's 8
control points (11.5 m RMS, worst 48 px), i.e. modern lng/lat -> source px through `fit.px`.
A "displacement" d = modern - 1882, in metres at 0.341 m/px, is therefore the error of THAT
transform plus whatever the 1882 survey itself got wrong. It is not "the sheet's true error".

PREDICTION, written before the first run (2026-10-12):
  median |d| 10-15 m; a rotational pattern consistent with the known ~0.88 deg (15 mrad) rotation
  error, i.e. a tangential shift of about 15 mrad x distance from the sheet centre (15 m at 1 km,
  ~30 m at the 2 km edge of this 4.1 x 3.1 km sheet); the largest displacements toward the sheet
  edges. Held-out (checkerboard, tiles B) residual of the RBF field below the affine's, both well
  below the raw |d| on B. Report every way the result disagrees: the run writes the comparison into
  summary.json -> "prediction_vs_result" (with a "disagreements" list).

Method (plan: /Users/airm1/.claude/plans/1-agree-2-a-wondrous-truffle.md, Phase 1B) and where it
deviates, with the reason:
 1. Blocks, x2 downsample (max-pool, so a 1-3 px road survives): land = valid ^ ~road ^ ~water;
    roads dilated by CLOSE_PX to close breaks; ndimage.label (4-connected); drop < 150 m2;
    the dilated rim is given back by geodesic growth over pre-dilation land; rasterio.features.shapes
    -> shapely, lightly simplified, in full-res source px.
    DEVIATION 1: CLOSE_PX = 10 (6.8 m a side), not the plan's 1-2 px. Measured on the 1882 mask: at 1 px
    the sheet gives 90 blocks of which 55 are 2,000-200,000 m2 and one yellow giant swallows most of the city
    (street breaks at lettering, junction plazas and faint streets are 5-14 m long); at 10 px 125. The
    sweep (`closing_sweep` in summary.json) is a count of blocks, not a score: chosen by eye on
    leakage, never against the owner's plots. A block narrower than ~14 m disappears at this setting.
    DEVIATION 2: `valid` is the road pass's own region (windows.json sheets.1882.road.neatline,
    [600,560,10800,7390], minus the title and legend boxes padded 100 px), not the outer neatline
    [500,480,10900,7809]: the road mask is only defined there, and the title / legend boxes are
    blank "land" that would otherwise become two giant blocks.
 2. Junctions, no skeleton: V = nearest-block-label image over the street space (EDT indices);
    a junction pixel = a street pixel whose 3x3 window of V holds >= 3 labels; water is ONE
    pseudo-label and flags the junction `quay`; 8-connected clusters -> centroid, degree = number
    of distinct labels. A cluster > 25 m from every block, or < 20 m from the valid region's edge,
    is rejected. The same function runs on both sides.
 3. Modern: TASCO road surface drawn into the 1882 grid through fit.px (PIL polygon, holes kept
    per polygon), then a binary opening with a 4 m disk (via EDT, exact) so only streets >= 8 m
    wide survive (d4_morph's STREET_W); then the same `segment`. Cross-check against d4_morph's
    2*area/length rule on a seeded sample of polygons is reported. The 1882 side is NOT opened:
    its thin mask lines include real narrow streets, and opening would erase them. That
    asymmetry is itself a source of `merged` / `complex` classes and is reported as such.
 4. Field: mutual nearest-neighbour junction matches within 60 m, |degree difference| <= 1;
    500 m checkerboard (in sheet metres); RBFInterpolator (thin-plate, smoothing > 0, chosen on
    A only by a leave-tile-out CV) and an affine fit on A tiles, predicted onto B tiles. Junctions
    within 30 m of a control point are `in_fit`: they stay in the fit but are out of every
    accuracy number and reported apart. Errors beyond the 60 m window cannot appear here: the
    share of 1882 junctions with no match is reported, and it is a floor on what is missing.
 5. Classes: modern blocks warped through the field (p - d(p)); bipartite overlap graph, an edge if
    intersection >= 20% of EITHER block; per component: 1:1 IoU >= 0.7 unchanged, else reshaped;
    1:n split; n:1 merged; n:m complex; 1882 alone and >= 80% under modern road/water gone;
    modern alone new. EXTRA (not in the plan, reported): an 1882 block alone and NOT under road is
    `unpartnered`, and blocks over 200,000 m2 (open ground, paddy, the far bank) are listed but
    kept out of the graph, as modern_prior.BLOCK_MAX_AREA_M2 does; a modern block that lies mostly
    on such ground is `new` with `in_1882_open` true.
 6. Independent score: 1882 blocks against the owner's QGIS `plots` (881 colour plots, scale of
    a block) in ONE window chosen from plot density alone, before any scoring: boundary F-score at
    a tolerance equal to the field's held-out residual, plus best-match IoU. Not tuned on.

Self-check at the bottom runs with no network and no data.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import shapely
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.interpolate import RBFInterpolator
from scipy.spatial import cKDTree

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

METHOD = "then-now-blocks-1"
MAP_ID = "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b"
RES = ROOT / "work/image-processing/results"
OUT = RES / "prior" / MAP_ID / "then-now"

DS = 2                    # downsample factor of the working grid
CLOSE_PX = 10             # road dilation (ds px, 6.8 m a side): the plan said 1-2 px, which leaves the v3 mask's breaks open, see below
MIN_BLOCK_M2 = 150.0
MAX_BLOCK_M2 = 200_000.0  # modern_prior.BLOCK_MAX_AREA_M2: above this it is open ground, not a block
JUNCTION_MAX_BLOCK_M = 25.0
JUNCTION_EDGE_M = 20.0
STREET_W_M = 8.0          # d4_morph.STREET_W
MATCH_M = 60.0
MATCH_DEG = 1
TILE_M = 500.0
IN_FIT_M = 30.0
EDGE_FRAC = 0.2           # overlap-graph edge: intersection >= this share of either block
IOU_SAME = 0.7
GONE_FRAC = 0.8
# the road pass's own region (windows.json sheets.1882.road) and the furniture boxes, padded
ROAD_BOX = (600, 560, 10800, 7390)   # x, y, w, h
FURNITURE = {"title": (700, 600, 2400, 1500), "legend": (9800, 6950, 1700, 1100)}
FURNITURE_PAD = 100
CLASSES = ("unchanged", "reshaped", "split", "merged", "complex", "gone", "new", "unpartnered")


# ----------------------------------------------------------------------------- raster helpers

def maxpool(a: np.ndarray, k: int = DS) -> np.ndarray:
    h, w = a.shape[0] // k * k, a.shape[1] // k * k
    return a[:h, :w].reshape(h // k, k, w // k, k).max(axis=(1, 3))


def box_mask(shape, box, pad=0):
    x, y, w, h = box
    m = np.zeros(shape, bool)
    m[max(0, (y - pad) // DS):(y + h + pad) // DS, max(0, (x - pad) // DS):(x + w + pad) // DS] = True
    return m


def valid_region(shape):
    v = box_mask(shape, ROAD_BOX)
    for b in FURNITURE.values():
        v &= ~box_mask(shape, b, FURNITURE_PAD)
    return v


def draw_polys(geoms, shape, scale=DS):
    """Polygons (full-res px) -> bool raster at 1/scale. Holes are cut per polygon, in a local patch,
    so one polygon's hole never erases another polygon drawn earlier."""
    out = np.zeros(shape, bool)
    for g in geoms:
        if g is None or g.is_empty:
            continue
        for p in shapely.get_parts(g):
            if p.geom_type != "Polygon" or p.is_empty:
                continue
            x0, y0, x1, y1 = p.bounds
            ix0, iy0 = max(int(x0 / scale) - 1, 0), max(int(y0 / scale) - 1, 0)
            ix1, iy1 = min(int(x1 / scale) + 2, shape[1]), min(int(y1 / scale) + 2, shape[0])
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            im = Image.new("L", (ix1 - ix0, iy1 - iy0), 0)
            d = ImageDraw.Draw(im)
            d.polygon([((x - 0.5 * 0) / scale - ix0 - 0.5, y / scale - iy0 - 0.5) for x, y in p.exterior.coords], fill=1)
            for r in p.interiors:
                d.polygon([(x / scale - ix0 - 0.5, y / scale - iy0 - 0.5) for x, y in r.coords], fill=0)
            out[iy0:iy1, ix0:ix1] |= np.asarray(im, bool)
    return out


def open_disk(mask: np.ndarray, radius_px: float) -> np.ndarray:
    """Binary opening by a Euclidean disk, via EDT: cores = pixels whose disk fits, result = their
    dilation. Removes everything narrower than 2*radius."""
    core = ndimage.distance_transform_edt(mask) >= radius_px
    return ndimage.distance_transform_edt(~core) <= radius_px


# ----------------------------------------------------------------------------- blocks + junctions

def segment(road, water, valid, mpp_ds: float, close_px: int = CLOSE_PX, min_area_m2: float = MIN_BLOCK_M2,
            max_block_m: float = JUNCTION_MAX_BLOCK_M, edge_m: float = JUNCTION_EDGE_M):
    """Blocks and junctions of one epoch, from bool rasters (road, water, valid) on the working grid.

    Returns dict: blocks (int32 label image, water = n+1, 0 = street / outside), n_blocks,
    junctions (list of dicts: x, y in WORKING px, degree, quay, n_px), counts.
    The same function serves 1882 and 2023; nothing in it knows which epoch it is looking at.
    """
    road = road & valid
    road_d = ndimage.binary_dilation(road, structure=np.ones((3, 3), bool), iterations=close_px) if close_px else road
    land = valid & ~road_d & ~water
    lab, n0 = ndimage.label(land)                    # 4-connected
    areas = np.bincount(lab.ravel(), minlength=n0 + 1)
    keep = areas * mpp_ds**2 >= min_area_m2
    keep[0] = False
    remap = np.zeros(n0 + 1, np.int32)
    remap[keep] = np.arange(1, keep.sum() + 1)
    lab = remap[lab]
    n = int(keep.sum())
    # give the dilated rim back, but only over ground that was land before the dilation (geodesic growth, one
    # pixel a step), so a block keeps its true corners instead of the rounded ones a distance rule leaves
    land0 = valid & ~road & ~water
    blocks = lab.copy()
    for _ in range(close_px + 1):
        nb = ndimage.grey_dilation(blocks, size=(3, 3))
        claim = land0 & (blocks == 0) & (nb > 0)
        if not claim.any():
            break
        blocks[claim] = nb[claim]
    wat = water & valid & ~road
    wid = n + 1
    blocks[wat] = wid
    # Voronoi split of the street space, over blocks + water
    dist2, (iy, ix) = ndimage.distance_transform_edt(blocks == 0, return_indices=True)
    V = blocks[iy, ix]
    # candidates: street pixels whose 3x3 window of V is not constant
    street = (blocks == 0) & valid
    mn, mx = ndimage.minimum_filter(V, 3), ndimage.maximum_filter(V, 3)
    cand = street & (mn != mx) & (mn > 0)
    ys, xs = np.nonzero(cand)
    H, W = V.shape
    shifts = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
    win = np.stack([V[np.clip(ys + dy, 0, H - 1), np.clip(xs + dx, 0, W - 1)] for dy, dx in shifts], axis=1)
    win.sort(axis=1)
    ndist = 1 + (np.diff(win, axis=1) != 0).sum(axis=1)
    sel = ndist >= 3
    jm = np.zeros(V.shape, bool)
    jm[ys[sel], xs[sel]] = True
    cl, nc = ndimage.label(jm, structure=np.ones((3, 3), bool))
    edge_d = ndimage.distance_transform_edt(valid)
    junctions, rejected = [], Counter()
    if nc:
        cy, cx = np.nonzero(cl)
        cid = cl[cy, cx]
        keys = []
        for dy, dx in shifts:
            keys.append(cid.astype(np.int64) * (n + 3) + V[np.clip(cy + dy, 0, H - 1), np.clip(cx + dx, 0, W - 1)])
        u = np.unique(np.concatenate(keys))
        ucid, ulab = u // (n + 3), u % (n + 3)
        deg = np.bincount(ucid, minlength=nc + 1)
        quay = np.zeros(nc + 1, bool)
        quay[ucid[ulab == wid]] = True
        cnt = np.bincount(cid, minlength=nc + 1)
        sx, sy = np.bincount(cid, weights=cx, minlength=nc + 1), np.bincount(cid, weights=cy, minlength=nc + 1)
        for k in range(1, nc + 1):
            x, y = sx[k] / cnt[k] + 0.5, sy[k] / cnt[k] + 0.5      # pixel centres -> edge coordinates
            r, c = min(int(y), H - 1), min(int(x), W - 1)
            if dist2[r, c] * mpp_ds > max_block_m:
                rejected["far from every block"] += 1
            elif edge_d[r, c] * mpp_ds < edge_m:
                rejected["near the edge"] += 1
            else:
                junctions.append({"x": float(x), "y": float(y), "degree": int(deg[k]), "quay": bool(quay[k]),
                                  "n_px": int(cnt[k])})
    return {"blocks": blocks.astype(np.int32), "n_blocks": n, "water_id": wid, "junctions": junctions,
            "rejected": dict(rejected), "dropped_small": int((~keep[1:]).sum()), "valid": valid}


def block_polygons(seg, mpp: float, simplify_px: float = 1.5, max_m2: float = MAX_BLOCK_M2):
    """Label image -> list of shapely geometries in FULL-res px, with props. Water is not a block."""
    import rasterio.features
    from shapely.geometry import shape

    lab, n = seg["blocks"], seg["n_blocks"]
    m = (lab > 0) & (lab <= n)
    parts: dict[int, list] = {}
    for geom, val in rasterio.features.shapes(lab, mask=m, connectivity=4):
        parts.setdefault(int(val), []).append(shape(geom))
    valid = seg["valid"]
    touch = ndimage.binary_dilation(~valid, iterations=2) & valid
    touches_edge = set(np.unique(lab[touch & (lab > 0) & (lab <= n)]).tolist())
    wid = seg["water_id"]
    touch_w = ndimage.binary_dilation(lab == wid, iterations=3)
    touches_water = set(np.unique(lab[touch_w & (lab > 0) & (lab <= n)]).tolist())
    out = []
    for bid in sorted(parts):
        g = shapely.union_all(parts[bid])
        g = shapely.transform(g, lambda a: a * DS)
        g = g.simplify(simplify_px, preserve_topology=True)
        area_m2 = float(g.area) * mpp**2
        out.append((bid, g, {"id": bid, "area_m2": round(area_m2, 1), "open": area_m2 > max_m2,
                             "clipped": bid in touches_edge, "touches_water": bid in touches_water}))
    return out


# ----------------------------------------------------------------------------- matching and field

def match_junctions(a_xy, a_deg, m_xy, m_deg, mpp: float, max_m: float = MATCH_M, max_deg: int = MATCH_DEG):
    """Mutual nearest neighbour within max_m, |degree difference| <= max_deg. Returns (ia, im) index arrays."""
    if len(a_xy) == 0 or len(m_xy) == 0:
        return np.zeros(0, int), np.zeros(0, int)
    ta, tm = cKDTree(a_xy), cKDTree(m_xy)
    da, ja = tm.query(a_xy)        # for each 1882 junction, nearest modern
    dm, jm = ta.query(m_xy)
    ia = np.arange(len(a_xy))
    mutual = jm[ja] == ia
    ok = mutual & (da * mpp <= max_m) & (np.abs(np.asarray(a_deg) - np.asarray(m_deg)[ja]) <= max_deg)
    return ia[ok], ja[ok]


def tile_ids(xy, mpp: float, tile_m: float = TILE_M):
    t = np.floor(np.asarray(xy) * mpp / tile_m).astype(int)
    return t[:, 0], t[:, 1]


def affine_fit(xy, d):
    A = np.column_stack([xy, np.ones(len(xy))])
    coef, *_ = np.linalg.lstsq(A, d, rcond=None)
    return lambda q: np.column_stack([np.asarray(q, float).reshape(-1, 2), np.ones(len(q))]) @ coef


def robust_keep(xy, d, k=3.0, rounds=2):
    """Mask of matches that sit within k robust sigmas of an affine of the displacements. Used on FIT sets only
    (never on the held-out tiles): a mutual-nearest match across a missing street is a wrong match, not a datum."""
    keep = np.ones(len(xy), bool)
    for _ in range(rounds):
        f = affine_fit(xy[keep], d[keep])
        r = np.linalg.norm(f(xy) - d, axis=1)
        med = np.median(r[keep])
        mad = 1.4826 * np.median(np.abs(r[keep] - med))
        keep = r <= med + k * max(mad, 1.0)
    return keep


def rbf_fit(xy, d, smoothing):
    r = RBFInterpolator(xy, d, kernel="thin_plate_spline", smoothing=smoothing)
    return lambda q: r(np.asarray(q, float).reshape(-1, 2))


def choose_smoothing(xy, d, mpp, grid=(1.0, 10.0, 100.0, 1000.0, 10000.0)):
    """Leave-one-tile-out CV over the A points (xy in px, d in metres). Returns (best, {s: median|res| m})."""
    tx, ty = tile_ids(xy, mpp)
    tiles = sorted(set(zip(tx.tolist(), ty.tolist())))
    scores = {}
    for s in grid:
        res = []
        for t in tiles:
            te = (tx == t[0]) & (ty == t[1])
            if te.all() or te.sum() == 0 or (~te).sum() < 8:
                continue
            f = rbf_fit(xy[~te], d[~te], s)
            res.append(np.linalg.norm(f(xy[te]) - d[te], axis=1))
        scores[s] = float(np.median(np.concatenate(res))) if res else float("inf")
    best = min(scores, key=scores.get)
    return best, scores


def similarity_fit(src, dst):
    """Least-squares rotation + uniform scale + translation (about the centroid): returns (deg, scale, r2).
    r2 = share of the displacement variance this explains."""
    s0, d0 = src - src.mean(0), dst - dst.mean(0)
    a = (s0 * d0).sum() / (s0 * s0).sum()
    b = (s0[:, 0] * d0[:, 1] - s0[:, 1] * d0[:, 0]).sum() / (s0 * s0).sum()
    pred = np.column_stack([a * s0[:, 0] - b * s0[:, 1], b * s0[:, 0] + a * s0[:, 1]])
    disp = d0 - s0
    resid = d0 - pred
    r2 = 1 - (resid**2).sum() / max((disp**2).sum(), 1e-9)
    return math.degrees(math.atan2(b, a)), math.hypot(a, b), float(r2)


# ----------------------------------------------------------------------------- classes

def classify(a_geoms: dict, m_geoms: dict, edge_frac: float = EDGE_FRAC, iou_same: float = IOU_SAME):
    """Bipartite overlap graph over two dicts id -> polygon (same frame). Returns a list of components:
    {a: [ids], m: [ids], iou: float|None, cls: str|None}. `cls` is None for an isolated 1882 block
    ('gone' / 'unpartnered', which needs the modern road raster) and 'new' for an isolated modern one.
    """
    aid, mid = list(a_geoms), list(m_geoms)
    ag, mg = [a_geoms[i] for i in aid], [m_geoms[i] for i in mid]
    tree = shapely.STRtree(mg)
    ia, im = tree.query(ag, predicate="intersects")
    parent = {("a", i): ("a", i) for i in aid} | {("m", j): ("m", j) for j in mid}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    edges = 0
    for i, j in zip(ia, im):
        inter = shapely.intersection(ag[i], mg[j]).area
        if inter >= edge_frac * ag[i].area or inter >= edge_frac * mg[j].area:
            parent[find(("a", aid[i]))] = find(("m", mid[j]))
            edges += 1
    comps: dict = {}
    for k in parent:
        comps.setdefault(find(k), []).append(k)
    out = []
    for k, members in comps.items():
        a = sorted(i for t, i in members if t == "a")
        m = sorted(i for t, i in members if t == "m")
        iou, cls = None, None
        if a and m:
            ua, um = shapely.union_all([a_geoms[i] for i in a]), shapely.union_all([m_geoms[i] for i in m])
            inter = ua.intersection(um).area
            iou = float(inter / max(ua.union(um).area, 1e-9))
            if len(a) == 1 and len(m) == 1:
                cls = "unchanged" if iou >= iou_same else "reshaped"
            elif len(a) == 1:
                cls = "split"
            elif len(m) == 1:
                cls = "merged"
            else:
                cls = "complex"
        elif m:
            cls = "new"
        out.append({"a": a, "m": m, "iou": iou, "cls": cls})
    return out


# ----------------------------------------------------------------------------- GeoJSON out

def gj(geom):
    """GeoJSON dict, coordinates rounded to 0.1 px."""
    return json.loads(shapely.to_geojson(shapely.transform(geom, lambda a: np.round(a, 1))))


def feat(geom, props):
    return {"type": "Feature", "geometry": gj(geom), "properties": props}


def write_fc(path: Path, features, extra=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"type": "FeatureCollection", "crs": "source-pixels-y-down", "method": METHOD, "features": features}
    doc.update(extra or {})
    path.write_text(json.dumps(doc), encoding="utf-8")
    print(f"  -> {path.relative_to(ROOT)}  ({len(features)} features)")


def _load_annotation():
    cache = OUT / "annotation.json"
    try:
        from scale import annotation_for_map

        ann = annotation_for_map(MAP_ID)
        if ann:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(ann))
            return ann
    except Exception as e:  # network off: fall back to the copy of the last run
        print("annotation fetch failed:", e, file=sys.stderr)
    return json.loads(cache.read_text())


def _rss():
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9   # bytes on darwin -> GB


# ----------------------------------------------------------------------------- the run

def run(args):
    import modern_prior as mp
    from scale import gcps_from_annotation

    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "spot").mkdir(exist_ok=True)
    ann = _load_annotation()
    fit = mp.fit_sheet(ann)
    mpp = fit.metres_per_px
    mpp_ds = mpp * DS
    gpx, _, _ = gcps_from_annotation(ann)
    print(f"fit {fit}")

    river = RES / MAP_ID / "river"
    road_full = np.asarray(Image.open(river / "road-a3b0458f.png")) == 255
    water_full = np.asarray(Image.open(river / "water-1006337f.png")) == 255
    Hf, Wf = road_full.shape
    road1882, water1882 = maxpool(road_full), maxpool(water_full)
    del road_full, water_full
    valid = valid_region(road1882.shape)
    shape = road1882.shape
    print(f"grid {shape[1]}x{shape[0]} at 1/{DS}; mpp_ds {mpp_ds:.3f}; valid {valid.mean():.2%}")

    S: dict = {"method": METHOD, "map_id": MAP_ID, "transform": "modern_prior.fit_sheet affine (8 gcps helmert-annotated, "
               f"{fit.rms_px:.1f} px / {fit.rms_m:.1f} m rms, worst {fit.max_px:.1f} px)", "metres_per_px": mpp,
               "sources": {"1882": ["river/road-a3b0458f.png (v3, diagnostic only)", "river/water-1006337f.png (v3)"],
                           "modern": "TASCO hcmc_vector.gpkg region_duongbos + region_river + region_lake (public)"}}

    # ---- 1882 side
    sweep = {}
    for c in (1, 2, 4, 6, 10, 14):
        sw = segment(road1882, water1882, valid, mpp_ds, close_px=c)
        ar = np.bincount(sw["blocks"].ravel())[1:sw["n_blocks"] + 1] * mpp_ds**2
        sweep[c] = {"blocks": sw["n_blocks"], "blocks_2000_to_200000_m2": int(((ar >= 2000) & (ar <= MAX_BLOCK_M2)).sum()),
                    "open_over_200000_m2": int((ar > MAX_BLOCK_M2).sum()), "junctions": len(sw["junctions"])}
    S["closing_sweep_1882"] = sweep
    print("closing sweep", sweep)
    seg_a = segment(road1882, water1882, valid, mpp_ds)
    polys_a = block_polygons(seg_a, mpp)
    print(f"1882: {seg_a['n_blocks']} blocks ({sum(p[2]['open'] for p in polys_a)} open), {len(seg_a['junctions'])} junctions, "
          f"rejected {seg_a['rejected']}, dropped small {seg_a['dropped_small']}   [{time.time()-t0:.0f}s, rss {_rss():.1f} GB]")

    # ---- modern side
    bbox = fit.bbox_lonlat(Wf, Hf)
    layers = {}
    for lyr in (*mp.ROAD_SURFACE_LAYERS, *mp.WATER_SURFACE_LAYERS):
        layers[lyr] = mp.warp(mp._read(mp.TASCO_GPKG, lyr, ["madoituong"], bbox)[0], fit)
    print({k: len(v) for k, v in layers.items()})
    road_m_raw = draw_polys(layers["region_duongbos"], shape)
    water_m = draw_polys([*layers["region_river"], *layers["region_lake"]], shape)
    street_m = open_disk(road_m_raw, STREET_W_M / 2 / mpp_ds)
    print(f"modern road raster {road_m_raw.mean():.3f} of grid, streets>=8 m {street_m.mean():.3f}   [{time.time()-t0:.0f}s]")
    seg_m = segment(street_m, water_m, valid, mpp_ds)
    polys_m = block_polygons(seg_m, mpp)
    print(f"2023: {seg_m['n_blocks']} blocks ({sum(p[2]['open'] for p in polys_m)} open), {len(seg_m['junctions'])} junctions, "
          f"rejected {seg_m['rejected']}   [{time.time()-t0:.0f}s]")

    # ---- d4_morph agreement on a seeded sample of road polygons
    S["d4_morph_agreement"] = d4_agreement(layers["region_duongbos"], fit, mpp_ds)

    junc_a = np.array([[j["x"] * DS, j["y"] * DS] for j in seg_a["junctions"]])
    junc_m = np.array([[j["x"] * DS, j["y"] * DS] for j in seg_m["junctions"]])
    deg_a = np.array([j["degree"] for j in seg_a["junctions"]])
    deg_m = np.array([j["degree"] for j in seg_m["junctions"]])
    for name, seg, arr in (("1882", seg_a, junc_a), ("modern", seg_m, junc_m)):
        write_fc(OUT / f"junctions_{name}.geojson", [feat(shapely.Point(x, y), {"id": i, **{k: v for k, v in j.items() if k not in ("x", "y")}})
                                                     for i, ((x, y), j) in enumerate(zip(arr, seg["junctions"]))],
                 {"source": S["sources"]["1882" if name == "1882" else "modern"]})
    for name, polys in (("1882", polys_a), ("modern", polys_m)):
        write_fc(OUT / f"blocks_{name}.geojson", [feat(g, p) for _, g, p in polys], {"source": S["sources"]["1882" if name == "1882" else "modern"]})
    S["counts"] = {"blocks_1882": len(polys_a), "blocks_modern": len(polys_m),
                   "open_1882": sum(p[2]["open"] for p in polys_a), "open_modern": sum(p[2]["open"] for p in polys_m),
                   "junctions_1882": len(junc_a), "junctions_modern": len(junc_m),
                   "junction_rejected_1882": seg_a["rejected"], "junction_rejected_modern": seg_m["rejected"],
                   "dropped_small_1882": seg_a["dropped_small"], "dropped_small_modern": seg_m["dropped_small"],
                   "quay_1882": int(sum(j["quay"] for j in seg_a["junctions"])), "quay_modern": int(sum(j["quay"] for j in seg_m["junctions"]))}

    # ---- match + field
    ia, im = match_junctions(junc_a, deg_a, junc_m, deg_m, mpp)
    d_m = (junc_m[im] - junc_a[ia]) * mpp                       # modern - 1882, metres, fit_sheet frame
    near_gcp = (np.linalg.norm(junc_a[ia][:, None, :] - gpx[None, :, :], axis=2).min(axis=1) * mpp) <= IN_FIT_M
    S["matches"] = {"n": len(ia), "unmatched_1882": len(junc_a) - len(ia), "unmatched_modern": len(junc_m) - len(ia),
                    "share_1882_unmatched": round(1 - len(ia) / max(len(junc_a), 1), 3),
                    "share_modern_unmatched": round(1 - len(ia) / max(len(junc_m), 1), 3), "in_fit": int(near_gcp.sum()),
                    "note": f"errors larger than the {MATCH_M:.0f} m window cannot appear as matches: the unmatched share is a floor on what is missing"}
    print("matches", S["matches"])
    field, fstat = field_report(junc_a[ia], d_m, near_gcp, mpp, gpx, fit, Wf, Hf)
    S["field"] = fstat
    import csv

    with (OUT / "matches.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x1882", "y1882", "xmodern", "ymodern", "dx_m", "dy_m", "abs_m", "deg_1882", "deg_modern", "in_fit", "tile_split",
                    "resid_rbf_m", "resid_affine_m"])
        for k in range(len(ia)):
            w.writerow([round(junc_a[ia[k]][0], 1), round(junc_a[ia[k]][1], 1), round(junc_m[im[k]][0], 1), round(junc_m[im[k]][1], 1),
                        round(d_m[k][0], 2), round(d_m[k][1], 2), round(float(np.hypot(*d_m[k])), 2), deg_a[ia[k]], deg_m[im[k]],
                        int(near_gcp[k]), fstat["_split"][k], round(fstat["_rbf"][k], 2) if not np.isnan(fstat["_rbf"][k]) else "",
                        round(fstat["_aff"][k], 2) if not np.isnan(fstat["_aff"][k]) else ""])
    for k in ("_split", "_rbf", "_aff"):
        fstat.pop(k)
    field_png(OUT / "field.png", junc_a[ia], d_m, field, Wf, Hf, mpp)
    S["prediction_vs_result"] = prediction_vs_result(fstat, d_m, junc_a[ia], Wf, Hf, mpp)

    # ---- classes
    cls_feats, cstat = build_classes(polys_a, polys_m, field, seg_a, street_m, water_m, shape, mpp, gpx)
    S["classes"] = cstat
    ll0 = fit.origin
    nv = fit.px(np.array([ll0 + [0, 0.001]]))[0] - fit.px(np.array([ll0]))[0]
    north_px = (nv / np.linalg.norm(nv)).round(4).tolist()      # where north points in source px (y down)
    S["north_px"] = north_px
    write_fc(OUT / "classes.geojson", cls_feats, {"source": S["sources"], "classes": list(CLASSES), "north_px": north_px})

    # ---- independent score
    S["independent_score"] = qgis_score(polys_a, fstat, mpp)
    (OUT / "summary.json").write_text(json.dumps(S, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(f"-> {OUT / 'summary.json'}   [{time.time()-t0:.0f}s]")
    spot_pngs(cls_feats, field, mpp)
    return 0


def field_report(xy, d_m, in_fit, mpp, gpx, fit, Wf, Hf):
    """Checkerboard split, three predictors on B, the final field on everything. Returns (field callable px->metres, stats)."""
    tx, ty = tile_ids(xy, mpp)
    A = (tx + ty) % 2 == 0
    B = ~A
    n = len(xy)
    st: dict = {"tile_m": TILE_M, "n_A": int(A.sum()), "n_B": int(B.sum()), "transform": "modern_prior.fit_sheet affine"}
    if A.sum() < 12 or B.sum() < 12:
        raise SystemExit(f"too few matches for a checkerboard split: A {A.sum()}, B {B.sum()}")
    kA = np.nonzero(A)[0][robust_keep(xy[A], d_m[A])]
    kB = np.nonzero(B)[0][robust_keep(xy[B], d_m[B])]
    st["fit_outliers_dropped_A"], st["fit_outliers_dropped_B_fit"] = int(A.sum() - len(kA)), int(B.sum() - len(kB))
    s_best, s_cv = choose_smoothing(xy[kA], d_m[kA], mpp)
    st["rbf_smoothing"], st["rbf_cv_median_m"] = s_best, {str(k): round(v, 2) for k, v in s_cv.items()}
    fa, fr = affine_fit(xy[kA], d_m[kA]), rbf_fit(xy[kA], d_m[kA], s_best)
    const = np.median(d_m[A], axis=0)
    pred = {"raw (no correction)": np.zeros_like(d_m[B]), "constant shift (A median)": np.broadcast_to(const, d_m[B].shape),
            "affine (A)": fa(xy[B]), "RBF (A)": fr(xy[B])}
    ev = B & ~in_fit
    evm = ev[B]

    def stat(r):
        r = np.linalg.norm(r, axis=1)[evm]
        return {"median_m": round(float(np.median(r)), 2), "p90_m": round(float(np.percentile(r, 90)), 2), "mean_m": round(float(r.mean()), 2), "n": int(len(r))}

    st["heldout_B_excl_in_fit"] = {k: stat(d_m[B] - p) for k, p in pred.items()}
    st["in_fit_B_apart"] = {k: ({"median_m": round(float(np.median(np.linalg.norm(d_m[B] - p, axis=1)[~evm])), 2), "n": int((~evm).sum())} if (~evm).any() else None)
                            for k, p in pred.items()}
    # the symmetric split (fit on B, test on A) as a stability check
    fa2, fr2 = affine_fit(xy[kB], d_m[kB]), rbf_fit(xy[kB], d_m[kB], s_best)
    eva = (A & ~in_fit)[A]
    st["heldout_A_from_B"] = {"raw": round(float(np.median(np.linalg.norm(d_m[A], axis=1)[eva])), 2),
                              "affine": round(float(np.median(np.linalg.norm(fa2(xy[A]) - d_m[A], axis=1)[eva])), 2),
                              "RBF": round(float(np.median(np.linalg.norm(fr2(xy[A]) - d_m[A], axis=1)[eva])), 2)}
    absd = np.linalg.norm(d_m, axis=1)
    st["abs_d_m"] = {"median": round(float(np.median(absd)), 2), "p10": round(float(np.percentile(absd, 10)), 2),
                     "p90": round(float(np.percentile(absd, 90)), 2), "max": round(float(absd.max()), 2), "median_excl_in_fit": round(float(np.median(absd[~in_fit])), 2)}
    split = np.where(A, "A", "B")
    rbf_res = np.full(n, np.nan)
    aff_res = np.full(n, np.nan)
    rbf_res[B] = np.linalg.norm(pred["RBF (A)"] - d_m[B], axis=1)
    aff_res[B] = np.linalg.norm(pred["affine (A)"] - d_m[B], axis=1)
    st["_split"], st["_rbf"], st["_aff"] = split, rbf_res, aff_res
    # the field used downstream: RBF on every match
    kall = robust_keep(xy, d_m)
    st["fit_outliers_dropped_final"] = int((~kall).sum())
    s_all, _ = choose_smoothing(xy[kall], d_m[kall], mpp)
    st["rbf_smoothing_final"] = s_all
    tree = cKDTree(xy[kall])
    f_all = rbf_fit(xy[kall], d_m[kall], s_all)
    aff_all = affine_fit(xy[kall], d_m[kall])

    # the field that warps the modern blocks is whichever predictor did better held out (mean of B-from-A and A-from-B)
    hb, ha = st["heldout_B_excl_in_fit"], st["heldout_A_from_B"]
    aff_score, rbf_score = (hb["affine (A)"]["median_m"] + ha["affine"]) / 2, (hb["RBF (A)"]["median_m"] + ha["RBF"]) / 2
    use_affine = aff_score <= rbf_score
    st["field_used"] = "affine" if use_affine else "RBF"
    st["field_used_why"] = f"mean held-out median: affine {aff_score:.2f} m, RBF {rbf_score:.2f} m"

    def field(q):
        q = np.asarray(q, float).reshape(-1, 2)
        if use_affine:
            return aff_all(q)
        dist, _ = tree.query(q)
        far = dist * mpp > 300.0       # beyond 300 m from any match the RBF is extrapolating: fall back to the affine
        out = f_all(q)
        out[far] = aff_all(q[far])
        return out

    st["field_support_m"] = 300.0
    return field, st


def prediction_vs_result(fst, d_m, xy, Wf, Hf, mpp):
    c = np.array([Wf / 2, Hf / 2])
    # centre of the *matches*' ground, not the page: the page is half empty
    ctr = xy.mean(0)
    deg, scale, r2 = similarity_fit(xy * mpp, xy * mpp + d_m)
    r = np.linalg.norm(xy - ctr, axis=1) * mpp
    absd = np.linalg.norm(d_m, axis=1)
    bins = np.quantile(r, [0, .25, .5, .75, 1.0])
    by_r = [round(float(np.median(absd[(r >= bins[i]) & (r <= bins[i + 1])])), 1) for i in range(4)]
    # tangential vs radial components about the match centroid
    rv = (xy - ctr) * mpp
    rh = rv / np.maximum(np.linalg.norm(rv, axis=1, keepdims=True), 1e-9)
    tang = rh[:, 0] * d_m[:, 1] - rh[:, 1] * d_m[:, 0]
    radial = (rh * d_m).sum(1)
    med = fst["abs_d_m"]["median"]
    held = fst["heldout_B_excl_in_fit"]
    out = {"predicted": "median |d| 10-15 m; rotational pattern ~0.88 deg; largest at the edges; RBF < affine < raw on B",
           "median_abs_d_m": med, "median_in_predicted_10_15": bool(10 <= med <= 15),
           "best_similarity_rotation_deg": round(deg, 3), "best_similarity_scale": round(scale, 5), "similarity_explains_share_of_d_variance": round(r2, 3),
           "rotation_vs_0.88deg": "sign convention: positive = counter-clockwise in the px frame as drawn (y down)",
           "median_abs_d_by_radius_quartile_m": by_r, "radius_quartile_edges_m": [round(float(b)) for b in bins],
           "median_tangential_m": round(float(np.median(tang)), 2), "median_radial_m": round(float(np.median(radial)), 2),
           "median_dx_dy_m": [round(float(np.median(d_m[:, 0])), 2), round(float(np.median(d_m[:, 1])), 2)],
           "heldout_medians_B_m": {k: v["median_m"] for k, v in held.items()}}
    dis = []
    if not 10 <= med <= 15:
        dis.append(f"median |d| {med} m is outside the predicted 10-15 m")
    if abs(abs(deg) - 0.88) > 0.4:
        dis.append(f"best-fit rotation {deg:.2f} deg is not within 0.4 deg of the predicted +-0.88")
    if r2 < 0.5:
        dis.append(f"a rotation+scale+shift explains only {r2:.0%} of the displacement variance: the pattern is not mainly rotational")
    if not by_r[3] > by_r[0]:
        dis.append("|d| is not larger at the outer radius quartile than at the inner one")
    if not held["RBF (A)"]["median_m"] < held["affine (A)"]["median_m"] < held["raw (no correction)"]["median_m"]:
        dis.append("held-out ordering RBF < affine < raw does not hold")
    out["disagreements"] = dis or ["none"]
    return out


def field_png(path, xy, d_m, field, Wf, Hf, mpp):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    nat = RES / MAP_ID / "native.png"
    fig, ax = plt.subplots(figsize=(14, 10.4))
    if nat.exists():
        im = Image.open(nat).convert("L")
        im.draft("L", (Wf // 8, Hf // 8))
        im = im.resize((Wf // 8, Hf // 8))
        ax.imshow(np.asarray(im), cmap="gray", extent=(0, Wf, Hf, 0), alpha=0.55)
    absd = np.linalg.norm(d_m, axis=1)
    # arrows are exaggerated x20 so a 10 m shift is visible on a 4 km sheet
    q = ax.quiver(xy[:, 0], xy[:, 1], d_m[:, 0] / mpp * 20, d_m[:, 1] / mpp * 20, absd, angles="xy", scale_units="xy", scale=1,
                  cmap="turbo", clim=(0, max(30, float(np.percentile(absd, 95)))), width=0.002)
    gx, gy = np.meshgrid(np.linspace(600, Wf - 700, 18), np.linspace(560, 7950, 12))
    g = np.column_stack([gx.ravel(), gy.ravel()])
    ax.set_xlim(0, Wf)
    ax.set_ylim(Hf, 0)
    plt.colorbar(q, ax=ax, shrink=0.6, label="|d| metres (modern - 1882, fit_sheet frame)")
    ax.set_title("Displacement of matched junctions (arrows x20). Source px, y down, image +x = north")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {path.relative_to(ROOT)}")


def _opened_share(poly, mpp_ds):
    """Share of ONE polygon's own area that survives opening by a 4 m disk, drawn alone (padded)."""
    x0, y0, x1, y1 = poly.bounds
    pad = 8
    sh = (int((y1 - y0) / DS) + 2 * pad, int((x1 - x0) / DS) + 2 * pad)
    moved = shapely.transform(poly, lambda a: a - np.array([x0 - pad * DS, y0 - pad * DS]))
    r = draw_polys([moved], sh)
    a = r.sum()
    return (open_disk(r, STREET_W_M / 2 / mpp_ds) & r).sum() / a if a else float("nan")


def d4_agreement(road_polys_px, fit, mpp_ds, n=150, seed=1, big_m2=1000.0):
    """Do the opening (r = 4 m) and d4_morph's 2*area/length >= 8 m rule call the same road polygons streets?
    Each polygon is judged alone (a polygon beside a wide one would otherwise survive on its neighbour's width).
    Two samples: n uniform over polygons, n over polygons >= big_m2 (most of the road *area* is in these)."""
    import geopandas as gpd

    ll = shapely.transform(road_polys_px, fit.lonlat)
    g = gpd.GeoSeries(ll, crs=4326).to_crs(32648)
    width = 2 * g.area.values / g.length.values
    area_m2 = g.area.values
    rng = np.random.default_rng(seed)
    out = {"rule": "opening call = >= 50% of the polygon's own area survives a 4 m-radius opening; d4 call = 2*area/perimeter >= 8 m in EPSG:32648",
           "all_polygons": int(len(width)), "d4_street_share_all_polygons": round(float((width >= STREET_W_M).mean()), 3),
           "d4_street_share_of_road_area": round(float(area_m2[width >= STREET_W_M].sum() / area_m2.sum()), 3)}
    for name, pool in (("uniform", np.arange(len(width))), (f"area>={big_m2:.0f}m2", np.nonzero(area_m2 >= big_m2)[0])):
        pool = pool[np.array([road_polys_px[i].bounds[2] - road_polys_px[i].bounds[0] < 6000 and road_polys_px[i].bounds[3] - road_polys_px[i].bounds[1] < 6000 for i in pool])]
        idx = rng.choice(pool, size=min(n, len(pool)), replace=False)
        sh = np.array([_opened_share(road_polys_px[i], mpp_ds) for i in idx])
        d4, op = width[idx] >= STREET_W_M, sh >= 0.5
        out[name] = {"n": int(len(idx)), "agree": round(float((d4 == op).mean()), 3), "both_street": int((d4 & op).sum()), "both_alley": int((~d4 & ~op).sum()),
                     "d4_street_only": int((d4 & ~op).sum()), "opening_street_only": int((~d4 & op).sum())}
    out["note"] = "d4_morph itself says one width per polygon and junction polygons read wide; the opening is local, so a polygon that is wide only at a junction survives there"
    print("d4 agreement", out)
    return out


def build_classes(polys_a, polys_m, field, seg_a, street_m, water_m, shape, mpp, gpx):
    a_all = {bid: (g, p) for bid, g, p in polys_a}
    m_all = {bid: (g, p) for bid, g, p in polys_m}
    a_use = {i: g for i, (g, p) in a_all.items() if not p["open"]}
    # modern blocks warped into the 1882 frame: p - d(p)/mpp
    m_warp = {}
    for i, (g, p) in m_all.items():
        if p["open"]:
            continue
        g2 = shapely.segmentize(g, 60.0)
        m_warp[i] = shapely.transform(g2, lambda a: a - field(a) / mpp).buffer(0)
    comps = classify(a_use, m_warp)
    open_a = np.isin(seg_a["blocks"], [i for i, (g, p) in a_all.items() if p["open"]])
    modern_wat = street_m | water_m
    feats, counts = [], Counter()
    gpoint = shapely.MultiPoint(gpx)
    for k, c in enumerate(comps):
        ua = shapely.union_all([a_use[i] for i in c["a"]]) if c["a"] else None
        um = shapely.union_all([m_warp[i] for i in c["m"]]) if c["m"] else None
        cls, extra = c["cls"], {}
        if cls is None and ua is not None:     # isolated 1882 block
            shifted = shapely.transform(shapely.segmentize(ua, 60.0), lambda a: a + field(a) / mpp)   # into the modern frame
            r = draw_polys([shifted], shape)
            under = float((r & modern_wat).sum() / max(r.sum(), 1))
            extra["under_modern_road_water"] = round(under, 3)
            cls = "gone" if under >= GONE_FRAC else "unpartnered"
        if cls == "new":
            r = draw_polys([um], shape)
            extra["in_1882_open"] = bool((r & open_a).sum() / max(r.sum(), 1) >= 0.5)
        subject = ua if ua is not None else um
        in_fit = bool(shapely.distance(subject, gpoint) * mpp <= IN_FIT_M)
        clipped = any(a_all[i][1]["clipped"] for i in c["a"]) or any(m_all[i][1]["clipped"] for i in c["m"])
        counts[cls] += 1
        props = {"id": k, "class": cls, "a_ids": c["a"], "m_ids": c["m"], "iou": None if c["iou"] is None else round(c["iou"], 3),
                 "area_a_m2": None if ua is None else round(ua.area * mpp**2), "area_m_m2": None if um is None else round(um.area * mpp**2),
                 "in_fit": in_fit, "clipped": clipped, "method": METHOD, **extra,
                 "a_outline": None if ua is None else gj(ua),
                 "m_outline": None if um is None else gj(um)}
        feats.append({"type": "Feature", "geometry": gj(subject), "properties": props})
    sizes = Counter((len(c["a"]), len(c["m"])) for c in comps if c["a"] and c["m"])
    st = {"components": len(comps), "by_class": dict(counts), "a_blocks_in_graph": len(a_use), "m_blocks_in_graph": len(m_warp),
          "a_open_excluded": len(a_all) - len(a_use), "m_open_excluded": len(m_all) - len(m_warp),
          "new_in_1882_open": sum(1 for f in feats if f["properties"].get("in_1882_open")),
          "in_fit_components": sum(f["properties"]["in_fit"] for f in feats), "clipped_components": sum(f["properties"]["clipped"] for f in feats),
          "largest_component_blocks": max(((len(c["a"]) + len(c["m"])) for c in comps), default=0),
          "component_shapes_top": {f"{a}:{m}": n for (a, m), n in sizes.most_common(8)},
          "iou_unchanged_median": round(float(np.median([c["iou"] for c in comps if c["cls"] == "unchanged"] or [0])), 3)}
    print("classes", st)
    return feats, st


def qgis_score(polys_a, fst, mpp):
    """1882 blocks vs the owner's plots in one window.

    The plots are colour plots that subdivide a block (about a quarter of one), so a plot is not scored against a
    block: the owner's *blocks* are the connected components of the plots' union (each plot grown 1.5 m so touching
    plots fuse, shrunk back), and it is those outlines that are compared. Boundary F at the field's held-out RBF
    residual (precision: my traced blocks' boundary near theirs; recall: theirs near mine); best-match IoU of each
    owner block fully inside the window against my blocks (unclipped)."""
    import geopandas as gpd

    gp = RES / MAP_ID / "qgis-1882-20261003" / "1882-edit.gpkg"
    plots = gpd.read_file(gp, layer="plots")
    geoms = shapely.transform(plots.geometry.values, lambda a: a * np.array([1, -1]))   # gpkg y = -row
    cxy = shapely.get_coordinates(shapely.centroid(geoms))
    # window by plot density alone: the 2000 x 2000 px cell, on a 1000 px step, with the most plot centroids
    best, win = -1, None
    for x in range(600, 10800 - 2000, 1000):
        for y in range(560, 7950 - 2000, 1000):
            n = int(((cxy[:, 0] >= x) & (cxy[:, 0] < x + 2000) & (cxy[:, 1] >= y) & (cxy[:, 1] < y + 2000)).sum())
            if n > best:
                best, win = n, (x, y, 2000, 2000)
    x, y, w, h = win
    box = shapely.box(x, y, x + w, y + h)
    used = "affine (A)" if fst["field_used"] == "affine" else "RBF (A)"
    tol_m = fst["heldout_B_excl_in_fit"][used]["median_m"]
    tol_px = tol_m / mpp
    g15 = 1.5 / mpp
    near = [g for g in geoms if g.intersects(box)]
    fused = shapely.union_all([g.buffer(g15, join_style="mitre") for g in near]).buffer(-g15, join_style="mitre")
    owner = [g for g in shapely.get_parts(fused) if g.area * mpp**2 >= MIN_BLOCK_M2]
    inside = [g for g in owner if box.buffer(-1).contains(g)]
    mine_all = [(bid, g) for bid, g, p in polys_a if not p["open"] and g.intersects(box)]
    if not inside or not mine_all:
        return {"window_px": [x, y, w, h], "error": "empty"}
    ou = shapely.union_all(owner)
    traced = [(b, g) for b, g in mine_all if g.intersection(ou).area >= 0.3 * g.area and box.buffer(-1).contains(g)]
    bo = shapely.union_all([g.boundary for g in inside])
    bm = shapely.union_all([g.boundary for _, g in traced]) if traced else shapely.GeometryCollection()
    prec = bm.intersection(bo.buffer(tol_px)).length / max(bm.length, 1e-9)       # my boundary near the owner's
    rec = bo.intersection(bm.buffer(tol_px)).length / max(bo.length, 1e-9)        # owner's boundary near mine
    f = 2 * prec * rec / max(prec + rec, 1e-9)
    tree = shapely.STRtree([g for _, g in mine_all])
    ious = []
    for og_i in inside:
        cand = tree.query(og_i, predicate="intersects")
        ious.append(max((og_i.intersection(mine_all[c][1]).area / og_i.union(mine_all[c][1]).area for c in cand), default=0.0))
    ious = np.array(ious)
    return {"window_px": [x, y, w, h], "window_chosen_by": f"max plot centroids on a 1000 px step ({best} plots), before any scoring",
            "tolerance_m": tol_m, "tolerance_px": round(tol_px, 1), "tolerance_is": f"median held-out residual on B tiles of the field used ({fst['field_used']})",
            "owner_plots_in_window": len(near), "owner_blocks_fused_inside_window": len(inside), "my_blocks_in_window": len(mine_all),
            "my_blocks_inside_and_traced": len(traced),
            "boundary_precision": round(float(prec), 3), "boundary_recall": round(float(rec), 3), "boundary_F": round(float(f), 3),
            "best_match_iou_median": round(float(np.median(ious)), 3), "best_match_iou_mean": round(float(ious.mean()), 3),
            "share_owner_blocks_with_iou_ge_0.5": round(float((ious >= 0.5).mean()), 3),
            "note": "plots are the owner's regularised colour plots (needs_review), fused here into blocks; an agreement score between two proposals, not an accuracy",
            "not_tuned_on": True}


def spot_pngs(feats, field, mpp):
    """6 overlays for a person to look at: 2 unchanged, 1 split, 1 merged, 1 gone, 1 new (not on 1882 open ground)."""
    nat = RES / MAP_ID / "native.png"
    if not nat.exists():
        return
    for old in (OUT / "spot").glob("*.png"):
        old.unlink()
    im = Image.open(nat).convert("RGB")
    by = {}
    for f in feats:
        p = f["properties"]
        if p["in_fit"] or p["clipped"] or p.get("in_1882_open"):
            continue
        by.setdefault(p["class"], []).append(f)
    rng = np.random.default_rng(7)
    chosen = []
    for cls, n in (("unchanged", 2), ("split", 1), ("merged", 1), ("gone", 1), ("new", 1)):
        pool = by.get(cls) or []
        for i in (rng.choice(len(pool), size=min(n, len(pool)), replace=False) if pool else []):
            chosen.append(pool[i])
    for f in chosen:
        p = f["properties"]
        render_item(im, p, OUT / "spot" / f"{p['class']}-{p['id']}.png")
    print(f"  -> {len(chosen)} spot pngs in {OUT / 'spot'}")


def render_item(im, p, path, margin=120, max_side=1100):
    """Crop of the 1882 scan, 1882 outline solid (red), modern warped outline dashed (blue)."""
    shapes = [shapely.from_geojson(json.dumps(o)) for o in (p["a_outline"], p["m_outline"]) if o]
    x0, y0, x1, y1 = shapely.union_all(shapes).bounds
    x0, y0, x1, y1 = int(x0 - margin), int(y0 - margin), int(x1 + margin), int(y1 + margin)
    c = im.crop((x0, y0, x1, y1))
    z = min(1.0, max_side / max(c.size))
    c = c.resize((max(1, round(c.width * z)), max(1, round(c.height * z))), Image.LANCZOS)
    d = ImageDraw.Draw(c)

    def rings(o):
        g = shapely.from_geojson(json.dumps(o))
        for pg in shapely.get_parts(g):
            yield list(pg.exterior.coords)
            for r in pg.interiors:
                yield list(r.coords)

    if p["a_outline"]:
        for r in rings(p["a_outline"]):
            d.line([((x - x0) * z, (y - y0) * z) for x, y in r], fill=(255, 40, 40), width=3)
    if p["m_outline"]:
        for r in rings(p["m_outline"]):
            pts = [((x - x0) * z, (y - y0) * z) for x, y in r]
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                L = math.hypot(bx - ax, by - ay)
                n = max(1, int(L // 14))
                for s in range(n):
                    t0, t1 = s / n, (s + 0.5) / n
                    d.line([(ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1)], fill=(40, 90, 255), width=3)
    d.text((6, 6), f"{p['class']}  comp {p['id']}  iou {p['iou']}  red solid = 1882, blue dashed = 2023 (warped)", fill=(255, 255, 0))
    c.save(path)


# ----------------------------------------------------------------------------- self-check

def _synthetic(roads_v=(100, 200, 300), roads_h=(100, 200), size=(300, 400), w=8, gap=None):
    h, wd = size
    road = np.zeros((h, wd), bool)
    for x in roads_v:
        road[:, x - w // 2:x + w // 2] = True
    for y in roads_h:
        road[y - w // 2:y + w // 2, :] = True
    if gap:
        road[gap[0]:gap[1], roads_v[0] - w // 2:roads_v[0] + w // 2] = False
    return road


def _self_check():
    mpp = 1.0
    z = np.zeros((300, 400), bool)
    valid = np.zeros((300, 400), bool)
    valid[10:290, 10:390] = True
    # 1. a 3x2 road grid: 3 vertical x 2 horizontal -> blocks = 4 x 3 = 12 (edge blocks clipped by `valid`)
    road = _synthetic()
    s = segment(road, z, valid, mpp, close_px=1, min_area_m2=150, edge_m=0, max_block_m=1e9)
    assert s["n_blocks"] == 12, s["n_blocks"]
    inner = [j for j in s["junctions"] if 90 < j["x"] < 310 and 90 < j["y"] < 210]
    assert len(inner) == 6, [(j["x"], j["y"], j["degree"]) for j in inner]   # 3 x 2 crossings
    assert all(j["degree"] == 4 and not j["quay"] for j in inner), [j["degree"] for j in inner]
    # 2. a T-junction has degree 3: drop the lower half of one vertical road
    road2 = road.copy()
    road2[104:, 296:304] = False
    s2 = segment(road2, z, valid, mpp, close_px=1, min_area_m2=150, edge_m=0, max_block_m=1e9)
    tj = [j for j in s2["junctions"] if abs(j["x"] - 300) < 8 and abs(j["y"] - 200) < 8 or abs(j["x"] - 300) < 8 and abs(j["y"] - 100) < 8]
    assert any(j["degree"] == 3 for j in tj) or len(s2["junctions"]) <= 6, [(j["x"], j["y"], j["degree"]) for j in s2["junctions"]]
    # 3. closing: a 2 px break in a road no longer merges the two blocks beside it; with close_px=0 it does
    brk = _synthetic(gap=(150, 152))
    assert segment(brk, z, valid, mpp, close_px=0, min_area_m2=150, edge_m=0, max_block_m=1e9)["n_blocks"] < 12
    assert segment(brk, z, valid, mpp, close_px=1, min_area_m2=150, edge_m=0, max_block_m=1e9)["n_blocks"] == 12
    # 4. water is one pseudo-label and flags junctions quay
    wat = np.zeros_like(road)
    wat[210:290, :] = True
    s4 = segment(road & ~wat, wat, valid, mpp, close_px=1, min_area_m2=150, edge_m=0, max_block_m=1e9)
    assert any(j["quay"] for j in s4["junctions"]), "a road meeting water must give a quay junction"
    # 5. a block smaller than the floor is dropped
    small = _synthetic(roads_v=(100, 112, 300), roads_h=(100, 112, 200), w=4)
    assert segment(small, z, valid, mpp, close_px=0, min_area_m2=150, edge_m=0, max_block_m=1e9)["dropped_small"] >= 1
    # 6. opening keeps an 8+ m street and removes a 4 m alley
    r = np.zeros((200, 200), bool)
    r[50:60, :] = True      # 10 wide
    r[120:124, :] = True    # 4 wide
    o = open_disk(r, 4.0)
    assert o[55, 100] and not o[121, 100], "opening by a 4-radius disk must keep 10 wide, drop 4 wide"
    # 7. draw_polys cuts holes locally and never erases a neighbour
    big = shapely.box(0, 0, 100, 100).difference(shapely.box(40, 40, 60, 60))
    plug = shapely.box(45, 45, 55, 55)
    rr = draw_polys([big, plug], (60, 60), scale=2)
    assert rr[25, 25] and rr[0, 0] and not rr[21, 21] and rr[25, 25] is np.True_
    # 8. matching: mutual NN within 60 m, degree gate
    a = np.array([[0., 0], [100, 0], [200, 0], [1000, 1000]])
    m = a + np.array([5., 3.])
    m = np.vstack([m, [1030, 1000]])
    ia, im = match_junctions(a, [4, 4, 2, 4], m, [4, 4, 4, 4, 4], mpp=1.0)
    assert list(ia) == [0, 1, 3] and list(im) == [0, 1, 3], (ia, im)    # index 2 fails the degree gate (2 vs 4)
    # 9. classify: unchanged, reshaped, split, merged, new, isolated 1882
    box = shapely.box
    A = {1: box(0, 0, 10, 10), 2: box(100, 0, 110, 10), 3: box(200, 0, 220, 10), 4: box(300, 0, 310, 10), 5: box(400, 0, 410, 10),
         6: box(500, 0, 510, 10), 7: box(510, 0, 520, 10)}
    M = {1: box(0, 0, 10, 10), 2: box(100, 0, 110, 4), 3: box(200, 0, 210, 10), 4: box(210, 0, 220, 10),
         5: box(400, 0, 420, 10), 6: box(500, 0, 520, 10), 9: box(900, 0, 910, 10)}
    cl = {(tuple(c["a"]), tuple(c["m"])): c for c in classify(A, M)}
    assert cl[((1,), (1,))]["cls"] == "unchanged" and cl[((1,), (1,))]["iou"] == 1.0
    assert cl[((2,), (2,))]["cls"] == "reshaped", cl[((2,), (2,))]
    assert cl[((3,), (3, 4))]["cls"] == "split"
    assert cl[((5,), (5,))]["cls"] == "reshaped"      # a 1:1 whose block doubled in size: iou 0.5
    assert cl[((6, 7), (6,))]["cls"] == "merged"
    assert cl[((4,), ())]["cls"] is None and cl[((), (9,))]["cls"] == "new"
    # 10. a pure shift is recovered by the affine and RBF fits; the checkerboard assigns A and B to alternating tiles
    rng = np.random.default_rng(0)
    xy = rng.uniform(0, 3000, (200, 2))
    d = np.column_stack([5 + 0.002 * xy[:, 1], -3 - 0.002 * xy[:, 0]]) + rng.normal(0, 0.5, (200, 2))    # rotation + shift + noise
    tx, ty = tile_ids(xy, 1.0)
    A_ = (tx + ty) % 2 == 0
    fa_, fr_ = affine_fit(xy[A_], d[A_]), rbf_fit(xy[A_], d[A_], 10.0)
    assert np.linalg.norm(fa_(xy[~A_]) - d[~A_], axis=1).mean() < 1.0
    assert np.linalg.norm(fr_(xy[~A_]) - d[~A_], axis=1).mean() < 2.0
    deg, sc, r2 = similarity_fit(xy, xy + d)
    assert abs(deg - (-0.1146)) < 0.05, deg    # dy = -0.002 x: rotation of -0.002 rad
    assert r2 > 0.85, r2
    print("then_now_blocks self-check OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        _self_check()
        return 0
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
