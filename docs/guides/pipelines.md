# Pipelines

Pipelines that live outside the SvelteKit app. Kind: guide (index). Each tool's reference now sits
beside the tool; this page says where. Moved 2026-10-17; section names are unchanged, so a
citation like "pipelines.md § Full resolution" is found by searching the page it moved to.

## Pipeline stages (`map_pipeline_status.stage`)

`idle → ocr_queued → ocr_done → reviewed → seg_queued → seg_done → seg_reviewed → exported`

Advances automatically when OCR batch (`--db`) or SAM2 inference (`--write-supabase`) writes. Manual
transitions via PATCH `/api/admin/maps/[id]/pipeline`.

## Where each section went

| Section | Now in |
| --- | --- |
| Is every map where it says it is? (`geo_audit.mjs`) | [scripts/README.md](../../scripts/README.md) |
| Is a row consistent with its own table? (`catalog_audit.mjs`) | [scripts/README.md](../../scripts/README.md) |
| Storing a script-made georeference (`georef_write.mjs`) | [scripts/README.md](../../scripts/README.md) |
| AMS Series L7014 mosaic | [scripts/l7014/README.md](../../scripts/l7014/README.md) |
| The worker | [work/worker/README.md](../../work/worker/README.md) |
| OCR, with local passes, name dictionary, label ↔ footprint join, reading a sheet's margins, sizing a grid, what to do next | [work/ocr/README.md](../../work/ocr/README.md) |
| Eval harness (`eval.py`); coarse → fine, coordinate contract, prompt design, known issues, cost, POC criteria | [work/ocr/README.md](../../work/ocr/README.md) |
| NLV press harvest, legend timeline, place report | [scripts/scout/README.md](../../scripts/scout/README.md) |
| MapSAM2 inference, tiles-as-video, Gemini as the prompt source, ordering the sequence | [work/MapSAM2/README.md](../../work/MapSAM2/README.md) |
