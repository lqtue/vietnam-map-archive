#!/usr/bin/env python3
"""
MapSAM2 full-map inference: IIIF tiles → SAM2 → polygons → JSON / Supabase.

Two inference modes:
  automatic  — SAM2AutomaticMaskGenerator grid-scan (no prompts, no seeds needed)
  prompted   — SAM2ImagePredictor with per-tile OCR bbox seeds (requires --ocr-run-id)

Two model modes:
  base       — standard SAM2 checkpoint (local testing / M1)
  lora       — MapSAM2 LoRA fine-tuned checkpoint (Colab, requires --mapsam2-dir)

Quick local test (base SAM2, automatic, small region):
  python inference_tiles_as_video.py \\
    --map-id 0e02b9d9-9d40-4cca-8e41-8c8373d54d3b \\
    --checkpoint /path/to/sam2.1_hiera_small.pt \\
    --region 4800,4300,1024,1024 \\
    --out-json work/MapSAM2/outputs/test_run.json --preview

Full run on Colab with LoRA checkpoint + OCR seeds:
  python inference_tiles_as_video.py \\
    --map-id 0e02b9d9-9d40-4cca-8e41-8c8373d54d3b \\
    --checkpoint /content/drive/MyDrive/vma_mapsam2/models/building_sam2_hiera_small_r4_*.pth \\
    --lora --mapsam2-dir /content/MapSAM2 \\
    --ocr-run-id v1b \\
    --tile-size 1024 --overlap 128 \\
    --out-json footprints.json --preview --write-supabase
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

# ── project imports (work/ocr/scripts/ must be on sys.path) ──────────────────
_HERE = Path(__file__).parent
_OCR_SCRIPTS = _HERE.parent / "ocr" / "scripts"
if str(_OCR_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_OCR_SCRIPTS))

from iiif_tiles import fetch_crop, tile_grid, get_image_info
from masks_to_polygons import masks_to_polygons, shift_polygons, PolygonResult

# Optional: seeds module (only needed for prompted mode — --ocr-run-id, --prior)
try:
    from to_sam2_seeds import partition_seeds
    _HAS_SEEDS = True
except ImportError:
    _HAS_SEEDS = False


# ── SAM2 helpers ──────────────────────────────────────────────────────────────

def _sam2_config_path(encoder: str) -> str:
    """Return the hydra config path for a SAM2 encoder name.

    The `configs/` prefix is required, not cosmetic: upstream `sam2/__init__.py`
    calls `initialize_config_module("sam2")`, so hydra's search root is the
    package itself and a name without it fails with `Cannot find primary config
    'sam2.1/sam2.1_hiera_s.yaml'`.
    """
    mapping = {
        "vit_t": "configs/sam2.1/sam2.1_hiera_t.yaml",
        "vit_s": "configs/sam2.1/sam2.1_hiera_s.yaml",
        "vit_b": "configs/sam2.1/sam2.1_hiera_b+.yaml",
        "vit_l": "configs/sam2.1/sam2.1_hiera_l.yaml",
    }
    return mapping.get(encoder, "configs/sam2.1/sam2.1_hiera_s.yaml")


def load_model_automatic(checkpoint: str, encoder: str = "vit_s", device: str = "cpu"):
    """Load SAM2AutomaticMaskGenerator for grid-scan inference."""
    import torch
    from sam2.build_sam import build_sam2
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator

    cfg = _sam2_config_path(encoder)
    sam = build_sam2(cfg, checkpoint, device=device)
    return SAM2AutomaticMaskGenerator(
        sam,
        points_per_side=32,
        pred_iou_thresh=0.80,
        stability_score_thresh=0.90,
        min_mask_region_area=300,
    )


def load_model_predictor(checkpoint: str | None, encoder: str = "vit_s", device: str = "cpu",
                          lora: bool = False, mapsam2_dir: str | None = None):
    """Load SAM2ImagePredictor, optionally with LoRA weights."""
    import torch
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    cfg = _sam2_config_path(encoder)

    if lora and mapsam2_dir:
        # LoRA model: build base SAM2, then load MapSAM2 state dict which includes LoRA weights
        if mapsam2_dir not in sys.path:
            sys.path.insert(0, mapsam2_dir)
        sam_base = build_sam2(cfg, None, device=device)  # no base weights; LoRA ckpt has everything

        # Upstream `sam2/__init__.py` and MapSAM2's `sam2_train/__init__.py` BOTH call
        # hydra's initialize_config_module at import time, and the second one raises
        # "GlobalHydra is already initialized". build_sam2 above has already resolved
        # its config, so clearing the global here costs nothing and lets sam2_train
        # register its own. Import after the clear, not at the top of the branch.
        from hydra.core.global_hydra import GlobalHydra
        GlobalHydra.instance().clear()
        from sam_lora_image_encoder import LoRA_Sam

        # LoRA_Sam builds its own nn.Linear layers, which land on the default device
        # (cpu) however the model it wraps was built — so the first forward pass dies
        # with "Tensor for argument weight is on cpu but expected on mps". Moving the
        # wrapper, not the base, is what puts the two on one device.
        model = LoRA_Sam(sam_base, r=4).to(device)
        if checkpoint:  # None only from --self-check, which qualifies the machine
            ckpt = torch.load(checkpoint, map_location=device, weights_only=True)
            # MapSAM2's train_2d.py saves {'model': state_dict, 'parameter': args},
            # not a bare state dict — `.load_state_dict(ckpt)` on the wrapper fails
            # with 583 missing keys and two unexpected ones.
            state = ckpt.get("model", ckpt) if isinstance(ckpt, dict) else ckpt
            missing, unexpected = model.load_state_dict(state, strict=False)
            # strict=False would also swallow a checkpoint for another architecture,
            # so the tolerated gap is pinned. These three exist only in the video /
            # memory-attention path, which SAM2ImagePredictor never enters, and are
            # absent from checkpoints trained against MapSAM2's vendored sam2_train.
            VIDEO_ONLY = {
                "sam.no_obj_embed_spatial",
                "sam.obj_ptr_tpos_proj.weight",
                "sam.obj_ptr_tpos_proj.bias",
            }
            if set(missing) - VIDEO_ONLY or unexpected:
                raise RuntimeError(
                    f"checkpoint does not match the model: "
                    f"missing={sorted(set(missing) - VIDEO_ONLY)[:5]} "
                    f"unexpected={sorted(unexpected)[:5]}"
                )
        model.eval()
        predictor = SAM2ImagePredictor(model.sam)
    else:
        # Base SAM2 checkpoint
        sam = build_sam2(cfg, checkpoint, device=device)
        predictor = SAM2ImagePredictor(sam)

    return predictor


# ── tile inference ────────────────────────────────────────────────────────────

RENDER_SIZE = 1024   # SAM2 always processes 1024×1024


def build_text_mask(
    iiif_base: str,
    map_id: str,
    full_w: int,
    full_h: int,
    ocr_run_id: str | None = None,
    padding: int = 4,
) -> np.ndarray | None:
    """
    Fetch validated OCR bboxes and build a full-image binary mask (1 = text region).

    Literature rationale: text ink is identical to contour ink on historical maps.
    Masking text BEFORE segmentation prevents SAM from confusing letter strokes
    with building edges (Schlegel 2021/2023, Chen 2024 SODUCO benchmark).
    """
    import os, requests

    url = os.environ.get("PUBLIC_SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("PUBLIC_SUPABASE_ANON_KEY", "")
    if not url or not key:
        print("WARNING: No Supabase credentials; skipping text mask")
        return None

    params: dict[str, str] = {
        "map_id": f"eq.{map_id}",
        "select": "global_x,global_y,global_w,global_h",
        "status": "neq.rejected",
    }
    if ocr_run_id:
        params["run_id"] = f"eq.{ocr_run_id}"

    r = requests.get(
        f"{url}/rest/v1/ocr_extractions",
        params=params,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    r.raise_for_status()
    bboxes = r.json()
    if not bboxes:
        print("  No OCR bboxes found; text mask is empty")
        return None

    mask = np.zeros((full_h, full_w), dtype=np.uint8)
    for b in bboxes:
        x, y, w, h = int(b["global_x"]), int(b["global_y"]), int(b["global_w"]), int(b["global_h"])
        x0 = max(0, x - padding)
        y0 = max(0, y - padding)
        x1 = min(full_w, x + w + padding)
        y1 = min(full_h, y + h + padding)
        mask[y0:y1, x0:x1] = 1

    print(f"  Text mask: {len(bboxes)} bboxes → {mask.sum()} masked pixels")
    return mask


def apply_text_mask(img: np.ndarray, text_mask: np.ndarray,
                    tile_region: tuple[int, int, int, int],
                    render_w: int, render_h: int) -> np.ndarray:
    """
    Paint over text regions in a tile with the local paper background color.
    Uses median of non-masked pixels as fill — adapts to paper tone per tile.
    """
    import cv2 as _cv2

    tx, ty, tw, th = tile_region
    tile_mask = text_mask[ty:ty+th, tx:tx+tw]
    if tile_mask.sum() == 0:
        return img

    resized = _cv2.resize(tile_mask, (render_w, render_h), interpolation=_cv2.INTER_NEAREST)
    mask_bool = resized > 0

    if img.ndim == 3:
        bg_pixels = img[~mask_bool]
        if len(bg_pixels) > 0:
            fill = np.median(bg_pixels, axis=0).astype(np.uint8)
        else:
            fill = np.array([220, 215, 205], dtype=np.uint8)
        img[mask_bool] = fill
    else:
        bg_pixels = img[~mask_bool]
        fill = int(np.median(bg_pixels)) if len(bg_pixels) > 0 else 220
        img[mask_bool] = fill

    return img


def preprocess_tile(img: np.ndarray) -> np.ndarray:
    """
    Apply CLAHE contrast enhancement to a tile before SAM2 inference.

    Historical map scans suffer from paper aging, uneven lighting, and scanning
    artifacts that compress the effective dynamic range. CLAHE (Contrast Limited
    Adaptive Histogram Equalization) restores local contrast without over-amplifying
    noise — standard preprocessing for degraded document images.

    Literature basis: contrast stretching (α=0.8–1.25) and histogram equalization
    are mandatory preprocessing steps for historical map segmentation
    (ETH IKG / ISPRS 2024 pipeline).
    """
    import cv2 as _cv2
    clahe = _cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    if img.ndim == 3:
        lab = _cv2.cvtColor(img, _cv2.COLOR_RGB2LAB)
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        return _cv2.cvtColor(lab, _cv2.COLOR_LAB2RGB)
    return clahe.apply(img)


def _run_automatic(generator, tile_img: np.ndarray) -> list[PolygonResult]:
    """Run grid-scan automatic segmentation on one tile."""
    masks_data = generator.generate(tile_img)
    masks  = [m["segmentation"] for m in masks_data]
    scores = [m["predicted_iou"] for m in masks_data]
    return masks_to_polygons(masks, scores)


def _run_prompted(predictor, tile_img: np.ndarray,
                  seeds: list[dict],
                  prompt: str = "box",
                  pick: str | None = None) -> list[PolygonResult]:
    """Run prompted inference for each OCR seed on one tile.

    `prompt` decides what SAM2 is asked with:

      box        the label's text box (the original behaviour)
      point      the label's centroid, one positive point
      box+point  both, which anchors the point inside the box

    Why this is a flag and not a constant. A box prompt asks SAM2 "what is
    inside this rectangle", and the rectangle is a *label*, so the honest
    answer is the lettering and the paper it sits on — not the building the
    label names. Inspected on the 1882 sheet, the highest-confidence masks were
    the ones that had simply redrawn their own prompt: in the 0.90-1.00 band the
    median mask agreed with its seed box at IoU 0.87. A point prompt asks
    "what is the thing at this spot" instead, which is the question we mean.

    `pick` decides which of the three multimask outputs is kept, and it matters
    more than it looks. SAM2 returns roughly sub-part / part / whole and scores
    them by predicted IoU; for a box prompt the box-filling mask scores highest
    almost by construction, so `argmax(score)` selects exactly the failure above
    — and then that same score was being used downstream as a quality gate,
    which made the gate circular. For a point prompt the three outputs are
    genuinely different scales of the same thing and the largest is usually the
    enclosing plot, so `largest` is the default there.

    Defaults preserve the old behaviour for `box` and pick `largest` otherwise.
    """
    import torch
    predictor.set_image(tile_img)
    if pick is None:
        pick = "score" if prompt == "box" else "largest"

    all_masks: list[np.ndarray] = []
    all_scores: list[float] = []
    all_seed_refs: list[dict] = []

    for seed in seeds:
        kwargs: dict = {"multimask_output": True}
        if prompt in ("box", "box+point"):
            kwargs["box"] = np.array(seed["box"], dtype=np.float32)  # [x1, y1, x2, y2]
        if prompt in ("point", "box+point"):
            px, py = seed["point"]
            kwargs["point_coords"] = np.array([[px, py]], dtype=np.float32)
            kwargs["point_labels"] = np.array([1], dtype=np.int32)   # 1 = foreground

        with torch.inference_mode():
            masks, scores, _ = predictor.predict(**kwargs)

        if pick == "largest":
            best = int(np.argmax([m.sum() for m in masks]))
        else:
            best = int(np.argmax(scores))
        all_masks.append(masks[best])
        all_scores.append(float(scores[best]))
        all_seed_refs.append(seed)

    return masks_to_polygons(all_masks, all_scores, all_seed_refs)


def infer_tile(
    model,
    iiif_base: str,
    tile_region: tuple[int, int, int, int],   # (x, y, w, h) in full-image pixels
    seeds: list[dict] | None,
    mode: str,
    text_mask: np.ndarray | None = None,
    prompt: str = "box",
    pick: str | None = None,
) -> list[PolygonResult]:
    """
    Fetch one IIIF tile, run inference, return polygons in full-image pixel coords.
    """
    tx, ty, tw, th = tile_region

    pil = fetch_crop(iiif_base, tx, ty, tw, th, size=RENDER_SIZE)
    render_w, render_h = pil.size   # should be RENDER_SIZE × (RENDER_SIZE or smaller)
    img_np = preprocess_tile(np.array(pil))

    if text_mask is not None:
        img_np = apply_text_mask(img_np, text_mask, tile_region, render_w, render_h)

    if mode == "automatic":
        polys = _run_automatic(model, img_np)
    else:
        polys = _run_prompted(model, img_np, seeds or [], prompt=prompt, pick=pick)

    if not polys:
        return []

    # Scale mask-space coords → full-image pixel coords
    scale_x = tw / render_w
    scale_y = th / render_h
    return shift_polygons(polys, origin_x=tx, origin_y=ty,
                          scale_x=scale_x, scale_y=scale_y)


# ── cross-tile dedup ──────────────────────────────────────────────────────────

def global_dedup(polys: list[PolygonResult], iou_thresh: float = 0.3) -> list[PolygonResult]:
    """
    Cross-tile Jaccard IoU dedup. Called after all tiles are collected.

    Threshold is 0.3 (not 0.5) because buildings at tile boundaries are only partially
    visible in each tile: each tile produces a partial-footprint polygon, and the two
    partials may overlap by less than 50% even though they represent the same building.
    Literature: tile stitching uses IoU > 0 (any overlap triggers reassignment);
    0.3 is a practical middle ground that catches boundary duplicates without
    merging genuinely different-but-adjacent buildings. (ISPRS 2024)
    """
    from shapely.validation import make_valid
    from shapely.geometry import Polygon

    polys.sort(key=lambda p: p.iou, reverse=True)
    kept: list[PolygonResult] = []
    kept_geom: list[Polygon] = []

    for cand in polys:
        try:
            p = make_valid(Polygon(cand.coords))
            if p.is_empty:
                continue
            suppress = any(
                (inter := p.intersection(kp).area) > 0
                and inter / p.union(kp).area > iou_thresh
                for kp in kept_geom
            )
            if not suppress:
                kept.append(cand)
                kept_geom.append(p)
        except Exception as e:
            print(f"WARNING: dedup intersection failed for polygon (iou={cand.iou:.3f}): {e}")
            kept.append(cand)
    return kept


# ── watershed post-processing ─────────────────────────────────────────────

def _nearest_original(
    coords: list[list[float]],
    polys: list[PolygonResult],
) -> PolygonResult | None:
    """Which pre-watershed polygon a refined ring came from.

    Cheap on purpose: the centroid of the refined ring against each original's
    bounding box, falling back to the nearest centroid when it lands in none
    (watershed boundaries sit a pixel or two outside the mask they came from).
    A per-pair shapely intersection would be more exact and is not worth it at
    ~100 polygons a sheet.
    """
    if not polys:
        return None
    cx = sum(c[0] for c in coords) / len(coords)
    cy = sum(c[1] for c in coords) / len(coords)

    inside: list[tuple[float, PolygonResult]] = []
    for p in polys:
        xs = [c[0] for c in p.coords]
        ys = [c[1] for c in p.coords]
        if min(xs) <= cx <= max(xs) and min(ys) <= cy <= max(ys):
            inside.append((p.area, p))
    if inside:
        # Smallest containing box wins: a split fragment sits inside its own
        # original and also inside anything larger that happens to span it.
        return min(inside, key=lambda t: t[0])[1]

    def dist2(p: PolygonResult) -> float:
        px = sum(c[0] for c in p.coords) / len(p.coords)
        py = sum(c[1] for c in p.coords) / len(p.coords)
        return (px - cx) ** 2 + (py - cy) ** 2

    return min(polys, key=dist2)


def watershed_refine(
    polys: list[PolygonResult],
    region: tuple[int, int, int, int],
    scale: float = 0.25,
) -> list[PolygonResult]:
    """
    Apply Meyer Watershed to polygon edge maps for topology-guaranteed closed shapes.

    SODUCO benchmark (Chen 2024): switching from connected components to watershed
    improved F1 from 0.27 → 0.59 at IoU 0.5. The watershed floods gradient basins
    to produce 1-pixel-wide, topologically closed boundaries.
    """
    import cv2
    from shapely.geometry import Polygon as ShapelyPoly
    from shapely.validation import make_valid

    rx, ry, rw, rh = region
    h = int(rh * scale)
    w = int(rw * scale)
    if h < 64 or w < 64:
        return polys

    edge_map = np.zeros((h, w), dtype=np.uint8)
    for p in polys:
        pts = np.array([
            [int((c[0] - rx) * scale), int((c[1] - ry) * scale)]
            for c in p.coords
        ], dtype=np.int32)
        cv2.polylines(edge_map, [pts], isClosed=True, color=255, thickness=1)

    dist = cv2.distanceTransform(255 - edge_map, cv2.DIST_L2, 5)
    _, markers = cv2.connectedComponents((dist > 2).astype(np.uint8))

    edge_3ch = cv2.cvtColor(edge_map, cv2.COLOR_GRAY2BGR)
    markers = markers.astype(np.int32)
    cv2.watershed(edge_3ch, markers)

    refined: list[PolygonResult] = []
    for label_id in range(2, markers.max() + 1):
        basin = (markers == label_id).astype(np.uint8) * 255
        contours, _ = cv2.findContours(basin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        c = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        if area < 20:
            continue
        eps = 0.015 * cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, eps, closed=True)
        if len(approx) < 3:
            continue
        coords = [
            [float(pt[0][0]) / scale + rx, float(pt[0][1]) / scale + ry]
            for pt in approx
        ]
        real_area = area / (scale * scale)
        if real_area < 400 or real_area > 200_000:
            continue
        try:
            sp = make_valid(ShapelyPoly(coords))
            if sp.is_empty:
                continue
        except Exception:
            continue
        # Carry the prompt through. Watershed rebuilds geometry from an edge map,
        # so without this every polygon comes back with seed=None and iou=0.5 —
        # which throws away the OCR label that is the entire point of prompted
        # mode, and flattens `confidence` (written from iou by --write-supabase)
        # to a constant. Measured before this line existed: 0 of 106 polygons
        # carried a label and all 106 claimed 0.5.
        #
        # A refined polygon is attributed to whichever original it overlaps most,
        # by centroid containment first and area overlap second. Watershed splits
        # one mask into several, so several refined polygons may share a seed —
        # correct, since a courtyard block split in two is still that building.
        owner = _nearest_original(coords, polys)
        refined.append(PolygonResult(
            coords=coords,
            area=real_area,
            iou=owner.iou if owner else 0.5,
            seed=owner.seed if owner else None,
        ))

    if len(refined) < len(polys) * 0.5:
        print(f"  Watershed produced too few polygons ({len(refined)} vs {len(polys)}); keeping originals")
        return polys

    print(f"  Watershed: {len(polys)} → {len(refined)} polygons")
    return refined


# ── preview rendering ─────────────────────────────────────────────────────────

def save_preview(
    iiif_base: str,
    region: tuple[int, int, int, int],
    polys: list[PolygonResult],
    out_path: str,
    preview_size: int = 2048,
) -> None:
    """Render region + polygon outlines as a PNG for visual QA."""
    import cv2
    from PIL import Image

    rx, ry, rw, rh = region
    pil = fetch_crop(iiif_base, rx, ry, rw, rh, size=preview_size)
    img = np.array(pil)
    h, w = img.shape[:2]
    if rw == 0 or rh == 0:
        print("WARNING: preview region has zero dimension, skipping overlay")
        return
    scale_x = w / rw
    scale_y = h / rh

    overlay = img.copy()
    for poly in polys:
        pts = np.array([
            [int((c[0] - rx) * scale_x), int((c[1] - ry) * scale_y)]
            for c in poly.coords
        ], dtype=np.int32)
        cv2.polylines(overlay, [pts], isClosed=True, color=(0, 120, 255), thickness=2)
        cx = int(np.mean([c[0] for c in poly.coords]))
        cy = int(np.mean([c[1] for c in poly.coords]))
        cv2.circle(overlay, (int((cx - rx) * scale_x), int((cy - ry) * scale_y)),
                   3, (255, 60, 0), -1)

    Image.fromarray(overlay).save(out_path)
    print(f"Preview saved → {out_path}")


# ── Supabase writeback ────────────────────────────────────────────────────────

def update_pipeline_status(map_id: str, stage: str, **kwargs) -> None:
    """No-op since migration 056.

    map_pipeline_status is a view: the seg stages are derived from the
    pipeline_jobs row the worker opens and closes around this script. Kept as a
    stub so a hand-run inference does not crash on the call.
    """
    return None


def write_to_supabase(
    polys: list[PolygonResult],
    map_id: str,
    feature_type: str = "building",
    source: str = "sam-auto",
    run_id: str | None = None,
) -> int:
    """Insert polygons into footprint_submissions. Returns inserted count."""
    import os
    import requests

    url  = os.environ.get("PUBLIC_SUPABASE_URL", "").rstrip("/")
    key  = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("PUBLIC_SUPABASE_ANON_KEY")
    hdrs = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    endpoint = f"{url}/rest/v1/footprint_submissions"

    rows = []
    for p in polys:
        # Column names are footprint_submissions', not PolygonResult's: the
        # outer ring is `pixel_polygon` (full-image source px, same grid as
        # ocr_extractions.global_*), and SAM2's IoU is the row's confidence.
        # Holes are dropped — the column holds one ring.
        row: dict[str, Any] = {
            "map_id":        map_id,
            "pixel_polygon": p.coords,
            "feature_type":  feature_type,
            "status":        "needs_review",
            "source":        source,
            "confidence":    round(p.iou, 4),
        }
        if run_id:
            row["run_id"] = run_id
        # A polygon SAM2 found because OCR pointed at it already knows its own
        # name — carry it now rather than making the join pass rediscover it.
        if p.seed:
            if p.seed.get("text"):
                row["name"] = p.seed["text"]
            if p.seed.get("category"):
                row["category"] = p.seed["category"]
        rows.append(row)

    # The GPU machine is normally a Colab session holding a `worker_keys` token
    # and nothing else. Since migration 089 the publishable key may not INSERT
    # here, so a direct PostgREST write needs SUPABASE_SERVICE_KEY — full
    # database access, on a runtime we do not own. Prefer the worker API, which
    # is the surface /api/pipeline/results exists to be; fall back to PostgREST
    # for a hand-run on a machine that already has the service key.
    api_url = os.environ.get("VMA_API_URL", "").rstrip("/")
    api_key = os.environ.get("VMA_WORKER_KEY", "")
    if api_url and api_key:
        # MAX_ROWS on the endpoint is 500.
        for i in range(0, len(rows), 500):
            resp = requests.post(
                f"{api_url}/api/pipeline/results",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"footprints": rows[i:i + 500]},
                timeout=120,
            )
            resp.raise_for_status()
        return len(rows)

    if not key:
        raise EnvironmentError(
            "No way to write footprints: set VMA_API_URL + VMA_WORKER_KEY (the "
            "worker path), or SUPABASE_SERVICE_KEY for a direct write."
        )
    resp = requests.post(endpoint, headers=hdrs, json=rows)
    resp.raise_for_status()
    return len(rows)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MapSAM2 full-map inference")
    p.add_argument("--map-id", help="maps.id UUID")
    p.add_argument("--iiif-base",   help="IIIF image base URL (fetched from Supabase if omitted)")
    p.add_argument("--checkpoint", help="Path to SAM2 or MapSAM2 .pt/.pth checkpoint")
    p.add_argument("--encoder",     default="vit_s",
                   choices=["vit_t", "vit_s", "vit_b", "vit_l"],
                   help="SAM2 encoder variant (must match checkpoint)")
    p.add_argument("--lora",        action="store_true",
                   help="Load as MapSAM2 LoRA checkpoint (requires --mapsam2-dir)")
    p.add_argument("--mapsam2-dir", default="/content/MapSAM2",
                   help="Path to cloned MapSAM2 repo (Colab: /content/MapSAM2)")
    p.add_argument("--mode",        default="automatic",
                   choices=["automatic", "prompted"],
                   help="automatic=grid-scan, prompted=OCR-seeded")
    p.add_argument("--ocr-run-id",  help="ocr_extractions run_id for seed bboxes (prompted mode)")
    p.add_argument("--run-id",      help="run_id stamped on every footprint_submissions row. The "
                                         "worker always passes one (enqueue_seg.mjs mints it), and "
                                         "without this argparse rejected the whole job.")
    p.add_argument("--prior",       help="modern_prior.py blocks.geojson to prompt from as well as "
                                         "(or instead of) OCR. Nameless, so its polygons carry no label")
    p.add_argument("--region",      help="x,y,w,h crop in full-image pixels (default: full image)")
    p.add_argument("--tile-size",   type=int, default=1024, help="Tile width/height in source pixels")
    p.add_argument("--overlap",     type=int, default=128,  help="Tile overlap in source pixels")
    p.add_argument("--device",      default="cpu", help="cpu | cuda | mps")
    p.add_argument("--out-json",    default="footprints.json")
    p.add_argument("--preview",     action="store_true", help="Save preview PNG")
    p.add_argument("--write-supabase", action="store_true")
    p.add_argument("--feature-type",   default="building")
    p.add_argument("--text-mask",    action="store_true",
                   help="Mask out OCR text bboxes before SAM inference (literature: prevents text→edge confusion)")
    p.add_argument("--watershed",    action="store_true",
                   help="Apply Meyer Watershed post-processing for topology-guaranteed closed shapes")
    p.add_argument("--prompt",       default="box", choices=["box", "point", "box+point"],
                   help="what SAM2 is asked with: the label's text box, its centroid, or both")
    p.add_argument("--pick",         default=None, choices=["score", "largest"],
                   help="which multimask output to keep (default: score for box, largest otherwise)")
    p.add_argument("--self-check",   action="store_true",
                   help="Build the model on --device and run one frame of noise through it; "
                        "no weights, no network. Use this to qualify a new machine.")
    return p.parse_args()


def self_check(device: str, encoder: str, mapsam2_dir: str | None) -> None:
    """Qualify a machine without a checkpoint or a map.

    Everything that has actually broken on this path is a wiring problem visible
    with random pixels: the two hydra config modules colliding on import, and the
    LoRA layers sitting on a different device from the model they wrap. A real run
    costs IIIF fetches and a 90 MB checkpoint before it reaches either.
    """
    import numpy as _np
    import torch as _torch

    print(f"torch {_torch.__version__}  device={device}")
    if device == "mps":
        print(f"  mps available: {_torch.backends.mps.is_available()}")

    t0 = time.time()
    predictor = load_model_predictor(
        checkpoint=None, encoder=encoder, device=device,
        lora=bool(mapsam2_dir), mapsam2_dir=mapsam2_dir,
    )
    print(f"  model built in {time.time() - t0:.1f}s")

    frame = (_np.random.rand(RENDER_SIZE, RENDER_SIZE, 3) * 255).astype(_np.uint8)
    t0 = time.time()
    predictor.set_image(frame)
    masks, scores, _ = predictor.predict(
        box=_np.array([[300, 300, 600, 600]]), multimask_output=False
    )
    print(f"  forward pass in {time.time() - t0:.1f}s -> mask {masks.shape}, score {float(scores[0]):.3f}")
    print("self-check OK")


def resolve_iiif_base(map_id: str) -> str:
    """Fetch iiif_image URL from Supabase maps table."""
    import os, requests
    url = os.environ.get("PUBLIC_SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("PUBLIC_SUPABASE_ANON_KEY", "")
    if not url or not key:
        # Both are public values, so this is a setup omission rather than a
        # secret problem — say which two names, since a bare KeyError on
        # PUBLIC_SUPABASE_URL reads like the worker needs database credentials.
        raise EnvironmentError(
            "Reading the sheet needs PUBLIC_SUPABASE_URL and PUBLIC_SUPABASE_ANON_KEY. "
            "Both are public; the worker token is separate and only writes."
        )
    r = requests.get(
        f"{url}/rest/v1/maps",
        params={"id": f"eq.{map_id}", "select": "iiif_image"},
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    r.raise_for_status()
    rows = r.json()
    if not rows or not rows[0].get("iiif_image"):
        raise ValueError(f"No iiif_image found for map {map_id}")
    return rows[0]["iiif_image"]


def main() -> None:
    args = parse_args()

    if args.self_check:
        self_check(args.device, args.encoder, args.mapsam2_dir if args.lora else None)
        return

    # ── validate args ──────────────────────────────────────────────────────────
    # Required for a real run, but not for --self-check, which returns above.
    for req in ("map_id", "checkpoint"):
        if not getattr(args, req):
            raise SystemExit(f"--{req.replace('_', '-')} is required (or use --self-check)")
    if not os.path.exists(args.checkpoint):
        raise FileNotFoundError(f"Checkpoint not found: {args.checkpoint}")
    if args.overlap >= args.tile_size:
        raise ValueError(
            f"--overlap ({args.overlap}) must be less than --tile-size ({args.tile_size})"
        )
    # LoRA fine-tuned checkpoints are trained for prompted (bbox) inference, not grid-scan.
    # The MapSAM2 paper eliminates grid-based automatic prompting for areal features
    # (buildings) in favour of trainable query tokens + bbox prompts. Running a LoRA
    # checkpoint in automatic mode wastes the fine-tuning and produces more false positives.
    if args.lora and args.mode == "automatic":
        print(
            "WARNING: --lora with --mode automatic bypasses the fine-tuned prompt pathway. "
            "Use --mode prompted --ocr-run-id <id> for best results with a LoRA checkpoint."
        )

    # ── resolve IIIF base ──────────────────────────────────────────────────────
    iiif_base = args.iiif_base or resolve_iiif_base(args.map_id)
    print(f"IIIF base: {iiif_base}")

    # ── parse region ───────────────────────────────────────────────────────────
    if args.region:
        rx, ry, rw, rh = map(int, args.region.split(","))
    else:
        info = get_image_info(iiif_base)
        rx, ry = 0, 0
        rw, rh = info["width"], info["height"]
        print(f"Full image: {rw}×{rh}")

    region = (rx, ry, rw, rh)

    # ── build tile grid ────────────────────────────────────────────────────────
    tiles = list(tile_grid(rw, rh, tile=args.tile_size, overlap=args.overlap,
                           region=(rx, ry, rw, rh)))
    print(f"Tiles: {len(tiles)} ({args.tile_size}px, {args.overlap}px overlap)")

    # ── load OCR seeds ─────────────────────────────────────────────────────────
    ocr_seeds_by_tile: dict[tuple, list[dict]] = {}
    if args.mode == "prompted":
        if not (args.ocr_run_id or args.prior):
            print("WARNING: prompted mode requires --ocr-run-id or --prior; falling back to automatic")
            args.mode = "automatic"
        elif not _HAS_SEEDS:
            print("WARNING: to_sam2_seeds.py not found; falling back to automatic")
            args.mode = "automatic"
        else:
            all_seeds: list[dict] = []
            if args.ocr_run_id:
                print(f"Loading OCR seeds for run '{args.ocr_run_id}'...")
                from to_sam2_seeds import load_seeds_for_map
                all_seeds += load_seeds_for_map(args.map_id, args.ocr_run_id)
            if args.prior:
                # Nameless block prompts from modern_prior.py. They union with the
                # OCR seeds rather than replacing them: OCR seeds carry a label and
                # so name their polygon at birth, and a block that a label already
                # sits on is worth prompting twice from two boxes, not once.
                print(f"Loading prior seeds from {args.prior} ...")
                from to_sam2_seeds import load_seeds_from_prior
                all_seeds += load_seeds_from_prior(args.prior, args.map_id)
            # One owner per seed. Calling seeds_for_tile per tile instead gives
            # every seed in an overlap band to both its neighbours and every
            # corner seed to four — on the 1959 sheet that was 17,317 prompts
            # for 13,037 seeds, a third of the GPU spent on masks the cross-tile
            # dedup then throws away.
            from to_sam2_seeds import partition_seeds
            ocr_seeds_by_tile, seed_counts = partition_seeds(
                all_seeds, tiles, render_size=RENDER_SIZE
            )
            loaded = len([t for t in ocr_seeds_by_tile.values() if t])
            print(f"Seeds loaded: {seed_counts['placed']} across {loaded}/{len(tiles)} tiles")
            if seed_counts["oversized"]:
                print(f"  {seed_counts['oversized']} dropped: box fills its tile, "
                      f"which prompts SAM2 with the whole crop and means nothing")
            if seed_counts["unplaced"]:
                print(f"  WARNING: {seed_counts['unplaced']} seeds fell outside every tile")

    # ── load model ────────────────────────────────────────────────────────────
    print(f"Loading model ({args.mode}, {'LoRA' if args.lora else 'base'})...")
    if args.mode == "automatic":
        model = load_model_automatic(args.checkpoint, args.encoder, args.device)
    else:
        model = load_model_predictor(args.checkpoint, args.encoder, args.device,
                                     lora=args.lora, mapsam2_dir=args.mapsam2_dir)

    # ── build text mask ──────────────────────────────────────────────────────
    text_mask = None
    if args.text_mask:
        print("Building text mask from OCR bboxes...")
        text_mask = build_text_mask(
            iiif_base, args.map_id, rx + rw, ry + rh,
            ocr_run_id=args.ocr_run_id,
        )

    # ── tile loop ─────────────────────────────────────────────────────────────
    all_polys: list[PolygonResult] = []
    t0 = time.time()

    for i, tile in enumerate(tiles):
        tx, ty, tw, th = tile
        seeds = ocr_seeds_by_tile.get(tile, [])
        print(f"  Tile {i+1}/{len(tiles)}: ({tx},{ty},{tw},{th})  seeds={len(seeds)}", end=" ")
        try:
            polys = infer_tile(model, iiif_base, tile, seeds, args.mode,
                               text_mask=text_mask, prompt=args.prompt, pick=args.pick)
            print(f"→ {len(polys)} polygons")
            all_polys.extend(polys)
        except Exception as e:
            print(f"→ ERROR: {e}")

    elapsed = time.time() - t0
    print(f"\nRaw polygons: {len(all_polys)}  ({elapsed:.1f}s)")

    # ── global dedup ──────────────────────────────────────────────────────────
    all_polys = global_dedup(all_polys)
    print(f"After dedup:  {len(all_polys)}")

    # ── watershed post-processing ─────────────────────────────────────────────
    if args.watershed and all_polys:
        all_polys = watershed_refine(all_polys, region)

    # ── write JSON ────────────────────────────────────────────────────────────
    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "map_id":    args.map_id,
        "region":    list(region),
        "mode":      args.mode,
        "lora":      args.lora,
        "ocr_run_id": args.ocr_run_id,
        "tile_size": args.tile_size,
        "overlap":   args.overlap,
        "n_tiles":   len(tiles),
        "n_polys":   len(all_polys),
        "elapsed_s": round(elapsed, 1),
        "polygons": [
            {
                "coords": p.coords,
                "holes":  p.holes,
                "area":   round(p.area, 1),
                "iou":    round(p.iou, 4),
                "seed":   p.seed,
            }
            for p in all_polys
        ],
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"Written → {out}")

    # ── preview ───────────────────────────────────────────────────────────────
    if args.preview:
        preview_path = str(out).replace(".json", "_preview.png")
        save_preview(iiif_base, region, all_polys, preview_path)

    # ── Supabase writeback ────────────────────────────────────────────────────
    if args.write_supabase:
        from datetime import datetime, timezone
        # The job's own run id when it has one; the output stem is the fallback for
        # a hand-run pass. Deriving it from the filename alone labelled every run
        # "footprints", which made join_labels' seg-run pinning meaningless.
        seg_run_id = args.run_id or out.stem

        update_pipeline_status(args.map_id, "seg_queued",
                               seg_started_at=datetime.now(timezone.utc).isoformat())

        # `source` is constrained to volunteer | sam-auto | sam-corrected |
        # import (mig 055); the prompted/automatic distinction lives in the run.
        n = write_to_supabase(all_polys, args.map_id, args.feature_type, "sam-auto", seg_run_id)
        print(f"Supabase: inserted {n} rows into footprint_submissions")

        update_pipeline_status(args.map_id, "seg_done",
                               seg_run_id=seg_run_id,
                               seg_finished_at=datetime.now(timezone.utc).isoformat())


if __name__ == "__main__":
    main()
