#!/usr/bin/env python3
"""Create an uploadable, no-write Colab bundle from an explicit source allowlist.

Optional --snapshot exports live 1882 inputs read-only. No service/worker key,
reference traces, private docs or unrelated work enters the archive.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
MAP_ID = '0e02b9d9-9d40-4cca-8e41-8c8373d54d3b'
SOURCES = [
    *[f'work/MapSAM2/{name}' for name in ('inference_tiles_as_video.py', 'memory_predictor.py',
        'seg_context.py', 'masks_to_polygons.py', 'to_sam2_seeds.py')],
    *[f'work/ocr/scripts/{name}' for name in ('iiif_tiles.py', 'scale.py')],
]


def fetch_rows(table, params):
    import requests
    url = os.environ['PUBLIC_SUPABASE_URL'].rstrip('/')
    key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ['PUBLIC_SUPABASE_ANON_KEY']
    rows = []
    for offset in range(0, 1_000_000, 1000):
        response = requests.get(f'{url}/rest/v1/{table}', params={**params, 'limit': 1000, 'offset': offset},
            headers={'apikey': key, 'Authorization': f'Bearer {key}'}, timeout=60)
        response.raise_for_status()
        page = response.json(); rows.extend(page)
        if len(page) < 1000: return rows
    raise RuntimeError('Unexpectedly large snapshot; refusing an incomplete export')


def normalize_prior(path, target, declared_crs=None):
    raw = path.read_bytes()
    document = json.loads(raw)
    document['comparison_input_sha256'] = hashlib.sha256(raw).hexdigest()
    if document.get('crs') is None and declared_crs == 'source-pixels-y-down':
        document.update(crs=declared_crs, crs_declared_by_bundle=True)
    if document.get('crs') != 'source-pixels-y-down':
        raise ValueError(f'{path}: prior must explicitly use source pixels')
    output = []
    for index, feature in enumerate(document.get('features', [])):
        props = feature.get('properties', {})
        if props.get('feature_type') == 'building': continue
        output.append({**feature, 'properties': {**props, 'candidate_id': str(props.get('id', props.get('source_index', index))),
            'original_feature_type': props.get('feature_type'), 'feature_type': target,
            'target_declared_by_comparison': True, 'review_required': True}})
    return {**document, 'features': output, 'target': target}


def prepare(args):
    output = Path(args.out).resolve(); output.mkdir(parents=True, exist_ok=True)
    inputs = output / 'inputs'; inputs.mkdir(exist_ok=True)
    previous = json.loads((output / 'manifest.json').read_text()) if args.reuse_snapshot else None
    if previous:
        for name in previous['files']:
            if name.startswith('inputs/') and hashlib.sha256((output / name).read_bytes()).hexdigest() != previous['files'][name]:
                raise ValueError(f'{name}: frozen input changed; establish a new experiment directory')
    priors = {}
    for name, supplied in [('colour', args.prior), ('then-now', args.then_now)]:
        if supplied:
            source = Path(supplied).resolve()
            document = normalize_prior(source, 'parcel', args.prior_crs if name == 'colour' else None)
            if previous and (name not in previous['priors'] or document['comparison_input_sha256'] != previous['priors'][name]['original_sha256']):
                raise ValueError(f'{name}: prior changed; establish a new experiment directory')
            destination = inputs / f'{name}.geojson'
            destination.write_text(json.dumps(document))
            priors[name] = {'path': f'inputs/{name}.geojson',
                'original_sha256': document['comparison_input_sha256'],
                'method': document.get('method', name)}
    if previous:
        priors = {**previous['priors'], **priors}
    if not priors: raise ValueError('Supply at least one --prior or --then-now source')
    metadata = {'map_id': args.map_id, 'source_size': [12102, 8982], 'target_feature_type': 'parcel',
        'name': '1882 Saigon cadastral plan', 'year': 1882, 'map_type': 'cadastral',
        'mpp': 0.3416, 'prompt': 'box+point', 'pick': 'largest',
        'provenance': '1882 source grid and existing plan; prompt policy is an experiment, not a fact'}
    snapshot_info = None
    if args.reuse_snapshot:
        metadata = json.loads((inputs / 'context.json').read_text())
        if previous['map_id'] != args.map_id or metadata['map_id'] != args.map_id:
            raise ValueError('Saved snapshot belongs to another map')
        snapshot_info = previous.get('snapshot')
    if args.snapshot:
        maps = fetch_rows('maps', {'id': f'eq.{args.map_id}', 'select': 'id,name,year,map_type,iiif_image'})
        if len(maps) != 1: raise ValueError('Map snapshot is missing or ambiguous')
        snapshot_info = maps[0]
        sys_path = str(ROOT / 'work/ocr/scripts')
        import sys
        sys.path.insert(0, sys_path)
        from iiif_tiles import get_image_info
        info = get_image_info(snapshot_info['iiif_image'])
        metadata.update(source_size=[info['width'], info['height']], name=snapshot_info['name'],
                        year=snapshot_info['year'], map_type=snapshot_info['map_type'])
        if metadata['source_size'] != [12102, 8982]:
            raise ValueError('1882 scan changed; re-establish metadata and priors instead of reusing old pixels')
        labels = fetch_rows('ocr_labels', {'map_id': f'eq.{args.map_id}', 'review_status': 'eq.validated',
            'select': 'id,run_id,global_x,global_y,global_w,global_h,review_status', 'order': 'id.asc'})
        (inputs / 'reviewed-labels.json').write_text(json.dumps(labels))
        footprints = fetch_rows('footprints', {'map_id': f'eq.{args.map_id}',
            'select': 'id,run_id,source,review_status,feature_type,pixel_polygon,updated_at,reviewed_at', 'order': 'id.asc'})
        # Correction snapshot stays local and is intentionally excluded from the
        # GPU bundle; it is not a training/reference source.
        (output / 'footprints.original.json').write_text(json.dumps(footprints))
        snapshot_info['footprints_count'] = len(footprints)
        snapshot_info['reviewed_label_count'] = len(labels)
    (inputs / 'context.json').write_text(json.dumps(metadata, indent=2))
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    manifest = {'map_id': args.map_id, 'source_size': metadata['source_size'], 'priors': priors,
        'iiif_base': args.iiif_base or (snapshot_info or {}).get('iiif_image'),
        'blind_boxes': [w['box'] for w in json.loads((ROOT / 'work/image-processing/experiments/river-reference/windows.json').read_text())['windows'] if w['sheet'] == '1882' and w['split'] == 'heldout' and not w['seen']],
        'regions': [], 'code_revision': revision, 'snapshot': snapshot_info,
        'sam2_revision': '2b90b9f5ceec907a1c18123530e92e794ad901a4', 'mapsam2_revision': '30110f02e23e2e804198763ab59885caa94cc7ee', 'files': {}}
    included = []
    for source in SOURCES:
        src = ROOT / source; destination = output / source
        destination.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src, destination)
        included.append(source)
    # Do not archive arbitrary files left in the output directory by a prior
    # run. Keep inputs as explicit an allowlist as source code.
    included.extend(prior['path'] for prior in priors.values())
    included.append('inputs/context.json')
    if (inputs / 'reviewed-labels.json').is_file():
        included.append('inputs/reviewed-labels.json')
    for name in included: manifest['files'][name] = hashlib.sha256((output / name).read_bytes()).hexdigest()
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    included.append('manifest.json')
    archive = output / 'vma-seg-comparison.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for name in included: tar.add(output / name, arcname=name)
    shutil.copyfile(ROOT / 'work/MapSAM2/vma_seg_comparison.ipynb', output / 'vma_seg_comparison.ipynb')
    print(f'Prepared {archive} and vma_seg_comparison.ipynb; references and secrets excluded')
    print('Set explicit development/test regions in the notebook before running.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map-id', default=MAP_ID); parser.add_argument('--prior'); parser.add_argument('--then-now')
    parser.add_argument('--prior-crs', choices=['source-pixels-y-down'], help='Explicit declaration for the known legacy colour artifact if it lost CRS metadata')
    parser.add_argument('--iiif-base'); parser.add_argument('--out', required=True)
    snapshot_options = parser.add_mutually_exclusive_group()
    snapshot_options.add_argument('--snapshot', action='store_true')
    snapshot_options.add_argument('--reuse-snapshot', action='store_true', help='Rebuild code/archive without replacing the frozen correction snapshot')
    arguments = parser.parse_args()
    if arguments.map_id != MAP_ID: parser.error('This prepared context is scoped to 1882; other maps need their own metadata')
    prepare(arguments)
