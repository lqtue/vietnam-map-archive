#!/usr/bin/env python3
"""clean_blocks.py — geometry + class hygiene on a sheet's colour-block seg output.

Three rules, all reversible (nothing is edited in place):

  1. drop  — centroid outside the layout pass's `map_content_bbox` (margin,
             title cartouche, legend: not map body)
  2. drop  — exact duplicate exterior ring
  3. drop  — bbox spanning more than --frame-span of the map body in BOTH axes:
             the neatline, traced as a block because it is a closed ink loop
  4. flag  — `source_class: building` above --building-max px^2. On both sheets
             the building median is ~800-950 px^2 and 1882's largest genuine
             building is 98 722; anything far past that is a mis-classed wash.
             Reclassed to land_plot, with class_orig + class_source kept so the
             call can be audited or undone.

  python3 work/ocr/scripts/clean_blocks.py --sheet all
  python3 work/ocr/scripts/clean_blocks.py --self-check

ponytail: shoelace area on the exterior ring, no shapely. Holes are carried
through untouched -- they are a queue problem (see audit.json), not a cleaning
one. Slivers are NOT dropped: upstream already floors at ~100 px^2.
"""
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
SHEETS = {
    "1882": ("work/ocr/outputs/0e02b9d9-9d40-4cca-8e41-8c8373d54d3b/colour-20260919-normalized/blocks.normalized.geojson",
             "work/ocr/outputs/0e02b9d9-9d40-4cca-8e41-8c8373d54d3b/runs/layout-2026-09-05T1523-0e02b9d9/scout.json"),
    "1898": ("work/ocr/outputs/20ec4f9a-16bd-4895-a593-40c6ed9c9555/colour-1898-20260919-normalized/blocks.normalized.geojson",
             "work/ocr/outputs/20ec4f9a-16bd-4895-a593-40c6ed9c9555/runs/layout-2026-09-05T1523-20ec4f9a/scout.json"),
}


def exteriors(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [p[0] for p in geom["coordinates"]]
    return []


def centroid(geom):
    pts = [c for r in exteriors(geom) for c in r]
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def area(ring):
    """Shoelace, absolute."""
    s = sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
            for i in range(len(ring) - 1))
    return abs(s) / 2


def clean(features, bbox, building_max, frame_span=0.6):
    x0, y0, x1, y1 = bbox
    assert x1 > x0 and y1 > y0, f"map_content_bbox is not x0,y0,x1,y1: {bbox}"
    kept, seen = [], set()
    log = {"outside_bbox": [], "duplicate": [], "neatline": [], "reclassed": []}
    for f in features:
        p = f["properties"]
        ref = p.get("source_index", len(kept))
        cx, cy = centroid(f["geometry"])
        if not (x0 <= cx <= x1 and y0 <= cy <= y1):
            log["outside_bbox"].append(ref)
            continue
        xs = [c[0] for r in exteriors(f["geometry"]) for c in r]
        ys = [c[1] for r in exteriors(f["geometry"]) for c in r]
        if (max(xs) - min(xs) > frame_span * (x1 - x0)
                and max(ys) - min(ys) > frame_span * (y1 - y0)):
            log["neatline"].append(ref)
            continue
        key = tuple(tuple(c) for r in exteriors(f["geometry"]) for c in r)
        if key in seen:
            log["duplicate"].append(ref)
            continue
        seen.add(key)
        a = p.get("area_px") or sum(area(r) for r in exteriors(f["geometry"]))
        if p.get("source_class") == "building" and a > building_max:
            p["class_orig"] = "building"
            p["class_source"] = "size_rule"
            p["feature_type"] = "land_plot"
            log["reclassed"].append({"source_index": ref, "area_px": round(a, 1)})
        kept.append(f)
    return kept, log


def run(tag, blocks_rel, scout_rel, building_max):
    src = ROOT / blocks_rel
    feats = json.loads(src.read_text())["features"]
    bbox = json.loads((ROOT / scout_rel).read_text())["map_content_bbox"]
    kept, log = clean(feats, bbox, building_max)
    out = src.with_name("blocks.clean.geojson")
    out.write_text(json.dumps({"type": "FeatureCollection", "features": kept},
                              separators=(",", ":")))
    audit = {"sheet": tag, "source": blocks_rel, "map_content_bbox": bbox,
             "building_max_px": building_max, "in": len(feats), "out": len(kept), **log}
    out.with_name("clean_audit.json").write_text(json.dumps(audit, indent=2))
    print(f"{tag}: {len(feats)} -> {len(kept)}  "
          f"(outside {len(log['outside_bbox'])}, dup {len(log['duplicate'])}, "
          f"neatline {len(log['neatline'])}, "
          f"reclassed {len(log['reclassed'])})  -> {out.relative_to(ROOT)}")


def self_check():
    sq = lambda x, y, s: {"type": "Feature", "properties": {"source_class": "building", "area_px": s * s, "source_index": f"{x},{y}"},
                          "geometry": {"type": "Polygon", "coordinates": [[[x, y], [x + s, y], [x + s, y + s], [x, y + s], [x, y]]]}}
    inside, outside, dup, big = sq(10, 10, 5), sq(900, 900, 5), sq(10, 10, 5), sq(20, 20, 40)
    frame = sq(5, 5, 90)
    kept, log = clean([inside, outside, dup, big, frame], [0, 0, 100, 100], building_max=1000)
    assert [f["properties"]["source_index"] for f in kept] == ["10,10", "20,20"], kept
    assert log["outside_bbox"] == ["900,900"] and log["duplicate"] == ["10,10"]
    assert log["neatline"] == ["5,5"]
    assert kept[1]["properties"]["feature_type"] == "land_plot"
    assert kept[1]["properties"]["class_orig"] == "building"
    assert area([[0, 0], [4, 0], [4, 3], [0, 3], [0, 0]]) == 12
    print("self-check ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", choices=[*SHEETS, "all"], default="all")
    ap.add_argument("--building-max", type=float, default=100_000)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        self_check(); sys.exit()
    for tag in (SHEETS if a.sheet == "all" else [a.sheet]):
        run(tag, *SHEETS[tag], a.building_max)
