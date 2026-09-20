#!/usr/bin/env python3
"""Measure the free joins in an L7014 mosaic.

    python3 scripts/l7014_seams.py --key l7014-faulty --csv work/l7014/regen/seams-faulty.csv
    python3 scripts/l7014_seams.py --self-check

The lattice supplies adjacency, but does not constrain either outline.  A seam
is consequently evidence only when both sheets were warped independently.
"""

import argparse
import csv
import json
import math
import sys

from pathlib import Path

from l7014_mosaic import ground_metres


WORK = Path("work/l7014")
BUILD = WORK / "build"
LATTICE = WORK / "lattice.json"
SAMPLES = 25
EDGE_MARGIN = 0.10
EDGES = (("N", 0, 1), ("E", 1, 2), ("S", 2, 3), ("W", 3, 0))


def rings(geometry):
    """The outer rings; holes are not sheet outlines."""
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    if geometry["type"] == "MultiPolygon":
        return [poly[0] for poly in geometry["coordinates"]]
    raise ValueError(f"unsupported manifest geometry {geometry['type']}")


def edge_key(a, b):
    """Seven decimals is the precision `corners` writes to lattice.json."""
    return tuple(sorted((tuple(round(v, 7) for v in a), tuple(round(v, 7) for v in b))))


def shared_edges(cells, present):
    """Yield each lattice edge held by exactly two present sheets, once."""
    by_edge = {}
    for sheet in sorted(present):
        corners = cells.get(sheet)
        if not corners:
            continue
        for side, start, end in EDGES:
            by_edge.setdefault(edge_key(corners[start], corners[end]), []).append(
                (sheet, side, corners[start], corners[end]))
    for holders in by_edge.values():
        if len(holders) != 2:
            continue
        a, b = sorted(holders)
        yield a, b


def nearest_on_segment(point, a, b):
    """Nearest lon/lat point on a segment, using its local metre plane."""
    latitude = math.radians(point[1])
    sx = 111320.0 * math.cos(latitude)
    sy = 110540.0
    ax, ay = (a[0] - point[0]) * sx, (a[1] - point[1]) * sy
    bx, by = (b[0] - point[0]) * sx, (b[1] - point[1]) * sy
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    t = 0.0 if not denom else max(0.0, min(1.0, -(ax * dx + ay * dy) / denom))
    return [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]


def nearest_outline(point, outline):
    best, distance = None, float("inf")
    for ring in outline:
        for a, b in zip(ring, ring[1:]):
            candidate = nearest_on_segment(point, a, b)
            candidate_distance = ground_metres(point, candidate)
            if candidate_distance < distance:
                best, distance = candidate, candidate_distance
    if best is None:
        raise ValueError("outline has no segments")
    return best


def measure_edge(start, end, outline_a, outline_b):
    displacements = []
    for index in range(SAMPLES):
        # Corners join four outlines, so they are not a measurement of either
        # one seam.  Leave a small interval at both ends for that ambiguity.
        fraction = EDGE_MARGIN + (1.0 - 2.0 * EDGE_MARGIN) * index / (SAMPLES - 1)
        point = [start[0] + fraction * (end[0] - start[0]),
                 start[1] + fraction * (end[1] - start[1])]
        on_a = nearest_outline(point, outline_a)
        on_b = nearest_outline(point, outline_b)
        displacements.append(ground_metres(on_a, on_b))
    ordered = sorted(displacements)
    return ordered[len(ordered) // 2], max(ordered), len(ordered)


def census(cells, features):
    by_sheet = {f["properties"]["sheet"]: f for f in features}
    rows = []
    for a, b in shared_edges(cells, by_sheet):
        sheet_a, side, start, end = a
        sheet_b, _, _, _ = b
        feature_a, feature_b = by_sheet[sheet_a], by_sheet[sheet_b]
        median, maximum, samples = measure_edge(start, end, rings(feature_a["geometry"]),
                                                  rings(feature_b["geometry"]))
        rows.append({"sheet_a": sheet_a, "kind_a": feature_a["properties"].get("kind", ""),
                     "sheet_b": sheet_b, "kind_b": feature_b["properties"].get("kind", ""),
                     "edge": side, "median_m": median, "max_m": maximum,
                     "samples": samples})
    return rows


def synthetic_feature(sheet, kind, west, south, east, north, dx=0.0, dy=0.0):
    ring = [[west + dx, south + dy], [east + dx, south + dy],
            [east + dx, north + dy], [west + dx, north + dy], [west + dx, south + dy]]
    return {"type": "Feature", "properties": {"sheet": sheet, "kind": kind},
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def self_check():
    # A small WGS 84 lattice centred near the real series; metres stay local.
    cells = {"1000-1": [[106.0, 10.1], [106.1, 10.1], [106.1, 10.0], [106.0, 10.0]],
             "1001-1": [[106.1, 10.1], [106.2, 10.1], [106.2, 10.0], [106.1, 10.0]],
             "1000-2": [[106.0, 10.0], [106.1, 10.0], [106.1, 9.9], [106.0, 9.9]],
             "1001-2": [[106.1, 10.0], [106.2, 10.0], [106.2, 9.9], [106.1, 9.9]]}

    def features(offset_by_sheet=None):
        offset_by_sheet = offset_by_sheet or {}
        return [synthetic_feature(sheet, "pdf", c[0][0], c[3][1], c[1][0], c[0][1],
                                  dx=offset_by_sheet.get(sheet, (0.0, 0.0))[0],
                                  dy=offset_by_sheet.get(sheet, (0.0, 0.0))[1])
                for sheet, c in cells.items()]

    zero = census(cells, features())
    assert len(zero) == 4, f"expected four seams, got {len(zero)}"
    assert all(r["max_m"] < 0.01 for r in zero), zero

    shift_x = 470.0 / (111320.0 * math.cos(math.radians(10.0)))
    shift_y = 470.0 / 110540.0
    # 470 m in both lattice axes makes the signal normal to each of this
    # corner sheet's two joins; a parallel translation is not a seam gap.
    one = census(cells, features({"1000-1": (shift_x, shift_y)}))
    moved = [r for r in one if "1000-1" in (r["sheet_a"], r["sheet_b"])]
    still = [r for r in one if "1000-1" not in (r["sheet_a"], r["sheet_b"])]
    assert len(moved) == 2 and len(still) == 2, one
    assert all(abs(r["median_m"] - 470.0) < 0.5 for r in moved), moved
    assert all(r["max_m"] < 0.01 for r in still), still

    common = census(cells, features({sheet: (shift_x, shift_y) for sheet in cells}))
    assert all(r["max_m"] < 0.01 for r in common), common
    print("self-check: 4 perfect sheets, 4 seams at 0 m")
    print("self-check: one sheet offset 470 m on both axes affects exactly 2 shared seams")
    print("self-check: common 470 m-per-axis offset leaves 4 seams at 0 m")
    print("self-check: ok")


def load_cells():
    if not LATTICE.exists():
        sys.exit(f"{LATTICE} missing -- run `l7014_mosaic.py corners` first")
    data = json.loads(LATTICE.read_text())
    cells = data.get("cells")
    if not isinstance(cells, dict):
        sys.exit(f"{LATTICE}: expected an object with a cells member")
    return cells


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=("sheet_a", "kind_a", "sheet_b", "kind_b", "edge",
                                                  "median_m", "max_m", "samples"))
        writer.writeheader()
        writer.writerows(rows)


def summary(rows):
    medians = sorted(r["median_m"] for r in rows)
    midpoint = len(medians) // 2
    median = ((medians[midpoint - 1] + medians[midpoint]) / 2 if len(medians) % 2 == 0
              else medians[midpoint]) if medians else 0.0
    over = sum(r["median_m"] > 300.0 for r in rows)
    groups = {}
    for row in rows:
        group = " / ".join(sorted((row["kind_a"], row["kind_b"])))
        groups[group] = groups.get(group, 0) + 1
    print(f"seams: {len(rows)}, median {median:.1f} m, over 300 m: {over}")
    print("kinds: " + ", ".join(f"{group} {count}" for group, count in sorted(groups.items())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", default="l7014-faulty", help="manifest key under work/l7014/build")
    parser.add_argument("--csv", type=Path, help="CSV destination")
    parser.add_argument("--self-check", action="store_true", help="run synthetic free-seam assertions")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if not args.csv:
        parser.error("--csv is required unless --self-check is used")
    manifest = BUILD / f"{args.key}.geojson"
    if not manifest.exists():
        sys.exit(f"{manifest} missing -- run `l7014_mosaic.py manifest --key {args.key}` first")
    # `ground_metres` is shared with phase_fit.  `cell_corners()` cannot read
    # this already-shifted artifact: it needs the Indian-1960 source index.
    rows = census(load_cells(), json.loads(manifest.read_text())["features"])
    write_csv(args.csv, rows)
    summary(rows)


if __name__ == "__main__":
    main()
