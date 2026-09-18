#!/usr/bin/env python3
"""Score segmentation runs against a sheet's hand-traced footprints, by type.

The segmentation counterpart to `eval.py`, and the reason it is split by
`feature_type` rather than pooled: the 1882 sheet's 46 traces are
`land_plot 24 · building 17 · road 3 · waterway 2`, and a pooled mean over
those mixes three incomparable things. A box or block prediction scores ~0
against a road centreline by construction, and a block-sized prediction is
capped against a building-sized truth however good the segmenter is. Pooling
is what first reported a block prior at 0.194 when its land_plot figure was
0.249.

Every run file is `{"polygons": [{"coords": [[x, y], ...]}, ...]}` in the
sheet's own source pixels — what `inference_tiles_as_video.py` and
`seg_gemini.py` both write.

    python work/ocr/scripts/seg_eval.py run_a.json run_b.json
    python work/ocr/scripts/seg_eval.py --map-id <uuid> --types land_plot run.json

`cover` is the median share of a ground-truth polygon's area caught by the
union of all predictions. It answers a different question from IoU and the two
move apart: a prior that returns fewer, fatter blocks can raise median IoU
while covering far less of each plot, which is exactly what the 4 m → 8 m
buffer change did.

**`cover` is not normalised by prediction count and is not comparable between
runs of very different size.** Enough predictions cover a sheet whatever they
are: 950 polygons reaching 0.97 and 100 reaching 0.78 is not a 19-point gap in
quality. The report prints a warning when the counts differ by more than 3x.
Compare cover between runs of comparable `n`, or read it only as "did this run
find the ink at all".

Self-check (no network): python work/ocr/scripts/seg_eval.py --self-check
"""

from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
from pathlib import Path

MAP_1882 = "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b"


def iou(a, b) -> float:
    try:
        inter = a.intersection(b).area
        if inter <= 0:
            return 0.0
        return inter / (a.area + b.area - inter)
    except Exception:
        # A self-intersecting ring survives make_valid as a GeometryCollection
        # that shapely will refuse to intersect. One bad prediction is not a
        # reason to lose the run's score.
        return 0.0


def load_gt(map_id: str) -> list[tuple[str, object]]:
    """(feature_type, geometry) for every usable hand trace on a sheet.

    **`source=volunteer` is the whole point of this function.**
    `footprint_submissions` holds predictions as well as traces — a `seg` run
    writes its output back with `source='sam-auto'`, into the same table this
    reads. Without the filter the table is not a ground truth, it is a mixture,
    and a model scored against it is partly scored against itself.

    That is not hypothetical: on the 1882 sheet, run `seg-20260916T1632` added
    72 `sam-auto` rows typed `building`, so this function returned 118 rows
    where the sheet has 46 traces, and every `building` number measured between
    2026-09-16 and this fix was 81% scored against model output. Worse, those
    72 are OCR label boxes — median IoU 0.83 to their own prompt box from
    `ocr_extractions` — so they are not buildings at all.
    """
    import requests
    from shapely.geometry import Polygon
    from shapely.validation import make_valid

    url = os.environ["PUBLIC_SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    rows = requests.get(
        f"{url}/rest/v1/footprint_submissions",
        params={
            "select": "pixel_polygon,feature_type",
            "map_id": f"eq.{map_id}",
            # ponytail: source is the trustworthy axis, status is not — a trace
            # sits at 'submitted' until someone reviews it. Add `status` here
            # only if volunteer tracing ever needs a quality gate of its own.
            "source": "eq.volunteer",
        },
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30,
    ).json()
    out = []
    for r in rows:
        poly = r.get("pixel_polygon")
        if poly and len(poly) >= 3:
            out.append((r.get("feature_type") or "unknown", make_valid(Polygon(poly))))
    return out


def called_area(path: str):
    """Union of the crops a run actually sent to the model, if it recorded them.

    Scoring a windowed run against a whole sheet's ground truth measures how
    much of the sheet the window covered, not how well the model did. 40 block
    crops on the 1882 sheet contain 12 of its 24 hand-traced plots, and mean
    IoU over all 24 is therefore about half of what the run earned.
    """
    from shapely.geometry import box
    from shapely.ops import unary_union

    doc = json.load(open(path, encoding="utf-8"))
    crops = {tuple(p["crop"]) for p in (doc.get("polygons") or []) if p.get("crop")}
    if not crops:
        return None
    return unary_union([box(x, y, x + w, y + h) for x, y, w, h in crops])


def load_run(path: str) -> list:
    from shapely.geometry import Polygon
    from shapely.validation import make_valid

    doc = json.load(open(path, encoding="utf-8"))
    polys = []
    for p in doc.get("polygons") or []:
        coords = p.get("coords")
        if coords and len(coords) >= 3:
            g = make_valid(Polygon(coords))
            if not g.is_empty:
                polys.append(g)
    return polys


def score(gt: list, preds: list) -> dict:
    """Best IoU per ground-truth polygon, plus the union's coverage of it."""
    from shapely.ops import unary_union

    if not gt:
        return {"n_gt": 0}
    best = [max((iou(g, q) for q in preds), default=0.0) for g in gt]
    row = {
        "n_gt": len(gt),
        "at50": sum(b >= 0.5 for b in best),
        "at30": sum(b >= 0.3 for b in best),
        "mean": st.mean(best),
        "median": st.median(best),
    }
    if preds:
        union = unary_union(preds)
        row["cover"] = st.median([g.intersection(union).area / g.area for g in gt if g.area > 0])
    else:
        row["cover"] = 0.0
    return row


def _report(groups: dict[str, list], runs: dict[str, list]) -> None:
    for name, gt in groups.items():
        if not gt:
            continue
        print(f"\n== {name} (n={len(gt)})")
        print(f"{'run':30s}{'n':>7s}{'@.5':>5s}{'@.3':>5s}{'mean':>8s}{'med':>8s}{'cover':>7s}")
        for run_name, preds in runs.items():
            r = score(gt, preds)
            print(f"{run_name[:30]:30s}{len(preds):7d}{r['at50']:5d}{r['at30']:5d}"
                  f"{r['mean']:8.3f}{r['median']:8.3f}{r['cover']:7.2f}")
        counts = [len(p) for p in runs.values() if p]
        if counts and max(counts) > 3 * min(counts):
            print(f"  ! prediction counts range {min(counts)}-{max(counts)}: "
                  f"compare `cover` only between runs of similar n")


def run(args: argparse.Namespace) -> int:
    gt = load_gt(args.map_id)
    if not gt:
        print(f"No hand traces on {args.map_id}", file=sys.stderr)
        return 1

    kinds: dict[str, list] = {}
    for kind, geom in gt:
        kinds.setdefault(kind, []).append(geom)
    print("ground truth: " + " · ".join(f"{k} {len(v)}" for k, v in sorted(kinds.items())))

    runs = {Path(p).stem: load_run(p) for p in args.runs}

    if args.in_frame:
        area = called_area(args.in_frame)
        if area is None:
            print(f"{args.in_frame} records no crops; --in-frame needs a run that does",
                  file=sys.stderr)
            return 1
        before = len(gt)
        # Half inside is the test rather than "touches": a plot clipped by the
        # window edge was never wholly available to be found.
        gt = [(k, g) for k, g in gt if g.intersection(area).area > 0.5 * g.area]
        print(f"--in-frame {Path(args.in_frame).stem}: {len(gt)}/{before} traces "
              f"are at least half inside a called crop")
        kinds = {}
        for kind, geom in gt:
            kinds.setdefault(kind, []).append(geom)

    groups: dict[str, list] = {}
    wanted = args.types.split(",") if args.types else sorted(kinds)
    for k in wanted:
        groups[k] = kinds.get(k, [])
    # The areal group is the honest headline: everything a polygon predictor
    # can be scored on at all, with the linear features left out.
    areal = [g for k in ("land_plot", "building") for g in kinds.get(k, [])]
    if len(wanted) > 1 and areal:
        groups["areal (land_plot+building)"] = areal
    if args.pooled:
        groups["pooled — mixes granularities, do not quote"] = [g for _, g in gt]

    _report(groups, runs)
    return 0


def _self_check() -> None:
    from shapely.geometry import Polygon
    from shapely.validation import make_valid

    unit = make_valid(Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]))
    half = Polygon([(0, 0), (5, 0), (5, 10), (0, 10)])        # IoU 0.5 exactly
    far = Polygon([(100, 100), (110, 100), (110, 110), (100, 110)])

    assert abs(iou(unit, unit) - 1.0) < 1e-9
    assert abs(iou(unit, half) - 0.5) < 1e-9
    assert iou(unit, far) == 0.0

    # One GT, one perfect prediction and one irrelevant one: the best match is
    # what counts, so a wrong extra prediction must not lower the score. That
    # is the whole reason precision is absent from this report — the same
    # partial-ground-truth problem `eval.py` has.
    r = score([unit], [unit, far])
    assert r["at50"] == 1 and abs(r["mean"] - 1.0) < 1e-9, r
    assert abs(r["cover"] - 1.0) < 1e-9, r

    # Coverage and IoU separate: two halves of a plot, each scoring 0.5 IoU on
    # its own, together cover all of it. A run that shatters every plot reads
    # as mediocre on IoU and perfect on cover, and both facts are true.
    left = Polygon([(0, 0), (5, 0), (5, 10), (0, 10)])
    right = Polygon([(5, 0), (10, 0), (10, 10), (5, 10)])
    r2 = score([unit], [left, right])
    assert abs(r2["mean"] - 0.5) < 1e-9, r2
    assert abs(r2["cover"] - 1.0) < 1e-9, r2

    # No predictions at all is a zero, not a crash — an empty run file is the
    # normal outcome of a mode that failed, and it has to be scoreable.
    r3 = score([unit], [])
    assert r3["mean"] == 0.0 and r3["cover"] == 0.0, r3
    assert score([], [unit]) == {"n_gt": 0}

    # A self-intersecting bowtie is what a model actually returns when it goes
    # wrong. It must score 0 rather than take the run down with it.
    bowtie = make_valid(Polygon([(0, 0), (10, 10), (10, 0), (0, 10)]))
    assert 0.0 <= score([unit], [bowtie])["mean"] <= 1.0

    print("[ok] seg_eval self-check passed")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("runs", nargs="*", help="run JSON files")
    p.add_argument("--map-id", default=MAP_1882)
    p.add_argument("--types", help="comma-separated feature_types to report")
    p.add_argument("--in-frame", metavar="RUN.json",
                   help="score only the traces this run's crops actually covered")
    p.add_argument("--pooled", action="store_true",
                   help="also print the pooled row, for comparison with older numbers")
    p.add_argument("--self-check", action="store_true")
    args = p.parse_args()

    if args.self_check:
        _self_check()
        return 0
    if not args.runs:
        p.error("give at least one run JSON, or --self-check")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
