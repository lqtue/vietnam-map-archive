#!/usr/bin/env python3
"""Fill in the fifteen L7014 backdrop sheets: bbox, sheet number, provenance.

`bulk_upload_local.sh` creates a row with a name and a collection and nothing
else -- its filename parser reads a sheet number only from a *leading* digit
run, and these are named "<place> (L7014 <sheet>).jpg", so every one of them
arrives with `extra_metadata = {}`. `map_series` keys off
`extra_metadata.sheet_number`, so until this runs the fifteen are invisible to
the series view no matter what their status is.

The bbox comes from `corners.csv` -- the printed graticule corners shifted to
WGS 84 -- and not from an annotation, because these sheets have none yet: that
is the whole reason they are in the georeferencing queue. For a 15' cell the
graticule corners *are* the mapped extent, which is what `maps.bbox` means, so
the value is right now and the annotation will not move it.

Two columns are deliberately left alone:

  year     index.geojson's Year is the cell's, not the scan's. It filed a 1984
           DMA sheet under 1965 once already (see l7014_city_years.py). These
           stay null until someone reads each collar.
  edition  l7014_city_metadata.py wrote the same index year into
           extra_metadata.edition, which is not an edition. Not repeated here.

`priority` is set so the fifteen sort above the other ~63 drafts in
/contribute/georef, which is the next thing that happens to them.

    python3 scripts/oneoff/l7014_backdrop_metadata.py [--write]
"""

import argparse
import csv
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

WORK = Path("work/l7014")
PCL = "https://maps.lib.utexas.edu/maps/topo/vietnam/"
COLLECTION = "Series L7014 (Vietnam 1:50,000)"
PRIORITY = 10

BACKDROP = ["6150-2", "6150-3", "6150-4", "6151-1", "6151-4",
            "6329-2", "6329-3", "6350-1", "6350-2", "6350-3",
            "6541-1", "6541-2", "6541-3", "6641-2", "6641-4"]


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


def corner_bbox():
    """sheet -> [minLon, minLat, maxLon, maxLat] from the shifted graticule."""
    pts = {}
    with open(WORK / "corners.csv") as f:
        for row in csv.DictReader(f):
            pts.setdefault(row["sheet"], []).append(
                (float(row["lon"]), float(row["lat"])))
    out = {}
    for sheet, ps in pts.items():
        if len(ps) != 4:            # a partial sheet is a bug, not a bbox
            continue
        lons, lats = [p[0] for p in ps], [p[1] for p in ps]
        out[sheet] = [round(min(lons), 6), round(min(lats), 6),
                      round(max(lons), 6), round(max(lats), 6)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    base, key = env()

    bboxes = corner_bbox()
    files = {r["sheet"]: r for r in json.loads((WORK / "sheets.json").read_text())}
    roman = {"1": "I", "2": "II", "3": "III", "4": "IV"}
    index = {f["properties"]["Sheet_no"].replace(" ", ""): f["properties"]
             for f in json.loads((WORK / "index.geojson").read_text())["features"]}

    rows = req(f"{base}/rest/v1/maps?select=id,name,status,bbox,extra_metadata"
               f"&collection=eq.{urllib.parse.quote(COLLECTION)}", key)

    done, missing = 0, []
    for sheet in BACKDROP:
        hits = [m for m in rows if f"(L7014 {sheet})" in m["name"]]
        # One row per sheet. Two means the upload ran twice; stop rather than
        # patch an arbitrary one of them.
        if len(hits) != 1:
            missing.append(f"{sheet}: {len(hits)} rows")
            continue
        m = hits[0]
        if sheet not in bboxes:
            missing.append(f"{sheet}: no corners")
            continue
        if m["status"] != "draft":
            missing.append(f"{sheet}: status={m['status']}, not touching it")
            continue

        num, quad = sheet.split("-")
        meta = index.get(num + roman[quad], {})
        name = (meta.get("Sheet_name") or "").strip()
        patch = {
            "bbox": bboxes[sheet],
            "priority": PRIORITY,
            "creator": "U.S. Army Map Service",
            "dc_publisher": "U.S. Army Map Service",
            "holding_institution": "Perry-Castañeda Library Map Collection, "
                                   "University of Texas at Austin",
            "rights": "Public domain — a work of the U.S. federal government.",
            "physical_description": "Topographic sheet, 1:50,000, Series L7014.",
            "shelfmark": f"Series L7014, Sheet {sheet}",
            "map_type": "topographic",
            "location": name.split(" / ")[0] or None,
            "original_title": name or None,
            "extra_metadata": {"sheet_number": sheet, "series": "L7014"},
        }
        if sheet in files:
            patch["source_url"] = PCL + files[sheet]["file"].strip().replace(" ", "%20")
        patch = {k: v for k, v in patch.items() if v is not None}

        if args.write:
            req(f"{base}/rest/v1/maps?id=eq.{m['id']}", key, "PATCH", patch)
        print(f"  {sheet}  {patch['bbox']}  {patch.get('original_title','-')}"
              f"  {'written' if args.write else '(dry run)'}")
        done += 1

    for p in missing:
        print(f"  SKIP {p}", file=sys.stderr)
    print(f"\n{done}/{len(BACKDROP)} sheets {'updated' if args.write else 'ready'}")
    if missing:
        print(f"{len(missing)} skipped — see above", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
