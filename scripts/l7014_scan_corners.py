#!/usr/bin/env python3
"""Neatline corners for the 15 L7014 sheets PCL published as plain JPG scans (no georeference).

Same detector as the GeoPDFs (`l7014_neatline_profile.find`, which reads any GDAL raster), fitted
to the lattice cell's own aspect. Merges into `work/l7014/regen/hand-corners.json`, which
`l7014_annotate_pdf.py --hand` reads; a sheet whose shape is more than 3% off its cell is marked
not ok and left unplaced.

    python3 scripts/l7014_scan_corners.py            # the 15
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import l7014_autoplace as A  # noqa: E402
import l7014_neatline_profile as P  # noqa: E402

JPGS = Path("/Users/airm1/Work/Maps/l7014/jpgs")
SHEETS = ["6150-2", "6150-3", "6150-4", "6151-1", "6151-4", "6329-2", "6329-3", "6350-1",
          "6350-2", "6350-3", "6541-1", "6541-2", "6541-3", "6641-2", "6641-4"]
TOL = 0.03
# The neatline read off a 1200-px preview (left, right, top, bottom, +-10 px) for the scans the
# unaided detector took a grid line or the collar for; `find` then snaps each side to the nearest rule.
ROUGH = {
    "6150-2": (70, 1147, 58, 1210), "6150-3": (72, 1147, 66, 1178), "6151-1": (68, 1140, 75, 1205),
    "6151-4": (78, 1143, 68, 1182), "6350-1": (72, 1143, 62, 1190), "6350-2": (72, 1143, 60, 1210),
    "6350-3": (70, 1145, 72, 1205), "6541-3": (70, 1146, 72, 1175), "6641-2": (58, 1148, 70, 1195),
    "6641-4": (66, 1150, 70, 1187),
}


def main():
    cells = A.lattice_cells()
    out_path = A.REGEN / "hand-corners.json"
    out = json.loads(out_path.read_text())
    for s in SHEETS:
        ground = cells[s]
        mid = sum(y for _, y in ground) / 4
        expect = ((ground[1][0] - ground[0][0]) * math.cos(math.radians(mid)) * 111320
                  / ((ground[0][1] - ground[3][1]) * 110540))
        jpg = JPGS / f"txu-pclmaps-oclc-21713238-{s}.jpg"
        try:
            r = P.find(jpg, expect, ROUGH.get(s), search=s in ROUGH)
        except Exception as e:  # noqa: BLE001
            print(s, "ERROR", str(e)[:80]); continue
        c = r["corners"]
        w = ((c["NE"][0] - c["NW"][0]) + (c["SE"][0] - c["SW"][0])) / 2
        h = ((c["SW"][1] - c["NW"][1]) + (c["SE"][1] - c["NE"][1])) / 2
        err = abs(w / h - expect) / expect
        ok = bool(err <= TOL and r["quad_ok"])
        out[s] = {"corners": {k: [float(x) for x in v] for k, v in c.items()}, "size": r["size"], "ground": ground,
                  "ground_from": "lattice", "aspect_err_pct": round(float(100 * err), 2),
                  "wobble_px": float(r["wobble_px"]), "ok": ok}
        print(f"{s} aspect err {100 * err:5.2f}%  wobble {r['wobble_px']:5.1f}px  quad_ok={r['quad_ok']}  {'' if ok else 'REFUSED'}", flush=True)
    out_path.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
