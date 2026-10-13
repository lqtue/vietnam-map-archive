"""
Convert SAM2 binary mask outputs → polygon coordinate lists.

Input:  np.ndarray mask (H, W) bool/uint8  +  iou_prediction float
Output: PolygonResult(coords, holes, area, iou)  — coords are [[x,y], ...] in the mask's
        pixel space (typically 1024×1024 SAM2 input). Callers shift to full-image coords.
"""

from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass, field
from shapely.geometry import Polygon
from shapely.validation import make_valid


MIN_AREA_PX      = 400     # px² — 400 px² is standard (literature: removes scanner dust/hatch noise)
MAX_AREA_PX      = 200_000
# Courtyards: interior rings ≥ HOLE_MIN_AREA are architectural voids, below are label artifacts
HOLE_MIN_AREA    = 100     # px²; raise if map labels leave large mask holes
LABEL_CLOSE_PX   = 9      # morphological closing kernel size to seal text-label gaps in mask
DEDUP_IOU        = 0.5    # Jaccard threshold for within-tile deduplication
# epsilon = ratio × arc_length(contour) — scales with contour perimeter, not image size
# 1.5% of perimeter is standard for building outlines (OpenCV docs, SAMPolyBuild ISPRS 2024)
APPROX_EPS_RATIO = 0.015


@dataclass
class PolygonResult:
    coords: list[list[float]]                      # [[x, y], ...] closed exterior ring, mask-space pixels
    area:   float                                  # contour area in pixels
    iou:    float                                  # SAM2 iou_prediction score (0–1)
    seed:   dict | None = field(default=None)      # OCR seed that prompted this mask
    holes:  list[list[list[float]]] = field(default_factory=list)  # interior rings (courtyards)


def mask_components(
    mask: np.ndarray,
    iou: float = 0.0,
    seed: dict | None = None,
    min_area: int = MIN_AREA_PX,
    max_area: int = MAX_AREA_PX,
) -> list[PolygonResult]:
    """
    Convert every substantive component of one H×W mask to a PolygonResult.
    Returns an empty list if no contour passes area/validity checks.
    Interior rings (courtyards) ≥ HOLE_MIN_AREA px² are preserved in PolygonResult.holes.

    Preprocessing:
    - Morphological closing (LABEL_CLOSE_PX kernel) fills holes left by map text printed
      over building footprints — standard raster repair step before polygonization
      (literature: dilation+erosion to close label-induced gaps, ISPRS 2024).
    """
    assert mask.ndim == 2, f"Expected 2D mask, got shape {mask.shape}"
    m = (mask > 0).astype(np.uint8) * 255

    # Close holes caused by map labels printed over building footprints.
    # Morphological closing = dilation then erosion; preserves outer shape while sealing voids.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (LABEL_CLOSE_PX, LABEL_CLOSE_PX))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)

    # RETR_CCOMP gives a two-level hierarchy: outer contours + their direct holes
    contours, hierarchy = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if not contours or hierarchy is None:
        return []

    h = hierarchy[0]  # (N, 4): [next, prev, first_child, parent]

    # Top-level (outer) contours have parent == -1
    outer_indices = [i for i in range(len(contours)) if h[i][3] == -1]
    if not outer_indices:
        return []

    results = []
    for component_index, main_idx in enumerate(outer_indices):
        main_c = contours[main_idx]
        area = float(cv2.contourArea(main_c))
        if area < min_area or area > max_area:
            continue

        # Simplify with perimeter-relative epsilon (not a fixed pixel value)
        eps = APPROX_EPS_RATIO * cv2.arcLength(main_c, True)
        approx = cv2.approxPolyDP(main_c, eps, closed=True)
        if len(approx) < 3:
            continue
        coords = [[float(p[0][0]), float(p[0][1])] for p in approx]
        coords.append(coords[0].copy())

        # Collect interior rings: direct children of main_c above the courtyard threshold.
        # Holes below HOLE_MIN_AREA are residual label artifacts that MORPH_CLOSE didn't seal.
        holes: list[list[list[float]]] = []
        for i in range(len(contours)):
            if h[i][3] == main_idx and cv2.contourArea(contours[i]) >= HOLE_MIN_AREA:
                h_eps = APPROX_EPS_RATIO * cv2.arcLength(contours[i], True)
                h_approx = cv2.approxPolyDP(contours[i], h_eps, closed=True)
                if len(h_approx) >= 3:
                    ring = [[float(p[0][0]), float(p[0][1])] for p in h_approx]
                    holes.append([*ring, ring[0].copy()])

        ref = {**seed, "component_index": component_index, "component_count": len(outer_indices)} if seed else None
        results.append(PolygonResult(coords=coords, area=area, iou=float(iou), seed=ref, holes=holes))
    return results


def mask_to_polygon(mask, iou=0.0, seed=None, min_area=MIN_AREA_PX, max_area=MAX_AREA_PX):
    """Legacy single-object helper; the pipeline uses all substantive components."""
    parts = mask_components(mask, iou, seed, min_area, max_area)
    return max(parts, key=lambda part: part.area) if parts else None


def masks_to_polygons(
    masks: list[np.ndarray],
    iou_scores: list[float] | None = None,
    seeds: list[dict | None] | None = None,
    min_area: int = MIN_AREA_PX,
    max_area: int = MAX_AREA_PX,
    dedup_iou: float = DEDUP_IOU,
) -> list[PolygonResult]:
    """
    Convert a list of SAM2 masks to deduplicated PolygonResults.

    Dedup: sort by iou descending, suppress a candidate whose Jaccard IoU with
    any already-kept polygon exceeds dedup_iou.
    """
    n = len(masks)
    if iou_scores is None:
        iou_scores = [0.0] * n
    if seeds is None:
        seeds = [None] * n

    raw: list[PolygonResult] = []
    for mask, iou, seed in zip(masks, iou_scores, seeds):
        raw.extend(mask_components(mask, iou, seed, min_area, max_area))

    if not raw:
        return []

    raw.sort(key=lambda r: r.iou, reverse=True)

    kept: list[PolygonResult] = []
    kept_geom: list[Polygon] = []

    for cand in raw:
        original = Polygon(cand.coords, cand.holes)
        fixed = make_valid(original)
        if fixed.is_empty:
            continue
        components = [fixed] if fixed.geom_type == "Polygon" else [g for g in fixed.geoms if g.geom_type == "Polygon"]
        for component in components:
            if component.area < min_area or component.area > max_area:
                continue
            suppress = any((inter := component.intersection(kp).area) > 0
                           and inter / component.union(kp).area > dedup_iou for kp in kept_geom)
            if suppress:
                continue
            ref = dict(cand.seed or {})
            if not original.is_valid:
                ref["geometry_repaired"] = True
            kept.append(PolygonResult(
                coords=[list(c) for c in component.exterior.coords],
                holes=[[list(c) for c in ring.coords] for ring in component.interiors],
                area=float(component.area), iou=cand.iou, seed=ref or None))
            kept_geom.append(component)

    return kept


def shift_polygons(
    polys: list[PolygonResult],
    origin_x: float,
    origin_y: float,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> list[PolygonResult]:
    """
    Shift and scale polygon coords from mask-space to full-image space.

    For a tile at full-image offset (tx, ty) rendered to (render_w, render_h)
    from a source region of (src_w, src_h):
        scale_x = src_w / render_w
        scale_y = src_h / render_h
        origin  = (tx, ty)
    """
    result = []
    for p in polys:
        new_coords = [
            [c[0] * scale_x + origin_x, c[1] * scale_y + origin_y]
            for c in p.coords
        ]
        new_holes = [
            [[c[0] * scale_x + origin_x, c[1] * scale_y + origin_y] for c in ring]
            for ring in p.holes
        ]
        result.append(PolygonResult(
            coords=new_coords,
            area=p.area * scale_x * scale_y,
            iou=p.iou,
            seed=p.seed,
            holes=new_holes,
        ))
    return result
