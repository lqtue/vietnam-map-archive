# Legend points in the fabric proto — 2026-10-06

What `work/proto/fabric/` now shows and what it found: the printed-legend entries (`ocr_labels`,
`category = legend_entry`) of the six District 4 sheets, placed on the same independent per-sheet
affines as the OCR labels, and linked across sheets by name. This records one build run against the
live Supabase project (read-only). The links are hypotheses from a name match inside a radius, not
facts, exactly as the Doling citations in the same viewer are tentative. Rebuild with
`work/ocr/.venv/bin/python work/proto/fabric/build.py`; `layers.json` is gitignored.

## What was built

`build.py` gains a legend pass. It reads each sheet's entries (`coalesce(category_corrected,
category) = legend_entry`, not `rejected`, paged), parses `notes` (a port of `legendEntry.ts`:
`px`, `more`, legacy `point`, `vn`, `n`), warps pixel points through the sheet's own affine, and keys
each entry by `placeCoreKey` (name, and `vn` when present). Links go into the existing union-find,
so a chain can mix legend points and body labels. `layers.json` gains `legend[]` and
`legend_links[]`; the existing `layers` and `links` are byte-identical to the previous build apart
from the opaque chain ids `c` (checked against a build of the committed `build.py`).

- Legend <-> legend: each point links to its closest key match on the nearest later sheet that has
  one, within `--legend-link-max-m` (300 m). This differs from the body rule, which links adjacent
  sheets only, because the sheets that carry placed legends are not neighbours (1923, 1959).
- Legend <-> body: each point links to the closest body label with the same key on every other
  sheet, same radius.
- `labels.name_key` was checked and is not equivalent to `placeCoreKey` (different prefix list, one
  prefix, no four-character floor), so `placeCoreKey` is ported; only `labels.fold` is reused.
- Entries with no `px`/`more`/`point` take a body numeral (`legend_ref`/`other`, digits 1..max n,
  outside the legend box) only when exactly one candidate exists; those points carry `src: numeral`.

## Entries and placed points per sheet

| Sheet | Entries | Staff-placed points (`px`) | Numeral-placed | Notes |
| --- | ---: | ---: | ---: | --- |
| 1882 `0e02b9d9` | 0 | 0 | 0 | no legend rows |
| 1895 `f08aa539` | 0 | 0 | 0 | in `maps.txt`, not in `build.py` |
| 1898 `20ec4f9a` | 0 | 0 | 0 | the sheet `build.py` actually renders |
| 1923 `1bce28f0` | 182 | 182 | 0 | validated |
| 1942 `eca788e5` | 235 | 0 | 62 | pending, no `px` |
| 1959 `34d4edb2` | 156 | 156 | 0 | validated |
| 1968 `3a446d85` | 244 | 0 | 45 | pending, no `px`; all carry `vn` |

Only two sheets hold staff-placed points. The 1942 and 1968 legends are read but unplaced in the
database at this time. Every `px` lay inside its image; no note was unparseable; no `more=` or
`point=` rows exist; no row was rejected or reclassified.

## Chains

34 chains contain a legend point: 12 with at least one legend-legend link (11 pairs, 1 triple) and
22 that are one legend point tied to body labels only. Counting every sheet in the chain, legend
or body:

| Sheets spanned | 2 | 3 | 4 | 5 |
| --- | ---: | ---: | ---: | ---: |
| Chains | 19 | 13 | 1 | 1 |

13 legend-legend links and 45 legend-body links were drawn (1923 -> 1898: 20, 1923 -> 1882: 12;
the body links lie at 11-280 m, median about 39 m). No legend point merged two previously separate
body chains: the body chain count is unchanged at 206.

Longest chains, legend names per year (body sheets listed where the chain reaches them):

1. 1882, 1898, 1923, 1942, 1959: 1923 #105 Marché de Cầu Ông Lãnh; 1942 #105 Marché de
   Cầu-Ông-Lãnh (numeral); 1959 #38 Chợ Cầu Ông Lãnh. Body labels carry it to 1882 and 1898.
2. 1923, 1942, 1959, 1968: 1959 #43 Chợ Phú Lâm, tied to body labels on the other three sheets.
3. 1882, 1898, 1923 (ten chains, eight more also reach only 1898 and 1923): 1923 Cathédrale, Trésor (#44 and #45), Gendarmerie, Justice de
   Paix, Couvent des Carmélites, Hôtel du Général, Collège Chasseloup Laubat, Sainte Enfance.
   Their 1882 and 1898 ends are body labels, 11-120 m away.

The remaining legend-legend chains are pairs: 1923-1942 (Inscription maritime, Commandant de la
Marine, Immigration, Service du Pilotage, Eglise de Chợ Đủi), 1923-1959 (Marché de Bình Đông, Marché
de Tân Định) and 1959-1968 (Chợ Cầu Kho, Chợ Chí Hòa, Ngân-Hàng Trung Quốc, Trường đua Phú Thọ).

## Name drift

- French to Vietnamese, 1923 to 1959: `Marché de X` becomes `Chợ X` (Tân Định, Bình Đông, Cầu Ông
  Lãnh, Bình Tây). `placeCoreKey` strips both generics, so the cores agree.
- Vietnamese to English with `vn`, 1959 to 1968: `Chợ Cầu Kho` is `Cầu-Kho Market / Chợ Cầu Kho`;
  `Trường đua Phú Thọ` is `Phú-Thọ Hippodrome`; `Ngân-Hàng Trung Quốc` is `Bank of China`. Matches
  here exist only because `vn` repeats the 1959 wording; the English names alone would never match.
- Spelling only: `Chợ Đủi` / `Chợ-Đũi`, `Cầu Ông Lãnh` / `Cầu-Ông-Lãnh` (hyphens and tone marks).
- Numbers never carry over: #105 / #105 / #38, #181 / #34, #36 / #184, #39 / #187, #148 / #164,
  #77 / #212. The one equal pair (#105) is a coincidence. Each legend is numbered afresh.
- 1942 to 1959 yields one pair only (the Cầu Ông Lãnh market).

## Single-sheet entries

Of 445 placed entries, 48 sit in any chain and 397 (89 %) are on one sheet only: 1923 154 of 182,
1942 55 of 62, 1959 147 of 156, 1968 41 of 45. Most of this is the key, not the city. A lookup of
every same-key pair regardless of distance finds only 33 across the four sheets, so almost no other
entry shares a core key with another sheet. `Hôpital`, `Eglise`, `Ecole`, `Temple` and the
Vietnamese `Bệnh viện`, `Nhà thờ`, `Trường` are not in `GENERIC_WORDS`, and a French legend never
meets an English one without `vn`.

## Legend and body links

45 links tie a legend point to a body label on another sheet. 1923 legend entries reach 1898 (20)
and 1882 (12): for example Cathédrale 15 m, Palais de Justice 20 m, Trésor 25 m, Marché de Cầu Ông
Lãnh 26 m (1898) and 33 m (1882). These are the strongest results of the run, because both ends are
independent readings. Weakest: Marché de Bình Tây 1923 -> 1959 body label at 125 m, five
1959 -> body links at 200-280 m, and Cadastre et Topographie 1923 -> 1898 at 223 m.

## Caveats

- Every sheet is placed by its own affine only. The three-point sheets fit exactly, so a small
  residual proves nothing, and paper stretch is not absorbed (see each sheet's `georef`). A
  legend point 300 m from its partner may be the same building or a neighbour; one at 10 m may be
  coincidence of two affine errors.
- A link is "same core key within the radius on a sheet that has one". Near-identical keys at the
  wrong place are not linked, and different words for one thing are never linked.
- Numeral points are unreliable. Of the 14 same-key 1923-1942 pairs, 6 fall within 300 m (those are
  linked), 4 more lie at 340-800 m and 4 lie 1.2-5.9 km apart; of the 13 same-key 1959-1968
  pairs only 4 are within 300 m and the rest are 2.4-9.7 km apart. A bare number such as `8` has
  many candidates, and "unique outside the box" does not mean "the legend marker". The viewer
  therefore draws a numeral point only once a link confirms it.
- Duplicate names inside one legend (1923 has two `Justice de Paix`, two `Trésor`) both compete for
  the same partner; the nearer wins.
- `vn` is an extra key only; an entry with an English name and no `vn` has no way to match.
