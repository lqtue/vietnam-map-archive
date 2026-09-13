#!/usr/bin/env python3
"""Correct the nine L7014 city sheets' years, read off each sheet's own collar.

`l7014_city_metadata.py` took `year` from `work/l7014/index.geojson`, whose
`Year` column is the cell's, not the scan's. For six of the nine cells PCL
publishes a 1960s AMS printing and the index agrees; for the other three PCL
publishes a 1980s **Defense Mapping Agency** recompilation of the same sheet
number, and the index's year is a different piece of paper. 6330-4 is the one
that shows: a 1984 DMA sheet titled THÀNH PHỐ HỒ CHÍ MINH, filed under 1965.

The years below were read off each scan in `work/l7014/jpgs/` — "MAP
INFORMATION AS OF <year>" on the AMS sheets, "COMPILED IN <year> FROM BEST
AVAILABLE SOURCE" on the DMA ones. Both are the content date, which is what a
reader of a topographic sheet means by its year; the print date differs and is
recorded separately where the sheet states it.

`extra_metadata.edition` held that same index year, which is not an edition.
The DMA sheets print theirs (EDITION 5-DMA); the AMS ones print it in the lower
margin, below where PCL's scan stops, so it stays null rather than wrong.

    python3 scripts/oneoff/l7014_city_years.py [--write]
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# sheet -> (content year, edition as printed or None, printing note or None)
SHEETS = {
    "6330-1": (1969, None, None),
    "6330-2": (1969, None, None),
    "6330-3": (1970, None, None),
    "6329-1": (1983, "3-DMA", None),
    "6329-4": (1967, None, None),
    "6541-4": (1968, None, None),
    "6641-3": (1984, "4-DMA", None),
    "6350-4": (1966, None, None),
    "6330-4": (1984, "5-DMA", "Reprinted by NIMA 12-99"),
}

# 6330-4 alone needs its name fixed: the scan is a 1984 sheet and prints the
# post-1976 name, so the record should too. `location` stays Saigon — that is
# the gazetteer entry the rest of the archive groups under.
RENAME = {
    "6330-4": {
        "name": "Thành phố Hồ Chí Minh (L7014 6330-4)",
        "original_title": "THÀNH PHỐ HỒ CHÍ MINH (HO CHI MINH CITY)",
    },
}

COLLECTION = "Series L7014 (Vietnam 1:50,000)"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    base, key = env()

    q = urllib.parse.quote(COLLECTION, safe="")
    rows = req(f"{base}/rest/v1/maps?select=id,name,year,extra_metadata"
               f"&collection=eq.{q}", key)

    n = 0
    for m in rows:
        sheet = (m.get("extra_metadata") or {}).get("sheet_number")
        if sheet not in SHEETS:
            continue
        year, edition, printing = SHEETS[sheet]
        extra = dict(m.get("extra_metadata") or {})
        extra["edition"] = edition          # was the index year; null beats wrong
        if printing:
            extra["printing"] = printing
        patch = {"year": year, "extra_metadata": extra}
        patch.update(RENAME.get(sheet, {}))

        was = m["year"]
        mark = "  " if was == year else "->"
        print(f"{mark} {sheet}  {was} -> {year}"
              f"{'  ed ' + edition if edition else ''}")
        if args.write:
            req(f"{base}/rest/v1/maps?id=eq.{m['id']}", key, "PATCH", patch)
        n += 1

    if n != len(SHEETS):
        print(f"\nmatched {n} of {len(SHEETS)} sheets", file=sys.stderr)
        return 1
    print(f"\n{n} sheets {'updated' if args.write else '(dry run)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
