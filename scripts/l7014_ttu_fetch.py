#!/usr/bin/env python3
"""Fetch Texas Tech's copy of an L7014 sheet — the other edition.

PCL publishes one scan per cell and for 25 cells it is a plain JPG with no
georeference; those 25 sit over Saigon, Huế, Đà Nẵng and Hải Phòng, which is
exactly the hole in the mosaic. For most of them a second scan exists and was
always recorded in our own index: `index.geojson`'s `Scanned_map` column points
at the Vietnam Archive at Texas Tech, and PCL is only `Scanned_map_02`.

They are different printings, which is the point. PCL's 6330-4 is a 1984 DMA
recompilation titled THÀNH PHỐ HỒ CHÍ MINH; TTU's is the Vietnamese SÀI GÒN,
"BẢN ĐỒ TIN TỨC NĂM 1965", redrawn and reprinted in 1978 by the Cục Đo đạc và
Bản đồ Nhà nước. Same cell, same series, two different maps.

Two things they are not: georeferenced (plain raster PDF — `gdalinfo` finds no
CRS and no GCPs, so each still needs its corners placed by hand), and large
(3882x3708 at 150 DPI against PCL's 4624x5949).

The old deep links in the index are dead — TTU moved to ArchivesSpace — but the
files are still addressable by sheet number, which is what this script uses.

    python3 scripts/l7014_ttu_fetch.py --jpg-cells      # the 25 PCL could not place
    python3 scripts/l7014_ttu_fetch.py 6330-4 6541-4    # named sheets
    python3 scripts/l7014_ttu_fetch.py --jpg-cells --check   # probe, download nothing
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

WORK = Path("work/l7014")
OUT = WORK / "ttu"
BASE = "https://vva.vietnam.ttu.edu/images.php?img=/maps"
UA = "vma-l7014/1.0 (Vietnam Map Archive; research use)"
PAUSE = 1.5  # ponytail: fixed courtesy delay, no backoff — a 25-file run, once


def sheets_of_kind(kind):
    rows = json.loads((WORK / "sheets.json").read_text())
    return [r["sheet"] for r in rows if r["kind"] == kind]


def fetch(url, dest, check):
    """curl, not urllib: TTU serves its chain without the intermediate, which
    curl walks and Python's ssl (system store or certifi) refuses. Shelling out
    keeps verification on rather than turning it off to get past this."""
    cmd = ["curl", "-sS", "-L", "--max-time", "300", "-A", UA,
           "-w", "%{http_code}"]
    cmd += ["-o", "/dev/null", "-I"] if check else ["-o", str(dest)]
    r = subprocess.run(cmd + [url], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    {r.stderr.strip()}", file=sys.stderr)
        return 0, 0
    code = int(r.stdout.strip()[-3:] or 0)
    return code, (dest.stat().st_size if not check and dest.exists() else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheets", nargs="*", help="sheet numbers, e.g. 6330-4")
    ap.add_argument("--jpg-cells", action="store_true",
                    help="every cell PCL publishes as an ungeoreferenced JPG")
    ap.add_argument("--check", action="store_true", help="probe only")
    args = ap.parse_args()

    want = list(args.sheets)
    if args.jpg_cells:
        want += sheets_of_kind("jpg")
    if not want:
        ap.error("name a sheet or pass --jpg-cells")

    OUT.mkdir(parents=True, exist_ok=True)
    got = missing = skipped = 0
    for sheet in dict.fromkeys(want):
        dest = OUT / f"{sheet}.pdf"
        if dest.exists() and not args.check:
            print(f"  {sheet}  have it ({dest.stat().st_size / 1e6:.1f} MB)")
            skipped += 1
            continue
        code, size = fetch(f"{BASE}/PDF/{sheet}.pdf", dest, args.check)
        if code == 200:
            # A missing sheet can come back as an HTML error page with a 200,
            # so believe the bytes rather than the status.
            if not args.check and not dest.read_bytes().startswith(b"%PDF"):
                dest.unlink()
                print(f"  {sheet}  not a PDF — no TTU copy")
                missing += 1
                continue
            print(f"  {sheet}  ok" + (f"  {size / 1e6:.1f} MB" if size else ""))
            got += 1
        else:
            print(f"  {sheet}  HTTP {code}")
            missing += 1
        time.sleep(PAUSE)

    print(f"\n{got} fetched, {skipped} already here, {missing} missing"
          f"{' (check only)' if args.check else ''} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
