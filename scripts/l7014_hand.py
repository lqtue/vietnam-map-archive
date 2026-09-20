#!/usr/bin/env python3
"""Splice the hand-georeferenced JPG sheets into a mosaic manifest.

    python3 scripts/l7014_hand.py --key l7014-faulty   # -> l7014-faulty-hand
    python3 scripts/l7014_hand.py --self-check

The 24 hand sheets are separate `maps` rows, not COGs, so `manifest` never
sees them and every seam in a plain census is `pdf / pdf`.  Their footprint in
the archive is their georeference's ground quad -- `maps.bbox` is derived from
it, and agrees with what this reads to under 0.1 m on the 15 sheets whose
georeference is still the `.points` file (the 9 with an Allmaps annotation
differ by 3-13 m, which is the nudge the annotation records).

Read the seams this makes with the source of that ground in mind: `corners`
writes the lattice cell as the ground half of each control point, so a hand
sheet is on the lattice by construction.  A hand/pdf seam therefore measures
the pdf sheet's displacement from its cell.  It is not a free seam.
"""

import argparse
import json
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from l7014_mosaic import BUILD, CITY, GCP_DIR, MANIFEST_PROPS, PINS, load_gcps, load_sheets


def ground_quad(gcp):
    """The four ground corners of a hand georeference, in mask order.

    Every annotation in this series masks the sheet with the same four pixels
    it controls on, so the quad is the control points' own ground and needs no
    transform.  A richer mask would; this refuses rather than approximate one.
    """
    pts = gcp["pts"]
    if gcp.get("ground_quad"):
        return list(gcp["ground_quad"])
    mask = gcp.get("mask")
    if mask:
        by_pixel = {(round(px), round(py)): (lon, lat) for px, py, lon, lat in pts}
        quad = [by_pixel.get((round(px), round(py))) for px, py in mask]
        if len(mask) != 4 or None in quad:
            raise ValueError(f"{gcp['src']}: {len(mask)}-point mask is not the control points "
                             f"-- warp the sheet and take its outline from the COG instead")
        return quad
    if len(pts) != 4:
        raise ValueError(f"{gcp['src']}: {len(pts)} control points and no mask")
    return [(lon, lat) for _, _, lon, lat in pts]


def hand_features(rows, pins):
    features, skipped = [], []
    for row in sorted(rows, key=lambda r: r["sheet"]):
        gcp = load_gcps(row["sheet"], pins)
        if not gcp:
            skipped.append(f"{row['sheet']}: no control points")
            continue
        try:
            quad = ground_quad(gcp)
        except ValueError as e:
            skipped.append(str(e))
            continue
        ring = [[round(lon, 5), round(lat, 5)] for lon, lat in quad]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring + [ring[0]]]},
            "properties": {k: row.get(k) for k in MANIFEST_PROPS},
        })
    return features, skipped


def self_check():
    gcp = {"pts": [(0, 0, 106.0, 10.1), (100, 0, 106.1, 10.1),
                   (100, 100, 106.1, 10.0), (0, 100, 106.0, 10.0)],
           "mask": [(0, 0), (100, 0), (100, 100), (0, 100)], "src": "synthetic"}
    assert ground_quad(gcp) == [(106.0, 10.1), (106.1, 10.1), (106.1, 10.0), (106.0, 10.0)]
    # Mask order, not control-point order: a quad read in the wrong order is a
    # bowtie, and a bowtie's nearest-segment distance is not a seam.
    shuffled = dict(gcp, mask=[(0, 100), (100, 100), (100, 0), (0, 0)])
    assert ground_quad(shuffled) == [(106.0, 10.0), (106.1, 10.0), (106.1, 10.1), (106.0, 10.1)]
    del gcp["mask"]
    assert ground_quad(gcp)[0] == (106.0, 10.1)
    for bad in ({"pts": gcp["pts"], "mask": [(0, 0), (50, 0), (100, 0), (100, 100), (0, 100)],
                 "src": "x"},
                {"pts": gcp["pts"][:3], "src": "x"}):
        try:
            ground_quad(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad}")
    print("self-check: mask order wins, control-point order is the fallback")
    print("self-check: a mask that is not the control points is refused")
    print("self-check: ok")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", default="l7014-faulty", help="manifest key under work/l7014/build")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        return self_check()

    base = BUILD / f"{args.key}.geojson"
    if not base.exists():
        sys.exit(f"{base} missing -- run `l7014_mosaic.py manifest --key {args.key}` first")
    manifest = json.loads(base.read_text())
    have = {f["properties"]["sheet"] for f in manifest["features"]}
    pins = json.loads(PINS.read_text()) if PINS.exists() else {}
    rows = [r for r in load_sheets() if r["kind"] == "jpg" and r["sheet"] not in have]
    features, skipped = hand_features(rows, pins)

    manifest["features"].extend(features)
    out = BUILD / f"{args.key}-hand.geojson"
    out.write_text(json.dumps(manifest, separators=(",", ":")))
    print(f"hand: {len(features)} hand sheets + {len(have)} warped -> {out}")
    print(f"  ({len(CITY)} city sheets are in the series index; they are hand sheets too)")
    for msg in skipped:
        print(f"  SKIP {msg}")


if __name__ == "__main__":
    main()
