#!/usr/bin/env python3
"""vma-worker — claims pipeline_jobs and runs them.

Any machine with the OCR venv can run this; the queue decides who gets what.

    source work/ocr/.venv/bin/activate
    python work/worker/vma_worker.py --kinds ocr --worker macbook-m1
    python work/worker/vma_worker.py --once          # drain one job and exit

Claiming goes through /api/pipeline/claim, which runs the claim_job() RPC
(FOR UPDATE SKIP LOCKED) server-side, so running several workers against the
same kinds needs no coordination between them.

The worker holds no database credentials. It needs two variables, from the
environment or the repo-root .env:

    VMA_API_URL      https://maparchive.vn  (or http://localhost:5173 in dev)
    VMA_WORKER_KEY   minted by scripts/mint-worker-key.mjs

They are passed down to the pipeline scripts too, so ocr.py writes its rows
through the same endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]

# Ceiling on one step of a job. The slowest legitimate step is the 1200px OCR
# pass, about 30 minutes on a dense sheet; two hours leaves room for rate-limit
# backoff without letting a wedged child hold a worker for a day.
STEP_TIMEOUT_S = int(os.environ.get("VMA_STEP_TIMEOUT_S", str(2 * 60 * 60)))

# The job this worker holds, so a Ctrl-C can hand it back instead of stranding
# it. At most one: the loop runs a single job at a time.
_IN_FLIGHT: list[str] = []
OCR_SCRIPT = REPO_ROOT / "work" / "ocr" / "scripts" / "ocr.py"


OCR_OUTPUTS = REPO_ROOT / "work" / "ocr" / "outputs"

# `pricing` has no imports of its own, so this costs nothing and cannot fail on
# a missing PIL. If it somehow does, a run still reports calls and tokens — it
# just cannot enforce a money budget, and says so rather than silently passing.
sys.path.insert(0, str(REPO_ROOT / "work" / "ocr" / "scripts"))
try:
    from pricing import call_cost_usd
except ImportError:  # pragma: no cover
    call_cost_usd = None


def _spend(map_id: str, run_id: str | None) -> dict:
    """What a run actually cost, read off the `calls.jsonl` each run already writes.

    Every Gemini call appends a line with its tokens and how many extractions it
    returned, so cost needs no new plumbing — only summing. Without this the job
    row carried a returncode and a last line, so nothing downstream could see
    that a pass spent sixty calls to find four labels: measured on the 1959
    sheet, the margin index returned 9.8 rows per call and a quadrant re-sweep
    of the same sheet returned 0.07.

    The glob is a prefix because the two-pass recipe runs as `<run>-a`, `<run>-b`
    and merges into `<run>`.
    """
    if not run_id:
        return {}
    calls = tokens = extractions = unpriced = 0
    cost = 0.0
    for log in sorted(OCR_OUTPUTS.glob(f"{map_id}/runs/{run_id}*/calls.jsonl")):
        for line in log.read_text().splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # a half-written last line is not worth failing a job over
            calls += 1
            tokens += int(rec.get("total_tokens") or 0)
            extractions += int(rec.get("n_extractions") or 0)
            # `cost_usd` is written by gemini_client since 2026-09-14. Older
            # logs predate it and are recomputed from the tokens they do carry,
            # so a budget works the same against a run from last week.
            c = rec.get("cost_usd")
            if c is None and call_cost_usd is not None:
                c = call_cost_usd(rec.get("model"), rec.get("input_tokens"),
                                  rec.get("output_tokens"), rec.get("total_tokens"),
                                  rec.get("cached_tokens"))
            if c is None:
                unpriced += 1
            else:
                cost += c
    if not calls:
        return {}
    out = {"calls": calls, "tokens": tokens, "extractions": extractions,
           "per_call": round(extractions / calls, 2),
           "cost_usd": round(cost, 4)}
    # A model with no published rate contributes 0 to the total, which would
    # make a money budget quietly unenforceable. Name the calls instead.
    if unpriced:
        out["unpriced_calls"] = unpriced
    return out


def _config() -> tuple[str, str]:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
    url = os.environ.get("VMA_API_URL", "").rstrip("/")
    key = os.environ.get("VMA_WORKER_KEY", "")
    if not url or not key:
        sys.exit(
            "Set VMA_API_URL and VMA_WORKER_KEY (mint one with "
            "`node --env-file=.env scripts/mint-worker-key.mjs <name>`)"
        )
    return url, key


def _post(path: str, body: dict) -> dict:
    url, key = _config()
    resp = requests.post(
        f"{url}{path}",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        data=json.dumps(body),
        timeout=30,
    )
    if resp.status_code in (401, 403):
        sys.exit(f"worker key rejected: {resp.status_code} {resp.text[:200]}")
    resp.raise_for_status()
    return resp.json()


def execute(job_id: str) -> dict:
    """Ask the server to run a job whose work needs the service key."""
    return _post("/api/pipeline/execute", {"job_id": job_id})


def claim(kinds: list[str], worker: str) -> dict | None:
    return _post("/api/pipeline/claim", {"kinds": kinds, "worker": worker}).get("job")


def finish(job_id: str, status: str, result: dict | None = None, err: str | None = None) -> None:
    """Report a job's outcome, retrying a transport failure a few times.

    This runs at the end of a batch that may have taken 45 minutes, and it used
    to be a bare _post: one 502 from the edge raised straight out of run_job,
    past the main loop's try (which wraps claim only), and killed the worker —
    leaving the row in 'running' with the extractions already written. That is
    the same stranded state migration 077's reclaim now clears after three
    hours, but three hours late. Four tries over ~15s covers a redeploy.
    """
    body = {"job_id": job_id, "status": status, "result": result or {}, "error": err}
    for attempt in range(4):
        try:
            _post("/api/pipeline/results", body)
            return
        except requests.RequestException as e:
            if attempt == 3:
                print(f"could not report job {job_id} as {status}: {e}", file=sys.stderr)
                return
            time.sleep(2 ** attempt)


def ocr_argv(job: dict, python_bin: str) -> list[str] | list[list[str]]:
    """Turn an `ocr` job payload into the ocr.py batch command line.

    `passes: 2` returns a plan instead: the batch on the grid, the same batch
    with the grid moved half a tile, and `merge --db` to vote them into the
    payload's run_id. `passes: 3` adds a 1200 px pass for small type first. Measured 2026-09-08 on the 1882 sheet: 39/43
    for one pass, 41/43 for two — see work/ocr/EVAL-BASELINE.md.
    """
    p = job["payload"]
    # Default two, not one: the grid plus the half-tile-shifted grid, voted. It
    # read 41/43 against 39/43 for a single pass on the 1882 sheet, and both
    # enqueue paths asked for 2 explicitly — so a `1` here only ever meant "this
    # job row predates the recipe", never "single pass was chosen".
    if int(p.get("passes", 2)) >= 2:
        return _two_pass_plan(job, python_bin)
    return _ocr_batch_argv(job, python_bin, p["run_id"], db=True)


# The hi-res pass's own grid. Named because `passes: 3` is only meaningful when
# the run's tile_size is coarser than this.
HIRES_TILE = 1200
HIRES_OVERLAP = 150

# The render the model actually sees, when a job does not name one.
#
# One rule, one place. Before this the flat default lived here at 1024 while
# enqueue_ocr_all.mjs computed max(tile, 1024) and sent it, so the same sheet was
# read at 1:1 by the fleet script and at a 2.34x downsample by the Run OCR
# button — and every number in EVAL-BASELINE was measured at the button's
# setting. Equal to the tile is 1:1, the source ceiling; anything above only
# upsamples. The 1024 floor is there because a very small image is not what
# these prompts expect.
RENDER_FLOOR = 1024


def _render_size(payload: dict) -> int:
    return max(int(payload.get("tile_size", 2400)), RENDER_FLOOR)


def _default_prompt() -> str | None:
    """The prompt id `ocr.py` would pick, resolved here so the job records it.

    Neither enqueue path sent a `prompt`, so every queued run silently inherited
    whatever `DEFAULT_PROMPT` the worker's checkout happened to have — and with
    the two-pass recipe the passes run with --db off, so the prompt was written
    down nowhere at all. Naming it in a third place (the route, the fleet script)
    would just be three constants to drift; reading the one declaration and
    stamping it into the argv means the run's rows say what they used.

    Returns None if the OCR venv is not importable, which leaves the previous
    behaviour rather than failing the job.
    """
    try:
        sys.path.insert(0, str(REPO_ROOT / "work" / "ocr" / "scripts"))
        from prompt import DEFAULT_PROMPT  # type: ignore[import-not-found]

        return str(DEFAULT_PROMPT)
    except Exception:
        return None


def _two_pass_plan(job: dict, python_bin: str) -> list[list[str]]:
    p = job["payload"]
    run, tile = p["run_id"], int(p.get("tile_size", 2400))
    a = _ocr_batch_argv(job, python_bin, f"{run}-a", db=False)
    b = _ocr_batch_argv(job, python_bin, f"{run}-b", db=False) + ["--grid-offset", str(tile // 2)]
    passes = [a, b]
    if int(p.get("passes", 2)) >= 3:
        # A near-1:1 pass for small type. It read POSTE DE POLICE and MESSAGERIES
        # MARITIMES, which no 2400 px pass ever returned — and fragments the long
        # labels the 2400 passes read whole, so it only ever rides along, never
        # alone. Twice the tokens of the other two together, ~30 min more.
        #
        # Only when it is actually finer than the grid passes. enqueue_ocr_all
        # normalises tile_size to ground metres, so on a coarse sheet it may
        # already have chosen 1200 or less — and then this pass is a byte-for-byte
        # copy of pass a. That costs nothing in tokens (the tile cache answers it)
        # but it poisons the vote: the merge would see three voters where two
        # agree only because they are the same pass, inflating `n_passes` and
        # turning the three-voter tie-break back into the two-voter one that
        # dropped diacritic_recall to 0.864.
        if tile > HIRES_TILE:
            hires = _ocr_batch_argv(job, python_bin, f"{run}-c", db=False)
            for flag, val in (("--tile-size", str(HIRES_TILE)), ("--overlap", str(HIRES_OVERLAP))):
                hires[hires.index(flag) + 1] = val
            passes.append(hires)
        else:
            print(f"[ocr] passes:3 ignored — tile_size {tile} is already at or below "
                  f"the {HIRES_TILE}px hi-res pass, which would duplicate pass a")
    runs = ",".join(cmd[cmd.index("--run-id") + 1] for cmd in passes)
    merge = [python_bin, str(OCR_SCRIPT), "merge", "--map-id", job["map_id"],
             "--runs", runs, "--run-id", run, "--tile-size", str(tile), "--db"]
    return [*passes, merge]


def _ocr_batch_argv(job: dict, python_bin: str, run_id: str, db: bool) -> list[str]:
    p = job["payload"]
    argv = [
        python_bin,
        str(OCR_SCRIPT),
        "batch",
        "--map-id", job["map_id"],
        "--run-id", run_id,
        "--tile-size", str(p.get("tile_size", 2400)),
        "--overlap", str(p.get("overlap", 600)),
        # The one that decides whether a street name is legible. Each tile is
        # `tile_size` source pixels rendered down to `render_size` before the
        # model sees it, so the effective ground resolution is the sheet's
        # own m/px times tile_size/render_size. The defaults are 2400/1024 —
        # a 2.34x downsample on top of the scan, which put the 1959 Saigon
        # sheet in front of Gemini at ~6.5 m/px. Equal values are 1:1, the
        # source ceiling; larger only upsamples and buys nothing.
        "--render-size", str(p.get("render_size") or _render_size(p)),
        "--concurrency", str(p.get("concurrency", 3)),
        "--min-confidence", str(p.get("min_confidence", 0.5)),
    ]
    if db:
        argv.append("--db")
    # Left unset, every queued job silently inherits gemini_client.DEFAULT_MODEL,
    # which is invisible from the job row. Passing it explicitly means the run's
    # calls.jsonl and the payload agree about what was used.
    if p.get("model"):
        argv += ["--model", str(p["model"])]
    # Same reasoning as --model: unset, every job silently ran DEFAULT_PROMPT,
    # whatever that was on the day the worker started, and the rows never said.
    prompt_id = p.get("prompt") or _default_prompt()
    if prompt_id:
        argv += ["--prompt", str(prompt_id)]
    # Opt-in: blank water and margin tiles cost the same as dense ones.
    if p.get("skip_sparse"):
        argv.append("--skip-sparse")
    # Same story as --auto-priority below: the flag existed in ocr.py and no
    # enqueue path or worker ever passed it, so every queued job ran with full
    # thinking. Measured on 2026-09-13, thinking was 59% of billed output
    # tokens and 56% of the day's bill. It changes the answer as well as the
    # price, so it stays opt-in per job rather than becoming the default.
    if p.get("low_thinking"):
        argv.append("--low-thinking")
    # The measured density pass, computed on the grid actually being tiled. It
    # existed in ocr.py all along and no enqueue path or worker ever passed it,
    # so the automated runs paid full price for blank margin tiles. Safe to wire
    # in now for two reasons: the overview is 2048px (at 1024 the signal was
    # inverted and it demoted the densest tiles), and tests/density-parity.spec.ts
    # pins it to the browser implementation that was actually measured.
    if p.get("auto_priority"):
        argv.append("--auto-priority")
    neatline = p.get("neatline")
    if neatline:
        argv += ["--crop", ",".join(str(n) for n in neatline)]
    # The printed legend and street-index blocks, so the tile pass does not read
    # a directory line as a numeral on the map body.
    exclude = p.get("exclude") or []
    if exclude:
        argv += ["--exclude", ";".join(",".join(str(n) for n in r) for r in exclude)]
    if p.get("auto", True):
        if not neatline:
            argv.append("--scout")  # a drawn neatline already pins the crop
        argv.append("--legend")
    if p.get("target_calls"):
        argv += ["--target-calls", str(p["target_calls"])]
    if p.get("prior_run"):
        argv += ["--prior-run", str(p["prior_run"])]
    if p.get("tile_overrides"):
        argv += ["--tile-overrides", json.dumps(p["tile_overrides"])]
    return argv


def layout_argv(job: dict, python_bin: str) -> list[str]:
    """Turn a `layout` job into the scout command line.

    The layout pass is scout with `--save-triage`: one low-resolution look at the
    whole sheet, asking the model where the main map, title, legend, name list
    and furniture are, written to maps.triage.regions for a person to correct on
    the digitalize canvas. It is a job rather than a route because the Gemini key
    lives here and deliberately not in the web app.
    """
    p = job["payload"]
    argv = [
        python_bin,
        str(OCR_SCRIPT),
        "scout",
        "--map-id", job["map_id"],
        "--render-size", str(p.get("render_size", 2048)),
        "--save-triage",
    ]
    if p.get("run_id"):
        argv += ["--run-id", str(p["run_id"])]
    if p.get("model"):
        argv += ["--model", str(p["model"])]
    if p.get("preview"):
        argv.append("--preview")
    return argv


def tile_argv(job: dict, python_bin: str) -> list[str]:
    """Turn a `tile_to_r2` job into the tiling script's command line.

    scripts/tile_map.sh needs vips and rclone with R2 credentials, so this only
    runs on a machine set up for it — the default kinds include it only when
    both tools are on PATH (see default_kinds()).
    """
    iiif = job["payload"].get("iiif_image", "").rstrip("/")
    if not iiif:
        raise ValueError("tile_to_r2 job has no iiif_image in its payload")
    # Gallica serves the full image under a different quality name.
    download = f"{iiif}/full/full/0/native.jpg" if "gallica.bnf.fr" in iiif else f"{iiif}/full/max/0/default.jpg"
    return [str(REPO_ROOT / "scripts" / "tile_map.sh"), job["map_id"], download, iiif]


def seg_argv(job: dict, python_bin: str) -> list[str]:
    """Turn a `seg` job into the MapSAM2 inference command line.

    This is the one runner whose machine is normally not a laptop: MapSAM2 wants
    a GPU, so the intended host is a Colab notebook running this same worker
    with `--kinds seg`. A GPU session becomes a worker, and nothing has to be
    copy-pasted out of the Segmentation panel any more.

    The flag set mirrors `src/lib/features/contribute/digitalize/segCommand.ts`,
    which is what that panel shows a human — keep the two in step. With a
    validated OCR run or a colour-block prior makes the model run LoRA-prompted;
    without either it falls back to automatic mode, exactly as the panel does.

    ponytail: checkpoint and MapSAM2 directory come from the environment, since
    they are properties of the machine rather than of the job. A job may still
    override either in its payload.
    """
    p = job["payload"]
    mapsam2_dir = p.get("mapsam2_dir") or os.environ.get("MAPSAM2_DIR", "/content/MapSAM2")
    # The fallback is the checkpoint the April 2026 training run actually wrote,
    # kept in step with DEFAULT_SEG_CONFIG in segCommand.ts. It used to be
    # MyDrive/mapsam2_checkpoint.pth, which does not exist in the Drive it names.
    checkpoint = p.get("checkpoint") or os.environ.get(
        "MAPSAM2_CHECKPOINT",
        "/content/drive/MyDrive/vma_mapsam2_cache/models/epoch_010.pth",
    )
    ocr_run_id = p.get("ocr_run_id")
    prior = p.get("prior")

    argv = [
        python_bin,
        str(REPO_ROOT / "work" / "MapSAM2" / "inference_tiles_as_video.py"),
        "--map-id", job["map_id"],
        "--checkpoint", checkpoint,
        "--encoder", str(p.get("encoder", "vit_s")),
    ]
    if ocr_run_id or prior:
        argv += ["--lora", "--mapsam2-dir", mapsam2_dir, "--mode", "prompted"]
        if ocr_run_id:
            argv += ["--ocr-run-id", str(ocr_run_id)]
        if prior:
            argv += ["--prior", str(prior)]
    else:
        argv += ["--mode", "automatic"]
    argv += [
        "--tile-size", str(p.get("tile_size", 1024)),
        "--overlap", str(p.get("overlap", 128)),
        "--device", str(p.get("device", "cuda")),
        "--out-json", "footprints.json",
        "--write-supabase",
    ]
    # Measured on 1882 label prompts: text masking mean IoU 0.062 vs 0.089
    # without it, because flat paper tone creates a rectangle at the prompt.
    if p.get("text_mask", False):
        argv.append("--text-mask")
    # Watershed is unmeasured: EVAL-BASELINE.md records no watershed run.
    if p.get("watershed", True):
        argv.append("--watershed")
    if p.get("run_id"):
        argv += ["--run-id", str(p["run_id"])]
    return argv


def join_argv(job: dict, python_bin: str) -> list[str]:
    """Turn a `join` job into the label↔footprint join command line.

    Run ids are optional: join_labels pins the newest run on each side when it
    is not told which ones to use.
    """
    p = job["payload"]
    argv = [python_bin, str(REPO_ROOT / "work" / "ocr" / "scripts" / "join_labels.py"), job["map_id"]]
    if p.get("ocr_run_id"):
        argv.append(str(p["ocr_run_id"]))
        if p.get("seg_run_id"):
            argv.append(str(p["seg_run_id"]))
    return argv


# Kinds this worker runs itself. mirror_annotation, sync_allmaps and warp are
# not here: they need the service key, so the server runs them (see execute()).
RUNNERS = {"ocr": ocr_argv, "seg": seg_argv, "join": join_argv, "layout": layout_argv,
           "tile_to_r2": tile_argv}
SERVER_KINDS = {"mirror_annotation", "sync_allmaps", "warp"}


def default_kinds() -> str:
    """Every kind this machine can run, so a worker left running finishes what
    publishing enqueues (mirror_annotation, tile_to_r2 — mig 058) instead of
    leaving those rows queued until someone remembers `--kinds`. `seg` stays
    opt-in: it wants a GPU. `tile_to_r2` needs vips + rclone on PATH."""
    kinds = ["ocr", "join", "layout", *sorted(SERVER_KINDS)]
    if shutil.which("vips") and shutil.which("rclone"):
        kinds.append("tile_to_r2")
    return ",".join(kinds)


def run_job(job: dict, python_bin: str) -> None:
    _IN_FLIGHT[:] = [job["id"]]
    try:
        _run_job(job, python_bin)
    finally:
        _IN_FLIGHT.clear()


def _run_streaming(cmd: list[str], env: dict, timeout_s: int) -> subprocess.CompletedProcess:
    """Run a step, echoing its output as it arrives, and keep the tail.

    `subprocess.run(capture_output=True)` reads nothing until the child exits,
    so a forty-minute seg pass printed a command line and then nothing at all —
    an operator could not tell a working run from a wedged one, and killed a
    healthy one for looking dead. Echoing is not a nicety on this pipeline:
    every defect it has had looked like success or like silence.

    stderr is merged into stdout because the two are interleaved progress and
    the caller only ever wants the tail of whichever came last. The tail is
    capped so a chatty run cannot put megabytes in a jsonb column.

    ponytail: one blocking readline loop, no threads. The child writes to one
    pipe and nobody else is waiting on this worker.
    """
    from collections import deque

    deadline = time.monotonic() + timeout_s
    tail: deque[str] = deque(maxlen=200)
    proc = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, env=env, bufsize=1)
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            print(f"    {line}", flush=True)
            tail.append(line)
            if time.monotonic() > deadline:
                proc.kill()
                proc.wait()
                raise subprocess.TimeoutExpired(cmd, timeout_s)
        proc.wait(timeout=max(1.0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    finally:
        proc.stdout.close()
    out = "\n".join(tail)
    # Same shape subprocess.run returned, so every caller below is unchanged.
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout=out, stderr="")


def _run_job(job: dict, python_bin: str) -> None:
    kind = job["kind"]
    if kind in SERVER_KINDS:
        print(f"[{kind}] {job['id']} handing to the server")
        try:
            execute(job["id"])
            print(f"[{kind}] {job['id']} done")
        except requests.RequestException as e:
            # /api/pipeline/execute already closed the job out; this is just the
            # local report of it.
            print(f"[{kind}] {job['id']} FAILED: {e}")
        return

    build = RUNNERS.get(kind)
    if build is None:
        finish(job["id"], "failed", err=f"this worker does not run {kind} jobs")
        print(f"[{kind}] {job['id']} rejected — not runnable here")
        return

    try:
        argv = build(job, python_bin)
    except (KeyError, ValueError) as e:
        finish(job["id"], "failed", err=f"bad job payload: {e}")
        print(f"[{kind}] {job['id']} rejected — {e}")
        return

    # A runner returns one command, or a plan of several run in order (the
    # two-pass OCR recipe). The first non-zero exit fails the job.
    plan: list[list[str]] = argv if argv and isinstance(argv[0], list) else [argv]  # type: ignore[list-item]
    finish(job["id"], "running")

    # The pipeline scripts write through the same endpoint with the same key.
    api_url, api_key = _config()
    # PYTHONUNBUFFERED because capture_output makes the child's stdout a pipe,
    # and Python block-buffers to a pipe. Without it a 40-minute seg run prints
    # nothing at all until it exits — the operator cannot tell a working run
    # from a wedged one, which is the whole reason the last one was killed.
    env = {**os.environ, "VMA_API_URL": api_url, "VMA_WORKER_KEY": api_key,
           "PYTHONUNBUFFERED": "1"}

    proc = None
    for step, cmd in enumerate(plan, 1):
        print(f"[{kind}] {job['id']} running {step}/{len(plan)}: {' '.join(cmd)}")
        try:
            proc = _run_streaming(cmd, env, STEP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            # Without this the worker blocked forever on a wedged child and the
            # job sat in 'running' with nobody able to queue that map again.
            # Generous on purpose: the slowest legitimate step is the 1200px
            # pass at about 30 minutes.
            finish(job["id"], "failed",
                   err=f"step {step}/{len(plan)} exceeded {STEP_TIMEOUT_S}s and was killed")
            print(f"[{kind}] {job['id']} TIMED OUT on step {step}/{len(plan)}")
            return
        except OSError as e:
            # A missing interpreter or script would otherwise leave the job stuck in
            # 'running' with nobody to claim it again.
            finish(job["id"], "failed", err=str(e))
            print(f"[{kind}] {job['id']} FAILED to start: {e}")
            return
        if proc.returncode != 0:
            break
        # Budget between steps, not inside them: the worker owns the plan, so
        # this is where a two- or three-pass recipe can be cut short without
        # threading a flag through ocr.py. Each step's own rows are already
        # written, so stopping here keeps what was paid for.
        budget = job["payload"].get("max_calls")
        cost_cap = job["payload"].get("max_cost_usd")
        so_far = _spend(job["map_id"], job["payload"].get("run_id"))
        # Two ceilings, either of which stops the plan. `max_calls` came first
        # and stays, but a call is a poor proxy for money: measured over 1,192
        # calls on this corpus one ranges $0.0012 to $0.155, a 6x spread around
        # the median, and the dearest tenth carry 28% of all spend. A run that
        # is cheap in calls and expensive in thinking looked identical before.
        reason = None
        if budget and so_far.get("calls", 0) >= int(budget):
            reason = f"{so_far['calls']} calls reached the {budget}-call budget"
        elif cost_cap and so_far.get("cost_usd", 0.0) >= float(cost_cap):
            reason = (f"${so_far['cost_usd']:.2f} reached the "
                      f"${float(cost_cap):.2f} budget")
        if reason and so_far.get("unpriced_calls"):
            reason += f" ({so_far['unpriced_calls']} call(s) had no published rate)"
        if reason and step < len(plan):
            finish(job["id"], "done", {"returncode": 0, "budget_stopped": True,
                                       "steps_run": step, "steps_planned": len(plan),
                                       **so_far})
            print(f"[{kind}] {job['id']} stopped after step {step}/{len(plan)}: "
                  f"{reason}")
            return

    assert proc is not None
    if proc.returncode == 0:
        tail = proc.stdout.strip().splitlines()[-1:] or [""]
        finish(job["id"], "done", {"returncode": 0, "last_line": tail[0][:500],
                                   **_spend(job["map_id"], job["payload"].get("run_id"))})
        print(f"[{kind}] {job['id']} done")
    else:
        # Keep the tail: the whole log would not fit a jsonb column comfortably,
        # and the last few lines are what actually says why it died.
        err = (proc.stderr or proc.stdout or "").strip()[-2000:]
        finish(job["id"], "failed",
               {"returncode": proc.returncode, **_spend(job["map_id"], job["payload"].get("run_id"))},
               err)
        print(f"[{kind}] {job['id']} FAILED rc={proc.returncode}\n{err[-500:]}")


def _self_check() -> None:
    """
    Run: python work/worker/vma_worker.py --self-check

    Guards ROADMAP 5c. Patches claim() rather than the network, so this needs
    no worker key, no server and no database.
    """
    import contextlib
    import io

    mod = sys.modules[__name__]
    original_claim, original_argv = mod.claim, sys.argv[:]

    def run(claim_impl, argv):
        mod.claim = claim_impl
        sys.argv = ["vma_worker.py", *argv]
        out, err, code = io.StringIO(), io.StringIO(), 0
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                main()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        return code, out.getvalue(), err.getvalue()

    def unreachable(kinds, worker):
        raise requests.ConnectionError("Failed to resolve 'maparchive.vn'")

    try:
        # 1. The network is down. This must not look like success.
        code, out, err = run(unreachable, ["--once", "--kinds", "ocr"])
        assert code != 0, f"a claim that raises must exit non-zero, got {code}"
        assert "queue empty" not in out, "a transport error must not report an empty queue"
        assert "claim failed" in err, "the transport error must be reported on stderr"

        # 2. The API answered and had no job. That is success.
        code, out, err = run(lambda kinds, worker: None, ["--once", "--kinds", "ocr"])
        assert code == 0, f"an empty queue is success, got {code}"
        assert "queue empty" in out, "an empty queue must say so"

        # 3. The two outcomes must not be confusable on the exit code alone,
        #    which is the whole point: a drain loop reads exactly that.
        down, _, _ = run(unreachable, ["--once"])
        empty, _, _ = run(lambda kinds, worker: None, ["--once"])
        assert down != empty, "unreachable and empty must differ in exit code"
    finally:
        mod.claim, sys.argv = original_claim, original_argv

    # 4. The render the model sees. One rule, here, so the Run OCR button and
    #    enqueue_ocr_all cannot disagree about it again.
    assert _render_size({"tile_size": 2400}) == 2400, "equal to the tile is 1:1"
    assert _render_size({"tile_size": 800}) == RENDER_FLOOR, "a small tile still gets the floor"
    assert _render_size({}) == 2400, "the default tile renders 1:1"

    # 5. `passes: 3` must not append a pass identical to pass a. On a sheet whose
    #    tile_size is already at or below the hi-res grid it would be a copy, and
    #    the merge would count it as an independent voter.
    def plan_for(tile, passes):
        job = {"id": "j", "map_id": "m", "payload": {"run_id": "r", "tile_size": tile,
                                                     "passes": passes}}
        return _two_pass_plan(job, "python")

    assert len(plan_for(2400, 3)) == 4, "coarse sheet: two grid passes, hi-res, merge"

    # 5b. The printed-index rectangles reach ocr.py, or every directory line on
    #     the 1942 Saigon-Cho Lon sheet comes back as a numeral on the map body.
    argv = _ocr_batch_argv({"id": "j", "map_id": "m",
                            "payload": {"run_id": "r",
                                        "exclude": [[8964, 7643, 5295, 2467],
                                                    [4549, 8749, 2728, 3298]]}},
                           "python", "r", db=False)
    assert argv[argv.index("--exclude") + 1] == "8964,7643,5295,2467;4549,8749,2728,3298", argv

    # 5b. --low-thinking rides the payload the way --model does. Unset, the
    #     flag must be absent entirely rather than passed as a false value.
    assert "--low-thinking" not in argv, "absent from the payload means absent from argv"
    lt = _ocr_batch_argv({"id": "j", "map_id": "m",
                          "payload": {"run_id": "r", "low_thinking": True}},
                         "python", "r", db=False)
    assert "--low-thinking" in lt, lt

    # 6. What a run cost. The job row used to carry a returncode and a last line,
    #    so a pass that spent sixty calls to find four labels looked exactly like
    #    a cheap one. Asserted against a written log rather than a mock, because
    #    the field names are gemini_client's to change.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        mod_outputs = mod.OCR_OUTPUTS
        try:
            mod.OCR_OUTPUTS = Path(tmp)
            run_dir = Path(tmp) / "map-1" / "runs" / "r7-a"
            run_dir.mkdir(parents=True)
            (run_dir / "calls.jsonl").write_text(
                '{"total_tokens": 100, "n_extractions": 3}\n'
                '{"total_tokens": 50, "n_extractions": 1}\n'
                '\n'                      # a blank line is not a call
                '{"total_tokens": 25,\n'  # nor is a half-written one
            )
            got = mod._spend("map-1", "r7")
            assert got == {"calls": 2, "tokens": 150, "extractions": 4,
                           "per_call": 2.0, "cost_usd": 0.0,
                           "unpriced_calls": 2}, got
            # A log with no model and no token split cannot be priced. It must
            # say so rather than report $0.00 as if that were measured — a
            # silent zero makes `max_cost_usd` unenforceable.
            assert got["unpriced_calls"] == 2, "an unpriced call must be named"

            # And the priced path, against the real rate table: one call of
            # 1M fresh input and 1M billed output is $0.75 + $3.75.
            priced = Path(tmp) / "map-2" / "runs" / "r8-a"
            priced.mkdir(parents=True)
            (priced / "calls.jsonl").write_text(json.dumps({
                "model": "gemini-3.8-flash", "input_tokens": 1_000_000,
                "output_tokens": 400_000, "total_tokens": 2_000_000,
                "cached_tokens": 0, "n_extractions": 5,
            }) + "\n")
            got2 = mod._spend("map-2", "r8")
            assert got2["cost_usd"] == 4.5, got2
            assert "unpriced_calls" not in got2, got2
            assert mod._spend("map-1", "nosuchrun") == {}, "a run with no log reports nothing"
            assert mod._spend("map-1", None) == {}, "no run id, no spend"
        finally:
            mod.OCR_OUTPUTS = mod_outputs
    assert len(plan_for(1200, 3)) == 3, "tile already 1200: hi-res would duplicate pass a"
    assert len(plan_for(900, 3)) == 3, "tile finer than the hi-res grid: likewise"
    assert len(plan_for(2400, 2)) == 3, "two passes plus the merge"
    # The merge must name every pass it is given, and write to the payload's run.
    plan = plan_for(2400, 3)
    merge = plan[-1]
    assert merge[merge.index("--runs") + 1] == "r-a,r-b,r-c", merge
    assert merge[merge.index("--run-id") + 1] == "r", "the merge owns the payload's run_id"
    assert "--db" in merge and not any("--db" in step for step in plan[:-1]), \
        "only the merge writes to the database"

    # 6. The prompt is stamped from its one declaration, so the rows say what
    #    they used instead of inheriting whatever the checkout had.
    argv = _ocr_batch_argv({"id": "j", "map_id": "m", "payload": {"run_id": "r"}}, "python",
                           "r", db=False)
    assert "--prompt" in argv, "a queued run must name its prompt"
    argv = _ocr_batch_argv({"id": "j", "map_id": "m",
                            "payload": {"run_id": "r", "prompt": "v8"}}, "python", "r", db=False)
    assert argv[argv.index("--prompt") + 1] == "v8", "an explicit prompt wins"

    # 7. The streaming runner must still hand back what the callers read: a
    #    returncode, and stdout carrying the tail. A step that failed reports
    #    through `proc.stderr or proc.stdout`, which is now always the latter.
    ok = _run_streaming([sys.executable, "-c", "print('first'); print('last')"],
                        dict(os.environ), 30)
    assert ok.returncode == 0, ok
    assert ok.stdout.splitlines()[-1] == "last", ok.stdout
    bad = _run_streaming([sys.executable, "-c",
                          "import sys; print('why it died', file=sys.stderr); sys.exit(3)"],
                         dict(os.environ), 30)
    assert bad.returncode == 3, bad
    assert "why it died" in (bad.stderr or bad.stdout), "stderr must survive the merge"

    print("[ok] vma_worker self-check passed")


def main() -> None:
    ap = argparse.ArgumentParser(description="Claim and run VMA pipeline jobs.")
    ap.add_argument(
        "--kinds",
        default=default_kinds(),
        help=f"comma-separated job kinds to claim; seg is opt-in, tile_to_r2 needs vips + rclone (default here: {default_kinds()})",
    )
    ap.add_argument("--worker", default=os.uname().nodename, help="name recorded on the claim")
    ap.add_argument("--interval", type=float, default=10.0, help="seconds between polls when idle")
    ap.add_argument("--once", action="store_true", help="run at most one job, then exit")
    ap.add_argument("--python", default=sys.executable, help="interpreter for the pipeline scripts")
    args = ap.parse_args()

    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    print(f"vma-worker {args.worker} polling {kinds} every {args.interval}s")

    while True:
        try:
            job = claim(kinds, args.worker)
        except requests.RequestException as e:
            # A transport error is not an empty queue. Conflating the two is how
            # ocr job 107182d6 sat stranded in `running` with a dead subprocess
            # while an unattended drain reported success (ROADMAP 5c). Under
            # --once the caller is a shell loop reading the exit code, so fail
            # there; when polling, keep going — a blip should not kill a worker
            # that is meant to run for hours.
            print(f"claim failed: {e}", file=sys.stderr)
            if args.once:
                sys.exit(1)
            time.sleep(args.interval)
            continue

        if job:
            try:
                run_job(job, args.python)
            except Exception as e:  # noqa: BLE001 — a worker meant to run for hours
                # Anything unhandled here would otherwise end the process and
                # leave the row in 'running'. Report it, keep polling.
                print(f"job {job.get('id')} raised: {e}", file=sys.stderr)
                finish(job["id"], "failed", err=f"worker error: {e}"[:2000])
            if args.once:
                return
        elif args.once:
            # Reached only when the API answered and had nothing to give.
            print("queue empty")
            return
        else:
            time.sleep(args.interval)


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        _self_check()
        sys.exit(0)
    try:
        main()
    except KeyboardInterrupt:
        # A job in flight is reported failed so finish_job requeues it (attempts
        # permitting). Ctrl-C is the documented way to stop a worker, and it used
        # to strand whatever was running.
        if _IN_FLIGHT:
            print(f"\nstopped — handing job {_IN_FLIGHT[0]} back to the queue")
            finish(_IN_FLIGHT[0], "failed", err="worker interrupted")
        else:
            print("\nstopped")
