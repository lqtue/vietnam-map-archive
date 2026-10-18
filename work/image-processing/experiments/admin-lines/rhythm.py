"""Find dash-dot boundary lines by their rhythm: an oriented complex filter tuned to the line's period.
Phase-free (complex magnitude), zero-mean along the line (solid lines score ~0), thin across it.
Usage: OCR=<ocr boxes.json> rhythm.py <image> <out.jpg> <period px> [x0,y0,x1,y1] [score cut] [density gate]
ponytail: one period per run; a trained line-type model is the upgrade (README)."""
import sys, time, numpy as np
from PIL import Image
from scipy.signal import oaconvolve
from scipy import ndimage as ndi
src, out = sys.argv[1], sys.argv[2]
P = float(sys.argv[3]) if len(sys.argv) > 3 else 23.0     # period in px, measured from clean chains
crop = tuple(map(int, sys.argv[4].split(','))) if len(sys.argv) > 4 else None
Image.MAX_IMAGE_PIXELS = None
im = Image.open(src).convert('RGB')
if crop: im = im.crop(crop)
rgb = np.asarray(im).astype(np.float32)
r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
mean = (r + g + b) / 3; paper = np.median(mean)
chroma = rgb.max(-1) - rgb.min(-1)
ink = np.clip((paper - mean) / 90, 0, 1) * (chroma < 60)    # grey/black ink only: drops blue water, pink wash
# blank out text: OCR boxes (same full-image pixel grid), rotated, padded
import json, os
from PIL import ImageDraw
ocr = os.environ.get('OCR')
if ocr:
    tm = Image.new('L', im.size, 0); dr = ImageDraw.Draw(tm)
    ox, oy = (crop[0], crop[1]) if crop else (0, 0)
    for o in json.load(open(ocr)):
        if max(o['global_w'], o['global_h']) > 450: continue      # spaced canton names: box covers villages
        x, y, w, h = o['global_x'] - ox, o['global_y'] - oy, o['global_w'], o['global_h']
        a = np.radians(o.get('rotation_deg') or 0); cx_, cy_ = x + w / 2, y + h / 2
        pts = [(-w / 2 - 8, -h / 2 - 8), (w / 2 + 8, -h / 2 - 8), (w / 2 + 8, h / 2 + 8), (-w / 2 - 8, h / 2 + 8)]
        dr.polygon([(cx_ + px * np.cos(a) - py * np.sin(a), cy_ + px * np.sin(a) + py * np.cos(a)) for px, py in pts], fill=255)
    ink[np.asarray(tm) > 0] = 0
NT, half = 16, int(2 * P)
yy, xx = np.mgrid[-half:half + 1, -half:half + 1].astype(np.float32)
best = np.zeros(ink.shape, np.float32); arg = np.zeros(ink.shape, np.int8)
t0 = time.time()
for k in range(NT):
    th = np.pi * k / NT; c, s = np.cos(th), np.sin(th)
    along = xx * c + yy * s; across = -xx * s + yy * c
    win = np.exp(-0.5 * (along / (0.9 * P)) ** 2)
    prof = np.exp(-0.5 * (across / 1.3) ** 2) - 0.5 * (np.exp(-0.5 * ((across - 5) / 1.3) ** 2) + np.exp(-0.5 * ((across + 5) / 1.3) ** 2))
    kr = win * prof * np.cos(2 * np.pi * along / P); ki = win * prof * np.sin(2 * np.pi * along / P)
    kr -= kr.mean(); ki -= ki.mean()
    ke = win * np.exp(-0.5 * (across / 1.3) ** 2)                     # plain ink along the line, no rhythm
    amp = np.hypot(oaconvolve(ink, kr, mode='same'), oaconvolve(ink, ki, mode='same'))
    energy = oaconvolve(ink, ke, mode='same')
    # share of the line's ink that follows the rhythm; needs some ink (a few dashes) to count
    resp = (amp / (energy + 0.15 * ke.sum() * 0.2)) * (energy > 0.15 * ke.sum() * 0.2)
    m = resp > best; best[m] = resp[m]; arg[m] = k
print('filtered in %.0fs' % (time.time() - t0))
# thin ridge: keep pixels that beat both neighbours across the line
nms = np.zeros_like(best, bool)
for k in range(NT):
    th = np.pi * k / NT; dx, dy = int(round(-np.sin(th) * 2)), int(round(np.cos(th) * 2))
    a = np.roll(best, (dy, dx), (0, 1)); b2 = np.roll(best, (-dy, -dx), (0, 1))
    nms |= (arg == k) & (best >= a) & (best >= b2)
# dense ink (city blocks, text clusters) is not a lone boundary line
dens = ndi.uniform_filter(ink, size=int(2 * P))
gate = float(sys.argv[6]) if len(sys.argv) > 6 else 0.12
best[dens > gate] = 0
thr = float(sys.argv[5]) if len(sys.argv) > 5 else np.percentile(best, 99.0)
ridge = nms & (best > thr)
ridge = ndi.binary_closing(ridge, structure=np.ones((3, 3)), iterations=2)
lab, n = ndi.label(ridge, structure=np.ones((3, 3)))
objs = ndi.find_objects(lab); keep = np.zeros(n + 1, bool)
for i, sl in enumerate(objs, 1):
    if max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) >= 3 * P: keep[i] = True
ridge = keep[lab]
print('threshold %.4f  segments kept %d of %d' % (thr, keep.sum(), n))
base = (rgb * 0.35 + 255 * 0.65).astype(np.uint8)
base[ndi.binary_dilation(ridge, iterations=2)] = (200, 0, 60)
Image.fromarray(base).save(out, quality=88)
np.save(out.replace('.jpg', '_score.npy'), best)
