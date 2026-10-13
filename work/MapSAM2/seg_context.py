"""Explicit map metadata for controlled segmentation experiments.

SAM2 does not consume prose. This context changes declared target/prompt/area
settings and proposes legend categories for review; it is not a text encoder.
"""
import hashlib
import json
import math
from pathlib import Path

TARGETS = {'parcel', 'land_plot', 'building', 'waterway', 'water_body', 'road', 'green_space', 'other'}
FIELDS = {'map_id', 'source_size', 'target_feature_type', 'mpp', 'min_area_m2', 'max_area_m2',
          'prompt', 'pick', 'legend', 'name', 'year', 'map_type', 'scale_denominator', 'provenance'}


def load_context(path, map_id, source_size):
    context = json.loads(Path(path).read_text())
    if not isinstance(context, dict) or set(context) - FIELDS:
        raise ValueError('Context must be an object using the documented fields')
    if context.get('map_id') != map_id or context.get('source_size') != list(source_size):
        raise ValueError('Context map/scan identity does not match this input')
    if context.get('target_feature_type') not in TARGETS:
        raise ValueError('Context must declare a supported target_feature_type')
    for key in ('mpp', 'min_area_m2', 'max_area_m2', 'scale_denominator'):
        value = context.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0):
            raise ValueError(f'{key} must be finite and positive')
    if any(k in context for k in ('min_area_m2', 'max_area_m2')) and 'mpp' not in context:
        raise ValueError('Area bounds need source-pixel mpp; printed scale alone is insufficient')
    if context.get('min_area_m2', 0) >= context.get('max_area_m2', float('inf')):
        raise ValueError('min_area_m2 must be smaller than max_area_m2')
    if context.get('prompt', 'box') not in ('box', 'point', 'box+point') or context.get('pick', 'score') not in ('score', 'largest'):
        raise ValueError('Unknown prompt/mask selection setting')
    for swatch in context.get('legend', []):
        if not isinstance(swatch, dict) or not isinstance(swatch.get('category'), str) or not swatch['category']:
            raise ValueError('Each legend swatch needs a category')
        rgb = swatch.get('rgb')
        if not isinstance(rgb, list) or len(rgb) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 255 for v in rgb):
            raise ValueError('Legend RGB must contain three values in [0,255]')
    canonical = json.dumps(context, sort_keys=True, separators=(',', ':'))
    return context, hashlib.sha256(canonical.encode()).hexdigest()


def mask_area_bounds(context, scale_x, scale_y):
    if not context or not context.get('mpp'):
        return 400, 200_000
    per_pixel = context['mpp'] ** 2 * scale_x * scale_y
    return (context.get('min_area_m2', 400 * per_pixel) / per_pixel,
            context.get('max_area_m2', 200_000 * per_pixel) / per_pixel)


def legend_suggestion(rgb, mask, context):
    import numpy as np
    if not context or not context.get('legend') or not np.asarray(mask).any():
        return None
    median = np.median(rgb[np.asarray(mask, bool)], axis=0)
    swatches = context['legend']
    distances = [float(np.linalg.norm(median - np.asarray(s['rgb']))) for s in swatches]
    index = int(np.argmin(distances))
    return {'category': swatches[index]['category'], 'rgb_distance': distances[index],
            'method': 'median-colour-nearest-swatch', 'review_required': True}


def self_check():
    assert mask_area_bounds({'mpp': 0.5, 'min_area_m2': 100, 'max_area_m2': 200}, 2, 2) == (100, 200)
    assert mask_area_bounds(None, 2, 2) == (400, 200_000)
    print('segmentation context self-check passed')


if __name__ == '__main__':
    self_check()
