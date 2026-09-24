"""OCR extractions → SAM2 prompts (roadmap-record C4).

`inference_tiles_as_video.py --mode prompted` needs, for each tile, the boxes to
prompt SAM2 with. Those come from the OCR pass: a label sitting on the map is
evidence that *something* is there, and its box is a far better prompt than a
grid point.

Two functions, in the order the caller uses them:

    all_seeds = load_seeds_for_map(map_id, ocr_run_id)     # once, full image
    seeds     = seeds_for_tile(all_seeds, tile, render)    # per tile

A seed carries its label, so a polygon prompted by "Rue Catinat" can be written
with that name already attached — the join pass then only has to deal with
labels that never became a prompt (legend text, orphan numerals, linear
features whose label sits beside rather than inside them).

**OCR is not the only thing that can point at a block.** `modern_prior.py
--blocks` warps today's buildings into the sheet's own pixel grid and
buffer-dissolves them into blocks, and the block structure of a city is the
part that survives a century — so those polygons are prompts too:

    all_seeds = load_seeds_from_prior(path, map_id)        # once, full image
    seeds     = seeds_for_tile(all_seeds, tile, render)    # per tile, as above

They arrive nameless (`text` is ""), so nothing downstream stamps a name on
their polygons; what they buy is coverage, on sheets where OCR read a few
hundred labels over tens of thousands of blocks. `seeds_for_tile` and
everything past it cannot tell the two sources apart, which is the point — the
seed dict is the only contract.

Self-check (no network): python work/MapSAM2/to_sam2_seeds.py --self-check
"""

from __future__ import annotations

import json
import os
import sys

# Categories worth prompting with. A street name labels a line, not an area, so
# prompting a box around the text would segment the lettering's background
# rather than the street; those go through the join pass instead.
AREA_CATEGORIES = {
    "building",
    "place",
    "institution",
    "block",
    "land_plot",
    "water_body",
    "legend_ref",
    "number",
}

# `other` used to be in that set, and is the category a row with no category at
# all falls back to. Measured on the 1882 sheet's v1b run: 7 of 91 seeds were
# `other`, and they supplied 4 of the 10 worst masks by SAM2's own iou —
# including the two readings of a pencil shelfmark in the sheet margin, one of
# which produced the largest polygon of the whole run at 153,116 px. A category
# the OCR pass could not name is not evidence that an area is there.

# Below this, the OCR pass was guessing; a bad prompt costs a whole mask.
MIN_CONFIDENCE = 0.4

# The string `modern_prior.py` stamps on everything it writes. Its outputs are
# source pixels wearing GeoJSON's clothes, and GeoJSON's own default is WGS84
# lng/lat — so a file that does not carry this is either from somewhere else or
# from an older writer, and reading it as pixels would put every prompt a few
# hundred pixels into the top-left corner of the sheet with no error anywhere.
PRIOR_CRS = "source-pixels-y-down"


def tiling_crop(triage: dict | None) -> list[float] | None:
    """The rectangle worth reading on a sheet: `main_map`, else the neatline.

    Python twin of `tilingCrop` in `src/lib/data/maps/triageTypes.ts`, and the
    same precedence for the same reason — the neatline is the *printed border*,
    so a legend or a street index printed inside it is inside the neatline too.
    Kept in step with that file; `--self-check` pins the precedence.
    """
    if not triage:
        return None
    for r in triage.get("regions") or []:
        if r.get("category") == "main_map" and len(r.get("bbox") or []) == 4:
            return [float(v) for v in r["bbox"]]
    neatline = triage.get("neatline")
    if neatline and len(neatline) == 4:
        return [float(v) for v in neatline]
    return None


def clip_seeds_to(seeds: list[dict], crop: list[float] | None) -> list[dict]:
    """Drop seeds whose centroid falls outside `crop`. Pure.

    Everything printed outside the main map is furniture — title block, legend,
    scale bar, the printer's imprint, a pencil shelfmark — and a label read off
    any of it is not a place. On the 1882 sheet this removes 4 of 91 seeds and
    with them the three largest errors in the run.

    Centroid rather than intersection on purpose, matching how `seeds_for_tile`
    already assigns a straddling seed to exactly one owner.
    """
    if not crop:
        return seeds
    cx0, cy0, cw, ch = crop
    kept = []
    for s in seeds:
        px, py = s["centroid"]
        if cx0 <= px <= cx0 + cw and cy0 <= py <= cy0 + ch:
            kept.append(s)
    return kept


def fetch_tiling_crop(map_id: str) -> list[float] | None:
    """The saved crop for a map, or None when it has no triage yet."""
    import requests

    url = os.environ.get("PUBLIC_SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("PUBLIC_SUPABASE_ANON_KEY", "")
    resp = requests.get(
        f"{url}/rest/v1/maps",
        params={"id": f"eq.{map_id}", "select": "triage"},
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()
    return tiling_crop(rows[0].get("triage") if rows else None)


def load_seeds_for_map(map_id: str, ocr_run_id: str | None = None) -> list[dict]:
    """Fetch prompt-worthy extractions for a map as full-image px seeds.

    Rejected rows are excluded; a validated row's human corrections win over the
    model's original text, because that is the name the polygon will carry. Seeds
    outside the sheet's `main_map` are dropped — see `clip_seeds_to`.
    """
    import requests

    url = os.environ.get("PUBLIC_SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("PUBLIC_SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise EnvironmentError("Set PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY")

    params = {
        "map_id": f"eq.{map_id}",
        "select": "id,text,text_corrected,category,category_corrected,confidence,review_status,"
                  "global_x,global_y,global_w,global_h",
        "review_status": "neq.rejected",
    }
    if ocr_run_id:
        params["run_id"] = f"eq.{ocr_run_id}"

    resp = requests.get(
        f"{url}/rest/v1/ocr_labels",
        params=params,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=60,
    )
    resp.raise_for_status()
    seeds = rows_to_seeds(resp.json())

    crop = fetch_tiling_crop(map_id)
    if crop:
        before = len(seeds)
        seeds = clip_seeds_to(seeds, crop)
        if len(seeds) != before:
            print(f"  Clipped to main_map {[int(v) for v in crop]}: "
                  f"{before} → {len(seeds)} seeds")
    return seeds


def rows_to_seeds(rows: list[dict]) -> list[dict]:
    """Filter and normalise extraction rows into seeds. Pure — see the self-check."""
    seeds: list[dict] = []
    for row in rows:
        category = row.get("category_corrected") or row.get("category") or "other"
        if category not in AREA_CATEGORIES:
            continue
        # A validated row was looked at by a human, so its confidence is moot.
        if row.get("review_status") != "validated" and (row.get("confidence") or 0) < MIN_CONFIDENCE:
            continue
        x, y, w, h = (row.get("global_x"), row.get("global_y"),
                      row.get("global_w"), row.get("global_h"))
        if None in (x, y, w, h) or w <= 0 or h <= 0:
            continue

        seeds.append({
            "extraction_id": row.get("id"),
            "text": row.get("text_corrected") or row.get("text") or "",
            "category": category,
            "bbox": [float(x), float(y), float(w), float(h)],       # full-image px
            "centroid": [float(x) + float(w) / 2, float(y) + float(h) / 2],
        })
    return seeds


def _coord_bounds(coords) -> tuple[float, float, float, float] | None:
    """(minx, miny, maxx, maxy) over a GeoJSON coordinate array of any depth.

    Written by hand rather than through shapely because this module is imported
    on Colab beside the SAM2 checkpoint, where the only geometry dependency is
    numpy — `modern_prior.py` may hold shapely, its consumer must not have to.
    Depth is not assumed: a Polygon nests two deep and a MultiPolygon three, and
    both reduce to the same walk over positions.
    """
    if not coords:
        return None
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    stack = [coords]
    while stack:
        node = stack.pop()
        if not isinstance(node, (list, tuple)) or not node:
            continue
        if isinstance(node[0], (int, float)):
            x, y = float(node[0]), float(node[1])
            minx, maxx = min(minx, x), max(maxx, x)
            miny, maxy = min(miny, y), max(maxy, y)
        else:
            stack.extend(node)
    if minx > maxx:
        return None
    return minx, miny, maxx, maxy


def blocks_to_seeds(features: list[dict]) -> list[dict]:
    """A block prior's features → seeds, same shape as `rows_to_seeds`.

    Pure — see the self-check. A block is prompted by its own bounding box,
    which is what SAM2 is given here (`predictor.predict(box=...)`), so the
    polygon's ring is read only for its bounds and then dropped.

    ponytail: the ring is thrown away. A block is L- or U-shaped often enough
    that its box covers a chunk of the street beside it, and SAM2 gets the box
    either way. If prompts start bleeding into the roadway, the upgrade is a
    point prompt at the polygon's representative point alongside the box, which
    `seeds_for_tile` already carries a slot for.
    """
    seeds: list[dict] = []
    for feat in features or []:
        geom = (feat or {}).get("geometry") or {}
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        bounds = _coord_bounds(geom.get("coordinates"))
        if bounds is None:
            continue
        x0, y0, x1, y1 = bounds
        w, h = x1 - x0, y1 - y0
        # Same refusal as `rows_to_seeds`: a zero-width box is not a prompt, and
        # a dissolve can leave a sliver whose ring collapses to a line.
        #
        # ponytail: the floor is strictly zero, not a pixel. On the 1959 sheet
        # 21 of 13,037 blocks come back thinner than 1 px — buffer-shrink
        # residue, not buildings — and a quarter of them are under 16 px on a
        # side, which is one tube house rather than a block. Both are prompts
        # SAM2 will answer badly. The upgrade is a MIN_BLOCK_PX floor here, set
        # from a run's measured mask IoU rather than from taste.
        if w <= 0 or h <= 0:
            continue
        # A *modern* block does not name an 1882 one, which is why `text` is
        # empty and `category` was a constant. `colour_blocks.py` writes the
        # same contract but reads its classes off the sheet's own legend —
        # salmon is *propriétés particulières*, admin is *service local* — so
        # when the prior carries a `feature_type`, carry it through. It is the
        # only route by which C6's write-back can stamp a cadastral class on
        # what SAM2 returns; dropping it here made that unreachable.
        klass = ((feat or {}).get("properties") or {}).get("feature_type")
        seeds.append({
            "extraction_id": None,      # nothing in ocr_labels to point at
            "text": "",
            "category": str(klass) if klass else "block",
            "bbox": [x0, y0, w, h],     # full-image px, y-down
            "centroid": [x0 + w / 2, y0 + h / 2],
        })
    return seeds


def load_seeds_from_prior(path: str, map_id: str) -> list[dict]:
    """Read a `modern_prior --blocks` GeoJSON as seeds, clipped to `main_map`.

    The CRS is checked before anything else and the mismatch is fatal. This is
    a trust boundary, not a formality: the file is GeoJSON, GeoJSON means
    lng/lat unless told otherwise, and a Saigon lng/lat read as a pixel is
    (106.7, 10.8) — the top-left corner of every sheet in the corpus. Every
    prompt would land in one square of the title block and SAM2 would return
    masks for it, so nothing downstream would fail; the run would just be
    quietly worthless.
    """
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)

    crs = doc.get("crs")
    if crs != PRIOR_CRS:
        raise ValueError(
            f"{path}: crs is {crs!r}, expected {PRIOR_CRS!r}. This loader reads "
            f"source pixels; a lng/lat file would put every prompt off West "
            f"Africa. Regenerate with modern_prior.py --blocks."
        )

    seeds = blocks_to_seeds(doc.get("features") or [])
    crop = fetch_tiling_crop(map_id)
    if crop:
        before = len(seeds)
        seeds = clip_seeds_to(seeds, crop)
        if len(seeds) != before:
            print(f"  Clipped to main_map {[int(v) for v in crop]}: "
                  f"{before} → {len(seeds)} seeds")
    return seeds


def seeds_for_tile(
    seeds: list[dict],
    tile: tuple[int, int, int, int],
    render_size: int = 1024,
) -> list[dict]:
    """The seeds whose centroid falls in `tile`, in that tile's render coords.

    **This does not give one owner per seed.** The test is against the tile's
    full width, but a tiling steps by `tile - overlap`, so every centroid in an
    overlap band satisfies it for two neighbours and every centroid in a corner
    for four. Measured on the 1959 sheet at 1024/128: 13,037 seeds produced
    17,317 placements — 294 of them four times over. The output is not wrong,
    because the cross-tile dedup merges the duplicates downstream, but a third
    of the prompts are paid for and thrown away.

    The docstring here used to claim exclusive ownership and the self-check
    appeared to prove it, because its one straddling seed sat exactly on a tile
    boundary — the single position where the claim happens to hold.

    Use `partition_seeds` when you want each seed prompted once. This function
    stays as it is: it is the right primitive for "what is in this tile", and
    Colab notebooks call it directly.

    The box is clipped to the tile: a prompt reaching outside the image SAM2 was
    shown is meaningless to it.
    """
    tx, ty, tw, th = tile
    scale_x = render_size / tw
    scale_y = render_size / th

    out: list[dict] = []
    for seed in seeds:
        cx, cy = seed["centroid"]
        if not (tx <= cx < tx + tw and ty <= cy < ty + th):
            continue

        x, y, w, h = seed["bbox"]
        x1 = max(tx, x)
        y1 = max(ty, y)
        x2 = min(tx + tw, x + w)
        y2 = min(ty + th, y + h)

        out.append({
            **seed,
            "box": [
                (x1 - tx) * scale_x,
                (y1 - ty) * scale_y,
                (x2 - tx) * scale_x,
                (y2 - ty) * scale_y,
            ],
            "point": [(cx - tx) * scale_x, (cy - ty) * scale_y],
        })
    return out


# A prompt box that fills its tile tells SAM2 nothing — "segment the thing that
# is everything" — and the mask that comes back is whatever dominates the crop.
# Blocks big enough to do this are real (33 of 697 on the 1882 cadastral, whose
# 1024 px tile spans only 351 m of ground at 0.343 m/px), so they are counted
# out loud rather than dropped in silence.
#
# ponytail: dropped, not rescued. The right answer is to segment an oversized
# block on a coarser scale factor where it does fit, which means a second pass
# at another zoom; do that when the count stops being a rounding error.
MAX_BOX_TILE_FRACTION = 0.9


def partition_seeds(
    seeds: list[dict],
    tiles: list[tuple[int, int, int, int]],
    render_size: int = 1024,
    max_box_fraction: float = MAX_BOX_TILE_FRACTION,
) -> tuple[dict[tuple[int, int, int, int], list[dict]], dict[str, int]]:
    """Assign every seed to exactly one tile, then map it into that tile.

    Ownership is by a half-open window on the tiling *step* rather than on the
    tile, which is what makes it exclusive: tiles start every `step` pixels, so
    `[tx, tx + step)` tiles the plane without gaps or overlaps even though the
    tiles themselves overlap.

    The last tile in a row or column is the exception and it matters: a tiling
    clamps its final tile against the image edge, so that tile's start is less
    than one step from its neighbour's and the band between `tx + step` and the
    image edge would belong to nobody. Any tile that no other tile starts after,
    on that axis, owns everything to its far edge.

    Returns (seeds by tile, counts) where counts carries `seeds`, `placed`,
    `oversized` and `unplaced` — `unplaced` must be zero and is asserted by the
    self-check, because a seed silently belonging to no tile is exactly the
    failure this function exists to remove.
    """
    if not tiles:
        return {}, {"seeds": len(seeds), "placed": 0, "oversized": 0, "unplaced": len(seeds)}

    xs = sorted({t[0] for t in tiles})
    ys = sorted({t[1] for t in tiles})
    # The step is the gap between adjacent starts. One column or row means there
    # is no gap to read, so the tile is its own step.
    step_x = (xs[1] - xs[0]) if len(xs) > 1 else tiles[0][2]
    step_y = (ys[1] - ys[0]) if len(ys) > 1 else tiles[0][3]
    last_x, last_y = xs[-1], ys[-1]

    owner: dict[tuple[int, int, int, int], list[dict]] = {t: [] for t in tiles}
    by_start = {(t[0], t[1]): t for t in tiles}
    unplaced = 0

    for seed in seeds:
        cx, cy = seed["centroid"]
        # Snap the centroid down to the grid of starts, then clamp: a centroid
        # past the last start belongs to the last tile, which is the clamped one.
        ix = min(int((cx - xs[0]) // step_x), len(xs) - 1) if cx >= xs[0] else -1
        iy = min(int((cy - ys[0]) // step_y), len(ys) - 1) if cy >= ys[0] else -1
        if ix < 0 or iy < 0:
            unplaced += 1
            continue
        tile = by_start.get((xs[ix], ys[iy]))
        if tile is None:
            unplaced += 1
            continue
        tx, ty, tw, th = tile
        if not (tx <= cx < tx + tw and ty <= cy < ty + th):
            unplaced += 1
            continue
        owner[tile].append(seed)

    placed = oversized = 0
    out: dict[tuple[int, int, int, int], list[dict]] = {}
    limit = max_box_fraction * render_size
    for tile, mine in owner.items():
        mapped = seeds_for_tile(mine, tile, render_size=render_size)
        kept = []
        for m in mapped:
            x1, y1, x2, y2 = m["box"]
            if (x2 - x1) >= limit and (y2 - y1) >= limit:
                oversized += 1
                continue
            kept.append(m)
        placed += len(kept)
        out[tile] = kept

    return out, {
        "seeds": len(seeds),
        "placed": placed,
        "oversized": oversized,
        "unplaced": unplaced,
    }



def _self_check() -> None:
    rows = [
        # kept: a validated building, human text wins
        {"id": "a", "text": "Marche", "text_corrected": "Marché", "category": "other",
         "category_corrected": "building", "confidence": 0.1, "review_status": "validated",
         "global_x": 100, "global_y": 100, "global_w": 40, "global_h": 20},
        # dropped: street names label a line, not an area
        {"id": "b", "text": "Rue Catinat", "category": "street_name", "confidence": 0.9,
         "review_status": "pending", "global_x": 200, "global_y": 200, "global_w": 80, "global_h": 10},
        # dropped: unvalidated and under the confidence floor
        {"id": "c", "text": "?", "category": "building", "confidence": 0.2, "review_status": "pending",
         "global_x": 300, "global_y": 300, "global_w": 10, "global_h": 10},
        # kept: confident enough without review
        {"id": "d", "text": "Hôpital", "category": "institution", "confidence": 0.8,
         "review_status": "pending", "global_x": 1200, "global_y": 80, "global_w": 60, "global_h": 20},
    ]
    seeds = rows_to_seeds(rows)
    assert [s["extraction_id"] for s in seeds] == ["a", "d"], seeds
    assert seeds[0]["text"] == "Marché", "a human correction must win over the model's text"

    # One 1000px tile at the origin, rendered to 1024: 'a' is inside, 'd' is not.
    tile = (0, 0, 1000, 1000)
    got = seeds_for_tile(seeds, tile, render_size=1024)
    assert [s["extraction_id"] for s in got] == ["a"], got
    box = got[0]["box"]
    assert abs(box[0] - 100 * 1.024) < 1e-6, box
    assert abs(box[2] - 140 * 1.024) < 1e-6, box
    assert abs(got[0]["point"][0] - 120 * 1.024) < 1e-6, got[0]["point"]

    # Centroid ownership: a box straddling the edge belongs to one tile only.
    straddler = rows_to_seeds([
        {"id": "e", "text": "Edge", "category": "building", "confidence": 0.9, "review_status": "pending",
         "global_x": 980, "global_y": 100, "global_w": 40, "global_h": 20},
    ])
    left = seeds_for_tile(straddler, (0, 0, 1000, 1000))
    right = seeds_for_tile(straddler, (900, 0, 1000, 1000))
    assert len(left) + len(right) == 1, "exactly one tile owns a straddling seed"
    # …and the surviving prompt is clipped to its owner's bounds.
    owner = (left or right)[0]
    assert owner["box"][2] <= 1024.0 + 1e-6, owner["box"]

    # A row with no category is no longer prompt-worthy: `other` left the set.
    assert rows_to_seeds([
        {"id": "f", "text": "Ge_ B. 9", "confidence": 0.9, "review_status": "pending",
         "global_x": 100, "global_y": 8500, "global_w": 200, "global_h": 60},
    ]) == []

    # tiling_crop precedence, kept in step with tilingCrop in triageTypes.ts:
    # main_map wins over the neatline, and a neatline alone still counts.
    assert tiling_crop(None) is None
    assert tiling_crop({"neatline": [1, 2, 3, 4]}) == [1.0, 2.0, 3.0, 4.0]
    assert tiling_crop({
        "neatline": [1, 2, 3, 4],
        "regions": [{"category": "title", "bbox": [9, 9, 9, 9]},
                    {"category": "main_map", "bbox": [10, 20, 30, 40]}],
    }) == [10.0, 20.0, 30.0, 40.0]
    assert tiling_crop({"regions": [{"category": "legend", "bbox": [0, 0, 1, 1]}]}) is None

    # Clipping is by centroid, and no crop means no filtering.
    marginal = rows_to_seeds([
        {"id": "g", "text": "In", "category": "building", "confidence": 0.9, "review_status": "pending",
         "global_x": 500, "global_y": 500, "global_w": 40, "global_h": 20},
        {"id": "h", "text": "Out", "category": "building", "confidence": 0.9, "review_status": "pending",
         "global_x": 100, "global_y": 8500, "global_w": 40, "global_h": 20},
    ])
    crop = [459.0, 413.0, 11073.0, 7913.0]          # the 1882 sheet's own main_map
    assert [s["extraction_id"] for s in clip_seeds_to(marginal, crop)] == ["g"]
    assert clip_seeds_to(marginal, None) == marginal

    # ── modern-prior blocks ────────────────────────────────────────────────
    # A block round-trips to its own bounds, whatever depth its rings nest at,
    # and the seed is the same shape an OCR row produces.
    square = {"type": "Feature", "properties": {"area_px": 400.0},
              "geometry": {"type": "Polygon",
                           "coordinates": [[[100, 200], [140, 200], [140, 230],
                                            [100, 230], [100, 200]]]}}
    block_seeds = blocks_to_seeds([square])
    assert len(block_seeds) == 1, block_seeds
    b = block_seeds[0]
    assert set(b) == set(seeds[0]), "a block seed must be shaped like an OCR seed"
    assert b["bbox"] == [100.0, 200.0, 40.0, 30.0], b
    assert b["centroid"] == [120.0, 215.0], b
    assert b["extraction_id"] is None and b["text"] == "" and b["category"] == "block"
    assert b["category"] in AREA_CATEGORIES, "a block must be prompt-worthy"

    # An L-shaped block and a MultiPolygon both reduce to their outer bounds;
    # a hole is inside the ring and cannot move them.
    ell = {"geometry": {"type": "Polygon", "coordinates": [
        [[0, 0], [10, 0], [10, 4], [4, 4], [4, 10], [0, 10], [0, 0]],
        [[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]]]}}
    assert blocks_to_seeds([ell])[0]["bbox"] == [0.0, 0.0, 10.0, 10.0]
    multi = {"geometry": {"type": "MultiPolygon", "coordinates": [
        [[[0, 0], [1, 0], [1, 1], [0, 0]]],
        [[[8, 8], [9, 8], [9, 9], [8, 8]]]]}}
    assert blocks_to_seeds([multi])[0]["bbox"] == [0.0, 0.0, 9.0, 9.0]

    # Degenerate and non-areal input is skipped, the way a bad row is.
    assert blocks_to_seeds([
        {"geometry": {"type": "Polygon",                       # zero height
                      "coordinates": [[[0, 5], [10, 5], [0, 5]]]}},
        {"geometry": {"type": "Polygon", "coordinates": []}},   # empty
        {"geometry": {"type": "LineString",                     # not an area
                      "coordinates": [[0, 0], [10, 10]]}},
        {"geometry": None},
        {},
    ]) == []
    assert blocks_to_seeds([]) == []

    # A block seed is indistinguishable to `seeds_for_tile`: same ownership,
    # same clipping, and a box in the tile's render coords.
    got = seeds_for_tile(block_seeds, (0, 0, 1000, 1000), render_size=1024)
    assert len(got) == 1, got
    box = got[0]["box"]
    assert [round(v, 6) for v in box] == [102.4, 204.8, 143.36, 235.52], box
    assert all(0.0 <= v <= 1024.0 for v in box), box
    assert seeds_for_tile(block_seeds, (2000, 2000, 1000, 1000)) == []

    # ...and the main_map clip treats it exactly like an OCR seed: `crop` is
    # the 1882 sheet's own main_map, so the block at (120, 215) is furniture.
    inside = blocks_to_seeds([{"geometry": {"type": "Polygon", "coordinates":
        [[[1000, 1000], [1040, 1000], [1040, 1030], [1000, 1000]]]}}])
    assert clip_seeds_to(inside + block_seeds, crop) == inside

    # The CRS guard. It has to fire before anything touches the network, so a
    # bad file is caught here with no Supabase credentials in the environment.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        lonlat = os.path.join(tmp, "wgs84.geojson")
        with open(lonlat, "w", encoding="utf-8") as fh:
            json.dump({"type": "FeatureCollection", "features": []}, fh)
        for doc in ({"features": []},                     # no crs at all
                    {"crs": "EPSG:4326", "features": []},  # someone else's
                    {"crs": None, "features": []}):
            with open(lonlat, "w", encoding="utf-8") as fh:
                json.dump(doc, fh)
            try:
                load_seeds_from_prior(lonlat, "no-such-map")
            except ValueError as exc:
                assert PRIOR_CRS in str(exc), exc
            else:
                raise AssertionError(f"a {doc.get('crs')!r} crs must be refused")

    # ── partition_seeds: exactly one owner ────────────────────────────────
    # A real overlapping tiling: 1024 px tiles stepping 896, so every tile
    # shares a 128 px band with each neighbour and the corners are shared four
    # ways. This is the arrangement seeds_for_tile double-counts on.
    STEP, TILE = 896, 1024
    grid = [(x, y, TILE, TILE)
            for y in (0, 896)
            for x in (0, 896, 1792)]

    def _seed(cx, cy, w=20, h=20):
        return {"extraction_id": None, "text": "", "category": "block",
                "bbox": [cx - w / 2, cy - h / 2, w, h], "centroid": [cx, cy]}

    # One centroid per 64 px across the whole 2816x1920 image.
    dense = [_seed(x + 0.5, y + 0.5)
             for y in range(0, 1920, 64) for x in range(0, 2816, 64)]
    by_tile, counts = partition_seeds(dense, grid)
    assert counts["unplaced"] == 0, counts
    assert counts["placed"] + counts["oversized"] == len(dense), counts
    assert sum(len(v) for v in by_tile.values()) == len(dense), counts

    # The claim seeds_for_tile could not make: no seed is prompted twice.
    placements = [id(m) for v in by_tile.values() for m in v]
    assert len(placements) == len(dense)
    seen_centroids = [tuple(m["centroid"]) for v in by_tile.values() for m in v]
    assert len(set(seen_centroids)) == len(dense), "a centroid was placed twice"

    # ...and the old function really does double-count the same input, so this
    # test fails loudly if someone "simplifies" partition_seeds back into it.
    naive = sum(len(seeds_for_tile(dense, t)) for t in grid)
    assert naive > len(dense), (naive, len(dense))

    # A centroid in an overlap band lands in exactly one tile, the later one.
    band, _ = partition_seeds([_seed(950, 100)], grid)
    owners = [t for t, v in band.items() if v]
    assert owners == [(896, 0, TILE, TILE)], owners

    # The clamped last tile owns its edge band. A tiling that does not divide
    # evenly pushes its final tile back against the image edge, so that tile
    # starts less than a step after its neighbour — the band beyond
    # `start + step` would otherwise belong to no tile at all.
    clamped = [(0, 0, TILE, TILE), (896, 0, TILE, TILE), (1476, 0, TILE, TILE)]
    edge, ec = partition_seeds([_seed(2400, 100)], clamped)
    assert ec["unplaced"] == 0, ec
    assert [t for t, v in edge.items() if v] == [(1476, 0, TILE, TILE)]

    # A seed outside every tile is reported, never silently dropped.
    _, oc = partition_seeds([_seed(-500, -500)], grid)
    assert oc["unplaced"] == 1 and oc["placed"] == 0, oc

    # A block that fills its tile is no prompt at all: counted, not kept.
    huge = {"extraction_id": None, "text": "", "category": "block",
            "bbox": [0, 0, TILE, TILE], "centroid": [500, 500]}
    _, hc = partition_seeds([huge], grid)
    assert hc["oversized"] == 1 and hc["placed"] == 0, hc
    # One that fills it in a single axis is still a usable prompt.
    thin = {"extraction_id": None, "text": "", "category": "block",
            "bbox": [0, 400, TILE, 60], "centroid": [500, 430]}
    _, tc = partition_seeds([thin], grid)
    assert tc["oversized"] == 0 and tc["placed"] == 1, tc

    # An empty tiling is a refusal that says so, not a crash.
    _, zc = partition_seeds([_seed(10, 10)], [])
    assert zc["unplaced"] == 1, zc

    print("[ok] to_sam2_seeds self-check passed")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        _self_check()
    else:
        print(__doc__)
        sys.exit(1)
