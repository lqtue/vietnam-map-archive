#!/usr/bin/env python3
"""Neatline corners for the L7014 sheets with no georeference of their own, read by eye and snapped by line.

The 62 NOGEO sheets (and the autoplace failures) have nothing to go on but the printed frame. A person
read each one off a 1200-px preview (ROUGH: left, right, top, bottom of the neatline, +-6 px); this snaps
each side to the strongest rule within +-15 px (of 2000) and fits it as a line through six windows
(l7014_neatline_profile.py). The result is only as good as the check against the cell it claims to be:
the width/height of the snapped quad must match the cell's within 3 per cent.

Ground. Almost every sheet is the 15' lattice cell. Nine on the Chinese border (PRINTED) are 10' tall,
which the lattice does not know -- found because their detected aspect was 1.38, not 0.93, and the
printed corner labels agree: e.g. 5454-1 runs 102 15' E / 22 50' N to 102 30' / 22 40'. Those labels are
Indian 1960 graticule, so they take the same datum shift as `l7014_mosaic.cell_corners`.

    python3 scripts/l7014_hand_corners.py     # -> work/l7014/regen/hand-corners.json
"""
import json
import math
import sys
from pathlib import Path

from osgeo import osr

sys.path.insert(0, str(Path(__file__).parent))
import l7014_autoplace as A  # noqa: E402
import l7014_neatline_profile as P  # noqa: E402

OUT = A.REGEN / "hand-corners.json"
ASPECT_TOL = 0.03

ROUGH = {
    '5454-1': [222, 1147, 60, 731],
    '5554-4': [65, 1135, 71, 840],
    '5654-1': [58, 1050, 95, 808],
    '5654-3': [68, 1070, 70, 790],
    '5728-1': [30, 1160, 52, 1192],
    '5729-1': [22, 1172, 62, 1222],
    '5729-2': [27, 1172, 45, 1212],
    '5750-2': [28, 1072, 50, 1160],
    '5754-2': [52, 1045, 72, 785],
    '5754-4': [55, 1065, 72, 800],
    '5853-1': [68, 1072, 60, 1135],
    '5854-4': [60, 1065, 82, 808],
    '5926-2': [165, 1133, 42, 745],
    '5929-4': [28, 1095, 80, 1118],
    '5949-3': [271, 1165, 53, 1000],
    '6030-1': [27, 1170, 48, 1208],
    '6030-3': [27, 1170, 48, 1205],
    '6030-4': [27, 1170, 48, 1205],
    '6130-1': [30, 1172, 62, 1215],
    '6130-4': [28, 1170, 50, 1198],
    '6131-3': [62, 1175, 62, 1180],
    '6146-2': [45, 1142, 48, 1122],
    '6147-1': [47, 1143, 45, 1190],
    '6148-4': [185, 1105, 33, 985],
    '6155-2': [195, 1148, 73, 738],
    '6155-3': [213, 1145, 85, 765],
    '6230-4': [27, 1170, 52, 1205],
    '6232-3': [27, 1170, 52, 1205],
    '6243-3': [195, 1168, 45, 1065],
    '6326-3': [150, 1092, 40, 985],
    '6342-1': [200, 1170, 47, 1060],
    '6433-1': [178, 1170, 47, 1058],
    '6433-4': [177, 1165, 45, 1050],
    '6434-1': [172, 1100, 48, 990],
    '6436-1': [170, 1160, 60, 1072],
    '6438-1': [52, 1150, 122, 1255],
    '6439-1': [182, 1168, 40, 1052],
    '6440-3': [55, 1155, 62, 1185],
    '6441-3': [192, 1172, 42, 1052],
    '6534-4': [28, 1170, 52, 1200],
    '6535-3': [36, 1105, 62, 1145],
    '6550-1': [55, 1146, 47, 1205],
    '6550-4': [55, 1145, 47, 1198],
    '6551-2': [57, 1140, 45, 1200],
    '6636-4': [28, 1165, 62, 1207],
    '6731-1': [28, 1172, 62, 1215],
    '6833-2': [22, 1145, 42, 1203],
    '6836-1': [43, 1148, 60, 1195]
}

# (lon deg, min), (lat deg, min) of the NW corner, then of the SE corner, as printed. Indian 1960 graticule.
PRINTED = {
    "5454-1": ((102, 15), (22, 50), (102, 30), (22, 40)),
    "5554-4": ((102, 30), (22, 50), (102, 45), (22, 40)),
    "5654-1": ((103, 15), (22, 50), (103, 30), (22, 40)),
    "5654-3": ((103, 0), (22, 40), (103, 15), (22, 30)),
    "5754-2": ((103, 45), (22, 40), (104, 0), (22, 30)),
    "5754-4": ((103, 30), (22, 50), (103, 45), (22, 40)),
    "5854-4": ((104, 0), (22, 50), (104, 15), (22, 40)),
    "6155-2": ((105, 45), (23, 10), (106, 0), (23, 0)),
    "6155-3": ((105, 30), (23, 10), (105, 45), (23, 0)),
}


def printed_ground(sheet):
    (lw, lnw), (la, lan), (le, lne), (ls, lsn) = PRINTED[sheet]
    w, n = lw + lnw / 60, la + lan / 60
    e, s = le + lne / 60, ls + lsn / 60
    t = osr.CoordinateTransformation(A.M.indian_1960_geog(), A.M.wgs84())
    return [list(t.TransformPoint(x, y)[:2]) for x, y in ((w, n), (e, n), (e, s), (w, s))]


def main(only=None):
    cells = A.lattice_cells()
    rows = {r["sheet"]: r for r in A.M.load_sheets() if r["kind"] == "pdf"}
    out = {}
    for s, rough in sorted(ROUGH.items()):
        if only and s not in only:
            continue
        pdf = A.WORK / "pdfs" / (Path(rows[s]["file"]).stem.strip() + ".pdf")
        ground = printed_ground(s) if s in PRINTED else cells[s]
        # the aspect the sheet must have, from the ground it is being fitted to
        mid = sum(y for _, y in ground) / 4
        expect = ((ground[1][0] - ground[0][0]) * math.cos(math.radians(mid)) * 111320
                  / ((ground[0][1] - ground[3][1]) * 110540))
        r = P.find(pdf, expect, rough, search=bool(only))
        c = r["corners"]
        w = ((c["NE"][0] - c["NW"][0]) + (c["SE"][0] - c["SW"][0])) / 2
        h = ((c["SW"][1] - c["NW"][1]) + (c["SE"][1] - c["NE"][1])) / 2
        err = abs(w / h - expect) / expect
        out[s] = {"corners": {k: [float(x) for x in v] for k, v in c.items()}, "size": r["size"], "ground": ground,
                  "ground_from": "printed" if s in PRINTED else "lattice",
                  "aspect_err_pct": round(float(100 * err), 2), "wobble_px": float(r["wobble_px"]), "ok": bool(err <= ASPECT_TOL)}
        print(f"{s} {out[s]['ground_from']:8} aspect err {100 * err:5.2f}%  wobble {r['wobble_px']:5.1f}px  "
              f"{'' if err <= ASPECT_TOL else 'REFUSED'}", flush=True)
    if only:  # a re-run of the refused few: merge, do not replace
        out = {**json.loads(OUT.read_text()), **out}
    OUT.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
