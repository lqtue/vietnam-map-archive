#!/usr/bin/env python3
"""
Evaluate MapSAM2 inference output against ground-truth footprints.

Benchmarks against SODUCO (Chen et al. 2024): best pipeline COCO PQ = 51.1%.

SODUCO baseline, verified against the paper 2026-09-19 (scite, DOI
10.1371/journal.pone.0298217). Chen, Chazalon & Carlinet (2024) report **COCO Panoptic
Quality throughout** — "We mainly follow the evaluation protocol used by [5,8], which relies
on the COCO Panoptic metric". Their figures: **51.1% PQ** is the best pipeline (U-Net with
contrast + TPS augmentation); 46.7% is U-Net before augmentation; **47.1% -> 45.1%** is the
mini-U-Net footprint ablation. **No F1 score appears.** So quote 51.1% COCO PQ. The
"F1=0.59 @ IoU 0.5" this file used to carry is unsourced and was not found in the paper;
47.1% was real but was one row of an ablation, not the benchmark's headline.

Usage:
  python evaluate.py --predictions footprints.json --ground-truth gt.json
  python evaluate.py --predictions footprints.json --map-id <uuid>  # fetch GT from Supabase
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon
from shapely.validation import make_valid


@dataclass
class Metrics:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    matched_ious: list[float] = None

    def __post_init__(self):
        if self.matched_ious is None:
            self.matched_ious = []

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def mean_iou(self) -> float:
        return float(np.mean(self.matched_ious)) if self.matched_ious else 0.0


def polygon_f1(
    pred_coords: list[list[list[float]]],
    gt_coords: list[list[list[float]]],
    iou_threshold: float = 0.5,
) -> Metrics:
    """Compute polygon-level F1 at a given IoU threshold."""
    preds = []
    for c in pred_coords:
        try:
            p = make_valid(Polygon(c))
            if not p.is_empty:
                preds.append(p)
        except Exception:
            pass

    gts = []
    for c in gt_coords:
        try:
            g = make_valid(Polygon(c))
            if not g.is_empty:
                gts.append(g)
        except Exception:
            pass

    matched_gt = set()
    metrics = Metrics()

    for pred in preds:
        best_iou = 0.0
        best_gt_idx = -1
        for j, gt in enumerate(gts):
            if j in matched_gt:
                continue
            try:
                inter = pred.intersection(gt).area
                union = pred.union(gt).area
                iou = inter / union if union > 0 else 0.0
            except Exception:
                iou = 0.0
            if iou > best_iou:
                best_iou = iou
                best_gt_idx = j

        if best_iou >= iou_threshold and best_gt_idx >= 0:
            metrics.tp += 1
            metrics.matched_ious.append(best_iou)
            matched_gt.add(best_gt_idx)
        else:
            metrics.fp += 1

    metrics.fn = len(gts) - len(matched_gt)
    return metrics


def geometric_quality(coords_list: list[list[list[float]]]) -> dict:
    """Compute geometric quality metrics: compactness, convexity, rectangularity."""
    import cv2

    compactness_vals = []
    convexity_vals = []
    rectangularity_vals = []

    for coords in coords_list:
        try:
            p = make_valid(Polygon(coords))
            if p.is_empty:
                continue

            area = p.area
            perimeter = p.length
            if perimeter > 0:
                compactness_vals.append(4 * np.pi * area / (perimeter ** 2))

            hull = p.convex_hull
            if hull.area > 0:
                convexity_vals.append(area / hull.area)

            pts = np.array(coords, dtype=np.float32)
            rect = cv2.minAreaRect(pts)
            rect_area = rect[1][0] * rect[1][1]
            if rect_area > 0:
                rectangularity_vals.append(area / rect_area)
        except Exception:
            pass

    return {
        "compactness_median": float(np.median(compactness_vals)) if compactness_vals else 0.0,
        "convexity_median": float(np.median(convexity_vals)) if convexity_vals else 0.0,
        "rectangularity_median": float(np.median(rectangularity_vals)) if rectangularity_vals else 0.0,
        "n_polygons": len(compactness_vals),
    }


def fetch_gt_from_supabase(map_id: str) -> list[list[list[float]]]:
    """Fetch verified/submitted footprint_submissions as ground truth."""
    import requests

    url = os.environ["PUBLIC_SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("PUBLIC_SUPABASE_ANON_KEY", "")
    r = requests.get(
        f"{url}/rest/v1/footprint_submissions",
        params={
            "map_id": f"eq.{map_id}",
            "status": "in.(submitted,consensus,verified)",
            "select": "coords",
        },
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    r.raise_for_status()
    return [row["coords"] for row in r.json() if row.get("coords")]


def main():
    p = argparse.ArgumentParser(description="Evaluate MapSAM2 predictions")
    p.add_argument("--predictions", required=True, help="Path to inference JSON output")
    p.add_argument("--ground-truth", help="Path to ground-truth JSON (coords list)")
    p.add_argument("--map-id", help="Fetch GT from Supabase footprint_submissions")
    p.add_argument("--iou-thresholds", default="0.5,0.75", help="IoU thresholds (comma-separated)")
    args = p.parse_args()

    pred_data = json.loads(Path(args.predictions).read_text())
    pred_coords = [poly["coords"] for poly in pred_data["polygons"]]

    if args.ground_truth:
        gt_data = json.loads(Path(args.ground_truth).read_text())
        gt_coords = gt_data if isinstance(gt_data, list) else gt_data.get("polygons", gt_data.get("coords", []))
        if gt_coords and isinstance(gt_coords[0], dict):
            gt_coords = [g["coords"] for g in gt_coords]
    elif args.map_id:
        gt_coords = fetch_gt_from_supabase(args.map_id)
    else:
        print("ERROR: provide --ground-truth or --map-id")
        sys.exit(1)

    print(f"Predictions: {len(pred_coords)} polygons")
    print(f"Ground truth: {len(gt_coords)} polygons")
    print()

    thresholds = [float(t) for t in args.iou_thresholds.split(",")]

    print("=== Polygon-Level Metrics ===")
    print(f"{'IoU Thresh':>12}  {'Prec':>8}  {'Recall':>8}  {'F1':>8}  {'Mean IoU':>10}")
    for thresh in thresholds:
        m = polygon_f1(pred_coords, gt_coords, thresh)
        print(f"{thresh:>12.2f}  {m.precision:>8.3f}  {m.recall:>8.3f}  {m.f1:>8.3f}  {m.mean_iou:>10.3f}")

    print()
    print("=== Benchmarks (SODUCO Chen 2024) ===")
    m50 = polygon_f1(pred_coords, gt_coords, 0.5)
    print(f"  VMA F1 @ 0.5:    {m50.f1:.3f}")
    print(f"  SODUCO best COCO PQ: 51.1%  (Chen et al. 2024; this repo reports mean IoU, not PQ -- not comparable, see docs/field-comparison.md \u00a70)")
    print(f"  Morlighem floor:  0.639  (degraded)")
    print(f"  Morlighem ceil:   0.929  (clean)")

    print()
    print("=== Geometric Quality ===")
    geo = geometric_quality(pred_coords)
    print(f"  Polygons evaluated: {geo['n_polygons']}")
    print(f"  Compactness (median):    {geo['compactness_median']:.3f}")
    print(f"  Convexity (median):      {geo['convexity_median']:.3f}")
    print(f"  Rectangularity (median): {geo['rectangularity_median']:.3f}")
    print(f"  Literature target rect:  0.75–0.82 (Morlighem post-regularization)")


if __name__ == "__main__":
    main()
