# work/ — the pipelines

Root context: `/CLAUDE.md`. Full command reference and design rationale: `docs/pipelines.md`.
§*Getting more out of OCR* there is the ranked list of what to do next and what not to re-attempt;
`work/ocr/EVAL-BASELINE.md` is the measured gate behind it. `scripts/` holds the living operator
scripts; `scripts/oneoff/` the backfills that have already run and stay only as a record.

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
writes the same way (`supabase_client.py` switches transport on those two variables; the
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
makes the C1 join possible; tile sizes differ and do not matter.

(The legacy `scripts/vectorize.py` colour-profile pipeline was removed — MapSAM2 supersedes it, and
`work/vectorize/` is gone from the tree.)
