# OCR workspace and shared Python environment

Text recognition, sheet layout, OCR evaluation and label joining live here. Image extraction,
polygon cleanup, registration and segmentation evaluation live in
[image-processing/scripts](../image-processing/scripts/README.md). Both areas share the Python
environment at `.venv` and the IIIF, georeference, model and database helpers in `scripts/`.
Start with the [image processing workspace](../image-processing/README.md) to browse local results.

Generated outputs physically live at [image-processing/results](../image-processing/results/),
and logs at [image-processing/logs](../image-processing/logs/). `outputs` and `logs` here are
temporary compatibility symlinks, so existing OCR commands still work. The 1882 plan removes
them after its reference audit. Run IDs and sheet UUIDs are preserved.

## What is where?

| Location                              | Contents                                                                   |
| ------------------------------------- | -------------------------------------------------------------------------- |
| [scripts](scripts/README.md)          | Reusable commands, shared helpers, checks and completed backfills          |
| [EVAL-BASELINE.md](EVAL-BASELINE.md)  | Recorded quality gate and experiment evidence                              |
| `outputs/<map-id>/runs/<run-id>/`     | Versioned OCR, layout and diagnostic runs                                  |
| `outputs/<map-id>/colour-*/`          | Colour segmentation and cleaned polygon exports                            |
| `outputs/<map-id>/seg-review/`        | Local segmentation review artifacts                                        |
| `outputs/prior/<map-id>/`             | Modern-map references transformed into source-image pixels                 |
| `outputs/annotations/`                | Local annotation snapshots                                                 |
| `outputs/osm/`                        | Local modern street source data                                            |
| `outputs/_layout-*/`                  | Dated layout batch artifacts                                               |
| `outputs/dedupe-*.json`               | Deduplication reports; filenames distinguish preview and applied runs      |
| `outputs/dictionary.*`                | Generated dictionary artifacts                                             |
| `outputs/.cache/`                     | Model-response cache                                                       |
| `logs/`                               | Local execution transcripts                                                |
| `.venv/`                              | Local Python environment, built using [requirements.txt](requirements.txt) |
| `prices.json`, `index-baselines.json` | Pricing and baseline configuration data                                    |

Outputs, logs and the environment are gitignored. Their absence in a fresh checkout is expected.

## Reading a run

Start with `run_config.json` for its model, prompt, tile size, render size and recorded timestamp.
`all_extractions.json` is the merged OCR result; coordinate-named JSON files are per-tile responses.
`calls.jsonl` records model calls. `scout.json` describes layout regions, and `scout.png` visualizes
them. An OCR summary does not prove every requested tile succeeded; inspect recorded errors and
processed/total tiles. A layout-only or partial run may have no merged OCR result.

Colour output uses `blocks.geojson` and segmentation JSON. Normalized, queue-safe and regularized
exports are different derived representations; use the run's audit and review notes to determine
which one is suitable. Folder names such as `baseline`, `batch_v6`, `seq-v1-shift` and `step3` are
historical experiment IDs. The generated catalog exposes their saved settings rather than assigning
quality based on their names. A `normalized` suffix does not establish approval or import.

Use [Pipelines](../../docs/pipelines.md) for commands and [worker instructions](../CLAUDE.md)
for queued jobs. Preserve UUID paths and run IDs already used by pipeline readers and database rows.
