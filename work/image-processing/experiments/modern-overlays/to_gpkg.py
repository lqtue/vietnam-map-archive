"""One-off: the HCMC parquet files -> the GeoPackages modern_prior.py reads.

The work/ocr venv's pyogrio has no Parquet driver and is meant to stay small, so convert once with
the system python3 (geopandas). Writes next to the parquet, using the MANIFEST's names:
  hcmc_buildings_3d.gpkg           layer `buildings`: height, area_m2 (UTM 48N), geometry
  vector_out/hcmc_vector.gpkg      the four layers modern_prior reads (road surface, river, lake)
"""
from pathlib import Path

import geopandas as gpd

D = Path("/Users/airm1/Work/Projects/hcmc-buildings")
LAYERS = ("region_duongbos", "region_duongbokhacs", "region_river", "region_lake")

v = gpd.read_parquet(D / "hcmc_vector.parquet", filters=[("layer", "in", list(LAYERS))])
(D / "vector_out").mkdir(exist_ok=True)
for name in LAYERS:
    sub = v[v.layer == name][["madoituong", "geometry"]]
    sub.to_file(D / "vector_out" / "hcmc_vector.gpkg", layer=name, driver="GPKG", mode="a")
    print(name, len(sub))

b = gpd.read_parquet(D / "hcmc_buildings_3d.parquet")
b = b.assign(area_m2=b.geometry.to_crs(32648).area)[["height", "area_m2", "geometry"]]
b.to_file(D / "hcmc_buildings_3d.gpkg", layer="buildings", driver="GPKG")
print("buildings", len(b))
