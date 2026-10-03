"""Warp today's HCMC layers onto the 1882 / 1898 sheets and overlay them on the river_ref windows.

Run with the SYSTEM python3 (geopandas, pyarrow), with .env exported:
    set -a; . ./.env; set +a; python3 work/image-processing/experiments/modern-overlays/overlay.py
Reads ~/Work/Projects/hcmc-buildings/{hcmc_vector,hcmc_buildings_3d}.parquet (licence unresolved:
derived outputs stay local, out/ is gitignored). Writes out/<sheet>-<layer>.geojson in SOURCE
pixels and out/overlay-<sheet>-<window>.jpg. This is a look, not a score: no trace exists yet.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import shapely
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "ocr" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from modern_prior import fit_sheet  # noqa: E402
from scale import annotation_for_map  # noqa: E402

DATA = Path("/Users/airm1/Work/Projects/hcmc-buildings")
REF = HERE.parent / "river-reference"
OUT = HERE / "out"
LAYERS = {  # layer -> (colour, width)
    "region_river": ("cyan", 2), "line_mepnuoc": ("blue", 2), "region_port": ("purple", 2),
    "region_duongbos": ("gold", 1), "line_mepduongbos": ("orange", 1), "line_duongbos": ("lime", 2),
}


_ALL = {}


def load(bbox):
    if not _ALL:  # no bbox covering column in either file: read once, clip per sheet
        _ALL["v"] = gpd.read_parquet(DATA / "hcmc_vector.parquet", filters=[("layer", "in", list(LAYERS))])
        _ALL["b"] = gpd.read_parquet(DATA / "hcmc_buildings_3d.parquet")
    clip = lambda g: g.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]  # noqa: E731
    return clip(_ALL["v"]), clip(_ALL["b"])


def to_px(geoms, fit):
    return shapely.transform(geoms, lambda c: fit.px(c), include_z=False)


def draw(img, geoms, colour, width, box):
    x0, y0 = box[:2]
    d = ImageDraw.Draw(img)
    for g in shapely.get_parts(geoms):
        for ring in ([g.exterior, *g.interiors] if g.geom_type == "Polygon" else [g]):
            xy = [(x - x0, y - y0) for x, y in ring.coords]
            if len(xy) > 1:
                d.line(xy, fill=colour, width=width)


def main():
    OUT.mkdir(exist_ok=True)
    spec = json.loads((REF / "windows.json").read_text())
    for sheet, s in spec["sheets"].items():
        fit = fit_sheet(annotation_for_map(s["map_id"]))
        bbox = fit.bbox_lonlat(s["width"], s["height"])
        v, b = load(bbox)
        print(sheet, fit, {k: int((v.layer == k).sum()) for k in LAYERS}, "buildings", len(b))
        px = {k: to_px(v[v.layer == k].geometry.values, fit) for k in LAYERS}
        px["buildings"] = to_px(b.geometry.values, fit)
        for k, g in px.items():
            gpd.GeoSeries(g).to_file(OUT / f"{sheet}-{k}.geojson", driver="GeoJSON")
        for w in [w for w in spec["windows"] if w["sheet"] == sheet]:
            box = w["box"]
            win = shapely.box(box[0], box[1], box[0] + box[2], box[1] + box[3])
            img = Image.open(REF / "crops" / f"{sheet}-{w['id']}.png").convert("RGB")
            for k, (col, wd) in LAYERS.items():
                hit = px[k][shapely.intersects(px[k], win)]
                draw(img, hit, col, wd, box)
            hit = px["buildings"][shapely.intersects(px["buildings"], win)]
            draw(img, hit, "red", 1, box)
            img.save(OUT / f"overlay-{sheet}-{w['id']}.jpg", quality=85)


if __name__ == "__main__":
    main()
