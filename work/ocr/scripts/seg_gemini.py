#!/usr/bin/env python3
"""Segment a sheet with Gemini instead of SAM2, and score it the same way.

The question this exists to answer: SAM2 needs a box prompt per object, a GPU,
a LoRA checkpoint and a mask-to-polygon step, and it returns a nameless shape.
Gemini returns `box_2d`, a `label` and a **polygon** in one call, in the same
0-1000 space `ocr.py` already parses. If it scores anywhere near SAM2 on the
same ground truth, four dependencies leave the tree.

Two modes, because the interesting comparison is not one number:

    tiles   the whole sheet on a grid, like an OCR pass. Tests whether Gemini
            can find parcels at all, and where its density ceiling is.
    blocks  one call per city block from `modern_prior.py --blocks`. This is
            the within-block split — a few parcels per frame, which is the
            regime a VLM is good at and the one SAM2 measurably is not
            (0.160 mean IoU on `building`, at 0.98 coverage: the ink is found,
            the subdivision is not).

Scored by the same script as every SAM2 run, on the same 46 hand traces:

    python work/ocr/scripts/seg_gemini.py --map-id <uuid> --mode blocks --limit 40
    python <outputs>/seg-review/blockprior-20260910/score.py <out.json>

Self-check (no network, no key): python work/ocr/scripts/seg_gemini.py --self-check
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

MAP_1882 = "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b"

# Two things the docs get wrong about this model's output, both measured over
# 240 objects from real calls (2026-09-11):
#
#   `mask` is normalized to the **image**, not "inside the bounding box". The
#   box reading scores half as well on every metric and is kept only as an
#   escape hatch for a model that does it the documented way.
#
#   `box_2d` is **[xmin, ymin, xmax, ymax]**, not the documented
#   [ymin, xmin, ymax, xmax]. Mean IoU between a polygon's own bounding box and
#   its `box_2d` is 0.909 read as x-first and 0.284 read as y-first. Nothing
#   here depends on the box — the polygon is the answer — but a reader will
#   reach for it, and the transposed version looks plausible on a square crop.
#
# There used to be an `auto` that guessed per object. It guessed "box" for 107
# of 139 objects, because it was comparing against a transposed box, and the
# wrong guess reads as a weak model rather than as a bug. Deleted: a heuristic
# that can hide a coordinate fault is worse than a flag.
MASK_SPACES = ("image", "box")

SEG_SCHEMA = {
    "type": "object",
    "properties": {
        "objects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "box_2d": {"type": "array", "items": {"type": "number"}},
                    "mask": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "number"}},
                    },
                    "label": {"type": "string"},
                },
                "required": ["box_2d", "mask", "label"],
            },
        }
    },
    "required": ["objects"],
}

SYSTEM_PROMPT = (
    "You are reading a scan of a historical printed city map. Work only from "
    "the ink on the page: the drawn boundary lines, not what a modern city "
    "looks like. Outlines must follow the printed line, not a smoothed guess "
    "at it."
)

TILE_PROMPT = (
    "Give the segmentation masks for every distinct land parcel and building "
    "block outlined on this map tile.\n"
    'Output a JSON object with key "objects", a list where each entry has the '
    '2D bounding box in "box_2d", the segmentation mask in "mask", and the '
    'text label in "label".\n'
    "Use the parcel's own printed number or name as the label, or an empty "
    "string if it has none. Do not invent a name.\n"
    "Each parcel enclosed by its own boundary line is one object. Do not merge "
    "adjacent parcels into a block, and do not return the street between them."
)

BLOCK_PROMPT = (
    "This image is one city block from a historical cadastral map.\n"
    "Give the segmentation masks for each separate land parcel inside the "
    "block — the units the boundary lines divide it into.\n"
    'Output a JSON object with key "objects", a list where each entry has the '
    '2D bounding box in "box_2d", the segmentation mask in "mask", and the '
    'text label in "label".\n'
    "Use the parcel's own printed number or name as the label, or an empty "
    "string if it has none. Do not invent a name.\n"
    "If the block is not subdivided, return it as a single object. Do not "
    "return the streets around the block."
)


# ── geometry: Gemini's answer → source pixels ────────────────────────────────

def _bbox(points: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _iou_box(a: tuple, b: tuple) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / area if area > 0 else 0.0


def obj_polygon(
    obj: dict,
    img_w: int,
    img_h: int,
    crop: tuple[float, float, float, float],
    mask_space: str = "image",
) -> tuple[list[list[float]], str] | None:
    """One Gemini object → (polygon in source px, the space it was read in).

    `crop` is the region of the source image that was rendered, `(x, y, w, h)`
    in source pixels; `img_w`/`img_h` are the rendered image's own size. Gemini
    normalizes to what it was shown, so every coordinate passes through the
    render before it means anything on the sheet.

    Returns None for an object that cannot be a polygon — fewer than three
    points, or a degenerate box — rather than letting a sliver downstream.
    """
    if mask_space not in MASK_SPACES:
        raise ValueError(f"mask_space must be one of {MASK_SPACES}")

    pts = [p for p in (obj.get("mask") or []) if isinstance(p, (list, tuple)) and len(p) >= 2]
    if len(pts) < 3:
        return None

    box = obj.get("box_2d") or []
    if len(box) != 4:
        return None
    # 0-1000 in the rendered image, x first — see MASK_SPACES.
    bx0, by0, bx1, by1 = (float(v) for v in box)
    if bx1 <= bx0 or by1 <= by0:
        return None

    def as_image(p):
        return [p[0] / 1000.0 * img_w, p[1] / 1000.0 * img_h]

    def as_box(p):
        return [
            (bx0 + p[0] / 1000.0 * (bx1 - bx0)) / 1000.0 * img_w,
            (by0 + p[1] / 1000.0 * (by1 - by0)) / 1000.0 * img_h,
        ]

    space = mask_space
    conv = as_image if space == "image" else as_box
    cx, cy, cw, ch = crop
    sx, sy = cw / img_w, ch / img_h
    poly = [[cx + px * sx, cy + py * sy] for px, py in (conv(p) for p in pts)]
    return poly, space


# ── running ──────────────────────────────────────────────────────────────────

def block_crops(path: str, pad: int, limit: int | None) -> list[tuple[int, int, int, int]]:
    """`modern_prior --blocks` GeoJSON → padded crop rectangles, biggest first.

    Biggest first because a 20 px block is one tube house and tells the test
    nothing; the question is whether a block that holds several parcels comes
    back subdivided.
    """
    doc = json.load(open(path, encoding="utf-8"))
    crops = []
    for feat in doc.get("features") or []:
        geom = (feat or {}).get("geometry") or {}
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        pts: list[list[float]] = []
        stack = [geom.get("coordinates")]
        while stack:
            node = stack.pop()
            if not isinstance(node, (list, tuple)) or not node:
                continue
            if isinstance(node[0], (int, float)):
                pts.append([float(node[0]), float(node[1])])
            else:
                stack.extend(node)
        if len(pts) < 3:
            continue
        x0, y0, x1, y1 = _bbox(pts)
        crops.append((int(x0) - pad, int(y0) - pad,
                      int(x1 - x0) + 2 * pad, int(y1 - y0) + 2 * pad))
    crops.sort(key=lambda c: c[2] * c[3], reverse=True)
    return crops[:limit] if limit else crops


def gt_boxes(map_id: str) -> list[tuple[float, float, float, float]]:
    """Bounding boxes of the hand-traced footprints on a sheet, in source px.

    Only used to choose *which* blocks to spend a call on. A block test that
    picks the largest blocks on the sheet scores zero for an uninteresting
    reason — the ground truth is 46 polygons in a few districts, and the
    biggest blocks are somewhere else.
    """
    import requests
    url = os.environ["PUBLIC_SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    rows = requests.get(
        f"{url}/rest/v1/footprints",
        params={"select": "pixel_polygon", "map_id": f"eq.{map_id}"},
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30,
    ).json()
    out = []
    for r in rows:
        poly = r.get("pixel_polygon")
        if poly and len(poly) >= 3:
            out.append(_bbox([[float(p[0]), float(p[1])] for p in poly]))
    return out


def run(args: argparse.Namespace) -> int:
    from iiif_tiles import fetch_crop, get_image_info, get_iiif_base_from_supabase, tile_grid
    from gemini_client import DEFAULT_MODEL, extract_labels

    iiif_base = args.iiif_base or get_iiif_base_from_supabase(args.map_id)
    if not iiif_base:
        print(f"No IIIF source for {args.map_id}", file=sys.stderr)
        return 1
    info = get_image_info(iiif_base)
    width, height = int(info["width"]), int(info["height"])
    print(f"{width}x{height} source px")

    out_dir = Path(args.out).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    # `--no-cache` is how a repeat pass gets a second opinion rather than the
    # first one back. The model is not deterministic here — one crop returned
    # 18 objects and then 1 — so a comparison between two settings is only
    # readable against a repeat of one setting against itself.
    cache_dir = None if args.no_cache else out_dir / "cache"
    log_path = out_dir / "calls.jsonl"

    if args.mode == "blocks":
        if not args.blocks:
            print("--mode blocks needs --blocks <blocks.geojson>", file=sys.stderr)
            return 1
        crops = block_crops(args.blocks, args.pad, None)
        if args.near_gt:
            boxes = gt_boxes(args.map_id)
            crops = [c for c in crops
                     if any(_iou_box((c[0], c[1], c[0] + c[2], c[1] + c[3]), b) > 0
                            for b in boxes)]
            print(f"{len(crops)} blocks overlap one of {len(boxes)} hand traces")
        if args.limit:
            crops = crops[: args.limit]
        prompt = BLOCK_PROMPT
    else:
        region = None
        if args.region:
            region = tuple(int(v) for v in args.region.split(","))  # type: ignore[assignment]
        crops = list(tile_grid(width, height, tile=args.tile,
                               overlap=args.overlap, region=region))
        if args.limit:
            crops = crops[: args.limit]
        prompt = TILE_PROMPT

    # Clamp to the sheet: a padded block at the margin, or a grid cell on the
    # last row, can run past the edge, and the IIIF server answers a region it
    # does not have with a 400 rather than with what it does have.
    crops = [(max(0, x), max(0, y),
              min(w, width - max(0, x)), min(h, height - max(0, y)))
             for x, y, w, h in crops]
    crops = [c for c in crops if c[2] > 16 and c[3] > 16]
    print(f"{len(crops)} calls, mode {args.mode}, model {args.model or DEFAULT_MODEL}")

    polygons: list[dict] = []
    spaces: dict[str, int] = {}
    empty = 0
    for i, (x, y, w, h) in enumerate(crops, 1):
        # `--render 0` sends the block at its own size, capped. A block is
        # whatever size it is on the sheet, and rendering every one to 1024 px
        # asks a 1443 px block to subdivide detail that was resampled away
        # before the model saw it — the same ground-per-call fault the OCR side
        # spent a month on, one layer down.
        size = min(w, args.render_cap) if args.render <= 0 else args.render
        img = fetch_crop(iiif_base, x, y, w, h, size=size)
        result = extract_labels(
            image=img,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=SEG_SCHEMA,
            model=args.model or DEFAULT_MODEL,
            thinking=not args.no_thinking,
            log_path=log_path,
            cache_dir=cache_dir,
        )
        objs = result.get("objects") or []
        if not objs:
            empty += 1
        for obj in objs:
            got = obj_polygon(obj, img.width, img.height, (x, y, w, h), args.mask_space)
            if got is None:
                continue
            poly, space = got
            spaces[space] = spaces.get(space, 0) + 1
            polygons.append({
                "coords": poly,
                "label": (obj.get("label") or "").strip(),
                "crop": [x, y, w, h],
            })
        print(f"  [{i}/{len(crops)}] {x},{y} {w}x{h} → {len(objs)} objects "
              f"({len(polygons)} total)", flush=True)

    payload = {
        "polygons": polygons,
        "meta": {
            "map_id": args.map_id,
            "mode": args.mode,
            "model": args.model or DEFAULT_MODEL,
            "calls": len(crops),
            "empty_calls": empty,
            "render": args.render,
            "mask_space": args.mask_space,
            "mask_space_seen": spaces,
            "thinking": not args.no_thinking,
        },
    }
    Path(args.out).write_text(json.dumps(payload), encoding="utf-8")
    print(f"\n{len(polygons)} polygons → {args.out}")
    print(f"mask space read as: {spaces or 'n/a'}; {empty}/{len(crops)} calls returned nothing")
    return 0


# ── self-check ───────────────────────────────────────────────────────────────

def _self_check() -> None:
    # A square occupying the middle ninth of a 1000x500 render, described both
    # ways. Both readings must land on the same source pixels.
    box = [333, 333, 666, 666]                      # xmin, ymin, xmax, ymax
    image_pts = [[333, 333], [666, 333], [666, 666], [333, 666]]
    box_pts = [[0, 0], [1000, 0], [1000, 1000], [0, 1000]]
    crop = (0, 0, 1000, 500)

    a, sa = obj_polygon({"box_2d": box, "mask": image_pts}, 1000, 500, crop, "image")
    b, sb = obj_polygon({"box_2d": box, "mask": box_pts}, 1000, 500, crop, "box")
    assert (sa, sb) == ("image", "box")
    for p, q in zip(a, b):
        assert abs(p[0] - q[0]) < 1e-6 and abs(p[1] - q[1]) < 1e-6, (p, q)
    # ...and on the pixels arithmetic says: x 333/1000 of 1000, y of 500.
    assert abs(a[0][0] - 333.0) < 1e-6 and abs(a[0][1] - 166.5) < 1e-6, a[0]

    # Image is the default, because that is what the model measurably does.
    assert obj_polygon({"box_2d": box, "mask": image_pts}, 1000, 500, crop)[1] == "image"

    # box_2d is x-first. A non-square box is the only shape that can prove it:
    # read y-first, this one would place the polygon outside the crop.
    wide = [100, 400, 900, 600]                     # xmin, ymin, xmax, ymax
    poly = obj_polygon({"box_2d": wide, "mask": [[0, 0], [1000, 0], [1000, 1000]]},
                       1000, 500, crop, "box")[0]
    assert abs(poly[0][0] - 100.0) < 1e-6 and abs(poly[1][0] - 900.0) < 1e-6, poly
    assert abs(poly[0][1] - 200.0) < 1e-6, poly   # y 400/1000 of a 500px render

    # The crop offset is what puts a tile's answer on the sheet. Same object,
    # same render size, a tile 4000 px across the page: every point moves by
    # the tile origin and nothing else.
    off = obj_polygon({"box_2d": box, "mask": image_pts}, 1000, 500,
                      (4000, 2000, 1000, 500), "image")[0]
    for p, q in zip(a, off):
        assert abs(q[0] - p[0] - 4000) < 1e-6 and abs(q[1] - p[1] - 2000) < 1e-6

    # A render smaller than its crop scales back up — the usual case, since a
    # 2400 px tile is asked for at 1024.
    up = obj_polygon({"box_2d": box, "mask": image_pts}, 1000, 1000,
                     (0, 0, 2000, 2000), "image")[0]
    assert abs(up[0][0] - 666.0) < 1e-6, up[0]

    # Refusals: too few points, a zero-area box, a missing box, junk points.
    assert obj_polygon({"box_2d": box, "mask": [[0, 0], [1, 1]]}, 100, 100, crop) is None
    assert obj_polygon({"box_2d": [5, 5, 5, 9], "mask": image_pts}, 100, 100, crop) is None
    assert obj_polygon({"mask": image_pts}, 100, 100, crop) is None
    assert obj_polygon({"box_2d": box, "mask": [1, 2, 3]}, 100, 100, crop) is None

    # Blocks: biggest first, padded, and non-areal geometry skipped.
    import tempfile
    doc = {"type": "FeatureCollection", "features": [
        {"geometry": {"type": "Polygon", "coordinates":
            [[[100, 100], [140, 100], [140, 130], [100, 130], [100, 100]]]}},
        {"geometry": {"type": "Polygon", "coordinates":
            [[[0, 0], [500, 0], [500, 500], [0, 500], [0, 0]]]}},
        {"geometry": {"type": "LineString", "coordinates": [[0, 0], [9, 9]]}},
    ]}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "blocks.geojson")
        json.dump(doc, open(path, "w", encoding="utf-8"))
        crops = block_crops(path, pad=10, limit=None)
        assert len(crops) == 2, crops
        assert crops[0] == (-10, -10, 520, 520), crops[0]     # the big one leads
        assert crops[1] == (90, 90, 60, 50), crops[1]
        assert block_crops(path, pad=0, limit=1) == [(0, 0, 500, 500)]

    print("[ok] seg_gemini self-check passed")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--self-check", action="store_true")
    p.add_argument("--map-id", default=MAP_1882)
    p.add_argument("--mode", default="blocks", choices=["tiles", "blocks"])
    p.add_argument("--blocks", help="modern_prior.py --blocks output, for --mode blocks")
    p.add_argument("--region", help="x,y,w,h in source px, for --mode tiles")
    p.add_argument("--tile", type=int, default=2048)
    p.add_argument("--overlap", type=int, default=256)
    p.add_argument("--render", type=int, default=1024,
                   help="px width sent to the model; 0 = the crop's own width")
    p.add_argument("--no-cache", action="store_true",
                   help="re-ask the model instead of replaying a cached answer")
    p.add_argument("--render-cap", type=int, default=2048,
                   help="ceiling for --render 0")
    p.add_argument("--pad", type=int, default=24, help="px around a block crop")
    p.add_argument("--limit", type=int, default=40, help="cap the number of calls")
    p.add_argument("--mask-space", default="image", choices=list(MASK_SPACES))
    p.add_argument("--no-thinking", action="store_true",
                   help="ask for thinking_level=minimal, which the docs recommend here")
    p.add_argument("--model")
    p.add_argument("--iiif-base", help="skip the Supabase lookup")
    p.add_argument("--near-gt", action="store_true",
                   help="blocks mode: only blocks overlapping a hand trace, "
                        "so the calls land where the ground truth is")
    p.add_argument("--out", default="work/ocr/outputs/seg_gemini.json")
    args = p.parse_args()

    if args.self_check:
        _self_check()
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
