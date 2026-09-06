# Pipelines

Pipelines that live outside the SvelteKit app. Each section is the canonical reference — CLAUDE.md only links here.

## The worker (`work/worker/vma_worker.py`)

Since migration 053 the app does not run a pipeline itself: "Run OCR" writes a `pipeline_jobs` row, and a worker claims it. Everything below still runs by hand — the worker only assembles the same command lines from a job payload.

```bash
source work/ocr/.venv/bin/activate
python work/worker/vma_worker.py --kinds ocr --worker $(hostname)  # poll forever
python work/worker/vma_worker.py --once                            # drain one job, exit
python work/worker/vma_worker.py --once --python /usr/bin/true     # exercise the loop, run nothing
```

Claiming goes through the `claim_job(kinds, worker)` RPC, which is a single `UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED LIMIT 1)`: several machines can poll the same kinds with no coordination. `finish_job(id, status, result, error)` closes a job out, and a failure with `attempts < max_attempts` goes back to `queued` instead of `failed`, so a worker dying mid-run costs one retry rather than the job.

The worker holds **no database credentials**: it authenticates with a `worker_keys` token against `/api/pipeline/claim` and `/api/pipeline/results`, so a compromised pipeline machine can write extractions and close its own jobs, nothing else.

```bash
node --env-file=.env scripts/mint-worker-key.mjs macbook-m1     # prints the token once
# on the worker machine's .env:
VMA_API_URL=https://maparchive.vn
VMA_WORKER_KEY=<token>
```

The worker exports both variables into each job's subprocess, so `ocr.py … --db` posts its rows through the same endpoint — `supabase_client.py` picks its transport from them. Run by hand without those variables, it falls back to PostgREST with the service key, which is what `clean`, `join_labels` and `eval` still use.

`seg` has a runner too, but its machine is not normally a laptop: MapSAM2 wants a GPU, so the intended host is a Colab notebook running this same worker with `--kinds seg`. A GPU session becomes a worker, and the Segmentation panel's command stops being something a human copies by hand. Its flag set mirrors `segCommand.ts` — keep the two in step. `MAPSAM2_DIR` and `MAPSAM2_CHECKPOINT` come from the environment, because they describe the machine rather than the job; a job payload may override either.

`--write-supabase` writes `pixel_polygon` (the outer ring, full-image source px — the same grid `ocr_extractions.global_*` uses), `confidence` from SAM2's IoU, `source='sam-auto'` and the run id. Holes are dropped: the column holds one ring. Before migration 055/057 this path could not insert at all — it posted three columns that do not exist and a `source` the check constraint refused.

The scripts no longer report a pipeline stage — `update_pipeline_status()` is a stub since migration 056, because `map_pipeline_status` is a view over the job queue. Opening and closing the job *is* the stage change.

`work/ocr/EVAL-BASELINE.md` records the measured quality gate. (Two hand-drawn companion diagrams used to live here; they went stale faster than the pipeline changed and were deleted — this file is the reference.)

Measured quality gate + the one recorded negative result: **`work/ocr/EVAL-BASELINE.md`**. Read it before changing anything in the core loop.

## OCR (`work/ocr/`)

Gemini Flash vision pipeline that extracts toponyms, street names, and institutional labels from IIIF map tiles. Uses `google-genai` with structured JSON output.

**There is no repo-root `.venv`.** The only venv in the tree is `work/ocr/.venv` (see *Local passes* below for how it is created); it also serves the Gemini passes once `google-genai` is installed into it.

```bash
source work/ocr/.venv/bin/activate

# Single tile
python work/ocr/scripts/ocr.py run \
  --map-id <uuid> --iiif-base <url> \
  --crop x,y,w,h --render-size 2048 --prompt v8 \
  --run-id <name> --preview

# Full-map macro scan (scout pass, no crop)
python work/ocr/scripts/ocr.py scout --map-id <uuid> --iiif-base <url> --run-id <name>

# Batch over all tiles (row-sequence is ON by default)
python work/ocr/scripts/ocr.py batch --map-id <uuid> --iiif-base <url> --scout --run-id <name> [--db]

# Fuzzy dedup + spatial fragment join → ocr_extractions
python work/ocr/scripts/ocr.py clean \
  --local work/ocr/outputs/<map-id>/runs/<run-id> \
  --map-id <uuid> --run-id <clean-run-id> --min-confidence 0.1 [--apply]
```

Subcommands (11): `run`, `batch`, `scout`, `stitch`, `clean`, `dedup`, `preview`, `list-models`, `detect-layout`, `numerals`, `legend`.

**Model.** `gemini_client.DEFAULT_MODEL` is `gemini-3.8-flash` ($0.75/$3.75 per 1M in/out) since 2026-09-04; it was `gemini-3-flash-preview`, which still answers but is absent from Google's pricing page — no published rate, no stated support window. `--model` overrides per run, an `ocr` job payload's `model` overrides per job (the worker passes it through), and `scripts/enqueue_ocr_all.mjs --model NAME` sets it for a whole batch. Measured on this corpus at 5,156 in / 1,810 out tokens per call and 30–60 calls per sheet, that is roughly $0.50 a map, or $0.06 on `gemini-2.5-flash-lite`. Rate limits are no longer published per model — read them at <https://aistudio.google.com/rate-limit>. `GEMINI_API_KEYS` (comma-separated) rotates keys when one hits its daily cap; `GEMINI_API_KEY` is the single-key fallback.

**Reading an R2-hosted map.** `fetch_crop` asks for an arbitrary region at an arbitrary scale; `worker/` renders nothing and serves only the tiles `vips dzsave` wrote, so every such request 404s and, until 2026-09-04, OCR failed on its first tile for all 39 georeferenced maps. `fetch_crop_level0` composes the region from the pyramid instead: scale factor from `scaleFactors` (degrading if the top one was advertised but never written), origin a multiple of `tile_size · sf`, region clipped to the image, and rendered `size = ceil(region_w / sf)` — a constant `256,` 404s on clipped edge tiles. `info.json` claims `profile: level2`; it is not, do not trust that field. `iiif_tiles.py --self-check` covers the addressing.

**Overview resolution matters more than it looks.** `compute_tile_densities` measures local 8×8 std-dev, which at a heavy downscale reads dense city hatching as *smooth*. Measured on the 1882 Saigon cadastral, centre-tile vs edge-tile mean density was inverted at 600, 1024, 1513 and 1700px and only correct at 2048 — so `--auto-priority` on the old 1024px overview demoted the densest, most label-rich tiles. `OVERVIEW_WIDTH = 2048` in `ocr.py`; do not lower it. The companion colour/wash pass scored 0.000 on every tile of that sheet at every saturation gate, because its hue bands (60–260°) miss a warm-toned scan entirely — treat it as unmeasured.

**The layout pass.** `scout` returns `regions`: one labelled rectangle per part of the sheet — `sheet`, `main_map`, `title`, `legend`, `name_list`, `inset`, `scale_bar`, `north_arrow`, `stamp`. A sheet is not one thing, and tiling all of it reads the legend as if it were terrain, paying full price to OCR a key. `--save-triage` writes them to `maps.triage.regions` (migration 070) in source pixels, where `/scan?mode=triage` draws them for a person to correct — the model proposes, a human decides, and a corrected region is marked `source: 'human'`.

Run it as a job (`kind = 'layout'`, the worker's default set) rather than by hand: the digitalize **Detect** button enqueues one and polls. `--save-triage` merges rather than replaces, so a re-run cannot discard somebody's neatline.

The payoff is `main_map`. `enqueue_ocr_all.mjs` crops to it in preference to the neatline, because the neatline is the *printed border* — a legend or a street index printed inside the border is inside the neatline too, and gets tiled at full resolution for nothing.

**Queueing a batch.** `scripts/enqueue_ocr_all.mjs` queues only sheets with a saved triage in `maps.triage` (migration 069) — the neatline, tile size, overlap and per-tile priorities someone set in `/scan?mode=triage` and pressed **Save triage** on — and spreads them into the payload unchanged. A triaged sheet therefore runs with `--crop` and no scout pass, because there is nothing left to guess. `--untriaged` also queues the rest, which fall back to `--scout` and the defaults; `--dry` prints the split first.

**Two things mean "neatline" and they land in the same payload field.** `enqueue_ocr_all.mjs` means the sheet's own printed border, read from `maps.triage`. `scripts/collection_aoi.mjs` means a study area, computed from an AOI polygon through the inverse georeference — which is why it queued all six District 4 sheets while zero of them carried a saved triage. Both are correct and neither reads the other. Unify them only with that distinction in hand.

`--auto-priority` fills the Triage grid without a human: text density decides blank → skip and sparse → low_res, then a colour pre-pass (`compute_tile_colours`, HSV) demotes any tile that is mostly water or vegetation wash one further step. Demotion only — a misread wash costs resolution, never a tile — and a monochrome scan scores ~0, so nothing happens on grey maps. `--wash-above` (default 0.6) is the threshold.

Useful `batch` flags: `--row-sequence` / `--no-row-sequence` (default on, `--max-row-frames 4`), `--adaptive`, `--target-calls N`, `--smart-grid`, `--skip-sparse`, `--auto-priority`, `--wash-above`, `--aoi-px x0,y0,x1,y1`, `--tile-overrides '{"x_y_w_h":"skip|low_res"}'`, `--crop x,y,w,h`, `--prior-run <dir>`, `--legend`, `--db`.

`--aoi-px x0,y0,x1,y1` limits a run to a study area (District 4 is the first one). It takes **source-image pixels, not lng/lat**: the Allmaps georeference lives on the JS side (`src/lib/server/transformer.ts`), so the caller warps the four WGS84 corners with `GcpTransformer.transformToResource` and passes the pixel bbox. `--aoi` exists only to fail with that instruction. The filter runs *after* `--auto-priority` / `--tile-overrides`, and only ever demotes: a tile overlapping the AOI keeps whatever priority it had, a tile outside becomes `skip`, and a tile straddling the boundary counts as inside. So an AOI covering the whole map changes nothing.

`--clahe` turns on an adaptive-contrast pre-pass before a tile's bytes reach the model. Faded colonial scans lose their thin hand-lettered toponyms into the paper: locally the ink-to-paper gap is a handful of grey levels while the sheet still spans the full range, so a plain histogram stretch does nothing and CLAHE equalizes per region instead. `--clahe-clip` (default 2.0) caps the amplification so flat paper between strokes does not become noise; `--clahe-grid` (default 8, or `RxC`) sets the region grid. It runs on **luminance only** — equalizing per RGB channel would move hue and saturation, and `compute_tile_colours` scores the water and vegetation wash in HSV. It is also applied after both tile caches and after the shared overview the colour pass reads, so the caches keep raw pixels, an A/B run reuses the same cached tiles, and the wash scores are structurally out of reach.

**Off by default, and it must stay off until it is measured.** The idea is borrowed from Pastmaps, which runs adaptive contrast on every sheet so computer vision can read faded copperplate, but borrowed practice is not evidence about *our* corpus. To measure it, run the eval set both ways against the ground truth in `work/ocr/EVAL-BASELINE.md`:

```bash
python work/ocr/scripts/eval.py --run-id baseline-noclahe
python work/ocr/scripts/eval.py --run-id baseline-clahe --clahe
```

Default it on only if recall improves and precision does not fall — a pre-pass that finds two more street names while inventing three is a loss. Record the numbers in `EVAL-BASELINE.md` either way, including a null result, so nobody re-runs this experiment blind.

### Files (`work/ocr/scripts/`)

| File | One line |
| --- | --- |
| `ocr.py` | The CLI: `scout`, `batch`, `layout`, the local passes, `--db` writes. Everything below is a helper it imports |
| `gemini_client.py` | Gemini wrapper: key rotation across `GEMINI_API_KEYS`, retries, model default |
| `prompt.py` | Versioned prompts `v1`–`v8` + scout, the JSON schemas, and the canonical coordinate contract |
| `iiif_tiles.py` | IIIF tile fetcher and grid utilities: scale levels, level0 addressing, colour pre-pass, CLAHE. `--self-check` |
| `local_vision.py` | Offline passes with no API call (geometry, digits) that run free on the M-series |
| `cache.py` | Disk cache for Gemini results keyed by SHA256(image + prompt + model + schema version) |
| `supabase_client.py` | DB access with two transports: worker API (`VMA_API_URL` + key) or service key when run by hand |
| `join_labels.py` | Level-aware label ↔ footprint join (writes `footprint_id`). `--self-check` |
| `dictionary.py` | Offline gazetteer of every name read so far → `outputs/dictionary.{json,md}`. `--self-check` |
| `eval.py`, `eval_metrics.py` | The quality gate: score an OCR or seg run against reviewed ground truth. Baseline in `EVAL-BASELINE.md` |
| `backfill_full800.py` | One-off: store the `full/800,` derivative in R2 for every published map. `--self-check` |
| `fix_info_scalefactors.py` | One-off: drop scale factors a stored `info.json` advertises but the pyramid does not hold. `--self-check` |

### Local passes (no API — run on the M-series for free)

Two subcommands offload the geometry/digit parts of map OCR to local tools, keeping Gemini for semantic text (place names, legend descriptions). Both live in `work/ocr/scripts/local_vision.py`.

They need only `numpy`, `scipy`, `Pillow`, `pytesseract` + the `tesseract` binary (`brew install tesseract`) — **not** `google-genai`. The venv is created with `--system-site-packages` to reuse brew numpy/scipy/PIL, since Homebrew Python is PEP-668 externally-managed:

```bash
python3 -m venv --system-site-packages work/ocr/.venv
work/ocr/.venv/bin/pip install pytesseract

# Find legend/cartouche/title boxes (scipy ruled-rectangle finder)
work/ocr/.venv/bin/python work/ocr/scripts/ocr.py detect-layout \
  --map-id <uuid> --run-id <name>          # → runs/<name>/layout.json (legend_region boxes)

# Spot standalone numerals / legend refs (Tesseract, digit whitelist)
work/ocr/.venv/bin/python work/ocr/scripts/ocr.py numerals \
  --map-id <uuid> --run-id <name> [--db]   # → runs/<name>/numerals.json; --db writes category='legend_ref'
```

- `detect-layout` finds **bordered** boxes only; borderless legends fall back to a manual region or the whole-image legend pass. The regions feed the (Gemini) structured `legend` pass.
- `numerals` writes `category='legend_ref'` rows — a later join `legend_ref.text == legend_entry.number` links each map numeral to its legend entry (pure SQL, no model).
- `legend` (Gemini) reads a numbered legend region into `{n, name, grid}` rows: `--region x,y,w,h` required; `--bilingual`, `--consensus N` (cross-check across N models and flag disagreements), `--db` → `category='legend_entry'`.
- All three accept `--local-image <path>` to skip IIIF entirely. Self-check: `work/ocr/.venv/bin/python work/ocr/scripts/local_vision.py`.
- **Known limit:** Tesseract single-digit recall is mediocre (rotated glyphs missed). Upgrade path if recall is too low — swap `spot_numerals()` for a PaddleOCR detector in a Python 3.11 venv, keeping the same `[{text, bbox, confidence}]` shape.

### Name dictionary

```bash
python work/ocr/scripts/dictionary.py            # → outputs/dictionary.{json,md}
python work/ocr/scripts/dictionary.py --self-check   # asserts only, no DB
```

One entry per distinct name across the whole corpus, with every sighting (map, year, run, confidence, source pixel). An offline artefact for review: OCR errors that are invisible one bbox at a time are obvious in an alphabetical list. `--min-confidence`, `--category` (repeatable), `--include-rejected`, `--include-furniture` (title/legend/other, excluded by default).

Diacritics are **not** folded — "Sài Gòn" and "Sai Gon" are different readings and the difference is the point. Entries whose only difference is accents are cross-linked in a "Same name, other accents" column instead, because a French label printed in caps loses its accents on the sheet itself. The `place_names` view (mig 067) makes the opposite call and folds them; it is the gazetteer of record, and ROADMAP item 4b is to rebuild this script on top of it rather than keep two normalisation rules.

### Label ↔ footprint join

```bash
python work/ocr/scripts/join_labels.py <map-id>       # link
python work/ocr/scripts/join_labels.py --self-check   # PIP + nesting assertions, no DB
```

Point-in-polygon assignment of each `ocr_extractions` row to the `footprint_submissions` polygon it names, writing `ocr_extractions.footprint_id` (migration `050_ocr_footprint_link.sql`, `ON DELETE SET NULL`). Level-aware: a bare numeral routes to a `building`, a name routes to the enclosing block; ties break to the **smallest** containing polygon. Rejected extractions never link; `category_validated` (the human fix) wins over `category`.

### Design notes

- Gemini bboxes are **0–1000 normalized space**; render with `img_dim / 1000`.
- `ocr_extractions.global_x/y/w/h` already store full-image pixel coords.
- Model: `DEFAULT_MODEL = "gemini-3-flash-preview"` (`work/ocr/scripts/gemini_client.py`), overridable per-subcommand with `--model`. Key in `.env` as `GEMINI_API_KEY` / `GEMINI_API_KEYS` (comma-separated for rotation). `ocr.py list-models` enumerates what the key can actually reach.
- Outputs versioned at `work/ocr/outputs/<map_id>/runs/<run_id>/` with `run_config.json` for reproducibility.
- Prompts `v1`–`v8` + scout in `work/ocr/scripts/prompt.py`. **`DEFAULT_PROMPT = "v8"`** (high-recall, no confidence floor). V6 introduced a 0.5 confidence floor that crushed recall; v8 reverts it.
- `clean` writes to `ocr_extractions` (correct target for the digitalize review UI); legacy `dedup` writes to `label_pins`.

Scripts: `ocr.py` (CLI), `gemini_client.py` (key rotation + retries), `iiif_tiles.py` (crop fetch, IA fallback, IIIF v2/v3 detection), `supabase_client.py` (direct REST), `prompt.py`, `local_vision.py`, `join_labels.py`, `eval.py` + `eval_metrics.py`, `cache.py`.

## MapSAM2 inference (`work/MapSAM2/`)

SAM2/MapSAM2 segmentation: IIIF tiles → masks → polygons → `footprint_submissions`. Colab (GPU) or local M1 (base SAM2 only).

No venv is checked in or currently set up for this pipeline — create one per your platform and install the SAM2 deps. Training/LoRA details, the paper reading and the improvement backlog are in **`work/MapSAM2/TECHNICAL.md`**; Colab config is in `work/MapSAM2/VMA_SETUP.md`.

```bash
# Local test (base SAM2, small region)
python work/MapSAM2/inference_tiles_as_video.py \
  --map-id <uuid> --checkpoint /path/to/sam2.1_hiera_small.pt \
  --region 4800,4300,1024,1024 --out-json test.json --preview

# Full Colab run with LoRA + OCR seeds + Supabase write
python work/MapSAM2/inference_tiles_as_video.py \
  --map-id <uuid> --checkpoint /path/to/mapsam2_lora.pth \
  --lora --mapsam2-dir /content/MapSAM2 \
  --mode prompted --ocr-run-id <run_id> \
  --tile-size 1024 --overlap 128 --text-mask --watershed \
  --out-json footprints.json --write-supabase

# Evaluate (SODUCO F1=0.59 baseline)
python work/MapSAM2/evaluate.py --predictions footprints.json --map-id <uuid> [--iou-thresholds 0.5,0.75]
```

Key flags: `--mode automatic|prompted`, `--lora`, `--encoder vit_s`, `--mapsam2-dir` (path to the **upstream** MapSAM2 clone), `--text-mask` (erase OCR bbox regions), `--watershed` (Meyer post-processing), `--region x,y,w,h`, `--device cpu|cuda|mps`.

Modes: `automatic` = SAM2AutomaticMaskGenerator grid-scan; `prompted` = SAM2ImagePredictor with OCR bbox seeds (requires `--ocr-run-id`; best with LoRA).

Scripts: `inference_tiles_as_video.py` (orchestrator; `--write-supabase` also advances `map_pipeline_status` seg_queued → seg_done), `masks_to_polygons.py` (`mask_to_polygon`, `masks_to_polygons` IoU dedup, `shift_polygons`), `evaluate.py` (F1 + geometric quality vs `footprint_submissions` status=verified).

Polygons written to `footprint_submissions.coords` as `[[x,y],...]` pixel-space arrays.

## Pipeline stages (`map_pipeline_status.stage`)

`idle → ocr_queued → ocr_done → reviewed → seg_queued → seg_done → seg_reviewed → exported`

Advances automatically when OCR batch (`--db`) or SAM2 inference (`--write-supabase`) writes. Manual transitions via PATCH `/api/admin/maps/[id]/pipeline`.

## Eval harness (`work/ocr/scripts/eval.py`)

The gate for any core-pipeline change: baseline, refactor, compare. Scores a run against the ground truth the HITL review already produces — validated OCR extractions and verified footprints — so no separate labelling step is needed. Needs `shapely` (seg polygon IoU) + `requests`; `eval_metrics.py` holds the pure scorers (self-check: `python work/ocr/scripts/eval_metrics.py`).

```bash
# OCR: a run's raw extractions vs human-validated rows (box IoU + char-acc)
python work/ocr/scripts/eval.py ocr --map-id <uuid> --run-id <run> [--iou 0.5]

# Seg: predicted footprints vs verified/consensus footprints (polygon IoU)
python work/ocr/scripts/eval.py seg --map-id <uuid> \
  [--pred-status submitted] [--gt-status verified,consensus] [--iou 0.5]

# Offline, no DB — score two JSON files directly
python work/ocr/scripts/eval.py ocr --pred-file p.json --gt-file g.json
```

Reports precision / recall / F1 / mean IoU (+ char-acc for OCR). Reads only, never writes. Distinct from `work/MapSAM2/evaluate.py`, which scores a `predictions.json` against a map rather than against DB ground truth.

**Recorded numbers and the one rejected experiment live in `work/ocr/EVAL-BASELINE.md`** — baseline recall/char-acc/mean-IoU on map `0e02b9d9…`, why `precision` on a partial ground-truth set is not trustworthy, and why neighbour-window batching was built, measured (−16 pts recall) and reverted. Row-sequence stays the default.

---

# Design rationale

Why the two pipelines are shaped the way they are, and what the intended end state is. Merged here from two now-deleted notes — `work/PIPELINE_INTEGRATION.md` (MapSAM2 paper reading, Xia et al. 2025, arXiv:2510.27547) and `work/ocr/TECHNICAL.md`; recover the originals from git history if needed. Historical — parts have shipped, parts have not; the *Status* lines say which.

## Tiles-as-video

The MapSAM2 paper's unifying insight: treat a set of static tiles from one map as a **video**, so SAM2's memory attention shares context across tiles instead of segmenting each in isolation. The paper measures memory attention alone at **+14.3% IoU on vineyards, +16.1% on railways**.

**Status: shipped in shape, not in mechanism.** `inference_tiles_as_video.py` is the VMA entry point and tiles the region sequentially, but still runs SAM2's default FIFO memory. The paper's **self-sorting memory bank** (MedSAM-2, Zhu et al. 2024) is the open change:

- admit candidate embedding `E_t` if IoU confidence `c_t` > threshold;
- keep the top-`K` most **dissimilar**, `D_i = Σ_{j≠i}(1 − sim(E_i, E_j))`, `M_t = TopK(D_i)`;
- for the next tile `F_{t+1}`, resample the top-`k` most **similar**, `p_{i,t} ∝ sim(F_{t+1}, E_i)`.

Highest single-change EV in the backlog, and the most complex.

## Gemini as the prompt source

The paper uses a fine-tuned YOLO to produce instance-level bbox prompts, and shows prompt quality is worth **+12.8% F1** (holding the segmenter fixed, varying only YOLO's training size). VMA substitutes Gemini:

- open-vocabulary, no training, several categories in one call;
- returns the **text** as well as the box — one call, two signals, so OCR and prompt generation are the same pass;
- on a corpus of ~46 annotated Saigon footprints, a 10-shot YOLO is the weaker option.

**Status: shipped.** `--mode prompted --ocr-run-id <run>` seeds SAM2 from `ocr_extractions` bboxes. `--text-mask` erases those regions from the image so label ink is not segmented as building.

The reverse direction closes the loop: once polygons exist, `join_labels.py` assigns each label to the polygon it names (migration 050). Bidirectional — labels prompt the segmenter, footprints then claim the labels.

## Ordering the sequence

Spatial ordering on the Gemini side is the cheap analogue of the paper's self-sorting memory: order tiles so dense urban-core frames come first and sparse edge tiles inherit accumulated context.

**Status: partially shipped, and one variant measured and rejected.** `batch --row-sequence` (default on, `--max-row-frames 4`) sends each row-strip as one sequence call to `extract_labels_sequence()`. A denser ordering was never implemented. The adjacent idea — reading each tile together with its four grid neighbours — *was* built, measured and reverted; see EVAL-BASELINE.md for the numbers and the two root causes (bad `frame_idx` attribution; centroid ownership leaking inside the 300px overlap band).

## Coarse → fine

`scout` reads the whole map at low resolution to find the neatline and the dense regions; `batch` then tiles only the content area (`--smart-grid`, `--crop`, `--auto-priority`, `--wash-above`, `--skip-sparse`) at full resolution.

**"Full resolution" is `tile_size / render_size`, and the default is not 1:1.** A tile is `--tile-size` source pixels rendered to `--render-size` before the model sees it, so what Gemini reads is the sheet's own ground resolution times that ratio. The stock 2400/1024 is a 2.34x downsample *on top of* the scan: on the 1959 Đô thành Sài Gòn sheet (2.80 m/px source) it delivers 6.5 m/px, which cannot resolve a street name. Until 2026-09-04 `vma_worker.py` did not pass `--render-size` at all, so **every queued OCR job ran at that ratio regardless of payload** — set `render_size` in the payload now, equal to `tile_size` for 1:1. Nothing above 1:1 buys real detail; past it the scan is the ceiling. Rendering 1:1 costs tiles, which is what cropping to a study area pays for — see `work/analysis/district4/README.md` for the worked case.

**But resolution was the smaller half.** Measured on the 1959 Đô thành Sài Gòn sheet, same crop and same 1:1 rendering, changing only `--tile-size` and counting distinct labels that warp back inside the study area: 2048 px (5.7 km of ground per call) found 1; 1024 px (2.9 km) found 2; ~500 px (1.4 km) found 6, and 5 on a repeat. Five to six times the yield off an unchanged scan, and only the finest runs read `QUẬN 4` printed on the sheet. Across a whole six-sheet collection the same change gave **+19%**, not 5x — the gain appears only where the ground per call actually drops a lot, and repeats of one configuration differ by a label or two, so do not read a single run's small difference as a result. Rendering was ruled out separately — 1024 px rendered 1:1 and at 2x gave byte-identical output, so upsampling past the scan buys nothing. **What starves a read is one call covering too much ground, and a fixed pixel tile is a different amount of ground on every sheet** (2048 px is 1.7 km on the 1923 sheet, 5.7 km on the 1959 one). That is why coarse sheets look empty and get blamed on their scans. `scripts/collection_aoi.mjs --tile-metres` (default 1400) sizes the tile per sheet from its own m/px; `enqueue_ocr_all.mjs` still takes a fixed `--tile-size` and would benefit from the same treatment. Density steers spend: `--adaptive` renders dense tiles at 2048 and sparse ones at 1024, `--target-calls` scales the grid to a call budget. The digitalize Triage UI writes the same decisions as `--tile-overrides`.

## Coordinate contract

Everything downstream of Gemini is **pixel space on the full source image**, which is also SAM2's input space and `footprint_submissions.pixel_polygon`'s space. Gemini returns 0–1000 normalized boxes per tile; `_to_global()` converts to full-image px; `ocr_extractions.global_x/y/w/h` stores that. Georeferencing to WGS84 happens later, via the Allmaps transform, not in the pipeline.

Note for anyone porting Google's spatial-understanding patterns: their notebook uses `[y_min, x_min, y_max, x_max]`; VMA's prompts document `bbox_px: [x, y, width, height]`. Calibrate before mixing the two.

## Prompt design decisions

1. **System prompt establishes map identity first** — priors for "French colonial Saigon 1882" are far stronger than for "historical map" generically.
2. **bbox within the tile** — coordinates relative to the submitted crop, directly compositable with SAM2 footprints (both pixel space).
3. **`rotation_deg`** — street labels on French cadastral maps follow the road axis; capturing the angle allows correct placement in the label overlay.
4. **`confidence`** — thresholds before human review. Surface everything ≥0.4 to HITL; auto-accept ≥0.85.
5. **`notes`** — deliberately free-form for model observations ("ink bleed", "partially occluded", "possibly Vietnamese transliteration").

The shipped category taxonomy is whatever `work/ocr/scripts/prompt.py` and the review UI's `OCR_CATEGORIES` agree on — including the pipeline-generated `legend_ref` and `legend_entry`. Do not treat any doc as the schema; read `prompt.py`.

## Known issues / risks

- **Hallucination on blank areas** — Gemini may invent text on featureless margin regions. Mitigate with confidence thresholding and a sanity check (extractions should be empty for blank tiles). `--skip-sparse` / `--auto-priority` avoid sending those tiles at all.
- **IIIF server rate limits** — archive.org throttles at ~10 req/s. The fetcher caches to `.tile_cache/` to avoid re-fetching.
- **Model IDs change** — Flash preview IDs get replaced or renamed. Run `ocr.py list-models` on first use of a new key.
- **French + quốc ngữ mix** — early French colonial maps use early Romanized Vietnamese transliterations. The model handles these but accuracy is lower.
- **Edge labels cut off** — a label straddling a tile boundary is read as two fragments; `clean` rejoins them spatially, and sequence mode assembles some of them in-model.

## Cost

Flash-tier vision is cheap enough that resolution, not budget, is the binding constraint: a full pass over one large map is cents, not dollars. Per-run token counts are recorded in each run's `run_config.json` — use those rather than any figure written down here, since both pricing and the default model change.

## POC acceptance criteria (historical)

The bar the POC was held to, before `eval.py` and EVAL-BASELINE.md replaced eyeballing: ≥80% of visible toponyms on a manually checked tile matched by an extraction; ≤10% of extractions hallucinated; extracted bbox overlapping the real text region by ≥50%. Superseded — use the eval harness.
