#!/usr/bin/env python3
"""Fill in the nine L7014 city sheets: bbox and the descriptive columns.

`bulk_upload_local.sh` creates a row with a name, a year and a collection —
enough to tile against, not enough to be a record. The bbox matters most:
/explore resolves a sheet's extent as bounds -> bbox -> annotation_url ->
allmaps_id, so without it every list view has to fetch and parse an annotation
to find out where the sheet is.

It is not guesswork. The bbox is the extent of the same four pinned graticule
corners the annotation was built from, which is exactly what `maps.bbox` means:
the georeferenced mask, not the whole scan.

    python3 scripts/oneoff/l7014_city_metadata.py [--write]
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

WORK = Path("work/l7014")
CITY = {"6330-4", "6330-1", "6330-2", "6330-3", "6329-1",
        "6329-4", "6541-4", "6641-3", "6350-4"}
PCL = "https://maps.lib.utexas.edu/maps/topo/vietnam/"


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

    pins = json.loads((WORK / "pins.json").read_text())
    index = {f["properties"]["Sheet_no"].replace(" ", ""): f["properties"]
             for f in json.loads((WORK / "index.geojson").read_text())["features"]}
    files = {r["sheet"]: r for r in json.loads((WORK / "sheets.json").read_text())}
    roman = {"1": "I", "2": "II", "3": "III", "4": "IV"}

    rows = req(f"{base}/rest/v1/maps?select=id,name,year,bbox"
               f"&collection=eq.Series%20L7014%20(Vietnam%201:50,000)", key)

    n = 0
    for m in rows:
        sheet = next((s for s in CITY if f"L7014 {s}" in m["name"]), None)
        if not sheet or sheet not in pins:
            continue
        g = pins[sheet]["ground"]
        lons = [g[c][0] for c in g]
        lats = [g[c][1] for c in g]
        num, quad = sheet.split("-")
        meta = index.get(num + roman[quad], {})
        patch = {
            # [minLon, minLat, maxLon, maxLat] — the same shape MapListItem uses.
            "bbox": [round(min(lons), 6), round(min(lats), 6),
                     round(max(lons), 6), round(max(lats), 6)],
            "creator": "U.S. Army Map Service",
            "dc_publisher": "U.S. Army Map Service",
            "holding_institution": "Perry-Castañeda Library Map Collection, "
                                   "University of Texas at Austin",
            "source_url": PCL + files[sheet]["file"].strip().replace(" ", "%20"),
            "rights": "Public domain — a work of the U.S. federal government.",
            "physical_description": "Topographic sheet, 1:50,000, Series L7014.",
            "shelfmark": f"Series L7014, Sheet {sheet}",
            "map_type": "topographic",
            "location": (meta.get("Sheet_name") or "").split(" / ")[0] or None,
            "original_title": meta.get("Sheet_name") or None,
            "extra_metadata": {"sheet_number": sheet, "series": "L7014",
                               "edition": str(int(meta["Year"])) if meta.get("Year") else None},
        }
        # The index has no date for two of them; an invented year is worse than none.
        if not m["year"] and meta.get("Year"):
            patch["year"] = int(meta["Year"])
        patch = {k: v for k, v in patch.items() if v is not None}
        if args.write:
            req(f"{base}/rest/v1/maps?id=eq.{m['id']}", key, "PATCH", patch)
        print(f"  {sheet}  bbox {patch['bbox']}  {'written' if args.write else '(dry run)'}")
        n += 1
    print(f"\n{n} sheets {'updated' if args.write else 'ready'}")


if __name__ == "__main__":
    main()
