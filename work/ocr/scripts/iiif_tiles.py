"""IIIF tile fetcher and grid utilities.

Re-export shim: the code now lives in `work/core/vma_core/iiif.py`. Every name,
private ones included (callers import `_headers`, `_load_config`, `_axis_tiles`,
`_cached_info`, ...), is re-exported by name so existing callers keep working.
New code should import from `vma_core.iiif`.

Run: python work/ocr/scripts/iiif_tiles.py --self-check
"""

from __future__ import annotations

import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parents[2] / "core"  # work/core
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from vma_core.iiif import (  # noqa: E402,F401
    CACHE_DIR,
    _ia_direct_url,
    _download_full,
    fetch_crop,
    MIN_LEVEL0_COVERAGE,
    _INFO_CACHE,
    _cached_info,
    level0_tile_url,
    _pick_scale_factor,
    fetch_crop_level0,
    _descending_from,
    _axis_tiles,
    tile_grid,
    get_iiif_base_from_supabase,
    get_iiif_base_from_allmaps,
    estimate_density,
    adaptive_render_size,
    _clahe_lut,
    apply_clahe,
    detect_neatline,
    compute_tile_densities,
    compute_tile_colours,
    auto_tile_overrides,
    AOI_GEO_HINT,
    parse_aoi_px,
    aoi_tile_overrides,
    auto_tile_params,
    get_image_info,
    choose_scale_levels,
    _self_check,
)


if __name__ == "__main__":
    from vma_core.iiif import main

    main()
