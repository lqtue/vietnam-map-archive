# Paper figures — every number the paper quotes, with where it came from

**Frozen 2026-09-19.** One file, so a draft cites this and not fifteen scattered originals.
Convention inherited from `docs/image-processing-record.md`: *where this file and a source file
disagree, the source file wins* — and then this file is corrected, not the other way round.

Three kinds of row:
- **live** — pulled from production on the date given, command recorded.
- **measured** — a run someone made, with the file that recorded it.
- **cited** — from a published paper, verified through scite on the date given.

Anything not in this file does not go in the paper.

---

## 0. The corpus, live

Pulled 2026-09-19 with `node --env-file=.env scripts/catalog_audit.mjs --quiet`,
`scripts/check_series_index.mjs`, and a paged PostgREST count (paged deliberately — the
un-paged version caps at 1,000 rows and reports the truncation as nothing, which is the bug
`260919-seg-audit.md` W3 found in `supabase_client.fetch_ocr_extractions`).

| | **2026-09-19 (live)** | 2026-09-04, as the dataset card still says | note |
|---|---|---|---|
| `maps` rows | **274** | 101 | 2.7× |
| published (`public` + `featured`) | **252** | 38 | |
| `georef_done` | **253** | 39 | the Tonkin ingest |
| carrying `annotation_url` | **253** | 38 | |
| carrying a ground `bbox` | **274 of 274** | 40 of 101 | |
| `ocr_extractions` | **13,525** | 1,544 | |
| …across | **22 sheets**, 42 runs | 6 of 39 | |
| `status = validated` (the human gate) | **96** | 43 | |
| `place_names` (gazetteer view) | **4,524** | 394 | |
| `footprint_submissions` | **1,519** | 46 | see §0.2 |
| `map_iiif_sources` | **174** | — | |
| `series_sheets` (cells) | **706** | — | 0 adrift / 0 dangling / 0 unindexed |
| `sheet_sources` (printings) | **1,131** | 1,023 (2026-09-14) | |

**Series coverage**, `check_series_index.mjs`, 2026-09-19:

```
series-l7014-vietnam-1-50-000:        461 held / 627
indochine-1-25-000-tonkin-thanh-hoa:   75 held /  79
0 adrift, 0 dangling, 0 unindexed, over 706 sheets.
```

### 0.1 Concentration — the card's warning is now much weaker, and say so

The dataset card says to publish the concentration, because *"a reader who sees '1,544 labels
across 39 maps' and discovers two sheets carry 95% of them will not trust the rest."* That is
still the right instinct and the number has changed: **the top two sheets are 44.0% of all
extractions, not 95%.**

| rows | share | sheet |
|---:|---:|---|
| 4,287 | 31.7% | 1942 Plan de Saigon – Cho Lon |
| 1,663 | 12.3% | 1959 Đô thành Sài Gòn |
| 1,420 | 10.5% | 1922 Carte routière des environs de Saïgon |
| 1,029 | 7.6% | 1923 Saigon – Cholon |
| 946 | 7.0% | 1912 Saigon – Cholon et Environs |
| 630 | 4.7% | 1878 Plan de la Ville de Saigon |
| 548 | 4.1% | 1888 Cochinchine Française |
| 499 | 3.7% | **1882 Plan Cadastral** — the gate sheet |
| 472 | 3.5% | 1898 Saigon Plan |
| 392 | 2.9% | 1968 Sài Gòn – Việt Nam City Maps 1:12,500 |

Twelve more sheets carry the remaining ~12%. **The 1942 sheet at 4,287 rows is the one whose
77% was invisible** to every caller until W3 paged the client (`260919-seg-audit.md`).

### 0.2 Footprints — read this before quoting 1,519

```
 888  import / land_plot / needs_review
 555  import / building / needs_review
  24  volunteer / land_plot / approved
  17  volunteer / building / approved
  16  volunteer / road      / submitted
  11  volunteer / water_body/ submitted
   3  volunteer / building  / submitted
   3  volunteer / road      / approved
   2  volunteer / waterway  / approved
```

Three things follow, and all three matter to any claim made off this table:

1. **1,443 of the 1,519 are machine output** — 888 + 555, which is exactly the W6 within-parcel-split
   run (`260919-seg-audit.md`), imported into the review queue as `import`.
2. **The scored ground truth is still 46**: 24 land_plot + 17 building + 3 road + 2 waterway, all
   `volunteer` and `approved`. Every segmentation figure in `EVAL-BASELINE.md` is against these.
3. **30 further volunteer traces have arrived and are `submitted`, not `approved`** — 16 road,
   11 water_body, 3 building. They are not in any score. `water_body` is a feature type no scored
   figure uses. Worth knowing before anyone reports "76 volunteer traces".

**Standing hazard.** The 1,443 `import` rows sit in the same table and the same `needs_review`
state as the 72 `sam-auto` rows that contaminated the ground truth in September and voided every
`n=89` figure. `seg_eval.load_gt` filters `source=eq.volunteer`, so it is safe *today*; any
consumer that forgets that filter reads 1,443 machine polygons as truth. This is the live form of
*"a table a pipeline writes into is not a ground truth."*

---

## 1. Series C1 — modelling the survey

| figure | value | source |
|---|---|---|
| cells indexed | 706 (627 L7014 + 79 Indochine) | live, 2026-09-19 |
| held | 461/627 and 75/79 | live, 2026-09-19 |
| known printings | **1,131** over the index | live, 2026-09-19 (was 1,023 over 613 cells on 2026-09-14) |
| what a one-row-per-cell table discards | two fifths of what four institutional catalogues already state | `087_sheet_sources.sql` |
| L7014 as advertised before the index | "9 sheets" | `083_series_sheets.sql` |
| Indochine cells held in two editions | 3 (so "56 sheets" over 53 cells) | `084` |
| worked examples of cell ≠ printing | L7014 6330-4 = two maps 19 years and one city-renaming apart; Indochine cell 39 = three physical sheets | `087` |

## 2. Series C2 — georeferencing without an editor

| figure | value | source |
|---|---|---|
| sheets georeferenced by pipeline | 514 (452 L7014 + 62 Indochine); the 452 is a hand-maintained publication constant, not verified against a serving manifest — archive-reported total, not a checked count | `allmaps-series-note.md` |
| Tonkin originals placed, no model calls | 121 of 121 | commits 2026-09-15 |
| Như Trác printed corners | `115ᵍ,20`/`22ᵍ,875` and `115ᵍ,40`/`22ᵍ,75` → 106.017 E/20.5875 N, 106.197 E/20.475 N | `allmaps-series-note.md` §2 |
| conversion | grades × 0.9 = degrees from Paris, + 2.3372 for Greenwich | ibid |
| two independent checks | ground box 18.75 × 12.48 km aspect **1.50** vs neatline 4496 × 3014 px aspect **1.49**; ~4.2 m/px ≈ 150 dpi on a 75 × 50 cm sheet | ibid |
| where **our own L7014 inward walk** stops on these sheets | at the graticule band — 40 px / 170 m short, residuals 14–41 px, every edge rejected | ibid |
| what MapEdge actually does (read in full 2026-09-19) | 1D black-pixel histograms on patched edge strips, peaks ranked against a user-declared fuzzy width prior, RANSAC per side, intersect. **No inward walk.** Reports no metric error figure at all | `related-work.md` §4 |
| the graticule confusion itself | **named as a limitation in MapEdge's own Discussion** — "linear features, such as graticule lines, can occupy the same number of black pixels as the neat line". Cite as their stated open problem, never as our finding against them | ibid |
| the anchor that works | thick neatline, `argmax`, no threshold — darkest thing on the strip by 3× | ibid |
| rim-to-neatline constant, Như Trác | 83.2 / 84.9 / 83.5 / 83.9 px on the four sides | ibid |
| cost of averaging half a sheet | scans up to 0.8° off square; a 10 px line smears across 30; top neatline landed 35 px out | ibid |
| cost of four rotations instead of one | opposite edges of the quad differed by 14 px where the projection says 4 | ibid |

## 3. Series C3 — verification

### 3.1 The lattice (relative)

```
west edges    9 distinct, smallest step 0.200ᵍ, off the 0.20ᵍ lattice by 0.000
north edges  15 distinct,                        off the 0.125ᵍ lattice by 0.000
rim offset   84.2 px median, 58/58 sheets within 15% of it
sheet numbers 0 rows out of order
```
`allmaps-series-note.md` §2. 58 sheets read independently.

### 3.2 Seams (relative)

| figure | value | source |
|---|---|---|
| mosaic-only cohort | **717** PDF/PDF seams; median 9.2 m; 97 over 300 m | `work/l7014/regen/REGEN.md`, 2026-09-20 |
| hand-extended cohort | **778** total: 717 PDF/PDF + 36 JPG/PDF + 25 JPG/JPG; median 9.2 m; 111 over 300 m | ibid |
| hand-to-mosaic subset | **36** JPG/PDF seams, spanning 1.8–446.2 m; seam components median 438.0 m E/W and 133.7 m N/S, recombined 457.9 m | `regen/seams-faulty-hand.csv`, 2026-09-20 |
| free subsets in corrected run | 715 PDF/PDF; the 25 JPG/JPG at 0.0–0.6 m are **not** free-seam evidence — `l7014_hand.py` assembles the hand manifest from lattice-derived ground corners on both sides, so this describes boundary consistency, not independent registration. Only PDF/PDF is used as free-seam evidence | ibid |
| **free-seam A/B, binned** (Figure 5) | PDF/PDF only. faulty **377 / 149 / 2 / 92 / 97**, corrected **492 / 218 / 5 / 0 / 0** over bins 0–10 / 10–50 / 50–100 / 100–300 / >300 m. **189** faulty seams exceed 100 m; **0** corrected ones do. Median 9.2 m → **6.8 m** | `regen/seams-faulty.csv` + `seams-fixed.csv`, binned 2026-09-20 |
| **the fault in space** (Figure 6) | of 627 cells: **269** warped and displaced, **168** warped and placed, **73** held but not warped, **117** not held. No `indian1960` sheet between **14°N and 17°N** | `figures/fault-map.json`, from `lattice.json` + `regen/datum-split.csv`, 2026-09-20 |
| what Heitzler et al. (2018) report (read in full 2026-09-20) | Hough-transform grid intersections, per-cell bilinear warp. Per-module precision on 20 sheets: corners 100%, grid intersections 97.9% → 94.6% after local optimisation, coordinate detection 93.8%, symbol interpretation 95.6%. **No ground-distance error anywhere in the paper** | `related-work.md`, Heitzler note |
| their one seam demonstration (Figure 11 in their paper) | one adjacent-sheet pair, by eye: a stream's topological break across the seam closes, a road's mismatch persists in both (attributed to needing conflation, not better georeferencing). No threshold, no denominator, no count | ibid |

### 3.3 The datum traps (absolute)

| figure | value | source |
|---|---|---|
| displacement | 395–528 m, median 455 m | `work/l7014/regen/REGEN.md`, 2026-09-20 |
| sheets shipped that way | **276 by fit / 269 by CRS displacement**, of 437 | ibid |
| `fit` verdict on the shipped archive | 341 of 452 sheets more than 150 m off their cell | ibid |
| PROJ non-uniformity (probed) | `106.00,16.00` moves **470 m**; `109.25,13.25` moves **0** | ibid |
| the blind self-check, at population scale | of 510 source files, 62 have no usable control; **448** reach `graticule_error`; it rejects **11**, leaving **437** in the faulty build, including **all 269** displaced sheets; the rejections it did issue fire at **0.004–0.076 deg** off the printed graticule, so this is not a sensitivity limit | `regen/warp-faulty.log`, 2026-09-20 |
| matched-pair seam result | same 715 PDF/PDF edges before/after correction: **189 → 0** above 100 m, max corrected edge 72.4 m; the two faulty-only edges (excluded from the match) measure 3.6 m and 15.6 m, so attrition cannot explain the tail's disappearance | `seam-paired-analysis.json`, `scripts/paper-seam-pairs.mjs`, 2026-09-20 |
| **A Lưới is _not_ a displaced sheet** | `6441-4` resolves to `declared`, CRS displacement **0.00 m**; `graticule_error` **2.167e-12**. It demonstrates the blind check on a *correctly placed* sheet. Never describe it as displaced — the earlier "2e-12 against a real 470 m displacement" conflated two sheets | `regen/datum-split.csv` + `REGEN.md`, 2026-09-20 |
| CRS selection against the adopted frame | `pick_crs` scores registration points against the lattice cell (150 m cutoff, refuses above it); `cell_corners` shares the same Everest 1830 (1937 Adj.) Helmert parameters as the alternative candidate, so agreement tests consistency with the adopted frame, not independent absolute accuracy at the ~15 m index-to-outline scale | ibid |
| the Helmert | Everest 1830 (1937 Adj.) `+a=6377276.345 +rf=300.8017 +towgs84=198,881,317` | ibid |
| `fit`, faulty pass | **161 of 437** on cell, median **11 m**, worst **50 m**; **276** more than 150 m off cell | `regen/fit-faulty.log`, 2026-09-20 |
| `fit`, corrected pass | **434 of 436** on cell, median **10 m**, worst **95 m**; **2** more than 150 m off cell — `6630-4` Xa Phan Thiet (mean 662 m, worst 2623 m) and `6349-4` Cua Tra Ly (mean 396 m, worst 1565 m) | `regen/fit-fixed.log`, 2026-09-20 |
| ~~dry run of the fix: median 430 m → 0 m, p95 9 m, max 115 m, none over 150~~ | **withdrawn 2026-09-20.** Sourced to `pipelines.md`, which predates the controlled A/B. `fit` reports no all-sheet median — it reports a median over the *on-cell* subset plus a count of off-cell sheets, so "430 → 0" was never a statistic `fit` computes. Superseded by the two rows above | — |
| ArcGIS index, shifted correctly | agrees with the GeoPDFs' own `NEATLINE` to **4–17 m** | `architecture.md` |
| hand-georeferenced sheets | 2.3–19.0 m rms, unaffected | ibid |

**State to report, not hide:** the live archive `l7014-20260913` is **not rebuilt**. `fit` fails on
it. This is the paper's exhibit, and it must be labelled as current state.

### 3.4 `Ha Noi` — the sheet every per-sheet check passes

Corners agree with each other · ground scale agrees with pixels to **0.78%** · rim at the series
offset · content is unmistakably Hanoi · and at 22ᵍ,56 it sits **75 km south** of the city it is
named after. Longitude right, latitude a clean 0.75ᵍ out. Caught only because it landed on Ninh
Bình's lattice cell. `allmaps-series-note.md` §2.

### 3.5 The river-channel probe, and its null

| figure | value |
|---|---|
| method | sheet warped to web-Mercator from four detected corners; Esri World Imagery for the same grid; water masked both sides; 794 rows compared |
| result | median **+58 m east** (modern − 1903), spread ±180 m = the river's own migration |
| what it cannot say | one sheet; the channel runs N–S so carries no N–S information; a full 2-D correlation put its peak against the search window edge at **z = 2.0** — the aperture problem, not a result |
| the confluence | agrees to ~100 m — reassurance, not measurement |

### 3.6 The IIIF size-segment mismatch (serving)

| figure | value | source |
|---|---|---|
| cause | `vips dzsave --layout iiif3` writes explicit `w,h`; canonical IIIF (and `@allmaps/render`, OpenLayers) request width-only | `worker/src/iiifKeys.ts` |
| rounding rule | dzsave size is `ceil(region / scaleFactor)` **per axis independently** — height follows the scale factor, not the requested width | ibid |
| failure rate at full resolution | **0%** | ibid |
| one level below the whole-sheet overview | **58.6%** of tiles, across the 83-sheet Indochine survey | ibid |
| why it survived a year | the one real key the old test pinned (`3758*256/4096 = 234.875`) rounds the same under `ceil` and `round` | ibid |
| test | `tests/tile-size-segment.spec.ts`, 29 checks against keys read out of the bucket | `docs/testing.md` |

---

## 4. Cited figures — verified through scite, 2026-09-19

| claim | verified value | DOI |
|---|---|---|
| SODUCO / MapSeg benchmark | **51.1% COCO PQ** best pipeline (U-Net + contrast + TPS aug.); 46.7% before aug.; 47.1 → 45.1 mini-U-Net ablation. **COCO PQ throughout; no F1 reported.** | 10.1371/journal.pone.0298217 |
| MapSAM2 memory attention | +14.3 IoU vineyard, +16.1 railway, both 10-shot (Table 2) | 10.48550/arxiv.2510.27547 |
| MapSAM2 prompt quality "+12.8% F1" | **UNVERIFIED** — full text not indexed, could not be read. MapSAM2 *does* cite YOLO (10.1109/cvpr.2016.91) from its Methods, so the shape is plausible. **Do not quote.** | ibid |
| MapSAM2 authorship | first three are **Xue Xia, Randall Balestriero, Tao Zhang** — not the ETH IKG list `network.md` §4f assumes | ibid |
| no editorial notices on either | checked, clean | — |

**Withdrawn, do not use:** "diacritic retention varies 9%–100% by run, not by sheet". Retracted in
`EVAL-BASELINE.md` 2026-09-08 — the pair spanned several sheets and was reading corpus composition.
Retention tracks the sheet's **language** (1895 fr 0.08–0.14 … 1959 vi 0.80–1.00), ±0.1 within a
sheet. The metric survives; this evidence does not.

---

## 5. Numbers that exist and must not be quoted

| number | why |
|---|---|
| 75/85 and 68/85 on the 1882 gate | both grids ceased to exist at `b532d3b9`; neither is reproducible | 
| any 1–2 label difference between two runs on one sheet | `_cached_tile` reads `{key}@{requested_render}` and writes `{key}@{max(size)}`, so right-edge tiles are re-fetched with different bytes every run |
| "354 tests" as integration coverage | 18 browser + 336 browser-less pure + 33 write against a local stack |
| "about nine seconds" for the colour pass | pre-`--recut`; the shipped reference run is **80 s** (25 s `--no-recut`) |
| $12–24 for the corpus OCR | pre-correction basis; billed is **$31–63** (thinking tokens) |
| 118, unqualified | three different senses circulate — polygons produced, the retracted trace set, and rows scored |
| any `cost_usd` as settled | the 3.5–4× thinking-token multiplier is still unverified against an invoice |
| the monorepo in `platform-design.md` | a proposal; `contracts/` holds three schemas and a ~50-line subset walker |
| anything from `work/deck-and-kg-2026-05/kg/` | frozen 2026-06-04 snapshot; migration head 048, 101 maps |

---

**Correction, 2026-09-19 (same day).** The row above previously read *"where MapEdge's inward walk
stops here"*. MapEdge has no inward walk — that is `scripts/l7014_neatline.py`, ours.
`allmaps-series-note.md:109` and `docs/private/allmaps.md:195` were correct all along; this file
compressed the sentence and reassigned the method to Meijers & Schoonman. Caught by reading the
paper in full. Recorded rather than silently rewritten, per the `note:` convention.

**Correction, 2026-09-20.** §3.3's dry-run row and blind-self-check row were both stale against
`work/l7014/regen/`, which is the source and therefore wins. Two claims that had reached `draft.md`
were wrong, not merely imprecise: A Lưới was described as a displaced sheet (it is not — 0.00 m,
`declared`), and the correction was said to leave no sheet more than 150 m off its cell (it leaves
two). `REGEN.md`'s "Against the paper's claims" table had already marked both **revise**; the
2026-09-20 claim audit transcribed seven of its nine revise rows and missed these. Recorded rather
than silently rewritten, per the `note:` convention.

## Changelog of this file

- **2026-09-20** — Applied the ARS integrity-correction round (`technical-revision-proposal.json`,
  now `APPLIED`) to keep this ledger in step with `draft.md`: the 452-sheet publication constant is
  now marked archive-reported/unverified; the blind-self-check row carries the full 510→62→448→11→437
  denominator chain; the JPG/JPG hand-seam figure is marked as boundary-consistency, not free-seam
  evidence; the CRS-selection row is reframed as consistency-with-adopted-frame; a matched-pair seam
  result row was added.
- **2026-09-20** — Heitzler et al. (2018) read in full; two rows added to §3.2. See `related-work.md`,
  the Heitzler note.
- **2026-09-19** — MapEdge read in full; §2's "inward walk" row corrected (it described our detector,
  not theirs) and two rows added. See `related-work.md` §4.
- **2026-09-19** — created. Phase 0 of the paper plan. Live counts pulled; ten documented
  contradictions resolved across `pipelines.md`, `field-comparison.md`, `image-processing-record.md`,
  `digitalize-guide.md`, `db-guidelines.md`, `src/lib/CLAUDE.md`, `worked-example-1882.md`,
  `network.md`, `260918-colour-blocks.md`, `work/MapSAM2/evaluate.py`, the two frozen `kg/` files and
  two published blog posts.
