"""Does the 2025 crosswalk list the right old communes? The resolutions say.

The 34 provincial resolutions (UBTVQH15 nos. 1654-1687, one per new province) state for every new
commune which old communes it was built from. This reads them, resolves each old name to a GSO
code inside the new province's old provinces, and compares the code set with the sheet's
(`old_codes` after CODE_FIXES, plus `hand_codes`). Classes per new unit: agree, wrong_commune
(the sheet has a commune the resolution lacks and lacks one it names), missing_source,
extra_source; unparsed, ambiguous, unresolved and no_codes (island districts) are left out of the
rate. Raw pages stay outside the repo; the derived item table is committed (legal texts are free of
copyright, IP Law Art. 15).

    python3 -I work/research/admin-2025/resolutions.py --fetch DIR   # download the 34 pages
    python3 -I work/research/admin-2025/resolutions.py DIR [PROVINCE] # write data/ and out/, print both rates
    python3 -I work/research/admin-2025/resolutions.py --check [DIR]  # self-test (more if DIR has pages)

DIR defaults to ~/Work/Data/resolutions-2025. Pages are untrusted data: run with -I.
"""
import html
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import names                      # noqa: E402  (same folder: key(), CODE_FIXES, crosswalk())

DEFAULT_DIR = Path.home() / 'Work/Data/resolutions-2025'
HOATIEU = 'https://hoatieu.vn/phap-luat/x-'
IDS = ('233499 233500 233501 233503 233508 233513 233523 233527 233528 233530 233531 233532 233533 233542 '
       '233546 233548 233550 233552 233554 233557 233558 233560 233561 233566 233568 233575 233578 233609 '
       '233610 233611 233612 233613 233614 233615').split()
ALIAS = {'hồ chí minh': 'TP HCM'}                          # the sheet's name for the city
UP = '[A-Z' + ''.join(c for c in map(chr, range(0xC0, 0x1EFA)) if c.isupper()) + ']'   # a capital, with marks
TYPES = r'thị trấn|thị xã|thành phố|phường|xã|đặc khu|huyện|quận'
KIND_OF = {'xã': 'Xã', 'phường': 'Phường', 'thị trấn': 'Thị trấn'}
ITEM = re.compile(r'^\s*(\d+)\.\s*(.*\S)\s*$')
NEWNAME = re.compile(r'thành\s*(?P<t>xã|phường|đặc\s*khu|thị\s*trấn)\s*(?:mới)?\s*(?:có\s*tên\s*gọi\s*là)?\s*'
                     r'(?:(?:xã|phường|đặc\s*khu|thị\s*trấn)\s*)?(?P<n>[^.]+?)\s*\.?\s*$')
DESC = r'(?:diện\s*tích(?:\s*tự\s*nhiên)?|quy\s*mô\s*dân(?:\s*số)?)'
DESCS = DESC + r'(?:\s*(?:,|và)?\s*' + DESC + r')?'
AFTER = re.compile(r'sau\s*khi\s*(?:thực\s*hiện\s*)?sắp\s*xếp\s*theo\s*quy\s*định\s*tại\s*(?:các\s*)?khoản\s*\d+'
                   r'(?:\s*(?:,|và)\s*(?:khoản\s*)?\d+)*(?:\s*(?:của\s*)?Điều\s*này)?')
FOUND = re.compile(r'^(?:các\s+)?(?:(?P<t>' + TYPES + r')\s*)?(?P<n>.*?)\s*(?:\((?P<q>[^)]*)\))?\s*$', re.I)


# --- text ---------------------------------------------------------------------------------------

def plain(page):
    """HTML -> lines of NFC text. The site's own typos stay; `parse_sources` copes with them."""
    s = re.sub(r'(?is)<(script|style)\b.*?</\1>', '', page)
    s = re.sub(r'(?i)<(br|/p|/div|/h\d|/li|/tr)[^>]*>', '\n', s)
    s = unicodedata.normalize('NFC', html.unescape(re.sub(r'<[^>]+>', ' ', s))).replace('\xa0', ' ')
    return re.sub(r'\n\s*\n+', '\n', re.sub(r'[ \t]+', ' ', s))


def province_of(text):
    m = re.search(r'cấp xã của (?:tỉnh|thành phố) ([^\n]+?)(?: năm 2025)?\s*\n', text, re.I)
    p = m.group(1).strip()
    return next((v for k, v in ALIAS.items() if names.key(p) == names.key(k)), p)


def article_one(text):
    i = re.search(r'(?m)^\s*Điều 1\.', text).start()
    j = re.search(r'(?m)^\s*Điều 2\.', text[i:]).start()
    return [m.groups() for m in map(ITEM.match, text[i:i + j].split('\n')[1:]) if m]


# --- one item -----------------------------------------------------------------------------------

def clean(n):
    return re.sub(r'\s+', ' ', n.replace('§', ' ')).strip(' ,.;')


def parse_sources(s):
    """'các xã A, B và một phần diện tích ... của xã C (huyện D)' -> [(type, name, qualifier, mark)].
    mark: 'W' whole, 'P' part, 'R' remainder. Marks and types carry on to the names after them."""
    s = re.sub(r'^(?:Sắp\s*xếp|Nhập)\s*', '', s)
    s = re.sub(r'phần\s*(?:' + DESCS + r'\s*)?còn\s*lại(?:\s*của)*', ' §R ', s)
    s = re.sub(r'một\s*phần\s*(?:' + DESCS + r')?(?:\s*của)*', ' §P ', s)
    s = re.sub(r'(?:toàn\s*)?bộ\s*(?:' + DESCS + r')?(?:\s*của)*', ' §W ', s)
    s = AFTER.sub(' ', s)
    s = re.sub(r'\b(' + TYPES + r')(?=' + UP + r')', r'\1 ', s)          # xãQuảng Chu
    s = re.sub(r'\s+và\s+|\s*và(?=\s*(?:§|các|' + TYPES + r'))|(?<=\S)và\s+(?=' + UP + r')|\s+và(?=' + UP + r')', ' , ', s)  # Chuvà các, Tiếnvà Nhất
    s = re.sub(r'\bcác(?=' + TYPES + r')', 'các ', s)                 # cácxã
    s = re.sub(r'(?<=[a-zà-ỹ0-9])(?<!các)(?<!thị)\s(?=(?:xã|phường|thị trấn|thị xã)\s)(?![^()]*\))|(?<=\d)\s(?=Phường\s)', ' , ', s)    # a comma lost: Cầm xã Nam Phúc Thăng
    mark, typ, out = 'W', '', []
    for tok in re.split(r',(?![^()]*\))', s):
        tok = tok.strip()
        while tok.startswith('§'):                               # a marker leads the entry it applies to
            mark, tok = tok[1], tok[2:].strip()
        m = FOUND.match(tok)
        typ = (m.group('t') or typ).lower() if m.group('n') else typ
        if clean(m.group('n')):
            out.append((typ, clean(m.group('n')), (m.group('q') or '').strip(), mark))
    return out


def parse_item(line):
    """-> dict(kind, new_type, new_name, sources) or None. kind: merge, rename, closing."""
    if line.startswith('Sau khi'):
        tail = line.split('không thực hiện sắp xếp', 1)
        if len(tail) == 2:
            return dict(kind='closing', new_type='', new_name='', sources=parse_sources(re.sub(r'^\s*(?:là|gồm)\s*|\s*\.\s*$', '', tail[1])))
        return dict(kind='closing', new_type='', new_name='', sources=[])
    m = re.match(r'Đổi\s*tên\s*(' + TYPES + r')\s*(.+?)\s*thành\s*(' + TYPES + r')\s*(.+?)\s*\.?\s*$', line)
    if m:
        return dict(kind='rename', new_type=m.group(3), new_name=clean(m.group(4)), sources=[(m.group(1), clean(m.group(2)), '', 'W')])
    m = NEWNAME.search(line)
    if not m:
        return None
    head = line[:m.start()]
    return dict(kind='merge', new_type=re.sub(r'\s+', ' ', m.group('t')), new_name=clean(m.group('n')),
                sources=parse_sources(head))


# --- resolving old names to codes ------------------------------------------------------------

def qual_keys(q):
    """'(thuộc huyện Đăk Hà)' or '(huyện Châu Thành, tỉnh Trà Vinh)' -> folded district and province."""
    return {names.key(re.sub(r'^thuộc\s+', '', t.strip())) for t in q.split(',') if t.strip()}


def candidates(src, pool):
    """One source name -> (old rows that could be it, note, the same before the type narrowed them).
    pool: the old communes of the new province's old provinces. Same folded name, narrowed by the
    district qualifier and the type (the GSO list types some numbered wards as Xã, so `choose` also
    sees the rows before the type).
    No same name, or none in the qualified district: the same letters with marks or spacing apart
    (Cỗ/Cổ Đạm, A Vương/Avương, Ea Bar/EaBar)."""
    typ, name, qual, _ = src
    if typ in ('huyện', 'quận'):
        hit = [o for o in pool if names.key(o['district']) == names.key(name)]
        return hit, 'district', hit   # all its communes
    k, note = names.key(name), ''
    qk = qual_keys(qual)
    inside = lambda hits: [o for o in hits if names.key(o['district']) in qk]
    hit = [o for o in pool if names.key(o['name']) == k]
    loose = lambda: [o for o in pool if names.squash(names.key(o['name'])) == names.squash(k)]
    if not hit or (qk and not inside(hit) and inside(loose())):
        hit, note = loose(), 'spelling'
    if hit and typ in KIND_OF and not any(o['type'] == KIND_OF[typ] for o in hit):
        alt = [o for o in loose() if o['type'] == KIND_OF[typ]]      # thị trấn Thạnh An is listed as Thanh An
        hit, note = alt or hit, 'spelling' if alt else note
    if not hit:
        return [], 'unresolved', []
    if qk:
        by = inside(hit)       # the province too, if the qualifier gives one
        by = [o for o in by if names.key(o['province']) in qk] if len(by) > 1 and any(
            names.key(o['province']) in qk for o in by) else by
        if by or len(hit) > 1:
            note = note or ('' if by else 'qualifier unmatched')
            hit = by or hit
    wide = hit
    if len(hit) > 1 and typ in KIND_OF:
        hit = [o for o in hit if o['type'] == KIND_OF[typ]] or hit
    return hit, note, wide


def choose(i, srcs, cands, sheet, taken):
    """Several old communes carry the name: pick by the qualifier that follows (Phường 1, 3, 4 và
    Phường 6 (thành phố Cao Lãnh)), then by the districts of the item's other sources, then by the
    sheet. Returns (code or None, how)."""
    hit, wide = cands[i][0], cands[i][2]
    later = next((srcs[j][2] for j in range(i, len(srcs)) if srcs[j][2]), '')
    near = {h[0]['district_code'] for h, _, _ in cands if len(h) == 1}
    for rows in (hit, wide):         # the GSO list types some numbered wards as Xã: look past the type last
        by = [o for o in rows if later and names.key(o['district']) in qual_keys(later)]
        if len(by) == 1:
            return by[0]['code'], 'by the next qualifier'
    for rows in (hit, wide):
        by = [o for o in rows if o['district_code'] in near]
        if len(by) == 1:
            return by[0]['code'], 'by the item\'s districts'
    by = [o for o in hit if o['code'] not in taken]       # a whole commune goes to one item only
    if len(by) == 1:
        return by[0]['code'], 'by elimination'
    by = [o for o in hit if o['code'] in sheet]
    if len(by) == 1:
        return by[0]['code'], 'by the sheet'
    return None, 'ambiguous'


def close(a, b):
    """Two names no rule folds together, a letter or two apart (Zuôih/Zuôich): the same commune
    written two ways, but only offered for a sheet commune no other source claimed."""
    a, b = names.squash(names.key(a)), names.squash(names.key(b))
    return len(a) >= 4 and names.lev(a, b) <= max(1, len(a) // 5)


def compare(sheet, res):
    miss, extra = res - sheet, sheet - res
    if not miss and not extra:
        return 'agree'
    return 'wrong_commune' if miss and extra else 'missing_source' if miss else 'extra_source'


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, mid - h), min(1, mid + h)


# --- the run -----------------------------------------------------------------------------------

def load_sheet(raw=False):
    """The sheet as names.py reads it: CODE_FIXES applied (raw=True: not), and the hand codes it
    drops as another province's left out."""
    old = {r['code']: r for r in names.read('data/old_units.csv')}
    for c, nm in names.NAME_FIXES.items():
        old[c]['name'] = nm
    new = names.read('data/new_units.csv')
    for u in new:
        if not raw:
            u['old_codes'] = names.CODE_FIXES.get((u['province'], u['name']), u['old_codes'])
    drop = names.crosswalk(old, new)[1]
    for u in new:
        u['hand_codes'] = ';'.join(c for c in names.split(u['hand_codes']) if (u['province'], u['name'], c) not in drop)
    return old, new


def run(folder, only=None, raw=False):
    old, new = load_sheet(raw)
    by_prov = defaultdict(dict)
    for u in new:
        by_prov[u['province']][names.key(u['name'])] = u
    sheet_of = lambda u: set(names.split(u['old_codes']) + names.split(u['hand_codes']))
    show = lambda cs: ' | '.join(f"{old[c]['name']} ({old[c]['district']}) {c}" for c in sorted(cs) if c in old)
    items_out, units_out = [], []
    for page in sorted(Path(folder).glob('r*.html')):
        no = page.stem[1:]
        text = plain(page.read_text(encoding='utf-8'))
        prov = province_of(text)
        if only and names.key(prov) != names.key(only):
            continue
        prov = next((p for p in by_prov if names.key(p) == names.key(prov)), prov)     # the sheet's spelling
        units = by_prov[prov]
        olds = {old[c]['province'] for u in units.values() for c in sheet_of(u) if c in old}
        pool = [o for o in old.values() if o['province'] in olds]
        seen, closing = {}, None
        for n, line in article_one(text):
            it = parse_item(line)
            if it is None:
                units_out.append(dict(province=prov, name='', res=no, item=n, cls='unparsed', note=line[:120]))
            elif it['kind'] == 'closing':
                closing = it
            else:
                seen[names.key(it['new_name'])] = (n, it)
        merges = list(seen.items())
        for t, nm, q, _ in (closing['sources'] if closing else []):       # kept unchanged: its own single source
            seen.setdefault(names.key(nm), ('closing', dict(kind='kept', new_type=t, new_name=nm, sources=[(t, nm, q, 'W')])))
        used, taken = set(), set()
        for k, (n, it) in list(seen.items()):
            u = units.get(k)
            sheet = sheet_of(u) if u else set()
            srcs = it['sources']
            # a kept commune is one no merge item named: leave the used codes out
            cands = [candidates(src, [o for o in pool if o['code'] not in used] if it['kind'] == 'kept' else pool)
                     for src in srcs]
            got = [([o['code'] for o in h], nt) if nt == 'district' else ([h[0]['code']], nt) if len(h) == 1 else ([], nt)
                   for h, nt, _ in cands]
            for i, (h, nt, _) in enumerate(cands):
                if len(h) > 1 and nt != 'district':
                    code, how = choose(i, srcs, cands, sheet, taken)
                    got[i] = ([code], (nt + ' ' if nt else '') + how) if code else ([], 'ambiguous')
            res = {c for codes, _ in got for c in codes}
            for i, ((codes, note), src) in enumerate(zip(got, srcs)):
                if note == 'unresolved':          # a lone leftover sheet commune, a letter or two off
                    left = [c for c in sheet - res if c in old and close(src[1], old[c]['name'])]
                    if len(left) == 1:
                        got[i] = ([left[0]], 'spelling: close')
                        res.add(left[0])
            if it['kind'] != 'kept':
                used |= res
                taken |= {c for (codes, _), src in zip(got, srcs) if src[3] == 'W' for c in codes}
            notes, parts = [], []
            for (codes, note), src in zip(got, srcs):
                if note:
                    notes.append(f'{src[1]}: {note}')
                parts.append(f"{src[0]} {src[1]}" + (f' ({src[2]})' if src[2] else '') +
                             {'W': '', 'P': ' [part]', 'R': ' [rest]'}[src[3]] + ' = ' + (','.join(codes) or '-'))
            items_out.append(dict(res=no, item=n, kind=it['kind'], new_type=it['new_type'], new_name=it['new_name'],
                                  sources=' ; '.join(parts), codes=';'.join(sorted(res)), notes=' ; '.join(notes)))
            bad = [x for x in notes if x.endswith(('unresolved', 'ambiguous'))]
            if u is None:
                units_out.append(dict(province=prov, name=it['new_name'], res=no, item=n, cls='unparsed',
                                      note='no such unit in the sheet'))
                continue
            if bad:
                cls = 'unresolved' if any(x.endswith('unresolved') for x in bad) else 'ambiguous'
            elif not sheet and all(src[0] in ('huyện', 'quận') for src in srcs):     # an island district, recorded by name
                cls = 'no_codes'
            else:
                cls = compare(sheet, res)
            units_out.append(dict(province=prov, name=u['name'], sheet_codes=';'.join(sorted(sheet)),
                                  res_codes=';'.join(sorted(res)), cls=cls, res=no, item=n,
                                  only_in_sheet=show(sheet - res), only_in_resolution=show(res - sheet),
                                  note=' ; '.join(notes)))
        for k, u in units.items():
            if k not in seen:
                units_out.append(dict(province=prov, name=u['name'], sheet_codes=';'.join(sorted(sheet_of(u))),
                                      cls='unparsed', res=no, item='', note='in the sheet, in no parsed item'))
    return items_out, units_out


PICKS = ('next qualifier', "item's districts", 'elimination', 'by the sheet', 'spelling')


def report(units_out):
    c = Counter(r['cls'] for r in units_out)
    for k in ('agree', 'wrong_commune', 'missing_source', 'extra_source', 'ambiguous', 'unresolved', 'unparsed', 'no_codes'):
        print(f'  {k:<15}{c[k]:>5}')
    bad = c['wrong_commune'] + c['missing_source'] + c['extra_source']
    n = bad + c['agree']
    out = c['ambiguous'] + c['unresolved'] + c['unparsed'] + c['no_codes']
    lo, hi = wilson(bad, n)
    print(f'\nWrong source list: {bad} of {n} checked units = {100 * bad / n:.2f} %  (Wilson 95 % {100 * lo:.2f}-{100 * hi:.2f} %)')
    print(f'Left out of the rate: {out} (ambiguous {c["ambiguous"]}, unresolved {c["unresolved"]}, '
          f'unparsed {c["unparsed"]}, no_codes {c["no_codes"]})')
    rest = lambda cls: sum(1 for r in units_out if r['cls'] in cls and any(p in r.get('note', '') for p in PICKS))
    print(f'Rest on a pick (qualifier, district, spelling or sheet): {rest(("agree",))} agree, '
          f'{rest(("wrong_commune", "missing_source", "extra_source"))} wrong')
    pure = bad - rest(('wrong_commune', 'missing_source', 'extra_source'))
    plo, phi = wilson(pure, pure + c['agree'] - rest(('agree',)))
    print(f'Names alone (no pick): {pure} of {pure + c["agree"] - rest(("agree",))} = '
          f'{100 * pure / (pure + c["agree"] - rest(("agree",))):.2f} %  (Wilson 95 % {100 * plo:.2f}-{100 * phi:.2f} %)')
    return bad, n


def fetch(folder):
    import urllib.request
    Path(folder).mkdir(parents=True, exist_ok=True)
    for i in IDS:
        req = urllib.request.Request(HOATIEU + i, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as r:
            body = r.read()
            no = re.search(r'nghi-quyet-(\d{4})-nq', r.geturl()).group(1)
        (Path(folder) / f'r{no}.html').write_bytes(body)
        print('r' + no)


def main(folder, only=None):
    """The findings come from the sheet as downloaded (no CODE_FIXES); `fixed` says which have an entry."""
    items, units = run(folder, only, raw=True)
    for u in units:
        u['fixed'] = 'yes' if (u['province'], u['name']) in names.CODE_FIXES else ''
    if not only:
        names.write('data/resolution_items.csv', items, ['res', 'item', 'kind', 'new_type', 'new_name', 'sources', 'codes', 'notes'])
        names.write('out/resolution_check.csv', units, ['province', 'name', 'sheet_codes', 'res_codes', 'cls', 'res', 'item',
                                                         'only_in_sheet', 'only_in_resolution', 'fixed', 'note'])
    print('The sheet as downloaded:')
    report(units)
    print('\nAfter CODE_FIXES:')
    report(run(folder, only)[1])


def selftest(folder):
    parse = lambda s: parse_item(s)
    a = parse('Sắp xếp toàn bộ diện tích tự nhiên, quy mô dân số của xã Lộc Thịnh và xã Lộc Thành thành xã mới có tên gọi là xã Lộc Thành.')
    assert a['new_name'] == 'Lộc Thành' and [s[1] for s in a['sources']] == ['Lộc Thịnh', 'Lộc Thành']
    a = parse('Sắp xếp toàn bộ diện tích tự nhiên, quy mô dân số của thị trấn Chợ Chuvà các xã Phúc Chu, Bảo Linh, Đồng Thịnh thành xã mới có tên gọi là xã Định Hóa.')
    assert [(s[0], s[1]) for s in a['sources']] == [('thị trấn', 'Chợ Chu'), ('xã', 'Phúc Chu'), ('xã', 'Bảo Linh'), ('xã', 'Đồng Thịnh')]
    a = parse('Sắp xếp toàn bộ diện tích tự nhiên, quy mô dân số của các phường Trung Thành (thành phố Thái Nguyên), Phú Xá, Tích Lương vàmột phần diện tích tự nhiên, quy mô dân số phường Cam Giá thành phường mới có tên gọi là phường Tích Lương.')
    assert a['sources'][0][2] == 'thành phố Thái Nguyên' and a['sources'][-1] == ('phường', 'Cam Giá', '', 'P')
    a = parse('Sắp xếp toàn bộ diện tích tự nhiên, quy mô dân số của phường Hương Sơn, phần còn lại của phường Gia Sàngsau khi sắp xếp theo quy định tại khoản 76 Điều này và phần còn lại củaphường Cam Giásau khi sắp xếp theo quy định tại khoản78 Điều nàythành phường mới có tên gọi là phường Gia Sàng.')
    assert [(s[1], s[3]) for s in a['sources']] == [('Hương Sơn', 'W'), ('Gia Sàng', 'R'), ('Cam Giá', 'R')]
    a = parse('Sắp xếp một phần diện tích tự nhiên, quy mô dân số của các phường A, B, một phần diện tích tự nhiên của phường C và phần còn lại của phường D sau khi sắp xếp theo quy định tại khoản 15, khoản 16 Điều này thành phường mới có tên gọi là phường E.')
    assert [(s[1], s[3]) for s in a['sources']] == [('A', 'P'), ('B', 'P'), ('C', 'P'), ('D', 'R')]
    a = parse('Sắp xếp toàn bộ diện tích tự nhiên, quy mô dân số của Phường 1 Phường 2, Phường 7 và Phường 8 (thành phố Bạc Liêu), Phường 3 thành phường mới có tên gọi là phường Bạc Liêu.')
    assert [s[1] for s in a['sources']] == ['1', '2', '7', '8', '3'] and a['sources'][3][2] == 'thành phố Bạc Liêu'
    a = parse('Sắp xếp toàn bộ diện tích tự nhiên, quy mô dân số của xã Ninh Thạnh Lợi A và xã Ninh Thạnh Lợi thành xã Ninh Thạnh Lợi.')
    assert a['new_name'] == 'Ninh Thạnh Lợi' and len(a['sources']) == 2
    a = parse('Đổi tên xã Krông Na thành xã Buôn Đôn.')
    assert a['kind'] == 'rename' and a['sources'][0][1] == 'Krông Na' and a['new_name'] == 'Buôn Đôn'
    a = parse('Sau khi sắp xếp, tỉnh X có 5 đơn vị, trong đó có 2 xã không thực hiện sắp xếp là xã Sảng Mộc, xã Thượng Quan.')
    assert [s[1] for s in a['sources']] == ['Sảng Mộc', 'Thượng Quan']
    assert wilson(0, 10)[0] == 0 and abs(wilson(5, 10)[0] - 0.2366) < 1e-3
    assert compare({'1', '2'}, {'1', '3'}) == 'wrong_commune' and compare({'1'}, {'1', '2'}) == 'missing_source'
    pool = [dict(code='1', name='Lộc Thạnh', district='Lộc Ninh', district_code='1', province='X', type='Xã'),
            dict(code='2', name='Lộc Thành', district='Lộc Ninh', district_code='1', province='X', type='Xã'),
            dict(code='3', name='Ea Bar', district='Buôn Đôn', district_code='2', province='X', type='Xã'),
            dict(code='4', name='EaBar', district='Sông Hinh', district_code='3', province='X', type='Xã')]
    assert candidates(('xã', 'Lộc Thành', '', 'W'), pool)[0] == [pool[1]]           # one mark apart: two communes
    assert candidates(('xã', 'Ea Bar', 'huyện Sông Hinh', 'W'), pool)[:2] == ([pool[3]], 'spelling')
    if Path(folder).exists():
        at = lambda units, no, n: next(r for r in units if r['res'] == no and r['item'] == n)
        items, units = run(folder)
        for no, n, name in (('1662', '43', 'Lộc Thành'), ('1661', '20', 'Sáng Nhè'), ('1683', '27', 'Văn Lăng')):
            r = at(units, no, n)
            assert r['name'] == name and r['cls'] == 'agree', r            # with CODE_FIXES applied
        r = at(run(folder, raw=True)[1], '1662', '43')                       # without them the check fails
        assert r['cls'] == 'wrong_commune' and 'Lộc Thạnh' in r['only_in_sheet'] and 'Lộc Thành' in r['only_in_resolution'], r
        assert len(items) == len(names.read('data/new_units.csv')) == 3321      # one item per new unit
    print('ok')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['--fetch']:
        fetch(a[1] if len(a) > 1 else DEFAULT_DIR)
    elif a[:1] == ['--check']:
        selftest(a[1] if len(a) > 1 else DEFAULT_DIR)
    else:
        main(a[0] if a else DEFAULT_DIR, a[1] if len(a) > 1 else None)
