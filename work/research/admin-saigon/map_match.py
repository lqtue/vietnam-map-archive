"""Pair each admin change in names.csv with the VMA sheets just before and just after it.

A sheet is a candidate when its bbox covers at least half the change's area and it is fine enough
to print that level of unit. Whether it does print the change is the human check: the blank
`shows_change` column. Reads the public catalogue (anon key, public sheets only, so drafts such
as the Cochinchina 1881–89 atlas are missing).

    set -a; . ./.env; set +a
    python3 work/research/admin-saigon/map_match.py

Stdlib only.
"""
import csv
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent

# lon/lat boxes, drawn by hand from today's districts
AREAS = {
    'SGN': (106.685, 10.765, 106.71, 10.795),    # first Ville de Saigon, today's Quận 1
    'CHL': (106.64, 10.745, 106.68, 10.765),     # first Ville de Cholon, Quận 5
    'CITY': (106.63, 10.74, 106.72, 10.80),      # Saigon and Cholon together
    'Q4': (106.69, 10.752, 106.715, 10.77),      # the Quận 4 peninsula
    'H20': (106.64, 10.73, 106.73, 10.81),       # Hạt 20 around the two cities
    'THT': (106.715, 10.765, 106.745, 10.795),   # Thủ Thiêm
    'Q1011': (106.64, 10.755, 106.675, 10.785),  # Quận 10 and 11
    'GDN-N': (106.64, 10.79, 106.72, 10.85),     # Gò Vấp, Phú Nhuận, Tân Bình
    'BCH': (106.55, 10.68, 106.65, 10.78),       # Bình Chánh
    'NBE': (106.69, 10.66, 106.76, 10.75),       # Nhà Bè, Quận 7
    'GDN': (106.5, 10.65, 106.85, 10.95),        # Gia Định province
    'CUCHI': (106.45, 10.9, 106.65, 11.1),
    'CANGIO': (106.75, 10.35, 107.0, 10.65),
}
# ponytail: sheet width stands in for scale; read the scale off the sheet if this misleads
MAX_KM = {'phường': 15, 'hộ': 15, 'làng': 40, 'xã': 40, 'city': 40, 'quận': 100, 'tổng': 100,
          'huyện': 150, 'arrondissement': 150, 'inspection': 150, 'province': 700}
PER_SIDE = 2


def catalogue():
    url, key = os.environ['PUBLIC_SUPABASE_URL'], os.environ['PUBLIC_SUPABASE_ANON_KEY']
    out, offset = [], 0
    while True:
        q = (f'{url}/rest/v1/maps?select=slug,year,bbox,is_georeferenced&archive_reason=is.null'
             f'&year=not.is.null&bbox=not.is.null&order=id&offset={offset}&limit=1000')
        page = json.load(urllib.request.urlopen(urllib.request.Request(q, headers={'apikey': key})))
        out += page
        if len(page) < 1000:
            return out
        offset += 1000


def coverage(area, b):
    w = max(0, min(area[2], b[2]) - max(area[0], b[0]))
    h = max(0, min(area[3], b[3]) - max(area[1], b[1]))
    return w * h / ((area[2] - area[0]) * (area[3] - area[1]))


def width_km(b):
    return (b[2] - b[0]) * 109.4  # km per degree of longitude at 10.8° N


def match(event, maps):
    area, year = AREAS[event['area']], int(event['date'][:4])
    fits = [m for m in maps if coverage(area, m['bbox']) >= 0.5
            and width_km(m['bbox']) <= MAX_KM[event['level']]]
    before = sorted((m for m in fits if m['year'] < year), key=lambda m: -m['year'])[:PER_SIDE]
    after = sorted((m for m in fits if m['year'] > year), key=lambda m: m['year'])[:PER_SIDE]
    same = [m for m in fits if m['year'] == year]
    return [('before', m) for m in before] + [('same year', m) for m in same] + [('after', m) for m in after]


def main():
    events = list(csv.DictReader(open(HERE / 'names.csv', encoding='utf-8')))
    maps = catalogue()
    rows = []
    for e in events:
        pairs = match(e, maps)
        if not pairs:
            rows.append({'event': e['id'], 'date': e['date'], 'side': 'no sheet'})
        for side, m in pairs:
            rows.append({'event': e['id'], 'date': e['date'], 'side': side, 'year': m['year'],
                         'slug': m['slug'], 'url': f"https://maparchive.vn/catalog/{m['slug']}",
                         'gap_years': abs(m['year'] - int(e['date'][:4])),
                         'width_km': round(width_km(m['bbox'])),
                         'coverage': round(coverage(AREAS[e['area']], m['bbox']), 2),
                         'georef': 'y' if m['is_georeferenced'] else ''})
    cols = ['event', 'date', 'side', 'year', 'gap_years', 'slug', 'url', 'width_km', 'coverage', 'georef',
            'shows_change', 'checked_by', 'remark']
    with open(HERE / 'map_match.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    testable = {r['event'] for r in rows if r['side'] == 'before'} & {r['event'] for r in rows if r['side'] == 'after'}
    print(f'{len(maps)} sheets, {len(events)} changes, {len(testable)} with a sheet on both sides',
          file=sys.stderr)


def demo():
    b = (106.0, 10.0, 107.0, 11.0)
    assert coverage(AREAS['Q4'], b) == 1.0
    assert coverage(AREAS['Q4'], (0, 0, 1, 1)) == 0.0
    maps = [{'slug': 'a', 'year': 1882, 'bbox': (106.6, 10.7, 106.8, 10.85), 'is_georeferenced': True},
            {'slug': 'b', 'year': 1898, 'bbox': (106.6, 10.7, 106.8, 10.85), 'is_georeferenced': True},
            {'slug': 'wide', 'year': 1890, 'bbox': (100, 5, 110, 20), 'is_georeferenced': True}]
    got = match({'area': 'Q4', 'date': '1888-01-12', 'level': 'làng'}, maps)
    assert [(s, m['slug']) for s, m in got] == [('before', 'a'), ('after', 'b')], got


if __name__ == '__main__':
    demo()
    main()
