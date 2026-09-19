# Where this work sits in the field

**Written 2026-09-19**, against `docs/image-processing-record.md`. That file says what we did; this
one holds it against published academic work and deployed industry systems, and says which of our
claims survive the comparison.

Every external number below was read from the paper or the competition page, not from memory. Where
a source could not be checked to the digit it says so.

---

## 0. The thing that blocks most comparisons

**Our segmentation numbers are not in a unit the field uses.** `seg_eval` reports *mean best-match
IoU per ground-truth polygon* — for each hand trace, the IoU of whichever prediction matched it
best. The literature reports one of two other things:

- **semantic IoU** — pixels predicted as class X against pixels labelled class X, over a held-out
  test set (MapSAM2, MapSAM, U-Net baselines);
- **COCO Panoptic Quality** — instance matching at IoU > 0.5, with false positives and false
  negatives each costing half a true positive (the SODUCO/MapSeg benchmark).

Both punish a prediction that matched nothing. Ours cannot see one. So **"colour blocks 0.331"
cannot be placed on the same axis as "MapSAM2 75.8"**, and any sentence that puts them in one table
without this paragraph is misleading. This is the same blocker `docs/image-processing-record.md` §5
item 1 already names, seen from outside: the missing precision number is also what makes us
un-comparable, not merely un-rigorous.

The cheap fix is known and is a tracing job: one exhaustively traced window gives precision, and
from a traced window both PQ and semantic IoU are computable from what `seg_eval --window` already
holds.

---

## 1. Segmentation of map features

| system | data it needs | metric | result |
|---|---|---|---|
| **MapSAM2** (Xia et al. 2025) | 10-shot | semantic IoU | **75.8** on ICDAR 2021 building blocks; vineyard 67.6; railway 73.0 |
| MapSAM (Xia et al. 2025) | 10-shot | semantic IoU | 71.1 building block · 60.0 vineyard · 78.5 railway |
| SAMed | 10-shot | semantic IoU | 70.3 · 61.5 · 75.4 |
| U-Net, domain-specific | 10-shot | semantic IoU | 60.0 · 60.2 · 61.4 |
| U-Net, full training | 5,872 railway images | semantic IoU | 91.9 railway · 77.0 vineyard |
| **SODUCO / MapSeg** (Chen et al. 2024) | 8,362 annotated polygons | COCO PQ | **51.1%** (U-Net + Meyer watershed + joint opt + augmentation); ViT 40.1% |
| **Semap / EPFL** (Petitpierre) | 1,439 annotated samples | mIoU | supervised HRNet/OCRNet family, heterogeneous collections |
| **VMA colour blocks** | **nothing — no training set** | best-match IoU, no precision | land_plot 0.331 · building 0.355 after the split, on 46 traces, one sheet |

Four things follow, and they are not all bad news.

**We are two orders of magnitude short on annotation.** 46 polygons on one sheet against 8,362
(Chen), 1,439 (Semap), 5,872 images (Siegfried railway). Our LoRA was fine-tuned on 46 traces and
scored against those same 46 — the field would call that a train-set score and not publish it, which
is exactly what `EVAL-BASELINE.md` already says about itself.

**But 46 traces is roughly the regime MapSAM2 is built for.** Its headline is *10-shot*. On the
ICDAR 2021 building-block set — city blocks on a historical city map, the closest published task to
ours — 10 annotated examples buy 75.8 semantic IoU. We have four times that many traces and have
never computed a semantic IoU. **That is the single most informative missing number in the repo**:
it is computable today from the existing 46 traces on a held-out region, it is the unit the field
reports, and it would tell us whether our pipeline is roughly at the published state of the art or
far below it. Right now nobody, us included, knows which.

**Memory attention, verified.** `docs/pipelines.md` says MapSAM2 measures memory attention alone at
+14.3% IoU on vineyards and +16.1% on railways. Checked against Table 2 of the paper: vineyard
10-shot 67.6 with, 53.3 without; railway 10-shot 73.0 with, 56.7 without. The repo's reading is
correct. Our `inference_tiles_as_video.py` still runs SAM2's default FIFO memory, so **we have
shipped the tiles-as-video shape and none of the mechanism that produces the paper's gain** — the
repo says this too, and the external check confirms the gain is worth the work: on areal features it
is the largest single effect in that paper, and areal features are what a cadastral sheet is made
of. It is also strongest in the low-data regime, which is ours.

**Where we are not behind, and it is the interesting part.** Chen et al. name their benchmark's
binding constraint explicitly: historical maps have *"limited colour and texture"*, which is what
pushes the Paris-atlas work to edge filtering plus watershed. That is a property of the Paris
atlases, not of historical maps in general. **A polychrome French colonial cadastral is the opposite
case** — the sheet carries a printed colour convention (cream parcels, salmon *propriétés
particulières*, green, blue) with a legend that defines it, and our within-parcel split works
because a building is drawn redder than the parcel it stands in. The current literature has no
equivalent pass: the supervised work does not need one, and the classical pre-deep-learning colour
segmentation it would descend from predates the benchmarks. A self-calibrating colour prior —
thresholds voted from the sheet's own histogram, an area band in metres, trained on nothing — is
plausibly novel **as a method for polychrome cadastrals specifically**, and that qualifier is the
whole claim. It needs precision and two more sheets before it is one.

---

## 2. Map text

| system | scale | approach |
|---|---|---|
| **mapKurator / Machines Reading Maps** | **60,000+ maps, 100M+ text labels**, ~57,000 georeferenced maps processed; deployed as *Search by Text-on-Maps* on David Rumsey | trained text spotters, patch-based, post-processing, geocoordinate conversion, gazetteer linking |
| **ICDAR 2025 MapText** | 7 teams, 25+ submissions, 4 tasks, 3 datasets — Rumsey, expanded French Land Registers, **new Taiwanese with Chinese characters** | competition; detection strong, **recognition and linking still hard** |
| **LIGHT** (Lin, Olson, Wu, Chiang, Weinman 2025) | ICDAR 2024/2025 data | multi-modal text linking, bi-directional reading order |
| **GPT-4o legend detection** (GeoSearch'25) | 40 DARPA–USGS maps | **in-context learning, no training** — 88% F1, 85% IoU, beats a LayoutLMv3 baseline; best at 15 in-prompt examples |
| **VMA** | **6 sheets, 958 distinct place names**, 43 human-checked | Gemini Flash, coarse→fine tiling, row-sequence, two-pass vote |

**On scale we are not in the conversation**, and should never imply otherwise. mapKurator has
processed four orders of magnitude more maps than we have.

**On method we are not behind, and the field is moving our way.** The GPT-4o legend paper is the
clearest evidence: a general VLM with in-context examples and *no training* beat a trained layout
model on a map task, published November 2025. That is the same bet as `--mode prompted
--ocr-run-id` and the Gemini layout pass. Our reason for the bet — open vocabulary, several
categories per call, and the text *and* the box from one call, so OCR and prompt generation are the
same pass — is stated in `docs/pipelines.md` and is now externally corroborated rather than merely
plausible.

**Two results we appear to hold alone:**

1. **Ground per call.** What starves a VLM read is one call covering too much ground, and a fixed
   pixel tile is a different amount of ground on every sheet (2,048 px is 1.7 km on the 1923 sheet,
   5.7 km on the 1959 one). Measured: 5.7 km/call → 1 label, 2.9 km → 2, 1.4 km → 6; +19% across a
   six-sheet collection; rendering above 1:1 is byte-identical. The map-text literature works in
   **pixels**, because a trained detector has a fixed receptive field and the question does not
   arise. For a VLM it is the binding variable. I found nothing stating this.
2. **Diacritic retention as a metric.** Our own measurement is that retention varies 9%–100% *by
   run, not by sheet*, on the same sheets — the single biggest quality lever we have, and one no
   standard metric captures. ICDAR MapText covers Latin, French and now Chinese; character accuracy
   and edit distance are the reported units. For Vietnamese, `CHÂTEAU` vs `CHATEAU` is a small edit
   distance and a wrong place name. A diacritic-retention metric on a diacritic-heavy corpus is a
   short, citable methods contribution.

**And one caution.** Our own Gemini-as-segmenter experiment found the model's `box_2d` is x-first
rather than the documented y-first (mean IoU 0.909 vs 0.284 over 240 objects) and its `mask` is
image-normalised rather than box-relative. Both are silent failures that read as a weak model. Any
VLM-on-maps comparison, ours or anyone's, is worth nothing until that calibration is checked — worth
saying in print, because the GPT-4o legend paper's pipeline has the same exposure.

---

## 3. Georeferencing

| route | what it needs | reported accuracy |
|---|---|---|
| **Feature matching** (Jerusalem, CaGIS 2025) | an already-georeferenced map of the same place | SuperPoint + SuperGlue + Delaunay consistency; **RMSE < 1% of map diagonal on 71 of 86 maps** |
| **Printed graticule + LLM** (Tyagi & Dubey, NCVPRIPG 2025) | printed lat/long labels in the margin | EasyOCR + two-stage multimodal LLM; **internal RMSE < 5 m, validation < 30 m on 11 of 12 sheets**, < 350 s/sheet |
| **Toponym matching** (Bahgat & Runfola 2021) | a gazetteer and ≥ ~10 toponyms | usable for data extraction in nearly half of cases; affine RMSE elsewhere reported 16.9–84.2 px, i.e. sometimes too imprecise |
| **Content-based** (Luft & Schiewe 2021) | topographic content | — |
| **VMA** | **a human** | Allmaps helmert, 10 GCPs, **RMSE 11.3 m** on the 1882 sheet; affine buys 10.6 m |

**We do no automatic georeferencing at all.** Our 11.3 m is a human result and belongs in the
ground-truth column, not the results column.

The useful finding is *why the two working automatic routes do not transfer to this corpus*:

- feature matching needs a georeferenced map of the same place in a comparable style — for Saigon
  1882 there is none, which is the whole reason the archive exists;
- the graticule route needs printed lat/long in the margin, which a colonial city cadastral usually
  does not carry (the Survey of India 1:50k sheets it was demonstrated on do).

That leaves toponyms, which is exactly the route `docs/private/260912-postgrad-route.md` already
outlined, and the reported weakness of toponym georeferencing (RMSE too large on some sheets) is the
open question our corpus is unusually well placed to answer, because we hold **human GCPs, VLM
toponyms and a gazetteer on the same 39 sheets**. That combination is what Bahgat & Runfola asked
for in print. The blocker is unchanged and is not research: toponyms on all 39 sheets rather than 6.

One reporting fix to adopt: the field states georeferencing error as **a percentage of map
diagonal**, not in metres. Our 11.3 m on a 4.14 × 3.09 km sheet is ~0.22% of the diagonal. Quote
both.

---

## 4. Infrastructure, and the part that is closer to industry than to papers

| | them | us |
|---|---|---|
| **Allmaps** | IIIF Georeference Extension; annotations CC0, published daily as an open dataset; formal IIIF partnership 2026–28 | we are a consumer of exactly this standard, and our sheets' annotations live in it |
| **Esri ArcGIS Pro** | pretrained OCR + map-simplification models in Living Atlas; workflow explicitly *requires human intervention*; as of 2025 map digitization is **not** fully automated and few products claim map vectorization | our propose-then-accept HITL is the same bet, built openly |
| **Kartta Labs** (Google) | open-source, open-data historical map organisation | adjacent; not a segmentation competitor |
| **mapKurator deployment** | text output folded into a library discovery platform (Luna) as searchable metadata | our `/explore` label layer is the same product idea at 1/10,000 the scale |

Two things we have that the papers mostly do not, because papers do not have to operate:

- **The eval harness reads its ground truth from the human review queue.** No separate labelling
  step exists; a reviewer's verdict is the test set. This is efficient and it has one specific
  failure mode, which we hit: 72 machine-written rows sat in the same table and voided every
  `n=89` figure until they were found by rendering an overlay. *A table a pipeline writes into is
  not a ground truth.* That is a short, genuinely useful methods note for anyone building a HITL
  digitization loop, and I found no paper stating it.
- **Provenance and staleness as first-class.** Run pinning on both sides of the join, `geom_src` as
  a hash of the GCP set so a stale row is queryable, cost per call logged with thinking tokens, and
  the planned I5 rebuild-set tracking. The ROADMAP's "map image-processing system" items (I1–I6) are
  an operations agenda, not a research one, and they are the right response to the four defects in
  `docs/worked-example-1882.md`.

---

## 5. Corpus — the clearest gap in the field, and our strongest asset

ICDAR MapText's three datasets are Rumsey (US/English), the French Land Registers, and as of 2025 a
Taiwanese set with Chinese characters. The segmentation benchmarks are Paris (SODUCO), Swiss
Siegfried (ETH/MapSAM), and European cadastres (Semap). **No Vietnamese, and no French-colonial
Indochina corpus, in any of them.** A general web search for a Vietnamese historical-map OCR dataset
returns our own site.

So the defensible corpus claims are:

- a French + Vietnamese, two-regime toponymy with diacritics, on sheets 1791–1968, georeferenced
  with human GCPs — a script and a colonial context the map-text field has not processed;
- the **Indian 1960 → WGS 84 silent-failure trap** found in L7014 (~470 m, found by seams), which
  is a short citable methods note by itself and which nobody appears to have published;
- the ground-per-call result, which is about VLM map reading generally and not about Vietnam at all.

---

## 6. Verdict, by axis

| axis | standing | what would change it |
|---|---|---|
| Segmentation **rigour** | **behind** — no precision, no held-out set, train-set scores, one sheet | one exhaustively traced window; then report PQ or semantic IoU |
| Segmentation **method** | **plausibly novel for polychrome cadastrals**, unproven | the same traced window, plus two sheets from other decades |
| SAM2 usage | **behind the paper we forked** — tiles-as-video shape without the self-sorting memory bank | implement it; the paper measures +14.3/+16.1 IoU for exactly this, strongest in low-data |
| Map text **scale** | **not in the conversation** (6 sheets vs 60,000 maps) | nothing cheap; do not claim scale |
| Map text **method** | **level with the field's direction**, corroborated by the GPT-4o legend result | — |
| Ground per call | **appears to be ours alone**, and is transferable | write it up; it is 1–2 pages and already measured |
| Diacritic retention metric | **appears to be ours alone** | ditto, and it needs the 39-sheet OCR pass |
| Georeferencing | **not competing** — we use humans | the toponym paper already outlined; needs 39 sheets of toponyms |
| HITL infrastructure | **ahead of the papers, level with industry practice** | the contamination note is publishable as-is |
| Corpus | **unique**, and the least contested claim we have | mint the Zenodo record |

**The one-sentence read:** *our methods are current and in one or two places ahead; our measurement
is not, and the measurement gap is a tracing job rather than a research problem.*

---

## 7. Corrections this comparison turned up in our own docs

- **`docs/pipelines.md:1240` cites a "SODUCO F1=0.59 baseline" in the `evaluate.py` command
  comment.** I could not trace that figure. The published SODUCO/MapSeg benchmark (Chen et al.
  2024, PLOS ONE) reports **51.1% COCO PQ** as its best pipeline, a different metric entirely.
  Either source the 0.59 or drop it — it is currently a number in a command line that a reader
  would take as a target.
- **The MapSAM2 memory-attention figures in the same file check out** (+14.3 vineyard, +16.1
  railway, both 10-shot). The "+12.8% F1 for prompt quality" claim attributed to the same paper was
  **not** verified in this pass; it may come from MapSAM (2025) rather than MapSAM2. Flag before
  quoting externally.
- **Report georeference error as a percentage of map diagonal as well as in metres**, since that is
  the field's unit.

---

## Sources

- [MapSAM2: Adapting SAM2 for Automatic Segmentation of Historical Map Images and Time Series](https://arxiv.org/abs/2510.27547) — Xia, Balestriero, Zhang, Zhou, Ding, Saini, Hurni, Oct 2025 ([IEEE version](https://ieeexplore.ieee.org/document/11457033/))
- [Automatic vectorization of historical maps: A benchmark](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0298217) — Chen et al., PLOS ONE 2024 (SODUCO/MapSeg) · [code](https://github.com/soduco/Benchmark_historical_map_vectorization)
- [The mapKurator System](https://dl.acm.org/doi/10.1145/3589132.3625579) — ACM SIGSPATIAL 2023 · [Text on Maps at David Rumsey](https://machines-reading-maps.github.io/rumsey/) · [Turing Institute announcement](https://www.turing.ac.uk/news/new-collaboration-promises-enrich-data-60000-historical-maps)
- [ICDAR 2025 Competition on Historical Map Text Detection, Recognition, and Linking](https://link.springer.com/chapter/10.1007/978-3-032-04630-7_33) · [results](https://rrc.cvc.uab.es/?ch=32)
- [LIGHT: Multi-modal Text Linking on Historical Maps](https://link.springer.com/chapter/10.1007/978-3-032-04617-8_4) — Lin, Olson, Wu, Chiang, Weinman 2025
- [Detecting Legend Items on Historical Maps Using GPT-4o with In-Context Learning](https://arxiv.org/pdf/2510.08385) — GeoSearch'25
- [Georeferencing historical maps using local feature matching and Delaunay consistency](https://www.tandfonline.com/doi/full/10.1080/15230406.2025.2566789) — CaGIS 2025 (Jerusalem, 86 maps)
- [Automated Georeferencing of Topographic Maps via OCR and In-Context Multimodal LLM Reasoning](https://link.springer.com/chapter/10.1007/978-3-032-08511-5_8) — Tyagi & Dubey, NCVPRIPG 2025
- [Automatic content-based georeferencing of historical topographic maps](https://onlinelibrary.wiley.com/doi/full/10.1111/tgis.12794) — Luft & Schiewe, Transactions in GIS 2021
- [Effective annotation for the automatic vectorization of cadastral maps](https://academic.oup.com/dsh/article/38/3/1227/7074303) — Petitpierre & Guhennec, DSH 2023 · [Semap dataset](https://zenodo.org/records/19048095) · [Generalizable Multiscale Segmentation of Heterogeneous Map Collections](https://infoscience.epfl.ch/server/api/core/bitstreams/bcf0ca8b-d9d6-45c8-a02f-e83cb8d72e89/content)
- [Allmaps](https://allmaps.org/) · [IIIF Georeference Extension](https://iiif.io/api/extension/georef/) · [Allmaps–IIIF partnership 2026–28](https://allmaps.org/iiif-partnership/)
- [Digitizing scanned maps using AI in ArcGIS Pro](https://www.esri.com/arcgis-blog/products/arcgis-pro/mapping/digitizing-scanned-maps-using-ai-in-arcgis-pro) · [Digitization of Historical Maps in the Age of AI](https://dlab.berkeley.edu/news/digitization-historical-maps-age-ai) (Berkeley D-Lab, 2025)
- [Kartta Labs](https://dl.acm.org/doi/10.1145/3356471.3365236) — ACM SIGSPATIAL workshop 2019
