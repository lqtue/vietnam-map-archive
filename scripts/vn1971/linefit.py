"""linefit.py [NN ...]: how far each stored GCP sits from the printed grid line, measured on the scan.
For each GCP, the darkest column in a +-60 px window of the vertical line (rows 30-150 px away from the
crossing, so the crossing itself is not in it) and likewise the row. Prints median and 90th percentile
per axis, in px and in metres on the ground. A rough check, not a gate: other dark features can win."""
import json, re, sys, numpy as np
from PIL import Image
from common import WORK
Image.MAX_IMAGE_PIXELS = None
scale = {}
for line in open(WORK + 'list.tsv'):
    j = json.loads(line.split('\t')[3]); scale[j['sheet_number']] = int(re.sub(r'\D', '', j['scale'].split(':')[1])) / 1000
for n in sys.argv[1:] or [f'{i:02d}' for i in range(1, 45)]:
    im = np.asarray(Image.open(WORK + f'up/{n}.jpg').convert('L'), dtype=np.float32)
    dx, dy = [], []
    for p in json.load(open(WORK + f'grid/gcp{n}.json')):
        x, y = map(int, p['px'])
        if not (200 < x < im.shape[1] - 200 and 200 < y < im.shape[0] - 200):
            continue
        dx.append(np.argmin(np.r_[im[y-150:y-30, x-60:x+61], im[y+30:y+150, x-60:x+61]].mean(0)) - 60)
        dy.append(np.argmin(np.c_[im[y-60:y+61, x-150:x-30], im[y-60:y+61, x+30:x+150]].mean(1)) - 60)
    m_px = 10000 / (2354 * 100 / scale[n])  # metres per px
    a, b = np.abs(dx), np.abs(dy)
    print(f'{n} {len(dx):4d}  x {np.median(a):4.0f} / {np.percentile(a, 90):4.0f} px   y {np.median(b):4.0f} / {np.percentile(b, 90):4.0f} px   = {max(np.median(a), np.median(b)) * m_px:5.0f} m median')
