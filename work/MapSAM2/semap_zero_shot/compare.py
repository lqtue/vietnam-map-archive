#!/usr/bin/env python3
"""Check step for the Semap zero-shot test on the 1882 sheet (tiles t01 and t06).

Three jobs, one file. Everything reads the database READ-ONLY with the public anon key (GET only;
the service key is never read, nothing is written). The reserved test windows R1 and R2 and the
held-out windows are never fetched, drawn or scored: a tile that touches one is refused, and every
fetched page is cut down to the rows that touch the chosen tiles before anything else sees it.

1. --agree   How much the Semap class map and the colour pass agree. No human reference needed.
             Colour pass = footprints rows with source 'import' and run 'colour-20260919' that are
             not rejected. Reports pixel agreement and IoU for
               (a) colour-pass blocks (land_plot rows dissolved, as export_tiles.py does) vs
                   Semap "not road and not water";
               (b1) colour-pass building rows vs Semap built;
               (b2) colour-pass built lots (a land_plot row with a colour-pass building inside it)
                    vs Semap built.
             Semap "built" means a built-up LOT, not a house (the zero-shot README), so (b1) is low
             by construction; (b2) is the fair comparison. Also writes a four-colour disagreement
             map per tile and kind, a shift search (alignment check), and, if the other agent's
             blocks_<tile>.geojson / lots_<tile>.geojson exist under <work>/post/, a review queue:
             each Semap polygon with its best-match IoU against the colour pass and a flag, agreed
             shapes first.

2. --score   The scoring harness, the same for every contender (colour pass, Semap, MapSAM2, U-Net).
             Reference = OWNER-APPROVED footprints rows inside the tile (review_status 'approved';
             'verified' is the old footprint_submissions word, not a footprints one: mig 055,
             src/lib/core/review/status.ts). The number is the one behind the 0.355 bar: for each
             reference polygon the best IoU over all predictions, then the mean, median, and counts
             at IoU >= 0.5 and >= 0.3 (work/image-processing/scripts/seg_eval.py `score`).
             Prediction: --pred-cls <Semap class png>, --pred-geojson <file>, or --pred-colour-pass.

3. --ref-count   How many approved reference rows exist in the tiles now, by type and source.

    python compare.py --agree --work <scratchpad>/semap
    python compare.py --ref-count
    python compare.py --score --tile t01 --pred-cls <t01 class png>      # later, not yet
    python compare.py --self-check                                       # no network

THE 0.355 BAR. Recorded in docs/ROADMAP.md (`colour-blocks`, ~line 548) and
docs/journals/260919-seg-audit.md (W6 table, building mean IoU 0.122 -> 0.355, median 0.314); the
all-predictions setting and the stricter building-only row (0.275) are in
docs/journals/261001-1882-layer-review.md. Measured by seg_eval.py `score`: best-match polygon IoU
per reference polygon, on the 17 volunteer `building` traces of the WHOLE 1882 sheet, against ALL
colour-pass polygons (a parcel can score as a building). So the definition here matches and the
sample does not: a t01/t06 approved-reference score is a different reference set, and is not a
like-for-like against 0.355 until the sets are put side by side.

CIRCULARITY. Approving a colour-pass row as it is makes it a reference row; the colour pass then
scores 1.0 on it. The harness therefore reports reference rows in two lines: `independent` (source
is not 'import': volunteer drawings and the owner's drawn replacements) and `all approved`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "work" / "MapSAM2" / "tiles_1882"))
sys.path.insert(0, str(REPO / "work" / "image-processing" / "scripts"))
import export_tiles as ET  # noqa: E402  (top level imports numpy and PIL only)
import seg_eval  # noqa: E402  (its heavy imports are inside functions)

MAP_ID = "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b"
TILE_IDS = ("t01", "t06")  # the two validation tiles; nothing else is allowed
COLOUR_RUN = "colour-20260919"
BAR = 0.355  # colour pass, building, best-match mean IoU: see the module docstring
CLS = {"background": 0, "contours": 1, "built": 2, "non_built": 3, "water": 4, "road": 5}
MIN_COMPONENT_PX = 30  # ignore specks when turning a class map into polygons
AGREE_IOU = 0.5  # a Semap shape "agrees" with the colour pass at or above this best-match IoU
SEMAP_ONLY_COVER = 0.2  # below this share of the shape under colour-pass land, the colour pass found nothing there

# four colours for the disagreement map (RGB), picked to stay apart for common colour blindness
C_BOTH = (0, 158, 115)  # agree, positive
C_NEITHER = (235, 235, 235)  # agree, negative (drawn faded)
C_SEMAP = (230, 159, 0)  # Semap only
C_COLOUR = (204, 121, 167)  # colour pass only


# ── pure maths (no I/O) ──────────────────────────────────────────────────────


def pixel_stats(cp: np.ndarray, sm: np.ndarray) -> dict:
    """Agreement and IoU between two boolean masks of one shape (cp = colour pass, sm = Semap)."""
    cp, sm = cp.astype(bool), sm.astype(bool)
    assert cp.shape == sm.shape
    both = int((cp & sm).sum())
    cp_only = int((cp & ~sm).sum())
    sm_only = int((~cp & sm).sum())
    neither = int((~cp & ~sm).sum())
    union = both + cp_only + sm_only
    n = cp.size
    return {
        "agree_both": both, "agree_neither": neither, "semap_only": sm_only, "colour_only": cp_only,
        "pixel_agreement": (both + neither) / n,
        "iou": both / union if union else float("nan"),
        "colour_share": float(cp.mean()), "semap_share": float(sm.mean()),
    }


def shift_search(cp: np.ndarray, sm: np.ndarray, r: int = 8) -> dict:
    """IoU of cp against sm with cp moved by (dx, dy) in [-r, r]. The block IoU surface is flat (big blocks, kerb margins differ),
    so a best shift only counts as misalignment when it gains 0.01 IoU over (0, 0); a wrong crop gains far more."""
    cp, sm = cp.astype(bool), sm.astype(bool)
    h, w = cp.shape
    best, at0 = (-1.0, 0, 0), float("nan")
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            a = cp[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
            b = sm[max(0, dy):h - max(0, -dy), max(0, dx):w - max(0, -dx)]
            u = int((a | b).sum())
            v = int((a & b).sum()) / u if u else 0.0
            if (dx, dy) == (0, 0):
                at0 = v
            if v > best[0]:
                best = (v, dx, dy)
    return {"best_iou": best[0], "best_dx": best[1], "best_dy": best[2], "iou_at_0": at0, "aligned": best[0] - at0 < 0.01}


def clip_to_box(geoms: list, box) -> list:
    from shapely.geometry import box as sbox

    tb = sbox(box[0], box[1], box[0] + box[2], box[1] + box[3])
    out = []
    for g in geoms:
        c = g.intersection(tb)
        if c.is_empty:
            continue
        out += [p for p in (c.geoms if hasattr(c, "geoms") else [c]) if p.geom_type == "Polygon" and p.area > 0]
    return out


def to_poly(ring):
    from shapely.geometry import Polygon

    if not ring or len(ring) < 3:
        return None
    p = Polygon(ring)
    if not p.is_valid:
        p = p.buffer(0)
    return None if p.is_empty else p


def raster_geoms(geoms: list, box) -> np.ndarray:
    """Boolean mask (h, w) of full-sheet-pixel shapes, in tile coordinates. Holes stay holes.
    PIL draws, so this needs no cv2."""
    x0, y0, w, h = box
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    for g in geoms:
        for p in (g.geoms if hasattr(g, "geoms") else [g]):
            if p.geom_type != "Polygon" or p.is_empty:
                continue
            d.polygon([(x - x0, y - y0) for x, y in p.exterior.coords], fill=255)
            for hole in p.interiors:
                d.polygon([(x - x0, y - y0) for x, y in hole.coords], fill=0)
    return np.array(im) > 0


def best_match(shape, others: list) -> float:
    return max((seg_eval.iou(shape, o) for o in others), default=0.0)


def cover_share(shape, mask_geom) -> float:
    return shape.intersection(mask_geom).area / shape.area if shape.area > 0 and mask_geom is not None else 0.0


def flag_polygon(shape, cp_polys: list, cp_union) -> dict:
    """Agreement of one Semap polygon with the colour pass, for the review queue.

    best_iou  best-match IoU against the colour-pass polygons of the same kind
    cover     share of the Semap polygon that lies under any colour-pass land
    flag      agreed      best_iou >= 0.5: the two drew about the same shape
              semap_only  cover < 0.2: the colour pass drew nothing here
              disagree    cover is high but the outline differs (split, merged, shifted, extra margin)
    """
    b = best_match(shape, cp_polys)
    c = cover_share(shape, cp_union)
    flag = "agreed" if b >= AGREE_IOU else ("semap_only" if c < SEMAP_ONLY_COVER else "disagree")
    return {"cp_best_iou": round(b, 3), "cp_cover": round(c, 3), "flag": flag}


FLAG_ORDER = {"agreed": 0, "disagree": 1, "semap_only": 2}


def rank_queue(features: list[dict]) -> list[dict]:
    """Agreed shapes first (highest IoU first), then disagreements (closest first), then Semap-only."""
    out = sorted(features, key=lambda f: (FLAG_ORDER[f["properties"]["flag"]], -f["properties"]["cp_best_iou"]))
    for i, f in enumerate(out):
        f["properties"]["queue_rank"] = i + 1
    return out


def mask_to_polygons(mask: np.ndarray, box, min_px: int = MIN_COMPONENT_PX) -> list:
    """Connected components of a boolean mask as shapely polygons in full-sheet pixel coordinates.

    cv2 traces the outermost pixel indices, which would shrink every shape by half a pixel on each
    side; a 0.5 px mitred buffer and a +0.5 shift put the edge back on the pixel border. Imports cv2 lazily (the self-check avoids it)."""
    import cv2
    from shapely.geometry import Polygon

    m = np.ascontiguousarray(mask.astype(np.uint8))
    cnts, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    if hier is None:
        return out
    hier = hier[0]
    for i, c in enumerate(cnts):
        if hier[i][3] != -1 or len(c) < 3:
            continue
        holes = []
        j = hier[i][2]
        while j != -1:
            if len(cnts[j]) >= 3:
                holes.append(cnts[j][:, 0, :].astype(float))
            j = hier[j][0]
        p = Polygon(c[:, 0, :].astype(float), holes)
        if not p.is_valid:
            p = p.buffer(0)
        p = p.buffer(0.5, join_style=2)
        if p.is_empty or p.area < min_px:
            continue
        for q in (p.geoms if hasattr(p, "geoms") else [p]):
            if q.geom_type == "Polygon":
                out.append(_shift(q, box[0] + 0.5, box[1] + 0.5))  # cv2 index i is the pixel [i, i+1]
    return out


def _shift(poly, dx, dy):
    from shapely import affinity

    return affinity.translate(poly, dx, dy)


def semap_masks(cls: np.ndarray) -> dict:
    """The masks compared and scored, from a Semap class map (0 bg, 1 contours, 2 built, 3 non-built,
    4 water, 5 road). land = not road and not water (the brief's definition: contour lines and the
    rare background pixel count as land). lots = built or non-built pixels, which the contour lines
    cut into lots; blocks = land."""
    road_or_water = (cls == CLS["road"]) | (cls == CLS["water"])
    return {
        "land": ~road_or_water,
        "built": cls == CLS["built"],
        "lots": (cls == CLS["built"]) | (cls == CLS["non_built"]),
    }


def built_lots(lots: list, buildings: list) -> list:
    """Colour-pass lots that hold at least one colour-pass building (the building's centroid inside)."""
    pts = [b.representative_point() for b in buildings]
    return [lot for lot in lots if any(lot.contains(p) for p in pts)]


# ── reading the database (anon key, GET only) ────────────────────────────────


def _env_candidates(explicit: str | None) -> list[Path]:
    c = [Path(explicit)] if explicit else []
    c.append(REPO / ".env")
    if REPO.parent.name == "worktrees":  # a git worktree under <main>/.claude/worktrees/<name>
        c.append(REPO.parents[2] / ".env")
    return c


def load_anon(explicit: str | None = None) -> tuple[str, str]:
    """(url, anon key). Reads only those two names from the .env file: nothing else is parsed
    into memory, and the service key is never touched."""
    for p in _env_candidates(explicit):
        if not p.is_file():
            continue
        got = {}
        for line in p.read_text().splitlines():
            m = re.match(r"\s*(PUBLIC_SUPABASE_URL|PUBLIC_SUPABASE_ANON_KEY)\s*=\s*(.*?)\s*$", line)
            if m:
                got[m.group(1)] = m.group(2).strip("'\"")
        if len(got) == 2:
            return got["PUBLIC_SUPABASE_URL"].rstrip("/"), got["PUBLIC_SUPABASE_ANON_KEY"]
    raise SystemExit("PUBLIC_SUPABASE_URL / PUBLIC_SUPABASE_ANON_KEY not found in any .env candidate (use --env)")


def keep_rows(rows: list[dict], boxes: list) -> list[dict]:
    """Rows whose polygon really intersects one of the tile boxes (bounding boxes first, then exact)."""
    from shapely.geometry import box as sbox

    out = []
    for r in rows:
        p = to_poly(r.get("pixel_polygon"))
        if p is None:
            continue
        if any(p.intersects(sbox(b[0], b[1], b[0] + b[2], b[1] + b[3])) for b in boxes):
            out.append(r)
    return out


def fetch_rows(boxes: list, env: str | None = None) -> list[dict]:
    import requests

    url, key = load_anon(env)
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    sel = "id,pixel_polygon,feature_type,review_status,source,run_id"
    out: list[dict] = []
    offset = 0
    while True:  # GET only; pages are cut to the tiles at once
        r = requests.get(f"{url}/rest/v1/footprints?map_id=eq.{MAP_ID}&select={sel}&order=id&limit=1000&offset={offset}",
                         headers=headers, timeout=60)
        r.raise_for_status()
        page = r.json()
        out += keep_rows(page, boxes)
        offset += len(page)
        if len(page) < 1000:
            return out


def tile_boxes(ids) -> dict:
    """{id: box} for the chosen validation tiles, refusing any that touch a window we must not touch."""
    cfg = json.loads(ET.TILES_JSON.read_text())
    wins = ET.load_windows()
    res = {}
    for t in cfg["tiles"]:
        if t["id"] not in ids:
            continue
        if t["id"] not in TILE_IDS or t["split"] != "val":
            raise SystemExit(f"{t['id']} is not one of the validation tiles {TILE_IDS}")
        hit = ET.check_tile(t["box"], wins)
        if hit["heldout"] or hit["other"]:
            raise SystemExit(f"{t['id']} touches a window it must not touch: {hit['heldout'] + hit['other']}")
        for r in cfg["reserved_test"]:
            if ET.boxes_hit(t["box"], r["box"]):
                raise SystemExit(f"{t['id']} touches reserved test window {r['id']}")
        res[t["id"]] = list(t["box"])
    missing = set(ids) - set(res)
    if missing:
        raise SystemExit(f"unknown tile(s): {sorted(missing)}")
    return res


# ── rows → shapes ────────────────────────────────────────────────────────────


def is_colour(r: dict) -> bool:
    return r.get("source") == "import" and r.get("run_id") == COLOUR_RUN and r.get("review_status") != "rejected"


def colour_shapes(rows: list[dict]) -> dict:
    """Colour-pass shapes by kind: lots (land_plot rows), buildings, blocks (lots dissolved, gap 10)."""
    lots = [p for r in rows if is_colour(r) and r["feature_type"] == "land_plot" and (p := to_poly(r["pixel_polygon"]))]
    blds = [p for r in rows if is_colour(r) and r["feature_type"] == "building" and (p := to_poly(r["pixel_polygon"]))]
    return {"lots": lots, "buildings": blds, "blocks": ET.dissolve_blocks(lots), "built_lots": built_lots(lots, blds)}


def reference_rows(rows: list[dict]) -> list[dict]:
    """Owner-approved rows. Volunteer domains over MAX_PLOT_PX2 are not lots and are dropped, as the exporter does."""
    out = []
    for r in rows:
        if r.get("review_status") != "approved":
            continue
        p = to_poly(r["pixel_polygon"])
        if p is None:
            continue
        if r["feature_type"] == "land_plot" and p.area > ET.MAX_PLOT_PX2 and r.get("source") != "import":
            continue
        out.append(r)
    return out


def ref_counts(rows: list[dict]) -> dict:
    c: dict = {}
    for r in reference_rows(rows):
        k = f"{r['feature_type']} / {r.get('source')}"
        c[k] = c.get(k, 0) + 1
    return c


# ── scoring harness ──────────────────────────────────────────────────────────


def score_set(ref: list, preds: list) -> dict:
    """seg_eval.score: best IoU per reference polygon, mean, median, at 0.5, at 0.3, cover. Same definition as 0.355."""
    return seg_eval.score(ref, preds) if ref else {"n_gt": 0}


def build_refs(rows: list[dict], box, independent_only: bool) -> dict:
    """Reference shapes by type, clipped to the tile: building, land_plot, block (approved lots dissolved)."""
    sel = [r for r in reference_rows(rows) if not (independent_only and r.get("source") == "import")]
    by = {"building": [], "land_plot": []}
    for r in sel:
        if r["feature_type"] in by:
            by[r["feature_type"]].append(to_poly(r["pixel_polygon"]))
    ref = {k: clip_to_box(v, box) for k, v in by.items()}
    ref["block"] = clip_to_box(ET.dissolve_blocks(by["land_plot"]), box) if by["land_plot"] else []
    return ref


def score_prediction(rows: list[dict], box, pred: dict) -> dict:
    """pred = {'building': [...], 'lot': [...], 'block': [...]} in full-sheet pixels (any may be empty).
    For each reference type and each of the two reference lines (independent / all approved):
    `all` scores against every prediction (the setting behind the 0.355), `typed` against the
    natural kind only (building->building, land_plot->lot, block->block)."""
    allp = clip_to_box([g for v in pred.values() for g in v], box)
    typed = {"building": "building", "land_plot": "lot", "block": "block"}
    out = {}
    for line, indep in (("independent", True), ("all_approved", False)):
        refs = build_refs(rows, box, indep)
        out[line] = {t: {"all": score_set(refs[t], allp), "typed": score_set(refs[t], clip_to_box(pred.get(typed[t], []), box))}
                     for t in ("building", "land_plot", "block")}
    return out


def pred_from_cls(cls: np.ndarray, box) -> dict:
    m = semap_masks(cls)
    return {"building": mask_to_polygons(m["built"], box), "lot": mask_to_polygons(m["lots"], box), "block": mask_to_polygons(m["land"], box)}


def pred_from_geojson(path: Path) -> dict:
    from shapely.geometry import shape

    doc = json.loads(Path(path).read_text())
    out: dict = {"building": [], "lot": [], "block": []}
    for f in doc.get("features", []):
        g = shape(f["geometry"])
        g = g if g.is_valid else g.buffer(0)
        kind = (f.get("properties") or {}).get("kind") or (f.get("properties") or {}).get("feature_type") or ""
        kind = {"land_plot": "lot", "plot": "lot"}.get(kind, kind)
        out.setdefault(kind if kind in out else "lot", []).append(g)
    return out


def pred_from_colour(rows: list[dict]) -> dict:
    s = colour_shapes(rows)
    return {"building": s["buildings"], "lot": s["lots"], "block": s["blocks"]}


def fmt_score(s: dict) -> str:
    if not s.get("n_gt"):
        return "no reference polygons"
    return (f"n={s['n_gt']} mean {s['mean']:.3f} median {s['median']:.3f} "
            f">=0.5: {s['at50']} >=0.3: {s['at30']} cover {s['cover']:.2f}")


def run_score(args) -> int:
    boxes = tile_boxes([args.tile])
    box = boxes[args.tile]
    rows = fetch_rows([box], args.env)
    if args.pred_cls:
        pred = pred_from_cls(np.array(Image.open(args.pred_cls)), box)
    elif args.pred_geojson:
        pred = pred_from_geojson(args.pred_geojson)
    else:
        pred = pred_from_colour(rows)
    res = score_prediction(rows, box, pred)
    print(f"{args.tile}: reference rows by type/source: {ref_counts(rows) or 'none approved'}")
    print(f"  prediction polygons: " + ", ".join(f"{k} {len(clip_to_box(v, box))}" for k, v in pred.items()))
    print(f"  bar to beat: {BAR} (colour pass, building, sheet-wide, 17 traces): not like-for-like, see the docstring")
    for line, per in res.items():
        print(f"  reference = {line}")
        for t, d in per.items():
            print(f"    {t:<9} all-predictions: {fmt_score(d['all'])}")
            print(f"    {'':<9} typed          : {fmt_score(d['typed'])}")
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1))
    return 0


# ── the agreement report ─────────────────────────────────────────────────────


def disagreement_png(src: np.ndarray, cp: np.ndarray, sm: np.ndarray, outlines: list, box, title: str) -> Image.Image:
    base = (src.astype(float) * 0.35 + 255 * 0.65).astype(np.uint8)  # faded source
    img = base.copy()
    cp, sm = cp.astype(bool), sm.astype(bool)
    a = 0.55
    for mask, col in ((cp & sm, C_BOTH), (~cp & sm, C_SEMAP), (cp & ~sm, C_COLOUR)):
        img[mask] = ((1 - a) * base[mask] + a * np.array(col)).astype(np.uint8)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    for g in outlines:  # colour-pass outline: a misaligned input shows as a double edge
        for p in (g.geoms if hasattr(g, "geoms") else [g]):
            if p.geom_type == "Polygon":
                d.line([(x - box[0], y - box[1]) for x, y in p.exterior.coords], fill=(40, 40, 40), width=1)
    d.rectangle([0, 0, im.width, 40], fill=(255, 255, 255))
    d.text((6, 4), title, fill=(0, 0, 0))
    for i, (col, name) in enumerate(((C_BOTH, "both"), (C_SEMAP, "Semap only"), (C_COLOUR, "colour pass only"), (C_NEITHER, "neither (faded)"))):
        x = 6 + i * 165
        d.rectangle([x, 22, x + 14, 36], fill=col, outline=(0, 0, 0))
        d.text((x + 20, 24), name, fill=(0, 0, 0))
    return im


def queue_for_tile(tid: str, box, post: Path, cp: dict) -> dict:
    """Flag every Semap block/lot polygon found in post/<kind>s_<tile>.geojson against the colour pass."""
    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union

    out = {}
    cp_union = unary_union(cp["lots"]) if cp["lots"] else None
    for kind, cps in (("blocks", cp["blocks"]), ("lots", cp["lots"])):
        f = post / f"{kind}_{tid}.geojson"
        if not f.is_file():
            continue
        feats = []
        for ft in json.loads(f.read_text()).get("features", []):
            g = shape(ft["geometry"])
            g = g if g.is_valid else g.buffer(0)
            if g.is_empty:
                continue
            props = dict(ft.get("properties") or {})
            props.update(flag_polygon(g, cps, cp_union))
            feats.append({"type": "Feature", "properties": props, "geometry": mapping(g)})
        feats = rank_queue(feats)
        counts = {k: sum(1 for x in feats if x["properties"]["flag"] == k) for k in FLAG_ORDER}
        # colour-pass shapes with no Semap match: the reverse disagreement
        semap_polys = [shape(x["geometry"]) for x in feats]
        miss = sum(1 for c in cps if best_match(c, semap_polys) < AGREE_IOU)
        out[kind] = {"n": len(feats), "flags": counts, "colour_pass_unmatched": miss, "colour_pass_n": len(cps), "features": feats}
    return out


def run_agree(args) -> int:
    work = Path(args.work)
    out = Path(args.out) if args.out else work / "compare"
    out.mkdir(parents=True, exist_ok=True)
    boxes = tile_boxes(TILE_IDS)
    rows = fetch_rows(list(boxes.values()), args.env)
    print(f"{len(rows)} footprint rows touch t01 or t06 (read-only, anon key)")
    summary: dict = {"bar": BAR, "tiles": {}}
    for tid, box in boxes.items():
        cls_p, src_p = work / "out" / f"1882_{tid}_s1_cls.png", work / "in" / f"1882_{tid}_s1.png"
        cls = np.array(Image.open(cls_p))
        src = np.array(Image.open(src_p).convert("RGB"))
        assert cls.shape == (box[3], box[2]) and src.shape[:2] == cls.shape, (tid, cls.shape, src.shape)
        trows = keep_rows(rows, [box])
        cp = colour_shapes(trows)
        sm = semap_masks(cls)
        masks = {
            "blocks": (raster_geoms(cp["blocks"], box), sm["land"], "(a) colour-pass blocks vs Semap not road/water"),
            "buildings": (raster_geoms(cp["buildings"], box), sm["built"], "(b1) colour-pass buildings vs Semap built"),
            "built_lots": (raster_geoms(cp["built_lots"], box), sm["built"], "(b2) colour-pass built lots vs Semap built"),
        }
        t: dict = {"box": box, "colour_pass_counts": {k: len(v) for k, v in cp.items()}, "reference_rows": ref_counts(trows)}
        for k, (a, b, title) in masks.items():
            t[k] = pixel_stats(a, b)
            outl = cp["blocks"] if k == "blocks" else (cp["buildings"] if k == "buildings" else cp["built_lots"])
            disagreement_png(src, a, b, outl, box, f"{tid} {title}").save(out / f"compare_{tid}_{k}.png")
        t["shift_blocks"] = shift_search(masks["blocks"][0], masks["blocks"][1])
        t["semap_class_share"] = {n: round(float((cls == i).mean()), 3) for n, i in CLS.items()}
        t["queue"] = {k: {kk: vv for kk, vv in v.items() if kk != "features"} for k, v in queue_for_tile(tid, box, work / "post", cp).items()}
        for kind, v in queue_for_tile(tid, box, work / "post", cp).items():
            (out / f"queue_{kind}_{tid}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": v["features"]}))
        summary["tiles"][tid] = t
        print(f"\n{tid} {box}  colour-pass shapes {t['colour_pass_counts']}  approved reference rows {t['reference_rows'] or 'none'}")
        for k in ("blocks", "buildings", "built_lots"):
            s = t[k]
            print(f"  {masks[k][2]:<52} agreement {s['pixel_agreement']:.3f}  IoU {s['iou']:.3f}  "
                  f"(both {s['agree_both']}, Semap-only {s['semap_only']}, colour-only {s['colour_only']})")
        sh = t["shift_blocks"]
        print(f"  alignment: best shift ({sh['best_dx']},{sh['best_dy']}) IoU {sh['best_iou']:.3f}, at (0,0) {sh['iou_at_0']:.3f}"
              f" -> {'ok' if sh['aligned'] else 'MISALIGNED, do not trust the numbers'}")
        for kind, q in t["queue"].items():
            print(f"  queue {kind}: {q['n']} Semap shapes, flags {q['flags']}, colour-pass shapes with no Semap match {q['colour_pass_unmatched']}/{q['colour_pass_n']}")
    (out / "agreement.json").write_text(json.dumps(summary, indent=1))
    print(f"\nwritten to {out}")
    return 0


def run_ref_count(args) -> int:
    boxes = tile_boxes(TILE_IDS)
    rows = fetch_rows(list(boxes.values()), args.env)
    for tid, box in boxes.items():
        trows = keep_rows(rows, [box])
        c = ref_counts(trows)
        indep = sum(v for k, v in c.items() if not k.endswith("/ import"))
        print(f"{tid}: approved reference rows {sum(c.values())} ({c or 'none'}); not from the colour pass: {indep}")
        print(f"     other rows here by status: " + str({s: sum(1 for r in trows if r['review_status'] == s) for s in sorted({r['review_status'] for r in trows})}))
    return 0


# ── self-check (no network) ──────────────────────────────────────────────────


def self_check() -> None:
    from shapely.geometry import Polygon, box as sbox

    sq = lambda x, y, w, h: Polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
    # pixel maths: 4x4 masks, 4 shared, 2 colour-only, 2 Semap-only, 8 neither
    a = np.zeros((4, 4), bool); b = np.zeros((4, 4), bool)
    a[0, :] = True; a[1, :2] = True          # 6 colour pixels
    b[0, :] = True; b[2, :2] = True          # 6 Semap pixels, 4 shared
    s = pixel_stats(a, b)
    assert (s["agree_both"], s["colour_only"], s["semap_only"], s["agree_neither"]) == (4, 2, 2, 8), s
    assert abs(s["iou"] - 4 / 8) < 1e-12 and abs(s["pixel_agreement"] - 12 / 16) < 1e-12
    assert pixel_stats(a, a)["iou"] == 1.0 and pixel_stats(a, ~a)["iou"] == 0.0 and pixel_stats(a, ~a)["pixel_agreement"] == 0.0
    # shift search: a block moved by (3, -2) is found at that shift; identical masks give (0, 0)
    base = np.zeros((60, 60), bool); base[20:40, 18:42] = True
    moved = np.roll(np.roll(base, 3, axis=1), -2, axis=0)
    ss = shift_search(base, moved)
    assert (ss["best_dx"], ss["best_dy"]) == (3, -2) and ss["best_iou"] > 0.99 and not ss["aligned"], ss
    assert shift_search(base, np.roll(base, 1, axis=1))["aligned"] is False and shift_search(base, base)["best_dx"] == 0
    assert shift_search(base, base)["aligned"] and shift_search(base, base)["iou_at_0"] == 1.0
    # rasterise: full-sheet coordinates land at tile coordinates, a hole stays a hole, outside is ignored
    box = (100, 200, 50, 40)
    sheet = sq(110, 210, 20, 10).union(sq(500, 500, 5, 5))
    r = raster_geoms([sheet], box)
    assert r.shape == (40, 50) and r[10:20, 10:30].all() and r.sum() == 21 * 11, int(r.sum())  # PIL fills the border pixel too
    holed = sq(100, 200, 30, 30).difference(sq(110, 210, 10, 10))
    rh = raster_geoms([holed], box)
    assert not rh[15, 15] and rh[5, 5] and rh[25, 25]
    # clip
    assert abs(clip_to_box([sq(90, 190, 30, 30)], box)[0].area - 20 * 20) < 1e-9 and clip_to_box([sq(0, 0, 5, 5)], box) == []
    # semap masks: land = not road, not water; built; lots = built or non-built
    cls = np.array([[0, 1, 2, 3], [4, 5, 2, 3]], np.uint8)
    m = semap_masks(cls)
    assert m["land"].tolist() == [[True, True, True, True], [False, False, True, True]]
    assert m["built"].tolist() == [[False, False, True, False], [False, False, True, False]]
    assert m["lots"].tolist() == [[False, False, True, True], [False, False, True, True]]
    # best match + the 0.355 definition (seg_eval.score): two refs, one hit exactly, one half overlapped
    ref = [sq(0, 0, 10, 10), sq(100, 0, 10, 10)]
    pred = [sq(0, 0, 10, 10), sq(100, 0, 5, 10), sq(500, 500, 3, 3)]
    sc = score_set(ref, pred)
    assert sc["n_gt"] == 2 and abs(sc["mean"] - (1.0 + 0.5) / 2) < 1e-12 and sc["at50"] == 2 and sc["at30"] == 2, sc
    assert score_set(ref, [])["mean"] == 0.0 and score_set([], pred) == {"n_gt": 0}
    # flags: same shape agrees; a shape with nothing under it is semap_only; an over-wide one is disagree
    cps = [sq(0, 0, 100, 100)]
    from shapely.ops import unary_union
    cu = unary_union(cps)
    assert flag_polygon(sq(0, 0, 100, 100), cps, cu)["flag"] == "agreed"
    assert flag_polygon(sq(300, 300, 50, 50), cps, cu) == {"cp_best_iou": 0.0, "cp_cover": 0.0, "flag": "semap_only"}
    wide = flag_polygon(sq(0, 0, 100, 25), cps, cu)  # a quarter slice: IoU 0.25, fully under colour land
    assert wide["flag"] == "disagree" and wide["cp_cover"] == 1.0 and wide["cp_best_iou"] == 0.25, wide
    fs = [{"properties": flag_polygon(g, cps, cu)} for g in (sq(300, 300, 5, 5), sq(0, 0, 100, 25), sq(0, 0, 100, 100), sq(0, 0, 100, 90))]
    q = rank_queue(fs)
    assert [f["properties"]["flag"] for f in q] == ["agreed", "agreed", "disagree", "semap_only"], [f["properties"] for f in q]
    assert q[0]["properties"]["cp_best_iou"] == 1.0 and [f["properties"]["queue_rank"] for f in q] == [1, 2, 3, 4]
    # built lots: a lot is built if a building centroid sits inside it
    assert built_lots([sq(0, 0, 10, 10), sq(20, 0, 10, 10)], [sq(2, 2, 3, 3)])[0].equals(sq(0, 0, 10, 10)) and len(built_lots([sq(0, 0, 10, 10), sq(20, 0, 10, 10)], [sq(2, 2, 3, 3)])) == 1
    # rows: reference words and filters
    P = lambda ft, st, src, poly, run=None: {"feature_type": ft, "review_status": st, "source": src, "run_id": run, "pixel_polygon": [list(p) for p in poly.exterior.coords][:-1]}
    rows = [
        P("building", "approved", "volunteer", sq(10, 10, 5, 5)),
        P("land_plot", "approved", "import", sq(0, 0, 40, 40), COLOUR_RUN),     # colour-pass row approved as-is
        P("land_plot", "approved", "volunteer", sq(0, 0, 900, 900)),            # a volunteer domain: dropped
        P("land_plot", "needs_review", "import", sq(70, 0, 20, 20), COLOUR_RUN),
        P("land_plot", "rejected", "import", sq(80, 0, 20, 20), COLOUR_RUN),
        P("building", "verified", "volunteer", sq(20, 20, 5, 5)),              # not a footprints word: ignored
    ]
    assert ref_counts(rows) == {"building / volunteer": 1, "land_plot / import": 1}, ref_counts(rows)
    cps_ = colour_shapes(rows)
    assert len(cps_["lots"]) == 2 and len(cps_["blocks"]) == 2 and len(cps_["buildings"]) == 0   # rejected and volunteer rows are not the colour pass
    rb = (0, 0, 100, 100)
    refs_i, refs_a = build_refs(rows, rb, True), build_refs(rows, rb, False)
    assert len(refs_i["building"]) == 1 and refs_i["land_plot"] == [] and len(refs_a["land_plot"]) == 1 and len(refs_a["block"]) == 1
    # a perfect prediction scores 1.0 on its own reference, the typed set and the all set
    res = score_prediction(rows, rb, {"building": [sq(10, 10, 5, 5)], "lot": [sq(0, 0, 40, 40)], "block": []})
    assert res["independent"]["building"]["typed"]["mean"] == 1.0 and res["all_approved"]["land_plot"]["typed"]["mean"] == 1.0
    assert res["independent"]["land_plot"]["all"] == {"n_gt": 0}
    # row filter keeps rows that touch a tile and nothing else
    kept = keep_rows([P("building", "approved", "volunteer", sq(10, 10, 5, 5)), P("building", "approved", "volunteer", sq(5000, 5000, 5, 5))], [(0, 0, 100, 100)])
    assert len(kept) == 1
    # the guard: a tile on a reserved window is refused, the two validation tiles are fine
    assert set(tile_boxes(TILE_IDS)) == {"t01", "t06"}
    assert ET.boxes_hit([4760, 4790, 600, 600], [4800, 4800, 10, 10])
    for bad in ("t02", "t05"):
        try:
            tile_boxes([bad]); raise AssertionError("training tile accepted")
        except SystemExit:
            pass
    # the .env reader takes the two public names only
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / ".env"
        p.write_text("SUPABASE_SERVICE_KEY=secret\nPUBLIC_SUPABASE_URL=https://x.example/\nPUBLIC_SUPABASE_ANON_KEY='anon'\n")
        assert load_anon(str(p)) == ("https://x.example", "anon")
    # class map -> polygons needs cv2; the PNG-to-polygon step is skipped where it is absent
    try:
        import cv2  # noqa: F401
    except ImportError:
        print("self-check: cv2 missing, mask_to_polygons not exercised")
    else:
        c = np.zeros((60, 80), np.uint8)
        c[10:30, 10:30] = CLS["built"]; c[10:30, 31:60] = CLS["non_built"]; c[40:50, 5:75] = CLS["road"]
        pg = pred_from_cls(c, (1000, 2000, 80, 60))
        assert len(pg["building"]) == 1 and abs(pg["building"][0].area - 400) < 1 and pg["building"][0].bounds == (1010, 2010, 1030, 2030), pg["building"][0].bounds
        assert len(pg["lot"]) == 2 and len(pg["block"]) == 1   # the 1 px gap is land, so the block is one piece
        # round trip: polygons of a mask rasterise back to the same mask
        back = raster_geoms(pg["lot"], (1000, 2000, 80, 60))
        assert (back == semap_masks(c)["lots"]).sum() >= 0.97 * back.size
    print("self-check: ok")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--self-check", action="store_true", help="synthetic arrays and polygons, no network")
    g.add_argument("--agree", action="store_true", help="Semap vs colour pass on t01 and t06, with maps and queues")
    g.add_argument("--score", action="store_true", help="score a prediction against the approved reference rows (later)")
    g.add_argument("--ref-count", action="store_true", help="count approved reference rows in t01 and t06")
    ap.add_argument("--work", help="folder with out/ (class pngs), in/ (source pngs) and optionally post/ (block and lot geojson)")
    ap.add_argument("--out", help="output folder (default <work>/compare)")
    ap.add_argument("--env", help=".env file holding PUBLIC_SUPABASE_URL and PUBLIC_SUPABASE_ANON_KEY")
    ap.add_argument("--tile", choices=TILE_IDS, help="tile for --score")
    ap.add_argument("--pred-cls", help="Semap class png for --score")
    ap.add_argument("--pred-geojson", help="prediction geojson (full-sheet pixels; property 'kind' = building|lot|block) for --score")
    ap.add_argument("--pred-colour-pass", action="store_true", help="score the colour pass itself with --score")
    ap.add_argument("--json", help="write the --score result here")
    a = ap.parse_args()
    if a.self_check:
        self_check()
        return 0
    if a.agree:
        if not a.work:
            ap.error("--agree needs --work")
        return run_agree(a)
    if a.score:
        if not a.tile or not (a.pred_cls or a.pred_geojson or a.pred_colour_pass):
            ap.error("--score needs --tile and one of --pred-cls, --pred-geojson, --pred-colour-pass")
        return run_score(a)
    return run_ref_count(a)


if __name__ == "__main__":
    sys.exit(main())
