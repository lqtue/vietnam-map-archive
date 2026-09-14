/**
 * What each survey is, in prose — the half a database cannot hold.
 *
 * `map_series` and `series_sheets` answer how many sheets a survey contains and
 * which of them the archive holds. Neither can say who made it, why its sheets
 * are numbered the way they are, or which of the things a reader will find
 * written about it elsewhere are wrong. That is research, it changes rarely,
 * and it belongs beside the page that shows it — the same reasoning as
 * `changelog/releases.ts` and `blog/posts.ts`.
 *
 * Keyed by `series_key` (migration 082). A survey with no entry renders no
 * panel at all, so adding one here is the only step.
 *
 * Every `fact` below is checked against something: the sheets' own collars, the
 * embedded metadata the mosaic was built from, or a named institution's
 * catalogue. Do not add one that is only remembered.
 */

export interface SeriesNote {
  /** What the survey is. Two short paragraphs is the useful length. */
  summary: string[];
  /** The things a catalogue record leaves out. Four to six. */
  facts: { label: string; value: string }[];
  /**
   * A claim about this survey that is commonly made and untrue. Rendered as a
   * correction because the archive is where someone checks.
   */
  correction?: { claim: string; actually: string };
}

export const SERIES_NOTES: Record<string, SeriesNote> = {
  'series-l7014-vietnam-1-50-000': {
    summary: [
      'The standard tactical sheet of the Vietnam War: U.S. Army Map Service 1:50,000 topographic coverage, printed in English and Vietnamese, with relief by contour and spot height in metres and hydrography by contour and sounding.',
      'The survey did not end with the war. Sheets were recompiled by the Defense Mapping Agency into the 1980s and redrawn after 1975 by Vietnamese state cartographic bodies, so a single cell can exist as an AMS sheet of 1966 and a Hanoi reprint of 1978 — the same ground, resurveyed, with roads, hamlets and spellings that moved between them.',
    ],
    facts: [
      {
        label: 'Compiled by',
        value:
          'Army Map Service; the 29th and 652d Engineer Battalions (Topographic); U.S. Army Topographic Command — the TPC in edition strings like 3-TPC (29 ETB); and the Defense Mapping Agency Topographic Center.',
      },
      {
        label: 'Printed by',
        value:
          'Frequently the National Geographic Service of Vietnam, and for the Australian holdings the Royal Australian Survey Corps.',
      },
      {
        label: 'Dates',
        value:
          'Usually catalogued as 1965–1971. The sheets held here carry printing dates from 1963 to 1989, the later ones being DMA recompilations and post-1975 Vietnamese redraws.',
      },
      {
        label: 'Sheet numbers',
        value:
          'Four digits name the 1:100,000 sheet, the suffix its quadrant — 6330-4 is the fourth quadrant of sheet 6330.',
      },
      {
        label: 'Editions',
        value:
          'Numbered from the first printing, with a suffix naming the issuing office: 001, 2-AMS, 3-TPC, 4-DMA. The suffix is the half that says which body issued it, so editions are never comparable as numbers alone.',
      },
      {
        label: 'Scans come from',
        value:
          'The Perry-Castañeda collection at UT Austin, which publishes most sheets as GeoPDFs carrying their own control points; the Vietnam Archive at Texas Tech, which holds different printings of the same cells; and the ANU Open Research Repository, which is the only one of the three to state a rights position — copyright expired, open access.',
      },
    ],
    correction: {
      claim: 'that the Roman numeral in a sheet designation such as 6738 III marks an edition',
      actually:
        'it is the quadrant, the same thing as the -3 in 6738-3. Reading it as an edition turns one cell into four, and four printings of one cell into one.',
    },
  },

  'indochine-1-25-000-tonkin-thanh-hoa': {
    summary: [
      "The French colonial 1:25,000 survey of Tonkin and Thanh Hóa, made by the Service Géographique de l'Indochine between 1903 and 1927 — the earliest systematic large-scale mapping of the northern delta, and the base layer beneath everything surveyed there since.",
      'Most cells were issued as two half-sheets, a western and an eastern, each with its own frame and its own printed corner figures. A dozen were issued instead as a single half-format sheet covering the whole cell. Both arrangements count as one cell of the survey, which is why the sheet count and the number of scans do not match.',
    ],
    facts: [
      {
        label: 'Compiled by',
        value: "Service Géographique de l'Indochine.",
      },
      {
        label: 'Dates',
        value: 'Sheets carry dates from 1903 to 1927.',
      },
      {
        label: 'Sheet numbers',
        value:
          'A single number per cell, with the west and east halves sharing it. The bracketed half of a printed title marks the part that sheet does not cover — [Cua-] Day is the eastern half.',
      },
      {
        label: 'Scans come from',
        value:
          "IGN's own scans, catalogued through CartoMundi and served over Nakala under CC BY 4.0, mirrored here so the whole survey reads through one pipeline.",
      },
    ],
  },
};
