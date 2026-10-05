"""Organize local L7014 inventory evidence; never changes masters or database rows.

Run from the repository root with the OCR Python environment and --apply.
Requires the read-only Supabase snapshot produced by vma-l7014-status-audit.mjs.
Without --apply, prints the inventory plan and writes nothing.
"""
import argparse
import collections
import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO = Path(__file__).resolve().parents[3]
WORK = REPO / 'work/l7014'
OUT = WORK / 'inventory'
MAPS = Path('/Users/airm1/Work/Maps/l7014')
SCRATCH = Path('/private/tmp/claude-501/-Users-airm1-Work-Projects-vietnam-map-archive/9d6fcabb-2a12-4852-ba68-9f6d23668d1b/scratchpad')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def cell_number(text):
    match = re.search(r'(\d{4})\s*[- ]?\s*(IV|III|II|I|[1-4])\b', text)
    if not match:
        return None
    quadrant = {'I': '1', 'II': '2', 'III': '3', 'IV': '4'}.get(match[2], match[2])
    return f'{match[1]}-{quadrant}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Write local manifests and preserve scratch evidence')
    parser.add_argument('--snapshot', type=Path, default=Path('/private/tmp/vma-l7014-status-snapshot.json'))
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    pcl = json.loads((WORK / 'sheets.json').read_text())
    raw_index = json.loads((WORK / 'index.geojson').read_text())
    indexed = {cell_number(f['properties']['Sheet_no']) for f in raw_index['features']}
    ttu_roots = [WORK / 'ttu', MAPS / 'ttu']
    ttu_pdfs = sorted(f for root in ttu_roots for f in root.glob('*.pdf'))
    ttu_cells = {f.stem for f in ttu_pdfs}
    source_cells = {r['sheet'] for r in pcl} | ttu_cells | {s['sheet_number'] for s in snapshot['sources']}
    plan = {'snapshot_at': snapshot['at'], 'index_cells': len(indexed),
            'pcl_items': len(pcl), 'pcl_cells': len({r['sheet'] for r in pcl}),
            'ttu_pdf_cells': len(ttu_cells), 'available_cells': len(source_cells),
            'gaps': sorted(indexed - source_cells), 'output': str(OUT)}
    if not args.apply:
        print(json.dumps(plan, indent=2)); return

    # Preserve temporary readings and crops without changing originals or operational corner files.
    for name, source in [('survey-index.geojson', WORK / 'index.geojson'),
                         ('corrected-lattice.json', WORK / 'lattice.json'),
                         ('pcl-items.json', WORK / 'sheets.json'),
                         ('anu-catalog.json', MAPS / 'anu-sources.json')]:
        dest = OUT / 'catalogs' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    write_json(OUT / 'catalogs/database-source-items.json', snapshot['sources'])
    for source_dir, label in [('margins', 'margins'), ('prev', 'neatlines'), ('titles', 'titles')]:
        source = SCRATCH / source_dir
        for file in sorted(source.glob('*')):
            keep = (file.suffix in ('.json', '.txt') or source_dir == 'margins' and file.suffix == '.png')
            if file.is_file() and keep:
                dest = OUT / 'evidence' / label / file.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest)
    for file in SCRATCH.glob('anu-*.json'):
        dest = OUT / 'evidence/anu' / file.name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(file, dest)
    shutil.copy2(WORK / 'regen/ttu-corners.json', OUT / 'evidence/neatlines/ttu-detector.json')
    for file in WORK.glob('ttu-ingest*.txt'):
        shutil.copy2(file, OUT / 'catalogs' / file.name)

    assets = []
    cache = {}
    # Source masters and processing inputs, including both known PCL locations. Aux files are not masters.
    locations = [('PCL', 'pdf', WORK / 'pdfs', '*.pdf'), ('PCL', 'pdf', MAPS / 'pdfs', '*.pdf'),
                 ('PCL', 'jpg', MAPS / 'jpgs', '*.jpg'),
                 ('TTU', 'pdf', WORK / 'ttu', '*.pdf'), ('TTU', 'pdf', MAPS / 'ttu', '*.pdf'),
                 ('TTU', 'native', MAPS / 'ttu/native', '*.jpg'),
                 ('TTU', 'legacy-jpg', MAPS / 'ttu/jpgs', '*.jpg'),
                 ('TTU', 'stage', MAPS / 'ttu/stage', '*.jpg')]
    for institution, role, root, pattern in locations:
        for file in sorted(root.glob(pattern)):
            stat = file.stat(); identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
            if identity not in cache:
                digest = hashlib.sha256()
                with file.open('rb') as stream:
                    signature = stream.read(8); stream.seek(0)
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''): digest.update(chunk)
                valid, width, height, error = True, '', '', ''
                if file.suffix == '.pdf':
                    valid = signature.startswith(b'%PDF-')
                    if not valid: error = 'Invalid PDF signature'
                else:
                    try:
                        with Image.open(file) as image:
                            width, height = image.size; image.verify()
                    except Exception as exception:
                        valid, error = False, str(exception)
                cache[identity] = dict(sha256=digest.hexdigest(), valid=valid, width=width, height=height, error=error)
            cell = cell_number(file.name)
            if institution == 'PCL':
                catalog_matches = [r for r in pcl if Path(r['file']).stem.strip() == file.stem.strip()]
                if len(catalog_matches) == 1:
                    cell = catalog_matches[0]['sheet']
            assets.append(dict(institution=institution, role=role, sheet_number=cell,
                               path=str(file), resolved_path=str(file.resolve()), bytes=stat.st_size,
                               device=stat.st_dev, inode=stat.st_ino, **cache[identity]))
    write_csv(OUT / 'manifests/local-files.csv', list(assets[0]), assets)

    item_rows=[]
    def source_item(institution, cell, source_ref, url, catalog):
        stored=next((s for s in snapshot['sources'] if s['institution']==institution and s['source_ref']==source_ref),None)
        if stored is None:
            candidates=[s for s in snapshot['sources'] if s['institution']==institution and s['sheet_number']==cell]
            if len(candidates)==1: stored=candidates[0]
        local=[a for a in assets if a['institution']==institution and a['role'] in ('pdf','jpg') and a['sheet_number']==cell]
        if institution=='PCL': local=[a for a in local if Path(a['path']).stem.strip()==Path(source_ref).stem.strip()]
        maps=[m for m in snapshot['maps'] if m['sheet_number']==cell and
              ((institution=='TTU' and m['extra_metadata'].get('source_archive')=='TTU') or
               (institution=='PCL' and m['extra_metadata'].get('source_archive')!='TTU'))]
        return dict(institution=institution,sheet_number=cell,source_ref=source_ref,
                    source_url=(stored or {}).get('url') or url,title=(stored or {}).get('title') or catalog.get('name',''),
                    year=(stored or {}).get('year') or catalog.get('year',''),edition=(stored or {}).get('edition') or catalog.get('edition',''),
                    database_source_id=(stored or {}).get('id',''),map_ids='|'.join(m['id'] for m in maps),
                    local_master_paths='|'.join(a['path'] for a in local),local_master_sha256='|'.join(sorted({a['sha256'] for a in local})),
                    printing_identity='unreviewed',master_policy='reference-only' if institution=='ANU' else 'retain-pending-review')
    for item in pcl: item_rows.append(source_item('PCL',item['sheet'],item['file'],item['url'],item))
    for cell in sorted(ttu_cells):
        item_rows.append(source_item('TTU',cell,cell+'.pdf',f'https://vva.vietnam.ttu.edu/images.php?img=/maps/PDF/{cell}.pdf',{}))
    for source in snapshot['sources']:
        if source['institution']=='ANU':item_rows.append(source_item('ANU',source['sheet_number'],source['source_ref'],source['url'],{}))
    write_csv(OUT / 'manifests/source-items.csv',list(item_rows[0]),item_rows)

    copies = collections.defaultdict(list)
    for asset in assets: copies[asset['sha256']].append(asset)
    groups = [{'sha256': digest, 'paths': [a['path'] for a in group],
               'physical_files': len({(a['device'], a['inode']) for a in group}),
               'bytes_per_file': group[0]['bytes']} for digest, group in copies.items() if len(group) > 1]
    write_json(OUT / 'manifests/exact-copy-groups.json', groups)

    native = {a['sheet_number']: a for a in assets if a['role'] == 'native'}
    rough = {}
    for file in (OUT / 'evidence/neatlines').glob('rough-[0-9]*.json'):
        for cell, reading in json.loads(file.read_text()).items():
            if cell in rough: raise ValueError(f'Duplicate rough reading for {cell}')
            rough[cell] = reading
    write_json(OUT / 'evidence/neatlines/rough-readings-index.json', rough)
    detector = json.loads((WORK / 'regen/ttu-corners.json').read_text())
    rows = []
    for cell in sorted(indexed):
        maps = [m for m in snapshot['maps'] if m['sheet_number'] == cell]
        sources = [s for s in snapshot['sources'] if s['sheet_number'] == cell]
        local = [a for a in assets if a['sheet_number'] == cell]
        p = [r for r in pcl if r['sheet'] == cell]
        margin_ids = [('t-' if m['extra_metadata'].get('source_archive') == 'TTU' else 's-') + cell
                      for m in maps if m['status'] == 'draft']
        cropped = [i for i in margin_ids if all((OUT / f'evidence/margins/{i}-{side}.png').exists() for side in ['L', 'R'])]
        rows.append(dict(sheet_number=cell, public_records=sum(m['status']=='public' for m in maps),
                         draft_records=sum(m['status']=='draft' for m in maps),
                         source_institutions='|'.join(sorted({s['institution'] for s in sources} | ({'TTU'} if cell in ttu_cells else set()))),
                         pcl_catalog_items=len(p), ttu_pdf_present=cell in ttu_cells,
                         ttu_native_present=cell in native, anu_items=sum(s['institution']=='ANU' for s in sources),
                         map_ids='|'.join(m['id'] for m in maps),
                         local_file_paths='|'.join(a['path'] for a in local),
                         margin_crop_ids='|'.join(sorted(set(cropped))),
                         rough_reading_present=cell in rough, detector_record_present=cell in detector,
                         detector_pass=bool(detector.get(cell,{}).get('ok')), no_source_in_catalogs=cell not in source_cells))
    write_csv(OUT / 'manifests/cell-master.csv', list(rows[0]), rows)
    # Preserve only inventory fields from maps; avoid copying unrelated account metadata.
    fields=['id','sheet_number','name','slug','status','year','iiif_image','annotation_url','is_georeferenced','bbox','extra_metadata']
    write_json(OUT / 'catalogs/map-records.json', [{f:m.get(f) for f in fields} for m in snapshot['maps']])

    missing_pcl=[]
    for row in pcl:
        stem = Path(row['file']).stem.strip()
        if not any(a['institution']=='PCL' and Path(a['path']).stem.strip()==stem and a['valid'] for a in assets):
            missing_pcl.append(row['file'])
    summary = {**plan, 'source_items_database': len(snapshot['sources']), 'map_records': len(snapshot['maps']),
               'local_file_paths': len(assets), 'physical_files': len(cache),
               'pcl_items_without_local_file': missing_pcl,
               'ttu_pdfs_without_native': sorted(ttu_cells - set(native)),
               'invalid_local_files': [a['path'] for a in assets if not a['valid']],
               'out_of_index_local_cells': sorted({a['sheet_number'] for a in assets if a['sheet_number']} - indexed),
               'unparsed_local_files': [a['path'] for a in assets if not a['sheet_number']],
               'catalog_vs_database_cell_difference': sorted(indexed ^ {c['sheet_number'] for c in snapshot['cells']}),
               'catalog_vs_lattice_cell_difference': sorted(indexed ^ set(json.loads((WORK/'lattice.json').read_text())['cells'])),
               'source_items_reconciled': len(item_rows),
               'rough_readings': len(rough), 'preserved_margin_images': len(list((OUT/'evidence/margins').glob('*.png'))),
               'exact_copy_groups': len(groups),
               'reclaimable_exact_copy_bytes': sum(g['bytes_per_file']*(g['physical_files']-1) for g in groups),
               'database_ttu_missing_source_cells': sorted({m['sheet_number'] for m in snapshot['maps'] if m['extra_metadata'].get('source_archive')=='TTU'} - {s['sheet_number'] for s in snapshot['sources'] if s['institution']=='TTU'}),
               'ttu_pdf_cells_without_ttu_row': sorted(ttu_cells - {m['sheet_number'] for m in snapshot['maps'] if m['extra_metadata'].get('source_archive')=='TTU'})}
    write_json(OUT / 'summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
