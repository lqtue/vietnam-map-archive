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
    python work/ocr/scripts/seg_eval.py --window x,y,w,h run.json

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
    `footprints` holds predictions as well as traces — a `seg` run
    writes its output back with `source='sam-auto'`, into the same table this
    reads. Without the filter the table is not a ground truth, it is a mixture,
    and a model scored against it is partly scored against itself.

    That is not hypothetical: on the 1882 sheet, run `seg-20260916T1632` added
    72 `sam-auto` rows typed `building`, so this function returned 118 rows
    where the sheet has 46 traces, and every `building` number measured between
    2026-09-16 and this fix was 81% scored against model output. Worse, those
    72 are OCR label boxes — median IoU 0.83 to their own prompt box from
    `ocr_labels` — so they are not buildings at all.
    """
    import requests
    from shapely.geometry import Polygon
    from shapely.validation import make_valid

    url = os.environ["PUBLIC_SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    rows = requests.get(
        f"{url}/rest/v1/footprints",
        params={
            "select": "pixel_polygon,feature_type",
            "map_id": f"eq.{map_id}",
            # ponytail: source is the trustworthy axis, review_status is not — a
            # trace sits at 'submitted' until someone reviews it. Add
            # `review_status` here only if volunteer tracing ever needs a
            # quality gate of its own.
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


# The categories that name something a polygon predictor should have found,
# and the one that names something it should have left alone. A street is the
# gap between blocks by construction, so a block covering a street label is a
# merge failure — which is the only signal in this file that points at a
# *prediction* rather than at a trace.
AREAL_LABELS = ("institution", "place", "building")
NEGATIVE_LABELS = ("street",)


def load_labels(map_id: str, ocr_run_id: str | None = None) -> tuple[list[dict], dict[str, int]]:
    """(text, category, x, y) for every placed OCR label on a sheet.

    The 1882 sheet has 499 of these against 46 hand traces, and they cost
    nothing: OCR has already run on every sheet that reaches this pass. They
    cannot score a polygon's *shape* — that is what `load_gt` is for — but they
    answer the question that keeps coming back, which is whether the pass
    emitted anything at all where the sheet says there is something.
    """
    import requests

    url = os.environ["PUBLIC_SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    # PostgREST's default maximum is 1,000 rows. A dense sheet can exceed it,
    # so one response is not a measurement of all OCR labels on the sheet.
    params = {
        "select": "text,category,global_x,global_y,global_w,global_h,run_id",
        "map_id": f"eq.{map_id}",
    }
    if ocr_run_id:
        params["run_id"] = f"eq.{ocr_run_id}"
    page_size = 1000
    def fetch_page(start: int) -> list[dict]:
        response = requests.get(
            f"{url}/rest/v1/ocr_labels",
            params=params,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Range-Unit": "items",
                "Range": f"{start}-{start + page_size - 1}",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    rows = paged_rows(fetch_page, page_size)
    provenance: dict[str, int] = {}
    labels = []
    for r in rows:
        run_id = r.get("run_id") or "(no run_id)"
        provenance[run_id] = provenance.get(run_id, 0) + 1
        if r.get("global_x") is not None:
            labels.append({"text": r.get("text") or "", "category": r.get("category") or "?",
                           "x": r["global_x"] + (r["global_w"] or 0) / 2.0,
                           "y": r["global_y"] + (r["global_h"] or 0) / 2.0})
    return labels, provenance


def paged_rows(fetch_page, page_size: int = 1000) -> list[dict]:
    """Read contiguous PostgREST-sized pages until the first short page."""
    rows = []
    start = 0
    while True:
        page = fetch_page(start)
        rows.extend(page)
        if len(page) < page_size:
            return rows
        start += page_size


def label_cover(polys: list, labels: list[dict], probe: float = 120.0) -> list[float]:
    """Covered share of a `probe`-px box around each label, 0 to 1.

    A point-in-polygon test is not enough and the Arsenal de la Marine is why:
    its label sits on the *edge* of the block above the boulevard, so the point
    test calls it covered while the dockyard apron it names has nothing on it.
    The box reads 0.74 there and 1.00 on a block that really is covered.
    """
    from shapely.geometry import Point
    from shapely.strtree import STRtree

    if not polys:
        return [0.0] * len(labels)
    tree = STRtree(polys)
    half = probe / 2.0
    offs = [(half * i / 5.0, half * j / 5.0) for i in range(-5, 6) for j in range(-5, 6)]
    out = []
    for lab in labels:
        n = 0
        for dx, dy in offs:
            p = Point(lab["x"] + dx, lab["y"] + dy)
            if any(polys[i].contains(p) for i in tree.query(p)):
                n += 1
        out.append(n / len(offs))
    return out


def report_labels(map_id: str, runs: dict[str, list], found: float = 0.5,
                  ocr_run_id: str | None = None) -> None:
    """Recall over the named areal features, and leak over the street names."""
    labels, provenance = load_labels(map_id, ocr_run_id)
    if not labels:
        print(f"No placed OCR labels on {map_id}", file=sys.stderr)
        return
    counts: dict[str, int] = {}
    for lab in labels:
        counts[lab["category"]] = counts.get(lab["category"], 0) + 1
    print("named labels: " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print("OCR label runs: " + " · ".join(
        f"{run_id} {n}" for run_id, n in sorted(provenance.items())
    ))
    areal = [l for l in labels if l["category"] in AREAL_LABELS]
    street = [l for l in labels if l["category"] in NEGATIVE_LABELS]
    print(f"\n== named-label coverage (areal {len(areal)} · street {len(street)}); "
          f"areal at {found:.0%} of a 120 px box, street on the centre pixel")
    print(f"{'run':<28}{'n':>6}{'areal':>8}{'recall':>8}{'street':>8}{'leak':>7}")
    missing: dict[str, list] = {}
    for name, polys in runs.items():
        ac = label_cover(polys, areal)
        # The street test is the *centre pixel*, not a box: a 120 px box around
        # a street name overlaps the blocks on either side of the street by
        # construction, so the box reads 0.60 where the point reads 0.39 and
        # the difference is geometry, not error. The two categories are asking
        # opposite questions and get the probe each one needs.
        sc = label_cover(polys, street, probe=0.0)
        a = sum(1 for v in ac if v >= found)
        t = sum(1 for v in sc if v >= found)
        print(f"{name:<28}{len(polys):>6}{a:>8}{a / len(areal):>8.2f}"
              f"{t:>8}{t / len(street):>7.2f}")
        missing[name] = sorted(((v, l) for v, l in zip(ac, areal) if v < found),
                               key=lambda kv: kv[0])
    print("\n  recall is the honest headline: a named institution, place or "
          "building with nothing under it is a miss whatever the IoU tables say.")
    print("  leak is a *direction*, not a precision figure — map typography "
          "legitimately sets a street name across a block, so compare it\n"
          "  between runs rather than reading it as a rate.")
    if len(runs) == 1:
        name, rows = next(iter(missing.items()))
        print(f"\n  {len(rows)} areal labels under {found:.0%} in {name}, emptiest first."
              f"\n  A worklist, not a defect count: `place` also tags the villages out on "
              f"open country\n  and the river's own lettering, and neither is a parcel "
              f"anyone failed to find.")
        for v, lab in rows[:20]:
            print(f"    {v:4.0%}  {lab['category']:<12} {lab['text'][:44]:<44} "
                  f"({lab['x']:.0f}, {lab['y']:.0f})")
        if len(rows) > 20:
            print(f"    ... and {len(rows) - 20} more")
        print("\n  colour_blocks.py --explain '<text>' says which filter dropped each.")


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


def load_run_records(path: str) -> list[tuple[object, str]]:
    """Usable run polygons with their optional feature type for window FPs."""
    from shapely.geometry import Polygon
    from shapely.validation import make_valid

    doc = json.load(open(path, encoding="utf-8"))
    records = []
    for p in doc.get("polygons") or []:
        coords = p.get("coords")
        if coords and len(coords) >= 3:
            geom = make_valid(Polygon(coords))
            if not geom.is_empty:
                records.append((geom, p.get("feature_type") or "unknown"))
    return records


def parse_window(value: str) -> tuple[float, float, float, float]:
    """Parse a positive source-pixel x,y,w,h window."""
    try:
        x, y, width, height = (float(v) for v in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--window needs x,y,w,h") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("--window width and height must be positive")
    return x, y, width, height


def window_score(gt: list[tuple[str, object]], records: list[tuple[object, str]],
                 window: tuple[float, float, float, float], threshold: float) -> dict:
    """Precision/recall in an exhaustively traced source-pixel rectangle.

    Both sides are clipped before IoU. An edge-spanning parcel is still one
    real object in the window, and clipping both shapes removes only the area
    neither side was asked to account for. Including whole shapes would lower
    an otherwise matching edge prediction merely for its unobserved outside
    portion; centroid ownership would discard it altogether. Boundary-only
    touches have zero scoreable area and are excluded after clipping.
    """
    from shapely.geometry import box

    x, y, width, height = window
    area = box(x, y, x + width, y + height)
    clipped_gt = [(kind, geom.intersection(area)) for kind, geom in gt if geom.intersects(area)]
    clipped_gt = [(kind, geom) for kind, geom in clipped_gt if not geom.is_empty and geom.area > 0]
    clipped_preds = [(geom.intersection(area), kind) for geom, kind in records if geom.intersects(area)]
    clipped_preds = [(geom, kind) for geom, kind in clipped_preds if not geom.is_empty and geom.area > 0]
    gt_best = [max((iou(geom, pred) for pred, _ in clipped_preds), default=0.0)
               for _, geom in clipped_gt]
    pred_best = [max((iou(pred, geom) for _, geom in clipped_gt), default=0.0)
                 for pred, _ in clipped_preds]
    matched_gt = sum(value >= threshold for value in gt_best)
    matched_preds = sum(value >= threshold for value in pred_best)
    recall = matched_gt / len(clipped_gt) if clipped_gt else 0.0
    precision = matched_preds / len(clipped_preds) if clipped_preds else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    false_positives = sorted(
        ((geom.area, kind, best) for (geom, kind), best in zip(clipped_preds, pred_best)
         if best < threshold), reverse=True
    )
    return {
        "n_gt": len(clipped_gt), "n_pred": len(clipped_preds), "matched_gt": matched_gt,
        "matched_pred": matched_preds, "precision": precision, "recall": recall, "f1": f1,
        "false_positives": false_positives,
    }


def report_window(gt: list[tuple[str, object]], paths: list[str],
                  window: tuple[float, float, float, float], threshold: float) -> None:
    """Print precision, recall and the largest unmatched predictions per run."""
    x, y, width, height = window
    print(f"\n== exhaustively traced window ({x:g},{y:g},{width:g},{height:g}); IoU ≥ {threshold:.2f}")
    print(f"{'run':30s}{'n_gt':>7s}{'n_pred':>8s}{'precision':>11s}{'recall':>8s}{'F1':>7s}")
    results = []
    for path in paths:
        name = Path(path).stem
        result = window_score(gt, load_run_records(path), window, threshold)
        results.append((name, result))
        print(f"{name[:30]:30s}{result['n_gt']:7d}{result['n_pred']:8d}"
              f"{result['precision']:11.2f}{result['recall']:8.2f}{result['f1']:7.2f}")
    print("  Precision is meaningful only because every parcel in this window is traced; "
          "it does not describe untraced parts of the sheet.")
    for name, result in results:
        rows = result["false_positives"]
        print(f"\n  {len(rows)} false positives in {name}, largest clipped area first.")
        for area, kind, best in rows[:20]:
            print(f"    {area:10.0f} px²  {kind:<14} best IoU {best:.3f}")
        if len(rows) > 20:
            print(f"    ... and {len(rows) - 20} more")


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
    if args.labels:
        report_labels(args.map_id, {Path(p).stem: load_run(p) for p in args.runs},
                      ocr_run_id=args.ocr_run_id)
        return 0
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
    if args.window:
        report_window(gt, args.runs, args.window, args.iou)
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

    # Window precision clips both sides: the edge-spanning perfect match stays
    # perfect, while the unrelated in-window square is the one false positive.
    edge_gt = Polygon([(8, 0), (18, 0), (18, 10), (8, 10)])
    extra = Polygon([(1, 1), (3, 1), (3, 3), (1, 3)])
    window = window_score(
        [("land_plot", edge_gt)], [(edge_gt, "plot"), (extra, "furniture")],
        (0, 0, 10, 10), 0.3,
    )
    assert window["n_gt"] == 1 and window["n_pred"] == 2, window
    assert window["precision"] == 0.5 and window["recall"] == 1.0, window
    assert window["f1"] == 2 / 3 and window["false_positives"][0][1] == "furniture", window

    # A dense OCR sheet cannot silently lose its second PostgREST page.
    starts = []
    pages = [[{}] * 1000, [{}, {}]]
    def fake_page(start: int) -> list[dict]:
        starts.append(start)
        return pages.pop(0)
    assert len(paged_rows(fake_page)) == 1002 and starts == [0, 1000]

    # The label probe: a box, not a point, because a label on a block's edge is
    # the failure it exists to catch (the Arsenal reads 0.74 that way).
    lab = [{"text": "X", "category": "institution", "x": 50.0, "y": 50.0}]
    block = make_valid(Polygon([(0, 0), (100, 0), (100, 100), (0, 100)]))
    edge = make_valid(Polygon([(50, 0), (100, 0), (100, 100), (50, 100)]))
    assert label_cover([block], lab, probe=40.0)[0] == 1.0
    assert label_cover([far], lab, probe=40.0)[0] == 0.0
    half = label_cover([edge], lab, probe=40.0)[0]
    assert 0.3 < half < 0.7, f"a label on a block's edge must read as partial: {half}"

    print("[ok] seg_eval self-check passed")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("runs", nargs="*", help="run JSON files")
    p.add_argument("--map-id", default=MAP_1882)
    p.add_argument("--types", help="comma-separated feature_types to report")
    p.add_argument("--in-frame", metavar="RUN.json",
                   help="score only the traces this run's crops actually covered")
    p.add_argument("--labels", action="store_true",
                   help="score against the sheet's own OCR labels instead of the hand "
                        "traces: recall over the named areal features, and leak over "
                        "the street names. 499 labels against 46 traces on the 1882 "
                        "sheet, and they cost nothing — OCR has already run")
    p.add_argument("--ocr-run-id",
                   help="OCR extraction run to use with --labels; without it, all runs are "
                        "pooled and their row counts are printed")
    p.add_argument("--window", type=parse_window, metavar="x,y,w,h",
                   help="exhaustively traced source-pixel rectangle for precision/recall")
    p.add_argument("--iou", type=float, default=0.3,
                   help="IoU match threshold for --window (default: 0.3)")
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
