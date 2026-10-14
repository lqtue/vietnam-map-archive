# work/core

Part of the **operations** layer — see [ATLAS](../../docs/ATLAS.md).

Code the OCR, segmentation and worker pipelines share. One package, `vma_core`.

| Module | Holds | Old home (now a re-export shim) |
|---|---|---|
| `vma_core/paths.py` | `REPO_ROOT`, `OUTPUTS`, `ENV_FILE`, `TILE_CACHE`, resolved from the file, never the cwd | the `parents[N]` lines in each script |
| `vma_core/iiif.py` | IIIF `info.json`, `fetch_crop`, level-0 tile assembly, `tile_grid`, base-URL lookup, plus the OCR tile-planning helpers that lived in the same file | `ocr/scripts/iiif_tiles.py` |
| `vma_core/georef.py` | GCPs from an Allmaps annotation, metres per pixel, `annotation_for_map`, plus the tile-sizing helpers (`TileFit`, `tile_size_for`) | `ocr/scripts/scale.py` |
| `vma_core/db.py` | Supabase config and transport (`_load_config`, `_headers`, worker-or-direct writes) and the OCR table reads and writes | `ocr/scripts/supabase_client.py` |

The code was moved, not rewritten. The three old files keep their names and every name they
exported (private ones too), so no caller changed. New code imports `vma_core` directly:

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[N] / "core"))   # work/core
from vma_core import iiif, georef, db, paths
```

## The rule

**Core imports nothing from `ocr`, segmentation (`image-processing`, `MapSAM2`) or `worker`.**
`ocr` and segmentation import core. The worker imports core and runs the others as subprocesses.
`test_core.py` fails if a core module imports one of those.

## Not done yet

- The OCR halves of `iiif.py` (density, CLAHE, overrides) and `georef.py` (`TileFit`) are still
  in core because the shims had to be thin. They belong in `ocr/scripts/tile_plan.py`.
- The OCR-table functions in `db.py` belong in `ocr`; the transport helpers stay.
- Scripts still write through `work/ocr/outputs`, which is a link to `image-processing/results`.
  `paths.OUTPUTS` names that link; switching writers to it is a separate step. The link is unmoved.
- Colab bundles that copy `work/ocr/scripts/{iiif_tiles,scale}.py` alone (as
  `MapSAM2/prepare_comparison.py` does) now also need `work/core/vma_core/`. A full
  `git clone` of the repo is unaffected.

## Check

```sh
work/ocr/.venv/bin/python work/core/vma_core/test_core.py
```
