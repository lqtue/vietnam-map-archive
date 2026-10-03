"""QGIS bridge for tracing the river_ref windows. Stdlib only.

  qgis.py prep          write crops/<sheet>-<id>.pgw so QGIS places each crop at its source pixels
  qgis.py import DIR    read DIR/1882.geojson and DIR/1898.geojson (one polygon layer per sheet,
                        text field `class` = water|block|ignore), file each feature under every window
                        of its layer (water -> water windows, block -> road windows, ignore -> both)
                        whose box its bbox overlaps, flip y back, write traces/<sheet>-<id>.geojson
                        with "reviewed": true. A window with no features is left untouched unless
                        named in --dry a,b (reviewed all-land: the dry controls).

The pgw has y negated (QGIS's engineering CRS is y-up, source pixels are y-down); import flips back.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
W = json.loads((HERE / "windows.json").read_text())["windows"]


def prep():
    for w in W:
        x, y, _, _ = w["box"]
        # ponytail: pgw refers to the upper-left pixel centre; half-pixel offset ignored, < 1 px
        (HERE / "crops" / f"{w['sheet']}-{w['id']}.pgw").write_text(f"1\n0\n0\n-1\n{x}\n{-y}\n")
    print(f"wrote {len(W)} .pgw files")
    # window outlines in the same x, -y frame, to trace on the whole sheet instead of the crops
    for sheet in {w["sheet"] for w in W}:
        feats = [{"type": "Feature", "properties": {k: w.get(k, "water") for k in ("id", "layer", "case", "split")},
                  "geometry": {"type": "Polygon", "coordinates": [[[x, -y], [x + bw, -y], [x + bw, -y - bh],
                                                                   [x, -y - bh], [x, -y]]]}}
                 for w in W if w["sheet"] == sheet for x, y, bw, bh in [w["box"]]]
        (HERE / "crops" / f"windows-{sheet}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    print("wrote crops/windows-<sheet>.geojson")


def flip(g):
    f = lambda ring: [[x, -y] for x, y in (p[:2] for p in ring)]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return [[f(r) for r in p] for p in polys]


LAYER = {"water": {"water"}, "block": {"road"}, "ignore": {"water", "road"}}


def overlaps(ring, box):
    # ponytail: bbox test; a near-miss lands as an empty clip, which the scorer ignores
    x, y, w, h = box
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    return min(xs) < x + w and max(xs) > x and min(ys) < y + h and max(ys) > y


def do_import(d, only):
    for sheet in ("1882", "1898"):
        src = Path(d) / f"{sheet}.geojson"
        feats = json.loads(src.read_text())["features"] if src.exists() else []
        out = {w["id"]: [] for w in W if w["sheet"] == sheet}
        for ft in feats:
            cls = ft["properties"].get("class")
            if cls not in LAYER:
                sys.exit(f"{sheet}: feature without class water|block|ignore: {ft['properties']}")
            for poly in flip(ft["geometry"]):
                hit = [w["id"] for w in W if w["sheet"] == sheet and w.get("layer", "water") in LAYER[cls]
                       and overlaps(poly[0], w["box"])]
                if not hit:
                    sys.exit(f"{sheet}: {cls} polygon near {poly[0][0]} overlaps no window of its layer")
                for wid in hit:
                    out[wid].append({"type": "Feature", "properties": {"class": cls},
                                     "geometry": {"type": "Polygon", "coordinates": poly}})
        for wid, fs in out.items():
            if not fs and wid not in only:
                continue  # untraced stays untouched; an all-land window must be named in --dry
            p = HERE / "traces" / f"{sheet}-{wid}.geojson"
            p.write_text(json.dumps({"type": "FeatureCollection", "reviewed": True, "features": fs}))
            print(f"{sheet}-{wid}: {len(fs)} polygons")


def selfcheck():
    g = {"type": "Polygon", "coordinates": [[[1, -2], [3, -2], [3, -5], [1, -2]]]}
    assert flip(g) == [[[[1, 2], [3, 2], [3, 5], [1, 2]]]]
    sq = [[8, 8], [20, 8], [20, 20], [8, 20], [8, 8]]                  # crosses the window edge
    assert overlaps(sq, [0, 0, 10, 10]) and not overlaps(sq, [30, 0, 10, 10])
    print("selfcheck ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["prep"]:
        prep()
    elif a[:1] == ["import"] and len(a) >= 2:
        do_import(a[1], set(a[a.index("--dry") + 1].split(",")) if "--dry" in a else set())
    elif a[:1] == ["selfcheck"]:
        selfcheck()
    else:
        sys.exit(__doc__)
