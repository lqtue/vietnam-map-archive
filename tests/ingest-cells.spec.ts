/**
 * How a sheet of paper is named — `scripts/lib/cells.mjs`.
 *
 * These parsers decide which cell of a survey an institution's record belongs
 * to. They used to exist as copies in four ingest scripts, whose headers said
 * "lifted verbatim" and had nothing enforcing it. They had already drifted:
 * measured over the 304 real IGN copy records on 2026-09-14, three part
 * classifiers disagreed on 79 of them — every assemblage — because
 * `ingest_indochine_nakala.mjs` had no assemblage branch and called each one
 * 'whole'. It reached no database only because its input file happens to be
 * pre-filtered.
 *
 * That is the failure this file exists to catch, and it is the archive's
 * recurring shape: a cell parsed two ways does not error and does not look
 * wrong. It finds nothing, and reads as an institution not holding a sheet it
 * holds.
 *
 * Every string below is bytes copied out of the real catalogues, not a case
 * re-derived from the implementation — a checker that shares the parser's blind
 * spot passes while the corpus is wrong. The full-corpus run lives in
 * `scripts/lib/cells.test.mjs`; the dumps it needs are gitignored, so this is
 * the half that rides CI.
 *
 * Browser-less pure checks, riding the Playwright runner like the rest.
 */
import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  cellNumber,
  cellOrder,
  cellOf,
  sheetPart,
  partFromTitle,
  printedYear,
  yearOf,
  clean,
} from '../scripts/lib/cells.mjs';

test.describe('Indochine cell numbers', () => {
  // Three cells, five spellings, all from `f100NumeroOuCode` in serie 243/175.
  test('the catalogue’s typography is not a distinct cell', () => {
    expect(cellNumber('0bis')).toBe('0 bis');
    expect(cellNumber('0 bis')).toBe('0 bis');
    expect(cellNumber('[0bis]')).toBe('0 bis');
    expect(cellNumber('5 bis')).toBe('5 bis');
    expect(cellNumber('[5 bis]')).toBe('5 bis');
    expect(cellNumber('73 bis')).toBe('73 bis');
    expect(cellNumber('[73 bis]')).toBe('73 bis');
    expect(cellNumber('[10 bis]')).toBe('10 bis');
  });

  test('brackets mark a half-sheet that does not print its number', () => {
    expect(cellNumber('[42]')).toBe('42');
    expect(cellNumber('[59]')).toBe('59');
    expect(cellNumber('42')).toBe('42');
  });

  // The spellings the merged parser is strictly better on than the one it
  // replaced in `load_sheet_sources.mjs`, which anchored `bis` to the whole
  // string and stripped brackets only at the ends.
  test('a doubled space or an inner bracket still resolves', () => {
    expect(cellNumber('0  bis')).toBe('0 bis');
    expect(cellNumber(' [ 10 bis ] ')).toBe('10 bis');
  });

  test('nothing is guessed from nothing', () => {
    expect(cellNumber(null)).toBe('');
    expect(cellNumber(undefined)).toBe('');
  });

  test('cells sort the way a printed index does', () => {
    const order = ['73 bis', '5', '0 bis', '10', '0', '5 bis'];
    order.sort((a, b) => {
      const [an, ak] = cellOrder(a);
      const [bn, bk] = cellOrder(b);
      return an - bn || ak.localeCompare(bk);
    });
    expect(order).toEqual(['0', '0 bis', '5', '5 bis', '10', '73 bis']);
  });
});

test.describe('which part of the cell a sheet of paper is', () => {
  // Every note here is verbatim from an IGN `f101Note`.
  test('a demi-format sheet carries the whole cell, not a half', () => {
    expect(
      sheetPart(
        "Feuille de demi-format titrée comme une feuille complète. La zone Ouest n'est pas couverte par la série"
      )
    ).toBe('demi-format');
  });

  test('an assemblage is its own thing — the 79 records that drifted', () => {
    expect(sheetPart('Assemblage de deux demi-feuilles')).toBe('assemblage');
    expect(sheetPart('Assemblage de deux demi-feuilles. Porte aussi le numéro 38/11')).toBe(
      'assemblage'
    );
    // CartoMundi's CSV export doubled the quotes and wrapped the field; left
    // alone the leading quotes defeat the `^` anchor.
    expect(sheetPart('"""Assemblage de deux demi-feuilles """')).toBe('assemblage');
  });

  test('the note names the other half, and must not be read as it', () => {
    // 73 bis 1927. An unanchored search of this string calls the east half west.
    expect(
      sheetPart(
        'Demi-feuille Est. La partie de la mention de date se trouve sur la demi-feuille Ouest'
      )
    ).toBe('E');
    expect(sheetPart('Demi-feuille Ouest')).toBe('W');
    expect(sheetPart('Demi-feuille Est')).toBe('E');
  });

  test('a note that says none of the above says nothing', () => {
    expect(sheetPart('Porte aussi le numéro 38/11')).toBeNull();
    expect(sheetPart(null)).toBeNull();
    expect(sheetPart('')).toBeNull();
  });

  test('the title’s brackets are the independent read', () => {
    // Brackets mark the half of the title this sheet does NOT print.
    expect(partFromTitle('[Quang] -Yên')).toBe('E');
    expect(partFromTitle('Quang [-Yên]')).toBe('W');
    expect(partFromTitle('[Cua-] Day')).toBe('E');
    expect(partFromTitle('Nhan-Ly')).toBeNull();
  });
});

test.describe('the AMS L7014 cell an ANU title names', () => {
  test('a lowercase L is a typist reaching for the nearest key', () => {
    // 20 of ANU's 160 titles. Unfolded, an eighth of the collection reads as
    // not held.
    expect(cellOf('Vietnam, Gia Vuc, Series: L7014, Sheet  6738 lll, 1967, 1:50 000')).toBe(
      '6738-3'
    );
    expect(cellOf('Vietnam , Ap Gai-Bac, Series: L7014, Sheet  6631 lV, 1967, 1:50 000')).toBe(
      '6631-4'
    );
    expect(cellOf('Vietnam, G. Rieng, Series: L7014, Sheet  6539 Il, 1966, 1:50 000')).toBe(
      '6539-2'
    );
    expect(cellOf('Vietnam , Phu Thien, Series: L7014, Sheet  6636 ll, 1969, 1:50 000')).toBe(
      '6636-2'
    );
  });

  test('a correctly typed numeral reads the same', () => {
    expect(cellOf('Vietnam, Gia Rai, Series: L7014, Sheet  6027 II, 1966, 1:50 000')).toBe(
      '6027-2'
    );
    expect(cellOf('Vietnam, Phu Loc, Series: L7014, Sheet 6541 I, 1968, 1:50 000')).toBe('6541-1');
  });

  test('the printed series index names no cell', () => {
    expect(cellOf('Vietnam INDEX, 1:50 000, Series: L7014, 1965 - 1979')).toBeNull();
    expect(cellOf('')).toBeNull();
    expect(cellOf(null)).toBeNull();
  });

  test('the numeral is a quadrant, so there is no fifth one', () => {
    // Reading it as an edition is the plausible wrong answer; V is not a cell.
    expect(cellOf('Vietnam, Series: L7014, Sheet 6531 V, 1966')).toBeNull();
  });
});

test.describe('the year a TTU collar says it was printed', () => {
  test('the two phrases that do mean printing', () => {
    expect(printedYear('xuất bản lần thứ 4, vẽ và in lại 1978')).toBe(1978);
    expect(printedYear('in lần thứ nhất 1980')).toBe(1980);
    expect(printedYear('in lần thứ nhất 1980 theo bản 1976, chỉnh lý 1979')).toBe(1980);
  });

  test('the three decoys a greedy four-digit match would take', () => {
    // Each would file a sheet under a decade it was not printed in, and the
    // result would look entirely reasonable.
    expect(printedYear('Indian Datum 1960')).toBeNull();
    expect(printedYear('renseignements cartographiques 1960')).toBeNull();
    expect(printedYear('information as of 1965')).toBeNull();
    expect(printedYear('chỉnh lý 1982, 1986, 1987')).toBeNull();
    expect(printedYear('tin tức 1969')).toBeNull();
  });
});

test.describe('the shared scrubbers', () => {
  test('a year is a year, not any four digits', () => {
    expect(yearOf(1911)).toBe(1911);
    expect(yearOf('1927')).toBe(1927);
    expect(yearOf(38)).toBeNull();
    expect(yearOf('')).toBeNull();
    expect(yearOf(null)).toBeNull();
    expect(yearOf('n.d.')).toBeNull();
  });

  test('the CSV export’s doubled quotes come off', () => {
    expect(clean('"""Assemblage de deux demi-feuilles """')).toBe(
      'Assemblage de deux demi-feuilles'
    );
    expect(clean('  two   spaces  ')).toBe('two spaces');
    expect(clean('')).toBeNull();
    expect(clean(null)).toBeNull();
  });
});

test.describe('the tracked Nakala read still parses', () => {
  // `nakala.json` is the only catalogue dump small enough to be in git, and it
  // is the input to `ingest_indochine_nakala.mjs`. If a re-fetch ever puts an
  // assemblage in it, the ingest must see one rather than mint a whole cell.
  const cells: Record<string, { title: string; note: string; year: number }[]> = JSON.parse(
    readFileSync(
      fileURLToPath(new URL('../work/tonkin/sources/nakala.json', import.meta.url)),
      'utf8'
    )
  ).cells;

  test('every cell key is a spelling the index knows', () => {
    for (const key of Object.keys(cells)) expect(cellNumber(key)).toBe(key);
    expect(Object.keys(cells)).toContain('73 bis');
  });

  test('every record classifies, and none is an unhandled assemblage', () => {
    const counts: Record<string, number> = {};
    for (const recs of Object.values(cells))
      for (const r of recs) {
        const p = sheetPart(r.note);
        expect(p, `unclassified note: ${r.note}`).not.toBeNull();
        counts[p as string] = (counts[p as string] ?? 0) + 1;
        // Where the title brackets say a half, the note must agree.
        const t = partFromTitle(r.title);
        if (t && (p === 'W' || p === 'E')) expect(t).toBe(p);
      }
    expect(counts).toEqual({ 'demi-format': 11, W: 10, E: 11 });
  });
});
