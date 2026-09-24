#!/usr/bin/env python3
"""VMA OCR CLI — Gemini vision extraction for historical map tiles.

Subcommands:
  run          Fetch tile(s) and extract labels via Gemini
  batch        Run OCR on all tiles of a map (resumable, concurrent)
  clean        Fuzzy dedup + spatial fragment join for V1-style raw results
  dedup        Deduplicate existing labels from DB or local files
  preview      Render bbox overlay on a saved output JSON
  stitch       Composite multiple tiles into one preview image
  list-models  List available Gemini models
  detect-layout  Local (scipy): find legend/cartouche boxes — no API
  grid           Read the printed reference grid an index refers to
  numerals       Local (Tesseract): spot legend-ref numerals — no API
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import re
import sys
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

# Python 3.11+ restricts int-string conversion length as a security measure.
# Gemini occasionally returns malformed bbox values with absurdly large integers;
# we disable the limit here and sanitize values downstream in _sanitize_extractions().
if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)

# Resolve repo root for relative imports
REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from iiif_tiles import (
    AOI_GEO_HINT,
    adaptive_render_size,
    apply_clahe,
    aoi_tile_overrides,
    auto_tile_overrides,
    auto_tile_params,
    choose_scale_levels,
    compute_tile_colours,
    compute_tile_densities,
    detect_neatline,
    estimate_density,
    fetch_crop,
    get_image_info,
    get_iiif_base_from_allmaps,
    get_iiif_base_from_supabase,
    parse_aoi_px,
    tile_grid,
)
from gemini_client import DEFAULT_MODEL, extract_labels, extract_labels_sequence, extract_legend, list_models
from prompt import (DEFAULT_PROMPT, EXTRACTION_SCHEMA, PROMPTS, SYSTEM_PROMPT, schema_for,
                    sequence_frame_rules)
from labels import LABEL_PREFIXES, fold, label_core
from local_vision import detect_legend_boxes, spot_numerals

OUTPUTS_CACHE_DIR = Path(__file__).resolve().parents[1] / "outputs" / ".cache"

OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "outputs"


def make_run_dir(map_label: str, run_id: str | None) -> Path:
    """Return versioned output dir: outputs/{map_label}/runs/{run_id}/"""
    if not run_id:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    d = OUTPUTS_DIR / map_label / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_run_config(run_dir: Path, config: dict) -> None:
    (run_dir / "run_config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False)
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def parse_crop(s: str) -> tuple[int, int, int, int]:
    parts = [int(v) for v in s.split(",")]
    if len(parts) != 4:
        raise ValueError("--crop must be x,y,w,h")
    return tuple(parts)  # type: ignore[return-value]


def parse_rects(s: str) -> list[tuple[int, int, int, int]]:
    """';'-separated x,y,w,h rectangles in source px."""
    return [parse_crop(part) for part in s.split(";") if part.strip()]


def in_rects(rects: list[tuple[int, int, int, int]], bbox) -> bool:
    """Is this read's centre inside one of the rectangles?

    Used to drop what the tile pass finds inside a *printed* directory — the
    numbered legend block, the street index. A tile sees "52  C 10  Marche
    Central" and there is nothing in the picture to say that 52 is a line of a
    table rather than a numeral stamped on the map: on the 1942 Saigon-Cho Lon
    sheet that put the whole index column into `legend_ref`, numbers 1..99
    claiming to be positions. Those blocks have their own structured passes
    (`legend`, `street-index`), so the tile pass has nothing to add there.
    """
    x, y, w, h = bbox
    cx, cy = x + w / 2, y + h / 2
    return any(rx <= cx < rx + rw and ry <= cy < ry + rh for rx, ry, rw, rh in rects)


def render_preview(
    image,
    extractions: list[dict],
    out_path: Path,
) -> None:
    """Draw bbox overlays on the tile image and save as PNG."""
    from PIL import ImageDraw, ImageFont

    preview = image.copy().convert("RGBA")
    overlay = preview.copy()
    draw = ImageDraw.Draw(overlay)
    img_w, img_h = image.size

    COLORS = {
        "street": (255, 50, 50, 180),
        "hydrology": (50, 100, 255, 180),
        "place": (50, 150, 255, 180),
        "building": (50, 220, 50, 180),
        "institution": (220, 150, 50, 180),
        "legend": (180, 50, 220, 180),
        "title": (50, 220, 220, 180),
        "other": (180, 180, 180, 120),
    }

    for ext in extractions:
        bbox = ext.get("bbox_px")
        if not bbox or len(bbox) < 4:
            continue
        # Gemini returns coordinates in 0-1000 normalized space — scale to pixels
        x = int(bbox[0] * img_w / 1000)
        y = int(bbox[1] * img_h / 1000)
        w = max(int(bbox[2] * img_w / 1000), 4)
        h = max(int(bbox[3] * img_h / 1000), 4)
        cat = ext.get("category", "other")
        color = COLORS.get(cat, COLORS["other"])
        draw.rectangle([x, y, x + w, y + h], outline=color[:3], width=2)
        label = f"{ext.get('text', '')[:30]} [{cat}]"
        tx, ty = x + 2, y - 13 if y > 13 else y + 2
        tw_est = len(label) * 6
        draw.rectangle([tx - 1, ty - 1, tx + tw_est, ty + 11], fill=(0, 0, 0))
        draw.text((tx, ty), label, fill=color[:3])

    from PIL import Image
    result = Image.alpha_composite(preview, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(out_path)
    print(f"Preview saved: {out_path}")


# ── Subcommands ───────────────────────────────────────────────────────────────


def clahe_prep(args: argparse.Namespace):
    """Build the tile pre-pass from the --clahe flags, or None when it is off.

    The returned callable is applied at the **last** point before a tile's
    bytes reach the model — after both tile caches, after the shared overview
    that feeds `compute_tile_colours`. So the caches keep raw pixels (an A/B
    eval reuses the same cached tiles and only the pre-pass differs, and a
    later run without the flag is not served an equalized tile), and the
    water/vegetation wash scores are structurally out of reach.
    """
    if not getattr(args, "clahe", False):
        return None
    spec = str(getattr(args, "clahe_grid", "8")).lower()
    grid: int | tuple[int, int]
    if "x" in spec:
        r, _, c = spec.partition("x")
        grid = (int(r), int(c))
    else:
        grid = int(spec)
    clip = float(getattr(args, "clahe_clip", 2.0))
    print(f"  CLAHE pre-pass ON (clip={clip}, grid={spec}) — advisory, "
          f"not yet in EVAL-BASELINE.md")
    return lambda img: apply_clahe(img, clip, grid)


def _tile_cache_path(tile_cache_dir: Path, tile_key: str, render: int) -> Path:
    """Where a tile rendered at `render` px lives. The render size is part of the
    name because a tile is not one image: the same crop at 1024 and at 2048 are
    different pictures of it.

    `render` is the size the caller **asked IIIF for** — the number that went
    into `fetch_crop(size=...)` — and never a dimension measured off the
    returned image. Those are not the same quantity: `fetch_crop` defaults to
    `fit=False`, so the IIIF size parameter is `{size},` — width only — and a
    crop taller than it is wide comes back with width == size and height larger.
    Naming it after `max(img.size)` stored such a tile under its *height*, while
    every read site asked for it by the render size it had requested, so the
    file could never be found again: the whole clipped right-hand column of a
    tile grid, plus the bottom-right corner, was re-fetched on every run. Worse
    than the wasted money, the re-fetched bytes are not the bytes the earlier
    run cached (the level0 composition path moved under 2cf6dd02), so no two
    runs on the same sheet were byte-comparable and every A/B this pipeline
    exists to produce was quietly contaminated — the 1882 re-gate manufactured
    a +1 label that way (`work/cleanup/F-1882-regate.md`).

    The requested size is also the only key that cannot collide: given
    `fit=False`, the crop's own w/h plus the requested width determine the
    rendered image exactly, whereas two different requests on a tall crop can
    land on the same `max(img.size)`.
    """
    return tile_cache_dir / f"{tile_key}@{render}_tile.png"


def _cached_tile(tile_cache_dir: Path, tile_key: str, render: int) -> Image.Image | None:
    """The cached PNG for this tile *at this render size*, or None to fetch it.

    The key was `x_y_w_h` alone until 2026-09-10, with no render size in it, so
    any sheet tiled once was served from cache no matter what `--render-size`,
    `--low-res-render` or `--adaptive` asked for afterwards. The flags were not
    overridden, they were silently ignored, and a run that changed one reported
    a number it had not measured — which is the worst shape a bug can take in a
    pipeline whose whole job is producing numbers. Measured on the 1882 gate
    sheet: a 2400 px and a 1024 px render of the same frame also tokenise to the
    same ~1032 input tokens, so the cache was hiding a knob that is inert at the
    API anyway. Two separate reasons not to trust an old render-size result.

    A legacy file is read and reused when it happens to hold the right size, and
    otherwise ignored — deliberately not renamed. Renaming would be tidier and
    is lossless, but these directories are shared with a running worker and with
    other sessions, and a cache that moves under a concurrent reader is a worse
    problem than a few files with uninformative names. The same reasoning is why
    the legacy test below still reads `max(img.size) == render` even though the
    key it sits beside now means the *requested* width: loosening it to
    `img.size[0] == render` would start serving pre-2cf6dd02 bytes for exactly
    the tall edge tiles this fix is about, which is a change to the pixels the
    model sees dressed up as a bug fix. It stays strictly as conservative as it
    was; the tall tiles are re-fetched once more and then hit forever.
    """
    from PIL import Image as PILImage  # imported per-function, as elsewhere here

    path = _tile_cache_path(tile_cache_dir, tile_key, render)
    if path.exists():
        return PILImage.open(path).convert("RGB")

    legacy = tile_cache_dir / f"{tile_key}_tile.png"
    if legacy.exists():
        img = PILImage.open(legacy).convert("RGB")
        if max(img.size) == render:
            return img
    return None


def cmd_run(args: argparse.Namespace) -> None:
    # Resolve IIIF base
    iiif_base = args.iiif_base
    if not iiif_base:
        if args.map_id:
            print(f"Resolving IIIF base for map {args.map_id} ...")
            iiif_base = get_iiif_base_from_supabase(args.map_id)
            if not iiif_base:
                print("  maps.iiif_image not set, falling back to Allmaps annotation")
                raise SystemExit("Could not resolve IIIF base. Set --iiif-base directly.")
        else:
            raise SystemExit("Provide --map-id or --iiif-base")

    map_label = args.map_id or "unknown"
    out_dir = make_run_dir(map_label, getattr(args, "run_id", None))
    # Shared tile image cache lives next to runs/ to avoid re-downloading
    tile_cache_dir = OUTPUTS_DIR / map_label
    tile_cache_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "calls.jsonl"

    prompt_text = PROMPTS.get(args.prompt, PROMPTS[DEFAULT_PROMPT])
    model = args.model

    # Always fetch image info for quality detection
    print(f"Fetching image info from {iiif_base}/info.json ...")
    info = get_image_info(iiif_base)
    iiif_quality = info.get("quality", "default")

    # Determine tiles to process
    if args.crop:
        tiles = [parse_crop(args.crop)]
    else:
        tiles = list(tile_grid(info["width"], info["height"], tile=args.tile_size, overlap=args.overlap))
        print(f"  Full grid: {len(tiles)} tiles")

    if args.limit:
        tiles = tiles[: args.limit]

    print(f"Processing {len(tiles)} tile(s) with model {model}")
    clahe = clahe_prep(args)

    for i, (x, y, w, h) in enumerate(tiles, 1):
        tile_key = f"{x}_{y}_{w}_{h}"
        json_path = out_dir / f"{tile_key}.json"

        print(f"[{i}/{len(tiles)}] tile {x},{y},{w},{h} ...", end=" ", flush=True)

        if args.dry_run:
            print("(dry-run, skipping)")
            continue

        # Fetch tile — adaptive render size based on density if requested
        if getattr(args, "adaptive", False):
            # Fetch a cheap 512px preview to measure density first
            preview = fetch_crop(iiif_base, x, y, w, h, size=512, quality=iiif_quality)
            render_size = adaptive_render_size(preview, low=1024, high=2048)
        else:
            render_size = args.render_size

        image = fetch_crop(iiif_base, x, y, w, h, size=render_size, quality=iiif_quality)
        density = estimate_density(image)
        print(f"fetched ({image.size[0]}×{image.size[1]}, density={density:.2f})", end=" ", flush=True)
        if clahe:
            image = clahe(image)

        # Extract labels
        result = _sanitize_extractions(extract_labels(
            image=image,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt_text,
            schema=schema_for(args.prompt),
            thinking=not getattr(args, 'low_thinking', False),
            model=model,
            log_path=log_path,
            cache_dir=OUTPUTS_CACHE_DIR,
        ), log_path=log_path)

        n = len(result.get("extractions", []))
        print(f"→ {n} extractions")

        # Gemini returns 0-1000 normalized coords — record as 1000 so _to_global works
        result["_meta"] = {
            "tile_x": x, "tile_y": y, "tile_w": w, "tile_h": h,
            "render_w": 1000, "render_h": 1000,
            "prompt": args.prompt, "model": args.model,
        }

        # Save JSON (in versioned run dir)
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        # Tile image cached at map level (shared across runs)
        # Keyed by the size we asked IIIF for, not by a dimension of what came
        # back — see _tile_cache_path.
        tile_img_path = _tile_cache_path(tile_cache_dir, tile_key, render_size)
        if not tile_img_path.exists():
            image.save(tile_img_path)

        # Save per-tile preview in run dir
        if args.preview:
            preview_path = out_dir / f"{tile_key}_preview.png"
            render_preview(image, result.get("extractions", []), preview_path)

    # Save run config for reproducibility / paper reference
    save_run_config(out_dir, {
        "map_id": map_label,
        "model": args.model,
        "prompt": args.prompt,
        "render_size": args.render_size,
        "tile_size": getattr(args, "tile_size", None),
        "overlap": getattr(args, "overlap", None),
        "tiles": [f"{x},{y},{w},{h}" for x, y, w, h in tiles],
        "clahe": [args.clahe_clip, args.clahe_grid] if getattr(args, "clahe", False) else False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    print(f"\nDone. Run dir:  {out_dir}")
    print(f"Usage log:     {log_path}")


def origin_keyed_overrides(overrides: dict[str, str], shift: int) -> dict[tuple[int, int], str]:
    """Re-key per-tile priorities from "{x}_{y}_{w}_{h}" to (x+shift, y+shift).

    A person's triage keys are strings against the grid they saw. The second
    pass of the two-pass recipe moves the whole grid by half a tile, and an edge
    tile's w/h differ from the interior's, so a literal string lookup matched
    nothing on that pass — every tile marked *skip* was read anyway at full cost.
    Matching on the origin alone, shifted, is what makes a triage decision hold
    across both passes. Unparseable keys are dropped rather than raising: the
    payload is JSON from a browser.
    """
    out: dict[tuple[int, int], str] = {}
    for key, priority in overrides.items():
        parts = key.split("_")
        if len(parts) < 2:
            continue
        try:
            out[(int(parts[0]) + shift, int(parts[1]) + shift)] = priority
        except ValueError:
            continue
    return out


def cmd_self_check(args: argparse.Namespace) -> None:
    """Run: python ocr.py self-check — the pure helpers on the automated path."""
    # Tile priorities must survive the half-tile grid shift. With tile 2400 and
    # overlap 600 the stride is 1800, so pass a starts at rx and pass b at
    # rx+1200: 1800m - 1800n = 1200 has no integer solution and not one key
    # coincides. The shift is what lines them back up.
    overrides = {"0_0_2400_2400": "skip", "1800_0_2400_2400": "low_res",
                 "3600_0_1200_2400": "skip"}
    unshifted = origin_keyed_overrides(overrides, 0)
    assert unshifted[(0, 0)] == "skip"
    assert unshifted[(1800, 0)] == "low_res"
    shifted = origin_keyed_overrides(overrides, 1200)
    assert shifted[(1200, 1200)] == "skip", shifted
    assert shifted[(3000, 1200)] == "low_res", shifted
    assert not set(unshifted) & set(shifted), \
        "the shifted grid must share no origin with the unshifted one"
    # The clipped edge tile is found by origin alone, whatever its w/h.
    assert shifted[(4800, 1200)] == "skip"
    # Junk in the payload is dropped, not raised.
    assert origin_keyed_overrides({"": "skip", "a_b_c_d": "skip", "7": "skip"}, 0) == {}

    # Every call must be costed as it is logged. Asserted against a written
    # log rather than a mock, because the usage field names are google.genai's
    # to change and a rename would silently make every cost None — which reads
    # downstream as "cheap", not as "broken".
    import tempfile as _tf, types as _ty
    from gemini_client import _log_call as _lc
    _usage = _ty.SimpleNamespace(prompt_token_count=3782, candidates_token_count=3423,
                                 total_token_count=8504, cached_content_token_count=1607,
                                 thoughts_token_count=1274)
    with _tf.TemporaryDirectory() as _tmp:
        _log = Path(_tmp) / "runs" / "r" / "calls.jsonl"   # parent must be created
        _lc(log_path=_log, model="gemini-3.8-flash", elapsed=1.0,
            usage=_usage, n_extractions=38)
        _lc(log_path=_log, model="gemini-3-flash-preview", elapsed=1.0,
            usage=_usage, n_extractions=2)
        _priced, _unpriced = [json.loads(x) for x in _log.read_text().splitlines() if x.strip()]
    # 1607 cached + 2175 fresh in, 4722 billed out, at 0.075/0.75/3.75 per Mtok.
    assert _priced["cost_usd"] == 0.019459, _priced
    assert _priced["thoughts_tokens"] == 1274, "the thinking field must be recorded"
    # A model with no published rate logs null. A plausible guess here would be
    # averaged into every report downstream as if it had been measured.
    assert _unpriced["cost_usd"] is None, _unpriced

    # The cache must not serve a result shaped by a different schema.
    from cache import SCHEMA_VERSION, schema_version
    assert schema_version(None) == SCHEMA_VERSION
    assert schema_version({"a": 1}) == schema_version({"a": 1}), "must be stable"
    assert schema_version({"a": 1}) != schema_version({"a": 1, "b": 2}), \
        "an added schema field must invalidate the cache"
    assert schema_version({"a": 1, "b": 2}) == schema_version({"b": 2, "a": 1}), \
        "key order is not a schema change"
    # …and today's schemas must still resolve to the version the 233 entries
    # already in outputs/.cache were written under, or deriving the version
    # would have thrown away every paid-for tile for no schema change at all.
    from prompt import EXTRACTION_SCHEMA, SCOUT_SCHEMA
    assert schema_version(EXTRACTION_SCHEMA) == SCHEMA_VERSION, "cache went cold"
    assert schema_version(SCOUT_SCHEMA) == SCHEMA_VERSION, "scout cache went cold"
    assert schema_version({**EXTRACTION_SCHEMA, "zzz": {"type": "string"}}) != SCHEMA_VERSION

    # A partial chunked write must be loud. The chunk loop is not
    # transactional, so this number is the only thing separating "the run
    # finished" from "the run stopped four chunks in and the rows look fine".
    from supabase_client import check_write_complete
    check_write_complete(337, 337, "m", "r")          # complete
    check_write_complete(337, 400, "m", "r")          # a previous attempt wrote more
    try:
        check_write_complete(337, 150, "m", "r")
    except RuntimeError as e:
        assert "150" in str(e) and "337" in str(e), e
    else:
        raise AssertionError("a short write must raise")

    # ── Row-sequence grouping: no group inside another one ────────────────
    # `range(0, n, max_frames - 1)` emitted a trailing group that was a subset
    # of the previous one whenever the row was one tile longer than a multiple
    # of the step. On the 1882 sheet's 7-column rows that group is the 402 px
    # right-edge sliver alone, rendered 1024x6113: it returned 0 extractions on
    # all five calls it was paid for, and then wiped what the 4-frame call had
    # read for that tile. `work/cleanup/F-1882-regate.md` measured the loss at
    # 78 of 362 extractions (22%) on one pass.
    seven = list(range(7))
    assert group_row_frames(seven, 4) == [[0, 1, 2, 3], [3, 4, 5, 6]],         group_row_frames(seven, 4)
    for n in range(1, 40):
        for max_frames in (1, 2, 3, 4, 5, 8):
            row = list(range(n))
            groups = group_row_frames(row, max_frames)
            assert groups, (n, max_frames)
            # every tile is read
            assert set().union(*(set(g) for g in groups)) == set(row), (n, max_frames)
            for g in groups:
                assert 1 <= len(g) <= max(1, max_frames), (n, max_frames, g)
                assert g == sorted(g), g              # order is left→right
            for earlier, later in zip(groups, groups[1:]):
                assert not set(later) <= set(earlier),                     f"group {later} is inside {earlier} — a paid call that reads "                     f"nothing new (n={n}, max_frames={max_frames})"
                assert not set(earlier) <= set(later), (earlier, later)
                if max_frames >= 2 and len(groups) > 1:
                    # the deliberate seam overlap, which is why row-sequence
                    # mode can assemble a label printed across a tile boundary
                    assert set(earlier) & set(later), (earlier, later)

    # ── …and a later group never replaces a reading with an empty one ──────
    a = {"text": "Rue Catinat", "bbox_px": [10, 20, 300, 40]}
    b = {"text": "Quai de Donnai", "bbox_px": [500, 20, 300, 40]}
    assert merge_group_extractions([a], []) == [a],         "an empty group wiped a tile the previous group had read"
    assert merge_group_extractions([], [a]) == [a]
    assert merge_group_extractions(None, []) == []
    assert merge_group_extractions([a], [b]) == [a, b], "both readings were paid for"
    # The same row read twice by two overlapping groups is one row.
    assert merge_group_extractions([a], [dict(a)]) == [a]
    # A different box for the same text is a different reading — dedup_items
    # owns the fuzzy merge, downstream and across the whole sheet.
    moved = {**a, "bbox_px": [12, 22, 300, 40]}
    assert len(merge_group_extractions([a], [moved])) == 2
    # Never mutate the caller's lists.
    first = [a]
    merge_group_extractions(first, [b])
    assert first == [a], "merge_group_extractions mutated its input"

    # A retry decision must read a status code, not a substring of a number.
    from gemini_client import _has_status
    assert _has_status("503 UNAVAILABLE", "503")
    assert not _has_status("used 1500 tokens", "500"), "1500 is not a 500"
    assert not _has_status("4290", "429")

    print("[ok] ocr self-check passed")


# `seq-v1-idx` asks the model for category="index_key" because that is what the
# thing is called on the sheet. `legend_ref` is what the column, the review UI's
# Numbers tab and the join to `legend_entry` all speak, and what `ocr numerals`
# writes. One name at the model boundary, one in the database.
#
# Before 2026-09-12 neither end worked: `index_key` was missing from the response
# schema, so the model could not return it, and nothing translated it if it had.
# The 1942 rescan one-off did this by hand afterwards; the 1878 sheet lost all 28
# of its numerals to `other` before anyone looked.
_CATEGORY_TO_DB = {"index_key": "legend_ref"}


def _db_category(category: str | None) -> str:
    return _CATEGORY_TO_DB.get(category or "other", category or "other")


def cmd_batch(args: argparse.Namespace) -> None:
    """Run OCR on every tile of a map with resume support and thread concurrency."""
    import concurrent.futures
    import threading
    from PIL import Image as PILImage

    if getattr(args, "aoi", None):
        raise SystemExit(AOI_GEO_HINT)

    local_image: str | None = getattr(args, "local_image", None)
    iiif_base = args.iiif_base

    if local_image:
        # Local file mode — derive image dimensions directly, no IIIF needed
        from PIL import Image as _PILImg
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _PILImg.MAX_IMAGE_PIXELS = None
            _im = _PILImg.open(local_image)
            img_w, img_h = _im.size
        print(f"Local image: {local_image} ({img_w}×{img_h} px)")
        iiif_base = iiif_base or "local"
    else:
        if not iiif_base:
            if args.map_id:
                print(f"Resolving IIIF base for map {args.map_id} ...")
                iiif_base = get_iiif_base_from_supabase(args.map_id)
                if not iiif_base:
                    raise SystemExit("Could not resolve IIIF base.")
            else:
                raise SystemExit("Provide --map-id, --iiif-base, or --local-image")
        print(f"Fetching image info from {iiif_base}/info.json ...")
        info = get_image_info(iiif_base)
        img_w, img_h = info["width"], info["height"]
        iiif_quality = info.get("quality", "default")

    map_label = args.map_id or "unknown"
    out_dir = make_run_dir(map_label, getattr(args, "run_id", None))
    tile_cache_dir = OUTPUTS_DIR / map_label
    tile_cache_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "calls.jsonl"

    if getattr(args, "db", False) and map_label != "unknown":
        try:
            from supabase_client import update_pipeline_status
            update_pipeline_status(map_label, "ocr_queued",
                                   ocr_started_at=datetime.now(timezone.utc).isoformat())
        except Exception as e:
            print(f"[pipeline] status update skipped: {e}")

    prompt_text = PROMPTS.get(args.prompt, PROMPTS[DEFAULT_PROMPT])
    model = args.model

    # ── Smart tiling pipeline ────────────────────────────────────────────────
    grid_region = None
    tile_size = args.tile_size
    overlap = args.overlap
    render_size = args.render_size

    # 0. Manual crop — human-specified neatline takes priority over all auto-detection
    if getattr(args, "crop", None):
        parts = [int(v) for v in args.crop.split(",")]
        grid_region = tuple(parts)  # (x, y, w, h)
        print(f"  Manual crop: {grid_region}")

    # 1. Scout pass (optional) — detect neatline via LLM
    scout_cartouche = None  # legend region for --legend, harvested from the scout pass
    if not grid_region and getattr(args, "scout", False):
        print("\n--- SCOUT PASS INITIALIZED ---")
        scout_args = argparse.Namespace(**{**vars(args), 'prompt': 'scout', 'render_size': 4096, 'preview': True})
        scout_out = cmd_scout(scout_args)
        grid_region = scout_out.get("content")
        scout_cartouche = scout_out.get("cartouche")
        if grid_region:
            print(f"  Adaptive Tiling: Constraining grid to map bound {grid_region}")

    # 2. Auto-scale tile size to hit target call count
    # ── Ground-distance tiling ────────────────────────────────────────────────
    # `--tile-metres` sizes the grid from the sheet's own georeference instead of
    # from a pixel count someone worked out by hand. It is the flag
    # `docs/pipelines.md` step 3 has referred to since it was written, and the
    # first thing on the Python side that can see the ground.
    #
    # Sized off `grid_region` when a crop is already known — which means a
    # --smart-grid crop is too late to be seen here, exactly as it is for
    # --target-calls below. Pass --crop if the neatline matters to the sizing.
    tile_metres = getattr(args, "tile_metres", None)
    sized_from_scale = False
    scale_fit = None
    if tile_metres and not local_image and args.map_id:
        from scale import (
            COARSE_SCAN_METRES_PER_PX,
            DEFAULT_OVERLAP_RATIO,
            annotation_for_map,
            metres_per_pixel,
            tile_size_for,
        )

        ann = annotation_for_map(args.map_id)
        fit = scale_fit = metres_per_pixel(ann) if ann else None
        if fit is None:
            print("  --tile-metres: no usable georeference on this map "
                  "(4+ GCPs needed) — keeping --tile-size")
        elif not fit.trustworthy:
            print(f"  --tile-metres: {fit}\n"
                  "     too anisotropic to size from — keeping --tile-size")
        else:
            region_w = grid_region[2] if grid_region else img_w
            region_h = grid_region[3] if grid_region else img_h
            plan = tile_size_for(
                fit.mean, region_w, region_h,
                target_metres=tile_metres,
                overlap_ratio=DEFAULT_OVERLAP_RATIO,
            )
            tile_size = plan.tile
            overlap = int(plan.tile * DEFAULT_OVERLAP_RATIO)
            render_size = plan.render
            sized_from_scale = True
            print(f"  Scale: {fit}")
            print(f"  Sizing: {plan}  (--overlap ignored; {DEFAULT_OVERLAP_RATIO:.0%} of the tile)")
            if fit.mean > COARSE_SCAN_METRES_PER_PX:
                print(f"  ⚠ Coarse scan: {fit.mean:.2f} m in every source pixel. The frame is "
                      "normalised to a fixed patch budget before the model sees it, so no "
                      "tile size or render size recovers ink the scan never captured. "
                      "Calibrated on city plans, where a name spans tens of metres; a "
                      "small-scale sheet spends hundreds per name and reads fine well past "
                      "this line (An Thi, 4.26 m/px, 272 names in one pass). A flag to read "
                      "beside the map's scale, not a reason to stop.")

    target_calls = getattr(args, "target_calls", None)
    if target_calls and sized_from_scale:
        print("  --target-calls ignored: --tile-metres already sized the grid.")
    elif target_calls and not local_image:
        region_w = grid_region[2] if grid_region else img_w
        region_h = grid_region[3] if grid_region else img_h
        tile_size, overlap, render_size = auto_tile_params(
            region_w, region_h, target_calls=target_calls,
            base_render=args.render_size, base_tile=args.tile_size,
        )
        print(f"  Auto-tile: tile={tile_size} overlap={overlap} render={render_size} "
              f"(targeting ~{target_calls} calls)")

    clahe = clahe_prep(args)

    # Shared full-image overview — neatline, skip-sparse and auto-priority all
    # want the same downscale; fetch it at most once.
    #
    # 2048, not the 1024 this used until 2026-09-04. `compute_tile_densities`
    # is resolution-critical: measured on the 1882 Saigon cadastral, the mean
    # density of centre tiles versus edge tiles ran 0.019 vs 0.134 at 600px,
    # 0.044 vs 0.129 at 1024px and 0.106 vs 0.140 at 1513px — inverted every
    # time, i.e. the dense city centre scored *below* the margins and
    # --auto-priority would have skipped exactly the tiles worth reading. Only
    # at 2048 does it come right (0.166 vs 0.139). Do not lower this.
    OVERVIEW_WIDTH = 2048
    _ov_cache: dict = {}
    def _overview():
        if "img" not in _ov_cache:
            _ov_cache["img"] = fetch_crop(iiif_base, 0, 0, img_w, img_h,
                                          size=OVERVIEW_WIDTH, quality=iiif_quality)
        return _ov_cache["img"]

    # 3. Local neatline detection as fallback (no API call, pure image processing)
    if not grid_region and not local_image and getattr(args, "smart_grid", False):
        print("  Detecting neatline from overview image ...")
        overview = _overview()
        neatline = detect_neatline(overview)
        if neatline:
            ox, oy, ow, oh = neatline
            sx, sy = img_w / overview.size[0], img_h / overview.size[1]
            grid_region = (int(ox * sx), int(oy * sy), int(ow * sx), int(oh * sy))
            print(f"  Neatline detected: {grid_region} "
                  f"({grid_region[2]*grid_region[3]*100//(img_w*img_h)}% of image)")
        else:
            print("  No margins detected — using full image")

    # Second pass of the two-pass recipe: same grid, moved half a tile in both
    # axes so every seam lands where the first pass had tile interior. Not meant
    # to stand alone (28/43 on its own); merged with the unshifted pass by
    # `ocr.py merge` it read 41/43. See EVAL-BASELINE.md.
    #
    # The offset is a phase shift of the grid, handed to `tile_grid`, and it
    # does **not** move or shrink the region. Until 2026-09-10 this line did
    # the shift by insetting the region — `(rx + off, ry + off, rw - off,
    # rh - off)` — which held the far edge but shortened the tiled extent by
    # `off` in both axes. Two things followed: the leading `off`-wide strip of
    # the region was never read on pass 2 at all, and whenever the shortened
    # extent dropped below a step boundary the pass lost a whole row or column.
    # On the 1882 gate sheet's `main_map` crop (459,413,11073,7913 at tile
    # 2400 / overlap 300) that was 20 tiles where pass 1 had 24, covering 76%
    # of the crop, and pass 2 came back with 255 labels against the 328 the
    # uncropped run read — the whole of the fleet payload's 68/85 against the
    # recipe of record's 75/85. See `test_grid_offset.py`.
    grid_offset = getattr(args, "grid_offset", 0) or 0
    if grid_offset:
        print(f"  Grid offset {grid_offset}px → grid phase-shifted inside region "
              f"{grid_region or (0, 0, img_w, img_h)}")

    tiles = list(tile_grid(img_w, img_h, tile=tile_size, overlap=overlap,
                           region=grid_region, offset=grid_offset))
    total_before_filter = len(tiles)

    # 4. Density-based skip (text-specific local variance)
    if not local_image and getattr(args, "skip_sparse", False):
        min_text_frac = getattr(args, "min_text_frac", 0.01)
        print(f"  Computing text density (threshold={min_text_frac}) ...")
        densities = compute_tile_densities(_overview(), tiles, img_w, img_h)
        tiles = [t for t in tiles if densities.get(t, 1.0) >= min_text_frac]
        skipped = total_before_filter - len(tiles)
        if skipped:
            print(f"  Density filter: skipped {skipped} sparse tiles")

    # 5. Prior-run skip — reuse empty-tile info from a previous run
    prior_run = getattr(args, "prior_run", None)
    if prior_run:
        prior_dir = Path(prior_run)
        if prior_dir.is_dir():
            empty_tiles = set()
            for f in prior_dir.glob("*.json"):
                if f.stem[0].isdigit() and "_" in f.stem:
                    data = json.loads(f.read_text())
                    if not data.get("extractions"):
                        parts = f.stem.split("_")
                        if len(parts) == 4:
                            empty_tiles.add(tuple(int(p) for p in parts))
            before = len(tiles)
            tiles = [t for t in tiles if t not in empty_tiles]
            if before > len(tiles):
                print(f"  Prior-run skip: dropped {before - len(tiles)} empty tiles "
                      f"(from {prior_dir.name})")

    # 6. Per-tile priority overrides — skip marked tiles, use lower render for low_res
    tile_overrides: dict[str, str] = {}
    # True when the grid these keys belong to is the one a person triaged, which
    # is the only case that needs shifting to this pass's grid.
    human_overrides = False
    if getattr(args, "tile_overrides", None):
        try:
            tile_overrides = json.loads(args.tile_overrides)
            human_overrides = bool(tile_overrides)
        except json.JSONDecodeError as e:
            print(f"  Warning: could not parse --tile-overrides JSON: {e}")
    elif not local_image and getattr(args, "auto_priority", False):
        # Auto-fill the priority grid from a color pre-pass instead of by hand:
        # blank → skip, sparse → low_res, dense → full render.
        print("  Auto-priority: computing density + colour pre-pass ...")
        overview = _overview()
        densities = compute_tile_densities(overview, tiles, img_w, img_h)
        # The colour/wash demotion is opt-in, and stays out of the automated
        # path. Water and vegetation wash reads as busy to the density pass and
        # holds almost no toponyms, so demoting it is the right idea — but the
        # implementation looks at hue 60–260° and every saturated pixel on the
        # 1882 cadastral sits in 0–60° (warm aged paper, pink parcel tints). It
        # scored 0.000 on every tile at every saturation gate down to 0.10, so
        # on this corpus it is an unmeasured signal, and `--auto-priority` is
        # now what the queue sends by default. `suggestTriage.ts` leaves it out
        # for the same reason.
        colours = None
        if getattr(args, "colour_wash", False):
            colours = compute_tile_colours(overview, tiles, img_w, img_h)
        tile_overrides = auto_tile_overrides(
            densities,
            skip_below=getattr(args, "skip_below", 0.01),
            low_res_below=getattr(args, "low_res_below", 0.08),
            colours=colours,
            wash_above=getattr(args, "wash_above", 0.6),
        )
        if colours:
            washed = sum(1 for v in colours.values() if v >= getattr(args, "wash_above", 0.6))
            print(f"  Colour pre-pass: {washed} tiles are mostly water/vegetation wash")
        n_skip = sum(1 for v in tile_overrides.values() if v == "skip")
        n_low = sum(1 for v in tile_overrides.values() if v == "low_res")
        print(f"  Auto-priority: {n_skip} skip, {n_low} low-res, "
              f"{len(tiles) - n_skip - n_low} full of {len(tiles)} tiles")

    # 6b. Study-area filter — everything outside the AOI becomes a skip. Runs
    # after the priority pass so it can only take tiles away, never promote.
    if getattr(args, "aoi_px", None):
        try:
            aoi = parse_aoi_px(args.aoi_px)
        except ValueError as e:
            raise SystemExit(str(e)) from None
        before = sum(1 for v in tile_overrides.values() if v == "skip")
        tile_overrides = aoi_tile_overrides(tiles, aoi, tile_overrides)
        after = sum(1 for v in tile_overrides.values() if v == "skip")
        print(f"  AOI {aoi}: {after - before} tiles outside the study area → skip")

    low_res_render = getattr(args, "low_res_render", 512)

    # Overrides arrive keyed "{x}_{y}_{w}_{h}" against the grid a person triaged.
    # Two things stop a literal string match from working on the second pass of
    # the two-pass recipe:
    #
    #   * `--grid-offset` moves the whole grid half a tile, so every origin is
    #     the first pass's plus that offset (same stride, shifted start).
    #   * w and h are only the clip at the sheet edge, so an edge tile's key
    #     differs even when it is the same tile.
    #
    # Before this, neither matched on the shifted pass: `tile_overrides.get()`
    # returned None for every tile, so every tile a person marked *skip* was
    # read anyway at full cost, and every *low_res* tile rendered full size.
    # Match on the origin alone, and shift a person's keys by the offset. Keys
    # this run generated itself (auto-priority, AOI) are already on this grid.
    priority_at = origin_keyed_overrides(
        tile_overrides, grid_offset if human_overrides else 0)
    # One tile of the shifted pass is *not* on the shifted lattice: the one that
    # straddles the region's start, which `tile_grid` clips back to the region
    # origin so the leading strip is read at all. Its origin is the unshifted
    # one, so it needs the unshifted keys. Kept as a separate fallback dict
    # because the two lattices must stay disjoint (`ocr.py self-check`).
    priority_unshifted = (origin_keyed_overrides(tile_overrides, 0)
                          if human_overrides and grid_offset else {})

    def _priority(x: int, y: int) -> str | None:
        key = (int(x), int(y))
        return priority_at.get(key) or priority_unshifted.get(key)

    if any(v == "skip" for v in (*priority_at.values(), *priority_unshifted.values())):
        before = len(tiles)
        tiles = [t for t in tiles if _priority(t[0], t[1]) != "skip"]
        n_low = sum(1 for v in priority_at.values() if v == "low_res")
        print(f"  Tile overrides: skipped {before - len(tiles)} skip tiles, {n_low} low-res tiles"
              + (f" (keys shifted {grid_offset}px with the grid)" if grid_offset and human_overrides else ""))

    if args.limit:
        tiles = tiles[: args.limit]

    total = len(tiles)
    already_done = [(x, y, w, h) for x, y, w, h in tiles
                    if (out_dir / f"{x}_{y}_{w}_{h}.json").exists()]
    todo = [(x, y, w, h) for x, y, w, h in tiles
            if not (out_dir / f"{x}_{y}_{w}_{h}.json").exists()]

    print(f"  Image: {img_w}×{img_h} px → {len(tiles)} tiles "
          f"({tile_size}px, {overlap}px overlap, render={render_size}px)")
    print(f"  {len(already_done)} already done, {len(todo)} to process "
          f"(concurrency={args.concurrency})")

    if not todo:
        print("All tiles already processed — running dedup only.")

    errors: list[tuple[str, str]] = []
    total = len(tiles)

    use_row_sequence = getattr(args, "row_sequence", False)

    if use_row_sequence and todo:
        # ── Row-sequence mode: send each row as one multi-image sequence call ──
        # Groups tiles by y-band so the model sees the full horizontal strip at once.
        # This eliminates edge duplicates and allows cross-tile label assembly.
        max_frames = getattr(args, "max_row_frames", 4)
        raw_rows = group_tiles_by_row(tiles, args.tile_size, args.overlap)
        # Split any row wider than max_frames into overlapping groups of
        # max_frames, one tile of overlap and never a group inside another one.
        rows = [group for raw_row in raw_rows
                for group in group_row_frames(raw_row, max_frames)]

        # What each group has already attributed to a tile *in this run*. The
        # groups overlap by a tile, so two of them write the same tile_key, and
        # the second must add to the first rather than replace it. Scoped to the
        # run: a tile carried over from a previous run (`already_done`) is still
        # overwritten, so resuming a run means the same thing it always did.
        group_written: dict[str, list] = {}

        def emit_tile(tile_key: str, result: dict) -> None:
            result["extractions"] = merge_group_extractions(
                group_written.get(tile_key), result.get("extractions", []))
            group_written[tile_key] = result["extractions"]
            (out_dir / f"{tile_key}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2))

        todo_set = set(todo)
        row_total = len(rows)
        done_rows = [0]
        print(f"  Row-sequence mode: {len(tiles)} tiles → {row_total} calls (max {max_frames} frames/call)")

        for row_idx, row_tiles in enumerate(rows):
            # Skip rows where all tiles are already done
            row_todo = [t for t in row_tiles if t in todo_set]
            if not row_todo:
                done_rows[0] += 1
                continue

            # Load images for every tile in the row (cache → fetch)
            row_images = []
            row_order = []  # tiles in the order images were collected
            use_adaptive = getattr(args, "adaptive", False) and not local_image
            for tile in row_tiles:
                x, y, w, h = tile
                tile_key = f"{x}_{y}_{w}_{h}"
                try:
                    # The render size has to be known before the cache is asked,
                    # because it is part of the key. Under --adaptive it is data
                    # dependent, so try both sizes the density rule can return
                    # before paying for the 512 px probe that decides between
                    # them — a cached tile is still free, just not free to find.
                    tile_priority = _priority(x, y)
                    if tile_priority == "low_res":
                        rs = low_res_render
                        img = _cached_tile(tile_cache_dir, tile_key, rs)
                    elif use_adaptive:
                        img, rs = None, None
                        for candidate in (2048, 1024):
                            img = _cached_tile(tile_cache_dir, tile_key, candidate)
                            if img is not None:
                                rs = candidate
                                break
                        if rs is None:
                            preview = fetch_crop(iiif_base, x, y, w, h, size=512,
                                                 quality=iiif_quality)
                            rs = adaptive_render_size(preview, low=1024, high=2048)
                    else:
                        rs = render_size
                        img = _cached_tile(tile_cache_dir, tile_key, rs)
                    if img is None:
                        img = fetch_crop(iiif_base, x, y, w, h, size=rs,
                                         local_image=local_image, quality=iiif_quality)
                        img.save(_tile_cache_path(tile_cache_dir, tile_key, rs))
                    row_images.append(clahe(img) if clahe else img)
                    row_order.append(tile)
                except Exception as e:
                    print(f"  Row {row_idx+1}: could not fetch tile {tile_key}: {e}")
                    errors.append((tile_key, str(e)))

            if not row_images:
                continue

            coords_str = " + ".join(f"{x},{y}" for x, y, w, h in row_order)
            print(f"  Row [{row_idx+1}/{row_total}] ({coords_str}) [{len(row_images)} frames] ...",
                  end=" ", flush=True)

            # Single sequence call for all tiles in the row
            if len(row_images) == 1:
                x, y, w, h = row_order[0]
                try:
                    result = _sanitize_extractions(extract_labels(
                        image=row_images[0],
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=prompt_text,
                        schema=schema_for(args.prompt),
                        thinking=not getattr(args, 'low_thinking', False),
                        model=model,
                        log_path=log_path,
                        cache_dir=OUTPUTS_CACHE_DIR,
                    ), log_path=log_path)
                    n = len(result.get("extractions", []))
                    print(f"{n} extractions")
                    result["_meta"] = {
                        "tile_x": x, "tile_y": y, "tile_w": w, "tile_h": h,
                        "render_w": 1000, "render_h": 1000,
                        "prompt": args.prompt, "model": args.model,
                    }
                    emit_tile(f"{x}_{y}_{w}_{h}", result)
                except Exception as e:
                    print(f"ERROR {e}")
                    errors.append((f"{x}_{y}_{w}_{h}", str(e)))
            else:
                try:
                    seq_result = _sanitize_extractions(extract_labels_sequence(
                        images=row_images,
                        system_prompt=SYSTEM_PROMPT,
                        schema=schema_for(args.prompt),
                        thinking=not getattr(args, 'low_thinking', False),
                        user_prompt=prompt_text + sequence_frame_rules(len(row_images)),
                        model=model,
                        log_path=log_path,
                        cache_dir=OUTPUTS_CACHE_DIR,
                    ), log_path=log_path)
                    n = len(seq_result.get("extractions", []))
                    print(f"{n} extractions")

                    # Distribute extractions back to per-tile JSONs using frame_idx
                    per_tile: dict[int, list] = {i: [] for i in range(len(row_order))}
                    for ext in seq_result.get("extractions", []):
                        fi = min(int(ext.get("frame_idx", 0)), len(row_order) - 1)
                        per_tile[fi].append(ext)

                    for fi, (x, y, w, h) in enumerate(row_order):
                        emit_tile(f"{x}_{y}_{w}_{h}", {
                            "extractions": per_tile[fi],
                            "_meta": {
                                "tile_x": x, "tile_y": y, "tile_w": w, "tile_h": h,
                                "render_w": 1000, "render_h": 1000,
                                "prompt": args.prompt, "model": args.model,
                                "row_sequence": True,
                            },
                        })
                except Exception as e:
                    print(f"ERROR {e}")
                    for x, y, w, h in row_order:
                        errors.append((f"{x}_{y}_{w}_{h}", str(e)))

            done_rows[0] += 1

    else:
        # ── Per-tile mode (original, kept for --no-row-sequence) ──────────────
        progress_lock = threading.Lock()
        done_count = [len(already_done)]

        def process_tile(tile: tuple[int, int, int, int]) -> None:
            x, y, w, h = tile
            tile_key = f"{x}_{y}_{w}_{h}"
            json_path = out_dir / f"{tile_key}.json"

            try:
                tile_rs = low_res_render if _priority(x, y) == "low_res" else render_size
                image = _cached_tile(tile_cache_dir, tile_key, tile_rs)
                if image is None:
                    image = fetch_crop(iiif_base, x, y, w, h, size=tile_rs,
                                       local_image=local_image, quality=iiif_quality)
                    image.save(_tile_cache_path(tile_cache_dir, tile_key, tile_rs))
                if clahe:
                    image = clahe(image)

                result = _sanitize_extractions(extract_labels(
                    image=image,
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=prompt_text,
                    schema=schema_for(args.prompt),
                    thinking=not getattr(args, 'low_thinking', False),
                    model=model,
                    log_path=log_path,
                    cache_dir=OUTPUTS_CACHE_DIR,
                ), log_path=log_path)
                result["_meta"] = {
                    "tile_x": x, "tile_y": y, "tile_w": w, "tile_h": h,
                    "render_w": 1000, "render_h": 1000,
                    "prompt": args.prompt, "model": args.model,
                }
                json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
                n = len(result.get("extractions", []))

                with progress_lock:
                    done_count[0] += 1
                    print(f"[{done_count[0]}/{total}] {tile_key}: {n} extractions", flush=True)

            except Exception as e:
                with progress_lock:
                    done_count[0] += 1
                    print(f"[{done_count[0]}/{total}] {tile_key}: ERROR {e}", flush=True)
                    errors.append((tile_key, str(e)))

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            concurrent.futures.wait([executor.submit(process_tile, t) for t in todo])

    if errors:
        print(f"\n{len(errors)} tile(s) failed:")
        for k, e in errors:
            print(f"  {k}: {e}")

    # Collect all tile results and dedup into a master output
    print("\nCollecting and deduplicating all extractions ...")
    tile_results = []
    for x, y, w, h in tiles:
        json_path = out_dir / f"{x}_{y}_{w}_{h}.json"
        if not json_path.exists():
            continue
        data = json.loads(json_path.read_text())
        tile_results.append({
            "tile_x": x, "tile_y": y, "tile_w": w, "tile_h": h,
            "render_w": 1000, "render_h": 1000,
            "extractions": data.get("extractions", []),
        })

    min_conf = args.min_confidence
    # Include scout results in master dedup if they exist
    scout_path = out_dir / "scout.json"
    if scout_path.exists():
        scout_data = json.loads(scout_path.read_text())
        exts = scout_data.get("extractions", [])
        if exts:
            print(f"  Including {len(exts)} macro features from scout pass ...")
            # Wrap as a pseudo-tile result for dedup_extractions
            tile_results.append({
                "tile_x": 0, "tile_y": 0, "tile_w": img_w, "tile_h": img_h,
                "render_w": 1000, "render_h": 1000,
                "extractions": exts,
            })

    # Apply per-category confidence floors before dedup
    for tr in tile_results:
        tr["extractions"] = _apply_conf_floors(tr["extractions"], global_min=min_conf)

    deduped = dedup_extractions(tile_results, iou_threshold=0.15)
    excluded = parse_rects(getattr(args, "exclude", None) or "")
    if excluded:
        kept = [e for e in deduped if not in_rects(excluded, e["global_bbox"])]
        print(f"  Printed-index regions: dropped {len(deduped) - len(kept)} read(s) "
              f"inside {len(excluded)} region(s)")
        deduped = kept
    raw_n = sum(len(tr["extractions"]) for tr in tile_results)
    confirmed_n = sum(1 for e in deduped if e.get("tier") == "confirmed")
    uncertain_n = sum(1 for e in deduped if e.get("tier") == "uncertain")
    print(f"Dedup: {raw_n} raw → {len(deduped)} unique extractions (confirmed={confirmed_n}, uncertain={uncertain_n}, conf ≥ {min_conf})")

    master_path = out_dir / "all_extractions.json"
    master_path.write_text(json.dumps({
        "map_id": map_label,
        "run_id": out_dir.name,
        "model": model,
        # Recorded because `merge` writes the DB rows for the two-pass recipe and
        # has nothing else to read the provenance off: the passes it merges run
        # with --db off, so their prompt is written down nowhere else.
        "prompt": args.prompt,
        "n_tiles_total": total,
        "n_tiles_processed": len(tile_results),
        "n_raw": raw_n,
        "n_deduped": len(deduped),
        "extractions": [{**e, "global_bbox": list(e["global_bbox"])} for e in deduped],
    }, ensure_ascii=False, indent=2))
    print(f"Master output: {master_path}")

    if getattr(args, "db", False) and map_label != "unknown":
        from supabase_client import upsert_ocr_extractions
        # Write the DEDUPED rows. The global-space IoU/proximity dedup above already
        # collapsed overlap-band double-reads (the tiling edge problem) — writing raw
        # per-tile rows here would reintroduce them, because the unique index
        # (map_id, run_id, tile_x, tile_y, text) can only dedup within a single tile,
        # not across the two tiles that share an overlap band.
        # Key each surviving row to its winning tile's origin so the unique index
        # still gives re-run idempotency. global_bbox is already full-image px.
        tile_dims = {(x, y): (w, h) for x, y, w, h in tiles}
        db_rows = []
        for e in deduped:
            gx, gy, gw, gh = e["global_bbox"]
            tx, ty = e.get("_tile_origin", (0, 0))
            tw, th = tile_dims.get((tx, ty), (img_w, img_h))
            db_rows.append({
                "tile_x": tx, "tile_y": ty, "tile_w": tw, "tile_h": th,
                "global_x": gx, "global_y": gy, "global_w": gw, "global_h": gh,
                "category": _db_category(e.get("category", "other")),
                "text": e.get("text", ""),
                "confidence": e.get("confidence", 0),
                "rotation_deg": e.get("rotation_deg"),
                "notes": e.get("notes"),
                "model": model,
                "prompt": args.prompt,
            })
        # ponytail: two distinct same-text features on one tile collapse to one DB
        # row (shared unique key) — same ceiling the old raw path had. Fix with a
        # location suffix in the key only if it ever bites.
        n_written = upsert_ocr_extractions(map_label, out_dir.name, db_rows)
        print(f"DB: upserted {n_written} deduped rows ({raw_n} raw per-tile) to ocr_labels")

        try:
            from supabase_client import update_pipeline_status
            update_pipeline_status(map_label, "ocr_done",
                                   ocr_run_id=out_dir.name,
                                   ocr_finished_at=datetime.now(timezone.utc).isoformat())
        except Exception as e:
            print(f"[pipeline] status update skipped: {e}")

        if getattr(args, "legend", False):
            try:
                _run_legend_pass(iiif_base, img_w, img_h, scout_cartouche,
                                 local_image, map_label, out_dir.name, model,
                                 quality=("default" if local_image else iiif_quality))
            except Exception as e:
                print(f"[legend] pass failed: {e}")

    save_run_config(out_dir, {
        "map_id": map_label,
        "model": model,
        "prompt": args.prompt,
        "render_size": render_size,
        "tile_size": tile_size,
        "overlap": overlap,
        "concurrency": args.concurrency,
        "row_sequence": use_row_sequence,
        "min_confidence": min_conf,
        "crop": getattr(args, "crop", None),
        "tile_overrides": tile_overrides or None,
        "low_res_render": low_res_render if tile_overrides else None,
        "target_calls": getattr(args, "target_calls", None),
        "tile_metres": tile_metres,
        "metres_per_pixel": round(scale_fit.mean, 4) if scale_fit else None,
        "smart_grid": getattr(args, "smart_grid", False),
        "clahe": [args.clahe_clip, args.clahe_grid] if getattr(args, "clahe", False) else False,
        "prior_run": getattr(args, "prior_run", None),
        "n_tiles": total,
        "n_errors": len(errors),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    print(f"Run dir: {out_dir}")


def cmd_preview(args: argparse.Namespace) -> None:
    json_path = Path(args.output)
    if not json_path.exists():
        raise SystemExit(f"File not found: {json_path}")

    data = json.loads(json_path.read_text())
    extractions = data.get("extractions", [])

    # Try to find the cached tile image
    tile_key = json_path.stem
    cache_parts = tile_key.split("_")
    if len(cache_parts) == 4:
        x, y, w, h = [int(v) for v in cache_parts]
        iiif_base = args.iiif_base
        if not iiif_base:
            raise SystemExit(
                "Provide --iiif-base to re-fetch the tile for preview rendering"
            )
        from iiif_tiles import fetch_crop, get_image_info
        _quality = get_image_info(iiif_base).get("quality", "default")
        image = fetch_crop(iiif_base, x, y, w, h, quality=_quality)
    else:
        raise SystemExit("Cannot parse tile coordinates from filename. Provide --iiif-base.")

    preview_path = json_path.with_suffix("_preview.png")
    render_preview(image, extractions, preview_path)


# Per-category minimum confidence floors (applied before dedup).
# Streets and hydrology use a lower floor since spatial anchoring matters even
# for uncertain fragments. Legend/other noise warrants a higher bar.
# Narrowest full-sheet render the scout will look at. Below this a street name is
# a few pixels tall and the layout/OCR passes return plausible nothing.
SCOUT_MIN_WIDTH = 1024

# Narrowest overview the density pre-pass may be computed from. Not a taste
# call: measured on the 1882 Saigon cadastral, mean density of centre tiles vs
# edge tiles ran 0.019 vs 0.134 at 600px, 0.044 vs 0.129 at 1024px and 0.106 vs
# 0.140 at 1513px — inverted every time, so --auto-priority would have skipped
# exactly the tiles worth reading. Only at 2048 does it come right (0.166 vs
# 0.139). The same number is hardcoded as OVERVIEW_WIDTH in cmd_batch; this is
# the floor the scout checks before it dares propose a priority grid.
PRIORITY_MIN_OVERVIEW_WIDTH = 2048

CATEGORY_MIN_CONF: dict[str, float] = {
    "street":      0.40,
    "hydrology":   0.40,
    "place":       0.50,
    "building":    0.55,
    "institution": 0.55,
    "title":       0.50,
    "legend":      0.65,
    "other":       0.65,
}


def _apply_conf_floors(extractions: list[dict], global_min: float = 0.4) -> list[dict]:
    """Filter extractions by per-category confidence floor (or global_min, whichever is higher)."""
    out = []
    for e in extractions:
        cat = e.get("category", "other")
        floor = max(CATEGORY_MIN_CONF.get(cat, global_min), global_min)
        if e.get("confidence", 0) >= floor:
            out.append(e)
    return out


def _sanitize_extractions(result: dict, log_path: Path | None = None) -> dict:
    """Drop or clamp extractions with malformed bbox values from Gemini.

    Gemini occasionally returns bbox coordinates outside the 0-1000 normalized
    range (e.g. 55358-digit integers). These are model hallucinations — discard
    the extraction rather than propagating garbage coordinates downstream.
    Also clamps confidence to [0, 1]. Logs violation counts to sanitize.jsonl.
    """
    import json as _json
    from datetime import datetime, timezone

    clean = []
    n_dropped = 0
    for ext in result.get("extractions", []):
        bbox = ext.get("bbox_px")
        if not bbox or len(bbox) < 4:
            n_dropped += 1
            continue
        try:
            coords = [float(v) for v in bbox[:4]]
        except (TypeError, ValueError, OverflowError):
            n_dropped += 1
            continue
        if any(v < 0 or v > 10_000 for v in coords):
            n_dropped += 1
            continue
        ext["bbox_px"] = [min(max(v, 0), 1000) for v in coords]
        ext["confidence"] = min(max(float(ext.get("confidence", 0)), 0.0), 1.0)
        clean.append(ext)
    if n_dropped > 0 and log_path:
        sanitize_path = log_path.parent / "sanitize.jsonl"
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "n_dropped": n_dropped,
            "n_total": len(result.get("extractions", [])),
        }
        sanitize_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sanitize_path, "a") as f:
            f.write(_json.dumps(entry) + "\n")
    result["extractions"] = clean
    return result


def _to_global(bbox_px, tile_x, tile_y, tile_w, tile_h, render_w=1000, render_h=1000):
    """Convert tile-local bbox (0-1000 normalized) to source-image pixel coords."""
    bx, by, bw, bh = bbox_px
    sx = tile_x + bx * tile_w / render_w
    sy = tile_y + by * tile_h / render_h
    sw = bw * tile_w / render_w
    sh = bh * tile_h / render_h
    return sx, sy, sw, sh


def _iou(a, b):
    """Intersection-over-union of two (x,y,w,h) boxes in the same coord space."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(ax, bx)
    iy = max(ay, by)
    iw = min(ax + aw, bx + bw) - ix
    ih = min(ay + ah, by + bh) - iy
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _lev_ratio(a: str, b: str) -> float:
    """Normalized similarity via SequenceMatcher: 0.0 (different) → 1.0 (identical)."""
    return SequenceMatcher(None, a, b).ratio()


# Label normalisation lives in `labels.py`: `eval_metrics` needs the same
# folding to score a body pass against a sheet's printed index, and it must not
# have to import the Gemini SDK to get it. Aliased under the old names because
# this module and its tests use them throughout.
_LABEL_PREFIXES = LABEL_PREFIXES
_label_core = label_core
_fold = fold


def _syl_match(x: str, y: str, fuzzy_threshold: float) -> bool:
    """Do two folded syllables name the same thing?

    Fuzzy only above four characters. Vietnamese syllables are two to five
    letters, and at that length a character ratio says nothing: "do" against
    "duc" scores 0.80, which would merge Đường Tự Do into Đường Tự Đức. Folding
    has already absorbed the noise that fuzz is for — a dropped tone mark — so
    below five characters the syllables simply have to agree.
    """
    if x == y:
        return True
    return min(len(x), len(y)) > 4 and _lev_ratio(x, y) >= fuzzy_threshold


def _name_like(folded: str) -> bool:
    """Is this folded text a name, rather than one syllable of one?

    Two syllables, or a single one long enough to stand alone. "Trần", "Lâm" and
    "Nghé" are not names; "Catinat" and "Chợ Lớn" are.
    """
    w = folded.split()
    return len(w) > 1 or (len(w) == 1 and len(w[0]) >= 5)


def _words_similar(a: str, b: str, fuzzy_threshold: float) -> bool:
    """Same syllable count, and every syllable matches its counterpart.

    Whole-string fuzzy matching cannot do this job: "lê lợi" and "lê lai" score
    0.83 as strings — above any threshold that still joins one street read twice
    — because they differ in three characters out of twelve. Positionally, the
    second syllable is "loi" against "lai" and they are plainly two streets.
    """
    wa, wb = _fold(a).split(), _fold(b).split()
    if not wa or len(wa) != len(wb):
        return False
    return all(_syl_match(x, y, fuzzy_threshold) for x, y in zip(wa, wb))


def _text_similar(a: str, b: str, fuzzy_threshold: float = 0.75) -> bool:
    """True if two labels are the same label read twice.

    Three tests, in the order they stop being generous. Each is here because of
    a way the 1959 Saigon sheet lost real streets: "Đại Lộ Lê Lợi" matched "Đại
    Lộ Hàm Nghi" on shared words, "Đại Lộ Lê Lợi" matched "Đại Lộ Lê Lai" on
    shared characters, and "Đường Tự Do" matched "Đường Tự Đức" on a fuzzy
    three-letter syllable. Lê Lợi, Hàm Nghi, Công Lý and Phan Chu Trinh were all
    deleted as duplicates of their neighbours, and the surviving row count still
    looked right, which is why it went unnoticed.
    """
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b:
        return False
    fa, fb = _fold(a), _fold(b)
    if fa == fb or fa.replace(" ", "") == fb.replace(" ", ""):
        return True
    # One read dropped the generic prefix. Tested on whole words and on the full
    # strings, before the prefix is stripped: after stripping, "Rạch Bến Nghé"
    # and "Rạch Thị Nghè" both end in "nghe" and one contains the other.
    #
    # Both sides have to be a name in their own right: two syllables or one long
    # one (`_name_like`), and something left after the generic comes off. A bare
    # "Trần" is inside every *Trần …* street and a bare "Đường" is inside every
    # street on the sheet — and `dedup_items` and `ensemble_items` both cluster
    # by union-find, so one such row chained 43 different streets into a single
    # cluster whose winning text replaced all of them. That is how Lý Thái Tổ,
    # Tổng Đốc Phương and Lê Đại Hành went missing. Assembling genuine fragments
    # is `_spatial_join_fragments`' job, and it runs after this.
    if (
        _name_like(fa)
        and _name_like(fb)
        and _label_core(a)
        and _label_core(b)
        and (f" {fa} " in f" {fb} " or f" {fb} " in f" {fa} ")
    ):
        return True
    ca, cb = _label_core(a), _label_core(b)
    if ca and cb:
        a, b = ca, cb
        fa, fb = _fold(a), _fold(b)
        if fa == fb:
            return True
    wa, wb = fa.split(), fb.split()
    # Word overlap alone is not enough. Vietnamese street names are personal
    # names, so sharing the family name ("nguyen hue" / "nguyen trai") clears
    # 0.5 on its own, and for a two-syllable name 0.5 means exactly one syllable
    # matched — coincidence, not similarity. So: two shared syllables at least,
    # and the last one, which names the person or place, has to be among them.
    sa, sb = set(wa), set(wb)
    shared = len(sa & sb)
    if (
        shared >= 2
        and shared / max(len(sa), len(sb)) >= 0.5
        and _syl_match(wa[-1], wb[-1], fuzzy_threshold)
    ):
        return True
    return _words_similar(a, b, fuzzy_threshold)


# How far apart two boxes may sit and still be one label, as a multiple of the
# text's own height. A calibration knob: the right value depends on the sheet's
# scale and the scan resolution, neither of which the code can see. Measured on
# the 1959 Saigon sheet, 2.5 → 6.0 changes the distinct names recovered by two
# (492 → 490) and the row count by 12% — once `_text_similar` stopped merging
# different streets, this threshold only decides how many rows one street keeps.
_CLOSE_FACTOR = 4.0


def _close_px(a, b) -> float:
    """The proximity budget for two boxes carrying the same text, in source px.

    Scaled to the *short* side of the boxes — a text label's height — not the
    long one. Two reads of one street name sit within a line-height of each
    other, while scaling by the length of a 600px street label bought a 900px
    budget and swept up the next street over.
    """
    short = max(min(a[2], a[3]), min(b[2], b[3]))
    return short * _CLOSE_FACTOR


def _centroid_distance(a, b):
    """Euclidean distance between centers of two (x,y,w,h) boxes."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    acx, acy = ax + aw / 2, ay + ah / 2
    bcx, bcy = bx + bw / 2, by + bh / 2
    return math.sqrt((acx - bcx)**2 + (acy - bcy)**2)


def _colinear(a_bbox, b_bbox, angle_deg, tolerance_px=200) -> bool:
    """True if two bbox centroids are roughly aligned along the given angle."""
    ax, ay, aw, ah = a_bbox
    bx, by, bw, bh = b_bbox
    acx, acy = ax + aw / 2, ay + ah / 2
    bcx, bcy = bx + bw / 2, by + bh / 2
    angle_rad = math.radians(angle_deg)
    # Project displacement onto perpendicular axis; if small → colinear
    dx, dy = bcx - acx, bcy - acy
    perp = abs(dx * math.sin(angle_rad) - dy * math.cos(angle_rad))
    return perp < tolerance_px


def _union_bbox(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0 = min(ax, bx)
    y0 = min(ay, by)
    x1 = max(ax + aw, bx + bw)
    y1 = max(ay + ah, by + bh)
    return (x0, y0, x1 - x0, y1 - y0)


_FRENCH_CONNECTORS = frozenset(
    "de du des d la le les l au aux en sur sous vers par "
    "et ou ni car or donc or nr n°".split()
)
_STREET_PREFIXES = frozenset(
    "rue ruelle impasse passage allée allée avenue boulevard quai chemin "
    "place cour hameau route voie pont sentier".split()
)


def _is_fragment_candidate(text: str) -> bool:
    """
    True only for tokens that are likely incomplete on their own:
      - single connector word (de, du, des, la, …)
      - bare street prefix alone, without a following name (e.g. "Rue" but not "Rue Catinat")
      - single word of 1–4 characters (abbreviations, initials)

    Explicitly NOT fragments: "Rue Catinat", "Boulevard Charner", any multi-word text
    with a full prefix+name pattern — those are complete labels.
    """
    t = text.lower().strip()
    if not t:
        return False
    words = t.split()
    if len(words) == 1:
        w = words[0]
        if w in _FRENCH_CONNECTORS:
            return True
        if w in _STREET_PREFIXES or w in _LABEL_PREFIXES:
            return True
        if len(w) <= 4:
            return True
    return False


def _spatial_join_fragments(items: list[dict], proximity_px: float = 700, angle_tol: float = 20) -> list[dict]:
    """
    Join word-fragments on the same axis into complete labels.

    Works on V1-style data where items have no edge-continuation notes.
    Groups items by rotation angle and spatial collinearity; sorts by position;
    concatenates texts in reading order.

    Only joins items where at least one is a fragment candidate (short or connector-word).
    """
    n = len(items)
    if n < 2:
        return items

    # Union-Find
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        ti = items[i].get("text", "").strip()
        ang_i = float(items[i].get("rotation_deg") or 0)
        bbox_i = items[i]["global_bbox"]

        for j in range(i + 1, n):
            tj = items[j].get("text", "").strip()

            # Skip if texts are similar (dedup handles those)
            if _text_similar(ti, tj):
                continue

            # At least one must be a fragment candidate
            if not _is_fragment_candidate(ti) and not _is_fragment_candidate(tj):
                continue

            ang_j = float(items[j].get("rotation_deg") or 0)
            # Angles must be compatible (same orientation modulo 180°)
            diff = abs(ang_i - ang_j) % 180
            if diff > angle_tol and diff < (180 - angle_tol):
                continue

            bbox_j = items[j]["global_bbox"]
            dist = _centroid_distance(bbox_i, bbox_j)
            if dist > proximity_px:
                continue

            avg_angle = (ang_i + ang_j) / 2
            max_dim = max(bbox_i[2], bbox_i[3], bbox_j[2], bbox_j[3])
            tol = max(150, max_dim * 0.8)
            if not _colinear(bbox_i, bbox_j, avg_angle, tolerance_px=tol):
                continue

            union(i, j)

    # Group by root
    clusters: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(i)

    result: list[dict] = []
    for root, members in clusters.items():
        if len(members) == 1:
            result.append(items[members[0]])
            continue

        # Sort members spatially (left→right or top→bottom by angle)
        avg_angle = sum(float(items[m].get("rotation_deg") or 0) for m in members) / len(members)
        is_horiz = abs(avg_angle % 180) < 45 or abs(avg_angle % 180) > 135

        def sort_key(m: int):
            bx, by, bw, bh = items[m]["global_bbox"]
            return bx + bw / 2 if is_horiz else by + bh / 2

        members_sorted = sorted(members, key=sort_key)

        merged_text = " ".join(items[m].get("text", "").strip() for m in members_sorted)
        merged_bbox = items[members_sorted[0]]["global_bbox"]
        for m in members_sorted[1:]:
            merged_bbox = _union_bbox(merged_bbox, items[m]["global_bbox"])
        merged_conf = max(items[m].get("confidence", 0) for m in members_sorted)
        merged_item = {
            **items[members_sorted[0]],
            "text": merged_text,
            "global_bbox": merged_bbox,
            "confidence": merged_conf,
            "notes": f"joined {len(members)} fragments (spatial)",
        }
        result.append(merged_item)

    return result


_EDGE_RE = re.compile(r"(left|right|top|bottom)")


def _parse_exit_edges(notes: str) -> set[str]:
    """Extract tile edges a fragment continues toward from its notes field."""
    n = notes.lower()
    if "continues" not in n and "outside" not in n and "cut" not in n:
        return set()
    return set(_EDGE_RE.findall(n))


_COMPLEMENTARY_EDGES = {
    ("right", "left"), ("left", "right"),
    ("top", "bottom"), ("bottom", "top"),
}


def _edges_compatible(edges_a: set[str], edges_b: set[str]) -> bool:
    """True if fragment A exits toward fragment B (complementary edges)."""
    for ea in edges_a:
        for eb in edges_b:
            if (ea, eb) in _COMPLEMENTARY_EDGES:
                return True
    return False


def _spatial_concat(item_a: dict, item_b: dict, edges_a: set[str], edges_b: set[str]) -> str:
    """Concatenate fragment texts in spatial order along label axis."""
    text_a = item_a.get("text", "").strip()
    text_b = item_b.get("text", "").strip()
    bbox_a, bbox_b = item_a["global_bbox"], item_b["global_bbox"]
    cx_a, cy_a = bbox_a[0] + bbox_a[2] / 2, bbox_a[1] + bbox_a[3] / 2
    cx_b, cy_b = bbox_b[0] + bbox_b[2] / 2, bbox_b[1] + bbox_b[3] / 2
    horizontal = bool(edges_a & {"left", "right"}) or bool(edges_b & {"left", "right"})
    if horizontal:
        first, second = (text_a, text_b) if cx_a <= cx_b else (text_b, text_a)
    else:
        first, second = (text_a, text_b) if cy_a <= cy_b else (text_b, text_a)
    return f"{first} {second}"


def dedup_items(items, iou_threshold=0.25):
    """Core deduplication logic for a flat list of items with 'global_bbox'."""
    if not items:
        return []

    # ── Fast pass: exact text + centroid within 150px → keep higher-confidence ──
    keep = [True] * len(items)
    seen_text: dict[str, int] = {}
    for i, item in enumerate(items):
        t = item.get("text", "").strip().lower()
        if not t:
            continue
        if t in seen_text:
            j = seen_text[t]
            if not keep[j]:
                seen_text[t] = i
                continue
            if _centroid_distance(items[i]["global_bbox"], items[j]["global_bbox"]) < 150:
                if item.get("confidence", 0) > items[j].get("confidence", 0):
                    keep[j] = False
                    seen_text[t] = i
                else:
                    keep[i] = False
        else:
            seen_text[t] = i

    # Dedup: suppress lower-confidence item when IoU/Proximity + text similarity match
    for i in range(len(items)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(items)):
            if not keep[j]:
                continue

            bbox_i = items[i]["global_bbox"]
            bbox_j = items[j]["global_bbox"]

            # Text similarity check first
            text_i = items[i].get("text", "")
            text_j = items[j].get("text", "")
            if not _text_similar(text_i, text_j):
                continue

            # Spatial check: overlap (IoU) OR center-point proximity (relative to size)
            iou = _iou(bbox_i, bbox_j)
            dist = _centroid_distance(bbox_i, bbox_j)
            is_close = dist < _close_px(bbox_i, bbox_j)

            if iou >= iou_threshold or is_close:
                # 0. Calculate textual substring overlap for prioritizing fragments
                is_sub = (text_i.lower() in text_j.lower() or text_j.lower() in text_i.lower())

                # 1. When scout and tile overlap, prefer tile (tighter bbox).
                # Scout bboxes cover 30-70% of the map and are spatially useless.
                source_i = items[i].get("source", "tile")
                source_j = items[j].get("source", "tile")

                if source_i != source_j:
                    if source_i == "scout":
                        keep[i] = False
                        break
                    else:
                        keep[j] = False
                elif is_sub and len(text_i) != len(text_j):
                    # 2. If one is a substring of the other, prefer the longer one 
                    #    unless its confidence is significantly lower (> 0.2 difference).
                    ci = items[i].get("confidence", 0)
                    cj = items[j].get("confidence", 0)
                    
                    i_is_longer = len(text_i) > len(text_j)
                    if i_is_longer:
                        # Keep i (longer) if it's reasonably confident compared to j
                        if ci >= (cj - 0.2):
                            keep[j] = False
                        else:
                            keep[i] = False
                            break
                    else:
                        # Keep j (longer) if it's reasonably confident compared to i
                        if cj >= (ci - 0.2):
                            keep[i] = False
                            break
                        else:
                            keep[j] = False
                else:
                    # 3. Standard confidence-based priority
                    ci = items[i].get("confidence", 0)
                    cj = items[j].get("confidence", 0)
                    if ci > cj:
                        keep[j] = False
                    elif cj > ci:
                        keep[i] = False
                        break
                    else:
                        # Tie: keep longer string
                        if len(text_i) >= len(text_j):
                            keep[j] = False
                        else:
                            keep[i] = False
                            break

    survivors = [items[k] for k in range(len(items)) if keep[k]]

    # ── Fragment assembly pass ────────────────────────────────────────────────
    # Merge pairs where v6 transcription-only mode returns fragments ("continues...",
    # "fragment") that belong to the same label on adjacent tiles.
    frag_keep = [True] * len(survivors)
    for i in range(len(survivors)):
        if not frag_keep[i]:
            continue
        notes_i = (survivors[i].get("notes") or "").lower()
        is_frag_i = "fragment" in notes_i or "continues" in notes_i
        if not is_frag_i:
            continue
        text_i = survivors[i].get("text", "").strip()
        angle_i = survivors[i].get("rotation_deg", 0)
        for j in range(i + 1, len(survivors)):
            if not frag_keep[j]:
                continue
            notes_j = (survivors[j].get("notes") or "").lower()
            is_frag_j = "fragment" in notes_j or "continues" in notes_j
            if not is_frag_j:
                continue
            text_j = survivors[j].get("text", "").strip()
            angle_j = survivors[j].get("rotation_deg", 0)
            avg_angle = (angle_i + angle_j) / 2

            # Text must be compatible: one contains the other, or they share a word
            t_i, t_j = text_i.lower(), text_j.lower()
            words_i, words_j = set(t_i.split()), set(t_j.split())
            text_compat = (t_i in t_j or t_j in t_i or bool(words_i & words_j))

            spatial_only = False
            if not text_compat:
                # Spatial-only merge: both have edge-continuation notes pointing
                # at complementary edges and come from different tiles
                edges_i = _parse_exit_edges(notes_i)
                edges_j = _parse_exit_edges(notes_j)
                origin_i = survivors[i].get("_tile_origin")
                origin_j = survivors[j].get("_tile_origin")
                if (edges_i and edges_j
                        and _edges_compatible(edges_i, edges_j)
                        and origin_i is not None and origin_i != origin_j
                        and _centroid_distance(survivors[i]["global_bbox"],
                                               survivors[j]["global_bbox"]) < 3000):
                    spatial_only = True
                else:
                    continue

            if not _colinear(survivors[i]["global_bbox"], survivors[j]["global_bbox"],
                             avg_angle, tolerance_px=200):
                continue

            if spatial_only:
                edges_i = _parse_exit_edges(notes_i)
                edges_j = _parse_exit_edges(notes_j)
                merged_text = _spatial_concat(survivors[i], survivors[j], edges_i, edges_j)
                merge_note = "assembled from edge fragments (spatial)"
            else:
                merged_text = text_i if len(text_i) >= len(text_j) else text_j
                merge_note = "assembled from fragments"

            merged_bbox = _union_bbox(survivors[i]["global_bbox"], survivors[j]["global_bbox"])
            merged_conf = max(survivors[i].get("confidence", 0), survivors[j].get("confidence", 0))
            survivors[i] = {
                **survivors[i],
                "text": merged_text,
                "global_bbox": merged_bbox,
                "confidence": merged_conf,
                "notes": merge_note,
            }
            frag_keep[j] = False

    result = [survivors[k] for k in range(len(survivors)) if frag_keep[k]]

    # ── Confidence tier tagging ───────────────────────────────────────────────
    # confirmed ≥ 0.7 | uncertain 0.4–0.7 | (below 0.4 already filtered out above)
    for item in result:
        conf = item.get("confidence", 0)
        item["tier"] = "confirmed" if conf >= 0.7 else "uncertain"
        notes = (item.get("notes") or "").lower()
        item["requires_review"] = conf < 0.7 or "uncertain:" in notes

    return result


def group_tiles_by_row(tiles, tile_size, overlap):
    """Group tiles by y-band (same grid row). Returns list of rows, each a list of tiles sorted left→right."""
    step = tile_size - overlap
    rows: dict[int, list] = {}
    for tile in tiles:
        x, y, w, h = tile
        row_idx = round(y / step) if step > 0 else 0
        rows.setdefault(row_idx, []).append(tile)
    return [sorted(row, key=lambda t: t[0]) for row in sorted(rows.values(), key=lambda r: r[0][1])]


def group_row_frames(row, max_frames):
    """Cut one grid row into the overlapping frame groups of a row-sequence call.

    Consecutive groups share exactly one tile on purpose: that is what lets the
    model assemble a label printed across a tile seam, which is the whole point
    of row-sequence mode. What a group must never be is wholly contained in the
    group before it — it costs a call, tells us nothing new, and (before the
    write merged) its rows replaced the ones the earlier group had read for the
    tiles they share.

    `range(0, len(row), max_frames - 1)` did exactly that on any row whose
    length is one more than a multiple of the step. A 7-tile row at
    `max_frames=4` came out `[0:4] [3:7] [6:7]`: the third group is a single
    tile already inside the second, and on the 1882 sheet that tile is the
    402 px right-edge sliver rendered 1024x6113 — a degenerate frame that
    returned 0 extractions on all five of the calls it was paid for, and then
    wiped what the 4-frame call had attributed to it
    (`work/cleanup/F-1882-regate.md`).

    Here the window advances by `max_frames - 1` and stops as soon as it has
    reached the end of the row, so every group ends strictly further right than
    the one before it and no group can contain another. A short tail is a real
    group with at least one tile the previous group never saw.
    """
    row = list(row)
    n = len(row)
    if n == 0:
        return []
    if max_frames < 2:
        # Degenerate by request (`--max-row-frames 1`): one frame per call, and
        # there is no overlap to preserve.
        return [[t] for t in row]
    if n <= max_frames:
        return [row]
    step = max_frames - 1
    groups = []
    start = 0
    while True:
        end = min(start + max_frames, n)
        groups.append(row[start:end])
        if end >= n:
            return groups
        start += step


def _ext_identity(ext):
    """What makes two readings of the same label the same row: its text and its
    box, to the pixel. Deliberately not a fuzzy match — `dedup_items` owns that,
    downstream and across the whole sheet."""
    bbox = ext.get("bbox_px") or []
    try:
        box = tuple(round(float(v)) for v in bbox[:4])
    except (TypeError, ValueError):
        box = ()
    return (str(ext.get("text", "")).strip().lower(), box)


def merge_group_extractions(previous, new):
    """Union two groups' readings of one shared tile, the earlier one first.

    Row groups overlap by one tile, so a shared tile is read twice in two
    different frame contexts, and both readings were paid for. The write used to
    be an unconditional `write_text` per frame, so the later group replaced the
    earlier group's rows for that tile — and when the later group was the empty
    trailing sliver above, an empty list replaced a good reading. Replayed out
    of `outputs/.cache` on the 1882 sheet: the model returned 362 extractions on
    pass 2 and 284 reached disk, 78 of them (22%) discarded; pass 1 was 315 to
    263.

    Union rather than "keep the longer list", because neither frame context is
    authoritative and near-identical boxes from overlapping frames are exactly
    what `dedup_items` already merges for every other overlapping tile on the
    sheet. Only a row identical in text *and* box is dropped, which is the one
    case where the second reading adds nothing at all. An empty `new` is
    therefore a no-op, which is the property that matters.
    """
    if not previous:
        return list(new)
    merged = list(previous)
    seen = {_ext_identity(e) for e in merged}
    for ext in new:
        identity = _ext_identity(ext)
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(ext)
    return merged


def dedup_extractions(tile_results, iou_threshold=0.25):
    """Merge duplicate detections from overlapping tiles.

    tile_results: list of dicts with keys:
        tile_x, tile_y, tile_w, tile_h, render_w, render_h, extractions

    Returns list of dicts: {text, category, language, global_bbox, confidence, notes}
    where global_bbox = (x, y, w, h) in source image pixel coords.
    """
    # Build flat list with global coords
    items = []
    for tr in tile_results:
        rw, rh = tr["render_w"], tr["render_h"]
        for ext in tr["extractions"]:
            bbox = ext.get("bbox_px")
            if not bbox or len(bbox) < 4:
                continue
            gx, gy, gw, gh = _to_global(
                bbox, tr["tile_x"], tr["tile_y"], tr["tile_w"], tr["tile_h"], rw, rh
            )
            items.append({
                **ext,
                "global_bbox": (gx, gy, gw, gh),
                "_tile_origin": (tr["tile_x"], tr["tile_y"]),
            })

    return dedup_items(items, iou_threshold)


def cmd_stitch(args: argparse.Namespace) -> None:
    """Composite multiple tiles into one image with all bboxes in global coords."""
    from PIL import Image as PILImage, ImageDraw, ImageFont

    # Resolve iiif_base for fetching tiles
    iiif_base = args.iiif_base
    if not iiif_base and args.map_id:
        iiif_base = get_iiif_base_from_supabase(args.map_id)

    iiif_quality = "default"
    if iiif_base:
        try:
            iiif_quality = get_image_info(iiif_base).get("quality", "default")
        except Exception:
            pass

    map_label = args.map_id or "unknown"
    out_dir = make_run_dir(map_label, getattr(args, "run_id", None))
    tile_cache_dir = OUTPUTS_DIR / map_label
    tile_cache_dir.mkdir(parents=True, exist_ok=True)

    # Parse crops
    crop_list = [parse_crop(c) for c in args.crops.split(";")]

    COLORS = {
        "street": (220, 50, 50),
        "hydrology": (50, 80, 220),
        "place": (50, 130, 220),
        "building": (50, 200, 50),
        "institution": (210, 140, 30),
        "legend": (160, 50, 210),
        "title": (50, 200, 200),
        "other": (160, 160, 160),
    }

    render_size = args.render_size

    # Determine global pixel bounds of all tiles (in source coords)
    all_x = [x for x, y, w, h in crop_list]
    all_y = [y for x, y, w, h in crop_list]
    x_min = min(all_x)
    y_min = min(all_y)
    x_max = max(x + w for x, y, w, h in crop_list)
    y_max = max(y + h for x, y, w, h in crop_list)
    total_src_w = x_max - x_min
    total_src_h = y_max - y_min

    # Stitch canvas is always 2048px wide regardless of tile render resolution
    canvas_w = 2048
    scale = canvas_w / total_src_w
    canvas_h = int(total_src_h * scale)

    canvas = PILImage.new("RGB", (canvas_w, canvas_h), (240, 235, 225))
    draw = ImageDraw.Draw(canvas)

    print(f"Stitching {len(crop_list)} tiles into {canvas_w}×{canvas_h} composite ...")

    prompt_text = PROMPTS.get(args.prompt, PROMPTS[DEFAULT_PROMPT])
    log_path = out_dir / "calls.jsonl"
    use_sequence = getattr(args, "sequence", False)
    tile_images: dict[str, Image.Image] = {}

    # ── Phase 1: fetch all tile images (cached at map level, shared across runs) ─
    for crop in crop_list:
        tx, ty, tw, th = crop
        tile_key = f"{tx}_{ty}_{tw}_{th}"
        adaptive = getattr(args, "adaptive", False)
        rs = None if adaptive else render_size
        # Map-level cache first, then the run dir (legacy layout).
        img = _cached_tile(tile_cache_dir, tile_key, rs) if rs else (
            _cached_tile(tile_cache_dir, tile_key, 2048)
            or _cached_tile(tile_cache_dir, tile_key, 1024)
        )
        if img is None:
            legacy = out_dir / f"{tile_key}_tile.png"
            if legacy.exists():
                img = PILImage.open(legacy).convert("RGB")

        if img is not None:
            tile_images[tile_key] = img
        elif iiif_base:
            print(f"  Fetching tile {tx},{ty},{tw},{th} ...")
            if rs is None:
                preview = fetch_crop(iiif_base, tx, ty, tw, th, size=512, quality=iiif_quality)
                rs = adaptive_render_size(preview)
                print(f"    density={estimate_density(preview):.2f} → {rs}px", end=" ")
            img = fetch_crop(iiif_base, tx, ty, tw, th, size=rs, quality=iiif_quality)
            img.save(_tile_cache_path(tile_cache_dir, tile_key, rs))
            tile_images[tile_key] = img
        else:
            print(f"  No image for tile {tile_key} — skipping")

    # ── Phase 2: paste all tiles onto canvas ──────────────────────────────────
    for crop in crop_list:
        tx, ty, tw, th = crop
        tile_key = f"{tx}_{ty}_{tw}_{th}"
        if tile_key not in tile_images:
            continue
        tile_img = tile_images[tile_key]
        paste_x = int((tx - x_min) * scale)
        paste_y = int((ty - y_min) * scale)
        paste_w = int(tw * scale)
        paste_h = int(th * scale)
        resized = tile_img.resize((paste_w, paste_h), PILImage.LANCZOS)
        canvas.paste(resized, (paste_x, paste_y))

    # ── Phase 3: run OCR ──────────────────────────────────────────────────────
    tile_results = []

    if use_sequence and len(crop_list) >= 2:
        # Group tiles into row-sized batches — one API call per row.
        # With grid_cols=3 and 6 tiles: 2 calls (row 0: tiles 0-2, row 1: tiles 3-5).
        # Maximises images-per-call to stay within RPD while TPM has headroom.
        cols = args.grid_cols if (hasattr(args, "grid_cols") and args.grid_cols) else len(crop_list)
        groups = [crop_list[i:i + cols] for i in range(0, len(crop_list), cols)]

        for grp_idx, group in enumerate(groups):
            # Cache key from all tile origins in this group
            grp_key = "seq_" + "__".join(f"{x}_{y}" for x, y, w, h in group)
            grp_json = out_dir / f"{grp_key}.json"

            if grp_json.exists():
                result = json.loads(grp_json.read_text())
                n = len(result.get("extractions", []))
                coords = " + ".join(f"{x},{y}" for x, y, w, h in group)
                print(f"  Group {grp_idx+1}/{len(groups)} ({coords}): loaded {n} extractions")
            else:
                coords = " + ".join(f"{x},{y}" for x, y, w, h in group)
                imgs = [tile_images[f"{tx}_{ty}_{tw}_{th}"]
                        for tx, ty, tw, th in group
                        if f"{tx}_{ty}_{tw}_{th}" in tile_images]
                if not imgs:
                    print(f"  Group {grp_idx+1}: no images, skipping")
                    continue
                print(f"  Group {grp_idx+1}/{len(groups)} ({coords}) [{len(imgs)} frames] ...", end=" ", flush=True)
                try:
                    result = extract_labels_sequence(
                        images=imgs,
                        system_prompt=SYSTEM_PROMPT,
                        schema=schema_for(args.prompt),
                        thinking=not getattr(args, 'low_thinking', False),
                        user_prompt=prompt_text + sequence_frame_rules(len(imgs)),
                        model=args.model,
                        log_path=log_path,
                    )
                except Exception as e:
                    if "429" in str(e) or "QUOTA" in str(e).upper() or "EXHAUSTED" in str(e).upper():
                        print(f"quota exceeded — skipping remaining groups (re-run when quota resets)")
                        break
                    raise
                n = len(result.get("extractions", []))
                print(f"{n} extractions")
                grp_json.write_text(json.dumps(result, ensure_ascii=False, indent=2))

            # Map frame_idx back to source tile coords
            # render_w/h are always 1000 — Gemini returns 0-1000 normalized coords
            for ext in result.get("extractions", []):
                frame_idx = ext.get("frame_idx", 0)
                frame_idx = min(frame_idx, len(group) - 1)
                tx, ty, tw, th = group[frame_idx]
                tile_results.append({
                    "tile_x": tx, "tile_y": ty, "tile_w": tw, "tile_h": th,
                    "render_w": 1000, "render_h": 1000,
                    "extractions": [ext],
                })
    else:
        # Per-tile OCR (original mode)
        for crop in crop_list:
            tx, ty, tw, th = crop
            tile_key = f"{tx}_{ty}_{tw}_{th}"
            json_path = out_dir / f"{tile_key}.json"
            if tile_key not in tile_images:
                continue
            tile_img = tile_images[tile_key]

            if json_path.exists():
                result = json.loads(json_path.read_text())
            else:
                print(f"  Running OCR on tile {tile_key} ...", end=" ", flush=True)
                result = extract_labels(
                    image=tile_img,
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=prompt_text,
                    schema=schema_for(args.prompt),
                    thinking=not getattr(args, 'low_thinking', False),
                    model=args.model,
                    log_path=log_path,
                )
                n = len(result.get("extractions", []))
                print(f"{n} extractions")
                result["_meta"] = {
                    "tile_x": tx, "tile_y": ty, "tile_w": tw, "tile_h": th,
                    "render_w": 1000, "render_h": 1000,
                }
                json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))

            tile_results.append({
                "tile_x": tx, "tile_y": ty, "tile_w": tw, "tile_h": th,
                "render_w": 1000, "render_h": 1000,
                "extractions": result.get("extractions", []),
            })

    # Draw tile boundary lines (before bboxes so they appear underneath)
    for tx, ty, tw, th in crop_list:
        bx = int((tx - x_min) * scale)
        by = int((ty - y_min) * scale)
        bw = int(tw * scale)
        bh = int(th * scale)
        draw.rectangle([bx, by, bx + bw, by + bh], outline=(0, 0, 200), width=1)

    # Dedup and draw all bboxes in global canvas coordinates
    # Filter low-confidence extractions before dedup
    min_conf = getattr(args, "min_confidence", 0.4)
    for tr in tile_results:
        tr["extractions"] = [
            e for e in tr["extractions"] if e.get("confidence", 1.0) >= min_conf
        ]

    deduped = dedup_extractions(tile_results, iou_threshold=0.15)
    before = sum(len(tr["extractions"]) for tr in tile_results)
    print(f"Dedup: {before} raw → {len(deduped)} after removing duplicates")

    for ext in deduped:
        gx, gy, gw, gh = ext["global_bbox"]
        cx = int((gx - x_min) * scale)
        cy = int((gy - y_min) * scale)
        cw = max(int(gw * scale), 4)
        ch = max(int(gh * scale), 4)

        cat = ext.get("category", "other")
        color = COLORS.get(cat, COLORS["other"])
        draw.rectangle([cx, cy, cx + cw, cy + ch], outline=color, width=2)
        label = ext.get("text", "")[:35]
        lx, ly = cx + 2, cy - 13 if cy > 13 else cy + 2
        lw_est = len(label) * 6
        draw.rectangle([lx - 1, ly - 1, lx + lw_est, ly + 11], fill=(0, 0, 0))
        draw.text((lx, ly), label, fill=color)

    out_path = out_dir / f"stitch_{'_'.join(f'{x}_{y}' for x,y,w,h in crop_list)}.png"
    canvas.save(out_path)
    print(f"Stitched preview: {out_path}")

    save_run_config(out_dir, {
        "map_id": map_label,
        "model": args.model,
        "prompt": args.prompt,
        "render_size": args.render_size,
        "sequence": getattr(args, "sequence", False),
        "grid_cols": getattr(args, "grid_cols", 0),
        "crops": args.crops,
        "n_raw": before,
        "n_deduped": len(deduped),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def ensemble_items(items: list[dict]) -> list[dict]:
    """Merge the same label seen by several passes into one row.

    `dedup_items` keeps the higher self-reported confidence, which is fine inside
    one run and wrong across runs: one prompt hands out 1.00 on a box at IoU 0.06
    and the union of four runs scored *lower* than the best single run (38/43 vs
    39). Agreement is the signal that survives a prompt change, so here a cluster
    is the same label (text-similar and overlapping or close), its text is the
    spelling most passes wrote (tie → longest) and its box is the member that
    overlaps the other members most. Measured 2026-09-08: 40/43 whether two or
    four runs go in, where dedup_items ran 40 → 39 → 38 as runs were added.
    Each item needs `text`, `global_bbox` and `_run`.
    """
    n = len(items)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if not _text_similar(items[i]["text"], items[j]["text"]):
                continue
            a, b = items[i]["global_bbox"], items[j]["global_bbox"]
            if _iou(a, b) >= 0.25 or _centroid_distance(a, b) < _close_px(a, b):
                parent[find(i)] = find(j)

    clusters: dict[int, list[dict]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(items[i])

    out = []
    for members in clusters.values():
        texts = Counter(m["text"].strip() for m in members)
        top = max(texts.values())
        text = max((t for t, c in texts.items() if c == top), key=len)
        pool = [m for m in members if m["text"].strip() == text] if len(members) > 1 else members
        best = max(pool, key=lambda m: sum(
            _iou(m["global_bbox"], o["global_bbox"]) for o in members if o is not m))
        out.append({
            **best,
            "text": text,
            "confidence": max(m.get("confidence", 0) for m in members),
            "n_passes": len({m.get("_run") for m in members}),
        })
    return out


def cmd_merge(args: argparse.Namespace) -> None:
    """Vote-merge several runs of one map into a new run directory (and optionally the DB)."""
    from supabase_client import upsert_ocr_extractions

    run_ids = [r.strip() for r in args.runs.split(",") if r.strip()]
    if len(run_ids) < 2:
        raise SystemExit("--runs needs at least two run ids")
    runs_dir = OUTPUTS_DIR / args.map_id / "runs"
    items: list[dict] = []
    for rid in run_ids:
        path = runs_dir / rid / "all_extractions.json"
        if not path.exists():
            raise SystemExit(f"no all_extractions.json for run {rid!r} under {runs_dir}")
        data = json.loads(path.read_text())
        # Provenance lives on the run manifest, not on the extractions: a tile
        # result has no model or prompt field. Reading `e.get("model")` here is
        # what wrote every merged row with a null model and prompt="merge" until
        # 2026-09-08, which made EVAL-BASELINE's one rule — compare runs by what
        # they actually used — unenforceable for anything the queue ran.
        run_model = data.get("model")
        run_prompt = data.get("prompt")
        if not run_prompt:
            print(f"  warning: run {rid!r} has no prompt recorded (written before 2026-09-08); "
                  f"its rows will carry a null prompt")
        for e in data.get("extractions", []):
            if not e.get("global_bbox"):
                continue
            items.append({**e, "global_bbox": tuple(e["global_bbox"]),
                          "_tile_origin": tuple(e.get("_tile_origin") or (0, 0)), "_run": rid,
                          "_model": run_model, "_prompt": run_prompt})
    merged = ensemble_items(items)
    agreed = sum(1 for e in merged if e.get("n_passes", 1) > 1)
    print(f"{len(run_ids)} runs, {len(items)} labels → {len(merged)} merged ({agreed} seen by more than one pass)")

    out_dir = runs_dir / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "all_extractions.json").write_text(json.dumps({
        "map_id": args.map_id,
        "run_id": args.run_id,
        "merged_from": run_ids,
        "n_raw": len(items),
        "n_deduped": len(merged),
        "extractions": [{**e, "global_bbox": list(e["global_bbox"]),
                         "_tile_origin": list(e["_tile_origin"])} for e in merged],
    }, ensure_ascii=False, indent=2))
    print(f"Master output: {out_dir / 'all_extractions.json'}")

    if args.db:
        db_rows = []
        for e in merged:
            gx, gy, gw, gh = e["global_bbox"]
            tx, ty = e["_tile_origin"]
            db_rows.append({
                "tile_x": tx, "tile_y": ty, "tile_w": args.tile_size, "tile_h": args.tile_size,
                "global_x": gx, "global_y": gy, "global_w": gw, "global_h": gh,
                # Same translation as the batch path: merge reads the raw run
                # files, which now carry the model's own `index_key`.
                "category": _db_category(e.get("category", "other")),
                "text": e.get("text", ""),
                "confidence": e.get("confidence", 0),
                "rotation_deg": e.get("rotation_deg"),
                "notes": ((e.get("notes") or "") + f" merged:{e['_run']} passes={e.get('n_passes', 1)}").strip(),
                "model": e.get("_model"),
                # The winning pass's prompt, with the merge recorded beside it
                # rather than in place of it.
                "prompt": e.get("_prompt"),
            })
        n_written = upsert_ocr_extractions(args.map_id, args.run_id, db_rows)
        print(f"DB: upserted {n_written} merged rows to ocr_labels")
        try:
            from supabase_client import update_pipeline_status
            update_pipeline_status(args.map_id, "ocr_done", ocr_run_id=args.run_id,
                                   ocr_finished_at=datetime.now(timezone.utc).isoformat())
        except Exception as e:
            print(f"[pipeline] status update skipped: {e}")


def cmd_dedup(args: argparse.Namespace) -> None:
    """Check and deduplicate existing labels."""
    items = []

    if args.local:
        local_dir = Path(args.local)
        if not local_dir.is_dir():
             raise SystemExit(f"Local directory not found: {local_dir}")
        print(f"Reading local .json files from {local_dir} ...")
        json_files = list(local_dir.glob("*.json"))
        # Exclude master outputs
        json_files = [f for f in json_files if "_" in f.stem and f.stem[0].isdigit()]
        
        tile_results = []
        for f in json_files:
            try:
                data = json.loads(f.read_text())
                parts = f.stem.split("_")
                tile_results.append({
                    "tile_x": int(parts[0]), "tile_y": int(parts[1]),
                    "tile_w": int(parts[2]), "tile_h": int(parts[3]),
                    "render_w": 1000, "render_h": 1000,
                    "extractions": data.get("extractions", []),
                })
            except Exception as e:
                print(f"  Error reading {f.name}: {e}")

        # Use the existing wrapper to convert to items
        for tr in tile_results:
            rw, rh = tr["render_w"], tr["render_h"]
            for ext in tr["extractions"]:
                bbox = ext.get("bbox_px")
                if not bbox: continue
                gx, gy, gw, gh = _to_global(bbox, tr["tile_x"], tr["tile_y"], tr["tile_w"], tr["tile_h"], rw, rh)
                items.append({**ext, "global_bbox": (gx, gy, gw, gh), "_tile_origin": (tr["tile_x"], tr["tile_y"])})

    elif args.db:
        if not args.map_id:
            raise SystemExit("Provide --map-id for DB fetch")
        from supabase_client import fetch_ocr_extractions
        print(f"Fetching labels for map {args.map_id} from Supabase ...")
        items = fetch_ocr_extractions(args.map_id, args.run_id)
        for item in items:
            item.setdefault("_tile_origin", (item.get("tile_x"), item.get("tile_y")))
    else:
        raise SystemExit("Provide --local <dir> or --db")

    if not items:
        print("No labels found to deduplicate.")
        return

    raw_n = len(items)
    # Filter by confidence and valid spatial data
    items = [
        i for i in items 
        if i.get("confidence", 1.0) >= args.min_confidence 
        and i.get("global_bbox") 
        and all(c is not None for c in i["global_bbox"])
    ]
    filtered_n = len(items)

    print(f"  Processing {filtered_n} labels (min_conf={args.min_confidence}, raw={raw_n})")
    
    deduped = dedup_items(items, iou_threshold=args.iou)
    
    confirmed = [e for e in deduped if e.get("tier") == "confirmed"]
    uncertain = [e for e in deduped if e.get("tier") == "uncertain"]

    print(f"\nDeduplication Result:")
    print(f"  Raw count (filtered): {filtered_n}")
    print(f"  Unique count:         {len(deduped)}  (confirmed={len(confirmed)}, uncertain={len(uncertain)})")
    print(f"  Reduction:            {filtered_n - len(deduped)} labels merged ({(1 - len(deduped)/filtered_n)*100:.1f}%)")

    if deduped:
        print("\nConfirmed labels (conf ≥ 0.7):")
        for e in confirmed[:10]:
            print(f"  - {e.get('text', '')[:40]} [{e.get('category', 'other')}] (conf={e.get('confidence', 0):.2f})")
        if len(confirmed) > 10:
            print(f"  ... and {len(confirmed) - 10} more")
        if uncertain:
            print(f"\nUncertain labels (0.4–0.7):")
            for e in uncertain[:5]:
                print(f"  ? {e.get('text', '')[:40]} [{e.get('category', 'other')}] (conf={e.get('confidence', 0):.2f}) — {(e.get('notes') or '')[:50]}")
            if len(uncertain) > 5:
                print(f"  ... and {len(uncertain) - 5} more")

    # Save a preview JSON
    out_name = f"dedup_preview_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    if args.local:
        out_path = Path(args.local) / out_name
    else:
        out_path = Path(out_name)
    
    out_path.write_text(json.dumps({
        "map_id": args.map_id or "unknown",
        "n_raw": filtered_n,
        "n_deduped": len(deduped),
        "extractions": [{**e, "global_bbox": list(e["global_bbox"])} for e in deduped]
    }, indent=2, ensure_ascii=False))
    print(f"\nResult saved to: {out_path}")

    if args.apply:
        if not args.map_id:
            raise SystemExit("Provide --map-id for --apply")
        
        if not args.user_id:
            raise SystemExit("Provide --user-id for --apply (pins need an owner)")
        user_id = args.user_id
        
        print(f"\nApplying {len(deduped)} labels as Map Pins for user {user_id} ...")
        from supabase_client import upsert_label_pins
        
        pins = []
        for e in deduped:
            bbox = e.get("global_bbox")
            if not bbox: continue
            gx, gy, gw, gh = bbox
            pins.append({
                "map_id": args.map_id,
                "user_id": user_id,
                "label": e.get("text", "").replace("\x00", ""),
                "pixel_x": int(gx + gw/2),
                "pixel_y": int(gy + gh/2),
                "data": {
                    "source": "ocr_cli_dedup",
                    "ocr_extraction_id": e.get("id"),
                    "confidence": e.get("confidence"),
                    "category": e.get("category"),
                    "run_id": args.run_id or e.get("run_id"),
                }
            })
            
        n = upsert_label_pins(args.map_id, pins)
        print(f"Applied {n} labels to supabase.label_pins table.")


def cmd_clean(args: argparse.Namespace) -> None:
    """Fuzzy dedup + spatial fragment join for V1-style raw OCR results."""
    # ── Load items ──────────────────────────────────────────────────────────────
    items: list[dict] = []

    if args.local:
        local_dir = Path(args.local)
        if not local_dir.is_dir():
            raise SystemExit(f"Local directory not found: {local_dir}")
        print(f"Reading .json files from {local_dir} ...")
        json_files = [f for f in local_dir.glob("*.json") if "_" in f.stem and f.stem[0].isdigit()]
        for f in json_files:
            try:
                data = json.loads(f.read_text())
                parts = f.stem.split("_")
                tx, ty, tw, th = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                for ext in data.get("extractions", []):
                    bbox = ext.get("bbox_px")
                    if not bbox:
                        continue
                    gx, gy, gw, gh = _to_global(bbox, tx, ty, tw, th)
                    items.append({**ext, "global_bbox": (gx, gy, gw, gh), "_tile_origin": (tx, ty)})
            except Exception as e:
                print(f"  Error reading {f.name}: {e}")
    elif args.db:
        if not args.map_id:
            raise SystemExit("Provide --map-id for DB fetch")
        from supabase_client import fetch_ocr_extractions
        print(f"Fetching items for map {args.map_id} (run={args.run_id or 'all'}) ...")
        items = fetch_ocr_extractions(args.map_id, args.run_id)
        for item in items:
            item.setdefault("_tile_origin", (item.get("tile_x"), item.get("tile_y")))
    else:
        raise SystemExit("Provide --local <dir> or --db")

    if not items:
        print("No items found.")
        return

    raw_n = len(items)

    # ── Filter by confidence ────────────────────────────────────────────────────
    items = [
        i for i in items
        if i.get("confidence", 1.0) >= args.min_confidence
        and i.get("global_bbox")
        and all(c is not None for c in i["global_bbox"])
    ]
    print(f"Loaded {len(items)} items (min_conf={args.min_confidence}, raw={raw_n})")

    # ── Pass 1: fuzzy dedup ─────────────────────────────────────────────────────
    deduped = dedup_items(items, iou_threshold=args.iou)
    print(f"After dedup:  {len(deduped)}  (removed {len(items) - len(deduped)})")

    # ── Pass 2: spatial fragment join ───────────────────────────────────────────
    joined = _spatial_join_fragments(deduped, proximity_px=args.proximity, angle_tol=args.angle_tol)
    n_joined = len(deduped) - len(joined)
    print(f"After join:   {len(joined)}  (merged {n_joined} fragment groups)")

    # ── Summary ─────────────────────────────────────────────────────────────────
    confirmed = [e for e in joined if e.get("confidence", 0) >= 0.7]
    uncertain = [e for e in joined if e.get("confidence", 0) < 0.7]
    print(f"\nResult: {len(joined)} labels  (confirmed={len(confirmed)}, uncertain={len(uncertain)})")
    print("\nSample confirmed:")
    for e in confirmed[:15]:
        print(f"  {e.get('text','')[:50]:50s}  [{e.get('category','other')}]  conf={e.get('confidence',0):.2f}")
    if len(confirmed) > 15:
        print(f"  … and {len(confirmed)-15} more")
    if uncertain:
        print(f"\nSample uncertain:")
        for e in uncertain[:5]:
            notes = (e.get("notes") or "")[:40]
            print(f"  ? {e.get('text','')[:50]:50s}  conf={e.get('confidence',0):.2f}  {notes}")
        if len(uncertain) > 5:
            print(f"  … and {len(uncertain)-5} more")

    # ── Save preview JSON ───────────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_name = f"clean_{ts}.json"
    out_path = Path(args.local) / out_name if args.local else Path(out_name)
    out_path.write_text(json.dumps({
        "map_id": args.map_id or "unknown",
        "run_id": args.run_id,
        "n_raw": raw_n,
        "n_after_dedup": len(deduped),
        "n_after_join": len(joined),
        "extractions": [{**e, "global_bbox": list(e["global_bbox"])} for e in joined],
    }, indent=2, ensure_ascii=False))
    print(f"\nSaved → {out_path}")

    # ── Apply → ocr_labels ─────────────────────────────────────────────────
    if args.apply:
        if not args.map_id:
            raise SystemExit("Provide --map-id for --apply")
        if not args.run_id:
            raise SystemExit("Provide --run-id for --apply (e.g. --run-id v1b)")
        from supabase_client import upsert_ocr_extractions
        rows = []
        for e in joined:
            bbox = e.get("global_bbox")
            if not bbox:
                continue
            gx, gy, gw, gh = bbox
            tile_origin = e.get("_tile_origin") or (0, 0)
            rows.append({
                "tile_x": int(tile_origin[0]),
                "tile_y": int(tile_origin[1]),
                "tile_w": int(e.get("tile_w") or 0),
                "tile_h": int(e.get("tile_h") or 0),
                "global_x": float(gx),
                "global_y": float(gy),
                "global_w": float(gw),
                "global_h": float(gh),
                "text": e.get("text", "").replace("\x00", ""),
                "category": e.get("category", "other"),
                "confidence": float(e.get("confidence", 0)),
                "rotation_deg": float(e.get("rotation_deg") or 0),
                "notes": (e.get("notes") or "").replace("\x00", ""),
                "model": e.get("model", ""),
                "prompt": e.get("prompt", ""),
                "review_status": "pending",
            })
        print(f"\nUpserting {len(rows)} rows to ocr_labels (run_id={args.run_id}) ...")
        n = upsert_ocr_extractions(args.map_id, args.run_id, rows)
        print(f"Done — {n} rows in ocr_labels.")


def cmd_scout(args: argparse.Namespace) -> None:
    """Run a macro-pass on the full map at low resolution."""
    iiif_base = args.iiif_base
    if not iiif_base and args.map_id:
        iiif_base = get_iiif_base_from_supabase(args.map_id)
    if not iiif_base:
        raise SystemExit("Provide --map-id or --iiif-base")

    print(f"Scouting map {args.map_id or 'unknown'} ...")
    info = get_image_info(iiif_base)
    full_w, full_h = info["width"], info["height"]
    iiif_quality = info.get("quality", "default")
    print(f"  Full resolution: {full_w}×{full_h} (IIIF v{info['version']}, quality={iiif_quality})")

    if info.get("sizes"):
        sizes_str = ", ".join(f"{s['width']}×{s['height']}" for s in info["sizes"])
        print(f"  Pre-rendered levels: {sizes_str}")
    if info.get("scale_factors"):
        print(f"  Scale factors: {info['scale_factors']}")

    # Choose scale levels from info.json — prefers server pre-rendered sizes
    render_size = args.render_size
    levels = choose_scale_levels(info, targets=(SCOUT_MIN_WIDTH, 2048, render_size))
    if not levels:
        # Two published Huế plans are 800×628 and 754×877 px at the source. The
        # picker returns nothing when every target exceeds the sheet, and the
        # old code then crashed on `images[-1]`, so the job's error was a
        # traceback rather than the fact. Say the fact.
        raise SystemExit(
            f"Sheet is {full_w}×{full_h} px, under the {SCOUT_MIN_WIDTH} px the scout "
            "needs to read a label. That is the scan itself, not the mirror: find a "
            "larger source (map_images) before running layout or OCR on this map."
        )
    print(f"  Using {len(levels)} scale level(s): "
          + ", ".join(f"{l['width']}×{l['height']}" for l in levels))

    # Fetch one image per level (full map, fit within the level's width)
    images = []
    for level in levels:
        lw = level["width"]
        print(f"  Fetching full map at {lw}px ...", end=" ", flush=True)
        img = fetch_crop(iiif_base, 0, 0, full_w, full_h, size=lw, quality=iiif_quality, fit=True)
        print(f"{img.size[0]}×{img.size[1]}")
        images.append(img)

    # Use the highest-res single image for single-image mode (backward compat)
    image = images[-1]
    
    from prompt import PROMPTS, SYSTEM_PROMPT, EXTRACTION_SCHEMA, SCOUT_SCHEMA
    prompt_key = args.prompt or "scout"
    schema = SCOUT_SCHEMA if prompt_key == "scout" else EXTRACTION_SCHEMA
    prompt_text = PROMPTS[prompt_key]

    # The run dir is made here, before the call, rather than at "Save results"
    # below, so the scout's spend lands in a calls.jsonl like every other pass.
    # Until 2026-09-14 the layout sweep was the one pass that cost money
    # invisibly: the 72 sheets scouted on 2026-09-13 left no token record, so
    # `vma_worker._spend()` and every job-row budget read them as free.
    map_label = args.map_id or "unknown"
    run_dir = make_run_dir(map_label, args.run_id)
    calls_log = run_dir / "calls.jsonl"

    if len(images) > 1:
        # Multi-scale sequence: one call, model sees all levels
        # Prepend level context to the prompt so the model knows what each frame is
        level_desc = "\n".join(
            f"Frame {i}: full map at {levels[i]['width']}×{levels[i]['height']}px"
            for i in range(len(images))
        )
        multi_prompt = (
            f"You are receiving {len(images)} frames of the SAME map at increasing resolutions.\n"
            f"{level_desc}\n"
            "Use all frames together: Frame 0 for overall structure and cartouche location, "
            "higher frames for reading fine text. Return results for the highest-resolution "
            "frame you can confidently read each label from.\n\n"
            + prompt_text
        )
        print(f"  Extracting via multi-scale sequence ({len(images)} frames, {args.model}) ...")
        res = extract_labels_sequence(
            images=images,
            system_prompt=SYSTEM_PROMPT,
            schema=schema,
            model=args.model,
            user_prompt=multi_prompt,
            log_path=calls_log,
        )
        # Discard frame_idx — scout results are always global (full-map coords)
        for ext in res.get("extractions", []):
            ext.pop("frame_idx", None)
    else:
        print(f"  Extracting via single image ({args.model}, prompt={prompt_key}) ...")
        res = extract_labels(
            image,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt_text,
            schema=schema,
            model=args.model,
            log_path=calls_log,
        )
    extractions = res.get("extractions", [])

    # ── Map content bound ─────────────────────────────────────────────────────
    content_bound = res.get("map_content_bbox")
    global_bound = None
    if content_bound and len(content_bound) == 4:
        bx = (content_bound[0] * full_w) / 1000
        by = (content_bound[1] * full_h) / 1000
        bw = (content_bound[2] * full_w) / 1000
        bh = (content_bound[3] * full_h) / 1000
        global_bound = (bx, by, bw, bh)
        print(f"  Map content bound: {tuple(int(v) for v in global_bound)}")

    # ── Cartouche bound ───────────────────────────────────────────────────────
    cartouche_norm = res.get("cartouche_bbox")
    global_cartouche = None
    if cartouche_norm and len(cartouche_norm) == 4:
        cx = (cartouche_norm[0] * full_w) / 1000
        cy = (cartouche_norm[1] * full_h) / 1000
        cw = (cartouche_norm[2] * full_w) / 1000
        ch = (cartouche_norm[3] * full_h) / 1000
        global_cartouche = (cx, cy, cw, ch)
        print(f"  Cartouche bound:  {tuple(int(v) for v in global_cartouche)}")

    # ── Layout regions ────────────────────────────────────────────────────────
    # The model answers on the 0-1000 normalized scale; everything downstream —
    # maps.triage, the tile grid, the digitalize canvas — works in source pixels.
    regions = []
    for r in res.get("regions") or []:
        bb = r.get("bbox")
        if not bb or len(bb) != 4:
            continue
        rx, ry, rw, rh = ((bb[0] * full_w) / 1000, (bb[1] * full_h) / 1000,
                          (bb[2] * full_w) / 1000, (bb[3] * full_h) / 1000)
        if rw < 1 or rh < 1:
            continue  # a zero-area box is the model filling a slot, not a region
        regions.append({
            "category": r["category"],
            "bbox": [int(rx), int(ry), int(rw), int(rh)],
            "confidence": float(r.get("confidence", 0)),
            "source": "model",
            **({"notes": r["notes"]} if r.get("notes") else {}),
        })
    if regions:
        print(f"  Layout: {len(regions)} region(s)")
        for r in regions:
            print(f"    {r['category']:12s} {tuple(r['bbox'])}  conf={r['confidence']:.2f}")

    # ── Metadata ──────────────────────────────────────────────────────────────
    metadata = res.get("metadata") or {}
    if metadata:
        print("  Metadata:")
        for k, v in metadata.items():
            if v:
                print(f"    {k:12s}: {v}")

    # ── Scale feature bboxes to global pixel coords ───────────────────────────
    items = []
    for ext in extractions:
        bbox = ext.get("bbox_px")
        if not bbox or len(bbox) < 4:
            continue
        gx = (bbox[0] * full_w) / 1000
        gy = (bbox[1] * full_h) / 1000
        gw = (bbox[2] * full_w) / 1000
        gh = (bbox[3] * full_h) / 1000
        items.append({**ext, "global_bbox": (gx, gy, gw, gh), "source": "scout"})

    print(f"  Found {len(items)} macro features.")

    # ── Tiling and priority proposal ──────────────────────────────────────────
    # The scout already holds a full-sheet overview and the layout regions, so it
    # already holds everything a tiling decision needs. Before this, a tile size
    # was picked by hand per sheet and the priority grid was derived inside the
    # batch run — at spend time, where nobody reviews it. Emitting both here
    # makes them a proposal someone accepts, which is the shape the rest of
    # triage already has.
    tiling = None
    priorities = None
    proposal_note = None
    overview = images[-1]

    if overview.size[0] < PRIORITY_MIN_OVERVIEW_WIDTH:
        proposal_note = (
            f"overview is {overview.size[0]}px wide, under the "
            f"{PRIORITY_MIN_OVERVIEW_WIDTH}px the density signal needs — no priority "
            "proposal (below it the signal inverts and rates the dense centre "
            "*below* the margins, which would skip the tiles worth reading)"
        )
        print(f"  Proposal: {proposal_note}")
    elif not args.map_id:
        proposal_note = "no --map-id, so no georeference to size from"
    else:
        from scale import (
            COARSE_SCAN_METRES_PER_PX,
            DEFAULT_OVERLAP_RATIO,
            DEFAULT_TILE_METRES,
            annotation_for_map,
            metres_per_pixel,
            tile_size_for,
        )

        ann = annotation_for_map(args.map_id)
        fit = metres_per_pixel(ann) if ann else None
        if fit is None:
            proposal_note = "no usable georeference (3+ non-collinear GCPs needed)"
            print(f"  Proposal: {proposal_note}")
        else:
            # main_map beats the content bound, for the same reason `tilingCrop`
            # in triageTypes.ts says so: the neatline is the printed border, and
            # a legend printed inside it is inside the neatline too.
            main = next((r for r in regions if r["category"] == "main_map"), None)
            if main:
                crop = tuple(main["bbox"])
                crop_src = "main_map region"
            elif global_bound:
                crop = tuple(int(v) for v in global_bound)
                crop_src = "map content bound"
            else:
                crop = (0, 0, full_w, full_h)
                crop_src = "whole sheet"

            target = args.tile_metres or DEFAULT_TILE_METRES
            plan = tile_size_for(fit.mean, crop[2], crop[3], target_metres=target,
                                 overlap_ratio=DEFAULT_OVERLAP_RATIO)
            overlap_px = int(plan.tile * DEFAULT_OVERLAP_RATIO)
            tiles = list(tile_grid(full_w, full_h, tile=plan.tile,
                                   overlap=overlap_px, region=crop))
            densities = compute_tile_densities(overview, tiles, full_w, full_h)
            priorities = auto_tile_overrides(
                densities,
                skip_below=args.skip_below,
                low_res_below=args.low_res_below,
            )
            tiling = {
                "metres_per_pixel": round(fit.mean, 4),
                "metres_per_pixel_x": round(fit.mx, 4),
                "metres_per_pixel_y": round(fit.my, 4),
                "anisotropy": round(fit.anisotropy, 4),
                "n_gcps": fit.n_gcps,
                "transformation": fit.transformation,
                "crop": list(crop),
                "crop_source": crop_src,
                "tile_size": plan.tile,
                "overlap": overlap_px,
                "render_size": plan.render,
                "tile_metres": round(plan.metres_per_tile, 1),
                "target_metres": target,
                "holds_target": plan.holds_target,
                "n_tiles": plan.n_tiles,
                "coarse_scan": fit.mean > COARSE_SCAN_METRES_PER_PX,
                "overview_width": overview.size[0],
            }
            n_skip = sum(1 for v in priorities.values() if v == "skip")
            n_low = sum(1 for v in priorities.values() if v == "low_res")
            print(f"  Scale: {fit}")
            print(f"  Tiling ({crop_src}): {plan}")
            print(f"  Priority: {len(tiles)} tiles -> {n_skip} skip, {n_low} low_res, "
                  f"{len(tiles) - n_skip - n_low} full")
            if fit.mean > COARSE_SCAN_METRES_PER_PX:
                print(f"  ⚠ Coarse scan ({fit.mean:.2f} m per source pixel): no tile size "
                      "recovers ink the scan never captured. Calibrated on city plans — a "
                      "small-scale sheet can read well past this line.")

    # Save results — run_dir was made above, before the call that costs money.
    out_path = run_dir / "scout.json"
    out_path.write_text(json.dumps({
        "map_id": args.map_id,
        "run_id": args.run_id or run_dir.name,
        "render_size": render_size,
        "n_features": len(items),
        "map_content_bbox": list(global_bound) if global_bound else None,
        "cartouche_bbox": list(global_cartouche) if global_cartouche else None,
        "regions": regions,
        "tiling": tiling,
        "priorities": priorities,
        "proposal_note": proposal_note,
        "metadata": metadata,
        "extractions": [{**e, "global_bbox": list(e["global_bbox"])} for e in items],
    }, indent=2, ensure_ascii=False))

    print(f"  Scout results saved to {out_path}")

    if args.preview:
        prev_path = out_path.with_suffix(".png")
        preview_extractions = list(extractions)
        if content_bound:
            preview_extractions.append({
                "text": "MAP CONTENT BOUND",
                "category": "other",
                "bbox_px": content_bound,
                "confidence": 1.0,
            })
        if cartouche_norm:
            preview_extractions.append({
                "text": "CARTOUCHE",
                "category": "title",
                "bbox_px": cartouche_norm,
                "confidence": 1.0,
            })
        for r in regions:
            preview_extractions.append({
                "text": r["category"].upper(),
                "category": "other",
                "bbox_px": [r["bbox"][0] * 1000 / full_w, r["bbox"][1] * 1000 / full_h,
                            r["bbox"][2] * 1000 / full_w, r["bbox"][3] * 1000 / full_h],
                "confidence": r["confidence"],
            })
        render_preview(image, preview_extractions, prev_path)
        print(f"  Preview saved to {prev_path}")

    # The proposal is only useful where a person can correct it, which is the
    # digitalize canvas, which reads maps.triage. Off by default: a hand-run
    # scout should not overwrite someone's saved triage.
    if getattr(args, "save_triage", False):
        if not args.map_id:
            raise SystemExit("--save-triage needs --map-id")
        from supabase_client import save_triage_regions
        # Adopt `main_map` as the crop at the same time. `tilingCrop()` already
        # prefers it to a hand-drawn neatline — the neatline is the printed
        # border and a legend inside it is inside the neatline too — so writing
        # it here is what lets a sheet reach OCR with nobody drawing anything.
        # Measured on the 1882 sheet: two independent layout runs put main_map
        # 0.2% apart at conf 0.98, on 80.4% of the sheet, against the 81% the
        # browser's ink-profile walk finds by a wholly different method.
        #
        # Not guessed when the model found no main_map: that sheet goes to the
        # "needs a crop" list for a person to open (see triageState).
        main = next((r for r in regions if r.get("category") == "main_map"), None)
        n = save_triage_regions(args.map_id, regions,
                                neatline=[int(v) for v in main["bbox"]] if main else None)
        print(f"  Wrote {n} region(s) to maps.triage.regions")
        if main:
            print(f"  Adopted main_map as the crop: {[int(v) for v in main['bbox']]} "
                  f"(conf {main.get('confidence')})")
        else:
            print("  No main_map region — the crop is left for a person to draw")

    return {"content": global_bound, "cartouche": global_cartouche, "regions": regions}


def cmd_scale(args: argparse.Namespace) -> None:
    """Print the sheet's scale and the tiling it implies. Spends nothing.

    The whole point of a proposal you can read before you pay for it: two HTTP
    GETs, no model call, no tile fetch. `--all` sweeps every georeferenced map
    so the coarse scans in the corpus can be found without opening 39 runs.
    """
    import requests

    from scale import (
        COARSE_SCAN_METRES_PER_PX,
        DEFAULT_OVERLAP_RATIO,
        DEFAULT_TILE_METRES,
        annotation_for_map,
        metres_per_pixel,
        tile_size_for,
    )
    from supabase_client import _headers, _load_config

    if args.all:
        url, key = _load_config()
        resp = requests.get(
            f"{url}/rest/v1/maps",
            params={"select": "id,name,year,allmaps_id,annotation_url",
                    "allmaps_id": "not.is.null", "order": "year"},
            headers=_headers(key), timeout=30,
        )
        resp.raise_for_status()
        targets = [(r["id"], f"{r.get('year') or '????'} {r.get('name') or r['id'][:8]}")
                   for r in resp.json()]
    else:
        if not args.map_id:
            raise SystemExit("Provide --map-id or --all")
        targets = [(args.map_id, args.map_id[:8])]

    target_metres = args.tile_metres or DEFAULT_TILE_METRES
    coarse: list[str] = []
    for map_id, label in targets:
        ann = annotation_for_map(map_id)
        fit = metres_per_pixel(ann) if ann else None
        if fit is None:
            print(f"{label}: no usable georeference (4+ GCPs needed)")
            continue
        source = ann["items"][0]["target"]["source"] if ann.get("items") else {}
        w, h = source.get("width"), source.get("height")
        print(f"{label}: {fit}")
        if not (w and h):
            print("   annotation carries no source dimensions — cannot size")
            continue
        plan = tile_size_for(fit.mean, w, h, target_metres=target_metres,
                             overlap_ratio=DEFAULT_OVERLAP_RATIO)
        print(f"   {w}x{h}px -> {plan}")
        # When a bound bound first, the target that *would* hold is the one worth
        # printing: the operator's next command, not the one they just typed.
        suggested = plan.metres_per_tile if not plan.holds_target else target_metres
        print(f"   ocr.py batch --map-id {map_id} --tile-metres {suggested:.0f}")
        if fit.mean > COARSE_SCAN_METRES_PER_PX:
            coarse.append(f"{label} ({fit.mean:.2f} m/px)")

    if coarse:
        print(f"\nCoarse scans — worth a look at the scan, but the line is calibrated on "
              f"city plans and a small-scale sheet can read well past it ({len(coarse)}):")
        for c in coarse:
            print(f"  {c}")


def cmd_list_models(args: argparse.Namespace) -> None:
    print("Fetching model list from Gemini API ...")
    models = list_models()
    thinking = [m for m in models if "think" in m.lower() or "flash" in m.lower()]
    print("\nAll models:")
    for m in models:
        print(f"  {m}")
    print(f"\nSuggested models (thinking / flash):")
    for m in thinking:
        print(f"  {m}")


# ── Argument parser ───────────────────────────────────────────────────────────


def _resolve_base_and_dims(args) -> tuple[str, int, int]:
    """Shared IIIF-base + image-dimension resolution for the local passes.

    Mirrors cmd_batch: --local-image | --iiif-base | --map-id.
    """
    local_image = getattr(args, "local_image", None)
    if local_image:
        import warnings
        from PIL import Image as _Img
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _Img.MAX_IMAGE_PIXELS = None
            w, h = _Img.open(local_image).size
        return "local", w, h
    base = args.iiif_base
    if not base:
        if not args.map_id:
            raise SystemExit("Provide --map-id, --iiif-base, or --local-image")
        base = get_iiif_base_from_supabase(args.map_id)
        if not base:
            raise SystemExit("Could not resolve IIIF base.")
    info = get_image_info(base)
    return base, info["width"], info["height"]


def cmd_detect_layout(args: argparse.Namespace) -> None:
    """Local scipy pass: find legend/cartouche/title boxes from a low-res overview.

    Emits source-pixel regions to feed the (Gemini) structured legend pass. No API
    calls — runs free on the M-series.
    """
    base, W, H = _resolve_base_and_dims(args)
    local_image = getattr(args, "local_image", None)
    overview = fetch_crop(base, 0, 0, W, H, size=args.overview_size, fit=True,
                          local_image=local_image)
    ow, oh = overview.size
    sx, sy = W / ow, H / oh  # overview px → source px

    boxes = detect_legend_boxes(overview, min_area_frac=args.min_area,
                                max_area_frac=args.max_area)
    regions = []
    for b in boxes:
        x, y, w, h = b["bbox"]
        regions.append({
            "bbox_source": [int(x * sx), int(y * sy), int(w * sx), int(h * sy)],
            "bbox_overview": [x, y, w, h],
            "score": b["score"],
            "category": "legend_region",
        })

    map_label = args.map_id or "unknown"
    out_dir = make_run_dir(map_label, getattr(args, "run_id", None))
    out_path = out_dir / "layout.json"
    out_path.write_text(json.dumps({
        "map_id": map_label,
        "source_size": [W, H],
        "overview_size": [ow, oh],
        "regions": regions,
    }, indent=2))
    print(f"Found {len(regions)} candidate box(es) (overview {ow}×{oh}):")
    for r in regions:
        print(f"  score={r['score']:.2f}  source_bbox={r['bbox_source']}")
    print(f"→ {out_path}")


def cmd_grid(args: argparse.Namespace) -> None:
    """Read the sheet's printed reference grid into maps.triage.grid.

    A printed index already knows roughly where everything is — "Bệnh Viện Chợ
    Rẫy ... J 5,6" is a position, at cell accuracy, that cost nothing extra to
    obtain. This reads the grid those codes refer to, so they can be turned into
    points without spotting a single numeral on the map body.
    """
    base, W, H = _resolve_base_and_dims(args)
    local_image = getattr(args, "local_image", None)
    overview = fetch_crop(base, 0, 0, W, H, size=args.render_size, fit=True,
                          local_image=local_image)
    print(f"  Overview {overview.size[0]}×{overview.size[1]} of {W}×{H}")

    from gemini_client import extract_grid
    # Run dir before the call, so the grid read is costed like any other pass.
    map_label = args.map_id or "unknown"
    out_dir = make_run_dir(map_label, getattr(args, "run_id", None))
    res = extract_grid(overview, model=args.model,
                       log_path=out_dir / "calls.jsonl")

    cols = [str(c) for c in (res.get("columns") or []) if str(c).strip()]
    rows = [str(r) for r in (res.get("rows") or []) if str(r).strip()]
    bb = res.get("bbox") or []
    if len(cols) < 2 or len(rows) < 2 or len(bb) != 4:
        print("  No usable reference grid on this sheet.")
        return

    grid = {
        "bbox": [int(bb[0] * W / 1000), int(bb[1] * H / 1000),
                 int(bb[2] * W / 1000), int(bb[3] * H / 1000)],
        "columns": cols,
        "rows": rows,
    }
    cw = grid["bbox"][2] / len(cols)
    ch = grid["bbox"][3] / len(rows)
    print(f"  Grid {len(cols)}×{len(rows)} at {tuple(grid['bbox'])}, cell ≈ {cw:.0f}×{ch:.0f} px")
    print(f"    columns: {' '.join(cols)}")
    print(f"    rows:    {' '.join(rows)}")

    # out_dir was made above, before the call that costs money.
    (out_dir / "grid.json").write_text(json.dumps(grid, indent=2, ensure_ascii=False))
    print(f"→ {out_dir / 'grid.json'}")

    if getattr(args, "save_triage", False):
        if not args.map_id:
            raise SystemExit("--save-triage needs --map-id")
        from supabase_client import save_triage_grid
        save_triage_grid(args.map_id, grid)
        print("  Wrote maps.triage.grid")


def cmd_numerals(args: argparse.Namespace) -> None:
    """Local Tesseract pass: spot standalone numerals (legend refs) across the map body.

    Writes category='legend_ref' rows — a later join on value links each to its
    legend entry. No API calls.
    """
    base, W, H = _resolve_base_and_dims(args)
    local_image = getattr(args, "local_image", None)
    tiles = list(tile_grid(W, H, tile=args.tile_size, overlap=args.overlap))
    if args.limit:
        tiles = tiles[: args.limit]
    print(f"Numeral pass over {len(tiles)} tile(s) "
          f"({args.tile_size}px, {args.overlap}px overlap, render={args.render_size}px)")

    items: list[dict] = []
    for i, (tx, ty, tw, th) in enumerate(tiles):
        img = fetch_crop(base, tx, ty, tw, th, size=args.render_size,
                         local_image=local_image)
        rw, rh = img.size
        rsx, rsy = tw / rw, th / rh  # render px → source px
        for hit in spot_numerals(img, min_conf=args.min_conf):
            bx, by, bw, bh = hit["bbox"]
            gx, gy = int(tx + bx * rsx), int(ty + by * rsy)
            gw, gh = int(bw * rsx), int(bh * rsy)
            items.append({
                "text": hit["text"],
                "confidence": hit["confidence"],
                "global_bbox": (gx, gy, gw, gh),
                "tile": (tx, ty, tw, th),
            })
        print(f"  [{i+1}/{len(tiles)}] tile ({tx},{ty}) → {len(items)} total so far")

    deduped = dedup_items(items, iou_threshold=args.iou)
    print(f"Dedup: {len(items)} raw → {len(deduped)} unique numerals")

    map_label = args.map_id or "unknown"
    out_dir = make_run_dir(map_label, getattr(args, "run_id", None))
    out_path = out_dir / "numerals.json"
    out_path.write_text(json.dumps({
        "map_id": map_label,
        "source_size": [W, H],
        "n_raw": len(items),
        "n_deduped": len(deduped),
        "numerals": [{**d, "global_bbox": list(d["global_bbox"]), "tile": list(d["tile"])}
                     for d in deduped],
    }, indent=2))
    print(f"→ {out_path}")

    if getattr(args, "db", False) and map_label != "unknown":
        from supabase_client import upsert_ocr_extractions
        rows = []
        for d in deduped:
            gx, gy, gw, gh = d["global_bbox"]
            tx, ty, tw, th = d["tile"]
            rows.append({
                "tile_x": tx, "tile_y": ty, "tile_w": tw, "tile_h": th,
                "category": "legend_ref", "text": d["text"],
                "confidence": d["confidence"],
                "global_x": gx, "global_y": gy, "global_w": gw, "global_h": gh,
                "rotation_deg": 0, "notes": None,
                "model": "tesseract", "prompt": "numerals-v1",
            })
        n = upsert_ocr_extractions(map_label, out_dir.name, rows)
        print(f"[db] upserted {n} legend_ref row(s)")


def legend_line_boxes(region: tuple[int, int, int, int],
                      n: int) -> list[tuple[int, int, int, int]]:
    """One rectangle per printed line of a legend column, top to bottom.

    A `--region` here is one column of the printed directory, read in one call,
    and the entries come back in printed order — so the lines are the column
    divided by how many there are. Without this every row of a column carried
    the column's own crop: on the 1942 sheet, 235 rows sharing **six**
    rectangles, one of them standing for 52 lines. That is not a bounding box of
    anything, and it makes a legend row impossible to zoom to, drag, or review
    against its own ink.

    Falls back to the whole region when the split would be a guess: fewer than
    three lines, or a pitch outside what a printed line can be. An even pitch
    down one column is the assumption, and it is the only shape the legend pass
    is ever handed.
    """
    x, y, w, h = region
    pitch = h / n if n else 0
    if n < 3 or pitch < 8 or pitch > h / 2:
        return [(x, y, w, h)] * n
    return [(x, int(y + i * pitch), w, max(1, int(pitch))) for i in range(n)]


def _fold_name(s: str) -> str:
    """A legend name flattened enough that two readings of one line match."""
    return " ".join(_fold(s or "").split())


def legend_block_collisions(blocks: list[dict]) -> list[dict]:
    """Numbers claimed by two legend blocks under *different* names.

    A sheet with two printed legend blocks is one of two things, and the numbers
    are the only evidence. Either the blocks continue one sequence — 1..99 in
    the first, 100..236 in the second — and merging by number is exactly right;
    or they are independent tables both numbering from 1, and merging by number
    silently puts one table's name on the other table's numerals wherever they
    overlap. On the 1942 Saigon-Cho Lon sheet, with two `legend` blocks and map
    numerals running past 170, that is not a hypothetical.

    The test is the *name*, not the number: the same number read twice off the
    same continued table (blocks that overlap, or a re-read) agrees with itself
    and is no collision.
    """
    by_n: dict[int, dict[int, str]] = {}
    for b in blocks:
        for e in b["entries"]:
            try:
                n = int(e["n"])
            except (KeyError, TypeError, ValueError):
                continue
            by_n.setdefault(n, {})[b["block"]] = (e.get("name") or "").strip()
    out = []
    for n in sorted(by_n):
        names = by_n[n]
        if len(names) > 1 and len({_fold_name(v) for v in names.values()}) > 1:
            out.append({"n": n, "names": names})
    return out


def _write_legend_rows(map_id: str, run_id: str, region: tuple[int, int, int, int],
                       entries: list[dict], model: str, block: int | None = None) -> int:
    """Upsert extracted legend entries as category='legend_entry' rows.

    `block` is the index of the printed block this line came from, written into
    notes only when the sheet has more than one — so a single-block sheet's rows
    are byte-identical to what they were, and a reviewer looking at a
    two-table sheet can see which table a name is from.

    ponytail: ocr_labels has no number/grid columns, so the number + grid
    live in `notes` (parseable "n=..; grid=..") and `text` carries "n. name" —
    that keeps the row key unique (duplicate names exist) and carries the
    body-numeral join key. Add real columns if the number-join gets clumsy.
    """
    from supabase_client import upsert_ocr_extractions
    x, y, w, h = region
    boxes = legend_line_boxes(region, len(entries))
    rows = []
    for e, (ex, ey, ew, eh) in zip(entries, boxes):
        note = f"n={e['n']}; grid={e.get('grid','')}"
        if block is not None:
            note += f"; block={block}"
        if e.get("name_vn"): note += f"; vn={e['name_vn']}"
        if e.get("grid_disputed"): note += "; grid_disputed"
        rows.append({
            "tile_x": x, "tile_y": y, "tile_w": w, "tile_h": h,
            "category": "legend_entry", "text": f"{e['n']}. {e['name']}",
            "confidence": 0.9,
            "global_x": ex, "global_y": ey, "global_w": ew, "global_h": eh,
            "rotation_deg": 0, "notes": note,
            "model": model, "prompt": "legend-v1",
        })
    return upsert_ocr_extractions(map_id, run_id, rows)


# Which OCR category a road-type word belongs to. The directory prints the
# generic in its own column, so this is a lookup rather than a guess.
_GENERIC_CATEGORY = {
    "duong": "street", "dai lo": "street", "hem": "street", "ngo": "street",
    "ben": "street", "cong truong": "street", "quoc lo": "street",
    "huong lo": "street",
    "rach": "hydrology", "kinh": "hydrology", "song": "hydrology",
}


def _cell_rect(grid: dict, ref: str) -> tuple[float, float, float, float] | None:
    """The source-pixel rectangle one printed grid cell covers, or None.

    The single-cell subset of `cellBox` in `src/lib/core/geo/mapGrid.ts`, which
    is the authority: `tests/street-index-grid.spec.ts` pins the two against a
    committed fixture so this copy cannot drift. A reference naming a label the
    sheet does not print — this sheet's index says "J 2" twice and its rows stop
    at I — returns None rather than a guess.
    """
    m = re.match(r"\s*([A-Za-z]+)\s*(\d+)\s*$", ref or "")
    if not m:
        return None
    rows = [str(r).strip().upper() for r in grid.get("rows") or []]
    cols = [str(c).strip().upper() for c in grid.get("columns") or []]
    a, b = m.group(1).upper(), m.group(2)
    if a not in rows or b not in cols:
        return None
    gx, gy, gw, gh = (float(v) for v in grid["bbox"])
    cw, ch = gw / len(cols), gh / len(rows)
    return (gx + cols.index(b) * cw, gy + rows.index(a) * ch, cw, ch)


def _expand_ref(ref: str) -> list[str]:
    """One printed reference into the single-cell references it names.

    A directory writes a two-cell entry as one reference: "J 5,6" is J5 and J6,
    and `cmd_street_index` has already stripped the space, so what arrives here
    is "J5,6". `_cell_rect` takes one cell — deliberately, because it is pinned
    against `cellBox` in the TypeScript — so the splitting happens out here.
    Anything that is not a letter followed by a comma-separated run of numbers
    is passed through unchanged and left for `_cell_rect` to reject.
    """
    m = re.match(r"\s*([A-Za-z]+)\s*(\d+(?:\s*,\s*\d+)+)\s*$", ref or "")
    if not m:
        return [ref]
    letter = m.group(1)
    return [f"{letter}{n.strip()}" for n in m.group(2).split(",")]


def _span_rect(grid: dict, ref_from: str, ref_to: str):
    """The rectangle spanning a street's TỪ and ĐẾN cells.

    A street index states where a street starts and where it ends, so the honest
    footprint is the union of the two cells — wide when the street crosses the
    sheet, one cell when it does not. Returns (rect, n_cells_resolved) so the
    caller can tell a two-cell span from a one-cell fallback.

    Either end may itself name a run of cells ("J 5,6"), which is why the ends
    go through `_expand_ref` first: taken literally that reference resolves to
    nothing and the street is dropped from the run without a mark.
    """
    got = [r for ref in (ref_from, ref_to) for e in _expand_ref(ref)
           if (r := _cell_rect(grid, e))]
    if not got:
        return None, 0
    x0 = min(r[0] for r in got)
    y0 = min(r[1] for r in got)
    x1 = max(r[0] + r[2] for r in got)
    y1 = max(r[1] + r[3] for r in got)
    return (x0, y0, x1 - x0, y1 - y0), len(got)


def cmd_street_index(args: argparse.Namespace) -> None:
    """Read a printed street directory into rows positioned by the printed grid.

    The directory is a tall narrow column — 798 x 7853 px on the 1959 Saigon
    sheet — so it is read in horizontal bands: one call each, overlapping, so a
    row split by a band edge is whole in the next one. Entries are merged on
    (generic, name), which is what the table is keyed by.

    Every row it yields carries a position, because the table states one. That
    is the point of reading it: spotting a street label out on the map body
    finds maybe half of them, while the index is complete by construction.
    """
    from gemini_client import extract_street_index

    base, W, H = _resolve_base_and_dims(args)
    local_image = getattr(args, "local_image", None)
    # `legend` as well as `name_list`: on the 1942 Saigon-Cho Lon sheet the
    # layout pass called both printed directories `legend`, and a sheet that has
    # a real `name_list` region will match that first.
    regions = _resolve_regions(args, ["name_list", "legend"], "--regions")

    map_label = args.map_id or "unknown"
    out_dir = make_run_dir(map_label, getattr(args, "run_id", None))
    log_path = out_dir / "calls.jsonl"

    merged: dict[tuple[str, str], dict] = {}
    conflicts: list[dict] = []
    failed: list[tuple[int, int, int]] = []
    n_bands = 0
    for ri, (x, y, w, h) in enumerate(regions):
        y0 = y
        while y0 < y + h:
            bh = min(args.band_height, y + h - y0)
            # A tail no taller than the overlap was already read whole by the
            # previous band. `<=`, not `<`: at exactly the overlap the step
            # below is zero and the loop never ends.
            if bh <= args.overlap:
                break
            crop = fetch_crop(base, x, y0, w, bh, size=args.render_size,
                              local_image=local_image)
            try:
                entries = extract_street_index(crop, model=args.model,
                                               log_path=log_path,
                                               cache_dir=OUTPUTS_CACHE_DIR)
            except Exception as e:
                # Named loudly and counted: a band that comes back empty is
                # thirty streets missing from a run that otherwise reports
                # success.
                print(f"  region {ri} band y={y0}: FAILED — {str(e)[:160]}")
                failed.append((ri, y0, bh))
                entries = []
            # Bands attempted, not calls billed. A band whose crop and prompt are
            # already in the model-response cache returns from `extract_labels`
            # before `_log_call` runs, so it counts here and never reaches
            # calls.jsonl. Measured 2026-09-10: 15 bands per pass, 14 billed.
            n_bands += 1
            kept = 0
            for e in entries:
                name = (e.get("name") or "").strip()
                generic = (e.get("generic") or "").strip()
                # A directory whose commonest road type is the default prints a
                # dash for it and spells out only the exceptions — the 1968
                # Saigon sheet does, where "—" is Đường. Taken literally it
                # becomes part of the label ("— Bạch Đằng") and of the dedupe
                # key, so it is dropped rather than mapped: which word the sheet
                # means is the sheet's business, not this function's.
                if generic in {"-", "\u2013", "\u2014", "\u2015", "--", "\u2026", "."}:
                    generic = ""
                if not name:
                    continue
                key = (_fold(generic), _fold(name))
                if key in merged:
                    # First writer wins, as before — but a repeat that states a
                    # *different* position is not a repeat. Two directories on
                    # one sheet index two different areas, and keeping the first
                    # silently places the street in the wrong one.
                    prev = merged[key]
                    cells = ((e.get("from") or "").strip().replace(" ", ""),
                             (e.get("to") or "").strip().replace(" ", ""))
                    if cells != (prev["from"], prev["to"]):
                        conflicts.append({
                            "name": f"{generic} {name}".strip(),
                            "kept": {"region": prev["region"],
                                     "cells": [prev["from"], prev["to"]]},
                            "dropped": {"region": ri, "cells": list(cells)},
                        })
                    continue
                merged[key] = {
                    "generic": generic, "name": name,
                    "from": (e.get("from") or "").strip().replace(" ", ""),
                    "to": (e.get("to") or "").strip().replace(" ", ""),
                    "region": ri, "band_y": y0,
                }
                kept += 1
            print(f"  region {ri} band y={y0} h={bh}: {len(entries)} read, {kept} new "
                  f"({len(merged)} total)")
            y0 += max(bh - args.overlap, 1)

    entries = sorted(merged.values(), key=lambda e: (_fold(e["name"]), _fold(e["generic"])))
    out_path = out_dir / "street_index.json"
    out_path.write_text(json.dumps({
        "map_id": map_label, "regions": [list(r) for r in regions],
        "model": args.model, "prompt": "street-index-v1",
        "n_bands": n_bands, "n_entries": len(entries),
        "failed_bands": [list(f) for f in failed],
        "cell_conflicts": conflicts, "entries": entries,
    }, indent=2, ensure_ascii=False))
    print(
        f"\n{len(entries)} street entries from {n_bands} band(s) attempted "
        f"→ {out_path}\n  calls.jsonl is what was billed; a cached band is free"
    )
    if failed:
        print(f"  {len(failed)} band(s) FAILED and read nothing: {failed}")
        print("  Re-run the same --run-id to retry them; every band that did land is cached.")
    if conflicts:
        print(f"  {len(conflicts)} street(s) listed twice with DIFFERENT cells — the "
              f"first reading was kept. Two directories indexing two areas is the "
              f"case to check for:")
        for c in conflicts[:20]:
            print(f"     {c['name']}: kept region {c['kept']['region']} "
                  f"{c['kept']['cells']}, dropped region {c['dropped']['region']} "
                  f"{c['dropped']['cells']}")
        if len(conflicts) > 20:
            print(f"     … and {len(conflicts) - 20} more")

    if not getattr(args, "db", False) or map_label == "unknown":
        return

    from supabase_client import fetch_triage_grid
    grid = fetch_triage_grid(map_label)
    if not grid:
        raise SystemExit("map has no triage.grid — run `ocr grid` first, or omit --db")
    from supabase_client import upsert_ocr_extractions
    rows, unplaced = [], []
    for e in entries:
        rect, got = _span_rect(grid, e["from"], e["to"])
        if not rect:
            unplaced.append(e)
            continue
        # How many cells the two references name, against how many the grid
        # could place. A street placed on half of what it states is a shorter
        # street than the sheet prints, and the row has to say so.
        want = len(_expand_ref(e["from"]))
        if e["to"] and e["to"] != e["from"]:
            want += len(_expand_ref(e["to"]))
        gx, gy, gw, gh = rect
        label = f"{e['generic']} {e['name']}".strip()
        note = (f"street index; grid={e['from']}\u2192{e['to']}; cells={got}/{want}"
                + ("; some cells unresolved" if got < want else ""))
        rows.append({
            "tile_x": int(gx), "tile_y": int(gy), "tile_w": int(gw), "tile_h": int(gh),
            "category": _GENERIC_CATEGORY.get(_fold(e["generic"]), "street"),
            "text": label,
            # Not a reading of the map body: the position is a cell span the
            # index states, several hundred metres across. The row says so in
            # `notes` and its box is that span rather than a false point.
            "confidence": 0.75,
            "global_x": gx, "global_y": gy, "global_w": gw, "global_h": gh,
            "rotation_deg": 0, "notes": note,
            "model": args.model, "prompt": "street-index-v1",
        })
    n = upsert_ocr_extractions(map_label, out_dir.name, rows)
    print(f"[db] upserted {n} row(s); {len(unplaced)} entry/ies had no placeable cell")
    for e in unplaced:
        print(f"     {e['generic']} {e['name']} — {e['from']}\u2192{e['to']}")


def cmd_street_index_fixture(args: argparse.Namespace) -> None:
    """Write the grid-parity fixture that `tests/street-index-grid.spec.ts` reads.

    `_cell_rect` here and `cellBox` in `src/lib/core/geo/mapGrid.ts` turn the
    same printed reference into the same rectangle, in two languages. This dumps
    what Python computes for every reference the sheet actually uses — both
    directory columns and the numbered index — plus every corner of the grid, so
    the TypeScript side has something to disagree with.
    """
    from supabase_client import fetch_triage_grid
    grid = fetch_triage_grid(args.map_id)
    if not grid:
        raise SystemExit(f"map {args.map_id} has no triage.grid")

    refs: set[str] = set()
    # Every cell of the grid, so both axes' ends are covered whatever the sheet
    # happens to reference.
    for r in grid["rows"]:
        for c in grid["columns"]:
            refs.add(f"{r}{c}")
    # Plus what the sheet's own tables say, including anything unplaceable.
    runs_dir = OUTPUTS_DIR / args.map_id / "runs"
    for path in sorted(runs_dir.glob("*/street_index.json")):
        for e in json.loads(path.read_text()).get("entries", []):
            refs.update(x for x in (e.get("from"), e.get("to")) if x)
    for path in sorted(runs_dir.glob("*/index.json")) + sorted(runs_dir.glob("*/legend.json")):
        for e in json.loads(path.read_text()).get("entries", []):
            if e.get("grid"):
                refs.add(str(e["grid"]).replace(" ", ""))

    # `_cell_rect` reads one cell; `cellBox` also spans a run ("G H 10"), which
    # only the browser needs — the street index puts its two cells in separate
    # fields. So parity is asserted on single-cell references, and references
    # naming a run go in `ts_only`, where the test pins the asymmetry instead of
    # leaving it to be discovered.
    single = re.compile(r"^[A-Za-z]+\s*\d+$")
    cases, ts_only = [], []
    for ref in sorted(refs):
        if single.match(ref):
            rect = _cell_rect(grid, ref)
            cases.append({"ref": ref, "rect": list(rect) if rect else None})
        else:
            ts_only.append(ref)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "_comment": ("Generated by `ocr street-index-fixture`. Python's _cell_rect against "
                     "the TypeScript cellBox — see tests/street-index-grid.spec.ts."),
        "map_id": args.map_id,
        "grid": {"bbox": grid["bbox"], "rows": grid["rows"], "columns": grid["columns"]},
        "cases": cases,
        "ts_only": ts_only,
    }, indent=2, ensure_ascii=False) + "\n")
    n_null = sum(1 for c in cases if c["rect"] is None)
    print(f"{len(cases)} single-cell references ({n_null} unplaceable), "
          f"{len(ts_only)} multi-cell (TypeScript only) → {out}")


def _run_legend_pass(iiif_base: str, img_w: int, img_h: int, cartouche,
                     local_image: str | None, map_id: str, run_id: str,
                     model: str, quality: str = "default") -> None:
    """Auto legend step for `batch --legend`: locate a legend region, extract it.

    Region priority: scout cartouche bbox → local ruled-box finder → skip.
    Single model, no consensus — the batch path stays cheap; use `legend
    --consensus` by hand when a legend's grid cells are worth cross-checking.
    """
    from gemini_client import extract_legend
    region = tuple(int(v) for v in cartouche) if cartouche else None
    if not region and not local_image:
        overview = fetch_crop(iiif_base, 0, 0, img_w, img_h, size=1024, quality=quality)
        boxes = detect_legend_boxes(overview)
        if boxes:
            bx, by, bw, bh = boxes[0]["bbox"]
            sx, sy = img_w / overview.size[0], img_h / overview.size[1]
            region = (int(bx * sx), int(by * sy), int(bw * sx), int(bh * sy))
    if not region:
        print("[legend] no cartouche/ruled-box region found — skipped")  # no silent cap
        return
    x, y, w, h = region
    crop = fetch_crop(iiif_base, x, y, w, h, size=2600, local_image=local_image, quality=quality)
    entries = extract_legend(crop, model=model,
                             log_path=make_run_dir(map_id, run_id) / "calls.jsonl")
    n = _write_legend_rows(map_id, run_id, region, entries, model)
    print(f"[legend] region={region} entries={len(entries)} upserted={n}")


def _resolve_regions(args, categories: list[str], flag: str) -> list[tuple[int, int, int, int]]:
    """The rectangles a printed-block pass should read.

    `--regions` when given, otherwise the sheet's own layout regions of the
    named categories. Typing them by hand is how the 1942 Saigon-Cho Lon sheet
    got one of its two `legend` blocks read and the other silently skipped:
    `--exclude` had both, so the tile pass dropped the numbers in block two and
    no structured pass ever picked them up. The layout pass already knows where
    both are.
    """
    raw = getattr(args, "regions", None)
    if raw:
        rects = parse_rects(raw)
        if not rects:
            raise SystemExit(f"{flag} parsed to no rectangles")
        return rects
    if not getattr(args, "map_id", None):
        raise SystemExit(f"{flag} is required without --map-id")
    from supabase_client import fetch_triage_regions
    rects = fetch_triage_regions(args.map_id, categories)
    if not rects:
        raise SystemExit(
            f"no {'/'.join(categories)} region on this sheet — run the layout pass, "
            f"draw one in /scan?mode=prepare, or pass {flag}"
        )
    print(f"  {flag} from maps.triage.regions ({'/'.join(categories)}): {len(rects)} block(s)")
    return rects


def cmd_legend(args: argparse.Namespace) -> None:
    """Gemini pass: read a sheet's numbered legend into structured {n, name, grid}.

    Optionally cross-checks the grid cell across N models (--consensus) and flags
    entries where they disagree — those are the ~few cells worth a human glance.

    **A sheet may print its legend in more than one block** — the 1942
    Saigon-Cho Lon sheet prints two — so `--regions` is a list and every block
    is read in the same run. Which blocks were read is written into each row's
    notes (`block=0`), because the two cases downstream cannot be told apart
    from the numbers alone: two blocks continuing one sequence (1..99, then
    100..236) merge cleanly, while two independent tables both numbering from 1
    collide, and a collision resolved by first-writer-wins puts the wrong name
    on every numeral of that value out on the map. The run reports which one
    this sheet is instead of guessing.
    """
    base, W, H = _resolve_base_and_dims(args)
    local_image = getattr(args, "local_image", None)
    regions = _resolve_regions(args, ["legend"], "--regions")

    models = [args.model]
    if args.consensus > 1:
        extra = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"]
        for m in extra:
            if m not in models and len(models) < args.consensus:
                models.append(m)

    import collections
    def ngrid(s): return "".join((s or "").upper().split()).replace(",", "").replace("-", "")

    multi = len(regions) > 1
    blocks: list[dict] = []
    flagged: list[int] = []
    # Before the loop: a --consensus run calls several models per block, and
    # every one of them bills. They all append to the same log.
    map_label = args.map_id or "unknown"
    out_dir = make_run_dir(map_label, getattr(args, "run_id", None))
    calls_log = out_dir / "calls.jsonl"
    for bi, (x, y, w, h) in enumerate(regions):
        print(f"  block {bi}: region {(x, y, w, h)}")
        crop = fetch_crop(base, x, y, w, h, size=args.render_size, local_image=local_image)

        runs = {}
        for m in models:
            try:
                entries = extract_legend(crop, model=m, bilingual=args.bilingual,
                                         log_path=calls_log)
                runs[m] = {int(e["n"]): e for e in entries
                           if str(e.get("n", "")).strip().lstrip("-").isdigit()}
                print(f"    {m}: {len(runs[m])} entries")
            except Exception as e:
                # Named and counted, like a failed street-index band: a block
                # that reads nothing is a whole table missing from a run that
                # otherwise reports success.
                print(f"    {m}: ERROR {str(e)[:100]}")

        best = runs.get(args.model) or (next(iter(runs.values())) if runs else {})
        out_entries = []
        for n in sorted(best):
            e = dict(best[n])
            e["block"] = bi
            if len(runs) > 1:
                present = [r[n] for r in runs.values() if n in r]
                votes = collections.Counter(ngrid(r.get("grid")) for r in present)
                top, cnt = votes.most_common(1)[0]
                # Adopt the majority grid; flag only when there is NO majority
                # (all models disagree) — those are the cells worth a human glance.
                if cnt >= 2:
                    e["grid"] = next(r.get("grid") for r in present if ngrid(r.get("grid")) == top)
                elif len(present) >= 2:
                    e["grid_disputed"] = True
                    e["grid_votes"] = dict(votes)
                    flagged.append(n)
            out_entries.append(e)
        blocks.append({"block": bi, "region": [x, y, w, h], "models": list(runs),
                       "entries": out_entries})

    all_entries = [e for b in blocks for e in b["entries"]]
    collisions = legend_block_collisions(blocks)

    # out_dir and map_label were set above, before the first call that costs money.
    out_path = out_dir / "legend.json"
    out_path.write_text(json.dumps({
        "map_id": map_label,
        "regions": [b["region"] for b in blocks],
        # Kept for the single-block readers that predate multi-block support.
        "region_source": blocks[0]["region"] if blocks else None,
        "models": sorted({m for b in blocks for m in b["models"]}),
        "n_blocks": len(blocks),
        "n_entries": len(all_entries),
        "grid_disputed": flagged,
        "number_collisions": collisions,
        "entries": all_entries,
    }, indent=2, ensure_ascii=False))
    print(f"\nExtracted {len(all_entries)} legend entries from {len(blocks)} block(s)"
          + (f" ({len(flagged)} grid-disputed: {flagged})" if flagged else " (no grid disputes)"))
    if collisions:
        print(f"  {len(collisions)} number(s) claimed by more than one block with a "
              f"DIFFERENT name — this sheet prints two independent tables, not one "
              f"sequence split in two. A numeral on the map cannot be joined by "
              f"number alone; review these before trusting the join:")
        for c in collisions[:20]:
            print(f"     n={c['n']}: " + " | ".join(f"block {b}: {nm}"
                                                    for b, nm in c["names"].items()))
        if len(collisions) > 20:
            print(f"     … and {len(collisions) - 20} more")
    elif multi:
        print("  No number is claimed by two blocks with different names — the blocks "
              "continue one sequence, so joining a map numeral by its number is safe.")
    print(f"→ {out_path}")

    if getattr(args, "db", False) and map_label != "unknown":
        total = 0
        for b in blocks:
            total += _write_legend_rows(map_label, out_dir.name, tuple(b["region"]),
                                        b["entries"], args.model,
                                        block=b["block"] if multi else None)
        print(f"[db] upserted {total} legend_entry row(s)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="VMA OCR — Gemini vision extraction for historical map tiles"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = sub.add_parser("run", help="Extract labels from tile(s)")
    p_run.add_argument("--map-id", help="Supabase maps.id UUID (resolves IIIF base)")
    p_run.add_argument("--iiif-base", help="IIIF image service base URL (overrides --map-id)")
    p_run.add_argument("--crop", help="Single crop: x,y,w,h (in source pixels)")
    p_run.add_argument("--tile-size", type=int, default=2400, help="Tile size for grid mode (source px)")
    p_run.add_argument("--overlap", type=int, default=600, help="Tile overlap for grid mode (source px)")
    p_run.add_argument("--render-size", type=int, default=1024, help="Rendered pixel width (default 1024)")
    p_run.add_argument("--limit", type=int, help="Max tiles to process")
    p_run.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model ID")
    p_run.add_argument("--prompt", default=DEFAULT_PROMPT, help="Prompt version key")
    p_run.add_argument("--run-id", help="Run identifier for versioned output dir (default: timestamp)")
    p_run.add_argument("--adaptive", action="store_true", help="Auto-scale render size by tile density (dense=2048, sparse=1024)")
    p_run.add_argument("--dry-run", action="store_true", help="Fetch tiles but skip API calls")
    p_run.add_argument("--preview", action="store_true", help="Save PNG preview with bbox overlay")
    p_run.add_argument("--clahe", action="store_true",
        help="Adaptive-contrast (CLAHE) pre-pass on each tile before the model call. "
             "OFF by default — for faded/low-contrast scans; not yet measured against EVAL-BASELINE.md")
    p_run.add_argument("--clahe-clip", type=float, default=2.0,
        help="CLAHE clip limit (default 2.0; 1.0 is a no-op, >4 amplifies paper grain)")
    p_run.add_argument("--clahe-grid", default="8",
        help="CLAHE grid: N for NxN, or ROWSxCOLS (default 8)")
    p_run.set_defaults(func=cmd_run)

    # batch
    p_batch = sub.add_parser("batch", help="Run OCR on all tiles of a map (resumable, concurrent)")
    p_batch.add_argument("--map-id", help="Supabase maps.id UUID")
    p_batch.add_argument("--iiif-base", help="IIIF image service base URL")
    p_batch.add_argument("--local-image", help="Local image file path (skips IIIF/IA entirely)")
    p_batch.add_argument("--tile-size", type=int, default=2400, help="Tile size in source pixels (default 2400)")
    p_batch.add_argument("--overlap", type=int, default=300, help="Tile overlap in source pixels (default 300)")
    p_batch.add_argument("--render-size", type=int, default=1024, help="Rendered pixel width per tile (default 1024)")
    p_batch.add_argument("--concurrency", type=int, default=3, help="Max concurrent Gemini calls (default 3)")
    p_batch.add_argument("--grid-offset", type=int, default=0,
                         help="Phase-shift the tile grid by this many source px in x and y, covering the same region (second pass of the two-pass recipe; tile_size/2)")
    p_batch.add_argument("--limit", type=int, help="Max tiles to process (for testing)")
    p_batch.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model ID")
    p_batch.add_argument("--prompt", default=DEFAULT_PROMPT, help="Prompt version key")
    p_batch.add_argument("--run-id", help="Run identifier (default: timestamp)")
    p_batch.add_argument("--min-confidence", type=float, default=0.4,
                         help="Min confidence for deduped master output (default 0.4)")
    p_batch.add_argument("--db", action="store_true",
                         help="Upsert deduped extractions to Supabase ocr_labels table")
    p_batch.add_argument("--scout", action="store_true", help="Run a macro-level Scout Pass first")
    p_batch.add_argument("--legend", action="store_true",
                         help="After tiles, auto-extract the legend region (scout cartouche → local box finder) into legend_entry rows")
    p_batch.add_argument("--row-sequence", action="store_true", default=True,
                         help="Process tiles as row-strips (one sequence call per row, default on)")
    p_batch.add_argument("--no-row-sequence", dest="row_sequence", action="store_false",
                         help="Disable row-sequence mode; process each tile independently")
    p_batch.add_argument("--max-row-frames", type=int, default=4,
                         help="Max tiles per sequence call in row-sequence mode (default 4)")
    p_batch.add_argument("--adaptive", action="store_true",
                         help="Auto-scale render size by tile density (dense=2048, sparse=1024). "
                              "Only fetches a 512px preview for uncached tiles; already-cached "
                              "tiles use their stored resolution.")
    p_batch.add_argument("--tile-metres", type=float,
                         help="Size the tile grid to hold this much ground per call, read "
                              "from the sheet's own georeference (1400 is the measured "
                              "value; see docs/pipelines.md step 3). Overrides --tile-size, "
                              "--overlap and --render-size, and wins over --target-calls. "
                              "Needs 4+ GCPs on the map; falls back to --tile-size and says "
                              "so when the georeference cannot support it.")
    p_batch.add_argument("--target-calls", type=int,
                         help="Auto-scale tile size to hit this many API calls "
                              "(e.g. --target-calls 12). Adjusts render size proportionally. "
                              "Only sizes *up* from --tile-size, so it can make a run cheaper "
                              "and never finer — prefer --tile-metres.")
    p_batch.add_argument("--smart-grid", action="store_true",
                         help="Detect neatline from overview image and crop grid to content area")
    p_batch.add_argument("--skip-sparse", action="store_true",
                         help="Pre-screen tiles via local variance and skip text-sparse regions")
    p_batch.add_argument("--min-text-frac", type=float, default=0.01,
                         help="Min text-like pixel fraction for --skip-sparse (default 0.01)")
    p_batch.add_argument("--prior-run",
                         help="Path to a previous run dir; skip tiles that had 0 extractions")
    p_batch.add_argument("--crop",
                         help="Manual neatline crop: x,y,w,h in source image pixels. "
                              "Overrides --scout and --smart-grid.")
    p_batch.add_argument("--exclude",
                         help="';'-separated x,y,w,h rectangles (source px) whose reads are "
                              "discarded — the sheet's printed legend and street index, which "
                              "the `legend` and `street-index` passes read properly.")
    p_batch.add_argument("--tile-overrides",
                         help='JSON object mapping tile keys (x_y_w_h) to "low_res" or "skip". '
                              'Example: \'{"390_295_2000_2000":"skip","2390_0_2000_2000":"low_res"}\'')
    p_batch.add_argument("--low-res-render", type=int, default=512,
                         help="Render size (px) for low_res tiles (default 512)")
    p_batch.add_argument("--low-thinking", action="store_true",
                         help="Ask for thinking_level=low. Measured 2026-09-12: 54%% of a body "
                              "pass's bill and 93%% of a numeral pass's is thinking, and on "
                              "numerals turning it down was cheaper AND more accurate. Score a "
                              "run against the sheet's printed index before trusting it here.")
    p_batch.add_argument("--auto-priority", action="store_true",
                         help="Auto-fill the priority grid from a density pre-pass "
                              "(blank→skip, sparse→low_res). Ignored if --tile-overrides is given.")
    p_batch.add_argument("--skip-below", type=float, default=0.01,
                         help="Text-density fraction below which --auto-priority marks a tile skip (default 0.01)")
    p_batch.add_argument("--low-res-below", type=float, default=0.08,
                         help="Text-density fraction below which --auto-priority marks a tile low_res (default 0.08)")
    p_batch.add_argument("--aoi-px",
                         help="Study-area filter: x0,y0,x1,y1 in source image pixels. "
                              "Tiles outside it are marked skip; tiles inside keep "
                              "their existing priority.")
    p_batch.add_argument("--aoi",
                         help="Study area in WGS84 lng/lat — not supported here; "
                              "errors with a pointer to --aoi-px.")
    p_batch.add_argument("--clahe", action="store_true",
        help="Adaptive-contrast (CLAHE) pre-pass on each tile before the model call. "
             "OFF by default — for faded/low-contrast scans; not yet measured against EVAL-BASELINE.md")
    p_batch.add_argument("--clahe-clip", type=float, default=2.0,
        help="CLAHE clip limit (default 2.0; 1.0 is a no-op, >4 amplifies paper grain)")
    p_batch.add_argument("--clahe-grid", default="8",
        help="CLAHE grid: N for NxN, or ROWSxCOLS (default 8)")
    p_batch.add_argument("--colour-wash", action="store_true",
                         help="With --auto-priority, also demote water/vegetation wash. Opt-in: "
                              "its hue bands miss a warm-toned scan entirely and it scored 0.000 "
                              "on every tile of the 1882 cadastral")
    p_batch.add_argument("--wash-above", type=float, default=0.6,
                         help="Water/vegetation coverage above which --auto-priority demotes a tile "
                              "one step (default 0.6)")
    p_batch.set_defaults(func=cmd_batch)

    # dedup
    p_clean = sub.add_parser("clean", help="Fuzzy dedup + spatial fragment join for V1-style raw results")
    p_clean.add_argument("--map-id", help="Supabase maps.id UUID")
    p_clean.add_argument("--run-id", help="Filter by specific run_id")
    p_clean.add_argument("--local", help="Path to a run directory containing per-tile .json files")
    p_clean.add_argument("--db", action="store_true", help="Fetch from Supabase ocr_labels table")
    p_clean.add_argument("--apply", action="store_true", help="Apply results as Map Pins in Supabase")
    p_clean.add_argument("--user-id", help="User ID for pin attribution (default: system admin)")
    p_clean.add_argument("--min-confidence", type=float, default=0.1, help="Min confidence to include (default 0.1 — V1 recall mode)")
    p_clean.add_argument("--iou", type=float, default=0.15, help="IoU threshold for dedup (default 0.15)")
    p_clean.add_argument("--proximity", type=float, default=700, help="Max px between fragment centroids for axis join (default 700)")
    p_clean.add_argument("--angle-tol", type=float, default=20, help="Max degree difference for same-axis fragments (default 20)")
    p_clean.set_defaults(func=cmd_clean)

    p_dedup = sub.add_parser("dedup", help="Check and deduplicate existing labels from DB or local files")
    p_dedup.add_argument("--map-id", help="Supabase maps.id UUID")
    p_dedup.add_argument("--run-id", help="Filter by specific run_id")
    p_dedup.add_argument("--local", help="Path to a run directory containing per-tile .json files")
    p_dedup.add_argument("--db", action="store_true", help="Fetch labels from Supabase ocr_labels table")
    p_dedup.add_argument("--apply", action="store_true", help="Apply deduped labels as Map Pins in Supabase")
    p_dedup.add_argument("--user-id", help="User ID for Map Pins attribution (default: system admin)")
    p_dedup.add_argument("--min-confidence", type=float, default=0.4, help="Min confidence to include (default 0.4; uncertain tier = 0.4–0.7, confirmed = ≥0.7)")
    p_dedup.add_argument("--iou", type=float, default=0.15, help="IoU threshold for dedup (default 0.15)")
    p_dedup.set_defaults(func=cmd_dedup)

    p_merge = sub.add_parser("merge", help="Vote-merge several runs of one map into a new run (find everything first, then agree)")
    p_merge.add_argument("--map-id", required=True)
    p_merge.add_argument("--runs", required=True, help="Comma-separated run ids under outputs/<map>/runs/")
    p_merge.add_argument("--run-id", required=True, help="Name of the merged run to write")
    p_merge.add_argument("--tile-size", type=int, default=2400, help="Recorded on the DB rows' tile_w/h (default 2400)")
    p_merge.add_argument("--db", action="store_true", help="Upsert the merged rows to ocr_labels")
    p_merge.set_defaults(func=cmd_merge)

    # scout
    p_scout = sub.add_parser("scout", help="Run a macro-pass on the full map at low resolution")
    p_scout.add_argument("--map-id", help="Supabase maps.id UUID")
    p_scout.add_argument("--iiif-base", help="IIIF image service base URL")
    p_scout.add_argument("--render-size", type=int, default=4096, help="Target max dimension (default 4096)")
    p_scout.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model ID")
    p_scout.add_argument("--prompt", default="scout", help="Prompt version key (default 'scout')")
    p_scout.add_argument("--run-id", help="Run identifier")
    p_scout.add_argument("--preview", action="store_true", help="Save PNG preview with bbox overlay")
    p_scout.add_argument("--tile-metres", type=float,
                         help="Ground per call to propose a tile grid for (default 1400)")
    p_scout.add_argument("--skip-below", type=float, default=0.01,
                         help="Text-density fraction below which a tile is proposed skip "
                              "(default 0.01, same as batch --auto-priority)")
    p_scout.add_argument("--low-res-below", type=float, default=0.08,
                         help="Text-density fraction below which a tile is proposed low_res "
                              "(default 0.08, same as batch --auto-priority)")
    p_scout.add_argument("--save-triage", action="store_true",
                         help="Write the detected regions to maps.triage.regions, and the "
                              "proposed tile grid + priorities to maps.triage.grid "
                              "(needs --map-id). Still a proposal — triage has to accept it.")
    p_scout.set_defaults(func=cmd_scout)

    # preview
    p_prev = sub.add_parser("preview", help="Render bbox overlay from a saved JSON")
    p_prev.add_argument("--output", required=True, help="Path to .json output file")
    p_prev.add_argument("--iiif-base", help="IIIF base URL to re-fetch the tile image")
    p_prev.set_defaults(func=cmd_preview)

    # stitch
    p_st = sub.add_parser("stitch", help="Run OCR on multiple tiles and composite into one preview")
    p_st.add_argument("--map-id", help="Supabase maps.id UUID")
    p_st.add_argument("--iiif-base", help="IIIF image service base URL")
    p_st.add_argument("--crops", required=True, help="Semicolon-separated list of x,y,w,h crops")
    p_st.add_argument("--render-size", type=int, default=1024, help="Per-tile render width (default 1024)")
    p_st.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model ID")
    p_st.add_argument("--prompt", default=DEFAULT_PROMPT, help="Prompt version key")
    p_st.add_argument("--run-id", help="Run identifier for versioned output dir (default: timestamp)")
    p_st.add_argument("--sequence", action="store_true", help="Send adjacent tile pairs in one call for cross-seam label assembly")
    p_st.add_argument("--grid-cols", type=int, default=2, help="Tiles per sequence group (default 2 = pairs)")
    p_st.add_argument("--min-confidence", type=float, default=0.3, help="Filter extractions below this confidence (default 0.3)")
    p_st.add_argument("--adaptive", action="store_true", help="Auto-scale render size by tile density")
    p_st.set_defaults(func=cmd_stitch)

    # list-models
    sub.add_parser("self-check",
                   help="Check the pure helpers on the automated path"
                   ).set_defaults(func=cmd_self_check)

    p_sc = sub.add_parser("scale",
                          help="Print a sheet's metres-per-pixel and the tiling it implies "
                               "(no API calls, no tile fetches)")
    p_sc.add_argument("--map-id", help="Supabase maps.id UUID")
    p_sc.add_argument("--all", action="store_true",
                      help="Every georeferenced map, oldest first")
    p_sc.add_argument("--tile-metres", type=float,
                      help="Ground per call to size for (default 1400)")
    p_sc.set_defaults(func=cmd_scale)

    p_lm = sub.add_parser("list-models", help="List available Gemini models")
    p_lm.set_defaults(func=cmd_list_models)

    # ── detect-layout (local scipy — legend/cartouche box finder) ──────────────
    p_dl = sub.add_parser("detect-layout",
                          help="Local: find legend/cartouche boxes (no API)")
    p_dl.add_argument("--map-id", help="Supabase maps.id UUID")
    p_dl.add_argument("--iiif-base", help="IIIF image service base URL")
    p_dl.add_argument("--local-image", help="Local image file path (skips IIIF)")
    p_dl.add_argument("--overview-size", type=int, default=2000,
                      help="Max overview dimension for detection (default 2000)")
    p_dl.add_argument("--min-area", type=float, default=0.008,
                      help="Min box area as fraction of image (default 0.008)")
    p_dl.add_argument("--max-area", type=float, default=0.6,
                      help="Max box area as fraction of image (default 0.6)")
    p_dl.add_argument("--run-id", help="Run identifier (default: timestamp)")
    p_dl.set_defaults(func=cmd_detect_layout)

    # ── grid (the printed reference grid an index refers to) ───────────────────
    p_grid = sub.add_parser("grid",
        help="Read the sheet's printed reference grid into maps.triage.grid")
    p_grid.add_argument("--map-id", help="Supabase maps.id UUID")
    p_grid.add_argument("--iiif-base", help="IIIF image service base URL")
    p_grid.add_argument("--local-image", help="Read from a local file instead of IIIF")
    p_grid.add_argument("--render-size", type=int, default=2048,
                        help="Overview width (default 2048)")
    p_grid.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model ID")
    p_grid.add_argument("--run-id", help="Run identifier")
    p_grid.add_argument("--save-triage", action="store_true",
                        help="Write the grid to maps.triage.grid (needs --map-id)")
    p_grid.set_defaults(func=cmd_grid)

    # ── numerals (local Tesseract — legend-ref digit spotting) ─────────────────
    p_num = sub.add_parser("numerals",
                           help="Local: spot standalone numerals / legend refs (no API)")
    p_num.add_argument("--map-id", help="Supabase maps.id UUID")
    p_num.add_argument("--iiif-base", help="IIIF image service base URL")
    p_num.add_argument("--local-image", help="Local image file path (skips IIIF)")
    p_num.add_argument("--tile-size", type=int, default=2400,
                       help="Tile size in source px (default 2400)")
    p_num.add_argument("--overlap", type=int, default=300,
                       help="Tile overlap in source px (default 300)")
    p_num.add_argument("--render-size", type=int, default=2048,
                       help="Rendered tile width — bigger helps tiny digits (default 2048)")
    p_num.add_argument("--min-conf", type=float, default=40.0,
                       help="Min Tesseract confidence 0-100 (default 40)")
    p_num.add_argument("--iou", type=float, default=0.15,
                       help="IoU threshold for cross-tile dedup (default 0.15)")
    p_num.add_argument("--limit", type=int, help="Max tiles (for testing)")
    p_num.add_argument("--db", action="store_true",
                       help="Upsert results into ocr_labels as category='legend_ref'")
    p_num.add_argument("--run-id", help="Run identifier (default: timestamp)")
    p_num.set_defaults(func=cmd_numerals)

    # ── legend (Gemini — structured numbered-legend read) ──────────────────────
    p_leg = sub.add_parser("legend",
                           help="Gemini: read a numbered legend region into {n, name, grid}")
    p_leg.add_argument("--map-id", help="Supabase maps.id UUID")
    p_leg.add_argument("--iiif-base", help="IIIF image service base URL")
    p_leg.add_argument("--local-image", help="Local image file path (skips IIIF)")
    p_leg.add_argument("--regions", "--region", dest="regions",
                       help="Legend block(s) as x,y,w,h in source px, ';'-separated. "
                            "Omit with --map-id to read every `legend` region the "
                            "layout pass found — a sheet may print more than one.")
    p_leg.add_argument("--render-size", type=int, default=2600,
                       help="Rendered crop width — bigger helps tiny text (default 2600)")
    p_leg.add_argument("--model", default=DEFAULT_MODEL, help="Primary Gemini model")
    p_leg.add_argument("--bilingual", action="store_true",
                       help="Rows carry both Vietnamese and English names")
    p_leg.add_argument("--consensus", type=int, default=1,
                       help="Cross-check grid cells across N models; flag disagreements (default 1)")
    p_leg.add_argument("--db", action="store_true",
                       help="Upsert into ocr_labels as category='legend_entry'")
    p_leg.add_argument("--run-id", help="Run identifier (default: timestamp)")
    p_leg.set_defaults(func=cmd_legend)

    # street-index
    p_si = sub.add_parser("street-index",
                          help="Gemini: read a printed street directory (BẢNG CHỈ DẪN ĐƯỜNG PHỐ) "
                               "into rows positioned by the sheet's own grid")
    p_si.add_argument("--map-id", help="Supabase maps.id UUID")
    p_si.add_argument("--iiif-base", help="IIIF image service base URL")
    p_si.add_argument("--local-image", help="Local image file path (skips IIIF)")
    p_si.add_argument("--regions",
                      help="One or more directory columns as x,y,w,h in source px, "
                           "';'-separated. Omit with --map-id to read every "
                           "`name_list` (or `legend`) region the layout pass found.")
    p_si.add_argument("--band-height", type=int, default=1300,
                      help="Source px per call. A tall column read in one call renders to "
                           "unreadable text; ~30 rows per band keeps it legible (default 1300)")
    p_si.add_argument("--overlap", type=int, default=150,
                      help="Source px of band overlap, so a row split by a band edge is whole "
                           "in the next one (default 150)")
    p_si.add_argument("--render-size", type=int, default=1500,
                      help="Rendered crop width (default 1500)")
    p_si.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model")
    p_si.add_argument("--db", action="store_true",
                      help="Upsert into ocr_labels, positioned on the T\u1eeb\u2192\u0110\u1ebfn cell span")
    p_si.add_argument("--run-id", help="Run identifier (default: timestamp)")
    p_si.set_defaults(func=cmd_street_index)

    p_sif = sub.add_parser("street-index-fixture",
                           help="Write tests/fixtures/street-index-grid.json — the Python/TS "
                                "parity fixture for turning a grid reference into a rectangle")
    p_sif.add_argument("--map-id", required=True)
    p_sif.add_argument("--out", default="tests/fixtures/street-index-grid.json")
    p_sif.set_defaults(func=cmd_street_index_fixture)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
