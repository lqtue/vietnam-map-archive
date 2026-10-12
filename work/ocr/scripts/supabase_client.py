"""Database access for the pipelines.

Re-export shim: the code now lives in `work/core/vma_core/db.py`. Every name,
private ones included (callers import `_headers`, `_load_config`, `_axis_tiles`,
`_cached_info`, ...), is re-exported by name so existing callers keep working.
New code should import from `vma_core.db`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parents[2] / "core"  # work/core
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from vma_core.db import (  # noqa: E402,F401
    _load_config,
    _CHUNK_SIZE,
    _CONFLICT_COLS,
    _api_config,
    _post_results,
    _headers,
    check_write_complete,
    upsert_ocr_extractions,
    PAGE,
    fetch_ocr_extractions,
    fetch_footprints,
    link_extractions_to_footprints,
    save_triage_regions,
    save_triage_grid,
    fetch_triage_grid,
    fetch_triage_regions,
    update_pipeline_status,
    upsert_label_pins,
)
