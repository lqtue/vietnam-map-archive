# Processing the 1882 and 1898 plans: river, road, block, building

> **Superseded 2026-10-03** by `docs/image-processing-1882-plan.md` (1882 only; 1898 deferred).
> Kept as the record of the 2026-10-01 plan; do not work from it.

**Plan, 2026-10-01. Nothing here is approved or measured unless a number is cited.** The 1882
Plan Cadastral (`0e02b9d9-…`, 12102 × 8982 px) is the in-depth sheet; the 1898 Bertaux plan
(`20ec4f9a-…`, 16267 × 14859 px) is the paired transfer check. Open items live in
[ROADMAP.md](../ROADMAP.md); river detail is in [river-reconstruction.md](../research/river-reconstruction.md).

## Rules for every stage

1. **One method, two calibrations.** Develop a method on both sheets; fit its appearance model
   on each sheet separately. Swapping 1882's and 1898's auto-derived colour constants cost 1882
   0.08 `land_plot` IoU and erased its road proposals
   ([journal](../journals/261001-colour-pair-1882-1898.md)).
2. **Source pixels, one pinned native tile level.** Pyramid levels shift thin-ink colour
   (`work/analysis/river_pair/README.md`). Record the scale of anything not at native.
3. **Reference windows, not whole sheets.** Hand-trace small windows, hold some out of all
   tuning, score by case. Same layout as `work/image-processing/experiments/river-reference/` for every stage.
4. **A stage's output is evidence for the next, never trusted by it.** Each stage consumes the
   previous layer as a *prior with a confidence*, so a river error cannot silently become a
   road error.
5. **No layer is approved without human review** of the low-confidence reaches, with
   corrections recorded in source pixels.

## What prior work says (read how deeply, and what it changes)

| Source | Finding | Depth | Changes in our plan |
|---|---|---|---|
| [Swiss Territorial Data Lab, Geneva 1850s cadastre](https://tech.stdl.ch/PROJ-CADMAP/) | Plans of 12,000 × 8,000 px, close to ours. Parcels, buildings, roads, rivers. 8 plans annotated; urban plans cost 2–3× rural (4–6 h). Multi-class mIoU 0.78; vectorization IoU 0.975, median Hausdorff 3 px; ~90% of polygons found; manual corrections still needed. | page summary | Sets the annotation scale; separate "borderline" detection from class segmentation. |
| [Annotation for cadastral vectorization (DSH)](https://academic.oup.com/dsh/article/38/3/1227/7074303) | Annotate what is *visible*, not the interpretation. A dozen sheets bootstrap a model. Accuracy falls as classes are added, so use two or three. | page summary | Binary stages (water / not-water, road / not-road) before any multi-class model. |
| [Vectorization benchmark, Paris atlases](https://pmc.ncbi.nlm.nih.gov/articles/PMC10868791/), [MapSeg](https://arxiv.org/pdf/2105.13265) | Edge probability then Meyer watershed gives closed shapes. Scored with COCO Panoptic Quality (best 51.1%). U-Net beat transformers. Topology losses gave little. | page summary | Block method to trial, and the block/building metric. |
| [Yuan et al. 2025](https://arxiv.org/pdf/2501.01845) | Pseudo-labels from neighbouring dates ("age-tracing") lifted mIoU about 20% over one-map baselines. Flowing water was weak (IoU 56.8 → 72.1 on 1898). Label drift between dates hurt, and one-directional tracing across a long gap was worse. | **read pp. 1–6** | How we use the 1882 ↔ 1898 pair. |
| [López-Rauhut et al. 2025](https://arxiv.org/pdf/2505.24824) | Forest, hydrography, roads, buildings over four centuries. Compares sparse historical labels, modern-label weak supervision and CycleGAN style translation. | abstract + related work only | Translation is an escalation, not a first step. |
| [Probabilistic road classification, synthetic data](https://arxiv.org/abs/2410.02250) | Extract geometry, skeletonize, repaint with the sheet's own symbology to make training data. Road completeness > 94%, correctness > 92% on Swiss maps. | abstract | Road stage: bootstrap from our own road-edge ink without labelling every class. |
| [TimeWalkOrg/Map_Reader](https://github.com/TimeWalkOrg/Map_Reader) | Ink threshold or SAM candidates, hatch-texture test to tell building fill from lettering, regularize to the street grid, human check in QGIS. Mean IoU 0.256; "SAM grabs whole hatched blocks". | page summary | Same failure we see; keep a human gate. |
| [PoLiS](https://elib.dlr.de/90425/1/avbelj_GRSL_00093_2014_final_submitted.pdf), Boundary IoU | Threshold-free polygon distance and boundary-band overlap for footprints. | snippet | Building outline metric. |

Not found: any paper on ruled-line water on 1:4000 city plans. scite was unavailable, so none of
these were screened for retractions or citation context.

## What exists in the repo

- `colour_blocks.py` makes blocks, parcels and buildings from the sheet's own ink. 1882 best-match
  mean IoU is 0.343 on 24 `land_plot` and 0.355 on 17 `building` traces. Those traces were
  selected, so they do not measure precision. Road: 0.162 on three traces at a 4096 render.
- MapSAM2 (LoRA, 46 volunteer traces, no independent test set), prompted by OCR boxes.
- `footprints.feature_type` already has `building`, `land_plot`, `road`, `waterway`, `water_body`.
- `river_ref/`: 19 windows, a scorer, and no traces yet.

## Stage 1 — River

*Defined and gated in [river-reconstruction.md](../research/river-reconstruction.md).* Summary: trace
`river_ref` windows → seeded region graph on native tiles (water likelihood from paper-relative
colour, line density, direction; bank-aware cost) → score by case → human review.
**Output:** a water mask and shoreline in source pixels, with a per-reach confidence.
**Used downstream as:** strong negative evidence for road and block, and the boundary for both.

## Stage 2 — Road

**Definition.** Road surface is the cream band between ruled street edges, outside water.
A street is also a centerline graph, because that is what Walk and the street-name join need.
**Method to trial, in order:**
1. *Surface:* the complement of {blocks, buildings, water} inside the sheet's printed neatline,
   cleaned by area. This is what `colour_blocks.py` already half-does, so measure it first.
2. *Edges:* binary edge detector on the dark street lines (U-Net, pretrained) trained on
   `road_ref` windows only. The synthetic-repaint approach above is the fallback if windows are too few.
3. *Centerline:* medial axis of the surface, simplified, joined at intersections.
**Reference set:** ~6 windows per sheet: regular grid, irregular outskirts, crossing a bridge,
dead-end, the quay road along the river, and a plaza. Trace road surface and `ignore` (labels).
**Metrics:** surface IoU / missed / false (same scorer); centerline completeness and correctness
inside a buffer whose width comes from the traced road width; connected components
and dead ends versus the traced graph.
**Gate:** both sheets, held-out windows, no leak into water or block interiors.
**Risks:** road lettering and printed street names inside the cream; outskirts where roads are
drawn as a single line, not a band; 1882 and 1898 road edges differ (the swap test erased 1882's
road proposals).

## Stage 3 — Block

**Definition.** A block is a closed face bounded by road surface and water, one polygon per
street-enclosed parcel group. A parcel (`land_plot`) is a division *inside* a block; keep them
as separate layers, because the current `land_plot` mixes both.
**Method to trial:** closed-shape extraction on the road and water layers (watershed on an edge
probability map with area and dynamic filtering, per the Paris benchmark), compared with the
current colour pass. Hierarchy is then deterministic: road → block faces.
**Reference set:** ~6 windows per sheet across dense, sparse, outskirt, quay-edge, a block cut
by a window edge, and a blue-wash domain block.
**Metrics:** COCO Panoptic Quality on matched polygons (segmentation quality × recognition
quality), stratified by area; false-block rate on traced water and dry-plan windows.
**Gate:** PQ and false-positive rate reported per sheet and case, with 1898 never scored
using 1882 thresholds.

## Stage 4 — Building

**Definition.** A building is a filled structure footprint inside a block, drawn with dark-red
hatch or solid fill (1882) and salmon (1898). Court buildings, sheds and kitchens are separate
cases; do not merge them into one count.
**Method to trial:** colour class + hatch-texture test inside each block, then regularize to the
block's grid, compared with MapSAM2 prompted by the **same** colour prior (the existing
`shape-precision` gate: one method must not be credited for the other's prior).
**Reference set:** ~8 windows per sheet: dense salmon rows, sparse suburban, institutional
(hatched large footprints), shophouse terraces, a hatched block that is *not* a building.
**Metrics:** PQ plus Boundary IoU and PoLiS on matched pairs; false-positive rate on blocks
traced with no buildings; count and area totals per case.
**Gate:** per case, per sheet. Whole-sheet totals are reported only if the windows were chosen
by a rule, not by looking.

## How the two sheets help each other

After a stage has a scored method on one sheet, use its confident predictions as pseudo-labels
on the other and fine-tune (Yuan et al.'s age-tracing). Two cautions the paper's own results
support: they gain most with an anchor *between* dates, and we have only two, so treat the
result as a transfer test, not free training; and the 16-year gap carries real change
(river banks, new streets, subdivided plots). So pseudo-labels set the **appearance model only**
(colour, line, hatch), never geometry, and the score always comes from independently traced
windows on the target sheet.

## Using today's HCMC layers

The 2023 government vector data (river, water edge, road surface, kerbs, centrelines; 2.1M
buildings) sits in `~/Work/Projects/hcmc-buildings/`, EPSG:4326, licence unresolved. It is
warped through each sheet's georeference (1882: 8 GCPs, 11.5 m RMS ≈ 34 px; 1898: 9 GCPs, 8.4 m
≈ 25 px) by `work/image-processing/experiments/modern-overlays/`. `modern_prior.py` already did this for blocks in
September and recorded that modern buildings give ~1,100 false seeds per real one, so only the
*structure that persisted* is worth using. What a first look at 16 windows says:

| Layer | Use it as | Do not use it as | Evidence |
|---|---|---|---|
| River polygon, eroded 60 px | **Positive water seed** for the appearance model, on both sheets | A mask | Covers the hand-checked water cores 100% (1882) and 96% (1898), and 0% of four dry boxes. Six boxes, so precision is shown but recall is not. |
| Water-edge line | A weak hint where the bank is, to be re-found on the ink | Truth: reclaimed banks (Arroyo Chinois east bank) and filled canals (1898 top-left) are gone | Visual, 6 windows: open-river banks land within tens of px; Chinois and the canal do not. |
| Road centreline / kerb | A **search corridor** and junction anchors for road | A road surface | Visual: kerbs trace printed streets but sit ~one street-width off (34 px against 10–20 m streets, 30–60 px). |
| Road-surface complement | The existing block prior (`--blocks-from-roads`) | Block truth: 0.262 `land_plot` IoU against the colour pass's 0.343 | Re-run 2026-10-01 on the 24 `land_plot` traces: 1,171 blocks, mean 0.247, cover 0.84 (September: 1,184, 0.262, 0.87). Selected traces, not precision. |
| Modern buildings | Nothing; at most the 406 "survivors" | Seeds or negatives | They do not coincide with 1882 or 1898 footprints in any window looked at. |

**What seeds buy.** About 263,000 water-ink pixels on 1882 and 100,000 on 1898, a much larger
sample than the 200 × 200 hand boxes. They confirm the earlier hand-box result at that scale:
colour separates water from salmon-hatched land (AUC 0.99 on both sheets) but not from
blue-grey land (AUC 0.70 on 1882, and 0.25 on 1898, where water ink is *redder*). So a
seed-derived colour cut is a per-sheet calibration for free, but it cannot reject blue-grey
parcels; that still takes line direction and the old map's own negatives.
**Why not negatives.** Modern land is not safe: filled canals are roads now. Negatives for water
come from the old sheet (hatched blocks, traced dry windows), never from modern land.
**Not measured:** seed recall (how much old water the modern river misses), the road corridor
width, and anything on 1898 buildings. `modern_prior.py` cannot run as it stands: its paths point
at `~/Desktop/tasco/hcmc/*.gpkg`, which no longer exists; the data is now parquet.

## Order of work and the gates between them

| # | Step | Needs | Done when |
|---|---|---|---|
| 1 | Trace `river_ref` (19 windows), a second person on 3 windows | person | `reviewed: true` on all; inter-tracer shoreline distance recorded |
| 2 | Score existing mask, 0.09 trial and bank-aware proposal | step 1 | river table by case × sheet × split |
| 3 | Build `road_ref`, `block_ref`, `building_ref` windows with the same exporter and scorer | step 2 selection pattern | windows chosen *before* looking at proposals |
| 4 | Road, then block, then building, each gated | previous stage's layer as a prior | each gate above passes on held-out windows of both sheets |
| 5 | Review + approve layer | human | review log with corrections |

## Not doing yet

CycleGAN style translation, vision-transformer backbones, topology-preserving losses (the
benchmark found little gain), whole-sheet annotation, and training the LoRA on more traces
before an independent test set exists.

## Open decisions

- **Tracing tool.** QGIS with an engineering CRS, or a small canvas tracer. Decide before step 1.
- **Is the road centerline graph a deliverable?** It roughly doubles the road work. Check `walk-plan.md` and
  `street-name-pairs` for whether either needs it; I have not.
- **Where the layers go.** `footprints` with `feature_type`, or a staging table until approved.
- **ROADMAP.** Needs `road-reconstruction` and `building-reconstruction` items beside
  `river-reconstruction` and `colour-blocks`, plus their names moved in `knowledge-system-plan.md`
  §9. Not done here: that file has another session's uncommitted edits.
