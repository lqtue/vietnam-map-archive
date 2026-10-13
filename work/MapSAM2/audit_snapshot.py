#!/usr/bin/env python3
"""Reproduce the live-import baseline from a frozen local snapshot, without DB writes.

Raw-outline similarity is provenance evidence, not accuracy against human truth.
Shapely simplification statistics are distinct from the browser preview algorithm.
"""
import argparse
import hashlib
import json
from pathlib import Path
from shapely.geometry import Polygon, shape
from shapely.strtree import STRtree


def audit(snapshot, prior):
    source = Path(snapshot); rows = json.loads(source.read_text())
    selection = {'run_id': 'colour-20260919', 'source': 'import',
                 'review_status': 'needs_review', 'feature_type': 'land_plot'}
    selected = [r for r in rows if all(r[k] == value for k, value in selection.items())]
    raw = [shape(f['geometry']) for f in json.loads(Path(prior).read_text())['features']
           if f['properties']['feature_type'] == 'land_plot']
    tree = STRtree(raw); close = 0; trials = []
    for row in selected:
        polygon = Polygon(row['pixel_polygon']); best, overlap = None, 0
        for index in tree.query(polygon, predicate='intersects'):
            candidate = raw[int(index)]; union = polygon.union(candidate).area
            value = polygon.intersection(candidate).area / union if union else 0
            if value > overlap: best, overlap = candidate, value
        close += bool(best is not None and overlap >= .999 and polygon.boundary.hausdorff_distance(best.boundary) <= 1)
    for tolerance in (2, 4, 6):
        before = after = changed = invalid = 0
        for row in selected:
            polygon = Polygon(row['pixel_polygon'])
            revised = polygon.simplify(tolerance, preserve_topology=True)
            before += len(polygon.exterior.coords) - 1; after += len(revised.exterior.coords) - 1
            changed += abs(revised.area - polygon.area) / polygon.area > .02 if polygon.area else False
            invalid += not revised.is_valid
        trials.append({'source_px': tolerance, 'vertex_reduction_percent': round(100 * (before - after) / before, 2) if before else 0,
                       'area_change_over_2_percent': changed, 'invalid_outputs': invalid})
    return {'snapshot_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'raw_prior_sha256': hashlib.sha256(Path(prior).read_bytes()).hexdigest(), 'selection': selection,
            'n': len(selected), 'near_raw_outline': close,
            'comparison': 'Best-overlap raw local plot; IoU>=0.999 and boundary Hausdorff<=1 source px',
            'trial_algorithm': 'Shapely topology-preserving simplification; differs from browser preview', 'trials': trials}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', required=True); p.add_argument('--raw-prior', required=True); p.add_argument('--out', required=True)
    args = p.parse_args()
    report = audit(args.snapshot, args.raw_prior)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(f"Audited {report['n']} live-import plots; {report['near_raw_outline']} match raw outlines under the stated rule")
