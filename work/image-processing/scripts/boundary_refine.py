#!/usr/bin/env python3
"""Experimental text-aware boundary refinement of pinned colour proposals.

Works on a bounded region, never writes the DB. OCR boxes locate potential text;
long straight strokes crossing each box are retained as boundary evidence. The
output flags weak support and storage limitations instead of deleting objects.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw
from shapely.geometry import shape, mapping, box

from regularize_blocks import regularize, ink


def text_aware_ink(image, labels, origin=(0, 0)):
    import cv2
    rgb = np.asarray(image.convert('RGB'))
    evidence = ink(image)
    strokes = (evidence > max(4.0, float(np.percentile(evidence, 80)))).astype(np.uint8) * 255
    retained = np.zeros(strokes.shape, np.uint8)
    # Preserve long straight geometry before suppressing ink inside text boxes.
    lines = cv2.HoughLinesP(strokes, 1, np.pi / 180, threshold=15,
                           minLineLength=20, maxLineGap=3)
    if lines is not None:
        for line in lines[:, 0]:
            cv2.line(retained, tuple(line[:2]), tuple(line[2:]), 1, 3)
    text = np.zeros(strokes.shape, bool)
    ox, oy = origin
    for label in labels:
        if label.get('review_status') != 'validated':
            continue
        x, y = label.get('global_x'), label.get('global_y')
        w, h = label.get('global_w'), label.get('global_h')
        if any(v is None or not np.isfinite(v) for v in (x, y, w, h)) or w <= 0 or h <= 0:
            continue
        x0, y0 = max(0, int(x - ox)), max(0, int(y - oy))
        x1, y1 = min(rgb.shape[1], int(np.ceil(x + w - ox))), min(rgb.shape[0], int(np.ceil(y + h - oy)))
        if x1 > x0 and y1 > y0:
            text[y0:y1, x0:x1] = True
    suppressed = text & ~retained.astype(bool)
    result = evidence.copy()
    result[suppressed] = 0
    return result, {'text_region_px': int(text.sum()), 'suppressed_ink_px': int((suppressed & (evidence > 4)).sum()),
                    'retained_line_px': int((text & retained.astype(bool)).sum())}


def refine(features, image, labels, region, text_aware=True):
    x, y, w, h = region
    crop = image.crop((x, y, x + w, y + h))
    evidence, diagnostic = text_aware_ink(crop, labels, (x, y)) if text_aware else (ink(crop), {})
    output = []
    for feature in features:
        geom = shape(feature['geometry'])
        if not geom.intersects(box(x, y, x + w, y + h)):
            continue
        # Only complete candidates are refined; clipping would create artificial
        # edges that the line fitting could mistake for printed boundaries.
        if not box(x, y, x + w, y + h).covers(geom):
            output.append({**feature, 'properties': {**feature.get('properties', {}),
                          'refinement': 'outside-complete-crop', 'review_required': True}})
            continue
        revised, method = regularize(geom, crop, (x, y), ink_map=evidence)
        boundary_distance = geom.boundary.hausdorff_distance(revised.boundary)
        props = {**feature.get('properties', {}), 'refinement': method,
                 'boundary_movement_px': boundary_distance, 'review_required': True,
                 'area_px': revised.area,
                 'importable': revised.geom_type == 'Polygon' and not bool(revised.interiors)}
        output.append({'type': 'Feature', 'geometry': mapping(revised), 'properties': props})
    return output, diagnostic


def self_check():
    image = Image.new('RGB', (120, 80), 'white')
    draw = ImageDraw.Draw(image); draw.line((0, 25, 119, 25), fill='black', width=2)
    draw.text((42, 35), 'RUE', fill='black')
    labels = [{'global_x': 35, 'global_y': 15, 'global_w': 55, 'global_h': 40, 'review_status': 'validated'}]
    result, diagnostic = text_aware_ink(image, labels)
    assert result[25, 60] > 4, 'A boundary crossing a text box must survive'
    assert diagnostic['suppressed_ink_px'] > 0 and diagnostic['retained_line_px'] > 0
    print('text-aware boundary refinement self-check passed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image'); p.add_argument('--proposals'); p.add_argument('--labels')
    p.add_argument('--region'); p.add_argument('--out'); p.add_argument('--no-text-aware', action='store_true')
    p.add_argument('--sheet', choices=['1882', '1898'], default='1882', help='Apply the existing unseen-window guard before reading crop pixels')
    p.add_argument('--self-check', action='store_true')
    args = p.parse_args()
    if args.self_check: return self_check()
    if not all((args.image, args.proposals, args.labels, args.region, args.out)):
        p.error('--image, --proposals, --labels, --region and --out are required')
    region = tuple(int(v) for v in args.region.split(','))
    if len(region) != 4 or min(region[:2]) < 0 or min(region[2:]) <= 0:
        p.error('--region must be positive source-pixel x,y,w,h')
    import importlib.util
    guard_path = Path(__file__).resolve().parents[1] / 'experiments/river-reference/view.py'
    spec = importlib.util.spec_from_file_location('blind_view', guard_path)
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    if guard.touches(region, args.sheet):
        p.error('Region touches an unseen held-out river/road window')
    image = Image.open(args.image).convert('RGB')
    if region[0] + region[2] > image.width or region[1] + region[3] > image.height:
        p.error('Region is outside the scan')
    proposals = json.loads(Path(args.proposals).read_text())
    if proposals.get('crs') != 'source-pixels-y-down': p.error('Proposals must declare source-pixels-y-down')
    labels = json.loads(Path(args.labels).read_text())
    output, diagnostic = refine(proposals['features'], image, labels, region, not args.no_text_aware)
    manifest = {name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                for name, path in [('image', args.image), ('proposals', args.proposals), ('labels', args.labels)]}
    path = Path(args.out); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'type': 'FeatureCollection', 'crs': 'source-pixels-y-down', 'features': output,
                    'provenance': manifest, 'region': region, 'text_aware': not args.no_text_aware,
                    'diagnostic': diagnostic}, indent=2))
    print(f'{len(output)} review proposals saved locally to {path}')


if __name__ == '__main__': main()
