#!/usr/bin/env python3
"""Neatline corners for TTU's L7014 scans, fitted to each sheet's lattice cell.

Same two steps as `l7014_scan_corners.py` / `l7014_scan_refine.py` (profile detector, then a per-side
RANSAC), on TTU's own images. Writes `work/l7014/regen/ttu-corners.json`, which
`l7014_annotate_pdf.py --hand --archive TTU --corners ttu-corners.json` reads. A sheet is `ok` when its
shape is within 3% of the cell and its corners fit a parallelogram to 80 m; the rest need a person.

    python3 scripts/l7014_ttu_corners.py [SHEET ...]
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import l7014_autoplace as A  # noqa: E402
import l7014_neatline_profile as P  # noqa: E402
import l7014_scan_refine as R  # noqa: E402
from l7014_hand_corners import PRINTED, printed_ground  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
NATIVE = Path("/Users/airm1/Work/Maps/l7014/ttu/native")
OUT = A.REGEN / "ttu-corners.json"
TOL, FIT = 0.03, 80.0


def main(only):
    cells = A.lattice_cells()
    sheets = [l.split("\t")[3] for l in Path("work/l7014/ttu-ingest.txt").read_text().splitlines()]
    sheets = [json.loads(x)["sheet_number"] for x in sheets]
    out = json.loads(OUT.read_text()) if OUT.exists() and only else {}
    for s in sheets:
        if only and s not in only:
            continue
        jpg = NATIVE / f"{s}-000.jpg"
        ground = printed_ground(s) if s in PRINTED else cells[s]
        mid = sum(y for _, y in ground) / 4
        expect = ((ground[1][0] - ground[0][0]) * math.cos(math.radians(mid)) * 111320
                  / ((ground[0][1] - ground[3][1]) * 110540))
        try:
            r = P.find(jpg, expect)
            rec = {"corners": r["corners"], "ground": ground}
            new, votes = R.refine(s, rec, jpg)
            if R.fit_m(new, ground) < R.fit_m(rec["corners"], ground):
                rec["corners"] = new
            c = rec["corners"]
            w = ((c["NE"][0] - c["NW"][0]) + (c["SE"][0] - c["SW"][0])) / 2
            h = ((c["SW"][1] - c["NW"][1]) + (c["SE"][1] - c["NE"][1])) / 2
            err, fit = abs(w / h - expect) / expect, R.fit_m(c, ground)
            W, H = Image.open(jpg).size
            out[s] = {"corners": {k: [float(x) for x in v] for k, v in c.items()}, "size": [W, H], "ground": ground,
                      "ground_from": "printed" if s in PRINTED else "lattice", "aspect_err_pct": round(100 * err, 2),
                      "fit_m": round(fit, 1), "wobble_px": float(r["wobble_px"]), "ok": bool(err <= TOL and fit <= FIT)}
            print(f"{s} aspect {100 * err:5.2f}%  fit {fit:6.1f} m  {'' if out[s]['ok'] else 'NEEDS EYES'}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(s, "ERROR", str(e)[:80], flush=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(sum(1 for v in out.values() if v["ok"]), "of", len(out), "ok ->", OUT)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
