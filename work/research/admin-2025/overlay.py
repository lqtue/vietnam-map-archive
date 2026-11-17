"""Witness C: where each old commune went, by area. Hồ Chí Minh City first.

The 2025 sheet lists the old communes each new one was built from, not how much of each. Laying
OSM's boundaries from before the reform over OSM's boundaries after it gives the share of every
old commune that fell in every new one; that settles the communes the sheet left out and the ones
it split, and checks the list where the two disagree.

Boundaries are OpenStreetMap (ODbL), cut from Geofabrik's dated Vietnam extracts and kept outside
the repo; only the shares are written here.

    ogr2ogr -f GeoJSON before.geojson vietnam-250101.osm.pbf multipolygons -spat 106.3 8.5 107.7 11.6 \
        -where "boundary='administrative' AND admin_level IN ('4','6','8')" -select osm_id,name,admin_level,other_tags
    ogr2ogr -f GeoJSON after.geojson vietnam-261013.osm.pbf multipolygons -spat 106.3 8.5 107.7 11.6 \
        -where "boundary='administrative' AND admin_level IN ('4','6')" -select osm_id,name,admin_level,other_tags
    python3 work/research/admin-2025/overlay.py before.geojson after.geojson

Needs shapely; everything else in this folder is stdlib.
"""
import json
import re
import sys
from collections import Counter, defaultdict

from shapely import STRtree
from shapely.geometry import shape

from names import key, read, split, write

OLD = {'VN-SG': 'TP HCM', 'VN-57': 'Bình Dương', 'VN-43': 'Bà Rịa - Vũng Tàu'}   # by ISO 3166-2
NEW = ('VN-SG', 'TP HCM')
LANDS = 0.05      # ponytail: a smaller share is the two surveys' edges disagreeing, not a piece of the unit


def features(path):
    by_level = defaultdict(list)
    for f in json.load(open(path, encoding='utf-8'))['features']:
        p = f['properties']
        iso = re.search(r'"ISO3166-2"=>"([^"]+)"', p.get('other_tags') or '')
        by_level[p['admin_level']].append({'name': p.get('name') or '', 'iso': iso and iso[1],
                                           'geom': shape(f['geometry']).buffer(0)})
    return by_level


def parent(units, parents):
    """The parent whose polygon holds each unit's inner point."""
    tree = STRtree([q['geom'] for q in parents])
    for u in units:
        pt = u['geom'].representative_point()
        hit = [parents[i] for i in tree.query(pt) if parents[i]['geom'].contains(pt)]
        u['parent'] = hit[0] if hit else None


def main(before_path, after_path):
    old = {r['code']: r for r in read('data/old_units.csv') if r['province'] in OLD.values()}
    new = [u for u in read('data/new_units.csv') if u['province'] == NEW[1]]
    listed = defaultdict(set)              # old code -> new units whose code list holds it
    for u in new:
        for c in split(u['old_codes']) + split(u['hand_codes']):
            listed[c].add(u['name'])

    # before: commune -> district -> province, then to a GSO code by folded names
    b = features(before_path)
    provinces = [p for p in b['4'] if p['iso'] in OLD]
    parent(b['6'], provinces)
    parent(b['8'], b['6'])
    gso = {(o['province'], key(o['district']), key(o['name'])): c for c, o in old.items()}
    olds, unmatched = [], []
    for u in b['8']:
        d = u['parent']
        if not (d and d['parent']):
            continue
        k = (OLD[d['parent']['iso']], key(d['name']), key(u['name']))
        (olds if k in gso else unmatched).append(u)
        u['code'] = gso.get(k)
    print(f'before: {len(olds)} OSM communes matched to {len({u["code"] for u in olds})} of {len(old)} GSO codes; '
          f'{len(unmatched)} unmatched')
    for u in unmatched:
        print(f"  no GSO code: {u['name']}, {u['parent']['name']}")

    # after: new communes inside the new city
    a = features(after_path)
    city = next(p for p in a['4'] if p['iso'] == NEW[0])
    parent(a['6'], [city])
    names = {key(u['name']): u['name'] for u in new}
    news = [u for u in a['6'] if u['parent'] and key(u['name']) in names]
    print(f'after: {len(news)} OSM communes matched of {len(new)} new units; missing: '
          f'{sorted(set(names.values()) - {names[key(u["name"])] for u in news})}')

    # the overlay
    tree = STRtree([u['geom'] for u in news])
    shares, rows = defaultdict(dict), []
    for u in olds:
        for i in tree.query(u['geom']):
            s = u['geom'].intersection(news[i]['geom']).area / u['geom'].area
            if s >= 0.01:
                nm = names[key(news[i]['name'])]
                shares[u['code']][nm] = max(s, shares[u['code']].get(nm, 0))
    for c, got in sorted(shares.items()):
        for nm, s in sorted(got.items(), key=lambda x: -x[1]):
            rows.append({'code': c, 'old': old[c]['name'], 'district': old[c]['district'],
                         'province': old[c]['province'], 'new': nm, 'share': f'{s:.3f}'})
    write('out/hcmc_overlay.csv', rows, ['code', 'old', 'district', 'province', 'new', 'share'])

    # witness C against the code list
    checks = []
    for c, o in old.items():
        lands = {nm for nm, s in shares.get(c, {}).items() if s >= LANDS}
        has = listed.get(c, set())
        if c not in shares:
            verdict = 'no geometry'
        elif not has:
            verdict = 'unassigned, settled'
        elif lands == has:
            verdict = 'agree'
        elif lands > has:
            verdict = 'geometry adds'
        elif lands < has:
            verdict = 'list adds'
        else:
            verdict = 'differ'
        checks.append({'code': c, 'old': o['name'], 'district': o['district'], 'province': o['province'],
                       'verdict': verdict, 'listed': ' + '.join(sorted(has)),
                       'geometry': ' + '.join(f'{nm} {shares[c][nm]:.2f}' for nm in sorted(lands, key=lambda n: -shares[c][n]))})
    write('out/hcmc_checks.csv', checks, ['code', 'old', 'district', 'province', 'verdict', 'listed', 'geometry'])
    print('\nWitness C against the code list:', dict(Counter(r['verdict'] for r in checks).most_common()))
    split_ = [r for r in checks if r['geometry'].count(' + ') > 0]
    print(f'old communes cut across two or more new ones (each piece >= {LANDS:.0%}): {len(split_)}')

    # a name kept from an old commune: does that commune lie in the unit that bears its name?
    by_key = defaultdict(list)
    for c, o in old.items():
        by_key[key(o['name'])].append(c)
    named = []
    for r in read('out/names.csv'):
        if r['province'] != NEW[1] or r['origin'] != 'ward':
            continue
        for src in re.findall(r'([^+]+?) \(ward\)', r['sources']):
            s = max((shares.get(c, {}).get(r['name'], 0) for c in by_key[key(src.strip())]), default=0)
            named.append({'name': r['name'], 'kind': r['kind'], 'source': src.strip(), 'share': f'{s:.2f}',
                          'verdict': 'inside' if s >= 0.5 else 'partly' if s >= LANDS else 'elsewhere'})
    write('out/hcmc_names.csv', named, ['name', 'kind', 'source', 'share', 'verdict'])
    print('Names kept from an old commune, by where that commune lies:', dict(Counter(r['verdict'] for r in named)))


if __name__ == '__main__':
    main(*sys.argv[1:3])
