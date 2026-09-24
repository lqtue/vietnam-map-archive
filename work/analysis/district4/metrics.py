#!/usr/bin/env python3
"""Morphology metrics for one study area, one map year.

The measurements behind "the urban evolution of District 4": for each sheet
that covers the area, how much of it was built, how coarse the blocks were,
how dense the streets, how much water was still open. Compare two years and
the difference is the change.

Everything here is a pure function over GeoJSON, so it runs without the
network and can be checked against geometry whose answer is known:

    python work/analysis/district4/metrics.py --self-check

Design notes: `docs/search-plan.md` §E2. The features come from
`/api/export/footprints`, which warps them server-side, so this module only
ever sees WGS84 and never touches a georeference.

ponytail: areas and lengths are computed in a metre CRS chosen once for the
AOI (UTM zone from its centroid), not on a geodesic. Over a few square
kilometres the difference is far below the warp error the export already
reports, and a projected CRS keeps the code to shapely calls. If this is ever
run on something continent-sized, swap `_to_metres` for a geodesic measure.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

from pyproj import CRS, Transformer
from shapely.geometry import shape, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform, unary_union

# What counts as what. `feature_type` comes from footprints and is
# the only classification a traced polygon carries.
BUILT = {"building"}
PLOT = {"land_plot"}
LINEAR = {"road", "waterway"}
WATER = {"water_body", "waterway"}
GREEN = {"green_space"}


@dataclass
class Metrics:
    year: int | None
    map_ids: str
    features: int
    aoi_area_m2: float
    built_area_m2: float
    built_share: float
    building_count: int
    mean_building_m2: float
    block_count: int
    mean_block_m2: float
    road_length_m: float
    road_density_m_per_km2: float
    water_area_m2: float
    water_length_m: float
    green_area_m2: float
    unwarped_dropped: int
    max_geom_rmse_m: float | None


def _to_metres(lng: float, lat: float) -> Transformer:
    """A transformer into the UTM zone containing this point."""
    zone = int((lng + 180) // 6) + 1
    crs = CRS.from_dict(
        {"proj": "utm", "zone": zone, "south": lat < 0, "datum": "WGS84", "units": "m"}
    )
    return Transformer.from_crs(CRS.from_epsg(4326), crs, always_xy=True)


def measure(features: list[dict], aoi: BaseGeometry | tuple[float, float, float, float]) -> Metrics:
    """Metrics for `features` clipped to `aoi`, a WGS84 geometry.

    A 4-tuple is still accepted and boxed, but a box is the wrong shape for a
    real study area. District 4 is a diagonal peninsula: its bounding box is
    7.62 km2 against 4.46 km2 of actual land, reaching across the Ben Nghe
    canal into District 1 and across the Te into District 7. Since
    `built_share` and `road_density` both divide by the AOI's area, measuring
    the box understates every ratio by nearly half *and* clips in features
    that were never in the district. Pass the polygon instead:

        parse_aoi(Path(__file__).with_name("district4.geojson"))
    """
    if isinstance(aoi, (tuple, list)):
        aoi = box(*aoi)
    centre = aoi.centroid
    tf = _to_metres(centre.x, centre.y)
    project = lambda g: shapely_transform(tf.transform, g)  # noqa: E731

    aoi_geom = project(aoi)
    aoi_area = aoi_geom.area

    built, plots, water_polys, greens = [], [], [], []
    roads, waters_lin = [], []
    years: set[int] = set()
    map_ids: set[str] = set()
    rmse: list[float] = []
    dropped = 0
    kept = 0

    for f in features:
        props = f.get("properties") or {}
        # An unwarped row carries pixel coordinates, not degrees. Measuring it
        # would silently add a polygon the size of a continent.
        if props.get("geo_converted") is False:
            dropped += 1
            continue
        try:
            geom = project(shape(f["geometry"]))
        except Exception:
            dropped += 1
            continue
        clipped = geom.intersection(aoi_geom)
        if clipped.is_empty:
            continue

        kept += 1
        if props.get("year") is not None:
            years.add(int(props["year"]))
        if props.get("map_id"):
            map_ids.add(str(props["map_id"]))
        if props.get("geom_rmse") is not None:
            rmse.append(float(props["geom_rmse"]))

        ftype = str(props.get("feature_type") or "other")
        if ftype in BUILT:
            built.append(clipped)
        if ftype in PLOT:
            plots.append(clipped)
        if ftype in GREEN:
            greens.append(clipped)
        if ftype in WATER:
            water_polys.append(clipped)
        if ftype in LINEAR:
            # A traced line arrives as a closed ring, so its "length" is the
            # ring's perimeter halved — an out-and-back around a street.
            line_len = clipped.length / 2 if clipped.geom_type in ("Polygon", "MultiPolygon") else clipped.length
            (waters_lin if ftype == "waterway" else roads).append(line_len)

    built_union = unary_union(built) if built else None
    built_area = built_union.area if built_union else 0.0
    block_union = unary_union(plots) if plots else None
    road_len = float(sum(roads))

    return Metrics(
        year=min(years) if years else None,
        map_ids=",".join(sorted(map_ids)),
        features=kept,
        aoi_area_m2=round(aoi_area, 1),
        built_area_m2=round(built_area, 1),
        built_share=round(built_area / aoi_area, 5) if aoi_area else 0.0,
        building_count=len(built),
        mean_building_m2=round(built_area / len(built), 1) if built else 0.0,
        block_count=len(plots),
        mean_block_m2=round(block_union.area / len(plots), 1) if plots else 0.0,
        road_length_m=round(road_len, 1),
        road_density_m_per_km2=round(road_len / (aoi_area / 1e6), 1) if aoi_area else 0.0,
        water_area_m2=round(unary_union(water_polys).area, 1) if water_polys else 0.0,
        water_length_m=round(float(sum(waters_lin)), 1),
        green_area_m2=round(unary_union(greens).area, 1) if greens else 0.0,
        unwarped_dropped=dropped,
        max_geom_rmse_m=round(max(rmse), 1) if rmse else None,
    )


def parse_aoi(spec: str | Path) -> BaseGeometry:
    """`minLng,minLat,maxLng,maxLat`, or the path to a GeoJSON polygon.

    The bbox form is for a quick look. A study area you intend to publish
    numbers for should be a polygon file, so that the denominator is land and
    not the river — see `measure()`.
    """
    text = str(spec)
    if text.lower().endswith((".json", ".geojson")):
        path = Path(text)
        if not path.exists():
            raise ValueError(f"no such AOI file: {path}")
        obj = json.loads(path.read_text())
        kind = obj.get("type")
        if kind == "FeatureCollection":
            geoms = [shape(f["geometry"]) for f in obj.get("features", [])]
            if not geoms:
                raise ValueError(f"{path} has no features")
            geom = unary_union(geoms)
        elif kind == "Feature":
            geom = shape(obj["geometry"])
        else:
            geom = shape(obj)
        if geom.is_empty or geom.area <= 0:
            raise ValueError(f"{path} encloses no area")
        return geom

    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError("aoi must be minLng,minLat,maxLng,maxLat, or a .geojson path")
    min_lng, min_lat, max_lng, max_lat = parts
    if min_lng >= max_lng or min_lat >= max_lat:
        raise ValueError(f"aoi corners are out of order: {spec}")
    return box(min_lng, min_lat, max_lng, max_lat)


# ── self-check ────────────────────────────────────────────────────────────────


def _square(lng: float, lat: float, side_deg: float, ftype: str, year: int = 1900) -> dict:
    """A square polygon feature, in degrees, shaped like the export's output."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [lng, lat],
                    [lng + side_deg, lat],
                    [lng + side_deg, lat + side_deg],
                    [lng, lat + side_deg],
                    [lng, lat],
                ]
            ],
        },
        "properties": {
            "id": f"{ftype}-{lng}-{lat}",
            "map_id": "m1",
            "year": year,
            "feature_type": ftype,
            "status": "approved",
            "source": "volunteer",
            "geo_converted": True,
            "geom_rmse": 5.0,
        },
    }


def self_check() -> None:
    # A degree of latitude is ~111.32 km; at Saigon's latitude a degree of
    # longitude is ~109.4 km. A 0.001° square is therefore ~111 m × 109 m.
    aoi = parse_aoi("106.700,10.770,106.710,10.780")
    m = measure([_square(106.701, 10.771, 0.001, "building")], aoi)
    assert m.building_count == 1, m
    assert 11_000 < m.built_area_m2 < 13_500, m.built_area_m2
    # The AOI is 0.01° × 0.01°, so ~1.09 km × 1.11 km.
    assert 1.15e6 < m.aoi_area_m2 < 1.30e6, m.aoi_area_m2
    assert 0.008 < m.built_share < 0.012, m.built_share
    assert m.max_geom_rmse_m == 5.0

    # Overlapping buildings must not double-count: two identical squares are
    # one built area, though they stay two counted features.
    dup = measure([_square(106.701, 10.771, 0.001, "building")] * 2, aoi)
    assert dup.building_count == 2
    assert abs(dup.built_area_m2 - m.built_area_m2) < 1.0, (dup.built_area_m2, m.built_area_m2)

    # Anything outside the AOI contributes nothing, and a partial overlap is
    # clipped rather than counted whole.
    outside = measure([_square(106.8, 10.9, 0.001, "building")], aoi)
    assert outside.features == 0 and outside.built_area_m2 == 0.0, outside
    straddle = measure([_square(106.7095, 10.771, 0.001, "building")], aoi)
    assert 0 < straddle.built_area_m2 < m.built_area_m2, straddle.built_area_m2

    # An unwarped row is dropped, loudly.
    px = _square(106.701, 10.771, 0.001, "building")
    px["properties"]["geo_converted"] = False
    assert measure([px], aoi).unwarped_dropped == 1

    # Types land in the right buckets.
    mixed = measure(
        [
            _square(106.701, 10.771, 0.001, "building"),
            _square(106.703, 10.771, 0.002, "land_plot"),
            _square(106.705, 10.771, 0.001, "water_body"),
            _square(106.706, 10.771, 0.001, "green_space"),
            _square(106.707, 10.771, 0.001, "road"),
        ],
        aoi,
    )
    assert mixed.block_count == 1 and mixed.mean_block_m2 > mixed.mean_building_m2, mixed
    assert mixed.water_area_m2 > 0 and mixed.green_area_m2 > 0, mixed
    assert mixed.road_length_m > 0 and mixed.road_density_m_per_km2 > 0, mixed

    # Empty input is zero, not a crash or a division by zero.
    empty = measure([], aoi)
    assert empty.features == 0 and empty.built_share == 0.0 and empty.road_density_m_per_km2 == 0.0

    # The shipped District 4 polygon is land, not a rectangle. If these two
    # ever converge, someone has quietly replaced the polygon with its bbox
    # and every built_share in the series has silently halved.
    d4 = parse_aoi(Path(__file__).with_name("district4.geojson"))
    poly_m2 = measure([], d4).aoi_area_m2
    bbox_m2 = measure([], parse_aoi(",".join(str(v) for v in d4.bounds))).aoi_area_m2
    assert 4.3e6 < poly_m2 < 4.6e6, poly_m2
    assert bbox_m2 / poly_m2 > 1.5, (bbox_m2, poly_m2)

    # A malformed AOI is refused.
    for bad in ("1,2,3", "106.71,10.77,106.70,10.78", "nope.geojson"):
        try:
            parse_aoi(bad)
            raise AssertionError(f"parse_aoi accepted {bad!r}")
        except ValueError:
            pass

    print("[ok] district4 metrics self-check passed")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-check", action="store_true", help="run the assertions and exit")
    ap.add_argument("--geojson", type=Path, help="a FeatureCollection from /api/export/footprints")
    ap.add_argument("--aoi", help="minLng,minLat,maxLng,maxLat, or a path to a GeoJSON polygon")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return
    if not args.geojson or not args.aoi:
        ap.error("pass --geojson and --aoi, or --self-check")

    fc = json.loads(args.geojson.read_text())
    print(json.dumps(asdict(measure(fc.get("features", []), parse_aoi(args.aoi))), indent=2))


if __name__ == "__main__":
    main()
