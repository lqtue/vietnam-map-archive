# Image-processing consolidation and the 1882 feature layer — plan

**Written 2026-10-03; Phase 0 steps 1–2 merged in PR #34; step 3 implemented on `refactor/image-processing-scripts` for PR review.** The plan to stop researching feature extraction and ship one approved
1882 layer (water, plots, buildings, roads), after first cleaning up the image-processing WIP. Scope is the 1882 sheet only:
1898 and District 4 are out of scope until this ships. The owner approved the direction and asked for this file
so another session or model can pick it up cold. The briefing below is everything that session needs and would
otherwise have to rediscover.

---

## Briefing for the session that picks this up

### The project in one paragraph
Vietnam Map Archive (VMA): a SvelteKit app over georeferenced historical maps of Saigon. Read `/CLAUDE.md`,
`work/CLAUDE.md` and `docs/lessons.md` first. Polygons live in the Supabase `footprints` table
(`pixel_polygon` = outer ring in source pixels; `feature_type` ∈ building, land_plot, road, waterway, green_space,
water_body, other; `source` ∈ volunteer, sam-auto, sam-corrected, import; `review_status`; `run_id`; `geom` filled by
the `warp` job, migration 066). Only `approved` rows reach `/explore` (`/api/export/footprints`). OCR labels join to
footprints via `work/ocr/scripts/join_labels.py` (migration 050, smallest containing polygon).

### Where things stand (2026-10-03)
- **Text extraction is solved.** Gemini OCR (`work/ocr/scripts/ocr.py`), run by `work/worker/vma_worker.py`.
- **Feature extraction has two methods, neither shipped.** Neither has an honest held-out polygon score.
  - **Colour passes** (CPU, numpy/scipy/PIL):
    - `colour_blocks.py`: plots and buildings. With the within-parcel split it scores land_plot IoU 0.343 and building 0.355 (best-match IoU over the 24 land_plot and 17 building traces among the 46 volunteer traces), in about 80 s per sheet. Its constants were tuned on those traces.
    - `river_pass.py`: water. 96.5% on blind points (v1, held out, 279/289). v3 scored 74/74 on batch 4, but v2 also scored 74/74 there, so batch 4 doesn't test v3's change.
    - `road_pass.py`: roads. v1 is 85.7%, below the 94.5% you'd get by calling everything land; v2 is 84.3%; v3 is unscored.
    - `sheet_features.py`: shared measurements (paper, wash, stroke, texture).
  - **MapSAM2** (`work/MapSAM2/`, a SAM2 LoRA run on Colab):
    - It has only ever been scored on its own 46 training traces: land_plot 0.249, building 0.160.
    - It has never been held out, never run on the colour prior, and never run on water or roads.
    - Its one production run (72 polygons, all label boxes) was deleted on 2026-09-19.
  - **Gemini as a segmenter** (`seg_gemini.py`) was rejected: one rectangle per block, not repeatable. It is kept for *naming* (`name_masks.py`).
- **Colour EDA (2026-10-02/03, `docs/journals/261002-colour-eda-1882-1898.md`):**
  - Colour only rules things out; it doesn't classify.
  - Plot outlines, kerbs and road edges are nearly indistinguishable.
  - The 1882 georeference has a smooth ~0.88° rotation error. Pixel-space footprints don't care, so it's not this plan's problem.
- **Full records:**
  - `docs/research/image-processing-record.md`
  - `work/ocr/EVAL-BASELINE.md`
  - `river-reconstruction.md`: `docs/river-reconstruction.md` on the branch, which holds all the scores; main has an uncommitted move to `docs/research/`
  - `docs/processing-plan-1882-1898.md` (branch only): the earlier two-sheet plan, superseded by this one
  - `docs/journals/260918-colour-blocks.md`, `260919-seg-audit.md` and `261001-colour-pair-1882-1898.md`

### The 1882 sheet
Map id `0e02b9d9-9d40-4cca-8e41-8c8373d54d3b`, 12102×8982 px, 0.3416 m/px, image +x points north.
- Frozen masks:
  - water v3 `water-1006337f.png`
  - road v3 `road-a3b0458f.png` (diagnostic only)
- Owner label rules:
  - pavement counts as land
  - the road edge is the kerb line
  - water drawn over parcel hatching counts as water
  - the citadel is dry

### Original checkout briefing — historical state before PR #33

Main’s reorganisation is now committed at `8a475366` (PR #33). The integration branch
consolidates `feat/1882-1898-processing` without changing that original branch or its worktree.
Reference tools are under `work/image-processing/experiments/river-reference/`; modern
overlays use `experiments/modern-overlays/`. Selected OSM evidence stays local pending
licence review. Image commands are separated from OCR on the step-3 branch, with shared
helpers and the environment retained in OCR. Cached outputs were copied additively during
integration; final output cleanup, the remaining compatibility-link audit, and remaining
Phase 0 documentation/roadmap alignment still need completion.
No layer has been approved or written to the database during integration.

The checkout details below record the plan’s starting point, rather than the current checkout.

### Two checkouts at plan creation
- **Main:** `/Users/airm1/Work/Projects/vietnam-map-archive`, on branch `l7014-iiif-ingest`.
  - Its dirty tree is mostly **other sessions' work** (paper, docs, scripts): never stage it wholesale.
  - It also holds the owner's **uncommitted `work/` reorganisation**: `work/analysis/*` → `work/image-processing/experiments/*`, outputs → `work/image-processing/results/`. `work/ocr/outputs`, `work/ocr/logs` and `work/analysis/{1882,river_pair,river_ref,modern_overlay,seg-260919}` are compatibility symlinks.
  - Every deletion in that reorganisation was verified to be a move; nothing is lost.
- **Worktree:** `/Users/airm1/Work/Projects/vma-1882-river`, branch `feat/1882-1898-processing`.
  - It is 39 commits ahead of `main` (+13.8k lines, mostly `work/analysis/river_ref/` and `docs/river-reconstruction.md`), on the old layout.
  - It has 618 MB of gitignored outputs in `work/ocr/outputs/<map>/{features,river,native.png}`.
  - Untracked there: `docs/journals/261002-colour-eda-1882-1898.md` and `work/analysis/osm_warp/`.
  - Its `.claude/handoff.md` has the river/road session's state. This plan supersedes that file's "Next" section.
- **Conflicts the merge must resolve:**
  1. The branch tracks `work/analysis/river_ref/` and `modern_overlay/` as real directories, while main has symlinks and gitignores their targets.
  2. `work/ocr/scripts/modern_prior.py` is edited on both sides (main's change is an uncommitted `--osm` feature).
  3. The branch scripts hard-code `work/ocr/outputs/...` and `work/analysis/river_ref/...`.
  4. Main moves `docs/river-reconstruction.md` and `docs/image-processing-record.md` to `docs/research/`, leaving symlinks, while the branch keeps editing them at the old paths. Expect modify/rename conflicts, and carry the branch's edits into `docs/research/`. Relative links to `river-reconstruction.md` in the branch's handoff and `processing-plan-1882-1898.md` need updating.
  5. The real `windows.json` and the label/trace files exist only in the branch's `river_ref/`. Main's `river-reference/` holds only `crops/`.
- **Python:** `/Users/airm1/Work/Projects/vietnam-map-archive/work/ocr/.venv/bin/python`. There is no venv in the worktree.

### Rules that bind this work
- **Blind-split discipline** (`river-reference/windows.json` is authoritative):
  - A window that is both `heldout` and `seen:false` is never cropped, previewed or tuned on (`view.py` `blind_boxes`). `calibrate` windows may be viewed, even when `seen:false`.
  - Each version is scored once, on data nothing was tuned on.
  - `view.py` refuses crops that touch blind boxes; use it.
- **Machine output enters `footprints` only as `needs_review`.** Only the owner approves. Never fabricate reference polygons: an LLM tracing the ground truth would defeat the test.
- **Git:**
  - Never commit on `main`, never push, never touch other sessions' files.
  - Commit messages end with the session's co-author line.
  - Keep `docs/private/` out of everything.
  - The HCMC modern layers' licence is unresolved, so their outputs stay local.
- **Docs:**
  - Close a ROADMAP item by moving it out and mirror it in `docs/knowledge-system-plan.md` §9 in the same commit.
  - Add a journal row to `docs/journals/README.md`.
- **Owner preferences:**
  - Short answers.
  - Sonnet subagents for analysis.
  - Show figures by opening them on screen.
  - Hand correction is preferred over further rule tuning.

---

## Phase 0 — Consolidate the repo (one session, before any 1882 work)
1. **Commit main's reorganisation alone.**
   - New branch `image-processing-consolidation` off `main`.
   - Stage only `work/**`, the reorganisation hunks of `.gitignore` (stage by hunk; confirm `docs/private/` is still ignored afterwards), `work/CLAUDE.md`, the new READMEs and the moved `oneoff/` scripts.
   - Leave the other sessions' dirty docs, paper and scripts unstaged.
   - Commit `modern_prior.py`'s `--osm` feature edit separately.
2. **Merge `feat/1882-1898-processing`** into that branch.
   - Its tracked `work/analysis/river_ref/` (47 files) becomes `work/image-processing/experiments/river-reference/`; `modern_overlay/` (6) becomes `experiments/modern-overlays/`.
   - Remove main's symlinks at those names.
   - Narrow `.gitignore` there to `crops/`, `proposals/` and `out/`.
   - Resolve `modern_prior.py`.
   - Commit the colour EDA journal and the kept `osm_warp` outputs (`summary.json`, `streets_warped_1882.geojson`, 3 figures; drop the ~20 fit scripts).
3. **Split OCR from image processing (after the merge).** `sheet_features`, `river_pass`, `road_pass` and `review_sheet` exist only on the branch. `git mv` into `work/image-processing/scripts/`:
   - `colour_blocks`, `clean_blocks`, `seg_gemini`, `seg_eval`, `sheet_register`, `name_masks`, `review_figs`, `legend_probe`, `modern_prior`, `sheet_features`, `river_pass`, `road_pass`, `review_sheet`
   - and `regularize_blocks`, already tracked by PR #33: move it with the other image scripts

   `work/ocr/scripts/` keeps OCR only: `ocr`, `join_labels`, `prompt`, `pricing`, `gemini_client`, `cache`, `labels`, `local_vision`, `scale`, `iiif_tiles`, `supabase_client`, `eval`, `eval_metrics`, `audit_run`, `dictionary`, `test_*`, `oneoff/`. Shared modules (`scale`, `iiif_tiles`, `supabase_client`) stay in `ocr/scripts`; image scripts import them by path.
   - Fix each moved script's `sys.path`/`ROOT` line.
   - Fix the `river_ref` paths in `sheet_features`, `river_pass`, `road_pass` and `edge_profile`.
   - Fix the callers that import a moved script: `sweep_water`, `review_water`, `modern_overlays/{fit,overlay,to_gpkg}` and `river_ref/edge_profile`.
   - `district4/*`, `build_contact` and `eda` import only the shared modules. They need a change only where they hard-code `ocr/outputs`.
4. **Move outputs.** The worktree's `work/ocr/outputs/<map>/{features,river,native.png}` moves into `work/image-processing/results/<map>/`.
5. **Delete local junk, after showing the owner the list:**
   - `experiments/segmentation-20260919/_superseded` (174 MB)
   - superseded `river/road-*.png`/`water-*.png`, keeping `water-1006337f`, `road-a3b0458f`, the 1898 `water-b7ff0618` and `road-fadb75b3`
   - `work/tmp/`
6. **Remove the compatibility symlinks** (`ocr/outputs`, `ocr/logs`, `analysis/*`, `work/vectorize`) once grep finds no live reference. Then remove the worktree.
7. **Fix the docs** (text, not only paths):
   - **`docs/pipelines.md`:** its Files table (around lines 566-582) lists only `modern_prior` of the image scripts. Add `colour_blocks`, `sheet_features`, `river_pass`, `road_pass` and `mask_to_footprints` at their new paths.
   - **`docs/ponytail-debt.md`:** the headings around lines 368-453 point at `work/ocr/scripts/{name_masks,colour_blocks,seg_eval,modern_prior}.py`.
   - **`work/README.md`, `work/CLAUDE.md:4` and `work/image-processing/README.md`:** they say code stays in `ocr/` and describe the symlinks as permanent. Rewrite both claims.
   - **`docs/research/image-processing-record.md`:** paths, plus line ~189 ("finish the scoped 4420 window"), which Phase 2 replaces.
   - **Branch `docs/processing-plan-1882-1898.md`:** mark it superseded by this file at the top. Its "no traces yet" state is stale.
   - **Branch `.claude/handoff.md`:** rewrite "Next" to point here. Its batch-7, 1898-fix and shadow-side steps are dropped.
   - **Indexes:** add this plan to `docs/README.md` (around lines 61-64) and `docs/research/README.md`. Add the `261002-colour-eda` row to `docs/journals/README.md`.
   - **`docs/ROADMAP.md`** (and `knowledge-system-plan.md` §9), reworded now so they don't contradict this plan:
     - `river-reconstruction`: the exit narrows to 1882 water approved; the 1898 exit is deferred.
     - `shape-precision`: the two new windows replace `4420,3800,650,550`.
     - `colab-seg-run`: its exit (a worker `seg` job writing `sam-auto` rows) becomes the hand-run, no-write head-to-head.
     - `temporal-fabric`: point it at that item instead of `colab-seg-run`.

## Phase 1 — 1882 water: freeze and ship (about 2 days)
1. **Freeze `water-1006337f.png`** (v3). No more water tuning. Known weak spots go to hand correction: narrow creek heads, the hatched Canal de ceinture, the citadel ramparts (dry).
2. **New script `work/image-processing/scripts/mask_to_footprints.py`** (minimal):
   - Reads a binary mask and writes outer-ring polygons in source pixels.
   - Simplifies at 1–2 px with `cv2.findContours` plus `approxPolyDP`, or numpy/PIL if cv2 is absent.
   - Drops pieces under a minimum area.
   - Splits by connected component: the river and arroyos become `waterway`, isolated bodies `water_body`.
   - Holes: the table stores an outer ring only, so islands are not cut out.
   - Writes rows with `source='import'`, `review_status='needs_review'`, a fresh `run_id` and a `category`.
   - `--dry-run` writes GeoJSON for a look first.
   - Inserts through its own small PostgREST call with the service key. `supabase_client.py` has no footprint insert, only `fetch_footprints`; copy its auth and headers pattern. One `--self-check` on a synthetic mask.
   - The pipeline `results` route (`src/routes/api/pipeline/results/+server.ts:233-274`) needs a claimed job, so a direct insert is simpler for a one-time import.
3. **Warp:** enqueue the existing `warp` job so `geom` is filled.
4. **The owner reviews** the water polygons in the review tool (`src/lib/features/contribute/review`) and approves. They show on `/explore`.

## Phase 2 — Blocks: one fair head-to-head (one week)
1. **Build a fresh reference.** The `shape-precision` window `4420,3800,650,550` (ROADMAP) holds 9 of the 46 traces the LoRA was trained on, so it can't judge MapSAM2.
   - Instead the owner traces **two new windows** of about 600×600 px with **no existing trace in them**: one dense centre and one mixed with buildings.
   - Trace exhaustively at `/scan?mode=shapes`, every land_plot and building, about 15–25 features each, about 2 h total.
   - Choose them outside the river/road blind windows in `windows.json`.
   - Record them as `shapes_ref_1`/`_2` in `windows.json` with `split: heldout, seen: true` and a new `layer: shapes`. First check that `view.py` and `score.py` ignore an unknown layer; if they don't, keep the two boxes in a separate `shapes_ref.json`. Nobody tunes on them.
2. **Colour run:** `colour_blocks.py --map-id 0e02b9d9… --out …/results/0e02b9d9…/blocks-<date>` with the defaults, within-parcel split on, render 4096. Then `clean_blocks.py`.
3. **MapSAM2 run:** one Colab run of `work/MapSAM2/inference_tiles_as_video.py --lora --mode prompted --prior <colour blocks.geojson> --out-json`.
   - Run it **without** `--write-supabase`: run it by hand, because the worker's `seg` argv always writes (`vma_worker.py:412-445`).
   - Checkpoint `epoch_010.pth`, as in earlier runs.
4. **Score both, once:** `seg_eval.py --window <w> --types land_plot,building --iou 0.5` on each window.
   - Report best-match IoU, the count above 0.5, and the precision, recall, F1 and false-positive list that `--window` already prints (`seg_eval.py` `window_score`/`report_window`, around lines 316-372).
5. **Rule:** MapSAM2 wins only if it beats colour by at least 0.05 mean IoU and is no worse on precision. Otherwise colour wins, because it is CPU-only and reruns in 80 s.
   - Record the result in `docs/research/image-processing-record.md` and `EVAL-BASELINE.md`.
   - The losing method stays in the repo, unused for 1882.

## Phase 3 — 1882 blocks, buildings and roads into the product (about a week, most of it owner review)
1. **Full-sheet run of the winner,** clipped to the neatline. Drop pieces overlapping approved water by more than 50%.
2. **Name them:**
   - `join_labels.py 0e02b9d9… <ocr_run_id> <seg_run_id>` (worker `join` job).
   - Where OCR misses, `name_masks.py --names <seg_gemini run> --masks <blocks run>`.
3. **Roads:** neatline minus approved water minus blocks, polygonised with `mask_to_footprints.py` as `road`. No more `road_pass` work.
4. **Insert land_plot, building and road** as `needs_review` with one `run_id` per class, then warp.
5. **Review in passes,** worst first: buildings, then plots, then roads.
   - The owner fixes geometry and approves.
   - Track progress with `select feature_type, review_status, count(*) from footprints where map_id = '0e02b9d9…' group by 1,2`.
6. **Done when** every 1882 polygon is approved or rejected and all four layers render on `/explore` for 1882.

## Dropped (record in ROADMAP as closed or deferred)
- Road-pass tuning and the batch-7 road labels.
- The 1898 dashed-street fix and the 1898 road batch.
- The shadow-side line cue.
- OSM warp follow-ups.
- The 1882 georeference rotation fix (the georeference session owns it).
- All of 1898 and District 4 until 1882 ships.

## Docs and roadmap, in the same commits as the work
- **`docs/ROADMAP.md`:**
  - `river-reconstruction` closes at water approval
  - `colour-blocks` and `colab-seg-run` become the head-to-head, then close with its result
  - `shape-precision` is satisfied by the two new windows
  - `temporal-fabric` notes that it runs on 1882 first
  - mirror every change in `knowledge-system-plan.md` §9
- **Register this file in `docs/README.md`.**
- **Keep the record current:** `image-processing-record.md`, `river-reconstruction.md`, `.claude/handoff.md`.

## Verification
- **Phase 0:**
  - every moved script passes `--help` or `--self-check` from its new path
  - `river_pass.py`/`road_pass.py` on 1882 reproduce `water-1006337f.png`/`road-a3b0458f.png` bit-identically (`cmp`)
  - `seg_eval.py --self-check` and `clean_blocks.py --self-check` pass
  - `ocr.py --help` and the worker `--once` with no jobs exit cleanly
  - `npm run check` and `npm run test` are green
  - `grep -rn "work/ocr/outputs\|analysis/river_ref\|ocr/scripts/colour_blocks"` finds no live hits
- **Phase 1:** `mask_to_footprints.py --self-check`; the dry-run GeoJSON overlaid on the sheet; polygons in review; after approval, the export returns them.
- **Phase 2:** both methods scored once on both new windows, numbers recorded before anything is tuned.
- **Phase 3:** zero `needs_review` rows for 1882; `/explore` shows all four layers.
