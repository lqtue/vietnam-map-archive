#!/usr/bin/env python3
"""Series 325: turn the grade-line placements (indochine325_graticule.py --method lines) into draft annotations.

GCPs = the four corners the fitted grade-line affine gives (px -> lon/lat), mask = the same quad, order-1.
The corners are consistent with the grade lines even when the border pick is wrong ("border_suspect"):
a wrong border only skews the mask, so those sheets are written too and flagged in the printout.
Dry run unless --apply. Never changes status: rows already public with no georef go live when stored. --apply also pushes to Allmaps.

    work/ocr/.venv/bin/python scripts/indochine100k/indochine325_annotate.py [--apply] [--ids a,b]
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import georef_annotation as G  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROBES = ROOT / "work/indochine-100k/325-graticule"
OUT = ROOT / "work/indochine-100k/325-annotations"
CORNERS = ("NW", "NE", "SE", "SW")


def build(res, iiif):
    s = res["scale"]
    w, h = res["size"]
    quad = [[v * s for v in res["corners"][c]["px"]] for c in CORNERS]
    gcps = [(q, (res["corners"][c]["lon"], res["corners"][c]["lat"])) for q, c in zip(quad, CORNERS)]
    return G.annotation(iiif, w, h, gcps, quad)


def selftest():
    res = {"scale": 2, "size": [100, 80], "corners": {
        "NW": {"px": [1, 1], "lon": 106.0, "lat": 11.0}, "NE": {"px": [49, 1], "lon": 106.1, "lat": 11.0},
        "SE": {"px": [49, 39], "lon": 106.1, "lat": 10.9}, "SW": {"px": [1, 39], "lon": 106.0, "lat": 10.9}}}
    a = build(res, "u")["items"][0]
    assert a["body"]["features"][1]["properties"]["resourceCoords"] == [98, 2]
    assert 'points="2,2 98,2 98,78 2,78"' in a["target"]["selector"]["value"]
    print("self-test ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--ids")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return selftest()
    load_dotenv(ROOT / ".env")
    url, key = os.environ["PUBLIC_SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_SERVICE_KEY"]
    r = requests.get(f"{url}/rest/v1/maps", timeout=60, headers={"apikey": key, "Authorization": f"Bearer {key}"},
                     params={"select": "id,status,is_georeferenced,iiif_image",
                             "collection": "eq.Indochine 1:100,000 — 1st édition SGI (1900–1947)", "limit": 500})
    r.raise_for_status()
    db = {x["id"]: x for x in r.json()}
    only = set(a.ids.split(",")) if a.ids else None
    OUT.mkdir(parents=True, exist_ok=True)
    files, skipped = [], []
    for f in sorted(PROBES.glob("*-*-*-*-*.json")):
        res = json.loads(f.read_text())
        row = db.get(res.get("id"))
        why = ("not ok" if res.get("status") != "ok" else "no row" if not row else
               "archived" if row["status"] == "archived" else "already georeferenced" if row["is_georeferenced"] else
               "not in --ids" if only and res["id"] not in only else None)
        if why:
            skipped.append((res.get("name"), why))
            continue
        (OUT / f"{res['id']}.json").write_text(json.dumps(build(res, row["iiif_image"]), indent=1))
        files.append(OUT / f"{res['id']}.json")
        if res.get("border_suspect"):
            print("  border suspect (mask may be off):", res["name"])
    from collections import Counter
    print(f"{len(files)} built, {len(skipped)} skipped", dict(Counter(w for _, w in skipped)))
    G.store(files, "printed-corners", apply=a.apply, allmaps=a.apply)


if __name__ == "__main__":
    main()
