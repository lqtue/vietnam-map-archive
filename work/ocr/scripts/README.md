# OCR commands and shared helpers

[OCR workspace](../README.md) · [Pipeline command reference](../../../docs/pipelines.md).
Run commands from the repository root, using `work/ocr/.venv/bin/python` where dependencies require it.
Consult each command's `--help` and the pipeline reference before running it.

| Task                              | Entry scripts                             |
| --------------------------------- | ----------------------------------------- |
| Read text and sheet layout        | `ocr.py` (subcommands)                    |
| Join labels and polygons          | `join_labels.py`                          |
| Audit and evaluate OCR            | `audit_run.py`, `eval.py`, `eval_metrics.py` |
| Build the label dictionary        | `dictionary.py`                          |

Shared modules include `iiif_tiles.py`, `scale.py`, `cache.py`, `gemini_client.py`, `local_vision.py`,
`supabase_client.py`, `labels.py`, `prompt.py`, `pricing.py`, and `eval_metrics.py`.
Image commands live in [image-processing/scripts](../../image-processing/scripts/README.md)
and import these helpers by path. `test_*.py` files check pipeline behavior, including the
relocated review-figure tool. `oneoff/` holds completed backfills, retained as records;
it is not a queue of commands to rerun.

Some commands call models or write through the pipeline API/database. Check their flags and the
[lessons](../../../docs/lessons.md) before an unattended run or database write.
