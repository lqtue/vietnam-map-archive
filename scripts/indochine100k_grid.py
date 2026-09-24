#!/usr/bin/env python3
"""Build the series-561 sheet grid from CartoMundi's published WKT.

The local source snapshots are matched by fkey. A read-only query attaches
current VMA map IDs. Only --apply writes local files, never database rows.
"""
import argparse
import json
import os
from pathlib import Path

from shapely import wkt
from shapely.geometry import mapping
from shapely.ops import unary_union

import indochine100k_georef as geo

COLLECTIONS = {
    325: "Indochine 1:100,000 — 1st édition SGI (1900–1947)",
    561: "Indochine 1:100,000 — 2nd édition SGI (1947–1959)",
}


def paths(series):
    return (geo.WORK / f"sources/serie-{series}.json",
            geo.WORK / f"sources/serie-{series}-wkt.json",
            geo.WORK / ("grid" if series == 561 else f"grid-{series}"))


def read_sources(series):
    source_path, wkt_path, _ = paths(series)
    source = json.loads(source_path.read_text())
    footprints = json.loads(wkt_path.read_text())["records"]
    by_fkey = {}
    for record in footprints:
        key = str(record["fkey"])
        if key in by_fkey:
            raise ValueError(f"duplicate WKT fkey {key}")
        polygon = wkt.loads(record["wkt"])
        if polygon.is_empty or not polygon.is_valid or polygon.geom_type not in ("Polygon", "MultiPolygon"):
            raise ValueError(f"invalid WKT for fkey {key}")
        west, south, east, north = polygon.bounds
        if not (98 <= west < east <= 112 and 8 <= south < north <= 25):
            raise ValueError(f"fkey {key} has coordinates outside series-{series} region")
        by_fkey[key] = {**record, "polygon": polygon}
    catalogue_keys = [str(r["fkey"]) for records in source["cells"].values() for r in records]
    if len(catalogue_keys) != len(set(catalogue_keys)):
        raise ValueError(f"duplicate fkey in series-{series} catalogue")
    missing = set(catalogue_keys) - set(by_fkey)
    if missing:
        raise ValueError(f"WKT missing {len(missing)} local catalogue fkeys")
    by_fkey = {key: value for key, value in by_fkey.items() if key in set(catalogue_keys)}
    return source, by_fkey


def map_index(rows, footprints):
    by_fkey = {}
    for row in rows:
        keys = (row.get("extra_metadata") or {}).get("cartomundi_fkeys") or []
        if len(keys) != 1:
            raise ValueError(f"map {row['id']} must have one CartoMundi fkey")
        key = str(keys[0])
        if key not in footprints or key in by_fkey:
            raise ValueError(f"map {row['id']} has an absent or duplicated fkey {key}")
        by_fkey[key] = row["id"]
    return by_fkey


def feature(identifier, polygons, properties):
    geometry = mapping(unary_union(polygons)) if polygons else None
    return {"type": "Feature", "id": identifier, "geometry": geometry,
            "properties": {"grid_id": identifier, **properties}}


def build(series, source, footprints, rows):
    maps = map_index(rows, footprints)
    cells, halves, crosswalk = [], [], []
    for number, records in source["cells"].items():
        cell_id = f"{series}:{number}"
        keys = sorted({str(r["fkey"]) for r in records})
        parts = {part: [str(r["fkey"]) for r in records if r.get("part") == part]
                 for part in ("W", "E")}
        cell_polygons = [footprints[k]["polygon"] for k in keys]
        cell_maps = sorted(maps[k] for k in keys if k in maps)
        codes = sorted({str(footprints[k]["grid_code"]) for k in keys})
        props = {"sheet_number": number, "geometry_source": "CartoMundi WKT",
                 "parts_present": [part for part in ("W", "E") if parts[part]],
                 "has_unclassified_records": any(r.get("part") not in ("W", "E") for r in records),
                 "grid_codes": codes, "fkeys": keys, "map_ids": cell_maps}
        cells.append(feature(cell_id, cell_polygons, props))
        for part in ("W", "E"):
            part_keys = sorted(set(parts[part]))
            slot_id = f"{cell_id}:{part}"
            halves.append(feature(slot_id, [footprints[k]["polygon"] for k in part_keys],
                                  {"cell_id": cell_id, "sheet_number": number, "part": part,
                                   "geometry_source": "CartoMundi WKT" if part_keys else None,
                                   "grid_codes": sorted({str(footprints[k]["grid_code"]) for k in part_keys}),
                                   "fkeys": part_keys,
                                   "map_ids": sorted(maps[k] for k in part_keys if k in maps)}))
        for record in records:
            key = str(record["fkey"])
            part = record.get("part")
            crosswalk.append({"map_id": maps.get(key), "fkey": key,
                              "grid_id": cell_id,
                              "slot_id": f"{cell_id}:{part}" if part in ("W", "E") else None,
                              "sheet_number": number, "part": part or "unclassified",
                              "title": record.get("title"),
                              "geometry_key": footprints[key]["geometry_key"],
                              "grid_code": footprints[key]["grid_code"],
                              "geometry_source": "CartoMundi WKT"})
    # Distinct sheet numbers with large polygon overlap remain visible for
    # review. CartoMundi assigns 153 W and 154 W the same geometry key.
    polygons = [unary_union([footprints[k]["polygon"] for k in c["properties"]["fkeys"]])
                for c in cells]
    for i, a in enumerate(cells):
        for j in range(i + 1, len(cells)):
            b = cells[j]
            overlap = polygons[i].intersection(polygons[j]).area
            if overlap > .2 * min(polygons[i].area, polygons[j].area):
                a["properties"].setdefault("spatial_conflicts", []).append(b["id"])
                b["properties"].setdefault("spatial_conflicts", []).append(a["id"])
    return cells, halves, crosswalk


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", choices=("325", "561"), default="561")
    parser.add_argument("--apply", action="store_true", help="write local grid files")
    args = parser.parse_args()
    series = int(args.series)
    source, footprints = read_sources(series)
    cells, halves, crosswalk = build(series, source, footprints, map_rows(series))
    mapped = [r["map_id"] for r in crosswalk if r["map_id"]]
    if len(mapped) != len(set(mapped)):
        raise ValueError("a map was matched to multiple catalogue records")
    conflicts = [c["id"] for c in cells if c["properties"].get("spatial_conflicts")]
    print(f"{len(cells)} numbered cells; {len(halves)} W/E slots; "
          f"{len(mapped)} matched maps; {len(crosswalk)} catalogue records")
    print(f"  absent W/E slots: {sum(h['geometry'] is None for h in halves)}")
    print(f"  cells with substantial spatial conflicts: {', '.join(conflicts) or 'none'}")
    if not args.apply:
        return
    _, _, output = paths(series)
    output.mkdir(parents=True, exist_ok=True)
    for name, features in (("cells.geojson", cells), ("halves.geojson", halves)):
        (output / name).write_text(json.dumps({"type": "FeatureCollection", "features": features},
                                              ensure_ascii=False, indent=1) + "\n")
    (output / "map-crosswalk.json").write_text(json.dumps(crosswalk, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {output / 'cells.geojson'}, {output / 'halves.geojson'}, "
          f"{output / 'map-crosswalk.json'}")


def map_rows(series):
    import requests
    from dotenv import load_dotenv
    load_dotenv(Path(".env"))
    url = os.environ["PUBLIC_SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    out, offset = [], 0
    while True:
        response = requests.get(f"{url}/rest/v1/maps", headers=headers, timeout=40,
                                params={"select": "id,name,extra_metadata",
                                        "collection": f"eq.{COLLECTIONS[series]}",
                                        "order": "id", "limit": 500, "offset": offset})
        response.raise_for_status()
        page = response.json()
        out.extend(page)
        if len(page) < 500:
            return out
        offset += 500


if __name__ == "__main__":
    main()
