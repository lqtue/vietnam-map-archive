#!/usr/bin/env python3
"""Does the tile cache know what resolution it is holding?

Until 2026-09-10 it did not. The key was the tile's geometry alone —
`x_y_w_h_tile.png` — so once a sheet had been tiled, every later run was served
those bytes no matter what `--render-size`, `--low-res-render` or `--adaptive`
asked for. The flags were not overridden, they were silently ignored, and a run
that changed one reported a number it had not measured. That is the worst shape
a bug can take in a pipeline whose only product is numbers: it was found by
measuring input tokens on the 1882 gate sheet and noticing a render change had
moved nothing, because it had never happened.

These asserts are the smallest thing that fails if the render size falls out of
the key again. No network, no API calls, no Supabase.

    python test_tile_cache.py
"""
import inspect
import re
import tempfile
from pathlib import Path

from PIL import Image

import ocr
from ocr import _cached_tile, _tile_cache_path

KEY = "5360_4987_1404_1404"
# A clipped right-edge tile of the 1882 gate sheet: 1602 px of paper by a full
# 2400 px of height. Every tile grid has a column of these, plus a corner.
TALL_KEY = "10500_0_1602_2400"


def _write(path: Path, size: int) -> None:
    Image.new("RGB", (size, size), (200, 190, 170)).save(path)


def _write_tall(path: Path, w: int, h: int) -> None:
    Image.new("RGB", (w, h), (200, 190, 170)).save(path)


with tempfile.TemporaryDirectory() as tmp:
    cache = Path(tmp)

    # 1. The render size is in the name. If this is ever "the tile key alone"
    #    again, everything below is decoration.
    p1024 = _tile_cache_path(cache, KEY, 1024)
    p2048 = _tile_cache_path(cache, KEY, 2048)
    assert p1024 != p2048, "one tile at two resolutions must not share a path"
    assert "1024" in p1024.name and KEY in p1024.name, p1024.name

    # 2. An empty cache asks for nothing.
    assert _cached_tile(cache, KEY, 1024) is None, "empty cache must miss"

    # 3. A tile stored at 1024 serves 1024 and refuses 2048 — the whole bug.
    _write(p1024, 1024)
    hit = _cached_tile(cache, KEY, 1024)
    assert hit is not None and max(hit.size) == 1024, "same size must hit"
    assert _cached_tile(cache, KEY, 2048) is None, \
        "a 1024px tile was served for a 2048px request — the render flag is inert again"

    # 4. Both resolutions can coexist; each request gets its own.
    _write(p2048, 2048)
    assert max(_cached_tile(cache, KEY, 1024).size) == 1024
    assert max(_cached_tile(cache, KEY, 2048).size) == 2048

with tempfile.TemporaryDirectory() as tmp:
    cache = Path(tmp)
    legacy = cache / f"{KEY}_tile.png"
    _write(legacy, 1024)

    # 5. A legacy file — written before the key carried a size — is reused when
    #    it happens to hold the requested size, and ignored otherwise. It is a
    #    real tile; it just never said so.
    assert max(_cached_tile(cache, KEY, 1024).size) == 1024, "legacy tile at the right size is reusable"
    assert _cached_tile(cache, KEY, 2048) is None, "legacy tile must not answer for another size"

    # 6. And it is not moved. These directories are shared with a running worker
    #    and with other sessions; a cache that renames files under a concurrent
    #    reader is a worse problem than a few uninformative names.
    assert legacy.exists(), "the legacy file was renamed or removed"
    assert not _tile_cache_path(cache, KEY, 1024).exists(), "nothing should have been written"

# ── A tall tile must survive the round trip ───────────────────────────────────
# `fetch_crop` defaults to fit=False, so the IIIF size parameter is `{size},` —
# WIDTH ONLY. A crop taller than it is wide comes back with width == size and
# height larger, so `max(img.size)` is the *height* and has nothing to do with
# what was requested. Naming the file after it stored the tile under a number no
# read site ever asks for: the whole clipped right-hand column of every grid,
# plus the bottom-right corner, missed on every run, was re-fetched, and came
# back as different bytes than the earlier run had cached (the level0
# composition path moved under 2cf6dd02) — so no two runs on a sheet were
# byte-comparable and the 1882 re-gate manufactured a label out of it
# (`work/archive/cleanup/F-1882-regate.md`).
with tempfile.TemporaryDirectory() as tmp:
    cache = Path(tmp)

    # 1602x2400 of paper asked for at width 1024 comes back 1024x1534.
    RENDER, W, H = 1024, 1024, 1534
    assert max(W, H) != RENDER, "the premise: max(img.size) is not the render size"

    _write_tall(_tile_cache_path(cache, TALL_KEY, RENDER), W, H)
    hit = _cached_tile(cache, TALL_KEY, RENDER)
    assert hit is not None, \
        "a tall tile saved by the write path was not found by the read path — " \
        "the two are keyed on different quantities again"
    assert hit.size == (W, H), hit.size

    # And the old key is what a read would never have asked for.
    assert _cached_tile(cache, TALL_KEY, max(W, H)) is None, \
        "a tile stored under its height answered a request for that height"

with tempfile.TemporaryDirectory() as tmp:
    # The bug itself, one directory at a time: written the old way, under the
    # returned image's larger dimension, the tile is unreachable forever. 25
    # files under work/ocr/outputs/ are still in this state and are simply not
    # found — deliberately not renamed, for the reason in _cached_tile.
    cache = Path(tmp)
    RENDER, W, H = 1024, 1024, 1534
    _write_tall(_tile_cache_path(cache, TALL_KEY, max(W, H)), W, H)
    assert _cached_tile(cache, TALL_KEY, RENDER) is None, \
        "a tile named after max(img.size) is not addressable and must miss"

# ── The write sites must key on the size they asked for ───────────────────────
# The round trip above only holds if the save path passes the *requested* render
# size. It cannot be checked by calling it — the saves live inside cmd_batch,
# behind a network fetch — so it is checked by reading the source. `max(img.size)`
# as a cache key is the bug, and this is the shape it takes.
_source = inspect.getsource(ocr)
_bad = re.findall(r"_tile_cache_path\([^)]*max\(", _source)
assert not _bad, (
    f"{len(_bad)} _tile_cache_path call(s) key on a dimension of the returned "
    f"image instead of the requested render size: {_bad}")

print("test_tile_cache.py ok")
