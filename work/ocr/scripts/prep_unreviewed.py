#!/usr/bin/env python3
"""What an *unreviewed* sheet's OCR rows can say before a human looks at them.

    python work/ocr/scripts/prep_unreviewed.py --map <uuid> --mpp 0.338 [--legend x,y,w,h]

`review_patterns.py` is built on verdicts and prints empty sections for a sheet nobody has reviewed.
This reads the same `ocr_labels` rows (PostgREST, read-only, no model call, no write) and reports only
what needs no verdict: run inventory, confidence, rotation, road-number tails and detached numbers
(French-era rule from docs/journals/261006-1882-ocr-review-patterns.md, rule 1), numeral spellings,
duplicate candidates (rule 4), suggested fragment groups (rule 5) and legend-like rows.
It reuses the 1882 helpers from review_patterns.py unchanged.

Box sizes: `label_w/label_h` exist only on human-edited rows, and a model box is not a tight text
rectangle (1898: `Quai Francis Garnier` is a 115 x 177 px box over a line printed ~600 px long; the letter
spacing read off the boxes that can be solved ranges 0.3-5.7 letter heights per character). So the
fragment heuristic uses one letter height `h0` (median short side of solved name rows) and lengths of
`1.2 * n_chars * h0` (1882 median spacing 1.23), and only the *centres and rotations* of the model's boxes.
That makes the suggested-group counts indicative, not a measurement.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labels import name_key  # noqa: E402
from review_patterns import (  # noqa: E402
    NAME_CATS, NUM_RE, OUT_ROOT, Sheet, axial_diff, fetch, incomplete_name, is_number_only,
    nchars, oriented_dims, pair_geometry, pctile, rot_bucket,
)

TAIL_RE = re.compile(r"(?:\b(?:n\s*[°º˚o]?\.?|no\.?)\s*)?\b\d+\w*\s*$", re.I)  # ends in a number token
NUMERAL_FORMS = {
    "N°": re.compile(r"N\s*°"), "Nº": re.compile(r"Nº"), "N˚": re.compile(r"N˚"),
    "No.": re.compile(r"\bNo\."), "No (no dot)": re.compile(r"\bNo\b(?!\.)"), "N.": re.compile(r"\bN\.(?!\s*[A-Za-z])"),
}


def solve_dims(rows: list[dict], spacing: float = 1.2) -> tuple[float, dict]:
    """One letter height h0 for the sheet (median short side oriented_dims can solve) and, per row,
    (long, short) = (spacing * n_chars * h0, h0). Model boxes are not trusted for length."""
    ss = [d[1] for r in rows for d in [oriented_dims(r)] if d and d[2] != "label" and d[1] > 0]
    h0 = median(ss) if ss else 50.0
    return h0, {r["id"]: (spacing * max(nchars(r["_eff_text"]), 1) * h0, h0) for r in rows}


def run(rows: list[dict], mpp: float, legend: tuple | None) -> dict:
    sh = Sheet(rows, mpp)
    res: dict = {"rows": len(rows)}

    # -- inventory
    res["runs"] = Counter(r["run_id"] for r in rows)
    res["models"] = Counter(r["model"] for r in rows)
    res["prompts"] = Counter(r.get("prompt") for r in rows)
    res["status"] = Counter(r["review_status"] for r in rows)
    res["category"] = Counter(r["category"] for r in rows)
    res["tiles"] = len({(r["tile_x"], r["tile_y"], r["tile_w"], r["tile_h"]) for r in rows})
    confs = [r["confidence"] for r in rows if r["confidence"] is not None]
    res["confidence"] = {
        "values": dict(sorted(Counter(round(c, 2) for c in confs).items())),
        "lt_0.9": sum(c < 0.9 for c in confs), "lt_0.8": sum(c < 0.8 for c in confs),
        "lt_0.9_by_category": dict(Counter(r["category"] for r in rows if r["confidence"] is not None and r["confidence"] < 0.9)),
        "median": median(confs),
    }
    res["rotation_axial_15deg_bins"] = {
        cat: dict(sorted(Counter(int(abs(r.get("rotation_deg") or 0) // 15 * 15) for r in rows if r["category"] == cat).items()))
        for cat in ("street", "hydrology")}
    res["rotation_bucket_street"] = dict(Counter(rot_bucket(r.get("rotation_deg")) for r in rows if r["category"] == "street"))

    # -- letter spacing (rows oriented_dims can solve) and the fitted k
    names = [r for r in rows if r["_eff_cat"] in NAME_CATS and not is_number_only(r["_eff_text"])]
    sp = []
    for r in names:
        d = oriented_dims(r)
        n = nchars(r["_eff_text"])
        if d and n >= 3 and d[1] > 0:
            sp.append(d[0] / n / d[1])
    h0, dims = solve_dims(names)
    res["letter_spacing"] = {"name_rows": len(names), "measurable": len(sp), "median": round(median(sp), 2) if sp else None,
                             "p10": pctile(sp, 10), "p90": pctile(sp, 90), "letter_height_h0_px": round(h0, 1)}

    # -- road numbers: tails, detached numbers, spellings
    street = [r for r in rows if r["_eff_cat"] == "street"]
    tail = [r for r in street if TAIL_RE.search(r["_eff_text"]) and not is_number_only(r["_eff_text"])]
    bare = [r for r in rows if is_number_only(r["_eff_text"]) or re.fullmatch(r"\s*\d{1,3}\s*", r["_eff_text"])]
    res["road_numbers"] = {
        "street_rows": len(street), "street_rows_ending_in_number": len(tail),
        "tail_examples": [r["_eff_text"] for r in tail[:10]],
        "bare_number_rows": len(bare), "bare_number_examples": [r["_eff_text"] for r in bare[:10]],
        "rows_with_any_digit": [(r["category"], r["_eff_text"]) for r in rows if re.search(r"\d", r["_eff_text"])],
    }
    # a bare number next to a street row: perpendicular offset <= 1.5 h and gap <= 30 h (1882 rule 5)
    detached = []
    for b in bare:
        if b["id"] not in dims:
            continue
        for s in street:
            if s["id"] == b["id"] or s["id"] not in dims:
                continue
            g = pair_geometry(_item(sh, b, dims), _item(sh, s, dims))
            if g and "gap_h" in g and g["perp_h"] <= 1.5 and -0.5 <= g["gap_h"] <= 30:
                detached.append((b["_eff_text"], s["_eff_text"]))
    res["road_numbers"]["detached_numbers_next_to_street"] = len(detached)
    forms = Counter()
    for r in rows:
        for name, rx in NUMERAL_FORMS.items():
            if rx.search(r["_eff_text"]):
                forms[name] += 1
    res["numeral_spellings"] = dict(forms)
    res["bare_generics"] = dict(Counter(r["_eff_text"].strip() for r in street
                                        if r["_eff_text"].strip().lower() in ("rue", "boulevard", "quai", "route", "avenue", "r.")))

    # -- duplicate candidates (rule 4): same name_key, rotation within 15 deg, centres within 75 m
    R_PX = 75 / mpp
    keyed = [(r, name_key(r["_eff_text"])) for r in rows if not r.get("is_text_group")]
    dup_pairs, same_key_far = [], []
    for i, (a, ka) in enumerate(keyed):
        if not ka:
            continue
        for b, kb in keyed[i + 1:]:
            if ka != kb:
                continue
            ax, ay = sh.centre(a)
            bx, by = sh.centre(b)
            d = math.hypot(ax - bx, ay - by) * mpp
            rot_ok = axial_diff(a.get("rotation_deg") or 0, b.get("rotation_deg") or 0) <= 15
            (dup_pairs if d <= 75 and rot_ok else same_key_far).append((a["_eff_text"], b["_eff_text"], round(d), a.get("rotation_deg"), b.get("rotation_deg")))
    keyless = Counter(r["_eff_text"].strip() for r, kk in keyed if not kk)
    # identical text, rotation within 15, within 75 m, any key (covers bare 'Rue')
    ident = []
    for i, (a, _) in enumerate(keyed):
        for b, _ in keyed[i + 1:]:
            if a["_eff_text"].strip().lower() == b["_eff_text"].strip().lower() and axial_diff(a.get("rotation_deg") or 0, b.get("rotation_deg") or 0) <= 15:
                ax, ay = sh.centre(a)
                bx, by = sh.centre(b)
                if math.hypot(ax - bx, ay - by) * mpp <= 75:
                    ident.append((a["_eff_text"], round(math.hypot(ax - bx, ay - by) * mpp, 1)))
    res["duplicates"] = {"radius_px": round(R_PX), "name_key_pairs_within_75m_rot15": len(dup_pairs), "pairs": dup_pairs[:15],
                         "same_name_key_elsewhere": len(same_key_far), "keyless_rows": sum(keyless.values()),
                         "keyless_top": keyless.most_common(6), "identical_text_within_75m_rot15": len(ident), "identical_examples": ident[:10]}

    # -- fragment candidates (rule 5): each incomplete piece -> candidate with smallest perpendicular offset
    items = {r["id"]: _item(sh, r, dims) for r in names if r["id"] in dims}
    inc = [r for r in names if r["id"] in items and incomplete_name(r["_eff_text"])]
    X, Y, K = 45, 1.5, 30
    top1, edges, with_cand, ncand = {}, [], 0, []
    for r in inc:
        cands = []
        for o in names:
            if o["id"] == r["id"] or o["id"] not in items:
                continue
            g = pair_geometry(items[r["id"]], items[o["id"]])
            if g and "gap_h" in g and g["drot"] <= X and g["perp_h"] <= Y and -0.5 <= g["gap_h"] <= K:
                cands.append((g["perp_h"], g["gap_h"], o))
        if cands:
            cands.sort(key=lambda t: t[0])
            with_cand += 1
            ncand.append(len(cands))
            top1[r["id"]] = cands[0][2]["id"]
            edges.append((r["_eff_text"], cands[0][2]["_eff_text"], round(cands[0][0], 2), round(cands[0][1], 1), len(cands)))
    byid = {r["id"]: r for r in names}
    pairs = {tuple(sorted((a, b))) for a, b in top1.items()}
    mutual = sum(1 for a, b in top1.items() if top1.get(b) == a and a < b)

    def generic_only(t):  # bare generic: no name core
        return not name_key(t)

    def no_generic(t):  # a name with no generic word at all ('Pagès', 'Lafont')
        return bool(name_key(t)) and incomplete_name(t) and not generic_only(t)
    gen = [r for r in inc if generic_only(r["_eff_text"])]
    bare_names = [r for r in inc if no_generic(r["_eff_text"])]
    # a bare generic whose centre sits inside a longer street row's box that contains the word: the
    # model's own second copy of one print (1882 'fragment' class), not a missing partner
    inside = 0
    for r in gen:
        cx, cy = sh.centre(r)
        w = r["_eff_text"].strip().lower()
        for o in names:
            if o["id"] != r["id"] and len(o["_eff_text"]) > len(r["_eff_text"]) and w in o["_eff_text"].lower().split():
                x, y, bw, bh = sh.box(o)
                if x <= cx <= x + bw and y <= cy <= y + bh:
                    inside += 1
                    break
    pair_kind = Counter()
    for a, b in pairs:
        ta, tb = byid[a]["_eff_text"], byid[b]["_eff_text"]
        ga, gb = generic_only(ta), generic_only(tb)
        pair_kind["generic + name-only" if (ga and no_generic(tb)) or (gb and no_generic(ta))
                  else "generic + full name" if ga or gb else "other"] += 1
    res["fragments"] = {
        "name_rows": len(names), "incomplete_pieces": len(inc), "bare_generics": len(gen), "name_only_rows": len(bare_names),
        "incomplete_with_a_candidate": with_cand, "mean_candidates": round(sum(ncand) / len(ncand), 1) if ncand else None,
        "bare_generic_inside_a_longer_row_that_contains_it": inside,
        "suggested_pairs_top1": len(pairs), "mutual_top1_pairs": mutual, "pair_kinds": dict(pair_kind),
        "rule": f"drot<={X}, perp<={Y} h, gap<={K} h, rank by perp; h0={h0:.0f}px, length=1.2*n*h0",
        "sample_pairs": [[byid[a]["_eff_text"], byid[b]["_eff_text"]] for a, b in list(pairs)[:15]],
    }
    lt = {r["id"] for r in rows if r["confidence"] is not None and r["confidence"] < 0.9}
    incs = {r["id"] for r in inc}
    other = {r["id"] for r in rows if r["category"] == "other"}
    res["review_queue"] = {
        "conf_lt_0.9": len(lt), "incomplete_name_pieces": len(incs), "category_other": len(other),
        "incomplete_also_lt_0.9": len(lt & incs), "union": len(lt | incs | other),
        "of_rows": len(rows),
    }
    # -- legend-like rows
    lg = [r for r in rows if r["category"] in ("legend", "legend_entry")]
    res["legend"] = {
        "legend_category_rows": len(lg), "texts": [r["_eff_text"] for r in lg],
        "numbered_lines": [r["_eff_text"] for r in rows if re.match(r"^\s*\d{1,3}\s*[.)\-]\s+\S", r["_eff_text"])],
        "propriet_rows": sum("propri" in r["_eff_text"].lower() for r in rows),
    }
    if legend:
        x, y, w, h = legend
        res["legend"]["rows_with_centre_inside_region"] = sum(x <= sh.centre(r)[0] <= x + w and y <= sh.centre(r)[1] <= y + h for r in rows)
    return res


def _item(sh: Sheet, r: dict, dims: dict) -> dict:
    cx, cy = sh.centre(r)
    lg, sh_ = dims.get(r["id"], (None, None))
    return {"cx": cx, "cy": cy, "rot": r.get("rotation_deg") or 0.0, "long": lg, "short": sh_, "id": r["id"], "text": r["_eff_text"]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--map", required=True)
    ap.add_argument("--mpp", type=float, required=True, help="metres per source pixel (scale.py / ocr.py scale)")
    ap.add_argument("--legend", default=None, help="x,y,w,h of the legend region in source px (maps.triage)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rows = fetch(a.map)
    if not rows:
        raise SystemExit(f"no ocr_labels rows for {a.map}")
    leg = tuple(float(v) for v in a.legend.split(",")) if a.legend else None
    res = run(rows, a.mpp, leg)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    out = Path(a.out) if a.out else OUT_ROOT / a.map / "prep_unreviewed.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print(f"\n[ok] wrote {out}")


if __name__ == "__main__":
    main()
