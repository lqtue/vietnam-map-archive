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
  'ams-l909-viet-nam-city-maps-1-12-500': {
    summary: [
      'L909 is a city-map series, with city names as sheet identifiers rather than a continuous numbered grid. Catalogue records show scales of 1:12,500, 1:15,000 and 1:10,000; the familiar 1:12,500 label does not describe every sheet.',
      'This partial index combines the L909 cities explicitly listed in the Perry-Castañeda Library Vietnam catalogue with the Sài Gòn L909 scan already served by Vietnam Map Archive. It is an index of known records, not a complete historical inventory of every L909 city or edition.',
    ],
    facts: [
      {
        label: 'Index source',
        value:
          'Perry-Castañeda Library Vietnam Maps catalogue, checked 6 October 2026: https://maps.lib.utexas.edu/maps/vietnam.html',
      },
      {
        label: 'Counting cities',
        value:
          'Nha Trang and Qui Nhon versos are separate source items of their city sheet, not additional city cells.',
      },
      {
        label: 'Saigon distinction',
        value:
          'The two Saigon sheets in the PCL Vietnam catalogue are L9012, not L909. The served Sài Gòn L909 map supplies its own city entry.',
      },
      {
        label: 'Edition evidence',
        value:
          'Catalogue year and edition statements remain source assertions. Existing VMA metadata for Hà Nội and Huế differs from the PCL edition labels; no printing identities are inferred or metadata overwritten.',
      },
      {
        label: 'Geographic extents',
        value:
          'City-cell extents have not been established from a survey index. Scan georeferences are not copied into catalogue cells.',
      },
    ],
  },

  'indochine-1-100-000-1st-edition-sgi-1900-1947': {
    summary: [
      "The first edition of the Service Géographique de l'Indochine's 1:100,000 survey, issued from 1900 to 1947. It is the earlier part of the mapping programme continued by the second edition.",
      'Many numbered cells were printed as separate western and eastern half-sheets. The index groups those halves under one cell and shows which scans the archive holds.',
    ],
    facts: [
      { label: 'Made by', value: "Service Géographique de l'Indochine." },
      { label: 'Dates', value: '1900–1947.' },
      {
        label: 'Sheet numbers',
        value: 'A number identifies a cell; East and West identify its two possible half-sheets.',
      },
      {
        label: 'Scans come from',
        value: 'IGN scans catalogued through CartoMundi and deposited in Nakala.',
      },
    ],
  },

  'indochine-1-100-000-2nd-edition-sgi-1947-1959': {
    summary: [
      "The second edition of the Service Géographique de l'Indochine's 1:100,000 survey, issued from 1947 to 1959 and also catalogued as L 605. It follows the earlier edition with new and revised printings across Indochina.",
      'Some sheets are civil editions; others carry military grid and bilingual overprints. A numbered cell may have western and eastern halves, or several printings. The index brings their scans together without treating each half as a separate place.',
    ],
    facts: [
      { label: 'Made by', value: "Service Géographique de l'Indochine." },
      { label: 'Dates', value: '1947–1959.' },
      {
        label: 'Sheet numbers',
        value: 'A number identifies a cell; East and West identify its two possible half-sheets.',
      },
      {
        label: 'Editions',
        value:
          'Civil sheets and military overprints appear in the same series; some cells have more than one printing.',
      },
      {
        label: 'Scans come from',
        value: 'IGN scans catalogued through CartoMundi and deposited in Nakala.',
      },
      {
        label: 'Sheet list',
        value:
          "CartoMundi's catalogue: 843 records, which group into 220 numbered cells. A cell with no digitised copy is listed as not held. Seventeen cells have only one of their two half-sheets catalogued; the other half is listed as not held, its position inferred from the half that is. Sheet 155 is not in the catalogue at all and is listed as not held, placed in the one cell-sized space between 154 and 156. CartoMundi's own extents for 154 and for the east half of 157 repeat those of 153 and 156, and are moved one cell east. A number the catalogue never lists and that leaves no gap is not counted, so the list is the catalogue's census and not necessarily the survey's.",
      },
    ],
  },

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
