"""Eval CLI — score an OCR run or a seg run against held-out ground truth.

Ground truth comes from the HITL review that already exists:
  OCR  — extractions a human validated (review_status='validated'); text is the
         corrected text_corrected when present.
  Seg  — footprints a human verified (review_status in verified/consensus).

Predictions are a machine run to score against that truth:
  OCR  — one run_id's rows (default: all non-validated rows for the map).
  Seg  — footprints with --pred-status (default 'submitted', i.e. sam-auto).

Usage:
    python eval.py ocr --map-id <uuid> --run-id <run>      # run vs validated
    python eval.py seg --map-id <uuid>                     # submitted vs verified
    python eval.py ocr --map-id <uuid> --pred-run-dir ../outputs/<map>/runs/<run>
    python eval.py ocr --pred-file p.json --gt-file g.json # offline, no DB
    python eval.py index-agreement --map-id <uuid> [--save]  # body pass vs printed index
    # JSON file shape: OCR [{"bbox":[x,y,w,h],"text":"..."}], seg [{"polygon":[[x,y],...]}]

Reads only. Prints a metrics report; exits 0 always (it's a measurement, not a gate).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval_metrics import score_index_agreement, score_ocr, score_seg

# What `ocr street-index` stamps on the rows it writes.
INDEX_PROMPT = "street-index-v1"


def _rest_get(path: str, params: dict[str, str]) -> list[dict]:
    """GET rows from PostgREST using the OCR pipeline's service creds."""
    import requests
    try:
        from supabase_client import _load_config, _headers
    except (ImportError, ValueError):
        from .supabase_client import _load_config, _headers  # type: ignore

    url, key = _load_config()
    query = "&".join(f"{k}={v}" for k, v in params.items())
    # Paged, because PostgREST caps a response at 1000 rows and says so nowhere
    # in the body: an unpaged read of a busy sheet returns exactly 1000 and
    # scores a partial run as if it were the whole thing. The 1959 sheet passed
    # that mark in September 2026.
    page, offset, out = 1000, 0, []
    while True:
        resp = requests.get(
            f"{url}/rest/v1/{path}?{query}",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Range-Unit": "items", "Range": f"{offset}-{offset + page - 1}"},
            timeout=30,
        )
        if not resp.ok:
            raise requests.HTTPError(f"{resp.status_code}: {resp.text[:300]}", response=resp)
        rows = resp.json()
        out += rows
        if len(rows) < page:
            return out
        offset += page


def _ocr_rows_to_items(rows: list[dict], use_validated_text: bool) -> list[dict]:
    """Keep rows with a full global bbox; box = (x,y,w,h), text = best available."""
    items = []
    for r in rows:
        gx, gy, gw, gh = r.get("global_x"), r.get("global_y"), r.get("global_w"), r.get("global_h")
        if None in (gx, gy, gw, gh):
            continue
        text = (r.get("text_corrected") or r.get("text")) if use_validated_text else r.get("text")
        cat = (r.get("category_corrected") or r.get("category")) if use_validated_text else r.get("category")
        items.append({"bbox": (gx, gy, gw, gh), "text": text or "", "category": cat,
                      "rotation_deg": r.get("rotation_deg")})
    return items


def _run_dir_to_items(run_dir: str) -> list[dict]:
    """Predictions read straight out of a run directory's `all_extractions.json`.

    The DB should not be the only place a run can be scored from. Scoring a candidate
    prompt by writing its rows into the shared `ocr_labels` table pollutes the
    corpus the review UI reads and then has to be dedup'd back out again — a real cost
    for a measurement that throws its predictions away. `batch` already writes
    `global_bbox` on every extraction, which is all `score_ocr` needs.
    """
    path = Path(run_dir)
    if path.is_dir():
        path = path / "all_extractions.json"
    data = json.loads(path.read_text())
    rows = data if isinstance(data, list) else data.get("extractions", [])
    items = []
    for r in rows:
        gb = r.get("global_bbox")
        if gb and len(gb) == 4:
            items.append({"bbox": tuple(gb), "text": r.get("text") or "",
                          "category": r.get("category"), "rotation_deg": r.get("rotation_deg")})
    return items


def _cmd_ocr(args: argparse.Namespace) -> None:
    if args.pred_file and args.gt_file:
        preds = json.loads(open(args.pred_file).read())
        gts = json.loads(open(args.gt_file).read())
    else:
        if not args.map_id:
            raise SystemExit("Provide --map-id (or --pred-file + --gt-file)")
        base = {"map_id": f"eq.{args.map_id}", "select": "*"}
        gt_rows = _rest_get("ocr_labels", {**base, "review_status": "eq.validated"})
        gts = _ocr_rows_to_items(gt_rows, use_validated_text=True)
        if args.pred_run_dir:
            preds = _run_dir_to_items(args.pred_run_dir)
        else:
            pred_params = {**base}
            if args.run_id:
                pred_params["run_id"] = f"eq.{args.run_id}"
            else:
                pred_params["review_status"] = "neq.validated"
            pred_rows = _rest_get("ocr_labels", pred_params)
            preds = _ocr_rows_to_items(pred_rows, use_validated_text=False)

    if not gts:
        print("No validated OCR ground truth for this map — nothing to score against.")
        return
    report = score_ocr(preds, gts, iou_thresh=args.iou)
    _print("OCR", report, args.iou)


def _seg_rows_to_items(rows: list[dict]) -> list[dict]:
    items = []
    for r in rows:
        poly = r.get("pixel_polygon")
        if poly and len(poly) >= 3:
            items.append({"polygon": poly})
    return items


def _cmd_seg(args: argparse.Namespace) -> None:
    if args.pred_file and args.gt_file:
        preds = json.loads(open(args.pred_file).read())
        gts = json.loads(open(args.gt_file).read())
    else:
        if not args.map_id:
            raise SystemExit("Provide --map-id (or --pred-file + --gt-file)")
        base = {"map_id": f"eq.{args.map_id}", "select": "pixel_polygon,review_status,feature_type"}
        gt_statuses = args.gt_status.split(",")
        gt_rows = _rest_get("footprints",
                            {**base, "review_status": f"in.({','.join(gt_statuses)})"})
        pred_rows = _rest_get("footprints",
                              {**base, "review_status": f"eq.{args.pred_status}"})
        gts = _seg_rows_to_items(gt_rows)
        preds = _seg_rows_to_items(pred_rows)

    if not gts:
        print("No verified footprint ground truth for this map — nothing to score against.")
        return
    report = score_seg(preds, gts, iou_thresh=args.iou)
    _print("SEG", report, args.iou)


def _print(kind: str, r: dict, iou: float) -> None:
    print(f"\n== {kind} eval @ IoU≥{iou} ==")
    print(f"  predictions: {r['n_pred']}   ground truth: {r['n_gt']}   matched: {r['tp']}")
    print(f"  precision {r['precision']}   recall {r['recall']}   f1 {r['f1']}   mean_iou {r['mean_iou']}")
    n_unmatched = r["n_pred"] - r["tp"]
    if n_unmatched:
        # Worse than blind: on a partial GT, precision prices new coverage as
        # harm. The 1882 GT is 85 street and institution names, so the margin
        # content the grid-offset fix recovered — `REGISTRE DU CADASTRE`, the
        # Boilloux imprint, 20 cadastral street numbers — enters here as false
        # positives. Read precision as agreement with the GT's *scope*, and
        # judge coverage by eye or against a GT that includes it.
        print(f"  ({n_unmatched} predictions matched no GT box. On a GT that covers "
              f"only part of the sheet's content, that is scope, not error — "
              f"precision falls when a pass reads more than the GT knows about.)")
    if "char_acc" in r:
        print(f"  char_acc {r['char_acc']}")
    if r.get("category_acc") is not None:
        print(f"  category_acc {r['category_acc']} (over {r['n_category_scored']} matched pairs with a GT category)"
              + (f"   confusions: {r['category_confusions']}" if r.get("category_confusions") else ""))
    if "text_recall_03" in r:
        print(f"  text_recall@0.3 {r['text_recall_03']} ({r['n_text_found_03']}/{r['n_gt']} GT read "
              f"correctly by some prediction overlapping at IoU>=0.3 — detection, box convention aside)")
    if "diacritic_rate" in r:
        dr = r["diacritic_recall"]
        print(f"  diacritic_rate {r['diacritic_rate']} (of all predictions)   "
              f"diacritic_recall {dr if dr is not None else 'n/a'} "
              f"(over {r['n_gt_diacritic']} matched GT labels that carry a mark)")
    if r.get("rotation_mae") is not None:
        print(f"  rotation_mae {r['rotation_mae']}\u00b0 (over {r['n_rotation_scored']} matched pairs; "
              f"{r['n_rotation_off_15']} disagree by 15\u00b0 or more \u2014 agreement with GT's own "
              f"unvalidated angle, not accuracy)")


def _cmd_index_agreement(args: argparse.Namespace) -> None:
    """Score a body OCR pass against the sheet's own printed street index."""
    from labels import name_key
    try:
        from supabase_client import fetch_triage_grid
    except (ImportError, ValueError):
        from .supabase_client import fetch_triage_grid  # type: ignore

    if not args.map_id:
        raise SystemExit("Provide --map-id")
    grid = fetch_triage_grid(args.map_id)
    if not grid:
        raise SystemExit(
            f"map {args.map_id} has no triage.grid — the slack is measured in cells, "
            f"so there is nothing to measure it in. Run `ocr grid` first."
        )
    cell = (grid["bbox"][2] / len(grid["columns"]), grid["bbox"][3] / len(grid["rows"]))

    base = {"map_id": f"eq.{args.map_id}", "select": "*", "review_status": "neq.rejected"}
    rows = _rest_get("ocr_labels", base)
    gt_rows = [r for r in rows if r.get("prompt") == INDEX_PROMPT]
    if not gt_rows:
        raise SystemExit(
            f"no `{INDEX_PROMPT}` rows on this map — read its street directory first:\n"
            f"  ocr.py street-index --map-id {args.map_id} --regions x,y,w,h[;...] --db"
        )
    def items(rs: list[dict]) -> list[dict]:
        out = []
        for r in rs:
            gx, gy, gw, gh = r.get("global_x"), r.get("global_y"), r.get("global_w"), r.get("global_h")
            if None in (gx, gy, gw, gh):
                continue
            out.append({"name": name_key(r.get("text_corrected") or r.get("text") or ""),
                        "bbox": (gx, gy, gw, gh)})
        return out

    if args.pred_run_dir:
        # Same reason `ocr` takes one: a candidate run should not have to write
        # into the shared table to be scored, and the printed index is in the DB
        # regardless of where the predictions came from.
        preds = [p for p in _run_dir_to_items(args.pred_run_dir)
                 if p.get("category") in ("street", "hydrology")]
        preds = [{"name": name_key(p["text"]), "bbox": p["bbox"]} for p in preds]
    else:
        preds = items([r for r in rows
                       if r.get("prompt") != INDEX_PROMPT
                       and r.get("category") in ("street", "hydrology")
                       and (not args.run_id or r.get("run_id") == args.run_id)])

    report = score_index_agreement(preds, items(gt_rows), cell,
                                   slack_cells=args.slack_cells)
    _print_index_agreement(args.map_id, args.pred_run_dir or args.run_id, report, cell)

    path = Path(args.baseline_file)
    saved = json.loads(path.read_text()) if path.exists() else {}
    prev = saved.get(args.map_id)
    if prev:
        print("\n  vs baseline "
              f"({prev.get('recorded')}, run {prev.get('run_id') or 'all'}):")
        for k in ("agreement", "name_recall", "n_unlisted"):
            d = report[k] - prev.get(k, 0)
            if isinstance(report[k], int):
                print(f"    {k:14} {prev.get(k, 0)} → {report[k]}  "
                      f"{'+' if d >= 0 else ''}{d}")
            else:
                print(f"    {k:14} {prev.get(k, 0):.4f} → {report[k]:.4f}  "
                      f"{'+' if d >= 0 else ''}{d:.4f}")
    elif not args.save:
        print("\n  no baseline recorded for this map — add --save to set one.")

    if args.save and args.pred_run_dir:
        raise SystemExit("--save records a baseline for the map's own rows; drop --pred-run-dir")
    if args.save:
        saved[args.map_id] = {
            "recorded": _today(), "run_id": args.run_id,
            "slack_cells": args.slack_cells,
            **{k: report[k] for k in ("agreement", "name_recall", "n_directory_names",
                                      "n_matched", "n_inside", "n_outside",
                                      "n_names_found", "n_unlisted")},
        }
        path.write_text(json.dumps(saved, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"\n  baseline saved → {path}")


def _today() -> str:
    from datetime import date
    return date.today().isoformat()


def _print_index_agreement(map_id: str, run_id: str | None, r: dict,
                           cell: tuple[float, float]) -> None:
    print(f"\nIndex agreement — map {map_id}, run {run_id or '(all body runs)'}")
    print(f"  directory: {r['n_directory_rows']} rows, {r['n_directory_names']} distinct names")
    print(f"  body labels: {r['n_pred']} (street + hydrology)")
    print(f"  cell {cell[0]:.0f}x{cell[1]:.0f} px, slack {r['slack_cells']} cell(s)")
    print(f"  name_recall {r['name_recall']:.4f} "
          f"({r['n_names_found']}/{r['n_directory_names']} printed names read on the map)")
    print(f"  agreement   {r['agreement']:.4f} "
          f"({r['n_inside']}/{r['n_matched']} matched labels inside their stated range)")
    print(f"  disagree {r['n_outside']}")
    # Coverage, reported apart from name_recall on purpose. Twice in one day
    # (2026-09-10) a change that genuinely widened what a pass read scored as
    # worth nothing: the 1882 grid-offset fix recovered margin content a GT of
    # 85 street names cannot contain, and the 1968 south band found 20 hamlet
    # and canal names a printed street directory never lists. Both are real
    # content the gate is structurally blind to, and both landed here, in the
    # count of labels with no directory row. A rise in this number beside a flat
    # name_recall is that case, not noise.
    print(f"  coverage    {r['n_unlisted']} labels read that the directory does not list "
          f"(hamlets, canals, margin text — real content this gate cannot score)")
    if r["misses"]:
        print("  labels outside their stated range:")
        for m in r["misses"][:20]:
            print(f"    {m['name']:28} at {m['at']}  stated {m['stated']}")
        if len(r["misses"]) > 20:
            print(f"    … and {len(r['misses']) - 20} more")


def main() -> None:
    p = argparse.ArgumentParser(description="Score OCR / seg runs against held-out ground truth.")
    sub = p.add_subparsers(dest="cmd", required=True)

    po = sub.add_parser("ocr", help="Score an OCR run vs validated extractions")
    po.add_argument("--map-id")
    po.add_argument("--run-id", help="Prediction run_id in the DB (default: all non-validated rows)")
    po.add_argument("--pred-run-dir",
                    help="Score a local run directory instead of DB rows (its "
                         "all_extractions.json). Ground truth still comes from the DB. "
                         "Use this for a candidate prompt — it needs no --db run.")
    po.add_argument("--iou", type=float, default=0.5)
    po.add_argument("--pred-file")
    po.add_argument("--gt-file")
    po.set_defaults(func=_cmd_ocr)

    ps = sub.add_parser("seg", help="Score seg footprints vs verified footprints")
    ps.add_argument("--map-id")
    ps.add_argument("--pred-status", default="submitted", help="Prediction status (default submitted)")
    ps.add_argument("--gt-status", default="verified,consensus", help="Comma GT statuses")
    ps.add_argument("--iou", type=float, default=0.5)
    ps.add_argument("--pred-file")
    ps.add_argument("--gt-file")
    ps.set_defaults(func=_cmd_seg)

    pi = sub.add_parser("index-agreement",
                        help="Score a body OCR pass against the sheet's own printed street "
                             "index — ground truth that costs no human labelling")
    pi.add_argument("--map-id")
    pi.add_argument("--run-id", help="Body run to score (default: every non-index run on the map)")
    pi.add_argument("--pred-run-dir",
                    help="Score a local run directory's all_extractions.json instead of DB "
                         "rows. Ground truth still comes from the DB. Use it for a candidate "
                         "prompt, or to score a run that has been superseded.")
    pi.add_argument("--slack-cells", type=float, default=1.0,
                    help="Inflate the stated cell range by this many cells on each side. "
                         "A street is labelled somewhere along its length, not between its "
                         "endpoints, and the printed cell is itself approximate (default 1.0)")
    pi.add_argument("--baseline-file",
                    default=str(Path(__file__).resolve().parents[1] / "index-baselines.json"),
                    help="Per-sheet baselines to compare against (default work/ocr/index-baselines.json)")
    pi.add_argument("--save", action="store_true",
                    help="Record this run as the map's baseline")
    pi.set_defaults(func=_cmd_index_agreement)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
