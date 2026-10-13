#!/usr/bin/env python3
"""Binary source-pixel mask -> reviewable GeoJSON. Writes to DB only with --apply.

Holes survive the local artifact. The current table accepts an exterior ring
only, so --apply refuses any polygon with holes instead of silently filling it.
Feature kind is explicit: connectedness alone cannot tell a basin from a canal.
"""
import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import uuid

import numpy as np


def vectorize(mask, kind, minimum=100, tolerance=1.0):
    import cv2
    from shapely.geometry import Polygon, mapping
    binary = (np.asarray(mask) > 0).astype(np.uint8)
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    features = []
    if hierarchy is None:
        return features
    for index, contour in enumerate(contours):
        if hierarchy[0][index][3] != -1 or cv2.contourArea(contour) < minimum:
            continue
        ring = contour[:, 0, :].astype(float).tolist()
        holes = [c[:, 0, :].astype(float).tolist() for j, c in enumerate(contours)
                 if hierarchy[0][j][3] == index and len(c) >= 3]
        if len(ring) < 3:
            continue
        polygon = Polygon(ring, holes)
        simplified = polygon.simplify(tolerance, preserve_topology=True)
        # Contour geometry errors are explicit, not fixed into a different object.
        if not simplified.is_valid:
            raise ValueError(f'Invalid mask contour {index}')
        features.append({'type': 'Feature', 'geometry': mapping(simplified), 'properties': {
            'feature_type': kind, 'source_index': index, 'area_px': simplified.area,
            'review_status': 'needs_review', 'importable': not bool(simplified.interiors),
            'holes': len(simplified.interiors)}})
    return features


def write_rows(map_id, features, run_id):
    import requests
    if any(f['geometry']['type'] != 'Polygon' or len(f['geometry']['coordinates']) != 1 for f in features):
        raise ValueError('Storage cannot preserve holes/MultiPolygons. Resolve them before --apply.')
    url, key = os.environ.get('PUBLIC_SUPABASE_URL'), os.environ.get('SUPABASE_SERVICE_KEY')
    if not url or not key:
        raise ValueError('Explicit import needs PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY')
    rows = [{'map_id': map_id, 'pixel_polygon': f['geometry']['coordinates'][0],
             'feature_type': f['properties']['feature_type'], 'source': 'import',
             'review_status': 'needs_review', 'run_id': run_id} for f in features]
    if rows:
        response = requests.post(f'{url.rstrip("/")}/rest/v1/footprints', json=rows,
            headers={'apikey': key, 'Authorization': f'Bearer {key}', 'Prefer': 'return=minimal'}, timeout=60)
        response.raise_for_status()


def self_check():
    mask = np.zeros((100, 100), np.uint8)
    mask[10:90, 10:90] = 1; mask[30:60, 30:60] = 0
    features = vectorize(mask, 'water_body')
    assert len(features) == 1 and len(features[0]['geometry']['coordinates']) == 2
    assert not features[0]['properties']['importable']
    solid = vectorize(np.pad(np.ones((20, 20), np.uint8), 5), 'parcel')
    assert len(solid) == 1 and solid[0]['properties']['importable']
    print('mask contour export self-check passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mask'); parser.add_argument('--map-id'); parser.add_argument('--out')
    parser.add_argument('--feature-type', default='waterway', choices=['parcel', 'land_plot', 'building', 'road', 'waterway', 'water_body', 'green_space', 'other'])
    parser.add_argument('--min-area', type=float, default=100)
    parser.add_argument('--tolerance', type=float, default=1)
    parser.add_argument('--run-id'); parser.add_argument('--apply', action='store_true')
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    if args.self_check: return self_check()
    if not args.mask or not args.out: parser.error('--mask and --out are required')
    if args.min_area < 0 or not np.isfinite(args.min_area) or args.tolerance < 0 or not np.isfinite(args.tolerance):
        parser.error('Area/tolerance must be finite and nonnegative')
    if args.apply and not args.map_id: parser.error('--apply needs --map-id')
    if args.map_id: uuid.UUID(args.map_id)
    from PIL import Image
    image = Image.open(args.mask).convert('L')
    features = vectorize(np.asarray(image) > 127, args.feature_type, args.min_area, args.tolerance)
    run_id = args.run_id or f'mask-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}'
    output = {'type': 'FeatureCollection', 'crs': 'source-pixels-y-down', 'features': features,
              'map_id': args.map_id, 'run_id': run_id, 'source_size': list(image.size)}
    path = Path(args.out); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2))
    print(f'{len(features)} proposals saved locally to {path}')
    if args.apply: write_rows(args.map_id, features, run_id)


if __name__ == '__main__': main()
