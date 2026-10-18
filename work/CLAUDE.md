# work/ — the pipelines

Root context: `/CLAUDE.md`. What every folder here is: `work/README.md`; which layer owns it: `docs/ATLAS.md`.
The shared Python environment is `work/ocr/.venv`. The code
OCR, segmentation and the worker share is the `vma_core` package in `work/core/` (PR #67: IIIF tile
fetching, georef maths, Supabase transport); the old `work/ocr/scripts/{iiif_tiles,scale,supabase_client}.py`
are re-export shims. Core imports nothing from `ocr`, segmentation or `worker` — see
`work/core/README.md`. `ocr/outputs` and `ocr/logs` are temporary compatibility
links pending the reference audit in `docs/plans/image-processing-1882-plan.md`.
Full command reference and design rationale: `work/ocr/README.md` (OCR), `work/worker/README.md`,
`work/MapSAM2/README.md`; the index of every tool is `docs/guides/pipelines.md`.
§*Getting more out of OCR* there is the ranked list of what to do next and what not to re-attempt;
`work/ocr/EVAL-BASELINE.md` is the measured gate behind it.

## The worker (`work/worker/vma_worker.py`)

Claims `pipeline_jobs` via the `claim_job` RPC (`FOR UPDATE SKIP LOCKED`) and shells out to the
pipeline scripts. Run it wherever the venv lives:

```bash
source work/ocr/.venv/bin/activate
python work/worker/vma_worker.py --worker $(hostname)   # poll forever (ocr + join)
python work/worker/vma_worker.py --once                 # drain one job
```

`--kinds` decides what it takes, and the default is **everything this machine can run**:
`ocr`/`join`/`layout` locally, `mirror_annotation`/`sync_allmaps`/`warp` claimed and handed to
`/api/pipeline/execute`, and `tile_to_r2` (via `scripts/tile_map.sh`) only when vips + rclone are on
PATH. `seg` is opt-in — it runs where a GPU is, which means a Colab notebook running this same
worker with `--kinds seg`. A worker left running therefore finishes what publishing enqueues.

It needs `VMA_API_URL` + `VMA_WORKER_KEY` and **no database credentials** — claim and results both
go through `/api/pipeline/*`. The worker exports both into the job's subprocess, so `ocr.py --db`
writes the same way (`vma_core/db.py` switches transport on those two variables; the
analysis-only subcommands still use the service key when run by hand). The `seg` runner's flags
mirror `segCommand.ts`, and `MAPSAM2_DIR` / `MAPSAM2_CHECKPOINT` come from the machine's environment
rather than the job.

## OCR (`work/ocr/`)

Gemini Flash → `ocr_labels`; `join_labels.py` writes the `footprint_id` join (mig 050).
Own venv at `work/ocr/.venv`. `EVAL-BASELINE.md` is the measured quality gate.

## MapSAM2 (`work/MapSAM2/`)

Fine-tuned SAM2 fork (LoRA, training notes) in `TECHNICAL.md` + `VMA_SETUP.md`. IIIF tiles →
polygons → `footprints`. `--mode prompted --ocr-run-id <run>` seeds SAM2 from OCR boxes
via `to_sam2_seeds.py` (area categories only, one owner per seed by centroid, clipped to the tile);
those polygons are written with the label already attached. Runs on Colab against an upstream clone;
there is no local venv for it.

Its polygons and `ocr_labels.global_*` share **one full-image pixel grid** (both scale
tile-render → source px and offset by the tile origin, off the same `info.json`), which is what
makes the OCR ↔ shape join possible; tile sizes differ and do not matter.
