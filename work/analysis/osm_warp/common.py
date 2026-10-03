"""Shared paths and masks for the OSM warp. Source pixels throughout unless a name ends in _q (quarter res)."""
import sys, json, math
import numpy as np
from pathlib import Path
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
WT = Path('/Users/airm1/Work/Projects/vma-1882-river')
MAIN = Path('/Users/airm1/Work/Projects/vietnam-map-archive')
SP = Path('/private/tmp/claude-501/-Users-airm1-Work-Projects-vietnam-map-archive/dc485793-f248-4d00-8d74-cf940ff84a86/scratchpad/osm_warp')
SP.mkdir(exist_ok=True, parents=True)
HERE = Path(__file__).resolve().parent
MID = '0e02b9d9-9d40-4cca-8e41-8c8373d54d3b'
OUT = WT / 'work/ocr/outputs' / MID
STREETS = MAIN / 'work/image-processing/results/prior' / MID / 'streets.geojson'
W = json.loads((WT / 'work/analysis/river_ref/windows.json').read_text())
S1882 = W['sheets']['1882']
MPP = 0.3416
Q = 4                      # quarter-res factor
H, WD = S1882['height'], S1882['width']
HQ, WQ = -(-H // Q), -(-WD // Q)
# every seen:false window, calibrate and heldout (conservative reading of rule 1)
BLIND = [w['box'] for w in W['windows'] if w['sheet'] == '1882' and not w['seen']]
BLIND_PAD_INK = 8          # px blanked around a box before anything is computed
KERNEL_PAD = 140           # px: Q within this of a box depends on blanked pixels -> NaN
SHIFT_MAX = 96             # px: largest shift the search may try
def boxes_mask_q(pad):
    m = np.zeros((HQ, WQ), bool)
    for bx, by, bw, bh in BLIND:
        m[max(0, (by - pad) // Q):-(-(by + bh + pad) // Q), max(0, (bx - pad) // Q):-(-(bx + bw + pad) // Q)] = True
    return m
def in_boxes(x, y, pad):
    m = np.zeros(len(x), bool)
    for bx, by, bw, bh in BLIND:
        m |= (x >= bx - pad) & (x < bx + bw + pad) & (y >= by - pad) & (y < by + bh + pad)
    return m
def neatline():
    return S1882.get('road', {}).get('neatline', S1882['neatline'])
def furniture_boxes(pad):
    return [[b[0] - pad, b[1] - pad, b[2] + 2 * pad, b[3] + 2 * pad] for b in S1882['furniture'].values()]
