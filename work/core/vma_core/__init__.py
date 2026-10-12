"""Shared code for the OCR, segmentation and worker pipelines.

Rule: nothing in this package imports from `work/ocr`, `work/image-processing`,
`work/MapSAM2` or `work/worker`. See `work/core/README.md`.

Put `work/core` on `sys.path` (the shims in `work/ocr/scripts/` do it) and then:

    from vma_core import iiif, georef, db, paths
"""
