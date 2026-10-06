# Framework landscape: where the VMA pipeline sits

**Written 2026-10-05.** An engineering and research record, not a pitch. It holds the nine-step
framework (find, credibility, record, georeference, layout scout, ground-distance tiling, VLM OCR
with review, footprints, link into a knowledge graph) against published work and deployed systems,
and says stage by stage how well each choice is supported.

**Evidence tags.** Every external claim carries one, and the References section lists each source
with its tag.

| tag | meaning |
|---|---|
| **V** | I opened the page, abstract or Crossref record this session and the statement is from it |
| **P** | previously verified in `docs/paper/related-work.md` (read in full there); not re-opened |
| **S** | seen only as a search-result excerpt; the page was not opened or was blocked. Treat as a lead |
| **F** | taken from `docs/research/field-comparison.md`, not re-verified |
| **R** | read in this repo, with the file and date |
| **A** | added or re-checked by the 2026-10-05 audit (see the Audit section at the end); where an A tag disagrees with an earlier tag, A wins |

"Preprint" means arXiv or a project site with no peer review. Crossref records for eight DOI-bearing
papers (Sun 2020, Shbita 2020, Cura 2018, MapSAM 2025, PeGazUs 2024, ICDAR 2024 MapText, MapReader
ACM 2022, Venice dataset 2025) carried no correction or retraction field. That is the only
retraction screen I ran; the scite tools were not used.

## Summary

1. **The pipeline is a competent integration of well-chosen parts, not a new architecture.** Each stage
   has a published counterpart. The order is the standard one in the document-AI and map-text literature,
   with the VLM-for-OCR and layout-by-prompt choices current rather than behind (Kirsanova 2025 [P],
   Greif 2025 [V]).
2. **The linkage-and-knowledge-graph thesis is not a literature gap, but the support is narrower than
   first written (audited 2026-10-05).** The `related-work.md` verdict
   (the lattice-as-evaluation-set claim does not survive) was about the georeferencing-QA paper. I
   tested the broader linkage thesis separately. The direct prior art is **Sun et al. 2020** (IJGIS;
   aligning entities across historical map editions as a step toward a geographic knowledge graph, average
   F-score 0.89 on two datasets of three maps each, vectorised by hand and without georeferences; the
   graph itself is not built in the paper) and **Shbita et al. 2020** (spatio-temporal KGs built from
   vectorised USGS railroad and wetland features across editions; a different entity type, not place-name
   linkage). Adjacent, not direct: Xia et al. 2024 (building-instance alignment across editions by video
   instance segmentation; no KG), Wu et al. 2026 (dense raster alignment, object detection and change
   profiling for Paris 1868-1937; no entity linkage and no KG in the abstract), Liu, Wu & Hurni 2025 (a
   spatio-temporal KG from historical map data used for question answering), and the SoDUCo/LASTIG line
   (Cura 2018 gazetteers of geohistorical objects from maps; PeGazUs 2024 KG of addresses and plots in one
   Paris district). "Maps never match, so treat disagreement as data" has two close precedents:
   **Vaienti's 2025 EPFL thesis** (errors and deformation used as evidence of copying lineage among
   Jerusalem maps; read from her page, not the thesis) and **Kitamoto & Nishimura's "data criticism"**
   (2013 two-page abstract: quantify a map's error before using it as a source). Jenny & Hurni 2011 is
   weaker support: it compares one old map against a modern reference and says the result informs the
   map's history, not that disagreement between maps is data. None of these is a bilingual,
   rename-aware, cross-edition link of OCR'd labels on a colonial Indochina corpus; nothing here shows
   such work does not exist elsewhere.
3. **What the repo has that the literature, as far as I found, does not:** a Vietnamese/French-colonial
   corpus; a legend-timeline match across a language change; a 1882-rooted name registration; the
   index-agreement gate (a sheet's own printed street index as free ground truth); ground-distance
   tiling for VLM calls; a documented catalogue of silent failures. Most rest on one or two sheets.
4. **Linkage is the weakest stage by the repo's own numbers**: 8 labels link to a polygon (`ocr_labels.footprint_id`;
   A: reproduced 2026-10-05 as 8 of the 10,574 labels the public key can read, on 22 maps; the recorded
   denominator of 14,506 in `knowledge-system-plan.md` is historical; the service-role follow-up
   counted 8 of 15,133 rows on 24 maps at 15:43 UTC, including rejected and legend rows),
   there is no entity table, no legend link, and no precision/recall for any cross-map match.
5. **The credibility-check step is not implemented.** `scout_candidates` stores scraped provenance fields
   (source, external id, creator, publisher, date, rights, holding institution, raw payload), a keyword
   relevance `score` and a pending/approved/rejected review status with a note. It has no assessment
   fields: nothing on creator competence, survey method, printing or copying, and no code applies such a
   test (A: schema and a repo-wide search checked). The framework order is also circular for
   the cartometric half of credibility, which needs a georeference first.
6. **Georeferencing as a choice is well supported (Allmaps, W3C Web Annotation, IIIF); its quality
   control is the gap that matters.** Per `related-work.md` §6.3 (2026-09-19), human-placed RMSE across the
   archive runs up to 1,415.9 m (A: the 1909 Thua-thien sheet, 4 GCPs, in `work/analysis/georef_coverage.md`;
   the 9.0 m minimum is also recorded for 1968 in `work/analysis/district4/georef_error.md`), and 65.0%
   (8,796 of 13,525 rows at that date) sat on a sheet whose stated limit was bad or absent. Those figures
   predate the 2026-10-01 re-fits and the row total has since changed, so treat 65.0% as a dated figure that
   was not re-derived. Placement uncertainty affects linkage; fitted-GCP residuals alone do not
   establish an upper bound on positional error or an achievable linkage score.
7. **Evaluation is thin.** The original OCR benchmark is 43 validated labels on the 1882 sheet, but that
   is stale as a current figure: `EVAL-BASELINE.md` itself records the ground truth doubling to 85 rows,
   and the public database now shows 91 validated labels on that sheet, 90 outside the legend category (A, 2026-10-05, all runs combined). Validated
   map labels also exist on 1799 (22) and 1895 (8); the 1898 sheet, the other half of the proposed linkage
   test, has none. The ground-per-call result rests on one sheet and single-digit counts.

## 1. What the system contributes

### 1a. Engineering integration (solid, and mostly not publishable as such)

Allmaps editing and storage, IIIF tiles on R2, a job queue with a keyed worker, VLM calls with context
caching and key rotation, a review UI that writes the ground truth, per-row `run_id`, `geom_src` hashing
of the control-point set so stale derived geometry is queryable, cost logged per call. The integration is
the project's real asset and its defects are well documented (`docs/lessons.md`: the gate green over a
broken thing, a refused probe read as "no", a 31.8% white-hole overview scored 7/7). Systems with the same
shape exist: MapReader (patch classification and text spotting, ~16,000 Ordnance Survey sheets, ~30.5M
patches [V]) and mapKurator (60,000+ maps, 100M+ labels [V]). VMA is smaller by orders of magnitude.

### 1b. Methods

| item | evidence in repo | what I found outside | status |
|---|---|---|---|
| Ground-distance tiling for VLM calls | 1959 sheet: 5.7 km per call found 1 label, 2.9 km found 2, 1.4 km found 6 (5 on repeat); +19% across six sheets; run-to-run spread of one label (R, `digitalize-guide.md`, `pipelines.md`) | The map-text work I read is stated in pixels (PALETTE, MapText [V]). No paper stating this effect for VLMs found; the search was not exhaustive | n = 1 sheet, counts in single digits: a lead, not a result |
| Index-agreement gate | 1959: name_recall 0.7947 (298/375), agreement 0.9434 (R). 1968: 0.0245 (9 of 367) before any body pass (R, `pipelines.md`), then 0.3270 (120/367), agreement 0.9603, after the first body pass (R, `EVAL-BASELINE.md` 2026-09-10). Two runs, not a disagreement | Four searches found no paper using a sheet's own printed index as recall ground truth. Weinman 2013 aligns recognised toponyms to an external gazetteer [S], which is a different use | Two sheets. Plausibly a defensible small method; needs more sheets with printed indexes |
| Legend-timeline matching across a French-to-Vietnamese rename | (canonical type, folded proper name) key plus a ~27-word lexicon: 602 entries to 447 threads, 85 on more than one sheet, 12 reaching the 1959 legend (R, `pipelines.md`) | Cross-edition entity alignment uses string, spatial and topological cues (Sun 2020 [V]); a bilingual rename key is not in what I opened. Kitamoto & Nishimura's ruins case (one site recorded under different names and types across expedition and survey reports, linked by hand) is a manual precedent for rename-aware identity [A] | No precision or recall. Counts only |
| Name-based sheet registration | 50 shared unique names, 35 inliers, 25.1 m from names alone, 16.1 m after ICP; two routes to the 1898 georeference differ by median 48 m, max 117 m (R, `260921-sheet-overlap.md`, 2026-09-21; **measured against the 1898 georeference that had 3 control points (`docs/journals/260921-sheet-overlap.md`) and was re-fitted to 9 control points by 2026-10-01** per `knowledge-system-plan.md` §4 and `docs/journals/261002-colour-eda-1882-1898.md`; A: the repo confirms the 3-to-9 change but 2026-10-01 is the date the stale derived geometry was found and re-warped, not necessarily the day of the re-fit. These figures need re-running) | Pope & Frean 2025 georeference against cadastral line intersections [S]; Vaienti 2025 uses feature matching [P] | One pair of sheets, and the script is kept as a cross-check, not the production route |
| Silent-failure taxonomy (datum fault, blind self-checks) | `claim-audit.md` rows, `related-work.md` headline | Luft & Schiewe 2021, Janata & Cajthaml 2020 [P] | Paper 1, already narrowed by its own audit |

### 1c. Research claims, and the test of the `related-work.md` verdict

`related-work.md` (2026-09-19) concluded that "nobody uses the series' own lattice as the evaluation
set" is false (Luft & Schiewe 2021; Janata & Cajthaml 2020; Uhl et al. 2018; Gede & Varga 2021 [P]).
**That verdict concerns Paper 1, the georeferencing self-check. It does not by itself test the
framework's central thesis, linkage across maps.** I tested both.

*Paper 1.* A short 2025-26 search for datum, seam and self-check blind spots found only papers already
in the file (Luft & Schiewe, Vaienti 2025 [P]) and nothing reporting a check that is blind because its
frame is shared. The narrowed claim in `claim-audit.md` still stands against what I could find. This
search was brief and does not establish absence.

*The linkage thesis.* As stated ("the value of the extractor is linkage across maps and other sources,
feeding a knowledge graph"), it does not survive:

- **Entity alignment across map editions, toward a KG.** Sun, Hu, Song & Zhu (IJGIS 2020): "a combination
  of measures based on string similarity, spatial distance, and approximate topological relation achieves
  the best performance with an average F-score of 0.89" [V, A: abstract and arXiv PDF read]. Scope, from
  the paper: two datasets of three maps each (Sanborn maps of Buffalo 1889, 1899, 1925; a campus set 1966,
  1982, 1990), entities vectorised with ArcScan plus manual editing, fewer than 30% of entities carry
  text labels, **neither dataset has georeferences**, code and datasets released. The abstract frames
  alignment as "one important step" of building a geographic knowledge graph; it does not build one.
  Shbita et al. (ESWC 2020; journal version in Semantic Web) convert vector features (railroads, wetlands)
  from multiple USGS editions into spatio-temporal KGs [V, A: journal-version page; GeoSPARQL querying
  comes from a reviewer summary on that page, not the abstract]. Xia et al. (NeurIPS 2024 workshop) treat
  building-instance alignment across editions as video instance segmentation, "a 24.9% improvement in AP
  and a 0.23 increase in F1 score compared to the model trained from scratch" [V, A]; no KG. Wu et al.
  (2026 preprint, Perret a co-author): "dense map alignment, multi-temporal object detection, and change
  profiling", applied to Paris 1868-1937 [V, A]. That is raster alignment and change measurement, not
  entity linkage, and no KG appears in the abstract. Liu, Wu & Hurni (2025 preprint) build a
  spatio-temporal KG from historical map data for question answering [V, A].
- **Maps into a perpetual gazetteer with sources.** Cura et al. 2018 (arXiv version marked "working
  paper") build gazetteers of "geohistorical objects extracted from historical topographical maps" and
  match historical addresses to them; the abstract lists "temporal aspect, semantic aspect, spatial
  precision, confidence in historical source" as uncertainties and matching criteria that "include several
  dimensions (fuzzy semantic, fuzzy temporal, scale, spatial precision ...)" [V, A: abstract]. The words
  "weighted" and "fuzzy string" in the earlier draft of this file are not in the abstract; the minimal
  object model (source, digitisation process, fuzzy date, geometry) is from a search excerpt [S].
  PeGazUs (EKAW 2024) builds a KG of addresses and land plots, applied to one Paris district (Butte aux
  Cailles) "for which a variety of contemporary and historical sources were used" [V, A: repository
  README]. The earlier "seven heterogeneous sources" and "factoid-to-facts" wording was not found in
  anything opened and is unverified. SoDUCo geocoded 144 Paris directories (1787-1914, about 23 million
  records) [V, A: DHQ article text] and evaluated geocoding by manual inspection and density ratios against
  atlases; over 98.5% of distinct addresses in the 1835 and 1890 directories were located [V]. The DHQ
  text also gives 172 extra-muros addresses, of which 40% were correct [V, A].
- **Map error and disagreement as evidence.** Kitamoto & Nishimura (JADH 2013, a two-page abstract)
  propose "data criticism", the quantitative evaluation of non-textual sources before use: they "quantified
  the distribution of errors" in Stein and Hedin Central Asian maps, and "revealed ... the original form"
  of a roughly 250-year-old Beijing map "by connecting 203 sheets" [V, A]. The 203 sheets are the
  reassembly of one map, not error measured across 203 sheets (corrected). The same abstract links ruins
  recorded under different names across expedition and survey reports, and their 2016 DH abstract
  proposes an evidence network (evidence, hypothesis, fact, reliability) in which a map-matching pin is an
  evidence node [V, A]. Jenny & Hurni (Computers & Graphics 35(2):402-411, 2011) transform modern
  control points into an old map's frame to analyse and visualise its planimetric and geodetic accuracy;
  they say this "can also provide valuable information to the map historian about the history of a
  particular map and its creation" [V, A: PDF read]. That is one map against a modern reference, so it is
  weak support for map-to-map disagreement as data. Vaienti (EPFL, defended 2025-12-05), thesis "A
  Genealogy of Jerusalem Maps (1810-1925)", studies "errors and biases, and how they can be used to
  discover historical information" and "Cartographic Stemmatology" from deformation similarity [V, A: her
  page only; the thesis text was not read]. This is the closest published statement of the idea.

**What survives** is narrower: (i) the corpus (I found no Vietnamese or French-colonial Indochina
benchmark; `field-comparison.md` §5 says the same [F]); (ii) a bilingual, rename-aware link key and a
legend-to-legend timeline; (iii) the claim that a VLM-first reading plus a review UI yields linkable
assertions with pixel provenance at low unit cost, which is an engineering claim until it is
measured; (iv) the documented failure catalogue. The "maps never match" thesis is better stated as a
design principle than a finding. The repo's one measurement of it (2026-09-21) put the 1882/1898 overlap
at ~50-100 m and attributed the floor to scan distortion (axis scales differing 1.5% and 2.79%) rather
than the transform (R, `260921-sheet-overlap.md`). **That measurement used a 3-point, exactly determined
affine for 1898, which had been re-fitted to 9 control points by 2026-10-01 (R; exact re-fit date unestablished). Treat the attribution as
unsettled until it is re-run on the new fit.** It does not yet separate cartographic style from distortion.

## 2. Comparison with established approaches

Criteria used, for the table and for §6: **(C1)** evidence on this corpus: n, held out or not, and the field's unit;
**(C2)** fit to the stated purpose, linkage with uncertainty carried; **(C3)** human and money cost;
**(C4)** auditability back to source pixels and run; **(C5)** whether a failure is loud or silent.
"Optimal" cannot be answered in the abstract; these are the criteria I could check.

| system | find / provenance | georeference | layout / text | footprints | linkage / KG | review | scale, evidence |
|---|---|---|---|---|---|---|---|
| **Allmaps** [V] | IIIF, any institution | Editor; Georeference Annotations on W3C Web Annotation; CC0 data | none | none | none | human editor | VMA consumes it |
| **Map Warper / NYPL** [V] | open source (T. Waters); used by NYPL, Harvard, Stanford, Leiden Archives | crowd, GCP | none | none | NYC Space/Time Directory ETLs [V, limited] | crowd | Building Inspector crowdsources footprint checking and fixing [S] |
| **Georeferencer (Klokan) / Old Maps Online** [S] | library partners | crowd, 3+ points | none | none | portal search | crowd | a Romanian batch of 1,800 sheets in under two days [S] |
| **Rumsey georeferencer** [V] | Rumsey collection | crowd, 3+ points, clip lines | mapKurator text layer [P] | none | none | crowd | pilot of 6,000 maps [V] |
| **MapReader** [V] | patch pipeline from web servers | n/a | patch classification, text spotting | patch labels | no cross-map link | annotate patches | ~16k sheets, 62k annotated patches [V] |
| **mapKurator / PALETTE** [P][V] | Rumsey | uses existing georef | trained spotter, linking to RDF/Wikidata [V] | none | linked geo-metadata, RDF [V] | n/a | 60,000+ maps, 100M+ labels; MapText: recognition and linking "still hard" [P] |
| **SoDUCo / LASTIG** [V] | archive sources | semi-automatic | directories OCR + NER + geocoding | vectorisation | PeGazUs KG, genealogy of plots [V] | HITL tools | 144 directories, ~23M records [S] |
| **ETH IKG (Hurni)** [V] | Swiss maps | n/a | n/a | MapSAM, MapSAM2 (10-shot) | alignment, KG GeoQA [V] | n/a | Siegfried time series |
| **Venice Time Machine** [V] | EPFL, Ca' Foscari, State Archive | cadaster georeferenced | HTR of registers | parcels | 20,000+ parcels linked to 12,277 disambiguated owner entities via 9,312 merges, with a published merge log [V, dataset paper] | semi-automated + manual | 2019 suspension: licensing and protocol gaps, plus a disputed provenance-metadata claim (§5) |
| **Linked Places, WHG, Pelagios, Recogito** [V] | attestation with citation | n/a | n/a | n/a | place attestations, temporal scoping | annotation | standards, not pipelines |
| **OpenHistoricalMap, Wikidata** [V] | volunteer | trace from georeferenced maps | n/a | vector with start/end dates | `wikidata=` cross-reference | volunteer | sparse coverage as of 2024 [V] |
| **Vietnam / SE Asia** | Virtual Saigon: 559 map documents, rich metadata, no georeferencing stated on the page [V]; HCMGIS GeoReference: user-driven image georeferencing service [V]; Historical Maps of SE Asia (Yale-NUS, Leiden, NLB, Bodleian, Beinecke; 1,400+ maps pre-1900, georeference tool) [S]; Hanoi: GIS of scanned maps called "a rough picture" by its authors (Duan & Shibayama, Kyoto CSEAS) [V] | | | | | | I found no Vietnamese text-spotting or linkage effort |
| **VMA** [R] | 1,067 scout candidates with provenance and relevance score (R, `knowledge-system-plan.md`; the public key cannot read this staff-only table) | Allmaps; rechecked 2026-10-05: 1882 12.3 m similarity RMSE on 8 GCPs; 1942 26.5 m affine RMSE (declared model), 33.6 m comparison similarity RMSE, on 8 GCPs (follow-up record) | Gemini VLM, two-pass vote, review | colour blocks; MapSAM2 fork | 8 label-to-polygon links among 15,133 service-role-visible OCR rows on 24 maps at 15:43 UTC (follow-up; historical total 14,506); no entity table | owner-reviewed | OCR rows on 24 maps; 499 validated rows in the service-role follow-up (includes legend entries); earlier public-key audit: 492 validated on 22 maps |

**Document AI.** For clean print, modern tools converge: ~0.6% CER, with early-modern print at
2.15-10.03% depending on tool, in a July 2026 working paper that is not peer reviewed [V, Clifford et
al.]. A multimodal LLM beat conventional OCR on German city directories 1754-1870 and reached under 1% CER
after post-correction (preprint) [V, Greif et al.]. Both are text pages; map labels are rotated,
scattered and curved. For maps the comparable evidence is the ICDAR MapText competitions (44
submissions in 2024; Rumsey and French Land Registers) [V]. PALETTE targets long, rotated text and
trains on synthetic maps [V]. LIGHT builds text linking on LayoutLMv3 [V]. No head-to-head of a prompted
VLM against these on the same crops exists in what I found. VMA's own VLM numbers are on one sheet
(§4).

**Segmentation.** Low-data regimes are crowded: MapSAM (peer reviewed, GIScience & Remote Sensing 2025)
[V], MapSAM2 [V], SMOL-MapSeg (one labelled example) [V], linear probing (67.3% mean PQ on building
blocks, arXiv version) [V], Chen et al. at 51.1% PQ on 8,362 annotated polygons [P]. VMA's colour blocks
(0.331 land_plot, 0.355 building best-match IoU, 46 traces, no precision; `field-comparison.md` §1 [F, R])
are not in the field's unit.

## 3. Alternative architectures

| alternative | what it would change for VMA | cost | evidence |
|---|---|---|---|
| **Text-first** (spot all text, then derive layout from clusters and links; mapKurator style) | Drops the scout call and the accept-triage gate. Legend and index text would be read like the rest and filtered later | Pays full tile cost on legends; VMA found local layout detection found 0 of 17 legend and index boxes on nine sheets, while the VLM scout costs ~$0.009 a sheet (R) | Layout-first is supported by repo numbers. VLM scout itself checked on two sheets by eye (R) |
| **Active learning on the review queue** | Order review by uncertainty. VMA's `confidence` cannot do it: median 0.9, p90 = p99 = 1.0 (R, `pipelines.md`). The two-pass vote gives a free query-by-committee signal that is already computed | A day of work and an ordering experiment | Generic HITL literature only; I found no map-specific active-learning paper |
| **Probabilistic linkage** (Fellegi-Sunter: link / possible link / non-link with m and u weights [V]; Bayesian variants [S]) | Replaces the hard (type, folded name) key with weights. "Possible link" maps onto review. The georeference error enters as a spatial-gate width | Needs a labelled correspondence set VMA does not have | Sun et al. combine three cues [V]; none of these papers carries georeference error forward as far as I could see |
| **Graph-first, attestation-based** (factoid model [V], Linked Places, PLATO with CertaintyLevel [V], PeGazUs) | Make the reading the primary object and entities derived. VMA's `ocr_labels` already are source assertions with a pixel region; the missing layer is `subjects` and `claims` (planned, checklist unticked) | Schema, review burden, and the risk the plan already names (no universal node/edge table) | Strong fit in shape; no evidence yet on VMA data |
| **Cross-edition propagation** (age tracing: pseudo-labels from adjacent editions, mIoU 77.3% from one map [S]; Xia 2024 [V]) | Use the better-checked sheet (1882) to seed labels on 1898/1923. `sheet_register.py` is the geometric half | Small | Preprint-level evidence |
| **Cartographic genealogy** (Vaienti [V]) | Test whether 1882/1898 agreement is independent confirmation or copying before counting it as corroboration | A research project in itself | Jerusalem only. Whether the Saigon plans copy one another is **not known** |
| **Event-centric CRM/CRMinf** [V] | Model claims, premises and beliefs formally; `claim_evidence` supports/contradicts is a CRMinf-shaped idea | Heavy ontology; adopt as a mapping, not as storage | No VMA data |

## 4. Evaluation

**How the field measures.** Georeferencing: median error in metres (Luft & Schiewe, 101 m, 96% sheet
location [P]), percentage of map diagonal (Vaienti 2025, under 1% on 71 of 86 [P]), per-sheet precision of
modules with no metric error (Heitzler, MapEdge [P]). Text: ICDAR MapText detection, recognition and linking
tasks [V; I did not extract the metric definitions]. Legends: F1 and IoU (88% / 85% [P]). Segmentation:
semantic IoU and COCO Panoptic Quality [P][V]. Linkage: F-score (0.89 [V]), AP and F1 [V]. Geocoding:
coverage and manual inspection of outliers, where 40% of 172 addresses outside historical boundaries were
correct [V].

**What VMA has** (R unless noted):

| measure | value | n and design | trust |
|---|---|---|---|
| OCR recall, single pass | 0.7674 (33/43); char_acc 0.9808; mean IoU 0.7234 | 43 validated labels, one sheet (1882), run `v1b`. **Stale as a fraction:** `EVAL-BASELINE.md` records the ground truth later reaching 85 scorable rows (A) | precision 0.2276 is uninterpretable on a partial ground truth |
| OCR two-pass vote | 41/43; rescored on the 85-row set: 75/85 at IoU 0.5, text recall 77/85 (0.906) (A, `EVAL-BASELINE.md`) | same | same sheet; tuned on it |
| index-agreement | 1959: 0.7947 / 0.9434; 1968: 0.3270 / 0.9603 | two sheets | gate is free but needs a printed index |
| river, 1882 (blind points) | 96.5% [94-98] (279/289) | owner-labelled blind points, held-out and seen windows | single annotator; later versions rescored on spent points |
| road, 1882, frozen pass | 85.7% [83-88]; half of road points missed | 614 points, 5.5% are road | author: "not good enough to promote" |
| georeference | 12.7 m (1882 similarity, 10-GCP set), 10.6 m affine, `geom_rmse` 16.50 stored. 1898 was RMSE 0.0 from 3 GCPs by arithmetic; re-fitted 2026-10-01 to 9 GCPs, 8.4 m misfit (R) | per sheet | three figures for one sheet, now named; the 1882 and 1898 fits changed on 2026-10-01 |
| cross-map | 33 name pairs within 150 m, median 25 m (1882/1898, 2026-09-21, old 3-GCP 1898 fit) | one pair | upper bound, labels sit near features; to be re-run on the 9-GCP fit |

The "validated" rows are mostly whole-legend entries: `knowledge-system-plan.md` (2026-10-01) gives 118 validated
labels on 22 OCR'd maps; the public database on 2026-10-05 shows 492 validated rows on those 22 maps,
367 of them `legend_entry` (A; the two figures are not reconciled here). Validated rows outside the legend
categories sit on 1882 (90, plus one `legend`), 1799 (22) and 1895 (8), with a few street rows on 1959 and 1968;
`digitalize-guide.md` still says only 1882 and 1799 have real validated map labels, which is out of date
(A). The 1898 sheet has none. The harness had its own contamination: 72 machine rows sat in the
ground-truth table and voided every n = 89 figure until found (`EVAL-BASELINE.md`, 2026-09-18).

**Smallest credible evaluation VMA could run on its own sheets**

1. **Linkage set (the missing one).** In the 1882 ∩ 1898 overlap, draw a stratified random sample of ~200
   1882 labels; an annotator records for each: same entity on 1898 / absent / ambiguous, with the
   1898 label. Double-annotate 50 for agreement. Report precision and recall at fixed thresholds against
   three baselines: exact folded-string key, string plus georeference gate, and the Sun et al.
   combination. Report the gate width against the georeference error (the 2026-09-21 figure of ≥25 m predates the 1898 re-fit and must be re-measured).
2. **OCR on three sheets, double-labelled**, ~100 map labels each, from different decades and both
   languages; add diacritic recall; score single-pass, two-pass and, if code is available, a trained
   spotter on the same crops. The ICDAR'24 Rumsey and Land Register data are on Zenodo [S, seen in
   search results, not opened] and would give an out-of-domain row.
3. **Index-agreement on every sheet that prints an index** (7 of 39 published maps carried a `name_list`
   region in September; R).
4. **Segmentation**: the blind-point protocol exists; add one exhaustively traced window for precision so
   PQ and semantic IoU can be computed (`field-comparison.md` §0 [F]).
5. **Georeference**: report every sheet on one error measure plus percent of diagonal (done for 274 sheets;
   `related-work.md` §6.3).

## 5. Credibility and provenance

| framework | what it prescribes | VMA today |
|---|---|---|
| **InterPARES** [V, 2008 lecture slides] | trustworthiness = reliability (statement of fact; author competence, controls on creation), accuracy, authenticity (identity + integrity metadata) | Not used. `scout_candidates` (mig 045) holds scraped provenance (source, external id, creator, publisher, date, rights, holding institution, raw payload), a keyword relevance `score`, and a review status pending/approved/rejected/ingested with a `review_note` (A: schema read). No creator-competence, survey-method or process-control field, and no code that scores them |
| **RiC-O 1.1** [V], **LRM** [V], **DCRM(C)** [S] | RiC: record resources in context as linked data. LRM: Work, Expression, Manifestation, Item (adopted 2017). DCRM(C): cataloguing rules for rare maps | Series, cell, printing, map, scan (migs 105-106) are WEMI-shaped. I infer the mapping; the repo does not state it. Printings are "reviewed, never inferred" |
| **PROV-O** [V] | Entity, Activity, Agent | `run_id`, `model`, `prompt`, `reviewed_by` and the `geom_src` hash are Activity/Agent/Entity-shaped. A repo-wide search for PROV-O, CIDOC, Linked Places, Pelagios, Pleiades and GeoNames found no use; only `search-plan.md` names Wikidata, for street-name history |
| **Linked Places / PLATO** [V] | attestation with citation, temporal scoping, certainty level | `claims` and `claim_evidence` with `cited_value` snapshots are planned (`evidence-chain-plan.md`); no migration creates them as of migration 110 |
| **Data criticism** (Kitamoto) [V] | evidence, hypothesis, fact, reliability attributed to a scholar; quantified spatial accuracy of maps | Closest published match to the planned claims design. VMA's `georef_versions` (mig 103) names the error method |
| **Harley** [S] | maps are not neutral records; authorship and power belong in the description | Not represented (inferred) |

**Credibility has two halves, and the framework orders them wrongly for one.** Authenticity and
provenance (who made it, which printing, who holds it, what rights) come before georeferencing. Cartometric
reliability (how far the sheet departs from the ground, which MapAnalyst-style distortion analysis
measures [S]) needs a georeference, so it cannot be a gate before step 4. VMA has the second half in
pieces (per-sheet RMSE, seam checks); neither half is a recorded assessment on a catalogue row.

**A cautionary case.** The 2019 Venice Time Machine suspension (Nature, 2019-10-25, "Venice 'time machine'
project suspended amid data row" [V, A: read from the Nature PDF at media.nature.com]). The archive's
stated cause was that the 2014 non-binding memorandum "left out crucial details on the research
protocols", in particular the licence for researchers' use of the data. Separately, the archive's
director Gianni Penzo Doria claimed that "from the point of view of archival science, 'these files are
useless'" because digitisation did not follow InterPARES guidelines on recording provenance in each file's
metadata (the earlier draft of this file quoted him as saying "unusable"; the word is "useless").
EPFL's Frédéric Kaplan said the researchers did collect metadata, following the ICA's ISAD
guidelines and procedures set by the archive's own staff; a former archive director, Raffaele Santoro,
said it should be possible to add more metadata without redoing the scans. Nature reports these as
disputed claims. The Time Machine Organisation's statement says only that the collaboration was suspended
and the documents were handed to the archive [V]. The dispute shows that a partner can contest digitised
output on provenance-documentation grounds; it does not show that archival-standard conformance decided
the outcome, since licensing and protocol gaps were the stated cause. It says nothing about VMA's data.

## 6. Verdict, stage by stage

Legend: **supported** = published support plus adequate evidence here; **defensible** = reasonable
choice, thin or unmeasured evidence here; **gap** = missing or contradicted.

| stage | verdict | evidence |
|---|---|---|
| 1 Find source | defensible | `scout_candidates` 1,067 rows with provenance; peers are catalogues (Virtual Saigon 559 documents). No measure of discovery recall or selection bias |
| 2 Credibility check | **gap** | Not implemented. No assessment fields in the schema (scraped creator, publisher and date fields exist; competence, method and copying do not); cartometric half cannot precede georeferencing |
| 3 Record and provenance | defensible, shape well aligned | Run, model, reviewer, hash, rights present; verbatim rights, claims and PROV serialisation planned. Normalised rights lost provider wording (mig 096; R) |
| 4 Georeference (Allmaps) | choice **supported**, QA **gap** | W3C Web Annotation and IIIF [V]. Archive range up to 1,415.9 m (9.0 m is recorded for 1968 in the District 4 analysis); 35 of 274 unmeasurable; 65.0% of rows on bad or absent-limit sheets (`related-work.md` §6.3, 2026-09-19; recorded, not re-derived; the 1882, 1898, 1923 and 1942 fits were changed on 2026-10-01, so these figures predate them) |
| 5 Layout scout | defensible | VLM scout 8/8 and 7/7 by eye on two sheets; local detector 0 of 17. Literature uses LayoutLMv3 [P]; a prompted VLM is current but unmeasured |
| 6 Ground-distance tiling | defensible | One sheet, counts of 1, 2, 6. Mechanism is plausible; field works in pixels |
| 7 VLM OCR + review | defensible | 43-label ground truth on one sheet (since grown to 85-91 rows on that sheet, same sheet; A); no comparison with a trained spotter; cost $0.945 for the 1882 two-pass merge, with a 3.5-4× billed-token correction still unchecked against an invoice (R) |
| 8 Footprints | **gap** in rigour; method plausible | 46 traces, train-set scores, no precision; MapSAM2 shape shipped without the memory mechanism (R) |
| 9 Link into KG | **gap** | 8 labels have a polygon (of 15,133 current all-status rows; 14,506 historical); no label-to-legend link; polygon class on 934 of 1,519; no entity table; no linkage P/R. Literature has working baselines to compare against |

**Why these four things are not equal.** Linkage and credibility are gaps in *existence*. Segmentation
and georeference QA are gaps in *measurement*. The second kind is cheaper to close, and it blocks the
first: a linkage score is uninterpretable while the georeference error is unrecorded per sheet.

## Repository figures reconciled (2026-10-05)

Current read-only service-role counts and reproduction details are in
[`framework-audit-followup.md`](framework-audit-followup.md). Historical counts remain dated snapshots.

| quantity | interpretation |
|---|---|
| Catalogue | 274 all-status maps in September; 859 on October 1; 1,499 at 15:43 UTC October 5, including 1,038 published maps. The old snapshots cannot be reconstructed from current mutable rows |
| OCR coverage | 6 sheets / 43 checked is an early benchmark; 958 distinct names is untraced. 13,525 and 14,506 are historical row counts; the service-role follow-up reads 15,133 rows on 24 maps, including rejected and legend rows |
| 1882 error | 12.7 m similarity and 10.6 m affine were a 10-GCP set; current 8-GCP fit reproduces 12.3 m similarity. Stored `gcp-roundtrip-rms` is a different measure |
| 1942 error | Current 8-GCP fit: 26.5 m affine (declared model), 33.6 m comparison similarity; 72.3 m is historical, and the 112 m nine-point state remains prose-backed only |
| 1968 name_recall | 0.0245 baseline and 0.3270 body pass are different runs; `pipelines.md` now labels both |
| Two “118”s | Historical validated-row count and segmentation dataset size are unrelated. Segmentation had 46 traces + 72 model rows |
| Georeference versions | Migration 103 is applied; 604 rows on 591 maps. Four writers still need coverage. Migration history matches locally/remotely through 111 |
| Tyagi & Dubey | Unverified comparison figures remain excluded |

## References

Tags: V opened this session; P previously verified in `related-work.md`; S search excerpt only; F per
`field-comparison.md`. Project sites and blogs are marked W.

**Standards and platforms**
1. Allmaps. https://allmaps.org/ (V, W)
2. IIIF Consortium (2023). Georeference Extension published. https://iiif.io/news/2023/05/15/georef-extension-published/ (V)
3. W3C. Web Annotation Data Model. https://www.w3.org/TR/annotation-model/ (V)
4. W3C. PROV-O. https://www.w3.org/TR/prov-o/ (V)
5. CIDOC CRM. https://cidoc-crm.org/ ; CRMinf https://cidoc-crm.org/crminf/ (V)
6. RiC-O. https://ica-egad.github.io/RiC-O/about.html (V); ICA RiC https://www.ica.org/ica-network/expert-groups/egad/records-in-contexts-ontology/ (S)
7. IFLA LRM. https://www.isko.org/cyclo/lrm (V, encyclopedia entry, tertiary)
8. DCRM(C). https://rbms.info/dcrm/dcrmc/ (S)
9. Linked Places format. https://github.com/LinkedPasts/linked-places-format (V, W)
10. Place Attestation Ontology (PLATO). https://github.com/pelagios/place-attestation-ontology (V, W)
11. World Historical Gazetteer. https://whgazetteer.org/about/ (V, W); Recogito https://recogito.pelagios.org/ (V, W)
12. OpenHistoricalMap. https://en.wikipedia.org/wiki/OpenHistoricalMap (V, tertiary)
13. Straub, D. (2026). Domus. arXiv:2608.12566. https://arxiv.org/abs/2608.12566 (V, preprint)
14. King's College London. Factoid prosopography. https://www.kcl.ac.uk/factoid-prosopography/about (V, W)
15. Duranti, L. (date unverified; the file name says 2007 and the text mentions InterPARES 3 as 2007-2012; earlier draft said 2008). It's All About Trust (lecture slides). https://www.interpares.org/display_file/ip1-2_dissemination_ls_duranti_lucas_2007.pdf (V, slides)
16. Kitamoto, A. & Nishimura, Y. (2016). Digital Criticism Platform for Evidence-based Digital Humanities with Applications to Historical Studies of Silk Road. DH2016 abstracts, pp. 596-600. https://dh2016.adho.org/abstracts/92 (V, A)
17. Kitamoto, A. & Nishimura, Y. (2013). Data Criticism: a Methodology for the Quantitative Evaluation of Non-Textual Historical Sources with Case Studies on Silk Road Maps and Photographs. JADH2013, pp. 11-12 (two-page abstract). https://agora.ex.nii.ac.jp/~kitamoto/research/publications/jadh13.html.en (V, A)
18. Harley, J.B. (1989). Deconstructing the Map. Cartographica 26(2):1-20. The DOI previously given here (10.1002/9780470669488.ch16) is the 2011 reprint in *Classics in Cartography* (Crossref, A), not the 1989 journal article; the 1989 article itself was not opened (S)
19. Jenny, B. & Hurni, L. (2011). Studying cartographic heritage: Analysis and visualization of geometric distortions. Computers & Graphics 35(2):402-411. doi:10.1016/j.cag.2011.01.005; https://www.berniejenny-info.colororacle.org/pdf/2011_Jenny_etal_GeometricDistortions.pdf (V, A: PDF abstract read; Crossref matches); MapAnalyst https://mapanalyst.org/ (S)
20. Introduction to probabilistic record linkage (Fellegi-Sunter). https://pmc.ncbi.nlm.nih.gov/articles/PMC7558187/ (V)

**Linkage, KGs, time machines**
21. Sun, K., Hu, Y., Song, J. & Zhu, Y. (2020). Aligning geographic entities from historical maps for building knowledge graphs. IJGIS. doi:10.1080/13658816.2020.1845702; https://arxiv.org/abs/2012.03069 (V)
22. Shbita, B. et al. (2020). Building Linked Spatio-Temporal Data from Vectorized Historical Maps. ESWC. doi:10.1007/978-3-030-49461-2_24 (V Crossref); journal version https://www.semantic-web-journal.net/content/building-spatio-temporal-knowledge-graphs-vectorized-topographic-historical-maps-0 (V)
23. Xia, X., Balestriero, R., Zhang, T. & Hurni, L. (2024). Self-supervised Video Instance Segmentation Can Boost Geographic Entity Alignment in Historical Maps. arXiv:2411.17425 (V, A, preprint, NeurIPS 2024 SSL workshop)
24. Liu, Z., Wu, S. & Hurni, L. (2025). Geospatial Question Answering on Historical Maps Using Spatio-Temporal Knowledge Graphs and Large Language Models. arXiv:2508.21491 (V, A, preprint)
25. Wu, S., Chen, Y., Gribaudi, M., Schindler, K., Mallet, C., Perret, J. & Hurni, L. (2026). Deep learning enables urban change profiling through alignment of historical maps. arXiv:2602.02154 (V, A, preprint)
26. Cura, R., Dumenieu, B., Abadie, N., Costes, B., Perret, J. & Gribaudi, M. (2018). Historical Collaborative Geocoding. ISPRS IJGI 7(7):262. doi:10.3390/ijgi7070262 (V Crossref; arXiv PDF read for the uncertainty framing; object-model detail S)
27. Bernard, C. et al. (2024). PeGazUs. EKAW. doi:10.1007/978-3-031-77792-9_22 (V Crossref); https://github.com/umrlastig/pegazus-ontology (V, W)
28. Gravier, J. et al. Evaluating and Understanding the Geocoding of City Directories of Paris. DHQ 19(4). https://dhq.digitalhumanities.org/vol/19/4/000814/000814.html (V)
29. SoDUCo. https://soduco.geohistoricaldata.org/ (S, W)
30. Vaienti, B. PhD page. https://beatricevaienti.github.io/ (V, W); Vaienti, di Lenardo & Kaplan (2025). doi:10.1080/15230406.2025.2566789 (P)
31. Yuan, Y., Thiemann, F. & Sester, M. (2025). Semantic Segmentation for Sequential Historical Maps by Learning from Only One Map. arXiv:2501.01845 (V, A: abstract; 77.3% mIoU is the best case on one dataset, Hameln)
32. di Lenardo, I. et al. (2025). The 1808 Napoleonic Land Registers of Venice. J. Open Humanities Data. doi:10.5334/johd.371 (V Crossref; abstract partly read)
33. Nature news (2019-10-25). Venice 'time machine' project suspended amid data row. https://www.nature.com/articles/d41586-019-03240-w (V, A: Nature PDF read at https://media.nature.com/original/magazine-assets/d41586-019-03240-w/d41586-019-03240-w.pdf); Time Machine Organisation statement https://www.timemachine.eu/venice-time-machine-project-current-state-of-affairs/ (V, W); Time Machine https://www.timemachine.eu/about-us/ (V, W)
34. Opll, F. The European Atlas of Historic Towns. https://journals.openedition.org/lerhistoria/1544?lang=en (earlier tagged V; on 2026-10-05 the page returned a bot-check wall, so the 17-country / 469-portfolio figures were not re-confirmed: S)
35. Petitpierre, R. (2025). Studying Maps at Scale. arXiv:2511.19538 (V, preprint thesis)

**Text, document AI, segmentation**
36. Li, Z., Lin, Y., Chiang, Y.-Y., Weinman, J. et al. (2024). ICDAR 2024 MapText. doi:10.1007/978-3-031-70552-6_22 (V Crossref)
37. Lin, Y. & Chiang, Y.-Y. (2025). PALETTE. arXiv:2506.15010 (V, preprint)
38. Li, Z., Chiang, Y.-Y. et al. (2021). Linked geo-metadata from map images. arXiv:2112.01671 (V, preprint)
39. LIGHT. arXiv:2506.22589 (V, preprint)
40. Greif, G., Griesshaber, N. & Greif, R. (2025). arXiv:2504.00414 (V, preprint)
41. Clifford, J. et al. (2026). Reading the Archive by Machine. https://working-papers-in-critical-search.github.io/paper-004-ocr-benchmark/ (V, not peer reviewed)
42. Hosseini, K., Wilson, D., Beelen, K. & McDonough, K. (2022). MapReader. ACM SIGSPATIAL Geospatial Humanities workshop. doi:10.1145/3557919.3565812 (V Crossref); arXiv:2111.15592 (V)
43. Xia, X. et al. (2025). MapSAM. GIScience & Remote Sensing. doi:10.1080/15481603.2025.2494883 (V Crossref); MapSAM2 arXiv:2510.27547 (V, preprint)
44. Yuan, Y. et al. SMOL-MapSeg. arXiv:2508.05501 (V, preprint; a ScienceDirect version appeared in search results, https://www.sciencedirect.com/science/article/pii/S2667393226000244, S); Sterzinger, R., Peer, M. & Sablatnig, R. arXiv:2506.21826 (V; an ICDAR 2025 Springer chapter also appeared in search results, https://link.springer.com/chapter/10.1007/978-3-032-04624-6_25, S)
45. Weinman, J. (2013). Toponym Recognition in Historical Maps by Gazetteer Alignment. https://weinman.cs.grinnell.edu/pubs/weinman13toponym.pdf (S; the host did not respond on 2026-10-05, A)

**Vietnam and Southeast Asia**
46. Virtual Saigon maps database. https://virtual-saigon.net/maps/collection?pn=2 (V)
47. HCMGIS GeoReference. https://georeference.hcmgis.vn/ (V)
48. Historical Maps of Southeast Asia (Leiden announcement). https://www.library.universiteitleiden.nl/news/2022/08/online-platform-historical-maps-of-southeast-asia-launched (S; fetch failed)
49. Duan, H.D. & Shibayama, M. Studies on Hanoi Urban Transition in 20th Century Based on GIS/RS. https://edit.cseas.kyoto-u.ac.jp/wp-content/uploads/2014/05/03_Duan.pdf (V; undated)

**Platforms**
50. Map Warper. https://mapwarper.net/about (V, W); David Rumsey georeferencer https://www.davidrumsey.com/view/georeferencer (V, W); Old Maps Online / Georeferencer https://www.oldmapsonline.org/en/news/2013/01/british-library-3rd-georeferencer-pilot_29 (S); NYPL Labs https://www.nypl.org/collections/labs (S); NYC Space/Time Directory https://github.com/nypl-spacetime (V, limited)

**Previously verified in `related-work.md` (P), not re-opened:** Luft & Schiewe 2021 (doi:10.1111/tgis.12794); Janata & Cajthaml 2020 (doi:10.3390/app11010299); Gede & Varga 2021; Uhl, Leyk & Chiang 2018; Meijers & Schoonman 2025; Heitzler et al. 2018; Milleville et al. 2022; Wijegunarathna et al. 2025; Kirsanova, Chiang & Duan 2025 (doi:10.48550/arxiv.2510.08385); Chen, Chazalon & Carlinet 2024 (doi:10.1371/journal.pone.0298217); mapKurator (doi:10.1145/3589132.3625579); ICDAR 2025 MapText (doi:10.1007/978-3-032-04630-7_33); Bahgat & Runfola 2021. **Per `field-comparison.md` (F), not re-verified:** Lemaître & Camillerapp 2021; Stanislawski et al. 2021; Uhl et al. 2020; FRAx4; Rabehi et al.

## What I could not verify

- Metric definitions in the ICDAR MapText papers; I did not open them.
- The NYPL Building Inspector blog (fetch returned empty), so its scale and consensus method are not stated here.
- The Nature article on the Venice dispute (login redirect). The InterPARES-versus-ISAD detail is from a search excerpt.
- The Shbita ESWC paper text (blocked); its description is from the journal-version page and Crossref. For Cura et al. 2018 I read the arXiv PDF for the uncertainty framing and matching criteria only; the "minimal object model" wording is from a search excerpt. The Shbita extended version's linkage evaluation is not stated on the page I read.
- Whether PALETTE or mapKurator code can run on VMA crops, and whether the ICDAR'24 Zenodo data are usable as stated.
- Georeferencer/Klokan and Yale-NUS/Leiden platform details beyond search excerpts.
- The exact name "Atlas of Historical Cities". The verifiable analogue is the ICHT European Atlas of Historic Towns (17 countries, 469+ town portfolios as of 2009 [V]); I found no digital linkage layer in it.
- "TextOnMap" as a named system; I found MapTextSynthesizer and SynthMap work instead.
- Whether anyone has used a map's own printed index as recall ground truth. Four searches found nothing; that is not proof.
- A systematic retraction check beyond the Crossref records named at the top.
- The `docs/research/README.md` index does not list this file (I may not edit existing files).

## Audit (2026-10-05)

An adversarial check of this file's novelty verdict, repo numbers and surprising claims, by a second pass
that re-opened sources and re-queried the repo (read-only; the public Supabase key, so staff-only tables
and rows were not readable). Edits above carry an **A** tag. Nothing was committed.

**Checked and confirmed.** Sun et al. 2020 (title, authors, IJGIS, F-score 0.89, method combination; arXiv
PDF and Crossref). Shbita et al. (Crossref; journal-version page). Xia et al. 2024 (title, authors,
NeurIPS 2024 SSL workshop, +0.23 F1). Wu et al. 2026 (authors incl. Perret; Paris 1868-1937). Cura et al.
2018 (Crossref, arXiv abstract). PeGazUs (Crossref authors; repository README). Vaienti thesis title and
defence date (her page). Kitamoto & Nishimura 2013 (authors, venue, content). Jenny & Hurni 2011 (PDF
abstract; volume and pages). Gravier et al. DHQ (144 directories, about 23 million records, 98.5%, 172
addresses and 40%). Venice dataset figures (12,277 entities, 9,312 merges, merge log). Nature's account
of the Venice dispute. MapReader, Greif, Petitpierre, Sterzinger, Yuan, PALETTE abstracts and their numbers.
Crossref records for 10 further DOIs resolved with the stated authors, years and venues; none showed a
correction field.

**Changed.** (1) The linkage verdict is narrowed: Sun 2020 and Shbita 2020 are the direct prior art;
Wu 2026 and Xia 2024 are adjacent and build no KG; Sun's datasets are six hand-vectorised maps without
georeferences and the paper does not build the graph. (2) Kitamoto's "203 sheets" corrected. (3) Jenny &
Hurni downgraded to weak support. (4) Cura wording ("weighted", "fuzzy string") removed; PeGazUs "seven
sources" and "factoid-to-facts" marked unverified. (5) The Venice quote is "useless", not "unusable",
and the stated cause was licensing and protocol gaps, with the InterPARES point a disputed claim. (6) The
`scout_candidates` description corrected: it does hold creator, publisher and date columns. (7) The OCR
ground-truth figure (43) is stale: 85 rows per `EVAL-BASELINE.md`, 91 validated on that sheet now; 1799 and
1895 also have validated map labels; 118 validated labels is now 492 (367 legend entries). (8) 65.0% and the
9.0 m minimum marked recorded-not-reproduced. (9) Harley DOI is the 2011 reprint. (10) Source tags upgraded
or downgraded where the page was or was not reachable.

**Reproduced now.** 8 labels carry a `footprint_id` (8 of 10,574 publicly readable labels on 22 maps).
The 3-point 1898 fit and its replacement by 9 points: documented in `docs/journals/260921-sheet-overlap.md`
and `docs/journals/261002-colour-eda-1882-1898.md` and `knowledge-system-plan.md`; the exact date of the
re-fit was not established, only that it was in place by 2026-10-01. 1,415.9 m (1909 Thua-thien sheet) is in
`work/analysis/georef_coverage.md`.

**Recorded but not reproduced.** The 14,506 label total (10,574 visible to the public key); 1,067 scout
candidates (table is staff-only); 65.0% (8,796 of 13,525, dated 2026-09-19, before the re-fits); the 9.0 m
minimum (found only in `related-work.md`).

**Still unverified.** Shbita ESWC paper text; Cura 2018 and PeGazUs beyond abstracts; Vaienti thesis text;
Opll (bot wall) and Weinman (host unreachable); Kitamoto 2013 error figures beyond the abstract; whether
the Wu 2026 and Xia 2024 full texts contain entity-level linkage that the abstracts do not mention; the
InterPARES slide date; the claim that no earlier use of a map's printed index as ground truth exists (a
search result, not a proof). The claim that no one has done bilingual, rename-aware linkage on a colonial
corpus rests on a limited search and should be stated as "I did not find".

## Follow-up reconciliation (2026-10-05, 15:43 UTC)

The service-role follow-up supersedes the earlier public-key inventory above: 1,499 maps across
all statuses (1,038 published), 15,133 OCR rows on 24 maps, 499 validated rows, 8 polygon links,
1,067 scout candidates, and 604 georeference versions on 591 maps. These are storage counts,
not distinct-name counts or linkage evaluation. Migration history matches through 111.
The older 14,506 total remains historical, not reproduced; 65.0% has verified saved-table
arithmetic but unrerun classifications. The 9.0 m figure is recorded in the District 4 analysis
as well as `related-work.md`. Exact queries, fit results and remaining limits are recorded in
[`framework-audit-followup.md`](framework-audit-followup.md). Earlier audit statements are dated history.
