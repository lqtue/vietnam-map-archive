# 1882 segmentation comparison — Colab operator guide

Prepared 2026-10-12. This is the interactive, artifact-only route for comparing whole street
blocks. The [delivery plan](../../docs/image-processing-1882-plan.md) defines the targets and
selection gate. The existing worker notebook is a separate route that writes proposals.

## Start the prepared notebook

1. Open [Google Colab](https://colab.research.google.com), choose **Upload notebook**, and upload
   `work/image-processing/results/seg-comparison-20261012/vma_seg_comparison.ipynb`.
2. Select a GPU runtime; choose T4 when available. Run the setup cell and upload
   `vma-seg-comparison.tar.gz` from the same directory. It verifies file hashes and installs the
   pinned upstream revisions. No database credentials are needed.
3. Authorize Drive mounting and set `CHECKPOINT` to your existing `epoch_010.pth`. The default
   location is `/content/drive/MyDrive/vma_mapsam2_cache/models/epoch_010.pth`.
4. Set `REGIONS` explicitly as source-pixel `x,y,width,height` boxes. Start with an already-seen
   development area. Freeze independent owner references before using a test region. The notebook
   rejects overlap with existing unseen river/road holdouts. The old 46 training traces and the
   seven QGIS proposal comparisons are not independent parcel references.
5. Run the configuration and comparison cells. JSON, logs and the comparison manifest save to
   Drive after each completed variant. Use a fresh `OUTPUT` directory for a new experiment.

This session has no browser-control connection to your Colab runtime. You start the notebook;
we can inspect its downloaded artifacts and adapt the code locally. Runtime/GPU availability
depends on your Colab account; see Google's [FAQ](https://research.google.com/colaboratory/faq.html).

## What it compares

| Variant | Prompts/settings | Cross-tile memory |
|---|---|---|
| baseline | Existing box/score defaults | Off |
| context | Explicit context file: initially box+point/largest | Off |
| memory | Same defaults as baseline | On |
| memory-context | Same context file as context | On |

This measures the effect of the declared context policy as a whole. A gain cannot be attributed
to the map's year or name: SAM2 has no prose encoder. Those fields record identity. Target type,
interior points, mask selection, source metres per pixel and optional physical area bounds affect
the workflow. Optional legend RGB swatches produce review suggestions, never approved labels.
Test individual context settings separately on development data if attribution matters.

The memory adapter uses SAM2's memory encoder and attention, a confidence gate and a diverse
bank with deterministic similarity retrieval. It keeps instance prompts; it is not the paper's
complete prompt-free semantic training pipeline. CPU checks verify tensor flow, not better map
accuracy. A memory comparison is uninformative if `conditioned_tiles` is zero.

Defaults use 2048 source-pixel tiles, 256 overlap and IIIF width 512. Coarsening suppresses fine
ink before SAM2's internal 1024 encoder, but may lose narrow boundaries. Treat it as an
experimental setting. A memory region needs at least two tiles containing eligible prompts;
small reference windows may sit inside a larger frozen inference region. Record and hold scale
constant across variants. Each subprocess uses the same initialization seed (42 by default),
records it and disables cuDNN benchmarking. This controls random initialization without promising
bitwise equivalence on every GPU. The notebook verifies identical tile RGB hashes.

`PRIOR_CHOICE` selects `then-now` or `colour`. The frozen 152-block street/water prior has known
mask leaks and lettering bumps. The colour prior omits building proposals and declares its
remaining candidates as parcel hypotheses; that declaration does not establish whole-block
correctness. Compare both CPU priors directly as well as the resulting SAM proposals. To run a
second prior, change `PRIOR_CHOICE` and use a new output directory.

No comparison cell passes `--write-supabase`, `--text-mask` or `--watershed`. Incomplete tile runs
are failures and their diagnostic JSON cannot establish accuracy. Local masks retain substantive
components and holes; the current database outer-ring contract cannot represent holes, so the
writer refuses them rather than filling them silently.

## Rebuild the upload bundle

`prepare_comparison.py --help` lists input arguments. Rebuild the prepared directory with
`--reuse-snapshot` to refresh code while retaining the verified frozen inputs and correction snapshot:

```bash
python work/MapSAM2/prepare_comparison.py --reuse-snapshot \
  --out work/image-processing/results/seg-comparison-20261012
```

For a new baseline supply both prior paths; the known legacy colour artifact needs the explicit
CRS declaration `--prior-crs source-pixels-y-down`. Use `--snapshot` only for a new named baseline;
it makes paged read-only requests. Never use both flags together.

The archive has an explicit source/input allowlist, full upstream revision pins and file hashes.
The original footprint snapshot stays local. Checkpoints, reference traces, private documents
and credentials are excluded. The manifest's Git revision may precede uncommitted changes;
file hashes identify the actual bundled implementation.

## Score and review locally

After the owner freezes exhaustive, class-labelled pixel references, use:

```bash
python work/image-processing/scripts/seg_eval.py \
  --reference /path/to/frozen-parcels.geojson \
  --types parcel --iou-thresholds 0.5,0.75 \
  --window x,y,width,height --report-json /path/to/score.json \
  /path/to/downloaded-run.json
```

Confirm option names with `--help` and retain the reference's source-pixel CRS, map identity and
window protocol. Score CPU GeoJSON through the same path; legacy untyped candidates require an
explicit `--prediction-type parcel`. Matches are one-to-one and class-aware, so duplicate and
wrong-class proposals count as false positives. Report precision, recall, boundary distances and
correction effort alongside overlap; polygon count alone is not quality.

`review_timings.py` checks the producing session's then-now outline hashes. “Outline right?”
latency measures review time. It measures correction effort only if a separate correction duration
was recorded. Keep those distinctions when selecting a method.

Local application changes need migrations 120/121 before deployment. The comparison notebook
needs neither migration and does not alter saved corrections or approvals.
