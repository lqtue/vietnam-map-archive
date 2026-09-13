import { expect, test } from '@playwright/test';
import {
  buildGallicaQuery,
  gallicaSearchUrl,
  spellingVariants,
  unaccent,
} from '../src/lib/server/gallica';
import {
  filterNlvByYear,
  mergeByDate,
  nlvDate,
  nearestNlvRows,
  nlvItem,
  nlvSearchUrl,
  oidDate,
  parseNlvCurve,
  parseNlvRows,
  parseNlvTotal,
} from '../src/lib/server/press';

// Pure checks for the two /api/press providers: Gallica's CQL builder and the
// NLV year-window filter.
//
// ponytail: the repo has no unit-test runner, so the pure checks ride the
// Playwright suite as browser-less tests. Nothing here touches the network or
// the dev server.
//
// What matters: Gallica's full text is OCR of colonial print and is mostly
// unaccented. If the unaccented spelling ever falls out of the query, /api/press
// returns nothing for every Vietnamese label and looks merely "empty".

test('unaccent strips Vietnamese diacritics, including đ', () => {
  expect(unaccent('Khánh Hội')).toBe('Khanh Hoi');
  expect(unaccent('Đa Kao')).toBe('Da Kao');
  expect(unaccent('Chợ Lớn đường')).toBe('Cho Lon duong');
});

test('spellingVariants OR-candidates: unaccented first, then hyphenated, then accented', () => {
  expect(spellingVariants('Khánh Hội')).toEqual(['Khanh Hoi', 'Khanh-Hoi', 'Khánh Hội']);
  // Already-hyphenated input normalises to the same three forms.
  expect(spellingVariants('Khanh-Hoi')).toEqual(['Khanh Hoi', 'Khanh-Hoi']);
  // One word has no hyphenated form; plain ASCII has no accented form.
  expect(spellingVariants('Saigon')).toEqual(['Saigon']);
});

test('buildGallicaQuery emits the CQL for a diacritic two-word label', () => {
  expect(buildGallicaQuery('Khánh Hội', 1923, 10)).toBe(
    '((gallica adj "Khanh Hoi") or (gallica adj "Khanh-Hoi") or (gallica adj "Khánh Hội")) ' +
      'and (dc.date >= "1913" and dc.date <= "1933")'
  );
});

test('the unaccented form is always present, and always first', () => {
  for (const label of ['Khánh Hội', 'Chợ Quán', 'Đa Kao', 'Thủ Đức', 'Saigon']) {
    const cql = buildGallicaQuery(label, 1930, 5);
    expect(cql).toContain(`(gallica adj "${unaccent(label)}")`);
    expect(cql.indexOf(`"${unaccent(label)}"`)).toBe(cql.indexOf('"'));
  }
});

test('the date range is year ± window', () => {
  expect(buildGallicaQuery('Saigon', 1900, 0)).toContain(
    '(dc.date >= "1900" and dc.date <= "1900")'
  );
  expect(buildGallicaQuery('Saigon', 1900, 25)).toContain(
    '(dc.date >= "1875" and dc.date <= "1925")'
  );
});

test('quotes and brackets cannot break out of the CQL phrase', () => {
  const cql = buildGallicaQuery('Khanh" or (gallica all "war', 1923, 10);
  // Quote and paren are stripped, so the injection stays inside the phrases.
  expect(cql).toBe(
    '((gallica adj "Khanh or gallica all war") or (gallica adj "Khanh-or-gallica-all-war")) ' +
      'and (dc.date >= "1913" and dc.date <= "1933")'
  );
});

test('gallicaSearchUrl is a well-formed SRU call', () => {
  const url = new URL(gallicaSearchUrl(buildGallicaQuery('Khánh Hội', 1923, 10), 3));
  expect(url.origin + url.pathname).toBe('https://gallica.bnf.fr/SRU');
  expect(url.searchParams.get('operation')).toBe('searchRetrieve');
  expect(url.searchParams.get('version')).toBe('1.2');
  expect(url.searchParams.get('maximumRecords')).toBe('3');
  expect(url.searchParams.get('query')).toContain('gallica adj "Khanh Hoi"');
});

/* ------------------------------------------------------- nlv (baochi.nlv.gov.vn) */

// One Veridian results page, trimmed to two results and the decade facet. The
// archive answers over http only and returns no matched text — the page image
// and its `crop` box are the evidence — so what these checks defend is that the
// oid, the date, the publication and the crop all survive the parse.
//
// The important failure is silent: a Veridian template change produces zero rows
// against a stated total, which reads as "the archive has nothing on this place"
// rather than as a bug. `fetchNlvPress` turns that into a degradation; this pins
// the parse itself.
const NLV_HTML = `
<td class="veridiansearchtablesubcontrolcell">
  Quá trình tìm kiếm for <b>Khánh Hội</b> trả về 88 kết quả. Hiển thị các kết quả từ 1 to 20.
</td>
<table cellpadding="3" cellspacing="0"><tr valign="top">
  <td><a href="/baochi/cgi-bin/baochi?a=d&amp;d=RbD19230501.2.9.1&amp;srpos=1&amp;e=-----">Chợ Khánh Hội &#91;Bài báo&#93;</a>
  <div>Sài Gòn 1 Tháng Năm 1923</div>
  <div class="veridiansnippetimagecontainerdiv"><img src="/baochi/cgi-bin/imageserver/imageserver.pl?oid=RbD19230501.2.9.1&amp;area=1&amp;crop=209,3322,621,81&amp;width=311&amp;color=all&amp;ext=jpg&amp;key=" /></div>
  </td></tr></table>
<table cellpadding="3" cellspacing="0"><tr valign="top">
  <td><a href="/baochi/cgi-bin/baochi?a=d&amp;d=RbD19360228.2.15.2&amp;srpos=2&amp;e=-----">Page 4 Advertisements Column 2 &#91;ADVERTISEMENT&#93;</a>
  <div>Sài Gòn 28 Tháng Hai 1936</div>
  </td></tr></table>
<script>initialiseCollapsibleTableEntry('facet-de', 'expanded');</script>
  <a href="?x">1920-1929</a> (7) <a href="?x">1930-1939</a> (42) <a href="?x">1970-1979</a> (19)
<script>initialiseCollapsibleTableEntry('facet-wo', 'expanded');</script>
  <a href="?x">51 - 1000</a> (60)
`;

test('parseNlvRows reads oid, headline, document type, publication and crop', () => {
  const rows = parseNlvRows(NLV_HTML);
  expect(rows).toHaveLength(2);
  expect(rows[0]).toEqual({
    oid: 'RbD19230501.2.9.1',
    title: 'Chợ Khánh Hội',
    docType: 'Bài báo',
    publication: 'Sài Gòn',
    dateId: '19230501',
    crop: '209,3322,621,81',
  });
  // The printed date is stripped off the publication, and a result with no
  // snippet image still parses — it just has no crop.
  expect(rows[1].publication).toBe('Sài Gòn');
  expect(rows[1].crop).toBeNull();
});

test('parseNlvTotal and parseNlvCurve read the stated total and the decade facet', () => {
  expect(parseNlvTotal(NLV_HTML)).toBe(88);
  expect(parseNlvTotal('<p>no results here</p>')).toBeNull();
  // Only the publication-decade facet, never the word-count facet after it.
  expect(parseNlvCurve(NLV_HTML)).toEqual({
    total: 68,
    decades: { 1920: 7, 1930: 42, 1970: 19 },
  });
  expect(parseNlvCurve('<p>nothing</p>')).toEqual({ total: 0, decades: {} });
});

test('oidDate pulls the packed date out of the archive key', () => {
  expect(oidDate('HtCq19320421.1.31')).toBe('19320421');
  expect(oidDate('nonsense')).toBe('');
});

test('the nlv year window keeps 1923 and drops 1936 at ±10 around 1923', () => {
  const rows = parseNlvRows(NLV_HTML);
  expect(filterNlvByYear(rows, 1923, 10).map((r) => r.dateId)).toEqual(['19230501']);
  // Widen the window and the 1936 issue comes back.
  expect(filterNlvByYear(rows, 1923, 15).map((r) => r.dateId)).toEqual(['19230501', '19360228']);
  // A missing or junk date is dropped, never treated as year zero.
  expect(filterNlvByYear([{ dateId: undefined }, { dateId: 'RbD' }], 1923, 10)).toEqual([]);
});

test('nearestNlvRows answers a window the archive cannot reach', () => {
  // The Vietnamese press begins around 1900, so a window over the 1870s holds
  // none of it however much the archive has on the place. The curve still says
  // 88, so an empty list reads as a bug — these are what gets shown instead.
  const rows = parseNlvRows(NLV_HTML);
  expect(filterNlvByYear(rows, 1878, 20)).toEqual([]);
  expect(nearestNlvRows(rows, 1878, 2).map((r) => r.dateId)).toEqual(['19230501', '19360228']);
  // Nearest means nearest in either direction, not simply the earliest.
  expect(nearestNlvRows(rows, 1990, 1).map((r) => r.dateId)).toEqual(['19360228']);
  // An undated row can have no distance, so it is dropped rather than sorted first.
  expect(nearestNlvRows([{ dateId: undefined }], 1878, 2)).toEqual([]);
});

test('nlvDate unpacks the packed date, degrading on zeroed parts', () => {
  expect(nlvDate('19360228')).toBe('1936-02-28');
  expect(nlvDate('19360200')).toBe('1936-02');
  expect(nlvDate('19360000')).toBe('1936');
  expect(nlvDate('')).toBe('');
});

test('nlvItem maps a parsed row to the response shape', () => {
  const [withCrop, without] = parseNlvRows(NLV_HTML);
  // The thumbnail is the archive's snippet box rather than the whole newspaper
  // page: ~120 kB rather than ~1.4 MB. It goes through the https proxy because
  // the archive itself is http only and a browser blocks a mixed-content image.
  expect(nlvItem(withCrop)).toEqual({
    source: 'nlv',
    title: 'Sài Gòn — Chợ Khánh Hội',
    date: '1923-05-01',
    snippet: '',
    url: 'http://baochi.nlv.gov.vn/baochi/cgi-bin/baochi?a=d&d=RbD19230501.2.9.1',
    thumb:
      'https://baochi-tvqg.vercel.app/api/image?oid=RbD19230501.2.9.1&area=1' +
      '&crop=209,3322,621,81&w=621&color=all&ext=jpg',
  });
  // No crop stated: fall back to the whole page at a small width.
  expect(nlvItem(without).thumb).toContain('&w=480&');
});

test('nlvSearchUrl quotes the label, because txq ANDs unquoted words', () => {
  const url = new URL(nlvSearchUrl('Khánh Hội', 50));
  expect(url.origin + url.pathname).toBe('http://baochi.nlv.gov.vn/baochi/cgi-bin/baochi');
  // Unquoted, this is "Khánh anywhere and Hội anywhere" — a different question,
  // and on this archive an enormously noisier one.
  expect(url.searchParams.get('txq')).toBe('"Khánh Hội"');
  expect(url.searchParams.get('txf')).toBe('txIN');
  expect(url.searchParams.get('o')).toBe('50');
  // A quote in the label cannot end the phrase early.
  expect(new URL(nlvSearchUrl('Khanh" Hoi', 50)).searchParams.get('txq')).toBe('"Khanh Hoi"');
});

/* --------------------------------------------------------------------- merge */

test('mergeByDate interleaves providers chronologically, undated last', () => {
  const merged = mergeByDate(
    [
      [
        { source: 'gallica', title: 'g1', date: '1930', snippet: '', url: 'a', thumb: '' },
        { source: 'gallica', title: 'g2', date: '', snippet: '', url: 'b', thumb: '' },
      ],
      [{ source: 'nlv', title: 'n1', date: '1923-05-01', snippet: '', url: 'c', thumb: '' }],
    ],
    10
  );
  expect(merged.map((i) => i.title)).toEqual(['n1', 'g1', 'g2']);
  expect(mergeByDate([[merged[0]], [merged[1]]], 1)).toHaveLength(1);
});

test('attested spellings from the gazetteer join the guessed ones, cleaned and capped', () => {
  // The gazetteer records how a place was really written; those forms are added
  // after the guesses, not instead of them.
  const withExtra = spellingVariants('Khánh Hội', ['Khanh-Hoi (Q.4)', 'Cầu Ông Lãnh']);
  expect(withExtra[0]).toBe('Khanh Hoi'); // unaccented guess still leads
  expect(withExtra).toContain('Cau Ong Lanh');
  expect(withExtra).toContain('Cầu Ông Lãnh');

  // A quote or bracket in an attested form cannot reach the CQL.
  const cql = buildGallicaQuery('Khánh Hội', 1923, 10, ['bad" or (gallica adj "anything']);
  expect(cql).not.toContain('bad"');
  expect(cql.match(/"/g)!.length % 2).toBe(0);

  // Capped, so a name with a dozen recorded spellings cannot build a query
  // Gallica will choke on.
  const many = spellingVariants(
    'Rue Test',
    Array.from({ length: 20 }, (_, i) => `Form ${i}`)
  );
  expect(many.length).toBeLessThanOrEqual(8);
});
