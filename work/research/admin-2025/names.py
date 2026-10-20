"""Where did each 2025 commune name come from?

Two witnesses read every new name against the old units it was built from:
  A, syllable rules: whole · variant · affix · part · near · compound · reused · new
  B, edit distance:  the nearest source name and how far it is
A syllable match settles itself. A one-letter difference, a compound, and a 'new' name that B
finds close to a source go to out/queue.csv, and a person's answer goes in decisions.csv, which is
applied on the next run. Nothing a person decides is lost, and every count can be rebuilt.

    python3 work/research/admin-2025/names.py           # write out/, print the counts
    python3 work/research/admin-2025/names.py --check   # self-test the folding and rules
"""
import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
TONES = '̣̀́̃̉'          # huyền sắc ngã hỏi nặng
VOWELS = set('aăâeêioôơuưy')
ROMAN = {'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'}
PREFIX = re.compile(r'^(phường|xã|thị trấn|thị xã|thành phố|tp\.?|quận|huyện|tỉnh|đặc khu)\s+', re.I)
FAMILY = {'whole': 'whole', 'variant': 'partial', 'affix': 'partial', 'part': 'partial', 'near': 'partial',
          'compound': 'partial',
          'reused': 'new', 'new': 'new'}
LEVELS = ('province', 'district', 'ward')               # a kept name is credited to the highest unit
                                                        # that bore it, as the article counted
ARTICLE = {'whole': 2596, 'partial': 290, 'new': 435}   # VnExpress, 1 Aug 2025, after hand review
NEAR = 0.34                                               # B: share of characters that must change


# --- folding: one key per spelling, whatever the tone placement or i/y habit -----------------

def syllable(tok):
    """'hoà' and 'hòa' -> ('hoa', 2); 'quý' and 'quí' -> ('qui', 1). 'thuý' keeps its y."""
    d = unicodedata.normalize('NFD', tok)
    tone = next((TONES.index(ch) + 1 for ch in d if ch in TONES), 0)
    base = unicodedata.normalize('NFC', ''.join(ch for ch in d if ch not in TONES))
    if len(base) > 1 and base.endswith('y') and (base[-2] not in VOWELS or base == 'quy'):
        base = base[:-1] + 'i'
    return base, tone


def key(name):
    s = PREFIX.sub('', unicodedata.normalize('NFC', name.strip().lower()))
    toks = re.sub(r'[-–—.,()]', ' ', re.sub(r"[’‘'`ʼ]", '', s)).split()
    if toks and toks[-1] in ROMAN:
        toks[-1] = ROMAN[toks[-1]]
    return tuple(syllable(t) for t in toks)


def loose(k):
    """Without any marks: Nà Hang and Na Hang meet here."""
    return tuple(unicodedata.normalize('NFD', b.replace('đ', 'd')).encode('ascii', 'ignore').decode() for b, _ in k)


def text(k):
    return ' '.join(f'{b}{t}' for b, t in k)


def squash(k):
    """Spacing in minority-language names drifts (A Vương, Avương; Ea Ly, Ealy): drop it.
    Numbers are dropped too; a number change is an affix, not a spelling."""
    return ''.join(b for b in loose(k) if not b.isdigit())


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


AFFIX = {key(w)[0] for w in ('bắc', 'nam', 'đông', 'tây', 'trung', 'thượng', 'hạ')}


def core(k):
    """Strip one direction word or number from each end, and a trailing A/B: Điện Bàn Bắc -> Điện Bàn,
    1 Bảo Lộc -> Bảo Lộc, Tân Thành A -> Tân Thành. A word is only stripped if two syllables remain,
    so Hà Nam stays Hà Nam."""
    k = list(k)
    for end in (0, -1):
        if len(k) > 1 and (k[end][0].isdigit() or (k[end] in AFFIX and len(k) > 2)
                           or (end == -1 and k[end][0] in ('a', 'b', 'c') and len(k) > 2)):
            k.pop(end)
    return tuple(k)


# --- the two witnesses -------------------------------------------------------------------------

def witness_a(nk, cands, nearby):
    """cands and nearby are (level, key, name). Returns (kind, the candidates it rests on)."""
    hit = [c for c in cands if c[1] == nk]
    if hit:
        return 'whole', hit
    digits = lambda k: [b for b, _ in k if b.isdigit()]
    same = [c for c in cands if digits(c[1]) == digits(nk)]
    hit = [c for c in same if squash(nk) and squash(c[1]) == squash(nk)]
    if hit:
        return 'variant', hit
    hit = [c for c in cands if core(nk) == core(c[1]) and core(nk) != nk or core(c[1]) != c[1] and core(c[1]) == nk]
    if hit:
        return 'affix', hit
    n = len(nk)       # a run of a longer name: Phan Rang from Phan Rang-Tháp Chàm
    hit = [c for c in cands if n > 1 and len(c[1]) >= n + 2 and nk in {c[1][i:i + n] for i in range(len(c[1]) - n + 1)}]
    if hit:
        return 'part', hit
    hit = [c for c in same if len(squash(nk)) >= 5 and lev(squash(nk), squash(c[1])) == 1]
    if hit:       # one letter: Châu Bình/Châu Bính is a correction, Tân Ninh/Tây Ninh is another name
        return 'near', hit
    words = [t for t in nk if not t[0].isdigit()]
    parts = [c for c in cands if c[0] != 'province' and set(words) & set(c[1])]
    if len(words) > 1 and all(any(t in c[1] for c in parts) for t in words) \
            and not any(set(words) <= set(c[1]) for c in parts):
        return 'compound', parts
    hit = [c for c in nearby if c[1] == nk]
    if hit:
        return 'reused', hit
    return 'new', []


def witness_b(nk, cands):
    """Nearest source by edit distance on the folded name, and the share of it that must change."""
    t = text(nk)
    scored = [(lev(t, text(c[1])), c) for c in cands]
    if not scored:
        return [], 99, 1.0
    d = min(s for s, _ in scored)
    return [c for s, c in scored if s == d], d, d / max(len(t), 1)


def settle(kind, src, best, ratio):
    """Syllable matches settle themselves. A person sees what the rules cannot prove:
    a one-letter difference, a compound, and a 'new' name that B finds close to a source."""
    names = lambda cs: ' + '.join(sorted({c[2] for c in cs}))
    if kind == 'near':
        return 'check', f'one letter from {names(src)}: correction or another name?'
    if kind == 'compound':
        return 'check', f'built from {len(src)} names: coincidence or intent?'
    if kind == 'new' and ratio <= NEAR:
        return 'check', f'B finds {names(best)} close ({ratio:.2f})'
    return 'auto', ''


# --- data --------------------------------------------------------------------------------------

def split(s):
    return [c for c in s.split(';') if c]


def read(name):
    path = HERE / name
    return list(csv.DictReader(open(path, encoding='utf-8'))) if path.exists() else []


def write(name, rows, cols):
    with open(HERE / name, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore', lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def crosswalk(old, new):
    """Checks that could fail: every old commune lands somewhere, and every hand-typed code sits in
    a province the unit's machine-matched codes already come from. Returns flags and bad hand codes."""
    used, flags, bad = Counter(), [], set()
    for u in new:
        machine = split(u['old_codes'])
        provinces = {old[c]['province'] for c in machine if c in old}
        for c in machine + split(u['hand_codes']):
            used[c] += 1
            if c not in old:
                flags.append({'province': u['province'], 'name': u['name'], 'code': c, 'type': 'unknown code',
                              'flag': 'code not in the GSO list'})
        for c in split(u['hand_codes']):
            if c in old and provinces and old[c]['province'] not in provinces:
                bad.add((u['province'], u['name'], c))
                flags.append({'province': u['province'], 'name': u['name'], 'code': c, 'type': 'hand code elsewhere',
                              'flag': f"hand code is {old[c]['name']}, {old[c]['district']}, {old[c]['province']}; "
                                      f"the unit's other codes are in {', '.join(sorted(provinces))}"})
    for c, o in old.items():
        if not used[c]:
            flags.append({'province': o['province'], 'name': '', 'code': c, 'type': 'old unit unassigned',
                          'flag': f"{o['type']} {o['name']}, {o['district']} is in no new unit"})
    return flags, bad, sum(n > 1 for n in used.values())


def main():
    old = {r['code']: r for r in read('data/old_units.csv')}
    new = read('data/new_units.csv')
    decided = {(d['province'], d['name']): d for d in read('decisions.csv')}
    flags, bad, shared = crosswalk(old, new)

    by_province = defaultdict(dict)
    for o in old.values():
        for lvl, nm in (('ward', o['name']), ('district', o['district'])):
            by_province[o['province']].setdefault((lvl, key(nm)), nm)

    rows = []
    for u in new:
        codes = [c for c in split(u['old_codes']) + split(u['hand_codes'])
                 if c in old and (u['province'], u['name'], c) not in bad]
        cands = {}
        for c in codes:
            o = old[c]
            for lvl, nm in (('ward', o['name']), ('district', o['district']), ('province', o['province'])):
                cands.setdefault((lvl, key(nm)), nm)
        for nm in u['sources_text'].split(','):   # island districts kept whole: "Huyện Côn Đảo"
            if re.match(r'\s*huyện\s', nm, re.I):
                cands[('district', key(nm))] = nm.strip()
        cands = [(lvl, k, nm) for (lvl, k), nm in cands.items()]
        nearby = [(lvl, k, nm) for p in {old[c]['province'] for c in codes}
                  for (lvl, k), nm in by_province[p].items() if (lvl, k, nm) not in cands]

        nk = key(u['name'])
        kind, src = witness_a(nk, cands, nearby)
        best, d, ratio = witness_b(nk, cands)
        status, reason = settle(kind, src, best, ratio)
        levels = {c[0] for c in src}
        origin = next((lvl for lvl in LEVELS if lvl in levels), '')
        row = {'province': u['province'], 'name': u['name'], 'kind': kind, 'origin': origin,
               'sources': ' + '.join(sorted({f'{c[2]} ({c[0]})' for c in src})),
               'b_nearest': ' + '.join(sorted({c[2] for c in best})), 'b_distance': d,
               'status': status, 'reason': reason, 'decided_by': ''}
        if (u['province'], u['name']) in decided:
            dec = decided[(u['province'], u['name'])]
            row.update(kind=dec['kind'], origin=dec['origin'], status='decided', decided_by=f"{dec['by']} {dec['date']}")
        row['family'] = FAMILY[row['kind']]
        rows.append(row)

    cols = ['province', 'name', 'family', 'kind', 'origin', 'sources', 'b_nearest', 'b_distance',
            'status', 'reason', 'decided_by']
    write('out/names.csv', rows, cols)
    write('out/queue.csv', [r for r in rows if r['status'] == 'check'], cols)
    write('out/crosswalk_flags.csv', flags, ['type', 'province', 'name', 'code', 'flag'])

    n = len(rows)
    pct = lambda c: f'{c:>5} ({100 * c / n:4.1f} %)'
    print(f'Crosswalk: {n} new units, {len(old)} old units, {shared} old units shared by two or more new ones')
    for t, c in Counter(f['type'] for f in flags).most_common():
        print(f'  flag  {c:>4}  {t}')
    print('\nKind (witness A, after decisions):')
    for k, c in Counter(r['kind'] for r in rows).most_common():
        print(f'  {k:<9}{pct(c)}')
    print('\nFamily    this run          article')
    fam = Counter(r['family'] for r in rows)
    for f in ('whole', 'partial', 'new'):
        print(f'  {f:<8}{pct(fam[f])}   {ARTICLE[f]:>5}')
    print('\nOrigin of kept names:', dict(Counter(r['origin'] for r in rows if r['family'] != 'new')))
    print('Status:', dict(Counter(r['status'] for r in rows)))
    print('Queue by kind:', dict(Counter(r['kind'] for r in rows if r['status'] == 'check')))


def selftest():
    assert key('Hoà Tú') == key('Hòa Tú') and key('Phú Quí') == key('Phú Quý')
    assert key('Thuý') != key('Thúi') and key('Xã Bờ Y') == key('Bờ Y')
    assert key('Hoà Tú II') == key('Hoà Tú 2') and key("Cư M'gar") == key('Cư M’gar')
    assert lev('kitten', 'sitting') == 3
    c = lambda *ns: [('ward', key(n), n) for n in ns]
    a = lambda name, *ns: witness_a(key(name), c(*ns), [])[0]
    assert a('Thành Bình Thọ', 'Thành Sơn', 'Bình Sơn', 'Thọ Sơn') == 'compound'
    assert a('Hội An Tây', 'Hội An', 'Cẩm Phô') == 'affix'
    assert a('Thường Phước', 'Thường Phước 1', 'Thường Phước 2') == 'affix'
    assert a('Nà Hang', 'Na Hang') == 'variant' and a('Avương', 'A Vương') == 'variant'
    assert a('Phan Rang', 'Phan Rang-Tháp Chàm') == 'part'
    assert a('Chợ Lớn', '11', '12', '13') == 'new'
    assert a('Hà Nam', 'Hà') == 'new'
    assert witness_a(key('Tân An'), [], [('district', key('Tân An'), 'Tân An')])[0] == 'reused'
    assert a('Tân Thành', 'Tân Thành A') == 'affix' and a('Tân Ninh', 'Tây Ninh') == 'near'
    assert settle('near', c('Tây Ninh'), c('Tây Ninh'), 0.1)[0] == 'check'
    assert settle('new', [], c('Tân Anh'), 0.1)[0] == 'check'
    print('ok')


if __name__ == '__main__':
    selftest() if '--check' in sys.argv else main()
