#!/usr/bin/env python3
"""Fill in the six Texas Tech L7014 sheets: bbox and the descriptive columns.

`bulk_upload_local.sh` gives a row a name, a year and a collection. These six
are the second edition of a cell the archive already holds, so the columns that
matter most are the ones that say *which* edition and *whose* paper — otherwise
two rows named for the same sheet number differ only by a diacritic.

The bbox is the cell's, from `corners.csv`, and identical to the PCL twin's:
the two scans are the same 15' x 15' square photographed twice. What differs is
everything else. The producing body is not the series' — three of these were
prepared by the 29th Engineer Battalion with the National Geographic Service in
Đà Lạt, and two are SRV reprints from 1978 — so `creator` is read off each
sheet rather than set once for the collection.

`rights` is where that matters. The AMS-lineage sheets are works of the U.S.
federal government and public domain; the two 1978 reprints are works of a
Vietnamese state body and are not, so they say so instead of claiming it.

    python3 scripts/oneoff/l7014_ttu_metadata.py [--write]
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

WORK = Path("work/l7014")
COLLECTION = "Series L7014 (Vietnam 1:50,000)"
TTU = "https://vva.vietnam.ttu.edu/images.php?img=/maps/PDF/{}.pdf"
HOLDING = ("Vietnam Center and Sam Johnson Vietnam Archive, "
           "Texas Tech University")

US = "29th Engineer Battalion (Base Topographic), U.S. Army, with the "\
     "National Geographic Service, Vietnam"
SRV = "Cục Đo đạc và Bản đồ Nhà nước"

PD = "Public domain — a work of the U.S. federal government."
# Not ours to declare. A 1978 reprint by a Vietnamese state body is outside the
# U.S. federal-works rule the rest of this series relies on.
UNKNOWN = "Rights not determined — a 1978 reprint by a Vietnamese state body."

SHEETS = {
    "6329-1": {"title": "CẦN GIỜ", "edition": "2-AMS (29 ETB)", "creator": US,
               "printing": "Printed by 29th Engr Bn (BT) 12-68; prepared 1968",
               "rights": PD},
    "6329-4": {"title": "GÒ CÔNG", "edition": "1-AMS", "creator": US,
               # The lower-left collar is torn away in this scan, which is where
               # the credits block and its year would be.
               "printing": None, "rights": PD},
    "6330-1": {"title": "BIÊN HÒA", "edition": "4", "creator": SRV,
               "printing": "Vẽ và in lại năm 1978 tại Cục Đo đạc và Bản đồ "
                           "Nhà nước; bản đồ tin tức năm 1969",
               "rights": UNKNOWN},
    "6330-2": {"title": "NHƠN TRẠCH", "edition": "3-TPC (29 ETB)", "creator": US,
               "printing": "Printed by 29th Engr Bn (BT) 12-70; prepared 1970",
               "rights": PD},
    "6330-3": {"title": "CẦN GIUỘC", "edition": "3-TPC (29 ETB)", "creator": US,
               "printing": "Printed by 29th Engr Bn (BT) 5-71; prepared 1970",
               "rights": PD},
    "6330-4": {"title": "SÀI GÒN", "edition": "3", "creator": SRV,
               "printing": "Vẽ và in lại năm 1978 tại Cục Đo đạc và Bản đồ "
                           "Nhà nước; bản đồ tin tức năm 1965",
               "rights": UNKNOWN},
}


def env():
    out = {}
    for line in Path(".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out["PUBLIC_SUPABASE_URL"].rstrip("/"), out["SUPABASE_SERVICE_KEY"]


def req(url, key, method="GET", body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, method=method)
    for k, v in (("apikey", key), ("Authorization", f"Bearer {key}"),
                 ("User-Agent", "vma-l7014/1.0")):
        r.add_header(k, v)
    if data:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as f:
        raw = f.read()
    return json.loads(raw) if raw and raw[:1] in b"[{" else raw


def cell_bbox():
    """[minLon, minLat, maxLon, maxLat] per sheet, from the graticule corners."""
    out = {}
    for line in (WORK / "corners.csv").read_text().splitlines()[1:]:
        parts = line.rsplit(",", 3)
        if len(parts) != 4:
            continue
        sheet = parts[0].split(",")[0]
        lon, lat = float(parts[2]), float(parts[3])
        b = out.setdefault(sheet, [lon, lat, lon, lat])
        b[0], b[1] = min(b[0], lon), min(b[1], lat)
        b[2], b[3] = max(b[2], lon), max(b[3], lat)
    return {k: [round(v, 6) for v in b] for k, b in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    base, key = env()
    bboxes = cell_bbox()

    q = urllib.parse.quote(COLLECTION, safe="")
    rows = req(f"{base}/rest/v1/maps?select=id,name,year,extra_metadata"
               f"&collection=eq.{q}", key)

    n = 0
    for m in rows:
        name = m["name"] or ""
        if ", ed." not in name:          # the PCL twin, not ours
            continue
        sheet = next((s for s in SHEETS if f"L7014 {s}" in name), None)
        if not sheet:
            print(f"  ? unrecognised: {name}", file=sys.stderr)
            continue
        s = SHEETS[sheet]
        extra = dict(m.get("extra_metadata") or {})
        extra.update({"sheet_number": sheet, "series": "L7014",
                      "edition": s["edition"], "source_archive": "TTU"})
        if s["printing"]:
            extra["printing"] = s["printing"]
        patch = {
            "bbox": bboxes.get(sheet),
            "creator": s["creator"],
            "dc_publisher": s["creator"],
            "holding_institution": HOLDING,
            "source_url": TTU.format(sheet),
            "rights": s["rights"],
            "physical_description": "Topographic sheet, 1:50,000, Series L7014.",
            "shelfmark": f"Series L7014, Sheet {sheet}, edition {s['edition']}",
            "map_type": "topographic",
            "original_title": s["title"],
            "extra_metadata": extra,
        }
        patch = {k: v for k, v in patch.items() if v is not None}
        print(f"  {sheet}  {name}")
        if args.write:
            req(f"{base}/rest/v1/maps?id=eq.{m['id']}", key, "PATCH", patch)
        n += 1

    print(f"\n{n} of {len(SHEETS)} sheets {'updated' if args.write else '(dry run)'}")
    return 0 if n == len(SHEETS) else 1


if __name__ == "__main__":
    sys.exit(main())
