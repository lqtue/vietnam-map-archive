"""Semap Mask2Former, zero-shot, with cleaner inputs: overlapping windows, two scales, text erased.

Two subcommands, one file.

  prepare   (local, read-only)  Fetch each target's tile plus a 512 px margin from IIIF at full
            resolution; for the 1882 sheet also fetch the OCR boxes (ocr_labels, run post0910,
            anon key, GET only), paint them out with cv2 TELEA (export_tiles.py's approach).
            Writes <out>/<name>_raw.png, <name>_clean.png (1882 only), <name>_ocr.json, jobs.json.
              PYTHONPATH=work/core python infer_tiled.py prepare --out DIR

  run       (Colab, inside the mmseg venv)  For every image in jobs.json and each variant:
            windows of 1024 px, stride 512, probabilities blended with a centre-weighted window;
            run at scale 1.0 and 0.5 and average. Writes, cropped to the target tile,
            <name>_probs.npz (float16, 6xHxW), <name>_cls.png, <name>_overlay.jpg, shares.json.
              MPLBACKEND=Agg /content/mm/bin/python infer_tiled.py run --root /content/tiled

Reserved 1882 test windows R1 and R2 are never fetched: prepare asserts no region touches them.
Classes: 0 background, 1 contours, 2 built, 3 non-built, 4 water, 5 road_network.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

NAMES = ['background', 'contours', 'built', 'non-built', 'water', 'road']
COLORS = np.array([[255, 255, 255], [0, 0, 0], [220, 40, 40], [240, 200, 120], [60, 140, 230], [150, 150, 150]], np.uint8)

MAP_1882 = '0e02b9d9-9d40-4cca-8e41-8c8373d54d3b'
MAP_1959 = '34d4edb2-f7df-4c47-a65a-f6b471400396'
IIIF = 'https://iiif.maparchive.vn/iiif/'
SIZE_1882 = (12102, 8982)
RESERVED = {'R1': (4760, 4790, 600, 600), 'R2': (8500, 2590, 600, 600)}
OCR_RUN = 'post0910'
PAD = 512
# name, sheet, tile box (x, y, w, h), erase text
TARGETS = [
    ('1882_t01', '1882', (6300, 2610, 1024, 1024), True),
    ('1882_t06', '1882', (2520, 3760, 1024, 1024), True),
    ('1959_d1', '1959', (9300, 2700, 2048, 2048), False),
]
WIN, STRIDE = 1024, 512


def overlaps(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


# ── prepare (local) ──────────────────────────────────────────────────────────

def _env(path: str) -> dict:
    out = {}
    for line in open(path):
        if '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            out[k] = v.strip('"\'')
    return out


def fetch_ocr(env_path: str) -> list[dict]:
    import requests
    e = _env(env_path)
    url, key = e['PUBLIC_SUPABASE_URL'], e['PUBLIC_SUPABASE_ANON_KEY']
    h = {'apikey': key, 'Authorization': f'Bearer {key}'}
    sel = 'id,text,category,review_status,global_x,global_y,global_w,global_h,label_w,label_h,rotation_deg'
    out: list[dict] = []
    while True:  # GET only
        r = requests.get(f'{url}/rest/v1/ocr_labels?map_id=eq.{MAP_1882}&run_id=eq.{OCR_RUN}&select={sel}&order=id&limit=1000&offset={len(out)}', headers=h, timeout=60)
        r.raise_for_status()
        page = r.json()
        out += page
        if len(page) < 1000:
            return out


def no_holes(arr: np.ndarray, block: int = 256) -> None:
    h, w = arr.shape[:2]
    for y in range(0, h, block):
        for x in range(0, w, block):
            if (arr[y:y + block, x:x + block] >= 254).all():
                raise SystemExit(f'all-white {block} px block at ({x},{y}): missing IIIF tile, run again')


def prepare(args) -> None:
    import requests
    here = Path(__file__).resolve()
    repo = here.parents[3]
    sys.path.insert(0, str(repo / 'work' / 'core'))
    sys.path.insert(0, str(repo / 'work' / 'MapSAM2' / 'tiles_1882'))
    from vma_core import iiif
    import export_tiles as et  # ocr_mask (oriented rectangles, group boxes skipped, 3 px dilation) and inpaint (TELEA)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sizes = {'1882': SIZE_1882}
    info = requests.get(f'{IIIF}{MAP_1959}/info.json', timeout=30).json()
    sizes['1959'] = (info['width'], info['height'])
    print('sheet sizes', sizes)
    ocr = fetch_ocr(args.env)
    print(len(ocr), 'OCR rows', OCR_RUN)
    jobs = []
    for name, sheet, tile, erase in TARGETS:
        W, H = sizes[sheet]
        x0, y0 = max(0, tile[0] - PAD), max(0, tile[1] - PAD)
        x1, y1 = min(W, tile[0] + tile[2] + PAD), min(H, tile[1] + tile[3] + PAD)
        region = (x0, y0, x1 - x0, y1 - y0)
        if sheet == '1882':
            for rn, rw in RESERVED.items():
                assert not overlaps(region, rw), f'{name} region {region} touches reserved window {rn}'
        base = IIIF + (MAP_1882 if sheet == '1882' else MAP_1959)
        im = iiif.fetch_crop(base, *region, size=region[2])
        assert im.size == (region[2], region[3]), (im.size, region)
        arr = np.array(im.convert('RGB'))
        no_holes(arr)
        Image.fromarray(arr).save(out / f'{name}_raw.png')
        files = {'raw': f'{name}_raw.png'}
        if erase:
            m, n = et.ocr_mask(ocr, region)
            clean = et.inpaint(arr, m)
            Image.fromarray(clean).save(out / f'{name}_clean.png')
            Image.fromarray(m).save(out / f'{name}_ocrmask.png')
            files['clean'] = f'{name}_clean.png'
            print(name, 'OCR boxes painted', n, f'mask share {float((m > 0).mean()):.3f}')
        jobs.append({'name': name, 'sheet': sheet, 'region': region, 'tile': tile,
                     'tile_in_region': [tile[0] - x0, tile[1] - y0, tile[2], tile[3]], 'files': files})
        print(name, 'region', region, arr.shape)
    json.dump(ocr, open(out / 'ocr_labels_1882_post0910.json', 'w'))
    json.dump(jobs, open(out / 'jobs.json', 'w'), indent=1)


# ── run (Colab) ──────────────────────────────────────────────────────────────

def load_model():
    from mmengine import Config
    from mmseg.apis import init_model
    root = '/content/semap'
    cfg = Config.fromfile(glob.glob(f'{root}/**/*.py', recursive=True)[0])
    ckpt = glob.glob(f'{root}/**/*.pth', recursive=True)[0]
    cfg.model.backbone.init_cfg = None
    return init_model(cfg, ckpt, device='cuda:0')


def starts(n: int) -> list[int]:
    if n <= WIN:
        return [0]
    s = list(range(0, n - WIN + 1, STRIDE))
    if s[-1] != n - WIN:
        s.append(n - WIN)
    return s


def window_weight() -> np.ndarray:
    t = (np.arange(WIN) + 0.5) / WIN
    w1 = 0.02 + np.sin(np.pi * t) ** 2  # low at the window edge, high in the middle
    return np.outer(w1, w1).astype(np.float32)


def to_probs(seg: np.ndarray) -> np.ndarray:
    """mmseg's Mask2Former head returns class-score x mask-sigmoid, already in [0, 1], not logits.
    Then normalise to sum 1 (argmax unchanged); real logits get a softmax."""
    if seg.min() >= 0 and seg.max() <= 1.0 + 1e-4:
        return seg / np.maximum(seg.sum(0, keepdims=True), 1e-6)
    e = np.exp(seg - seg.max(0, keepdims=True))
    return e / e.sum(0, keepdims=True)


def window_probs(model, bgr: np.ndarray) -> np.ndarray:
    from mmseg.apis import inference_model
    res = inference_model(model, bgr)  # an ndarray is read as BGR, like mmcv.imread
    return to_probs(res.seg_logits.data.float().cpu().numpy())


def slide(model, rgb: np.ndarray) -> np.ndarray:
    """Centre-weighted average of softmax probs over 1024 px windows, stride 512. (6,H,W) float32."""
    import cv2
    H, W = rgb.shape[:2]
    ph, pw = max(0, WIN - H), max(0, WIN - W)
    if ph or pw:
        rgb = cv2.copyMakeBorder(rgb, 0, ph, 0, pw, cv2.BORDER_REFLECT_101)
    HH, WW = rgb.shape[:2]
    acc = np.zeros((6, HH, WW), np.float32)
    wsum = np.zeros((HH, WW), np.float32)
    ww = window_weight()
    for y in starts(HH):
        for x in starts(WW):
            p = window_probs(model, np.ascontiguousarray(rgb[y:y + WIN, x:x + WIN, ::-1]))
            acc[:, y:y + WIN, x:x + WIN] += p * ww
            wsum[y:y + WIN, x:x + WIN] += ww
    return (acc / wsum)[:, :H, :W]


def multiscale(model, rgb: np.ndarray, scales=(1.0, 0.5)) -> np.ndarray:
    import cv2
    H, W = rgb.shape[:2]
    out = np.zeros((6, H, W), np.float32)
    for s in scales:
        im = rgb if s == 1.0 else cv2.resize(rgb, (round(W * s), round(H * s)), interpolation=cv2.INTER_AREA)
        p = slide(model, im)
        if s != 1.0:
            p = np.stack([cv2.resize(c, (W, H), interpolation=cv2.INTER_LINEAR) for c in p])
        out += p / len(scales)
    return out


def run(args) -> None:
    import cv2
    from mmseg.apis import inference_model
    root = Path(args.root)
    outd = root / args.outdir
    scales = tuple(float(v) for v in args.scales.split(','))
    outd.mkdir(exist_ok=True)
    model = load_model()
    print('classes:', model.dataset_meta.get('classes'))
    jobs = json.load(open(root / 'jobs.json'))

    # Sanity: an ndarray window must give the same answer as the same file read by path.
    j = jobs[0]
    rgb = np.array(Image.open(root / j['files']['raw']).convert('RGB'))
    Image.fromarray(rgb[:WIN, :WIN]).save('/content/_chk.png')
    a = inference_model(model, '/content/_chk.png')
    b = inference_model(model, np.ascontiguousarray(rgb[:WIN, :WIN, ::-1]))
    agree = float((a.pred_sem_seg.data == b.pred_sem_seg.data).float().mean())
    sl = a.seg_logits.data
    print('ndarray(BGR) vs path agreement', agree, '| seg_logits', tuple(sl.shape), float(sl.min()), float(sl.max()), 'sum(0) mean', float(sl.sum(0).mean()))
    assert agree > 0.99, 'channel order mismatch'

    shares = {}
    t_all = time.time()
    for j in jobs:
        tx, ty, tw, th = j['tile_in_region']
        for variant, key in (('text', 'clean'), ('notext', 'raw')) if 'clean' in j['files'] else (('', 'raw'),):
            t0 = time.time()
            nm = f"{j['name']}_{args.tag}" + (f'_{variant}' if variant else '')
            rgb = np.array(Image.open(root / j['files'][key]).convert('RGB'))
            raw = np.array(Image.open(root / j['files']['raw']).convert('RGB'))
            p = multiscale(model, rgb, scales)[:, ty:ty + th, tx:tx + tw]
            cls = p.argmax(0).astype(np.uint8)
            np.savez_compressed(outd / f'{nm}_probs.npz', probs=p.astype(np.float16))
            Image.fromarray(cls).save(outd / f'{nm}_cls.png')
            img = raw[ty:ty + th, tx:tx + tw]
            over = (0.45 * img + 0.55 * COLORS[cls]).astype(np.uint8)
            Image.fromarray(np.concatenate([img, over], axis=1)).save(outd / f'{nm}_overlay.jpg', quality=88)
            shares[nm] = {NAMES[i]: round(float((cls == i).mean()), 3) for i in range(6)}
            print(nm, shares[nm], f'{time.time() - t0:.0f}s', flush=True)
    json.dump(shares, open(outd / 'shares.json', 'w'), indent=1)
    print('total', f'{time.time() - t_all:.0f}s')


def main() -> None:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('prepare')
    p.add_argument('--out', required=True)
    p.add_argument('--env', default='/Users/airm1/Work/Projects/vietnam-map-archive/.env')
    r = sp.add_parser('run')
    r.add_argument('--root', default='/content/tiled')
    r.add_argument('--scales', default='1.0,0.5', help='comma list; "1.0" gives windows only, one scale')
    r.add_argument('--tag', default='ms', help='name part after the sheet/tile, e.g. ms or w1')
    r.add_argument('--outdir', default='out')
    a = ap.parse_args()
    {'prepare': prepare, 'run': run}[a.cmd](a)


if __name__ == '__main__':
    main()
