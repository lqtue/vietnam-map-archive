"""Audit one saved OCR run without touching Supabase.

The model's confidence is useful inside a single call but not a publication
decision.  A merged run also knows whether independent grid passes saw the
same label.  This command keeps those facts together in a small, portable
report, so a worker or reviewer can decide what needs attention before a run
is promoted.

    python work/ocr/scripts/audit_run.py --run-dir work/ocr/outputs/<map>/runs/<run>

It reads only ``all_extractions.json``.  ``--output`` writes the report; the
default prints it, which makes the command safe to use as a CI-style gate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


EDGE_OR_FRAGMENT = re.compile(r"\b(continues outside|fragment|edge zone)\b", re.I)
TILE_NAME = re.compile(r"^(\d+)_(\d+)_(\d+)_(\d+)_tile\.png$")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _valid_bbox(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(_is_number(part) for part in value)
        and value[2] > 0
        and value[3] > 0
    )


def _item_errors(item: Any, index: int) -> list[str]:
    prefix = f"extractions[{index}]"
    if not isinstance(item, dict):
        return [f"{prefix}: not an object"]
    errors = []
    if not isinstance(item.get("text"), str) or not item["text"].strip():
        errors.append(f"{prefix}: missing text")
    confidence = item.get("confidence")
    if not _is_number(confidence) or not 0 <= confidence <= 1:
        errors.append(f"{prefix}: confidence must be a number in [0, 1]")
    if not _valid_bbox(item.get("global_bbox")):
        errors.append(f"{prefix}: global_bbox must be [x, y, width, height] with positive size")
    return errors


def audit(data: dict[str, Any], *, review_confidence: float = 0.7) -> dict[str, Any]:
    """Return a JSON-serialisable audit for an ``all_extractions`` manifest."""
    errors: list[str] = []
    items = data.get("extractions")
    if not isinstance(items, list):
        return {"ok": False, "errors": ["manifest: extractions must be a list"]}

    for index, item in enumerate(items):
        errors.extend(_item_errors(item, index))

    valid_items = [(index, item) for index, item in enumerate(items) if isinstance(item, dict)]
    passes = Counter(item.get("n_passes", 1) for _, item in valid_items)
    categories = Counter(item.get("category", "other") for _, item in valid_items)
    candidates = []
    for index, item in valid_items:
        confidence = item.get("confidence")
        notes = item.get("notes") if isinstance(item.get("notes"), str) else ""
        n_passes = item.get("n_passes", 1)
        # A partial label can be useful evidence, but is not safe as a public
        # label on its own.  We deliberately do not queue high-confidence,
        # complete singleton labels: a shifted grid does not necessarily cover
        # the same content, and that would turn the queue into every new label.
        reasons = []
        if n_passes == 1 and _is_number(confidence) and confidence < review_confidence:
            reasons.append(f"single pass and confidence < {review_confidence:g}")
        if n_passes == 1 and EDGE_OR_FRAGMENT.search(notes):
            reasons.append("single pass with edge/fragment note")
        if reasons:
            candidates.append(
                {
                    "index": index,
                    "text": item.get("text"),
                    "category": item.get("category", "other"),
                    "confidence": confidence,
                    "n_passes": n_passes,
                    "notes": notes or None,
                    "reasons": reasons,
                    "already_marked": bool(item.get("requires_review")),
                }
            )

    candidates.sort(key=lambda item: (not item["already_marked"], item["confidence"], item["text"]))
    return {
        "ok": not errors,
        "map_id": data.get("map_id"),
        "run_id": data.get("run_id"),
        "merged_from": data.get("merged_from", []),
        "counts": {
            "items": len(items),
            "raw": data.get("n_raw"),
            "deduped": data.get("n_deduped"),
            "by_passes": {str(key): value for key, value in sorted(passes.items(), key=lambda pair: str(pair[0]))},
            "by_category": dict(sorted(categories.items())),
            "currently_marked_for_review": sum(bool(item.get("requires_review")) for _, item in valid_items),
            "automated_review_queue": len(candidates),
        },
        "review_policy": {
            "single_pass_confidence_below": review_confidence,
            "single_pass_edge_or_fragment_note": True,
        },
        "errors": errors,
        "review_candidates": candidates,
    }


def self_check() -> None:
    healthy = {
        "map_id": "map", "run_id": "run", "n_raw": 3, "n_deduped": 2,
        "extractions": [
            {"text": "Rue Catinat", "category": "street", "confidence": 0.95,
             "global_bbox": [1, 2, 3, 4], "n_passes": 2},
            {"text": "...al", "category": "street", "confidence": 0.5,
             "global_bbox": [1, 2, 3, 4], "n_passes": 1,
             "notes": "continues outside left edge", "requires_review": True},
        ],
    }
    report = audit(healthy)
    assert report["ok"]
    assert report["counts"]["automated_review_queue"] == 1
    assert report["review_candidates"][0]["already_marked"]
    broken = audit({"extractions": [{"text": "", "confidence": 1, "global_bbox": [0, 0, 0, 1]}]})
    assert not broken["ok"] and len(broken["errors"]) == 2
    print("[ok] audit_run self-check passed")


def render_review_crops(report: dict[str, Any], tiles_dir: Path, out_dir: Path) -> int:
    """Render one labelled crop per queued item from locally cached source tiles."""
    from PIL import Image, ImageDraw

    tiles = []
    for path in tiles_dir.glob("*_tile.png"):
        match = TILE_NAME.match(path.name)
        if match:
            x, y, width, height = (int(value) for value in match.groups())
            tiles.append((path, x, y, width, height))
    if not tiles:
        raise ValueError(f"no source tile images under {tiles_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for candidate in report["review_candidates"]:
        index = candidate["index"]
        # The report deliberately does not duplicate every bbox.  Retrieve the
        # item from the already-loaded manifest via the attached private value.
        bbox = candidate.pop("_bbox", None)
        if not bbox:
            continue
        x, y, width, height = bbox
        cx, cy = x + width / 2, y + height / 2
        containing = [tile for tile in tiles if tile[1] <= cx <= tile[1] + tile[3]
                      and tile[2] <= cy <= tile[2] + tile[4]]
        if not containing:
            manifest.append({"index": index, "text": candidate["text"], "status": "no cached tile"})
            continue
        path, tx, ty, tw, th = min(containing, key=lambda tile: tile[3] * tile[4])
        image = Image.open(path).convert("RGB")
        sx, sy = image.width / tw, image.height / th
        pad = max(180, int(max(width, height) * 0.75))
        left, top = max(tx, x - pad), max(ty, y - pad)
        right, bottom = min(tx + tw, x + width + pad), min(ty + th, y + height + pad)
        crop = image.crop(((left - tx) * sx, (top - ty) * sy, (right - tx) * sx, (bottom - ty) * sy))
        draw = ImageDraw.Draw(crop)
        draw.rectangle(((x - left) * sx, (y - top) * sy, (x + width - left) * sx, (y + height - top) * sy),
                       outline=(230, 35, 35), width=max(2, round(sx * 3)))
        filename = f"{index:03d}.png"
        crop.save(out_dir / filename)
        manifest.append({"index": index, "text": candidate["text"], "file": filename,
                         "source_tile": path.name, "bbox": bbox})
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return len(manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", type=Path, help="directory containing all_extractions.json")
    parser.add_argument("--output", type=Path, help="write report JSON instead of stdout")
    parser.add_argument("--review-confidence", type=float, default=0.7,
                        help="queue a single-pass label below this confidence (default: 0.7)")
    parser.add_argument("--tiles-dir", type=Path,
                        help="locally cached source tiles; with --review-dir, render candidate crops")
    parser.add_argument("--review-dir", type=Path,
                        help="write labelled candidate crops here (requires --tiles-dir)")
    parser.add_argument("--self-check", action="store_true", help="run offline assertions")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return 0
    if not args.run_dir:
        parser.error("--run-dir is required unless --self-check is used")
    if not 0 <= args.review_confidence <= 1:
        parser.error("--review-confidence must be in [0, 1]")
    if bool(args.tiles_dir) != bool(args.review_dir):
        parser.error("--tiles-dir and --review-dir must be used together")
    path = args.run_dir / "all_extractions.json"
    if not path.exists():
        parser.error(f"no such artifact: {path}")
    report = audit(json.loads(path.read_text()), review_confidence=args.review_confidence)
    if args.review_dir:
        # Keep bbox private to rendering: the public report remains compact.
        source_items = json.loads(path.read_text())["extractions"]
        for candidate in report["review_candidates"]:
            candidate["_bbox"] = source_items[candidate["index"]]["global_bbox"]
        rendered = render_review_crops(report, args.tiles_dir, args.review_dir)
        for candidate in report["review_candidates"]:
            candidate.pop("_bbox", None)
        print(f"review crops: {args.review_dir} ({rendered} candidates)")
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded)
        print(f"audit: {args.output} ({report['counts']['automated_review_queue']} review candidates)")
    else:
        print(encoded, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
