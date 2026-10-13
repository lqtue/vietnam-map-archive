"""Sheet scale from a map's own georeference.

Re-export shim: the code now lives in `work/core/vma_core/georef.py`. Every name,
private ones included (callers import `_headers`, `_load_config`, `_axis_tiles`,
`_cached_info`, ...), is re-exported by name so existing callers keep working.
New code should import from `vma_core.georef`.

Run: python work/ocr/scripts/scale.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parents[2] / "core"  # work/core
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from vma_core.georef import (  # noqa: E402,F401
    METRES_PER_DEG_LAT,
    METRES_PER_DEG_LON_EQUATOR,
    DEFAULT_TILE_METRES,
    MAX_RENDER_SIZE,
    DEFAULT_OVERLAP_RATIO,
    MIN_GCPS,
    MIN_GCP_CONDITION,
    MIN_TILE_PX,
    ANISOTROPY_LIMIT,
    COARSE_SCAN_METRES_PER_PX,
    ScaleFit,
    TileFit,
    gcps_from_annotation,
    metres_per_pixel,
    annotation_for_map,
    _grid,
    tile_size_for,
    render_size_for,
    _self_check,
)


if __name__ == "__main__":
    from vma_core.georef import main

    main()
