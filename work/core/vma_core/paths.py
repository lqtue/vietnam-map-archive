"""Where things are. Resolved from this file's location, never from the cwd.

`work/core/vma_core/paths.py` -> parents: vma_core, core, work, <repo root>.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Run outputs, shared by OCR and the image tools. Today `work/ocr/outputs` is a
# link to `work/image-processing/results`; this names the link so a writer can
# stop caring where it points. The link itself is not moved.
OUTPUTS = REPO_ROOT / "work" / "ocr" / "outputs"

# Secrets file read by every script that talks to Supabase or Gemini.
ENV_FILE = REPO_ROOT / ".env"

# Disk cache of fetched IIIF crops and level-0 tiles (large; keep the folder).
TILE_CACHE = REPO_ROOT / ".tile_cache" / "ocr"
