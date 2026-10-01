"""Does today's river, eroded inward, make a precise water seed on the 1882 / 1898 sheets?

Run with system python3 after overlay.py. For each hand-checked control box, the share of the
box covered by (modern river polygon eroded by N source px). Controls: water cores (expect
high) and dry parcels/blocks (expect 0). 1 px = 0.34 m on both sheets.
"""
import json
from pathlib import Path

import geopandas as gpd
import shapely

HERE = Path(__file__).resolve().parent
BOXES = {  # sheet -> {name: (box, expected)}  from river_ref/windows.json + 1882/river-windows.json
    "1882": {"water_core": ([3900, 6400, 200, 200], "water"), "dry_blue_parcels": ([6900, 4800, 800, 800], "land"),
             "dry_city_blocks": ([4300, 3700, 900, 900], "land")},
    "1898": {"water_core": ([10950, 8650, 200, 200], "water"), "dry_blue": ([8500, 5700, 800, 800], "land"),
             "dry_salmon": ([4800, 5200, 900, 900], "land")},
}
for sheet, boxes in BOXES.items():
    river = shapely.union_all(gpd.read_file(HERE / "out" / f"{sheet}-region_river.geojson").geometry.values)
    print(sheet, "river area km2", round(river.area * 0.34**2 / 1e6, 2))
    for erode in (0, 30, 60, 90):
        seed = river.buffer(-erode)
        row = []
        for name, (b, exp) in boxes.items():
            box = shapely.box(b[0], b[1], b[0] + b[2], b[1] + b[3])
            row.append(f"{name}[{exp}] {seed.intersection(box).area / box.area:6.1%}")
        print(f"  erode {erode:>2}px ({erode*0.34:4.0f} m): " + "  ".join(row))
