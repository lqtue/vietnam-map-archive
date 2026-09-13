/**
 * Period press lookup — the data half of `GET /api/press` (time-machine E3).
 *
 * Two providers, queried in parallel, merged chronologically:
 *  - **gallica** (`./gallica.ts`) — BnF. The French-language colonial press:
 *    *L'Écho annamite*, *Le Courrier saïgonnais*, the *Annuaire général*.
 *  - **nlv** (here) — the National Library of Vietnam's newspaper archive
 *    (`baochi.nlv.gov.vn`): *Sài Gòn*, *Công luận báo*, *Điện tín* and 78 other
 *    titles. The Vietnamese-language press, and the better source for a
 *    Vietnamese place name after 1900. Queried **directly** — see below — which
 *    also returns a decade-by-decade curve for the name at no extra cost.
 *
 * Nothing is stored. One provider failing never fails the response — the caller
 * still answers 200 and names the degradation in `reason`.
 *
 * Runs on Cloudflare Workers: `fetch`, `URLSearchParams`, `AbortController`.
 * No Node builtins, no dependency.
 */

import { fetchGallicaPress } from './gallica';

export type PressSource = 'gallica' | 'nlv';

export type PressItem = {
  source: PressSource;
  title: string;
  /** ISO-ish: `YYYY`, `YYYY-MM-DD`, or whatever the provider gave. */
  date: string;
  snippet: string;
  url: string;
  thumb: string;
};

export type PressResult = {
  items: PressItem[];
  /** The providers asked, in request order. */
  sources: PressSource[];
  /** The Gallica CQL, when Gallica was one of them. Returned to cite/debug. */
  query?: string;
  /** Present only when a provider degraded. */
  reason?: string;
  /**
   * Hits per decade across the whole archive, not just the requested window —
   * "when was this place in the news". Free: it comes off the same NLV response
   * as the items. Gallica has no facet and a curve there would be one request
   * per decade, so only `nlv` is present.
   */
  curve?: { nlv?: PressCurve };
};

/**
 * The National Library's archive runs **Veridian**, whose search is a plain GET
 * and needs no session — so this talks to the library directly rather than to
 * the proxy behind hanoimaps.github.io/news, which was 8-16 s per call, stated
 * no result total, and exposed none of the filters below.
 *
 * `txq` ANDs words unless they are quoted, so the label goes over **quoted**:
 * unquoted, `bản đồ` means "bản anywhere and đồ anywhere" and returns 15,154
 * rows of noise against 838 for the phrase.
 *
 * `o` is the page size (50 max) and `r` the 1-based index of the first result.
 */
const NLV_SEARCH = 'http://baochi.nlv.gov.vn/baochi/cgi-bin/baochi';
const NLV_PAGE = 50;
/**
 * The archive answers on **http only** — no https listener at all. A server-side
 * subrequest is fine with that, but a browser on an https page blocks an http
 * image, so thumbnails cannot come from the library's own image server. They
 * come from the hanoimaps proxy instead, which is https and passes Veridian's
 * `crop` straight through. That crop is the box of the matched phrase on the
 * page, so a thumbnail is now the clipping itself at ~120 kB rather than the
 * whole newspaper page at ~1.4 MB.
 */
const NLV_IMAGE = 'https://baochi-tvqg.vercel.app/api/image';
/** Direct, the search answers in about 1.5 s; this is headroom, not the budget. */
const NLV_DEADLINE_MS = 8_000;

/** One parsed result row. `crop` is `x,y,w,h` on the page scan, when stated. */
export type NlvRow = {
  oid: string;
  title: string;
  docType: string;
  publication: string;
  dateId: string;
  crop: string | null;
};

/** Hits per decade, keyed by the decade's first year. */
export type PressCurve = { total: number; decades: Record<number, number> };

/** Strip tags and decode the few entities Veridian emits. Pure. */
function plain(html: string): string {
  return html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(Number(d)))
    .replace(/&amp;/g, '&')
    .replace(/&nbsp;/g, ' ')
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, ' ')
    .trim();
}

/** `"HtCq19320421.1.31"` → the packed date `"19320421"`. Pure. */
export function oidDate(oid: string): string {
  return /^[A-Za-z]+(\d{8})\b/.exec(oid ?? '')?.[1] ?? '';
}

/** `"…trả về 15154 kết quả…"` → 15154. Null when the page states no total. Pure. */
export function parseNlvTotal(html: string): number | null {
  const m = /trả về\s+([\d.,]+)\s+kết quả/.exec(plain(html));
  return m ? Number(m[1].replace(/[.,]/g, '')) : null;
}

/**
 * The results page's decade facet → the whole time curve, from the same
 * response as the results. This is the reason to talk to the archive directly:
 * "when was this place in the news" costs no extra request.
 *
 * Pure.
 */
export function parseNlvCurve(html: string): PressCurve {
  const start = html.indexOf("'facet-de'");
  const end = html.indexOf("'facet-wo'");
  const decades: Record<number, number> = {};
  let total = 0;
  if (start >= 0 && end > start)
    for (const [, d, n] of plain(html.slice(start, end)).matchAll(/(\d{4})-\d{4}\D{0,120}?\((\d+)\)/g)) {
      decades[Number(d)] = Number(n);
      total += Number(n);
    }
  return { total, decades };
}

/**
 * One results page → its rows. Each result is a `<table cellpadding="3">`: the
 * title anchor carries the oid, the `<div>` under it the publication and printed
 * date, and the snippet `<img>` the crop box.
 *
 * ponytail: regexes, not a parser — Workers have no DOMParser and this is flat
 * machine-generated markup from one publisher. The ceiling is a Veridian
 * template change, which shows up as zero rows against a non-zero total; the
 * caller reports that as a degradation rather than as an empty archive.
 *
 * Pure.
 */
export function parseNlvRows(html: string): NlvRow[] {
  const rows: NlvRow[] = [];
  for (const block of html.split(/<table cellpadding="3"/).slice(1)) {
    const a = /<a href="[^"]*a=d&amp;d=([^&"]+)&amp;srpos=\d+[^"]*"\s*>([^<]*)<\/a>/.exec(block);
    if (!a) continue;
    const line = /<\/a>\s*<div>([^<]*)<\/div>/.exec(block);
    const crop = /crop=(\d+,\d+,\d+,\d+)/.exec(block);
    const title = plain(a[2]);
    // Veridian appends the document type in brackets: "Bản đồ Công-gô [Bài báo]".
    const typed = /^(.*?)\s*\[([^\]]+)\]\s*$/.exec(title);
    rows.push({
      oid: a[1],
      title: typed ? typed[1] : title,
      docType: typed ? typed[2] : '',
      publication: line ? plain(line[1]).replace(/\s*\d{1,2} Tháng .*$/, '').trim() : '',
      dateId: oidDate(a[1]),
      crop: crop ? crop[1] : null,
    });
  }
  return rows;
}

/** `"19360228"` → 1936. Null when the id is not a plausible packed date. */
export function nlvYear(dateId: string | undefined): number | null {
  const y = Number((dateId ?? '').slice(0, 4));
  return Number.isInteger(y) && y > 1400 && y < 2200 ? y : null;
}

/** `"19360228"` → `"1936-02-28"`; a zeroed month/day degrades to `"1936"`. */
export function nlvDate(dateId: string | undefined): string {
  const y = nlvYear(dateId);
  if (!y) return '';
  const mm = (dateId ?? '').slice(4, 6);
  const dd = (dateId ?? '').slice(6, 8);
  if (!/^\d\d$/.test(mm) || mm === '00') return String(y);
  if (!/^\d\d$/.test(dd) || dd === '00') return `${y}-${mm}`;
  return `${y}-${mm}-${dd}`;
}

/** Pure: keep only rows whose year is inside `year ± windowYears`. */
export function filterNlvByYear<T extends { dateId?: string }>(
  results: T[],
  year: number,
  windowYears: number
): T[] {
  const lo = Math.trunc(year) - Math.trunc(windowYears);
  const hi = Math.trunc(year) + Math.trunc(windowYears);
  return results.filter((r) => {
    const y = nlvYear(r.dateId);
    return y !== null && y >= lo && y <= hi;
  });
}

/** Pure: one parsed row → the response item shape. */
export function nlvItem(r: NlvRow): PressItem {
  const headline = r.title.trim();
  return {
    source: 'nlv',
    title: [r.publication, headline].filter(Boolean).join(' — ') || '(untitled)',
    date: nlvDate(r.dateId),
    // ponytail: the archive returns no matched text, only the page image. The
    // crop below *is* the evidence; a snippet would need the upstream OCR.
    snippet: '',
    url: `${NLV_SEARCH}?a=d&d=${r.oid}`,
    thumb: r.crop
      ? `${NLV_IMAGE}?oid=${r.oid}&area=1&crop=${r.crop}&w=${r.crop.split(',')[2]}&color=all&ext=jpg`
      : `${NLV_IMAGE}?oid=${r.oid}&area=1&w=480&color=all&ext=jpg`,
  };
}

/**
 * The search URL. `limit` is capped at Veridian's own page size — one page is
 * one request, and the year window is applied to the rows we get back.
 */
export function nlvSearchUrl(q: string, limit: number): string {
  const p = new URLSearchParams({
    a: 'q',
    r: '1',
    results: '1',
    // Quoted: unquoted, `txq` ANDs the words rather than matching the phrase.
    txq: `"${q.replace(/"/g, '')}"`,
    txf: 'txIN',
    ssnip: 'img',
    o: String(Math.min(NLV_PAGE, Math.max(1, limit))),
    e: '-------vi-20--1--img-txIN------',
  });
  return `${NLV_SEARCH}?${p}`;
}

async function fetchNlvPress(opts: {
  q: string;
  year: number;
  windowYears: number;
  limit: number;
}): Promise<{ items: PressItem[]; curve: PressCurve }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), NLV_DEADLINE_MS);
  try {
    // One request. The window is applied here rather than through the archive's
    // own `dafyq`/`datyq`, because the decade facet on this page is the whole
    // curve and asking for a window would narrow that to the window too.
    const res = await fetch(nlvSearchUrl(opts.q, NLV_PAGE), { signal: controller.signal });
    if (!res.ok) throw new Error(`nlv http ${res.status}`);
    const html = await res.text();
    const rows = parseNlvRows(html);
    if (!rows.length && (parseNlvTotal(html) ?? 0) > 0)
      throw new Error('nlv parse failed: results stated, none parsed');
    return {
      items: filterNlvByYear(rows, opts.year, opts.windowYears).slice(0, opts.limit).map(nlvItem),
      curve: parseNlvCurve(html),
    };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Pure: merge provider lists into one chronological run. Undated items sink to
 * the end rather than sorting as year zero.
 */
export function mergeByDate(lists: PressItem[][], limit: number): PressItem[] {
  return lists
    .flat()
    .sort((a, b) => (a.date || '9999').localeCompare(b.date || '9999'))
    .slice(0, limit);
}

/**
 * Query the requested providers for press mentioning `q` within
 * `year ± windowYears`. Degrades, never throws.
 */
export async function fetchPress(opts: {
  q: string;
  /**
   * Attested spellings from the gazetteer (`place_names.variants[]`), if the
   * caller has them. Only Gallica uses them: its full text is OCR'd and its
   * house style hyphenates, so more real forms means more hits. The NLV proxy
   * takes a single query string, so it still gets the label as typed.
   */
  extra?: string[];
  year: number;
  windowYears: number;
  limit: number;
  sources: PressSource[];
}): Promise<PressResult> {
  const { sources } = opts;
  const settled = await Promise.allSettled([
    sources.includes('gallica') ? fetchGallicaPress(opts) : null,
    sources.includes('nlv') ? fetchNlvPress(opts) : null,
  ]);

  const reasons: string[] = [];
  const lists: PressItem[][] = [];
  let query: string | undefined;

  const [gallica, nlv] = settled;
  if (gallica.status === 'fulfilled' && gallica.value) {
    query = gallica.value.query;
    if (gallica.value.reason) reasons.push(gallica.value.reason);
    lists.push(gallica.value.items);
  } else if (gallica.status === 'rejected') {
    // fetchGallicaPress swallows its own failures; this is belt-and-braces.
    console.error('[press] gallica rejected:', gallica.reason);
    reasons.push('gallica unavailable');
  }
  let curve: { nlv?: PressCurve } | undefined;
  if (nlv.status === 'fulfilled' && nlv.value) {
    lists.push(nlv.value.items);
    if (nlv.value.curve.total) curve = { nlv: nlv.value.curve };
  } else if (nlv.status === 'rejected') {
    console.error('[press] nlv rejected:', nlv.reason);
    reasons.push(
      nlv.reason instanceof Error && nlv.reason.name === 'AbortError'
        ? 'nlv timeout'
        : 'nlv unavailable'
    );
  }

  return {
    items: mergeByDate(lists, opts.limit),
    sources,
    query,
    reason: reasons.length ? reasons.join('; ') : undefined,
    curve,
  };
}
