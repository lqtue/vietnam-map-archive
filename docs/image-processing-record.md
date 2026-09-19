# Map image processing — what we built, how, and what it measures

**Started 2026-09-19.** A single collection of the image-processing work, so it can be held
against what the field is doing. Nothing here is new: every number is copied from the file that
measured it, and that file is named. Where the two disagree, the source file wins.

Primary sources, in order of evidential weight:

| file | what it holds |
|---|---|
| `work/ocr/EVAL-BASELINE.md` | every OCR and segmentation number, with its run and its caveats |
| `docs/journals/260918-colour-blocks.md` | the colour-block pass, built and measured over two days |
| `docs/journals/260919-seg-audit.md` | the audit of that pass, its work list, and the results |
| `docs/worked-example-1882.md` | one sheet through every stage, with the four defects it exposed |
| `docs/pipelines.md` | command reference + design rationale |
| `docs/journals/260912-postgrad-route.md` | the dataset card and first-paper outline already drafted |
| `docs/network.md` §4a, §4d-bis | who works on this, and what may be claimed to them |

---

## 1. Chronology

| when | what landed |
|---|---|
| Apr 2026 | `ocr.py` — Gemini tiling pass over IIIF. `inference_tiles_as_video.py` — SAM2 entry point. 46 polygons hand-traced on the 1882 cadastral by a volunteer |
| Aug 2026 | Track C design: colour pre-pass → OCR → coarse seg → fine seg → level-aware join. `join_labels.py` written |
| early Sep | worker + job queue; OCR defaults consolidated into `vma_worker.py`; `--tile-metres`; two-pass merge; cost logging |
| 2026-09-10 | `modern_prior.py` — blocks from 2023 HCMC buildings, warped into sheet pixels. The ground-per-call measurements |
| 2026-09-11 | `seg_eval.py`. First segmentation numbers. Gemini tried as the segmenter |
| 2026-09-12 | dataset card + paper outline drafted |
| 2026-09-16 | one sheet end-to-end for the first time — first completed `seg`, first `join`, first `approved` footprints |
| 2026-09-18 | `colour_blocks.py` — blocks and parcels from the sheet's own ink, CPU only |
| 2026-09-19 | audit of that pass; within-parcel split; ground truth purged of machine rows |

Five months, one corpus, one sheet carrying almost all of the evidence.

---

## 2. The stages, and the method in each

**Georeference.** Allmaps annotations, human GCPs, helmert. On the 1882 sheet: 10 GCPs, **RMSE
11.3 m**, worst point 23.0 m; a 6-dof affine buys 10.6 m, so the scan is undistorted and more
control points buy little. That 11 m is the floor on every ground claim from the sheet.
`geo_audit.mjs` (is the map where it says it is) and `catalog_audit.mjs` (is a row consistent with
its own table) are the standing checks. L7014's mixed-datum fault — Indian 1960 read as WGS 84,
~470 m — was found by seams, and is probed for now.

**Read (OCR).** Gemini Flash over IIIF tiles. Coarse→fine: `scout` finds the neatline and dense
regions at low resolution, `batch` tiles only the content area at full. Tiles in a row are sent as
one sequence call (the cheap analogue of SAM2's memory attention). Two passes, then a merge vote.
Output is 0–1000 normalised boxes per tile, converted to full-image source pixels
(`ocr_extractions.global_*`) — georeferencing happens later, never in the pipeline.

**Shape (segmentation).** Three methods tried, in this order:

1. **SAM2 + LoRA** (`hiera_small`, r=4, `epoch_010.pth`), prompted from OCR label boxes.
2. **SAM2 prompted from a modern prior** — 2023 HCMC buildings buffer-dissolved into blocks and
   warped into the sheet's pixel grid.
3. **A CPU colour pass** (`colour_blocks.py`) that reads blocks and parcels off the sheet's own
   wash, with every threshold voted or swept from the sheet itself rather than learned.

**Join.** `join_labels.py`: smallest containing polygon, with a category↔level preference. Labels
prompt the segmenter; footprints then claim the labels.

**Measure.** `eval.py` / `eval_metrics.py` (OCR), `seg_eval.py` (polygons). Ground truth is
whatever the human review already produced, so no separate labelling step exists — which is also
the source of the contamination described in §5.

---

## 3. What is measured

### OCR

| | figure | source |
|---|---|---|
| Baseline, IoU ≥ 0.5 | recall **0.7674** · char acc **0.9808** · mean IoU **0.7234** | EVAL-BASELINE §Baseline |
| Diacritic retention, three-voter tie-break | 0.864 → **0.955** | EVAL-BASELINE |
| Two passes then agree | 41/43 | EVAL-BASELINE 2026-09-08 |
| Ground per call, 1959 sheet, same crop and rendering | 5.7 km/call → **1** label · 2.9 km → **2** · 1.4 km → **6** | EVAL-BASELINE |
| Same change, six-sheet collection | **+19%**, not 5× | EVAL-BASELINE |
| Rendering above 1:1 | byte-identical output — the scan is the ceiling | EVAL-BASELINE |
| Cost, 1882 two-pass merge / 1968 body pass | USD **0.945** / **1.236** (thinking tokens included) | EVAL-BASELINE |
| Spend spread over 1,192 calls | \$0.0012–\$0.155 per call; dearest tenth carries 28% | `docs/pipelines.md` |

The transferable result here is the third row: **what starves a VLM read is one call covering too
much ground, and a fixed pixel tile is a different amount of ground on every sheet** (2048 px is
1.7 km on the 1923 sheet, 5.7 km on the 1959 one). The map-text literature works in pixels and
does not state this. `--tile-metres` is the fix.

### Segmentation, 1882 Plan Cadastral, best IoU per ground-truth polygon

| prompts / method | land_plot (24) | building (17) | notes |
|---|---:|---:|---|
| SAM2 LoRA on OCR label boxes | — | — | **0.089** pooled over 46; median 0.000 |
| …with `--text-mask` | — | — | **0.062** — worse; flat paper in a label box makes a rectangle where the prompt is |
| SAM2 LoRA on 4 m modern blocks | **0.249** | 0.160 | cover 0.92–0.98 |
| SAM2 stock-large, same prompts | 0.198 | 0.132 | 3.7× the runtime for less |
| those block boxes used raw, no model | 0.161 | 0.093 | SAM2 is worth **+55%** over its own prompts |
| Gemini asked for polygons directly | 0.254 mean / 0.278 med (n=12 in-frame) | 0.056 | does not subdivide; median 5 vertices |
| **colour blocks, CPU** | **0.331** mean / 0.218 med, cover 0.98 | 0.122 | 888 polygons, 80 s, no GPU, trained on nothing |
| **+ within-parcel split** | 0.343 | **0.355** mean / **0.314** med | 1443 polygons, +3 s; @0.5 went 1 → 5 |

Three readings that the table alone does not give:

- **The prompt was the fault, not the model.** A box around lettering asks what is inside a
  rectangle, and SAM2 answers by redrawing it — median IoU 0.64–0.68 between a mask and its own
  prompt box. Only 22 of 46 traces contain an OCR label centroid, so label prompting could not
  exceed 48% recall whatever the model.
- **`building` is capped by granularity, not by the segmenter.** Cover is 0.98–1.00 — the ink is
  found, the subdivision is not. That is what the within-parcel split addresses, and it is the
  biggest single move made on this sheet: a **local** threshold (each polygon's own ink-excluded
  wash median, median delta +0.035) where five months of sheet-level threshold work found nothing.
- **Read the median, not the mean.** `seg_eval` takes the best match per trace, so a mean rises on
  prediction count alone. The median and @0.5 cannot be bought that way.

### Join

`join_labels.py` on the 1882 sheet, pinned to the reviewed OCR run:

- **19 of 177** against hand-traced polygons. **14 of the 19 are exact name agreement between two
  sources that never saw each other** — Gemini reading ink in May, a volunteer tracing shapes in
  April. The join corrects the volunteer as often as the reverse, and it names four polygons that
  carried `name: null`.
- **68 of 177** after segmentation — and this is the number not to quote. 63 of the 68 have label
  text identical to polygon name *because the name came from the seed that prompted the polygon*.
  Independent corroborations went **19 → 8**. The archive gained 49 links and lost 11 pieces of
  independent evidence; only one of those is visible in the headline.

---

## 4. Methods tried and rejected

Worth as much as the wins, and cheaper to cite:

| null | why |
|---|---|
| Neighbour-window OCR batching | −16 pts recall; bad `frame_idx` attribution, centroid ownership leaking in the overlap band |
| v8 prompt plumbing | correct plumbing, worse output; rejected as default |
| First colour/wash pre-pass | scored 0.000 on every tile — every saturated pixel is hue 0–60° and the detector looked at 60–260° |
| Gemini as the segmenter | leads on IoU against block-sized traces, but 22 of 37 calls returned exactly one object, median 5 vertices — a rotated rectangle, not a boundary. Two calls on the same crop minutes apart: 18 objects, then 1 |
| Nearest-legend-swatch classification | measured, rejected |
| Enclosed-water rule (dock/lake inside a parcel) | scored **identical to the digit** and was still wrong — missed both targets, put water in two control windows. `solid` is not a water mask; it is *dark, bluish and ruled*, and an ordinary city block satisfies it over 17% of its area |
| Ink axis for the dark building convention | explodes component count — dense ink is also lettering, hatching and every block outline |
| Four pattern axes on the Arsenal edge | all four null; the discriminator is the drawn outline, not the fill |
| Named street network from cream + `street_name` | not built — the hull of a street network is a disc, and nothing on this sheet can referee a street-surface polygon |

Two of those (Gemini-as-segmenter, enclosed water) also produced the more useful finding: **the
metric could not see the thing that mattered**, five times on this track.

Silent bugs found by scores being wrong, both undocumented upstream behaviour:
Gemini's `box_2d` is `[xmin, ymin, xmax, ymax]`, not the documented y-first order (mean IoU 0.909
vs 0.284 over 240 objects); its `mask` is normalised to the image, not to the bounding box (0.254
vs 0.141).

---

## 5. What is not established

Four blockers, unchanged as of 2026-09-19, and the first is the real one:

1. **There is no precision number, and the metric cannot produce one.** `seg_eval` scores the
   best-matching prediction per trace and never looks at a prediction that matched nothing — 1,443
   polygons against 46 traces score exactly as well as 46 good ones would. Every false positive
   found so far was found *by eye*, by rendering the run. `seg_eval --window` now exists; no window
   has been exhaustively traced. **This is a tracing job, not a code job.**
2. **Every SAM2 figure is a train-set score.** The LoRA was fine-tuned on the same 46 traces it is
   scored against. A held-out trace set does not exist.
3. **One sheet, one era, one printer.** The colour pass's thresholds self-calibrate by design, but
   that is a claim about the method, and the method has been run on one sheet. Two more, from
   different decades, is the minimum.
4. **The colour pass produces a prior, not footprints.** "No GPU" is true of the prior and not of
   the pipeline.

And one process lesson that cost a day: **a table a pipeline writes into is not a ground truth.**
72 machine rows (`source='sam-auto'`) sat in `footprint_submissions` alongside 46 volunteer traces,
were OCR label boxes rather than buildings (median IoU 0.83 to their own prompt box), and voided
every `n=89` figure until they were found by rendering an overlay. They also caused a null to be
declared and later retracted. Deleted 2026-09-19, backed up first.

The sentence currently defensible in public, quoted verbatim from `docs/network.md` §4d-bis:

> a CPU-only colour pass, calibrated from the sheet itself and trained on nothing, produces a
> block-and-parcel prior for a polychrome cadastral sheet in about nine seconds, and on the one
> sheet measured it covers every hand-traced land plot.

---

## 6. Where this goes next — the comparison itself

This file is the inventory. The landscape pass is the next step, and the repo already carries its
anchors:

- **MapSAM2** (Xia et al. 2025, arXiv:2510.27547) — the tiles-as-video framing this pipeline
  borrowed. Its self-sorting memory bank is still unimplemented here; the paper measures memory
  attention alone at +14.3% IoU on vineyards, +16.1% on railways, and prompt quality at +12.8% F1.
- **SODUCO F1 = 0.59** — the segmentation baseline `work/MapSAM2/evaluate.py` quotes.
- **Bahgat & Runfola (2021)**, toponym-assisted georeferencing — asked in print for the exact
  triple this corpus holds.
- **ICDAR MapText** (Zou et al. 2025) — Rumsey, French Napoleonic cadastre, Taiwanese maps, and no
  Vietnamese in any of them.
- **Chen et al. (2024)** vectorization benchmarks · **mapKurator / Yao-Yi Chiang** · **EPFL DHLAB**
  (Jerusalem 1840–1940 4D) — the groups whose work is nearest, listed with what to lead with in
  `docs/network.md` §4a.

Three axes on which this work is plausibly not the same as theirs, to be checked rather than
assumed: a **VLM rather than a trained detector** as the prompt and text source; **ground per call**
as the resolution variable instead of pixels; and a **self-calibrating CPU colour prior** where the
field reaches for a fine-tuned model. Each needs the precision number in §5 before it is a claim.
