"""Read printed L7014 titles/dates into local evidence, never the database.

Bare invocation reports the plan. --apply enables local crops and model calls.
Existing readings are reused; --limit bounds a pilot run. Date fields stay separate.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/ocr/scripts'))
from gemini_client import DEFAULT_MODEL, _load_client, genai_types

Image.MAX_IMAGE_PIXELS = 250_000_000
OUT = ROOT / 'work/l7014/metadata-20261004'
PROMPT = '''Transcribe the title and dating evidence actually printed on this historical map.
The images are the TOP TITLE BAND and, when provided, BOTTOM LEFT / BOTTOM RIGHT margins
of ONE scan. Preserve Vietnamese, Lao and Khmer diacritics exactly. Do not modernize names,
infer accents, copy dates from geographic knowledge, or use PDF creation dates. Ignore
magnetic-declination dates, aerial-photo dates and datum years (e.g. Indian 1960).
Return JSON: {"title": string or null, "title_confidence": "high"|"medium"|"low",
"edition_statement": string or null, "printing_statement": string or null,
"dates": [{"kind": "printing"|"edition"|"preparation"|"content", "year": integer,
"month": integer or null, "quote": exact printed phrase proving this specific year,
"confidence": "high"|"medium"|"low"}], "notes": string}.
The most recent ACTUAL printing/reprinting statement is printing. Preparation is a separate
date. Expand explicit two-digit printer dates such as "12-68" to 1968, but preserve the
exact phrase as quote. If unreadable or absent, return null / [] and explain. No guesses.'''


def source_for(row, catalog):
    cell = row['sheet_number']
    institution = (row.get('extra_metadata') or {}).get('source_archive')
    if institution == 'TTU':
        p = Path('/Users/airm1/Work/Maps/l7014/ttu/native') / f'{cell}-000.jpg'
        return p if p.exists() else None
    if institution == 'PCL':
        matches = [r for r in catalog if r['sheet'] == cell and r['kind'] == 'pdf']
        if len(matches) == 1:
            p = ROOT / 'work/l7014/pdfs' / matches[0]['file']
            if not p.exists():
                # PCL's 6331-4 URL has a trailing space; the preserved download
                # removed that space. Match only that filename normalization.
                p = p.with_name(p.stem.rstrip() + p.suffix)
            return p if p.exists() else None
    # The original 24 PCL JPEG records have no archive tag. Their actual scan
    # was staged by sheet number, before subsequent GeoPDF/TTU ingestion.
    matches = list(Path('/Users/airm1/Work/Maps/l7014/stage').glob(f'* (L7014 {cell})*.jpg'))
    if len(matches) == 1 and matches[0].exists():
        return matches[0]
    matches = list(Path('/Users/airm1/Work/Maps/l7014/jpgs').glob(f'*-{cell}.jpg'))
    return matches[0] if len(matches) == 1 else None


def missing_year(row):
    return row['year'] is None or not 1850 <= row['year'] <= 2026


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def page_rotation(row, source):
    pdf = source if source.suffix.lower() == '.pdf' else (
        Path('/Users/airm1/Work/Maps/l7014/ttu') / f"{row['sheet_number']}.pdf"
        if (row.get('extra_metadata') or {}).get('source_archive') == 'TTU' else None)
    if pdf is None or not pdf.exists():
        return 0
    import re
    info = subprocess.run(['pdfinfo', str(pdf)], check=True, capture_output=True, text=True)
    match = re.search(r'Page rot:\s*(\d+)', info.stdout)
    return int(match[1]) % 360 if match else 0


def crops(row, source, rotation=0):
    folder = OUT / 'crops' / row['id']
    if rotation:
        folder = folder / f'page-rotation-{rotation}'
    metadata_file = folder / 'source.json'
    if metadata_file.exists():
        return json.loads(metadata_file.read_text())
    folder.mkdir(parents=True, exist_ok=True)
    native = source
    display_rotation = rotation
    if source.suffix.lower() == '.pdf':
        prefix = folder / 'embedded'
        subprocess.run(['pdfimages', '-f', '1', '-l', '1', '-j', str(source), str(prefix)],
                       check=True, capture_output=True)
        images = list(folder.glob('embedded-*'))
        if len(images) != 1:
            # PDFs with multiple raster strips need their actual page layout.
            prefix = folder / 'page'
            subprocess.run(['pdftoppm', '-f', '1', '-l', '1', '-r', '150',
                            '-scale-to', '9000', '-jpeg', '-singlefile',
                            str(source), str(prefix)], check=True, capture_output=True)
            native = prefix.with_suffix('.jpg')
            display_rotation = 0  # pdftoppm already applies the PDF page transform.
        else:
            native = images[0]
    with Image.open(native) as image:
        if display_rotation:
            image = image.rotate(-display_rotation, expand=True)
        w, h = image.size
        regions = [('title', (0, 0, w, int(h * .16)))]
        if missing_year(row):
            regions += [('bottom-left', (0, int(h * .72), w // 2, h)),
                        ('bottom-right', (w // 2, int(h * .72), w, h))]
        saved = []
        for name, box in regions:
            crop = image.crop(box).convert('RGB')
            crop.thumbnail((3600 if name == 'title' else 2800, 2500))
            dest = folder / f'{name}.jpg'
            crop.save(dest, quality=95)
            saved.append({'label': name, 'path': str(dest.relative_to(ROOT)),
                          'source_box': list(box), 'sha256': sha(dest)})
    metadata = {'map_id': row['id'], 'sheet_number': row['sheet_number'],
                'previous_name': row['name'], 'previous_year': row['year'],
                'source_path': str(source), 'source_sha256': sha(source),
                'image_size': [w, h], 'page_rotation': rotation,
                'display_rotation_clockwise': display_rotation, 'crops': saved}
    metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    return metadata


def read_one(row, source, model, reader, rotation):
    dest = OUT / 'readings' / f"{row['id']}.json"
    if dest.exists() and json.loads(dest.read_text()).get('page_rotation', 0) == rotation:
        return 'cached', row['sheet_number']
    if dest.exists():
        preserved = OUT / 'readings-before-rotation' / dest.name
        preserved.parent.mkdir(parents=True, exist_ok=True)
        if not preserved.exists():
            preserved.write_bytes(dest.read_bytes())
    evidence = crops(row, source, rotation)
    if reader == 'tesseract':
        transcriptions = []
        for crop in evidence['crops']:
            result = subprocess.run(['tesseract', str(ROOT / crop['path']), 'stdout',
                                     '-l', 'eng+vie', '--psm', '11'],
                                    check=True, capture_output=True, text=True,
                                    env={**os.environ, 'OMP_THREAD_LIMIT': '1'})
            transcriptions.append({**crop, 'text': result.stdout})
        evidence.update(ocr=transcriptions, reader=reader, review_status='machine_transcription')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
        return 'read', row['sheet_number']
    client, _ = _load_client()
    content = [PROMPT]
    for crop in evidence['crops']:
        content += [crop['label'], genai_types.Part.from_bytes(
            data=(ROOT / crop['path']).read_bytes(), mime_type='image/jpeg')]
    started = time.time()
    response = client.models.generate_content(model=model, contents=content,
        config=genai_types.GenerateContentConfig(temperature=0,
            response_mime_type='application/json', max_output_tokens=2200))
    reading = json.loads(response.text)
    if not isinstance(reading.get('dates'), list):
        raise ValueError('Invalid date response')
    for date in reading['dates']:
        if not isinstance(date.get('year'), int) or not 1850 <= date['year'] <= 2026:
            raise ValueError('Invalid year')
        if date.get('kind') not in {'printing', 'edition', 'preparation', 'content'} or not date.get('quote'):
            raise ValueError('Date lacks kind or printed evidence')
    dest.parent.mkdir(parents=True, exist_ok=True)
    evidence.update(reading=reading, model=model, seconds=round(time.time()-started, 2),
                    usage=response.usage_metadata.model_dump(mode='json') if response.usage_metadata else None,
                    review_status='machine_transcription')
    dest.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    return 'read', row['sheet_number']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--limit', type=int)
    p.add_argument('--workers', type=int, default=3)
    p.add_argument('--model', default=DEFAULT_MODEL)
    p.add_argument('--reader', choices=['tesseract', 'gemini'], default='tesseract')
    p.add_argument('--missing-years', action='store_true')
    a = p.parse_args()
    maps = json.loads(a.snapshot.read_text())['maps']
    catalog = json.loads((ROOT / 'work/l7014/sheets.json').read_text())
    jobs, unavailable = [], []
    for row in sorted(maps, key=lambda m: (not missing_year(m), m['sheet_number'], m['id'])):
        if a.missing_years and not missing_year(row):
            continue
        source = source_for(row, catalog)
        if source is None:
            unavailable.append({'id': row['id'], 'sheet': row['sheet_number'], 'name': row['name']})
        else:
            rotation = page_rotation(row, source)
            cached = OUT / 'readings' / f"{row['id']}.json"
            if not cached.exists() or json.loads(cached.read_text()).get('page_rotation', 0) != rotation:
                jobs.append((row, source, rotation))
    if a.limit is not None:
        jobs = jobs[:a.limit]
    print(json.dumps({'pending': len(jobs), 'no_local_source': unavailable, 'reader': a.reader,
                      'model': a.model if a.reader == 'gemini' else None,
                      'apply': a.apply}, ensure_ascii=False), flush=True)
    if not a.apply:
        return
    failures = []
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures = {pool.submit(read_one, r, source, a.model, a.reader, rotation): r for r, source, rotation in jobs}
        for i, future in enumerate(as_completed(futures), 1):
            row = futures[future]
            try:
                status, cell = future.result()
                print(f'{i}/{len(jobs)} {cell} {status}', flush=True)
            except Exception as e:
                failures.append(row['id'])
                # Do not print exception content: SDK errors may include request credentials.
                print(f'{i}/{len(jobs)} {row["sheet_number"]} failed: {type(e).__name__}', flush=True)
    print(json.dumps({'completed': len(jobs)-len(failures), 'failed_ids': failures}), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
