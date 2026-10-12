#!/usr/bin/env python3
"""Checks for work/core: path resolution and the three re-export shims.

Plain asserts, no pytest, no network. The shim checks import requests, PIL and
numpy, so run it with the OCR venv:

    work/ocr/.venv/bin/python work/core/vma_core/test_core.py

It works from any cwd; every path below comes from this file's location.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent  # work/core/vma_core
CORE = HERE.parent  # work/core
WORK = CORE.parent  # work
sys.path.insert(0, str(CORE))

from vma_core import paths  # noqa: E402

# ── paths: resolved from the file, not the cwd ─────────────────────────────
assert paths.REPO_ROOT == WORK.parent, paths.REPO_ROOT
assert (paths.REPO_ROOT / "work" / "core" / "vma_core" / "paths.py").is_file()
assert paths.OUTPUTS == paths.REPO_ROOT / "work" / "ocr" / "outputs"
assert paths.ENV_FILE == paths.REPO_ROOT / ".env"
assert paths.TILE_CACHE == paths.REPO_ROOT / ".tile_cache" / "ocr"
for p in (paths.REPO_ROOT, paths.OUTPUTS, paths.ENV_FILE, paths.TILE_CACHE):
    assert p.is_absolute()

other = Path(os.environ.get("TMPDIR", "/tmp"))
out = subprocess.run(
    [sys.executable, "-B", "-c",
     f"import sys; sys.path.insert(0, {str(CORE)!r}); from vma_core import paths; print(paths.REPO_ROOT)"],
    cwd=other, capture_output=True, text=True, check=True,
).stdout.strip()
assert Path(out) == paths.REPO_ROOT, "REPO_ROOT must not depend on the cwd"

# ── the rule: core imports nothing from ocr, seg or the worker ─────────────
FORBIDDEN = {"ocr", "iiif_tiles", "scale", "supabase_client", "gemini_client", "prompt",
             "pricing", "colour_blocks", "vma_worker", "inference_tiles_as_video"}
for src in (s for s in HERE.glob("*.py") if s.name != Path(__file__).name):
    for node in ast.walk(ast.parse(src.read_text())):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods = [node.module]
        for m in mods:
            assert m.split(".")[0] not in FORBIDDEN, f"{src.name} imports {m}"

# ── shims: every name core defines is re-exported, privates included ───────
try:
    import numpy, PIL, requests  # noqa: F401,E401
except ImportError as e:
    print(f"test_core.py: path checks ok; shim checks skipped ({e.name} missing; use the OCR venv)")
    sys.exit(0)

sys.path.insert(0, str(WORK / "ocr" / "scripts"))
import iiif_tiles, scale, supabase_client  # noqa: E402
from vma_core import db, georef, iiif  # noqa: E402


def defined(mod) -> set[str]:
    out = set()
    for n in ast.parse(Path(mod.__file__).read_text()).body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
    return {n for n in out if n != "main" and not n.startswith("__")}


for shim, core in ((iiif_tiles, iiif), (scale, georef), (supabase_client, db)):
    names = defined(core)
    assert names, core
    for name in names:
        assert getattr(shim, name) is getattr(core, name), f"{shim.__name__}.{name} is not core's"

# The private names other scripts import, spelled out so a rename shows up here.
for name in ("_headers", "_load_config", "_api_config", "_post_results", "_CHUNK_SIZE"):
    assert getattr(supabase_client, name) is getattr(db, name)
for name in ("_axis_tiles", "_cached_info", "_INFO_CACHE", "_pick_scale_factor", "_descending_from"):
    assert getattr(iiif_tiles, name) is getattr(iiif, name)
assert scale._grid is georef._grid

# Same dict object, not a copy: callers that seed the info cache must reach core.
assert iiif_tiles._INFO_CACHE is iiif._INFO_CACHE

# Path logic now comes from paths.py.
assert iiif.CACHE_DIR == paths.TILE_CACHE

# One concrete behaviour through the shim, no network.
assert list(iiif_tiles.tile_grid(100, 100, tile=100, overlap=0)) == [(0, 0, 100, 100)]
assert iiif_tiles.parse_aoi_px("3,4,1,2") == (1, 2, 3, 4)
assert scale.render_size_for(4048) == scale.MAX_RENDER_SIZE
try:
    supabase_client.check_write_complete(10, 9, "m", "r")
except RuntimeError:
    pass
else:
    raise AssertionError("a short write must raise")

print(f"test_core.py ok: paths, {len(defined(iiif)) + len(defined(georef)) + len(defined(db))} names re-exported")
