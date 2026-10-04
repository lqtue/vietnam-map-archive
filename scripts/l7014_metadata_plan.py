"""Prepare explicit L7014 metadata corrections from a snapshot and reviewed evidence.

Writes only local plans. Names share accents only within the same survey cell and
folded title; historically different titles stay distinct. Dates require a reviewed
per-scan evidence record. Existing dates and public slugs are preserved.
"""
import argparse
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]


def clean_name(name):
    if name is None:
        return None
    name = unicodedata.normalize('NFC', name)
    # Word separators only; sheet numbers, apostrophes and other punctuation stay.
    name = re.sub(r'(?<=[^\W\d_])\s*[-–]\s*([^\W\d_])',
                  lambda m: ' ' + m[1].upper(), name)
    return re.sub(r'\s+', ' ', name).strip()


def fold(name):
    name = unicodedata.normalize('NFD', name.lower().replace('đ', 'd'))
    return re.sub(r"[^a-z0-9']", '', name.encode('ascii', 'ignore').decode())


def accent_count(name):
    return sum(unicodedata.combining(c) != 0 for c in unicodedata.normalize('NFD', name)) + name.lower().count('đ')


def title_case(name):
    return ' '.join(w[:1].upper() + w[1:].lower() for w in clean_name(name).split())


def aliases(name):
    # Keep an index's historical/modern alternatives, accenting each match.
    return [x.strip() for x in re.split(r'[/()]', name) if x.strip()]


def build(snapshot, dates, titles=None):
    titles = titles or {}
    candidates = {}
    for row in snapshot['maps']:
        title = titles.get(row['id'])
        if title and (title.get('review_status') != 'reviewed' or not title.get('source_sha256') or not title.get('quote')):
            raise ValueError('Unreviewed title evidence')
        name = clean_name(title['title'] if title else row['name'])
        evidence = title if title else {'kind': 'existing_map', 'id': row['id'], 'name': row['name']}
        candidates.setdefault(row['sheet_number'], []).append((name, evidence))
        for alias in aliases(name):
            if alias != name:
                candidates[row['sheet_number']].append((alias, evidence))
    for filename in ['read-A.json', 'read-B.json']:
        path = ROOT / 'work/l7014/inventory/evidence/titles' / filename
        if not path.exists():
            continue
        for row in json.loads(path.read_text()):
            if row.get('title') and row.get('confidence') == 'high':
                candidates.setdefault(row['cell'], []).append((title_case(row['title']),
                    {'kind': 'preserved_title_read', 'path': str(path.relative_to(ROOT)),
                     'cell': row['cell'], 'title': row['title']}))

    canonical = {}
    ambiguities = []
    for cell, names in candidates.items():
        for key in set(fold(n) for n, _ in names):
            options = [(n, e) for n, e in names if fold(n) == key]
            reviewed = [(n, e) for n, e in options if e.get('review_status') == 'reviewed']
            if reviewed:
                if len(set(n.casefold() for n, _ in reviewed)) != 1:
                    raise ValueError(f'Conflicting reviewed titles for {cell}')
                canonical[cell, key] = reviewed[0]
                continue
            most = max(accent_count(n) for n, _ in options)
            best = [(n, e) for n, e in options if accent_count(n) == most]
            distinct = set(n.casefold() for n, _ in best)
            if len(distinct) > 1:
                ambiguities.append({'cell': cell, 'variants': sorted(distinct)})
                continue
            canonical[cell, key] = best[0]

    def corrected_name(row):
        name = clean_name(row['name'])
        evidence = []
        direct = canonical.get((row['sheet_number'], fold(name)))
        if direct:
            chosen, proof = direct
            if chosen != name and (proof.get('review_status') == 'reviewed' or accent_count(chosen) > accent_count(name) or chosen.casefold() == name.casefold()):
                name = chosen
                evidence.append(proof)
        else:
            parts = re.split(r'([/()])', name)
            for i, part in enumerate(parts):
                stripped = part.strip()
                chosen = canonical.get((row['sheet_number'], fold(stripped))) if stripped else None
                if chosen and chosen[0] != stripped and (accent_count(chosen[0]) > accent_count(stripped) or chosen[0].casefold() == stripped.casefold()):
                    parts[i] = part.replace(stripped, chosen[0])
                    evidence.append(chosen[1])
            name = ''.join(parts)
        if name != row['name'] and not evidence:
            evidence = [{'kind': 'word_separator_normalization'}]
        return name, evidence

    changes = []
    resulting_maps = {}
    for row in snapshot['maps']:
        after = {}
        evidence = []
        name, proofs = corrected_name(row)
        title = titles.get(row['id'])
        if title:
            name = clean_name(title['title'])
            proofs = [title]
            previous = row['extra_metadata'].get('catalog_title_evidence')
            if name != row['name'] or not previous:
                after['extra_metadata'] = {**row['extra_metadata'],
                    'catalog_title_evidence': {**{k: v for k, v in title.items() if k != 'review_status'},
                                               'previous_name': previous.get('previous_name', row['name']) if previous else row['name']}}
        if name != row['name']:
            after['name'] = name
            evidence += proofs
        date = dates.get(row['id'])
        missing = row['year'] is None or not 1850 <= row['year'] <= 2026
        if missing and date:
            if date.get('review_status') != 'reviewed' or not date.get('quote') or not date.get('source_sha256'):
                raise ValueError(f"Unreviewed date for {row['id']}")
            if date['kind'] not in {'printing', 'edition', 'preparation', 'content'} or not 1850 <= date['year'] <= 2026:
                raise ValueError('Invalid date evidence')
            after['year'] = date['year']
            evidence.append(date)
            after['extra_metadata'] = {**after.get('extra_metadata', row['extra_metadata']),
                'catalog_year_evidence': {k: v for k, v in date.items() if k != 'review_status'}}
        elif missing and row['year'] is not None:
            after['year'] = None
            evidence.append({'kind': 'invalid_year_placeholder', 'previous_year': row['year']})
        resulting_maps[row['id']] = {**row, **after}
        if after:
            changes.append({'table': 'maps', 'id': row['id'], 'sheet_number': row['sheet_number'],
                'before': {key: row.get(key) for key in after}, 'after': after,
                'invariants': {'slug': row['slug'], 'status': row['status'],
                               'series_key': row['series_key'], 'printing_id': row.get('printing_id')},
                'evidence': evidence})

    for row in snapshot['cells']:
        if row['name'] is None:
            continue
        after = {}
        name, evidence = corrected_name(row)
        if name != row['name']:
            after['name'] = name
        # Only fill the representative date from the exact previously selected
        # archive map, never from another institution/printing of this cell.
        selected = resulting_maps.get(row['map_id'])
        if row['year'] is None and selected and selected['year'] is not None and 1850 <= selected['year'] <= 2026:
            after['year'] = selected['year']
            evidence.append({'kind': 'selected_map', 'id': selected['id'], 'year': selected['year']})
        if after:
            changes.append({'table': 'series_cells', 'id': row['id'], 'sheet_number': row['sheet_number'],
                'before': {key: row.get(key) for key in after}, 'after': after,
                'invariants': {'map_id': row['map_id'], 'series_key': row['series_key']}, 'evidence': evidence})
    return {'snapshot_at': snapshot['at'], 'series_key': 'series-l7014-vietnam-1-50-000',
            'changes': changes, 'ambiguous_names': ambiguities,
            'summary': {'map_names': sum(c['table']=='maps' and 'name' in c['after'] for c in changes),
                        'cell_names': sum(c['table']=='series_cells' and 'name' in c['after'] for c in changes),
                        'map_years': sum(c['table']=='maps' and 'year' in c['after'] for c in changes),
                        'cell_years': sum(c['table']=='series_cells' and 'year' in c['after'] for c in changes)}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', required=True, type=Path)
    p.add_argument('--reviewed-dates', type=Path)
    p.add_argument('--reviewed-titles', type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    snapshot = json.loads(a.snapshot.read_text())
    dates = json.loads(a.reviewed_dates.read_text()) if a.reviewed_dates else {}
    titles = json.loads(a.reviewed_titles.read_text()) if a.reviewed_titles else {}
    plan = build(snapshot, dates, titles)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(plan['summary']))
    for c in plan['changes']:
        old = {k: v for k, v in c['before'].items() if k != 'extra_metadata'}
        new = {k: v for k, v in c['after'].items() if k != 'extra_metadata'}
        print(c['table'], c['sheet_number'], json.dumps(old, ensure_ascii=False), '->', json.dumps(new, ensure_ascii=False))


if __name__ == '__main__':
    main()
