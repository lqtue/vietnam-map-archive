# Image processing scripts

[OCR workspace](../README.md) · [Pipeline command reference](../../../docs/pipelines.md).
Run commands from the repository root, using `work/ocr/.venv/bin/python` where dependencies require it.
Consult each command's `--help` and the pipeline reference before running it.

| Task                              | Entry scripts                             |
| --------------------------------- | ----------------------------------------- |
| Read text and sheet layout        | `ocr.py` (subcommands), `legend_probe.py` |
| Generate colour polygons          | `colour_blocks.py`                        |
| Clean and regularize polygons     | `clean_blocks.py`, `regularize_blocks.py` |
| Generate model-based segmentation | `seg_gemini.py`                           |
| Compare against modern references | `modern_prior.py`                         |
| Align sheets                      | `sheet_register.py`                       |
| Join labels and polygons          | `join_labels.py`                          |
| Generate review figures           | `review_figs.py`                          |
| Evaluate a run or segmentation    | `audit_run.py`, `eval.py`, `seg_eval.py`  |
| Build dictionaries and masks      | `dictionary.py`, `name_masks.py`          |

Shared modules include `iiif_tiles.py`, `scale.py`, `cache.py`, `gemini_client.py`, `local_vision.py`,
`supabase_client.py`, `labels.py`, `prompt.py`, `pricing.py`, and `eval_metrics.py`.
`test_*.py` files check pipeline behavior. `oneoff/` holds completed backfills, retained as records;
it is not a queue of commands to rerun.

Some commands call models or write through the pipeline API/database. Check their flags and the
[lessons](../../../docs/lessons.md) before an unattended run or database write.
