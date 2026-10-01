"""Can ink colour alone separate modern-river-seeded water from dry land? (native pixels, per sheet)

Run with system python3 after overlay.py + river_ref/export.py. Seeds: modern river eroded 60 px,
inside the sheet's open-river windows. Land: the hand-checked dry boxes only (the only land we
trust). "Dark ink" = max(RGB)/255 < 0.8, as in river_pair/eda.py. Reports AUC of (R-B)/255 for
water-ink vs land-ink, and what share passes the repo's 0.07 cut and a seed-derived cut.
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REF = HERE.parent / "river_ref"
CASES = {  # sheet -> (water windows, land windows)
    "1882": (["open_bank", "river_label"], ["dry_blue_parcels", "dry_city_blocks"]),
    "1898": (["open_bank", "water_core"], ["dry_blue", "dry_salmon"]),
}
BOX = {"1882": {"open_bank": [3800, 6100, 800, 800], "river_label": [1400, 7000, 1000, 1000],
                "dry_blue_parcels": [6900, 4800, 800, 800], "dry_city_blocks": [4300, 3700, 900, 900]},
       "1898": {"open_bank": [10300, 8000, 1000, 1000], "water_core": [10950, 8650, 200, 200],
                "dry_blue": [8500, 5700, 800, 800], "dry_salmon": [4800, 5200, 900, 900]}}


def ink(sheet, name, mask=None):
    px = np.asarray(Image.open(REF / "crops" / f"{sheet}-{name}.png").convert("RGB")).astype(float) / 255
    dark = px.max(2) < 0.8
    if mask is not None:
        dark &= mask
    return (px[..., 0] - px[..., 2])[dark]


def seed_mask(river, box, erode=60):
    x, y, w, h = box
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    for g in shapely.get_parts(shapely.intersection(river.buffer(-erode), shapely.box(x, y, x + w, y + h))):
        if g.geom_type == "Polygon":
            d.polygon([(a - x, b - y) for a, b in g.exterior.coords], fill=1)
            for r in g.interiors:
                d.polygon([(a - x, b - y) for a, b in r.coords], fill=0)
    return np.array(m, bool)


def auc(pos, neg, n=200_000, seed=0):
    rng = np.random.default_rng(seed)
    p, q = rng.choice(pos, n), rng.choice(neg, n)
    return float((p > q).mean() + 0.5 * (p == q).mean())  # P(water ink redder than land ink)


for sheet, (wins, lands) in CASES.items():
    river = shapely.union_all(gpd.read_file(HERE / "out" / f"{sheet}-region_river.geojson").geometry.values)
    water = np.concatenate([ink(sheet, w, seed_mask(river, BOX[sheet][w])) for w in wins])
    land = np.concatenate([ink(sheet, l) for l in lands])
    cut90 = float(np.percentile(water, 90))
    print(f"{sheet}: water-seed dark px {len(water):,}  land dark px {len(land):,}")
    print(f"  median (R-B)/255  water {np.median(water):+.3f}  land {np.median(land):+.3f}   AUC(water redder than land) {auc(water, land):.3f}")
    for name, t in (("0.07 (repo)", 0.07), ("0.09", 0.09), (f"seed p90 = {cut90:.3f}", cut90)):
        print(f"  cut < {name:<18} water ink kept {np.mean(water < t):6.1%}   land ink kept {np.mean(land < t):6.1%}")
    for l in lands:  # pooled land hides which negative is hard
        li = ink(sheet, l)
        print(f"  vs {l:<18} AUC {1 - auc(water, li):.3f} (water bluer than land)  land ink kept at <0.07: {np.mean(li < 0.07):6.1%}")
