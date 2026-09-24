#!/usr/bin/env python3
"""Build a gazetteer of every name the OCR pipeline has read off the maps.

    python work/ocr/scripts/dictionary.py                 # → outputs/dictionary.{json,md}
    python work/ocr/scripts/dictionary.py --category street --min-confidence 0.6
    python work/ocr/scripts/dictionary.py --self-check     # no DB, asserts only

One entry per distinct name, not per extraction: the same "Rue Catinat" read on
four maps is one headword carrying four sightings. Grouping is by a normalized
key (case, whitespace and edge punctuation folded); diacritics are preserved,
because "Sài Gòn" and "Sai Gon" are different readings and the difference is the
kind of thing this file exists to show.

`text_corrected` / `category_corrected` (what a human fixed in the OCR Review
tab) win over the model's `text` / `category`. Rejected rows are dropped unless
--include-rejected.

Overlaps with the `place_names` view (migration 067), which groups the same rows
in Postgres and does it better: `place_key` folds punctuation *and* accents, so
FOURRIERE and FOURRIÈRE are one row there and two cross-linked rows here. The
view is the gazetteer of record and feeds /place and /api/press. This file earns
its place only on what the view drops — `legend_entry` rows, a confidence
filter, and the per-sighting provenance below. See ROADMAP `dictionary-on-place-names`: the grouping
here should be replaced by a read of that view before the two rules drift.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

OUT_DIR = Path(__file__).resolve().parents[1] / "outputs"
PAGE = 1000

# Categories that are map furniture rather than places on the ground.
FURNITURE = {"title", "legend", "other"}


def normalize(text: str) -> str:
    """Fold a surface form to its grouping key. Diacritics survive; case does not."""
    s = unicodedata.normalize("NFC", text).strip()
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" .,;:!?\"'()[]{}«»-–—_")
    return s.casefold()


def fold(key: str) -> str:
    """Accent-stripped key, for spotting the same name read two ways.

    Grouping on this would be wrong — "Sài Gòn" and "Sai Gon" are different
    readings — but a French label printed in caps loses its accents on the sheet
    itself, so CHATEAU D'EAU and CHÂTEAU D'EAU are one place and the reviewer
    should see them side by side.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", key) if not unicodedata.combining(c)
    )


def _fetch_all(endpoint: str, select: str) -> list[dict[str, Any]]:
    """Page through a PostgREST table with the service key."""
    import requests
    from supabase_client import _load_config

    url, key = _load_config()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    rows: list[dict[str, Any]] = []
    while True:
        offset = len(rows)
        resp = requests.get(
            f"{url}/rest/v1/{endpoint}?select={select}&limit={PAGE}&offset={offset}"
            f"&order=id.asc",
            headers=headers,
            timeout=60,
        )
        if not resp.ok:
            raise requests.HTTPError(f"{resp.status_code} {endpoint}: {resp.text[:300]}")
        page = resp.json()
        rows.extend(page)
        if len(page) < PAGE:
            return rows


def build(
    min_confidence: float = 0.0,
    categories: set[str] | None = None,
    include_rejected: bool = False,
    include_furniture: bool = False,
) -> dict[str, Any]:
    extractions = _fetch_all(
        "ocr_labels",
        "map_id,run_id,text,text_corrected,category,category_corrected,"
        "confidence,review_status,global_x,global_y",
    )
    maps = {
        m["id"]: m
        for m in _fetch_all("maps", "id,name,year,date_label,status")
    }

    entries: dict[str, dict[str, Any]] = {}
    skipped = Counter()

    for row in extractions:
        if not include_rejected and row["review_status"] == "rejected":
            skipped["rejected"] += 1
            continue
        if (row.get("confidence") or 0) < min_confidence:
            skipped["low_confidence"] += 1
            continue

        surface = (row.get("text_corrected") or row["text"] or "").strip()
        category = row.get("category_corrected") or row["category"]
        if not include_furniture and category in FURNITURE:
            skipped["furniture"] += 1
            continue
        if categories and category not in categories:
            skipped["other_category"] += 1
            continue

        key = normalize(surface)
        if not key:
            skipped["empty"] += 1
            continue

        m = maps.get(row["map_id"], {})
        e = entries.setdefault(
            key,
            {
                "key": key,
                "headword": surface,
                "surface_forms": Counter(),
                "categories": Counter(),
                "sightings": [],
                "validated": 0,
            },
        )
        e["surface_forms"][surface] += 1
        e["categories"][category] += 1
        e["validated"] += row["review_status"] == "validated"
        e["sightings"].append(
            {
                "map_id": row["map_id"],
                "map_name": m.get("name"),
                "year": m.get("year"),
                "run_id": row["run_id"],
                "confidence": row.get("confidence"),
                "px": [row.get("global_x"), row.get("global_y")],
            }
        )

    out = []
    for e in entries.values():
        years = sorted({s["year"] for s in e["sightings"] if s["year"]})
        map_ids = {s["map_id"] for s in e["sightings"]}
        out.append(
            {
                "key": e["key"],
                # Most-seen spelling is the headword; ties break to the longest,
                # which keeps "Rue Catinat" over a truncated "Rue Catina".
                "headword": max(
                    e["surface_forms"].items(), key=lambda kv: (kv[1], len(kv[0]))
                )[0],
                "category": e["categories"].most_common(1)[0][0],
                "categories": dict(e["categories"]),
                "variants": sorted(f for f in e["surface_forms"] if f != e["headword"]),
                "n_sightings": len(e["sightings"]),
                "n_maps": len(map_ids),
                "years": years,
                "first_year": years[0] if years else None,
                "last_year": years[-1] if years else None,
                "validated": e["validated"],
                "sightings": sorted(
                    e["sightings"], key=lambda s: (s["year"] or 0, s["run_id"])
                ),
            }
        )

    # Cross-link entries whose only difference is diacritics.
    by_fold: dict[str, list[dict[str, Any]]] = {}
    for e in out:
        by_fold.setdefault(fold(e["key"]), []).append(e)
    for group in by_fold.values():
        if len(group) > 1:
            for e in group:
                e["similar"] = sorted(o["headword"] for o in group if o is not e)

    out.sort(key=lambda e: (e["category"], e["key"]))
    return {
        "generated_from": {
            "extractions": len(extractions),
            "maps_in_corpus": len({r["map_id"] for r in extractions}),
            "min_confidence": min_confidence,
            "include_rejected": include_rejected,
            "include_furniture": include_furniture,
            "skipped": dict(skipped),
        },
        "n_names": len(out),
        "entries": out,
    }


def to_markdown(doc: dict[str, Any]) -> str:
    src = doc["generated_from"]
    lines = [
        "# Map name dictionary",
        "",
        f"{doc['n_names']} distinct names from {src['extractions']} extractions "
        f"across {src['maps_in_corpus']} maps.",
        f"Skipped: {src['skipped'] or 'nothing'}.",
        "",
    ]
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for e in doc["entries"]:
        by_cat.setdefault(e["category"], []).append(e)

    for cat in sorted(by_cat):
        lines += [f"## {cat} ({len(by_cat[cat])})", "", "| Name | Years | Maps | Seen | Variants | Same name, other accents |", "|---|---|---|---|---|---|"]
        for e in by_cat[cat]:
            years = (
                f"{e['first_year']}–{e['last_year']}"
                if e["first_year"] != e["last_year"]
                else str(e["first_year"] or "—")
            )
            variants = ", ".join(e["variants"][:4]) or ""
            name = e["headword"].replace("|", "\\|")
            lines.append(
                f"| {name} | {years} | {e['n_maps']} | {e['n_sightings']} | {variants} "
                f"| {', '.join(e.get('similar', []))} |"
            )
        lines.append("")
    return "\n".join(lines)


def self_check() -> None:
    assert normalize("  Rue   Catinat. ") == "rue catinat"
    assert normalize("RUE CATINAT") == normalize("rue catinat")
    # Diacritics are meaningful and must not fold together.
    assert normalize("Sài Gòn") != normalize("Sai Gon")
    assert normalize("«Chợ Lớn»") == "chợ lớn"
    assert normalize(" ... ") == ""
    assert fold(normalize("CHÂTEAU D'EAU")) == fold(normalize("CHATEAU D'EAU"))
    assert fold("chợ lớn") == "cho lon"
    print("dictionary self-check ok")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT_DIR)
    p.add_argument("--min-confidence", type=float, default=0.0)
    p.add_argument("--category", action="append", help="repeatable; default = all")
    p.add_argument("--include-rejected", action="store_true")
    p.add_argument("--include-furniture", action="store_true",
                   help=f"keep {sorted(FURNITURE)} rows, which are map furniture not places")
    p.add_argument("--self-check", action="store_true")
    args = p.parse_args()

    if args.self_check:
        self_check()
        return

    doc = build(
        min_confidence=args.min_confidence,
        categories=set(args.category) if args.category else None,
        include_rejected=args.include_rejected,
        include_furniture=args.include_furniture,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "dictionary.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    (args.out / "dictionary.md").write_text(to_markdown(doc))
    src = doc["generated_from"]
    print(
        f"{doc['n_names']} names from {src['extractions']} extractions "
        f"across {src['maps_in_corpus']} maps → {args.out}/dictionary.{{json,md}}"
    )


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
