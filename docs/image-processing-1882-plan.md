# The 1882 feature layer — consolidated plan

> **Priority (`docs/NOW.md`, 2026-10-12): this plan is bet 1b, after place links (1a) and the
> measured gates (2).** Work already running may finish one bounded step (the prepared Colab
> comparison); owner reference tracing and full-sheet runs wait.

**Updated 2026-10-12.** Ship an owner-approved 1882 layer by recovering whole street blocks,
then roads, lots and buildings. Preserve the owner's saved corrections and reduce correction
work per accepted feature. This consolidates the October 3 delivery plan, the October 11
parcel-first decision and the October 12 extraction review. The implementation below is now local and checked; GPU execution and independent
reference tracing remain open. 1898 and District 4 remain outside delivery scope.

Repo consolidation is complete: PR #33 reorganised `work/`, #34 integrated the image-processing
branch, and #35 separated image scripts from OCR. Those PRs retain the historical checkout and
migration work; do not repeat it. Current commands live in `work/image-processing/scripts/`;
shared helpers and the Python environment remain in `work/ocr/`.

## Implementation status (2026-10-12)

- **Validate:** `SimplifyPanel.svelte`, `simplifyRing.ts` and `reviewQueue.ts` provide preview,
  cancel, staged acceptance, undo and neighbour checks. Migration 121 adds atomic original-outline,
  type and status comparison; a changed geometry invalidates its geographic cache and queues warp.
  Apply 120/121 before deploying the associated review changes. Neither was pushed by this session.
- **Evaluation:** `seg_eval.py` now scores one-to-one, class-aware matches, reads frozen pixel
  references/GeoJSON, and exports per-threshold diagnostics and matched boundary distances.
  Duplicate proposals remain false positives; unknown classes require an explicit declaration.
- **Extraction:** `boundary_refine.py` is the bounded text-aware candidate; `regularize_blocks.py`
  preserves holes and MultiPolygon parts. Mask conversion retains substantive components and closes
  rings. `mask_to_footprints.py` exports local contours and refuses unsupported holes at import.
  These changes have synthetic checks, not a new historical-map accuracy result.
- **GPU:** `memory_predictor.py` activates the real SAM2 memory encoder and attention with a
  confidence-gated diverse bank. A real SAM2.1 CPU smoke passed. `seg_context.py` turns metadata
  into explicit prompt/target/area settings and review-only legend suggestions; it does not encode
  prose. The interactive notebook isolates baseline, metadata, memory and both.
- **Prepared handoff:** `work/image-processing/results/seg-comparison-20261012/` holds the source
  archive, uploadable notebook, paged correction snapshot, metadata, both priors and baseline audit.
  `prepare_comparison.py` uses an explicit source allowlist, full upstream commit pins and hashes;
  secrets, reference traces and the correction snapshot are excluded from the GPU archive. The
  notebook refuses overlap with existing unseen held-out windows and verifies identical tile pixels
  across variants. Region selection and owner runtime startup are still required.

No production shapes, approvals, migration history or deployment were changed. Remaining work is
owner reference tracing, the T4 comparison, method selection and owner review before any new import.

## Target and boundaries

Map `0e02b9d9-9d40-4cca-8e41-8c8373d54d3b`, source image 12102×8982 px. All extraction,
comparison and simplification use that source-pixel grid. Pin the actual scan before a run.

| Object | Definition and order |
|---|---|
| `parcel` | One whole street block, following the printed block boundary. First review target; the block line and the kerb are distinct. Migration 120 adds the type; verify its remote availability before importing it. |
| `road` | Street surface derived after water and whole parcels are approved. Respect the kerb rule; review pavement, open land and margins rather than calling every remaining pixel a road. |
| `land_plot` | A lot inside a parcel. Review after the enclosing parcel. |
| `building` | An individual footprint inside a parcel. Review after the enclosing parcel. |
| `waterway`, `water_body` | Frozen water proposals with owner correction; independent of the block experiment. |

Plot/building containment inside a parcel is expected. Two whole parcels overlapping is an error.
Property-fill classes from the legend describe holdings, not necessarily buildings or whole blocks.
Owner rules remain: pavement counts as land; water over parcel hatching counts as water; the citadel
is dry. Names join only after geometry is established.

## Evidence and baseline

- The [blog preview](https://maparchive.vn/blog/buildings-as-ground-control) contains 91 polygons
  from the retired coarse SAM plot pass on one city-centre crop. It demonstrates whole-block
  extraction, without establishing full-sheet accuracy. Keep the archived preview as a development
  comparison; do not restore the deleted pipeline wholesale or treat its polygons as ground truth.
- The cleaned September colour output contains 1,431 proposals (881 plots, 550 buildings).
  The saved October 1 colour run contains 1,887 proposals at render width 4096 and is not canonical.
  These are local artifact counts, not current database counts or accuracy figures.
- The [October layer review](journals/261001-1882-layer-review.md) retained 17 of 30 sampled cream
  proposals, each still needing geometry correction. It records text/tree residue, partial hatch
  extents, missing grey buildings and merged shophouse rows. Shape filters also rejected genuine
  narrow plots: use their signals for review ordering, not automatic deletion.
- The read-only October 12 snapshot independently confirms **814 machine plots and 496
  buildings**, all `import`, `needs_review`, run `colour-20260919`. **778 of 814 plots** match the
  raw local layer using best overlap with IoU ≥0.999 and boundary Hausdorff ≤1 source px.
  `audit_snapshot.py` reproduced the Shapely trial: 4.25%, 25.46%, 35.22% fewer vertices at 2/4/6 px,
  with 7/212/296 plots changing area by over 2%. Saved in the handoff's `baseline-audit.json`,
  bound to the snapshot hash and selection. These are provenance/editing figures, not accuracy;
  the browser preview uses a different, guarded simplification implementation.
- **Street/water candidate:** `then_now_blocks.py` produced 152 whole blocks in
  `results/prior/<1882 id>/then-now/blocks_1882.geojson`, independently of colour. Known faults are
  south-east mask leakage joining blocks and lettering bumps. The reported median overlap 0.87 on
  seven QGIS plots compares proposals with another layer; it does not establish independent truth.
  Freeze its input hash in the comparison and leave the producing session's files untouched.
- Selected-trace best-match IoU is diagnostic: extra proposals can improve it while adding residue.
  The SAM2 LoRA was trained on the old 46 volunteer traces. Neither those scores nor a neat preview
  establish independent precision or full-sheet performance.

See [extraction record](research/image-processing-record.md),
[September audit](journals/260919-seg-audit.md) and `work/ocr/EVAL-BASELINE.md` for dated evidence.
“Normalized” means a consistent data format; it does not certify correct boundaries.

## Work order

| Step | Deliverable | Depends on |
|---|---|---|
| 0 | Reproducible baseline and protected correction snapshot | Read-only export |
| 1 | Reversible Simplify preview in Validate | Step 0; can proceed while references are traced |
| 2 | Complete parcel references and fixed evaluation protocol | Owner tracing; before extraction tuning |
| 3 | Bounded extraction comparison, including one Colab run | Step 2; development crops separate from test windows |
| 4 | Chosen proposals reviewed as parcels, then roads, then lots/buildings | Step 3 gate; approved water for road derivation |

Water preparation can proceed alongside steps 1–3. A full-sheet replacement is not the starting
point: existing corrected rows remain the working layer.

## Step 0 — Freeze the input and preserve corrections

Export the live 1882 rows read-only with pagination: id, source, run_id, feature_type,
review_status, source-pixel geometry and available review/update stamps. Preserve all current
geometries, including corrections still pending approval. Separately identify the September import,
raw local output and regularized local output; define the geometric matching tolerance explicitly.
Do not infer unedited status solely from `reviewed_at`: the manual baseline records missing stamps.

Save an input manifest: scan URL/dimensions and rendered-image hash, exact code revision, OCR
run/label selection, render width and source-to-render scale, model/checkpoint and configuration,
region coordinates, hardware, elapsed time and output paths. Pin dependencies for a reproducible
GPU comparison. Hash each trial input; keep simplification results alongside, never over it.

**Exit:** another session can reproduce the count and trial against the same snapshot, and distinguish
machine proposals from saved owner work without treating an old local file as the live layer.

## Step 1 — Make existing geometry easier to edit

Add a **Simplify preview** to Validate for the selected feature. Start from its current saved
geometry. Offer 2, 4 and 6 source px as trial tolerances without choosing 4 px as a validated default.

Overlay current and proposed outlines. Show vertex counts, area change and maximum boundary
movement; flag validity failures, hole changes and newly introduced overlaps with other parcels.
Preserve holes in the preview and flag features the current storage contract cannot represent.
Neighbour checks apply within each feature type, including existing plots/buildings:
expected building/lot containment across types is not an error.

Acceptance stages the outline through the existing review edit path; preview/cancel writes nothing.
Edits persist with the approve/reject verdict, and can be undone before it. A preview must be used or
cancelled before a verdict. Migration 121 compares the original saved outline/type/status atomically. Treat a feature changed since preview as a conflict
and recompute instead of overwriting it. Keep the user's chosen corners and notches visible.

Independent topology-preserving simplification does not preserve shared edges between neighbours.
Use shared-edge simplification only after validating a true non-overlapping, edge-matched coverage;
the current mixed proposal layer does not satisfy that assumption.

**Exit:** preview, cancel, accept and undo work; saved corrections survive; invalid/newly overlapping
results are clearly flagged. Verify a rectangle, diagonal/triangular block, L-notch, curve and adjacent
parcels. Test the real write path and preview isolation; no full-sheet automatic simplification.

## Step 2 — Establish the reference before tuning

Use the blog area and other already-seen regions for development. The old candidate
`4420,3800,650,550` contains LoRA training traces and cannot serve as its independent test.

The owner traces **two new exhaustive windows**, initially about 600×600 source px: one dense
centre and one mixed area including weak outlines, hatching or grey buildings. Choose windows
outside training traces and existing river/road blind boxes; confirm the target classes before
looking at candidate predictions. If the windows cannot contain representative whole-block
structure, enlarge them before freezing. Trace every parcel in both windows; record lots/buildings
separately if they will also be scored. A parcel reference alone cannot evaluate buildings.

Record source image identity, boxes, definitions, split and trace ids in a dedicated
`shapes_ref.json`, or `windows.json` only after verifying compatibility with its existing tools.
A test window may be owner-seen for tracing, but it is never used for tuning. Use the existing
`view.py` blind-window protection for crops; never inspect `heldout` plus `seen:false` windows.
Machine imports and LLM-generated polygons cannot become reference traces.

Freeze the scoring protocol with the reference:

- Clip both predictions and references to each window; state how edge-spanning objects count.
- Score classes separately with one-to-one matches at IoU 0.5 and 0.75; report precision, recall,
  F1, duplicate/split/merge errors and all unmatched proposals. Record mean/median overlap as
  supplementary diagnostics, not the sole selection criterion.
- Measure boundary distance in source px, boundary agreement with the printed line, and parcel
  overlaps. Record owner correction time per accepted parcel using a fixed procedure and order
  chosen before review; repeated correction of the same block is subject to learning effects.
  `review_timings.py` consumes the producing session's `then-now/verdicts.jsonl` against the exact
  `classes.geojson` outlines and method hash, separating shown/blind arms and excluding stale/idle
  rows. “Outline right?” latency is review time; it is not correction time unless an explicit
  correction duration was recorded. Joint 1882/modern verdicts cannot replace parcel references.
- The evaluator now enforces those class/matching rules. Use `--reference <frozen pixel GeoJSON>`
  and `--iou-thresholds 0.5,0.75`; its default threshold is 0.5. Do not substitute a geographic
  export or changing database traces for the frozen reference.

**Exit (`shape-precision`):** owner-confirmed exhaustive references, a versioned protocol and a
scorer that penalizes residue and duplicate objects. Score each frozen candidate once; no iterative
tuning against test results. State sample limitations rather than generalizing to the whole sheet.

## Step 3 — Compare bounded extraction methods

Develop on the seen crops, then freeze the following candidates for the same target objects and
source image. Record each method's processing scale; different scales are an experimental factor,
not an unnoticed change between runs.

| Candidate | Work to test |
|---|---|
| Street/water blocks | Freeze the 152-block then-now candidate and its mask/code provenance; compare it directly and as a SAM prior. It is not reference truth. |
| Current colour baseline | Reproduce `colour_blocks.py` and `clean_blocks.py`, with the pinned defaults and render scale; evaluate whole-block candidates separately from lots/buildings. |
| Text-aware boundary refinement | Use reviewed OCR boxes to locate potential lettering; distinguish letter strokes from continuous boundary evidence inside them. Refine colour candidates against visible lines, infer only supported short continuations, and flag uncertainty. |
| Coarse SAM proposals | Adapt the current SAM2 inference path to seek whole blocks and compare on the development crop; retain only if a reproducible configuration can be frozen. |
| Colour-prompted SAM2 LoRA | One Colab run with `--mode prompted --prior <pinned colour proposals>`, `epoch_010.pth`, explicit region/scale and JSON output. This comparison remains unperformed. |

Boundary work must address masks as well as polygonization. Direct contour tracing and controlled
line fitting are candidates, not an assumed upgrade. Preserve diagonal streets, triangles, L-shapes
and curves; no universal four-corner or rectangle rule. The regularizer now preserves holes and components; the text-aware candidate supplies filtered
ink evidence. Broad reuse still depends on independent scoring, because tidier boundaries can
remain wrong. Simplification cannot remove a false object.

### Colab execution

The prepared comparison uses 2048 source-pixel tiles rendered at width 512 to suppress fine ink
before SAM2's internal 1024 encoding. This is an experimental coarse setting, not a validated
optimum. A memory test needs at least two tiles with eligible prompts and accepted memories;
the notebook labels an unconditioned run uninformative. Small owner reference windows can sit
inside a larger frozen inference region. See [operator guide](../work/MapSAM2/COMPARISON.md).

Prepare an interactive comparison notebook that checks CUDA/actual GPU, installs pinned code,
mounts the owner's checkpoint, reads the pinned prior and runs standalone inference. The owner
selects GPU/T4 when available, authorizes Drive access and starts the cells. This session has no
connected browser-control tool; do not claim a live connection merely because a notebook exists.
Persist JSON, configuration, logs and previews to Drive for local scoring. **Omit
`--write-supabase`; do not enqueue the current seg worker for this no-write comparison.**

The existing `work/MapSAM2/vma_seg_worker.ipynb` is a later queue-processing route: it uses a
seg-scoped worker token and `vma_worker.py --kinds seg`, whose runner writes proposals. Use Colab
Secrets for tokens, never the service key. Google's [FAQ](https://research.google.com/colaboratory/faq.html)
restricts distributed workers and remote shells on free runtimes without a positive compute-unit
balance; use an eligible paid runtime for that route. GPU type and runtime limits vary. An
interactive notebook with saved artifacts is sufficient for this experiment.

### Avoid repeating established failures

- Blanking entire OCR rectangles reduced the earlier SAM2 score (0.089 to 0.062) and can erase
  real boundaries. The text-aware candidate is not the existing `--text-mask` switch.
- Direct tracing changed an offline 1,135-proposal hull run to 648, triggering sliver filtering;
  the hybrid still left incomplete outlines. Repair/test the region masks and filtering together.
- More aggressive closing can bridge alleys; harder shape filters can remove real narrow lots.
  Use residue signals to rank review, keeping a random audit of apparently clean candidates.
- Our `SAM2ImagePredictor` path processes tiles independently; it does not implement the published
  MapSAM2 cross-tile memory by itself. The new opt-in adapter explicitly calls memory encoding
  and attention, with deterministic top-k retrieval rather than the paper's stochastic sampling.
  It keeps instance prompts; full prompt-free semantic training is a separate deferred task.
- The current watershed option redraws predicted polygon edges rather than discovering printed
  image edges, and is unmeasured. Record its setting explicitly; a standalone comparison starts
  with it off and tests it separately only on development data.

**Selection gate (`colour-blocks`, `colab-seg-run`):** report results before choosing a method.
With both CPU methods available, retain the earlier +0.05 mean IoU margin for selecting SAM2
but compare it against the stronger CPU candidate, require
no worse precision or recall on the fixed parcel reference, and report correction effort. Prefer
the simpler method when the gain is unclear. Retain current proposals plus hand correction if no
candidate improves the workflow. Neither model confidence nor polygon count is an accuracy gate.

## Water — freeze, correct and review

Keep `water-1006337f.png` (v3) fixed; no further river/road threshold tuning. Hand-correct creek
heads, the hatched Canal de ceinture and dry citadel ramparts. `road-a3b0458f.png` remains diagnostic.
The river record's point scores measure water classification, not shore-polygon accuracy.

Implement `mask_to_footprints.py` as a minimal source-pixel contour export with an explicit area
floor and 1–2 px simplification. Separate waterways and isolated water bodies with owner review.
Default execution produces local GeoJSON; database insertion requires explicit `--apply`, with
`source='import'`, `review_status='needs_review'` and a fresh run id. Preserve holes locally and
flag islands/voids unsupported by the outer-ring storage contract; never silently fill them and
call the result correct. Verify the writer's schema/API contract before choosing the transport.

Warp after import. Only the owner approves. **Exit (`river-reconstruction`):** approved, corrected
1882 water renders on `/explore`; 1898 remains deferred.

## Step 4 — Ship in review order

1. **Parcels:** use the chosen method to propose missing or unresolved whole blocks, clipped to the
   map body. Compare with the correction snapshot before import; skip collisions with existing
   owner work or present them for explicit reconciliation. Do not overwrite or delete the old run.
   Verify migration 120 availability; import as `parcel`, `needs_review`, with a distinct run id.
   Review against the block line and approve before deriving roads. Flag water conflicts for review.
2. **Roads:** derive candidate street surfaces from the map body minus approved water and parcels.
   The complement also contains pavement/open land, so apply the owner definitions and review it.
   Explicitly resolve the space between block boundaries and kerbs. Import and approve road polygons.
3. **Inside each approved parcel:** split lots and individual buildings; address grey-fill buildings
   and merged shophouse rows separately. Keep the per-class reference/scoring distinction. Import
   only new/unresolved proposals, then correct and approve. Preserve existing saved edits throughout.
4. **Names and geographic output:** run `join_labels.py` against pinned runs after shapes are
   established; use `name_masks.py` only for naming. Warp through the current annotation and check
   `/explore` and the export. A changed georeference changes geographic output, not source geometry.

Reject false proposals in Validate rather than deleting them in Draw, preserving their verdicts
and the precision denominator. Track per-class approved/rejected/pending counts by run. The owner
alone approves machine output. **Done:** every in-scope 1882 proposal is decided; water, parcels,
roads, lots and buildings render correctly, without overwriting the correction snapshot.

## Tracking and verification

ROADMAP remains the open tracker; this file defines implementation order. `shape-simplify` covers
step 1; `shape-precision` step 2; `colour-blocks` and `colab-seg-run` step 3; `river-reconstruction`
the water delivery. `temporal-fabric` consumes the approved 1882 layer. The broader `seg-eval-set`
remains separate: two windows cannot establish archive-wide accuracy.

For implementation, read `docs/testing.md` before adding checks and the relevant tree's
`CLAUDE.md` before editing. Load the repo Svelte skill for UI work; read `supabase/CLAUDE.md` and
`docs/db-guidelines.md` before any migration/write. Verify preview isolation, save/undo/conflict
behavior and geometry cases; run `npm run check` and focused existing tests. Extraction requires
reproduced artifacts and frozen reference scoring, not merely passing a code check. Document each
run and decision in the research record; update ROADMAP and knowledge-system §9 together.

Deferred: 1898/District 4 extraction, road-pass tuning, OSM-warp follow-ups, larger-model searches,
prompt-free semantic MapSAM2 training, retraining without an independent reference, automatic building
matching/change detection and blanket replacement of existing shapes. The georeference rotation
fix remains with the placement workstream.

## External method references

- [Historical-map vectorization benchmark](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0298217): learned edge filtering plus closed-region extraction; independent evaluation.
- [MapSAM2](https://arxiv.org/html/2510.27547v1): adapted segmentation with cross-tile memory; its reported results are not measurements of VMA's predictor path.
- [Historical-map object extraction](https://link.springer.com/article/10.1007/s42489-023-00131-z): text removal while preserving feature edges.
- [Shapely simplification](https://shapely.readthedocs.io/en/2.1.2/reference/shapely.simplify.html) and [coverage simplification](https://shapely.readthedocs.io/en/2.1.2/reference/shapely.coverage_simplify.html): individual geometry validity versus preservation of shared edges.
