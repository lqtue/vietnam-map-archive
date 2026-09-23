#!/usr/bin/env python3
"""Push the 1968 Sài Gòn sheet's already-computed legend/numerals onto the DB.

Why this exists: `legend1968/legend.json` (244 entries) and
`numerals1968/numerals.json` (712 markers, deduped) were both run and written
to disk on 2026-09-10/11 but never upserted to `ocr_extractions` — the map's
`ocr --legend`/`ocr --numerals` DB-write step was skipped that day, and nothing
since has re-run either (both call Gemini/local Tesseract, and this data is
already paid for). `modern_prior.py --legend` is what caught it: the sheet
shows `runs=2!` with no legend_entry/legend_ref rows at all.

This is a pure import — no API calls, no re-extraction — of the exact JSON the
pipeline already produced, through the exact functions `ocr.py` uses to write
those rows (`_write_legend_rows` for the legend key, the same row shape
`cmd_numerals --db` builds for the map numerals), so the rows this writes are
byte-for-byte what a normal `--db` run that day would have written.

    python work/ocr/scripts/backfill_1968_legend.py --dry-run
    python work/ocr/scripts/backfill_1968_legend.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

MAP_ID = "3a446d85-25a8-4e81-9cfc-8de357c3a5df"
OUT = Path(__file__).resolve().parents[1] / "outputs" / MAP_ID / "runs"
LEGEND_RUN, NUMERALS_RUN = "legend1968", "numerals1968"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    from ocr import _write_legend_rows

    legend = json.loads((OUT / LEGEND_RUN / "legend.json").read_text())
    numerals = json.loads((OUT / NUMERALS_RUN / "numerals.json").read_text())

    entries = legend["entries"]
    disputed = set(legend.get("grid_disputed", []))
    for e in entries:
        if e["n"] in disputed:
            e["grid_disputed"] = True
    model = ",".join(legend.get("models", [])) or "gemini"

    print(f"legend: {len(entries)} entries, region={legend['region_source']}, "
          f"{len(disputed)} grid_disputed")
    print(f"numerals: {len(numerals['numerals'])} deduped markers "
          f"(of {numerals['n_raw']} raw)")

    if args.dry_run:
        print("--dry-run: nothing written")
        return 0

    n_legend = _write_legend_rows(
        MAP_ID, LEGEND_RUN, tuple(legend["region_source"]), entries, model
    )
    print(f"[db] upserted {n_legend} legend_entry row(s)")

    from supabase_client import upsert_ocr_extractions

    rows = []
    for d in numerals["numerals"]:
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
    n_refs = upsert_ocr_extractions(MAP_ID, NUMERALS_RUN, rows)
    print(f"[db] upserted {n_refs} legend_ref row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
