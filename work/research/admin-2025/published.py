"""How far does out/names.csv agree with the tags VnExpress published on 1 Aug 2025?

The article's map is a Flourish story; its saved page carries every unit's published tag. Pass the
saved page, get agreement counts. The published tags are not written anywhere in the repo.

    python3 work/research/admin-2025/published.py ~/Downloads/embed          # counts
    python3 work/research/admin-2025/published.py ~/Downloads/embed --list   # and each disagreement
"""
import csv
import json
import re
import sys
from collections import Counter

from names import HERE, key

FAMILY = {'Tên giữ toàn bộ': 'whole', 'Tên giữ một phần': 'partial', 'Tên mới hoàn toàn': 'new'}
ORIGIN = {'Từ phường xã cũ': 'ward', 'Từ quận huyện cũ': 'district', 'Từ tỉnh thành cũ': 'province', 'Tên mới': ''}
CALL = ('(function(array, column_names, metadata, timestamps){ array.column_names = column_names; '
        'array.metadata = metadata; array.timestamps = timestamps; return array; })(')


def published(path):
    """The first data table in the story: one row per new unit."""
    s = open(path, encoding='utf-8').read()
    dec = json.JSONDecoder()
    rows, end = dec.raw_decode(s, s.index(CALL) + len(CALL))
    cols, _ = dec.raw_decode(s, s.index('{', end))
    names = cols['metadata']
    return [dict(zip(names, r['metadata'])) for r in rows]


def join_key(name):
    # ponytail: Đăk/Đắk is one spelling drift the rules keep apart; fold it only for the join
    return tuple((b, 0) if b == 'đăk' else (b, t) for b, t in key(name))


def unit(p, n):
    return join_key(re.sub(r'^tp\.? hcm$', 'hồ chí minh', p.strip().lower())), join_key(n)


def main(path, show):
    pub = {unit(r['new_prov'], r['new_ward']): r for r in published(path)}
    ours = {unit(r['province'], r['name']): r for r in csv.DictReader(open(HERE / 'out/names.csv'))}
    both = pub.keys() & ours.keys()
    print(f'published {len(pub)} · ours {len(ours)} · joined {len(both)}')
    fam, org = Counter(), Counter()
    for k in sorted(both):
        p, o = pub[k], ours[k]
        f = (FAMILY[p['Phân loại chung']], o['family'])
        g = (ORIGIN[p['Nguồn gốc']], o['origin'])
        fam[f] += 1
        org[g] += 1
        if show and (f[0] != f[1] or g[0] != g[1]):
            print(f"  {o['province']} · {o['name']}: published {f[0]}/{g[0] or '-'} ({p['detail']}), "
                  f"ours {o['kind']}/{o['origin'] or '-'} [{o['status']}]")
    for title, c in (('family', fam), ('origin', org)):
        same = sum(v for (a, b), v in c.items() if a == b)
        print(f'{title}: {same} of {len(both)} agree')
        for (a, b), v in sorted(c.items()):
            if a != b:
                print(f'  published {a or "-"} -> ours {b or "-"}: {v}')
    judged = {unit(r['province'], r['name']): r for r in csv.DictReader(open(HERE / 'judged.csv'))
              if r['confidence'] != 'unsure'}
    if judged:     # where the two agree both are taken as right; judged.csv rules where they differ
        print(f'\nJudged {len(judged)} disagreements (judged.csv); errors over all {len(both)} joined units:')
        for side, tags in (('published', {k: (FAMILY[p['Phân loại chung']], ORIGIN[p['Nguồn gốc']]) for k, p in pub.items()}),
                           ('ours', {k: (o['family'], o['origin']) for k, o in ours.items()})):
            fam = sum(tags[k][0] != j['family'] for k, j in judged.items())
            org = sum(tags[k][1] != j['origin'] for k, j in judged.items() if j['family'] != 'new')
            low = sum(tags[k][0] != j['family'] for k, j in judged.items() if j['confidence'] == 'low')
            print(f'  {side:<10} family {fam:>3} ({100 * fam / len(both):.1f} %, {low} of them low-confidence)'
                  f' · origin of kept names {org:>3}')
    if show:
        for k in sorted(pub.keys() - ours.keys()):
            print('  published only:', pub[k]['new_prov'], '·', pub[k]['new_ward'])


if __name__ == '__main__':
    main(sys.argv[1], '--list' in sys.argv)
