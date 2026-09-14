/**
 * cells.mjs — how a sheet of paper is named, in one place.
 *
 * These parsers used to live as copies. `load_sheet_sources.mjs` said so in its
 * own header — `cellOf` "lifted verbatim from scout_anu_l7014.mjs", `cellNumber`
 * "lifted verbatim from import_indochine_series_sheets.mjs", `partOf` the "same
 * rule as half() in ingest_indochine_nakala.mjs, widened" — three copy-paste
 * admissions in one file with nothing keeping any of them honest. And the
 * failure mode they warn about is the quiet one: a cell parsed two ways does
 * not error, it just finds nothing and reads as an institution not holding a
 * sheet it holds.
 *
 * They had already drifted. Measured 2026-09-14 over the 304 IGN copy records
 * in `work/tonkin/sources/ign-serie-{243,175}.json`:
 *
 *   - `cellNumber()` and `cellKey()` agreed on all 304. Safe to merge, and
 *     `sheetPart()` below is pinned on that.
 *   - the three part classifiers disagreed on **79 of 304** — every assemblage
 *     record. `ingest_indochine_nakala.mjs`'s `half()` had no assemblage branch
 *     at all and called each one 'whole'.
 *
 * That 79 never reached a database: `nakala.json` is a pre-filtered read and
 * holds 11 demi-format + 21 demi-feuille records and no assemblage. It was a
 * landmine, not a wound — regenerate that file over serie 175, which is all
 * assemblages, and an assemblage of two halves gets minted as one whole-cell
 * sheet, which is the shape of wrong this archive keeps finding: plausible
 * output, silently dropped data.
 *
 * Pinned by `tests/ingest-cells.spec.ts` (trap bytes copied from the real
 * catalogues, runs anywhere) and `scripts/lib/cells.test.mjs` (old vs new over
 * the full catalogue dumps, which are gitignored — run it by hand when they are
 * on disk).
 */

/**
 * CartoMundi's CSV export doubled every quote and then wrapped the field, so a
 * handful of IGN notes arrive as `"""Assemblage … """`. Left alone the leading
 * quotes defeat every anchored match below.
 * @param {unknown} s
 * @returns {string | null}
 */
export function clean(s) {
  const t = String(s ?? '')
    .replace(/"{2,}/g, '"')
    .replace(/^"+|"+$/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return t || null;
}

/**
 * A four-digit year, or nothing. Not every four-digit number on a sheet is one.
 * @param {unknown} v
 * @returns {number | null}
 */
export function yearOf(v) {
  const n = Number(v);
  return Number.isInteger(n) && n > 1800 && n < 2100 ? n : null;
}

// ── Indochine 1:25,000 ──────────────────────────────────────────────────────

/**
 * One spelling for a cell, across both series and both bracket conventions.
 *
 * Cell numbering is not a number: `0 bis`, `5 bis`, `10 bis`, `73 bis` are real
 * cells, and the catalogue spells three of them five ways — `0bis`, `0 bis`,
 * `[0bis]`. Brackets are the catalogue's own typography for a half-sheet that
 * does not print its cell number (`[59]` is cell 59), not a distinct cell.
 * Match on this, never on `parseFloat`.
 *
 * This is `cellKey()` from `plan_indochine_halfsheet_migration.mjs`, which is
 * the more forgiving of the two spellings that existed: it strips brackets
 * anywhere rather than only at the ends, spaces `bis` anywhere rather than only
 * when the whole string is `<digits>bis`, and collapses inner runs of
 * whitespace. On the 304 real records it returns exactly what
 * `cellNumber()` returned; on `0  bis` or `[10 bis]` it is the one that is right.
 * @param {unknown} raw
 * @returns {string}
 */
export function cellNumber(raw) {
  return String(raw ?? '')
    .replace(/[[\]]/g, '')
    .toLowerCase()
    .replace(/(\d)\s*bis/g, '$1 bis')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Sort cells the way a printed sheet index does: numerically, `bis` after the
 * number it qualifies. Anything unparseable sorts last, by its own spelling.
 * @param {string} key a `cellNumber()` output
 * @returns {[number, string]}
 */
export function cellOrder(key) {
  const m = /^(\d+)(\s*bis)?$/.exec(key);
  if (!m) return [Number.POSITIVE_INFINITY, key];
  return [Number(m[1]) + (m[2] ? 0.5 : 0), key];
}

/**
 * Which part of the cell one IGN record is, off its `f101Note`.
 *
 * Returns the catalogue's own vocabulary and lets each caller map it, because
 * the three callers need three different spellings of the same four facts:
 *
 *   'demi-format'  a half-format sheet carrying the WHOLE cell — not a half
 *   'assemblage'   IGN's own join of the two halves
 *   'W' | 'E'      one half-sheet
 *   null           the note says none of the above
 *
 * Order matters and is fixed here rather than per caller: `demi-format` is a
 * statement about the paper and wins over `assemblage`, which is a statement
 * about what was joined. On the 304 real records no note contains both words,
 * so the order is unobservable today and pinned so it stays decided.
 *
 * The demi-feuille test is anchored at `^` because several notes go on to
 * discuss the OTHER half — 73 bis 1927 reads "Demi-feuille Est. La partie …
 * demi-feuille Ouest" — and an unanchored search calls the east half west.
 * @param {unknown} note
 * @returns {'demi-format' | 'assemblage' | 'W' | 'E' | null}
 */
export function sheetPart(note) {
  const n = clean(note) ?? '';
  if (/demi-format/i.test(n)) return 'demi-format';
  if (/^assemblage/i.test(n)) return 'assemblage';
  const m = /^demi-feuille\s+(ouest|est)\b/i.exec(n);
  if (m) return /ouest/i.test(m[1]) ? 'W' : 'E';
  return null;
}

/**
 * The same fact read off the title's brackets, which mark the half of the title
 * this sheet does NOT print: `[Quang] -Yên` is the east half, `Quang [-Yên]` the
 * west. An independent check on the note, and the notes are not all right — so
 * a disagreement is something to report, never to resolve here.
 * @param {unknown} title
 * @returns {'W' | 'E' | null}
 */
export function partFromTitle(title) {
  const t = String(title ?? '');
  const i = t.indexOf('[');
  if (i < 0) return null;
  return t.slice(0, i).replace(/[\s-]/g, '') ? 'W' : 'E';
}

// ── AMS Series L7014 ────────────────────────────────────────────────────────

const ROMAN = { I: 1, II: 2, III: 3, IV: 4 };

/**
 * The cell an ANU title names, as this archive spells it: `6531-2`.
 *
 * Two traps, both live. ANU spells the Roman numeral with a lowercase L on
 * 20 of its 160 titles — "Sheet 6738 lll", "6631 lV", "6539 Il" — which is a
 * typist reaching for the nearest key, not a different numbering; fold `l` to
 * `I` before reading it or an eighth of the collection reads as not held. And
 * the numeral is the QUADRANT of the 1:100,000 sheet, not an edition: at least
 * one secondary source reads it as an edition and produces a plausible, wrong
 * answer.
 *
 * The collection's index sheet ("Vietnam INDEX, 1:50 000, Series: L7014") names
 * no cell and correctly returns null.
 * @param {unknown} title
 * @returns {string | null}
 */
export function cellOf(title) {
  const m = /Sheet\s+(\d{4})\s*([IVl]{1,3})(?=[,\s]|$)/i.exec(String(title ?? ''));
  if (!m) return null;
  const q = ROMAN[/** @type {keyof typeof ROMAN} */ (m[2].replace(/l/g, 'I').toUpperCase())];
  return q ? `${m[1]}-${q}` : null;
}

/**
 * The year a TTU collar says the sheet was PRINTED, or nothing.
 *
 * Only two phrases on these collars mean it: `in lần thứ nhất 1980` (first
 * printing) and `vẽ và in lại 1978` (redrawn and reprinted). Everything else
 * four-digit on the paper is a datum or a currency-of-information date —
 * "Indian Datum 1960", "renseignements cartographiques 1960", "information as
 * of 1965" — and a greedy `\d{4}` files three of the 25 hand-read sheets under
 * a decade they were not printed in, entirely reasonably.
 * @param {unknown} s
 * @returns {number | null}
 */
export function printedYear(s) {
  const t = String(s ?? '');
  const m = /in\s+l[ạa]i\s+(\d{4})/i.exec(t) || /in\s+l[ầa]n\s+th[ứu][^\d]{0,20}(\d{4})/i.exec(t);
  return m ? yearOf(m[1]) : null;
}
