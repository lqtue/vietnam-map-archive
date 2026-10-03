#!/usr/bin/env python3
"""Put the names from one segmentation run onto the shapes of another.

`seg_gemini.py` returns a name bound to a polygon, but a coarse polygon —
median 5 vertices, a rotated rectangle over a block. MapSAM2 returns a good
boundary and no name at all. This joins the two: each mask takes the name of
the **smallest named polygon that contains it**, which is the rule
`join_labels.py` already uses for OCR extractions.

Why not just use OCR for the naming, which is what the pipeline does today:
only 22 of the 46 hand-traced polygons on the 1882 sheet contain an OCR label
centroid, so an OCR-fed join is capped at 48% of them before the segmenter is
even considered. A name read off the ink as part of the segmentation call is
not subject to that ceiling — it is a different question asked of the paper,
not a better answer to the same one.

    python work/image-processing/scripts/name_masks.py --names gemini_run.json \\
        --masks sam2_run.json --out named.json

Nothing is written to the database. The output is a run file in the same shape
as its inputs, so `seg_eval.py` scores it unchanged.

Self-check (no network): python work/image-processing/scripts/name_masks.py --self-check
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# A mask this far outside a name's polygon is a neighbour, not a member. The
# coarse polygon overhangs its block by design, so "centroid inside" would
# claim buildings across the street; "wholly inside" would reject anything the
# rectangle clips. 0.7 is the middle, and it is a knob:
#
# ponytail: one threshold for every sheet. Tune it per sheet when a run names
# things across a street, or drop to centroid-in-polygon if the polygons ever
# get tight enough to make containment exact.
MIN_INSIDE = 0.7


def _polys(path: str):
    from shapely.geometry import Polygon
    from shapely.validation import make_valid

    doc = json.load(open(path, encoding="utf-8"))
    out = []
    for p in doc.get("polygons") or []:
        coords = p.get("coords")
        if not coords or len(coords) < 3:
            continue
        g = make_valid(Polygon(coords))
        if not g.is_empty and g.area > 0:
            out.append((p, g))
    return doc, out


def assign(masks: list, names: list) -> list[str | None]:
    """For each mask, the name of the smallest named polygon containing it.

    `masks` and `names` are lists of `(record, geometry)`. Smallest wins so a
    building inside a named block inside a named quarter takes the building's
    name — the same preference `join_labels.py` applies, and the reason a
    containment join does not need the levels to be declared anywhere.
    """
    out: list[str | None] = []
    for _, mg in masks:
        best_name, best_area = None, None
        for rec, ng in names:
            label = (rec.get("label") or "").strip()
            if not label:
                continue
            try:
                share = mg.intersection(ng).area / mg.area
            except Exception:
                continue
            if share < MIN_INSIDE:
                continue
            if best_area is None or ng.area < best_area:
                best_name, best_area = label, ng.area
        out.append(best_name)
    return out


def run(args: argparse.Namespace) -> int:
    names_doc, names = _polys(args.names)
    masks_doc, masks = _polys(args.masks)
    named_sources = sum(1 for rec, _ in names if (rec.get("label") or "").strip())
    print(f"{len(names)} name polygons ({named_sources} carry a name) · {len(masks)} masks")

    assigned = assign(masks, names)
    hit = sum(1 for a in assigned if a)
    for (rec, _), label in zip(masks, assigned):
        if label:
            rec["label"] = label

    out = dict(masks_doc)
    out["polygons"] = [rec for rec, _ in masks]
    out["meta"] = {**(masks_doc.get("meta") or {}),
                   "named_from": Path(args.names).name,
                   "named": hit,
                   "min_inside": MIN_INSIDE}
    Path(args.out).write_text(json.dumps(out), encoding="utf-8")

    print(f"{hit}/{len(masks)} masks named ({hit / len(masks):.1%}) → {args.out}")
    from collections import Counter
    for name, n in Counter(a for a in assigned if a).most_common(12):
        print(f"  {n:4d}  {name}")
    return 0


def _self_check() -> None:
    from shapely.geometry import Polygon

    def rec(label, coords):
        return ({"label": label, "coords": coords}, Polygon(coords))

    block = rec("CASERNES", [(0, 0), (100, 0), (100, 100), (0, 100)])
    wing = rec("POUDRIERE", [(60, 60), (100, 60), (100, 100), (60, 100)])
    unnamed = rec("", [(0, 0), (100, 0), (100, 100), (0, 100)])

    inside = rec(None, [(10, 10), (30, 10), (30, 30), (10, 30)])
    in_wing = rec(None, [(70, 70), (90, 70), (90, 90), (70, 90)])
    outside = rec(None, [(200, 200), (210, 200), (210, 210), (200, 210)])
    # 60% inside the block — under the threshold, so it belongs to nobody.
    straddling = rec(None, [(90, 40), (115, 40), (115, 60), (90, 60)])

    got = assign([inside, in_wing, outside, straddling], [block, wing, unnamed])
    assert got == ["CASERNES", "POUDRIERE", None, None], got

    # The smallest containing name wins, whatever order the names arrive in.
    assert assign([in_wing], [wing, block])[0] == "POUDRIERE"
    assert assign([in_wing], [block, wing])[0] == "POUDRIERE"

    # An unnamed polygon never claims a mask, even when it is the tightest fit.
    tight = rec("", [(9, 9), (31, 9), (31, 31), (9, 31)])
    assert assign([inside], [tight, block])[0] == "CASERNES"

    # No names at all, and no masks at all, are both quiet no-ops rather than
    # errors: an empty run file is the normal output of a failed pass.
    assert assign([inside], []) == [None]
    assert assign([], [block]) == []

    print("[ok] name_masks self-check passed")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--names", help="run whose polygons carry labels")
    p.add_argument("--masks", help="run whose polygons carry the good boundaries")
    p.add_argument("--out", default="named.json")
    p.add_argument("--self-check", action="store_true")
    args = p.parse_args()

    if args.self_check:
        _self_check()
        return 0
    if not (args.names and args.masks):
        p.error("--names and --masks are both required")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
