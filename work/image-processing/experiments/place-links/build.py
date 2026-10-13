#!/usr/bin/env python3
"""Build the place-link items for the 1882 Plan Cadastral and score the suggester on an independent reference.

    python3 work/image-processing/experiments/place-links/build.py [--refresh] [--radius 150]
    python3 work/image-processing/experiments/place-links/build.py --self-check

Reads (no writes to any database; labels come from one read-only Supabase query, cached in labels.json):
  ocr_labels                 scope: non-rejected, effective category (corrected wins) in institution, place, building, legend
  results/annotations/<map>.json                       the georeference (fit_sheet affine, 8 GCPs)
  results/prior/<map>/landmarks_overpass*.json         cached OSM
  results/prior/<map>/landmarks.csv                    24 hand-sourced rows: THE INDEPENDENT REFERENCE
  results/prior/<map>/gcps-1882.json                   control points: a label within 30 m of one is `in_fit`
Writes under results/prior/<map>/place-links/: items.json candidates.csv score.json (labels.json = cache).

Not the dev set: the 27 legend_finds picks (1968 map) tuned name_today.py; `name_today.py --eval` prints
them as "DEV, in-sample". This script never uses them.

PREDICTIONS, written 2026-10-12 before the first scoring run (also in README.md):
  landmark rows with a matched in-scope label  13 of 14
  of those in_fit                              2
  scored n                                     11
  hit@1                                        5/11   (45%)
  hit@3                                        7/11   (64%)
  no candidate within 150 m                    2      (old-marche-central, ba-son)

Truth: a candidate is the right modern place when it carries the landmark's OSM id (primary or merged),
its Wikidata id, or - rows with neither, and `gone` rows - its folded name contains (or is contained in) the
folded first clause of `name_modern` (token overlap was tried first and let "Bến Nghé" stand for "Bến Thành").
`in_fit`: the label is within 30 m of a GCP, or the matched modern place's outline is. The transform behind every distance: the `modern_prior.fit_sheet` affine (11.5 m RMS), not
the stored Allmaps helmert.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "work" / "image-processing" / "scripts"))
sys.path.insert(0, str(ROOT / "work" / "review-kit"))
import name_today as ns  # noqa: E402
from review_record import wilson  # noqa: E402

MAP = "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b"
PRIOR = ROOT / "work" / "image-processing" / "results" / "prior" / MAP
OUT = PRIOR / "place-links"
IN_FIT_M = 30.0
PLACE_LINK_VERSION = "place-link-v1"
PREDICTED = {"landmark_rows_with_label_matched": 13, "in_fit": 2, "scored_n": 11, "hit1": 5, "hit3": 7, "no_candidate": 2}


def outline_px(geom_ll, fit, approx: bool, maxpts: int = 60):
    """A candidate's outline in source pixels, or None (a point, or a bounding box standing in for an outline)."""
    import numpy as np

    if approx or geom_ll.geom_type == "Point":
        return None
    g = geom_ll
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda p: p.area)
    pts = g.exterior.coords if g.geom_type == "Polygon" else g.coords if g.geom_type == "LineString" else None
    if pts is None:
        return None
    a = np.array(pts)
    if len(a) > maxpts:
        a = a[np.linspace(0, len(a) - 1, maxpts).astype(int)]
    return [[round(float(x), 1), round(float(y), 1)] for x, y in fit.px(a)]


def truth_hit(row: dict, c: dict) -> str | None:
    """How candidate c is the landmark row's modern place: 'osm' | 'wikidata' | 'name' | None."""
    if row.get("osm_id") and (c["osm"] == row["osm_id"] or row["osm_id"] in c["osm_alts"]):
        return "osm"
    if row.get("wikidata") and c["wikidata"] == row["wikidata"]:
        return "wikidata"
    if not row.get("osm_id") and not row.get("wikidata") or row["status"] == "gone":
        first = ns.fold(row["name_modern"].split(",")[0].split("(")[0])
        if len(first.split()) >= 2 and any(first in ns.fold(n) or ns.fold(n) in first for n in c["names"]):
            return "name"
    return None


def score_landmarks(rows, items_by_text, gcp_flag) -> dict:
    """rows: landmarks.csv dicts. items_by_text: folded label text -> list of item dicts (all candidates ranked)."""
    out, scored = [], []
    for r in rows:
        if not r["name_1882"]:
            continue
        key = ns.fold(r["name_1882"])
        its = items_by_text.get(key, [])
        rec = {"key": r["key"], "status": r["status"], "name_1882": r["name_1882"], "name_modern": r["name_modern"],
               "label_matches": len(its)}
        if not its:
            rec["result"] = "no_in_scope_label"
            out.append(rec)
            continue
        it = its[0]
        if len(its) > 1 and r.get("ocr_label_xy"):
            x, y = (float(v) for v in r["ocr_label_xy"].split(","))
            it = min(its, key=lambda i: math.hypot(i["px"][0] - x, i["px"][1] - y))
        rec.update(label_id=it["id"], category=it["category"], in_fit=it["in_fit"], gcp_dist_m=it["gcp_dist_m"],
                   n_cands=len(it["all"]))
        rank, how = None, None
        for k, c in enumerate(it["all"], 1):
            h = truth_hit(r, c)
            if h:
                rank, how = k, h
                rec["truth_gcp_m"] = round(c.get("gcp_m", 1e9), 1)
                if c.get("gcp_m", 1e9) <= IN_FIT_M:
                    it = {**it, "in_fit": True}
                    rec["in_fit"] = True
                break
        near = sorted(it["all"], key=lambda c: c["d"]) if it["all"] else []
        rec["rank_nearest_only"] = next((k for k, c in enumerate(near, 1) if truth_hit(r, c)), None)
        rec.update(rank=rank, match_by=how, top1=(it["all"][0]["name"] if it["all"] else None))
        rec["result"] = "in_fit" if it["in_fit"] else "scored"
        if not it["in_fit"]:
            scored.append(rec)
        out.append(rec)
    n = len(scored)
    h1, h3 = sum(1 for s in scored if s["rank"] == 1), sum(1 for s in scored if s["rank"] and s["rank"] <= 3)
    nc = sum(1 for s in scored if s["n_cands"] == 0)

    def by(f):
        g = Counter(f(s) for s in scored)
        return {k: {"n": g[k], "hit1": sum(1 for s in scored if f(s) == k and s["rank"] == 1),
                    "hit3": sum(1 for s in scored if f(s) == k and s["rank"] and s["rank"] <= 3)} for k in g}

    nn1 = sum(1 for s in scored if s["rank_nearest_only"] == 1)
    return {"n_scored": n, "baseline_nearest_hit1": nn1, "baseline_nearest_hit1_wilson": wilson(nn1, n), "hit1": h1, "hit3": h3, "hit1_wilson": wilson(h1, n), "hit3_wilson": wilson(h3, n),
            "no_candidate": nc, "in_fit": [s["key"] for s in out if s.get("in_fit")],
            "matched_label": sum(1 for s in out if s["result"] != "no_in_scope_label"),
            "rows_with_1882_name": sum(1 for s in out), "by_status": by(lambda s: s["status"]),
            "found_but_below_3": [s["key"] for s in scored if s["rank"] and s["rank"] > 3],
            "never_found": [s["key"] for s in scored if not s["rank"]], "rows": out}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--radius", type=float, default=150.0)
    ap.add_argument("--refresh", action="store_true", help="re-read ocr_labels from Supabase (read-only)")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return self_check()

    import numpy as np

    import modern_prior as mp

    OUT.mkdir(parents=True, exist_ok=True)
    lab_f = OUT / "labels.json"
    if a.refresh or not lab_f.exists():
        labels = ns.rest("ocr_labels", {"map_id": f"eq.{MAP}", "select": "id,text,text_corrected,category,category_corrected,"
                                        "review_status,notes,global_x,global_y,global_w,global_h"})
        lab_f.write_text(json.dumps(labels))
    labels = json.loads(lab_f.read_text())
    ann = json.loads((ROOT / "work/image-processing/results/annotations" / f"{MAP}.json").read_text())
    fit = mp.fit_sheet(ann)
    W, H = json.loads((ROOT / "work/image-processing/experiments/river-reference/native.json").read_text())["1882"]["size"]
    pool = ns.build_pool(fit.bbox_lonlat(W, H), (PRIOR / "landmarks_overpass.json", PRIOR / "landmarks_overpass_relations.json"))
    srcs = Counter(r["source"] for r in pool.recs)

    # scope: exact counts
    live = [l for l in labels if l.get("review_status") != "rejected"]
    scope_raw = Counter(l["category"] for l in live if l["category"] in ns.PLACE_CATS)
    scope_eff = Counter(ns.cat(l) for l in live if ns.cat(l) in ns.PLACE_CATS)
    in_scope = [l for l in live if ns.cat(l) in ns.PLACE_CATS]

    rows = ns.propose(labels, fit, pool, a.radius, 1000, cats=ns.PLACE_CATS)
    placed = {r["lab"]["id"] for r in rows}
    unplaced = Counter(ns.cat(l) for l in in_scope if l["id"] not in placed)

    gcps = json.loads((PRIOR / "gcps-1882.json").read_text())["gcps"]
    mpp = fit.metres_per_px
    p0, p1 = fit.px(np.array([[106.7, 10.78], [106.7, 10.781]]))
    nv = (p1 - p0) / np.linalg.norm(p1 - p0)

    import shapely

    gcp_m = [shapely.Point(*pool.tf.transform(*g["lonlat"])) for g in gcps]
    items, all_rows = [], []
    for r in rows:
        lab = r["lab"]
        gd = min(math.hypot(r["px"][0] - g["px"][0], r["px"][1] - g["px"][1]) for g in gcps) * mpp
        placed_by_note = "px=" in (lab.get("notes") or "")
        cands = []
        for k, c in enumerate(r["cands"][:3]):
            cc = c["c"]
            px = fit.px(np.array([[cc["lon"], cc["lat"]]]))[0]
            cands.append({**ns.public(cc), "dist_m": round(c["d"], 1), "score": round(c["score"], 2), "shared": c["shared"],
                          "same_kind": c["same_kind"], "px": [round(float(px[0]), 1), round(float(px[1]), 1)],
                          "outline_px": outline_px(cc["geom_ll"], fit, cc["approx"])})
        pool300 = [{**{k: v for k, v in ns.public(rec).items() if k in ("id", "name", "names", "source", "osm", "wikidata",
                                                                          "tasco_ids", "lon", "lat")}, "dist_m": round(d, 1)}
                   for rec, d in pool.near(r["lon"], r["lat"], 300.0)[:200]]
        box = None if placed_by_note or lab.get("global_x") is None else \
            [lab["global_x"], lab["global_y"], lab.get("global_w") or 0, lab.get("global_h") or 0]
        items.append({"id": lab["id"], "category": ns.cat(lab), "text": lab.get("text_corrected") or lab.get("text") or "",
                      "names": r["names"], "px": [round(r["px"][0], 1), round(r["px"][1], 1)], "lon": round(r["lon"], 7),
                      "lat": round(r["lat"], 7), "box": box, "pos_from": "px" if placed_by_note else "box",
                      "in_fit": gd <= IN_FIT_M, "gcp_dist_m": round(gd, 1), "cands": cands, "pool300": pool300})
        all_rows.append({"id": lab["id"], "category": ns.cat(lab), "px": r["px"], "in_fit": gd <= IN_FIT_M, "gcp_dist_m": gd,
                         "text": lab.get("text_corrected") or lab.get("text") or "", "all": [{**ns.public(c["c"]), "d": c["d"], "gcp_m": float(min(shapely.distance(c["c"]["geom_m"], g) for g in gcp_m))}
                                                                                        for c in r["cands"]]})

    blob = ns.blob_hash(ROOT / "work/image-processing/scripts/name_today.py")
    meta = {"map_id": MAP, "built": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "radius_m": a.radius, "pool_radius_m": 300,
            "method": f"name_today@{blob[:8]}+{PLACE_LINK_VERSION}", "name_today_blob": blob,
            "m_per_px": round(mpp, 4), "north_px": [round(float(nv[0]), 5), round(float(nv[1]), 5)], "size": [W, H],
            "fit": str(fit), "transform": "modern_prior.fit_sheet affine over the sheet's 8 GCPs (not the Allmaps helmert)",
            "pool": dict(srcs), "in_fit_m": IN_FIT_M}
    (OUT / "items.json").write_text(json.dumps({"meta": meta, "items": items}, ensure_ascii=False))

    with (OUT / "candidates.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["label_id", "category", "name_on_sheet", "px_x", "px_y", "in_fit", "gcp_dist_m", "rank", "shown_in_top3",
                    "today", "source", "osm_id", "osm_alts", "wikidata", "tasco_ids", "dist_m", "approx_outline", "lon", "lat"])
        for r, rw in zip(rows, all_rows):
            base = [r["lab"]["id"], ns.cat(r["lab"]), " | ".join(r["names"]), round(r["px"][0]), round(r["px"][1]),
                    int(rw["in_fit"]), round(rw["gcp_dist_m"], 1)]
            if not r["cands"]:
                w.writerow(base + ["", "", "", "", "", "", "", "", "", "", ""])
            for k, c in enumerate(r["cands"], 1):
                cc = c["c"]
                w.writerow(base + [k, int(k <= 3), cc["name"], cc["source"], cc["osm"] or "", ";".join(cc["osm_alts"]),
                                   cc["wikidata"] or "", ";".join(map(str, cc["tasco_ids"])), round(c["d"], 1),
                                   int(cc["approx"]), round(cc["lon"], 7), round(cc["lat"], 7)])

    by_text: dict[str, list] = {}
    for rw in all_rows:
        by_text.setdefault(ns.fold(rw["text"]), []).append({**rw, "all": rw["all"]})
    lm = list(csv.DictReader((PRIOR / "landmarks.csv").open()))
    sc = score_landmarks(lm, by_text, None)
    score = {
        "map_id": MAP, "built": meta["built"], "method": meta["method"], "radius_m": a.radius, "transform": meta["transform"],
        "scope": {"rule": "non-rejected; effective category (category_corrected else category) in institution, place, building, legend",
                  "by_category_effective": dict(scope_eff), "by_category_raw": dict(scope_raw),
                  "n_effective": sum(scope_eff.values()), "n_raw": sum(scope_raw.values()),
                  "unplaced_dropped": dict(unplaced), "reviewable_items": len(items),
                  "reviewable_by_category": dict(Counter(i["category"] for i in items)),
                  "in_fit_items": sum(i["in_fit"] for i in items),
                  "items_with_candidate": sum(1 for i in items if i["cands"]),
                  "items_without_candidate": sum(1 for i in items if not i["cands"])},
        "pool": dict(srcs), "predicted": PREDICTED,
        "actual": {"landmark_rows_with_label_matched": sc["matched_label"], "in_fit": len(sc["in_fit"]), "scored_n": sc["n_scored"],
                   "hit1": sc["hit1"], "hit3": sc["hit3"], "no_candidate": sc["no_candidate"]},
        "independent_score": sc,
        "dev_set_note": "The 27 legend_finds picks (1968 map) are DEV: name_today.py --map-id 3a446d85-... --eval prints them as in-sample. Not used here.",
    }
    (OUT / "score.json").write_text(json.dumps(score, indent=1, ensure_ascii=False))
    print(json.dumps({k: score[k] for k in ("scope", "pool", "predicted", "actual")}, indent=1, ensure_ascii=False))
    print("hit@1", sc["hit1_wilson"], " hit@3", sc["hit3_wilson"], " in_fit", sc["in_fit"])
    for r in sc["rows"]:
        print(f"  {r['result']:18} {r['key']:18} rank={r.get('rank')} by={r.get('match_by')} cands={r.get('n_cands')} "
              f"top1={str(r.get('top1'))[:38]!r} status={r['status']}")
    return 0


def self_check() -> int:
    import shapely

    c = {"osm": "way/1", "osm_alts": ["way/2"], "wikidata": "Q9", "names": ["Dinh Độc Lập"]}
    assert truth_hit({"osm_id": "way/2", "wikidata": "", "status": "kept", "name_modern": "x"}, c) == "osm"
    assert truth_hit({"osm_id": "", "wikidata": "Q9", "status": "kept", "name_modern": "x"}, c) == "wikidata"
    assert truth_hit({"osm_id": "", "wikidata": "", "status": "gone", "name_modern": "Dinh Độc Lập (Independence Palace), built 1962"},
                     {**c, "wikidata": None}) == "name"
    assert truth_hit({"osm_id": "way/9", "wikidata": "", "status": "kept", "name_modern": "Dinh Độc Lập"}, c) is None, \
        "a row with an OSM id is matched by id only"
    assert truth_hit({"osm_id": "", "wikidata": "", "status": "gone", "name_modern": "Chợ Bến Thành, the successor"},
                     {**c, "names": ["Chợ Bến Thành"], "wikidata": None}) == "name"
    assert truth_hit({"osm_id": "", "wikidata": "", "status": "gone", "name_modern": "Chợ Bến Thành"},
                     {**c, "names": ["Chợ Cầu Muối"], "wikidata": None}) is None
    assert truth_hit({"osm_id": "", "wikidata": "", "status": "gone", "name_modern": "Chợ Bến Thành"},
                     {**c, "names": ["Trạm Y tế phường Bến Nghé"], "wikidata": None}) is None, "Bến Nghé is not Bến Thành"
    pt = shapely.Point(0, 0)
    assert outline_px(pt, None, False) is None
    rows = [{"key": "a", "status": "kept", "name_1882": "HÔPITAL", "name_modern": "H", "osm_id": "way/1", "wikidata": "",
             "ocr_label_xy": ""},
            {"key": "b", "status": "kept", "name_1882": "ÉGLISE", "name_modern": "E", "osm_id": "way/5", "wikidata": "", "ocr_label_xy": ""},
            {"key": "c", "status": "kept", "name_1882": "MAIRIE", "name_modern": "M", "osm_id": "way/6", "wikidata": "", "ocr_label_xy": ""},
            {"key": "d", "status": "kept", "name_1882": "", "name_modern": "x", "osm_id": "way/7", "wikidata": "", "ocr_label_xy": ""}]
    cand = lambda i: {"osm": f"way/{i}", "osm_alts": [], "wikidata": None, "names": ["n"], "name": "n", "d": i}
    by = {ns.fold("HÔPITAL"): [{"id": "1", "category": "institution", "px": (0, 0), "in_fit": False, "gcp_dist_m": 500, "text": "", "all": [cand(1)]}],
          ns.fold("ÉGLISE"): [{"id": "2", "category": "institution", "px": (0, 0), "in_fit": False, "gcp_dist_m": 500, "text": "", "all": [cand(8), cand(9), cand(5)]}],
          ns.fold("MAIRIE"): [{"id": "3", "category": "institution", "px": (0, 0), "in_fit": True, "gcp_dist_m": 5, "text": "", "all": []}]}
    s = score_landmarks(rows, by, None)
    assert (s["n_scored"], s["hit1"], s["hit3"], s["no_candidate"], s["in_fit"]) == (2, 1, 2, 0, ["c"]), s
    assert s["rows_with_1882_name"] == 3 and s["matched_label"] == 3
    print("place-links build self-check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
