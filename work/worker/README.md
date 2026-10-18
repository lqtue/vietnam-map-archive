# The worker

For whoever runs or changes the job worker. Kind: guide.
Moved here from `docs/guides/pipelines.md` on 2026-10-17, word for word.

## The worker (`work/worker/vma_worker.py`)

Since migration 053 the app does not run a pipeline itself: "Run OCR" writes a `pipeline_jobs` row,
and a worker claims it. Everything below still runs by hand — the worker only assembles the same
command lines from a job payload.

```bash
source work/ocr/.venv/bin/activate
python work/worker/vma_worker.py --kinds ocr --worker $(hostname)  # poll forever
python work/worker/vma_worker.py --once                            # drain one job, exit
python work/worker/vma_worker.py --once --python /usr/bin/true     # exercise the loop, run nothing
```

Claiming goes through the `claim_job(kinds, worker)` RPC, which is a single
`UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED LIMIT 1)`: several machines can poll the same
kinds with no coordination. `finish_job(id, status, result, error)` closes a job out, and a failure
with `attempts < max_attempts` goes back to `queued` instead of `failed`, so a worker dying mid-run
costs one retry rather than the job.

The worker holds **no database credentials**: it authenticates with a `worker_keys` token against
`/api/pipeline/claim` and `/api/pipeline/results`, so a compromised pipeline machine can write
extractions and close its own jobs, nothing else.

```bash
node --env-file=.env scripts/mint-worker-key.mjs macbook-m1     # prints the token once
# on the worker machine's .env:
VMA_API_URL=https://maparchive.vn
VMA_WORKER_KEY=<token>
```

The worker exports both variables into each job's subprocess, so `ocr.py … --db` posts its rows
through the same endpoint — `supabase_client.py` picks its transport from them. Run by hand without
those variables, it falls back to PostgREST with the service key, which is what `clean`,
`join_labels` and `eval` still use.

`seg` has a runner too, but its machine is not normally a laptop: MapSAM2 wants a GPU, so the
intended host is a Colab notebook running this same worker with `--kinds seg`. A GPU session becomes
a worker, and the Segmentation panel's command stops being something a human copies by hand. Its
flag set mirrors `segCommand.ts` — keep the two in step. `MAPSAM2_DIR` and `MAPSAM2_CHECKPOINT` come
from the environment, because they describe the machine rather than the job; a job payload may
override either.

`--write-supabase` writes `pixel_polygon` (the outer ring, full-image source px — the same grid
`ocr_labels.global_*` uses), `confidence` from SAM2's IoU, `source='sam-auto'` and the run id.
Holes are dropped: the column holds one ring. Before migration 055/057 this path could not insert at
all — it posted three columns that do not exist and a `source` the check constraint refused.

The scripts no longer report a pipeline stage — `update_pipeline_status()` is a stub since migration
056, because `map_pipeline_status` is a view over the job queue. Opening and closing the job *is*
the stage change.

`work/ocr/EVAL-BASELINE.md` records the measured quality gate. (Two hand-drawn companion diagrams
used to live here; they went stale faster than the pipeline changed and were deleted — this file is
the reference.)

Measured quality gate + the one recorded negative result: **`work/ocr/EVAL-BASELINE.md`**. Read it
before changing anything in the core loop.
