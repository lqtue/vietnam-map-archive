# Image-processing scripts

Reusable feature extraction, polygon cleanup, registration and review tools.
[Workspace](../README.md) · [Pipeline commands](../../../docs/pipelines.md).
Run from the repository root with `work/ocr/.venv/bin/python`; the environment is shared
with OCR. Commands that need OCR's IIIF, georeference, database or model helpers add
`work/ocr/scripts/` to their import path. Those shared modules remain with OCR.

| Task | Scripts |
| --- | --- |
| Colour polygons | `colour_blocks.py`, `clean_blocks.py`, `regularize_blocks.py` |
| Sheet measurements and frozen masks | `sheet_features.py`, `river_pass.py`, `road_pass.py` |
| Review figures and legend diagnostics | `review_figs.py`, `review_sheet.py`, `legend_probe.py` |
| Model segmentation and naming | `seg_gemini.py`, `name_masks.py` |
| Modern priors and sheet registration | `modern_prior.py`, `sheet_register.py` |
| Segmentation evaluation | `seg_eval.py` |

Generated outputs use `work/image-processing/results/`. The reference window registry,
owner labels, traces and blind-safe preview helper live in `experiments/river-reference/`.
Follow the [1882 plan](../../../docs/image-processing-1882-plan.md) before running a pass:
water v3 is frozen, road v3 is diagnostic, and held-out scoring must not be repeated.

Consult `--help` and [lessons](../../../docs/lessons.md) before model calls or database writes.
