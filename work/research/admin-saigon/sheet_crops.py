"""Crop the Quận 4 area from the four national sheets, for transfer-test.md part 2.

Usage (from the repo root): work/ocr/.venv/bin/python work/research/admin-saigon/sheet_crops.py OUT_DIR
The georef comes from the app's annotation mirror, not annotations.allmaps.org (those ids 404).
The 1930 inset (1:50,000, not georeferenced) is cropped by fixed pixels.
"""
import sys, requests, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'core'))
from vma_core.iiif import fetch_crop, get_image_info
OUT = sys.argv[1]
SHEETS = {
  '1882': 'https://iiif.maparchive.vn/iiif/3d065384-bb09-4b8c-b46b-bf006d0c3ba3',
  '1930': 'https://iiif.maparchive.vn/iiif/9bc7ce55-8302-49e0-88bb-56de33b54884',
  '1971': 'https://iiif.maparchive.vn/iiif/7a068afa-a45e-4d2c-b03b-4183682c7c95',
  '1984': 'https://iiif.maparchive.vn/iiif/08f9e044-c324-4291-99da-69783768e85f',
}
BOX = (106.680, 10.745, 106.725, 10.778)  # Q4 box from map_match.py, plus ~1 km
for year, base in SHEETS.items():
    ann = requests.get(f'https://maparchive.vn/api/maps/{base.rsplit("/",1)[1]}/annotation', timeout=30).json()
    item = ann['items'][0] if 'items' in ann else ann
    src = item['target']['source']
    gcps = [(f['properties']['resourceCoords'], f['geometry']['coordinates']) for f in item['body']['features']]
    px = np.array([g[0] for g in gcps], float); geo = np.array([g[1] for g in gcps], float)
    A = np.c_[geo, np.ones(len(geo))]
    M, *_ = np.linalg.lstsq(A, px, rcond=None)  # ponytail: affine, fine for a crop box with a margin
    info = get_image_info(base)
    k = info['width'] / src.get('width', info['width'])
    corners = np.array([[BOX[0], BOX[1], 1], [BOX[2], BOX[1], 1], [BOX[0], BOX[3], 1], [BOX[2], BOX[3], 1]]) @ M * k
    x0, y0 = corners.min(0).clip(0); x1, y1 = corners.max(0)
    x1, y1 = min(x1, info['width']), min(y1, info['height'])
    w, h = int(x1 - x0), int(y1 - y0)
    print(year, len(gcps), 'gcps', 'scale', round(k, 3), 'crop', int(x0), int(y0), w, h, 'of', info['width'], info['height'])
    if w > 0 and h > 0:
        fetch_crop(base, int(x0), int(y0), w, h, size=min(2400, w)).save(f'{OUT}/{year}.jpg')
fetch_crop(SHEETS['1930'], 2900, 9300, 1300, 1700, size=1300).save(f'{OUT}/1930_inset.jpg')
