# The 1882 colour layer, reviewed — what is missing, and what was hiding it

**2026-10-01.** Question: is the 1882 colour-pass layer duplicated, missing features, or not
normalized? Checked against `colour-20260919-normalized/blocks.clean.geojson` (1,431 features),
the layer `sheet_register.py` reads. The 4096 run from
[the colour-pair journal](261001-colour-pair-1882-1898.md) is saved at
`work/image-processing/results/<id>/colour-20261001/` for both sheets (`image_sha256` pinned in each
`blocks.run.json`) and is **not** canonical.

## Findings

**Normalized.** All 1,431 features carry the same five keys, valid geometry, an `area_px` that
matches the polygon, coordinates inside the sheet, a unique `source_index`. Ten polygons have holes
(the queue stores none). Buildings carry no `category`.

**Duplicated: no.** No pair above IoU 0.8, no exact ring twice. All 550 buildings sit inside a
`land_plot`, which is the design: two layers. Cream parcels nested inside other cream parcels: 89
pairs, plus 29 partial overlaps; about 6% of parcel area is counted twice. The largest cases are
around source 367 (8 holes) and are not yet looked at.

**Missing: buildings.** Of the 17 volunteer `building` traces, 7 have no predicted building at all.
Causes, from a contact sheet of all 17:

| Cause | Traces | Note |
|---|---|---|
| Grey fill or hatch (College d'Adran, Palais du Gouverneur, Conseil de Guerre) | 3 | `split_buildings` finds wash *redder than the parcel's own median*; a grey building has no such cue. Already recorded in its docstring. |
| Building on a green or blue parcel | 2 | Same cue fails. |
| Dense shophouse block returned as one polygon | 3 | A detection that is not split: IoU 0.03 against a small trace. |
| Trace may not be a building | 4 | Reviewed below. |

Parcels are well covered: no traced parcel lacks an overlapping prediction.

## Trace check

Four building traces the pass found nothing for were shown large, with the outline toggleable.
Verdicts (project owner, 2026-10-01):

| Footprint | Verdict |
|---|---|
| `c212943f-fb34-48de-a5b6-5e53410d214a` | **not a building** |
| `109dbc15-333b-47d8-a6ba-3bcfc4972825` | **not a building** |
| `148ba772…` | building |
| `e4db92c6…` | building |

Both "not a building" traces are still `approved` in `footprints`. `seg_eval.load_gt` does not filter
on review status on purpose, so rejecting them would not change a score; the exclusion is
recorded here instead.

| Layer | Predictions | 17 traces | 15 traces |
|---|---|---:|---:|
| 19 Sep clean | all | 0.355 | 0.393 |
| 19 Sep clean | building only | 0.275 | 0.312 |
| 1 Oct 4096 | all | 0.302 | 0.337 |
| 1 Oct 4096 | building only | 0.265 | 0.300 |

Hits at IoU 0.5 do not move (5 of 15, or 4 with building predictions only). The two exclusions were
made after their low scores were known, so quote the 15-trace figure as "2 of 17 excluded after
review". **Building predictions only** is the stricter row; the usual all-predictions setting lets a
parcel polygon score as a building. The ROADMAP's 0.355 is the 17-trace, all-predictions figure and
is unchanged here.

## What was hiding the buildings from review

The Validate queue (`/scan?mode=shapes&tab=validate`) showed "1000 pending" for a run of 1,443.
`fetchSubmittedFootprints` and `fetchMapsWithSubmittedFootprints` read an unpaged select, and
PostgREST caps those at `max_rows = 1000` without an error. The list is ordered by `created_at` and
the 888 parcels were imported before the 555 buildings, so roughly 443 buildings could never be
reviewed. The pending count was capped too, across all maps at once. Both reads now page through
`readAllPages` with a unique `id` tail on the order, pinned by `tests/footprint-queue.spec.ts`.

## Precision sample (project owner, 2026-10-01)

A random 30 of the cream parcels (seed 20261001) and all 24 `admin` features, from the 19 Sep clean
layer, each marked keep or drop with a reason. The verdicts are not stored in the repo.

| Class | Keep | Drop | Drops that are not an object | Drops that are a real object, wrong extent |
|---|---:|---:|---:|---:|
| cream (30 sampled) | 17 | 13 | 7: tree and grass noise, road-name text, red planning line | 5, plus 1 ambiguous (`854`, noted "normalize", marked drop) |
| admin (all 24) | 4 | 20 | 7: water 4, name noise 2, road silver 1 | 13: hatch covers part of the plot, or mixes grey and red plots |

- Cream is 17 of 30 usable, 57% (about 39–73% at 95%, n = 30). A 23% false-detection rate is the
  harder number: 7 of 30 are not a parcel at all.
- **Every one of the 17 cream keeps carries "need to normalize and polygonize".** No kept outline
  was accepted as is. Outline regularisation is a separate missing stage, not a detector fault.
- The `admin` drops are mostly real public sites (Poste de Police, Marché Central, the opium
  boiling-house) whose hatch does not enclose the plot. Seven of 24 are not an object; none of the
  four keeps was clean either.
- Two cream parcels are cut by the river or a branch of it (`553` dropped, `747` kept with a note).

**A candidate filter, not applied.** Area under 12,000 px² and circularity (4πA/P²) under 0.5 removes
7 of the 13 cream drops and none of the 17 keeps; circularity under 0.5 alone removes 7 of the 20
`admin` drops and none of the 4 keeps. It was read off the same 30 and 24 labels, so it is in-sample
and needs a held-out sample before any drop is made.

## Outline regularisation

`work/ocr/scripts/regularize_blocks.py` straightens the outlines on `blocks.clean.geojson` and writes
`blocks.regularized.geojson` beside it (same features, same order; `reg` and `iou_orig` added; the input
is untouched). It simplifies at 5% of the plot's size, cuts chamfered corners to a sharp meet, and slides
each edge onto the nearest ink line. A snap that moves a plot more than 15% IoU falls back to the cut
outline. Nothing is squared; an L stays an L (`--self-check` pins both).

- **1882, all 1,431 features:** 918 snapped, 512 cut only (the guard held the snap back), 1 left as is.
  No invalid geometry; median IoU to the original 0.94; 17 holes dropped in 10 polygons.
- **Scoring does not move.** Against the 17 building traces: 0.355 → 0.361 (all predictions), 0.275 → 0.281
  (building predictions only); hits at IoU 0.5 stay 5 and 4. This is tidiness, not accuracy: the extent
  errors above are untouched.
- **Reviewed by eye on the 17 kept cream parcels only.** Buildings (small, so the snap reach is 2–3 px and
  the guard held back 300 of 550), the salmon, blue, green and `admin` classes, and the 1898 sheet are
  unreviewed.
- **Known miss:** the ink map cannot tell a thick stroke from a thin one, so the printed diamond (#799)
  sits just inside its shadow stroke. The ceiling is named in the script's docstring.

## What separates a plot from residue

Shape metrics on the regularized layer (1882, 1,431 features), against the 54 verdicts. AUC is the
chance a random keep scores above a random drop; 0.5 is no signal.

| Signal | Cream AUC | Admin AUC |
|---|---:|---:|
| Nodes in the regularized outline (fewer is a plot) | 0.93 | 0.79 |
| Fill: area over its minimum rotated rectangle | 0.94 | 0.90 |
| Boundary on ink: share of the outline within 2 px of an ink line | 0.94 | 0.77 |
| Longest ink-free run of the outline (shorter is a plot) | 0.93 | 0.77 |
| Circularity | 0.88 | 0.76 |
| Area, aspect | 0.75, 0.76 | 0.72, 0.53 |

Kept cream parcels have a median of **4 nodes**; dropped ones, 7. A plot is a quadrilateral and residue is
not, and that survives regularisation, so node count is the cheapest filter. Boundary ink support adds
what node count cannot see: a clean four-sided shape that follows no ink line.

- **Candidate rule: at most 5 nodes and at least 95% of the outline on ink.** On the 30 cream verdicts it
  keeps 15 of 17 keeps and passes 1 of 13 drops; on the 24 admin, 3 of 4 and 2 of 20 (admin's looser variant
  of the fill and node test keeps all 4 and passes 2). In-sample, so read it as a ceiling.
- **Held-out sheet, 24 cream features nobody had labelled (12 removed by the rule, 12 passed)
  (`colour-20261001/filter_check.jpg`). The project owner labelled 16 of them; 8 are still unlabelled.**

  | Rule said | Owner's verdict |
  |---|---|
  | passed, 11 labelled | 10 real plots: `356`, `753`, `639`, `771`, `422` clean; `604` clean but a boundary line runs through it; `700` and `53` real plots cut by the river; `861` and `789` thin blank plots in the middle of a street. `802` is a sliver of road-name text |
  | removed, 5 labelled | `788` a real lot with the edge wrong; `221` a clean red blank plot; `781` a blank strip in a street or tree line; `847` a bosquet, not a plot; `810` land by the river |
  | unlabelled | passed `805`; removed `348`, `342`, `849`, `818`, `343`, `518`, `282` |

  The rule's pass set was 10 real plots of 11 labelled. Its removed set is not residue: three of five
  labelled are real plots (`788`, `221`, `781`). `221` misses on ink support 0.949 against the 0.95 line;
  `781` is a street strip with ink on one side only.
- **Correction.** Claude read `861`, `789`, `805`, `802` as residue (thin strips between road edges) and
  proposed an aspect cut. The owner says `861` and `789` are real blank plots in the street, `802` is
  residue as read, and `805` is unlabelled. A cut on shape alone would have removed real plots, so none
  is applied.
- **Applied to the whole cream layer:** 389 of 679 pass, 290 do not. Use it to rank the review queue, with
  the passed set first. It is not a drop rule: it removes real plots, and the removed set needs review.

## Still open

- The queue holds the 12 features the clean pass drops (outside the map body) and the ten polygons
  with holes as filled rings.
- No sample mode or per-class precision readout in Validate; the figures above come from a
  one-off review page, not the site.
- Grey-fill buildings and merged shophouse blocks are the two real detector gaps.
