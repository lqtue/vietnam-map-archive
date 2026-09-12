"""IIIF tile fetcher and grid utilities for the OCR pipeline."""

from __future__ import annotations

import hashlib
import math
import os
import time
from pathlib import Path
from typing import Generator

import requests
from PIL import Image
from io import BytesIO

CACHE_DIR = Path(__file__).resolve().parents[3] / ".tile_cache" / "ocr"


def _ia_direct_url(iiif_base: str) -> str | None:
    """Convert an IA IIIF base URL to a direct download URL, or None if not IA."""
    # IA IIIF base: https://iiif.archive.org/image/iiif/3/<item>%2F<file>
    import re, urllib.parse
    m = re.search(r"/iiif/\d+/(.+)$", iiif_base)
    if not m:
        return None
    encoded = m.group(1)
    decoded = urllib.parse.unquote(encoded)  # e.g. "vma-map-<uuid>/Map_of_Saigon_1882.jpg"
    parts = decoded.split("/", 1)
    if len(parts) != 2:
        return None
    item_id, filename = parts
    return f"https://archive.org/download/{item_id}/{filename}"


def _download_full(url: str, cache_path: Path) -> Image.Image:
    """Download a full image, suppressing DecompressionBomb warning for large maps."""
    import warnings
    from PIL import Image as _Image
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _Image.MAX_IMAGE_PIXELS = None
        img = _Image.open(BytesIO(resp.content)).convert("RGB")
    img.save(cache_path, format="JPEG", quality=90)
    return img


def fetch_crop(
    iiif_base: str,
    x: int,
    y: int,
    w: int,
    h: int,
    size: int = 1024,
    *,
    retries: int = 3,
    local_image: str | None = None,
    quality: str = "default",
    fit: bool = False,
) -> Image.Image:
    """Fetch a IIIF image crop, caching to disk.

    quality: IIIF quality token — "default" for v3/most v2, "native" for Gallica v2.
    fit: if True, use !{size},{size} (fit-within-box) instead of {size}, (width-only).
         Use for full-image fetches where you want max(w,h) <= size.

    If local_image is set, skips all network calls and crops from that file.
    Otherwise tries the IIIF region URL first; if the server returns 4xx/5xx
    (common on Internet Archive), falls back to downloading the full image and
    cropping locally.
    """
    # Local file path — crop directly, no network needed
    if local_image:
        import warnings
        from PIL import Image as _Image
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _Image.MAX_IMAGE_PIXELS = None
            full = _Image.open(local_image).convert("RGB")
        region = full.crop((x, y, x + w, y + h))
        region = region.resize((size, max(1, int(size * h / w))), Image.LANCZOS)
        return region

    # For full-image fetches at a known level, use exact {w},{h} — server serves from cache.
    # For crops or unknown sizes, use width-only {size}, or fit !{size},{size}.
    is_full = (x == 0 and y == 0 and w > 0 and h > 0)
    if fit:
        size_param = f"!{size},{size}"
    else:
        size_param = f"{size},"
    region_url = f"{iiif_base}/{x},{y},{w},{h}/{size_param}/0/{quality}.jpg"
    cache_key = hashlib.md5(region_url.encode()).hexdigest()
    cache_path = CACHE_DIR / f"{cache_key}.jpg"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        return Image.open(cache_path).convert("RGB")

    # Try IIIF region endpoint first
    try:
        resp = requests.get(region_url, timeout=30)
        if resp.ok:
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            img.save(cache_path)
            return img
    except Exception:
        pass

    # Fallback 1: a fixed tile pyramid (our R2 host, and any other level0
    # server). Cheaper than the full-image download below and the only path
    # that works for a mirrored map, so it goes first.
    try:
        stats: dict = {}
        img = fetch_crop_level0(iiif_base, x, y, w, h, size, quality, stats=stats)
        # Only a complete assembly is cacheable — see fetch_crop_level0.
        if stats.get("coverage", 0) >= 1.0:
            img.save(cache_path)
        return img
    except Exception:
        pass

    # Fallback 2: download full image and crop locally (works when IIIF region is broken)
    direct_url = _ia_direct_url(iiif_base)
    if direct_url:
        full_cache = CACHE_DIR / f"full_{hashlib.md5(direct_url.encode()).hexdigest()}.jpg"
        if full_cache.exists():
            import warnings
            from PIL import Image as _Image
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _Image.MAX_IMAGE_PIXELS = None
                full = _Image.open(full_cache).convert("RGB")
        else:
            print(f"\n  (IIIF region failed — downloading full image from IA ...)", flush=True)
            full = _download_full(direct_url, full_cache)

        region = full.crop((x, y, x + w, y + h))
        region = region.resize((size, int(size * h / w)), Image.LANCZOS)
        region.save(cache_path)
        return region

    raise RuntimeError(
        f"fetch_crop failed: IIIF region returned error and no IA direct URL found.\n"
        f"IIIF base: {iiif_base}"
    )


# ── Level0 tile assembly ──────────────────────────────────────────────────────
#
# Our own R2 host (`worker/`) renders nothing: it maps a IIIF path straight onto
# an R2 key, serving only the tiles `vips dzsave` wrote. An arbitrary region at
# an arbitrary scale — which is every request fetch_crop makes — is a 404, so
# without this every OCR run against a mirrored map failed on its first tile.
# Its info.json advertises `profile: level2`, which is untrue and is why this
# went unnoticed; do not trust that field, try the region and fall back.
#
# The addressing rule, established against the live host:
#   * scale factor from info.json's scaleFactors, but only those that exist —
#     the top factor is often advertised and absent (64 is listed, 32 is the
#     largest served on ours), so a missing level degrades to the next one down
#   * tile origin a multiple of tile_size * sf
#   * region width/height clipped to the image bounds
#   * rendered size = ceil(region_w / sf) — NOT a constant `256,`. A clipped
#     edge tile is narrower, and asking for 256 there 404s.

# Below this share of tiles, an assembled region is not worth returning: the
# caller cannot tell a white hole from blank paper.
MIN_LEVEL0_COVERAGE = 0.9

_INFO_CACHE: dict[str, dict] = {}


def _cached_info(iiif_base: str) -> dict:
    if iiif_base not in _INFO_CACHE:
        _INFO_CACHE[iiif_base] = get_image_info(iiif_base)
    return _INFO_CACHE[iiif_base]


def level0_tile_url(iiif_base: str, tx: int, ty: int, tw: int, th: int, sf: int,
                    quality: str = "default") -> str:
    """The one URL a dzsave pyramid actually holds for this tile.

    Both halves of the size segment are required. `--layout iiif3` names every
    size `w,h`; the bare `w,` form IIIF also allows is never written, so asking
    for it misses R2 and the worker proxies the tile to the originating library
    instead — the mirrored pyramid goes unused and parallel runs fail as
    upstream rate-limiting. Verified live: `256,256`, `82,256`, `256,167`.
    """
    return (
        f"{iiif_base}/{tx},{ty},{tw},{th}/"
        f"{math.ceil(tw / sf):d},{math.ceil(th / sf):d}/0/{quality}.jpg"
    )


def _pick_scale_factor(info: dict, region_w: int, size: int) -> int:
    """Largest downscale that still delivers at least `size` pixels across.

    Bigger factor = fewer tiles. Going past the requested width would upscale,
    so stop at the last factor whose rendered region is still wide enough.
    """
    factors = sorted(info.get("scale_factors") or [1])
    chosen = factors[0]
    for f in factors:
        if region_w / f >= size:
            chosen = f
        else:
            break
    return chosen


def fetch_crop_level0(
    iiif_base: str, x: int, y: int, w: int, h: int, size: int,
    quality: str = "default", stats: dict | None = None,
) -> Image.Image:
    """Compose an arbitrary region out of a fixed tile pyramid.

    Fetches every tile overlapping (x, y, w, h) at the coarsest scale factor
    that still satisfies `size`, pastes them, then crops and resizes exactly as
    a level2 server would have. Raises if no tile could be fetched at all.

    `stats`, when given, receives {"coverage": float} — 1.0 when every tile
    landed. The caller must not cache anything below 1.0: a hole is
    indistinguishable from blank paper once written to disk, and one bad run
    would otherwise poison every later one.
    """
    info = _cached_info(iiif_base)
    full_w, full_h = info["width"], info["height"]
    ts = info.get("tile_size", 256)
    if not full_w or not full_h:
        raise RuntimeError(f"level0 assembly needs width/height in info.json: {iiif_base}")

    for sf in _descending_from(_pick_scale_factor(info, w, size), info):
        step = ts * sf
        x0, y0 = (x // step) * step, (y // step) * step
        canvas = Image.new("RGB", (math.ceil((full_w - x0) / sf), math.ceil((full_h - y0) / sf)), "white")
        got = 0
        wanted = 0
        for ty in range(y0, min(y + h, full_h), step):
            for tx in range(x0, min(x + w, full_w), step):
                wanted += 1
                tw, th = min(step, full_w - tx), min(step, full_h - ty)
                url = level0_tile_url(iiif_base, tx, ty, tw, th, sf, quality)
                at = ((tx - x0) // sf, (ty - y0) // sf)

                # Per-tile disk cache. `fetch_crop` (the level2 path) has had one
                # since the start; this path never did, so every pass over a sheet
                # re-downloaded the same few thousand 256px tiles. Measured
                # 2026-09-12 on the 1942 sheet: 12.2 min of tile fetching against
                # 5.1 min of actual model time, repeated in full for each of three
                # runs over the same crop.
                #
                # Only whole tiles are cached, never the assembled crop — a partial
                # assembly is white paper to everything downstream (see the coverage
                # check below), and one written to disk would poison every later run.
                cpath = CACHE_DIR / f"l0_{hashlib.md5(url.encode()).hexdigest()}.jpg"
                if cpath.exists():
                    try:
                        canvas.paste(Image.open(cpath).convert("RGB"), at)
                        got += 1
                        continue
                    except Exception:
                        cpath.unlink(missing_ok=True)  # truncated write, refetch

                # Retry: measured 2026-09-04, some tiles of a mirrored map hang
                # rather than 404 — 3 of 8 timed out on an idle host for map
                # 3a446d85 while 8 of 8 succeeded for 0e02b9d9. A short timeout
                # with two retries turns most of those into hits; a 30s one just
                # made a 108-tile overview take twenty minutes.
                for attempt in range(3):
                    try:
                        resp = requests.get(url, timeout=10)
                        if not resp.ok:
                            break  # a real 404 will not become a 200 on retry
                        tile_img = Image.open(BytesIO(resp.content)).convert("RGB")
                        canvas.paste(tile_img, at)
                        CACHE_DIR.mkdir(parents=True, exist_ok=True)
                        tmp = cpath.with_suffix(".part")
                        tile_img.save(tmp, format="JPEG", quality=90)
                        tmp.replace(cpath)  # atomic: a killed run leaves no half tile
                        got += 1
                        break
                    except Exception:
                        continue
        if got:
            # A hole is white paper to everything downstream: the density pass
            # reads it as blank and the model reads it as nothing there. Silence
            # here cost a third of the 1968 sheet before anyone noticed, so a
            # partial assembly says so, and a mostly-empty one refuses.
            missing = wanted - got
            coverage = got / wanted
            if stats is not None:
                stats["coverage"] = coverage
            if missing:
                msg = (f"  level0: {missing} of {wanted} tiles unreadable "
                       f"({coverage:.0%} coverage) for {iiif_base}")
                if coverage < MIN_LEVEL0_COVERAGE:
                    raise RuntimeError(
                        msg + f" — below {MIN_LEVEL0_COVERAGE:.0%}; re-run tile_to_r2 for this map"
                    )
                print(msg + " — proceeding with gaps", flush=True)
            # Crop in canvas space, then scale to the width the caller asked for.
            if stats is not None:
                stats.setdefault("coverage", 1.0)
            cx, cy = (x - x0) // sf, (y - y0) // sf
            cw, ch = max(1, w // sf), max(1, h // sf)
            region = canvas.crop((cx, cy, cx + cw, cy + ch))
            return region.resize((size, max(1, round(size * h / w))), Image.LANCZOS)

    raise RuntimeError(
        f"level0 assembly fetched no tiles. IIIF base: {iiif_base} "
        f"region={x},{y},{w},{h} scale_factors={info.get('scale_factors')}"
    )


def _descending_from(sf: int, info: dict) -> list[int]:
    """`sf` and every smaller factor — a level advertised but not written 404s."""
    factors = sorted((info.get("scale_factors") or [1]), reverse=True)
    return [f for f in factors if f <= sf] or [1]


def _axis_tiles(
    start: int, extent: int, tile: int, step: int, offset: int = 0
) -> list[tuple[int, int]]:
    """One axis of the grid as (origin, size) pairs, clipped to the region.

    With `offset` 0 this is the plain grid: origins at `start + k*step`, the
    last one clipped at the far edge.

    With an offset the *lattice* is phase-shifted — origins at
    `start + offset + k*step` — so every seam of the unshifted grid lands
    inside a shifted tile. The tile that straddles `start` (lattice index -1)
    is kept and clipped to the region rather than dropped, which is what makes
    the shifted pass cover the same span as the unshifted one.

    Until 2026-09-10 `ocr.py` implemented the offset by insetting the region
    instead — `(rx + offset, rw - offset)` — which shortened the tiled extent
    by `offset` and so silently dropped a whole row or column whenever the
    shortened extent fell below a step boundary. On the 1882 gate sheet's
    `main_map` crop that cost pass 2 four of its tiles (20 instead of 24) and
    a quarter of its labels, because the leading `offset`-wide strip of the
    crop was never read at all. See EVAL-BASELINE.md and test_grid_offset.py.
    """
    if extent <= 0 or tile <= 0 or step <= 0:
        return []
    end = start + extent
    offset %= step  # a whole-step shift is the same lattice
    origins = [start + offset - step] if offset else []
    o = start + offset
    while o < end:
        origins.append(o)
        o += step
    out: list[tuple[int, int]] = []
    for o in origins:
        x = max(o, start)
        w = min(o + tile, end) - x
        if w <= 0:
            continue
        # Drop a tile that adds no pixels its predecessor did not already have.
        # `w > 0` alone kept a sliver, and on an offset grid the far edge makes
        # one every time: the 1968 sheet's crop is 10015 wide, so a 600-step
        # lattice phase-shifted by 400 puts its last origin 15 px from the end
        # and yields a 15x800 column entirely inside the 615x800 one before it.
        #
        # It is not merely redundant, it is destructive. Gemini answers a 15 px
        # strip with `400 INVALID_ARGUMENT: Unable to process input image`, and
        # row-sequence packs four tiles into one call — so each sliver took its
        # three real neighbours down with it. Measured on run
        # `body-1968-20260910h-t800off`: 16 slivers, and 13 perfectly good
        # 615-wide tiles lost as collateral, 32 of 306 tiles never read.
        #
        # Containment rather than a pixel floor, because containment is the
        # exact statement of "this tile is worthless" and needs no threshold to
        # argue about. A clipped far-edge tile that still reaches past its
        # predecessor is kept, however narrow.
        if out and x >= out[-1][0] and x + w <= out[-1][0] + out[-1][1]:
            continue
        out.append((x, w))
    return out


def tile_grid(
    width: int,
    height: int,
    tile: int = 2048,
    overlap: int = 256,
    region: tuple[int, int, int, int] | None = None,
    offset: int = 0,
) -> Generator[tuple[int, int, int, int], None, None]:
    """Yield (x, y, w, h) tuples covering the full image or a sub-region with overlap.

    `offset` phase-shifts the grid in both axes without shrinking what it
    covers — the second pass of the two-pass recipe. See `_axis_tiles`.
    """
    if region:
        rx, ry, rw, rh = region
    else:
        rx, ry, rw, rh = 0, 0, width, height

    step = tile - overlap
    cols = _axis_tiles(rx, rw, tile, step, offset)
    rows = _axis_tiles(ry, rh, tile, step, offset)
    for y, h in rows:
        for x, w in cols:
            yield x, y, w, h


def get_iiif_base_from_supabase(map_id: str) -> str | None:
    """Resolve maps.iiif_image for a given map UUID via Supabase REST API."""
    from dotenv import load_dotenv
    from pathlib import Path as _Path

    load_dotenv(_Path(__file__).resolve().parents[3] / ".env")
    supabase_url = os.environ.get("PUBLIC_SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get(
        "PUBLIC_SUPABASE_ANON_KEY"
    )

    if not supabase_url or not service_key:
        raise EnvironmentError(
            "Set PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"
        )

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }
    resp = requests.get(
        f"{supabase_url}/rest/v1/maps",
        headers=headers,
        params={"id": f"eq.{map_id}", "select": "iiif_image,allmaps_id"},
        timeout=15,
    )
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        return None
    return rows[0].get("iiif_image") or None


def get_iiif_base_from_allmaps(allmaps_id: str) -> str | None:
    """Resolve IIIF base URL via Allmaps annotation API (fallback)."""
    resp = requests.get(
        f"https://annotations.allmaps.org/maps/{allmaps_id}",
        timeout=15,
    )
    if not resp.ok:
        return None
    ann = resp.json()
    return (
        ann.get("items", [{}])[0]
        .get("target", {})
        .get("source", {})
        .get("id")
    )


def estimate_density(image: Image.Image) -> float:
    """Return a 0–1 density score based on pixel std-dev (higher = denser/more detail).

    Used to decide render resolution: dense urban core → higher res; sparse → lower.
    """
    import statistics
    gray = image.convert("L")
    pixels = list(gray.getdata())
    mean = sum(pixels) / len(pixels)
    variance = sum((p - mean) ** 2 for p in pixels) / len(pixels)
    std = variance ** 0.5
    # Typical range: ~10 (blank water/margin) to ~70 (dense urban cadastral grid)
    return min(std / 70.0, 1.0)


def adaptive_render_size(image: Image.Image, low: int = 1024, high: int = 2048, threshold: float = 0.35) -> int:
    """Return high or low render size based on tile density."""
    return high if estimate_density(image) >= threshold else low


# ── Adaptive-contrast pre-pass (CLAHE) ────────────────────────────────────────
#
# Faded French colonial scans lose their thin hand-lettered toponyms into the
# paper: locally the ink/paper gap is a handful of grey levels, globally the
# sheet still spans 0-255 so a plain histogram stretch does nothing. CLAHE
# equalizes per-region instead, with a clip limit so the flat paper between
# strokes is not amplified into noise.
#
# Applied to **luminance only** (LAB L). Equalizing per RGB channel would move
# hue and saturation, and `compute_tile_colours` scores the water/vegetation
# wash in HSV — the pre-pass must never be able to reach that signal. It cannot:
# it runs on the per-tile render on its way to the model, long after the shared
# overview the colour pass reads. See docs/pipelines.md.
#
# ponytail: pure numpy + Pillow, ~30 lines, because there is no cv2 wheel for
# Python 3.14 and this must not add a dependency. Ceiling: a full 2048px tile
# costs ~0.2s and four 256-entry LUT gathers of float32 (~64 MB peak), and the
# interpolation is bilinear between tile centres exactly as cv2 does it, so
# output is equivalent but not bit-identical. Upgrade path if it ever shows up
# in the profile — `cv2.createCLAHE(clipLimit, tileGridSize).apply(L)` on the
# same L channel, same flag surface, delete `_clahe_lut` and this function's
# body. Nothing downstream sees the difference.


def _clahe_lut(block, clip_limit: float):
    """Clipped, excess-redistributed CDF for one grid block → a 256-entry LUT."""
    import numpy as np

    n = block.size
    if n == 0:
        return np.arange(256, dtype=np.float32)
    hist = np.bincount(block.ravel(), minlength=256).astype(np.int64)
    # Clip tall bins (flat paper) and spread what was cut back over all levels.
    limit = max(1, int(clip_limit * n / 256.0))
    excess = int(np.maximum(hist - limit, 0).sum())
    hist = np.minimum(hist, limit) + excess // 256
    cdf = np.cumsum(hist)
    # max(...,1) is the uniform-image guard: a flat block still has a non-zero
    # total after redistribution, but never divide by an unchecked cdf.
    return (cdf * (255.0 / max(int(cdf[-1]), 1))).astype(np.float32)


def apply_clahe(
    image: Image.Image,
    clip_limit: float = 2.0,
    grid: int | tuple[int, int] = 8,
) -> Image.Image:
    """Contrast-Limited Adaptive Histogram Equalization on the LAB L channel.

    clip_limit: histogram clip, as a multiple of the flat-histogram bin height.
                1.0 ≈ no equalization, 2.0 is a safe default, >4 gets noisy.
    grid:       grid blocks — an int for square, or (rows, cols).

    Pure function: no network, no cache, no mutation of the input.
    """
    import numpy as np

    if isinstance(grid, int):
        grid = (grid, grid)
    gy, gx = max(1, int(grid[0])), max(1, int(grid[1]))

    lab = np.array(image.convert("LAB"), dtype=np.uint8)
    lum = lab[:, :, 0]
    h, w = lum.shape
    if h == 0 or w == 0:
        return image.copy()

    ys = np.linspace(0, h, gy + 1).round().astype(int)
    xs = np.linspace(0, w, gx + 1).round().astype(int)
    luts = np.empty((gy, gx, 256), dtype=np.float32)
    for i in range(gy):
        for j in range(gx):
            luts[i, j] = _clahe_lut(lum[ys[i]:ys[i + 1], xs[j]:xs[j + 1]], clip_limit)

    # Bilinear blend between the four surrounding block centres, so block
    # boundaries do not show up as seams the model would read as strokes.
    def _axis(centres, length, count):
        coord = np.arange(length, dtype=np.float32)
        i1 = np.clip(np.searchsorted(centres, coord), 0, count - 1)
        i0 = np.clip(i1 - 1, 0, count - 1)
        span = np.where(i1 > i0, centres[i1] - centres[i0], 1.0)
        t = np.clip((coord - centres[i0]) / span, 0.0, 1.0).astype(np.float32)
        return i0, i1, t

    iy0, iy1, ty = _axis((ys[:-1] + ys[1:] - 1) * 0.5, h, gy)
    jx0, jx1, tx = _axis((xs[:-1] + xs[1:] - 1) * 0.5, w, gx)

    Iy0, Iy1 = iy0[:, None], iy1[:, None]
    Jx0, Jx1 = jx0[None, :], jx1[None, :]
    TY, TX = ty[:, None], tx[None, :]
    top = luts[Iy0, Jx0, lum] * (1.0 - TX) + luts[Iy0, Jx1, lum] * TX
    bot = luts[Iy1, Jx0, lum] * (1.0 - TX) + luts[Iy1, Jx1, lum] * TX

    lab[:, :, 0] = np.rint(top * (1.0 - TY) + bot * TY).clip(0, 255).astype(np.uint8)
    return Image.fromarray(lab, mode="LAB").convert("RGB")


def detect_neatline(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Detect map content bounding box (neatline) from a low-res overview.

    Returns (x, y, w, h) in the overview's pixel space, or None if the
    content fills >95% of the image (no meaningful margins to crop).
    """
    try:
        import numpy as np
    except ImportError:
        return None
    gray = np.array(image.convert("L"), dtype=np.float32)
    h, w = gray.shape
    content_mask = gray < 230
    rows_any = np.any(content_mask, axis=1)
    cols_any = np.any(content_mask, axis=0)
    if not rows_any.any() or not cols_any.any():
        return None
    rmin, rmax = int(np.where(rows_any)[0][0]), int(np.where(rows_any)[0][-1])
    cmin, cmax = int(np.where(cols_any)[0][0]), int(np.where(cols_any)[0][-1])
    bw, bh = cmax - cmin, rmax - rmin
    if bw * bh > 0.95 * w * h:
        return None
    return (cmin, rmin, bw, bh)


def compute_tile_densities(
    overview: Image.Image,
    tiles: list[tuple[int, int, int, int]],
    full_w: int,
    full_h: int,
    text_threshold: float = 25.0,
) -> dict[tuple[int, int, int, int], float]:
    """Compute text-likelihood fraction for each tile from a low-res overview.

    Uses local 8×8 std-dev to detect high-frequency ink (text) vs smooth areas.
    Returns {tile: fraction} where fraction is 0-1 (pct of tile area with
    local std-dev above text_threshold).
    """
    try:
        import numpy as np
        from scipy.ndimage import uniform_filter
    except ImportError:
        return {t: 1.0 for t in tiles}

    gray = np.array(overview.convert("L"), dtype=np.float32)
    h, w = gray.shape
    local_mean = uniform_filter(gray, size=8)
    local_sqmean = uniform_filter(gray ** 2, size=8)
    local_std = np.sqrt(np.maximum(local_sqmean - local_mean ** 2, 0))

    densities = {}
    for tile in tiles:
        tx, ty, tw, th = tile
        ox = int(tx / full_w * w)
        oy = int(ty / full_h * h)
        ow = max(1, int(tw / full_w * w))
        oh = max(1, int(th / full_h * h))
        region = local_std[oy : oy + oh, ox : ox + ow]
        densities[tile] = float(np.mean(region > text_threshold)) if region.size > 0 else 0.0
    return densities


def compute_tile_colours(
    overview: "Image.Image",
    tiles: list[tuple[int, int, int, int]],
    full_w: int,
    full_h: int,
) -> dict[tuple[int, int, int, int], float]:
    """Fraction of each tile covered by flat colour wash — water or vegetation.

    A blue or green wash on a historical map is a river, a park or a paddy: it
    carries almost no toponyms, but its edges are busy enough that the text
    density pre-pass sees "ink" and pays for a full render anyway.

    Hue is taken in HSV: water ≈ 150–260°, vegetation ≈ 60–150°, both only when
    the pixel is saturated enough to be a deliberate wash rather than aged
    paper. A monochrome scan returns ~0 everywhere, which is the point — the
    caller must not act on a signal that is not there.

    **Measured null result, 1882 Saigon cadastral, 2026-09-04.** This scores
    0.000 on every tile of that sheet, and not because of the saturation gate:
    dropping it from 0.25 to 0.10 changes nothing. Every saturated pixel on the
    sheet sits in hue 0–60° — warm aged paper and the pink parcel tints — and
    nothing at all falls in the 60–260° band this looks for. Its blue river and
    green parks are pale enough to read as warm paper in HSV. So on a
    warm-toned colonial scan the wash demotion is a no-op. Do not rely on it
    until it has been measured on a sheet where it fires; see
    `docs/pipelines.md` and `EVAL-BASELINE.md`.
    """
    try:
        import numpy as np
    except ImportError:
        return {t: 0.0 for t in tiles}

    hsv = np.array(overview.convert("HSV"), dtype=np.float32)
    hue = hsv[:, :, 0] * 360.0 / 255.0
    sat = hsv[:, :, 1] / 255.0
    val = hsv[:, :, 2] / 255.0

    # Saturated, not near-black (ink), not near-white (paper).
    washed = (sat > 0.25) & (val > 0.2) & (val < 0.97)
    coloured = washed & (((hue >= 60) & (hue < 150)) | ((hue >= 150) & (hue < 260)))

    h, w = hue.shape
    out: dict[tuple[int, int, int, int], float] = {}
    for tile in tiles:
        tx, ty, tw, th = tile
        ox = int(tx / full_w * w)
        oy = int(ty / full_h * h)
        ow = max(1, int(tw / full_w * w))
        oh = max(1, int(th / full_h * h))
        region = coloured[oy : oy + oh, ox : ox + ow]
        out[tile] = float(np.mean(region)) if region.size > 0 else 0.0
    return out


def auto_tile_overrides(
    densities: dict[tuple[int, int, int, int], float],
    skip_below: float = 0.01,
    low_res_below: float = 0.08,
    colours: dict[tuple[int, int, int, int], float] | None = None,
    wash_above: float = 0.6,
) -> dict[str, str]:
    """Turn per-tile pre-pass fractions into a priority-grid override map.

    Auto-fills what the Triage grid does by hand: blank tiles (below skip_below)
    → "skip" so they cost no API call; sparse tiles (below low_res_below) → a
    cheap low-res render; dense tiles are omitted (full render, the default).
    Same {"x_y_w_h": "skip"|"low_res"} shape ocr.py already consumes.

    `colours` adds the water/vegetation pass: a tile that is mostly wash gets
    demoted one step — full render becomes low_res, low_res becomes skip. It
    only ever demotes, so a mislabelled wash costs resolution, never a tile.
    """
    out: dict[str, str] = {}
    for tile, frac in densities.items():
        x, y, w, h = tile
        key = f"{x}_{y}_{w}_{h}"
        wash = (colours or {}).get(tile, 0.0)

        if frac < skip_below:
            out[key] = "skip"
        elif frac < low_res_below:
            out[key] = "skip" if wash >= wash_above else "low_res"
        elif wash >= wash_above:
            out[key] = "low_res"
    return out


AOI_GEO_HINT = (
    "--aoi takes WGS84 lng/lat, and this pipeline has no georeferencer: the "
    "Allmaps transform lives on the JS side (src/lib/server/transformer.ts), "
    "not in Python. Warp the study area to source-image pixels first "
    "(GcpTransformer.transformToResource on the map's annotation) and pass "
    "--aoi-px x0,y0,x1,y1."
)


def parse_aoi_px(spec: str) -> tuple[int, int, int, int]:
    """Parse "x0,y0,x1,y1" source-image pixels into a corner-ordered rect.

    Corners may arrive in any order — the caller warped four geo corners and
    a rotated map does not keep them sorted.
    """
    try:
        x0, y0, x1, y1 = (int(round(float(v))) for v in spec.split(","))
    except ValueError:
        raise ValueError("--aoi-px must be x0,y0,x1,y1 in source image pixels") from None
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def aoi_tile_overrides(
    tiles: list[tuple[int, int, int, int]],
    aoi_px: tuple[int, int, int, int],
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Mark every tile outside the AOI "skip", leaving the rest untouched.

    A study area (District 4 is the first one) is a filter, not a priority
    signal: a tile that overlaps it keeps whatever --auto-priority or the
    Triage grid decided, and a tile that does not becomes "skip" so the
    existing override machinery drops it. This never promotes — the AOI can
    only take tiles away.

    Rectangles are half-open, so a tile whose edge merely touches the AOI
    boundary counts as outside; a tile straddling it counts as inside.

    # ponytail: the AOI is an axis-aligned rectangle in pixel space. A
    # rotated or badly-skewed map means the caller's pixel bbox over-covers
    # the true geo polygon, so a few extra tiles survive. Over-covering costs
    # API calls; under-covering would lose labels, so the ceiling is the safe
    # side of the trade.
    """
    ax0, ay0, ax1, ay1 = aoi_px
    out = dict(overrides or {})
    for tx, ty, tw, th in tiles:
        inside = tx < ax1 and tx + tw > ax0 and ty < ay1 and ty + th > ay0
        if not inside:
            out[f"{tx}_{ty}_{tw}_{th}"] = "skip"
    return out


def auto_tile_params(
    full_w: int,
    full_h: int,
    target_calls: int = 12,
    base_render: int = 1024,
    base_tile: int = 2400,
    overlap_ratio: float = 0.125,
) -> tuple[int, int, int]:
    """Compute tile_size, overlap, and render_size to hit a target call count.

    Scales tile_size up (and render_size proportionally) so that the uniform
    grid produces approximately target_calls tiles. Maintains constant
    pixel density per source pixel.

    Returns (tile_size, overlap, render_size).
    """
    import math

    best_tile = base_tile
    best_diff = float("inf")
    for tile_sz in range(base_tile, max(full_w, full_h) + 1, 200):
        ovlp = int(tile_sz * overlap_ratio)
        step = tile_sz - ovlp
        cols = math.ceil(max(full_w - ovlp, 1) / step)
        rows = math.ceil(max(full_h - ovlp, 1) / step)
        n = cols * rows
        diff = abs(n - target_calls)
        if diff < best_diff:
            best_diff = diff
            best_tile = tile_sz
        if n <= target_calls:
            break

    overlap = int(best_tile * overlap_ratio)
    render_size = int(best_tile * base_render / base_tile)
    render_size = min(render_size, 4096)
    return best_tile, overlap, render_size


def get_image_info(iiif_base: str, retries: int = 3) -> dict:
    """Fetch IIIF info.json.

    Returns:
        width, height       — full-resolution dimensions
        version             — 2 or 3
        quality             — "default" or "native" (Gallica BnF v2)
        sizes               — list of {"width": int, "height": int} pre-rendered levels,
                              sorted ascending by width. Empty list if server omits it.
        scale_factors       — list of ints from tiles[0].scaleFactors (e.g. [1,2,4,8,16]).
                              Empty list if server omits tiles.

    sizes are the levels the server has already rendered — requesting these exact
    dimensions avoids server-side scaling and is cheaper/faster.
    scale_factors describe the tile pyramid: factor N means full_w // N pixels wide.
    """
    url = f"{iiif_base}/info.json"
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=45)
            resp.raise_for_status()
            data = resp.json()

            context = data.get("@context", "")
            if isinstance(context, list):
                context = " ".join(str(c) for c in context)
            version = 3 if ("image/3" in context or data.get("type") == "ImageService3") else 2

            quality = "default"
            if version == 2:
                profile = data.get("profile", [])
                if isinstance(profile, list) and len(profile) > 1 and isinstance(profile[1], dict):
                    qualities = profile[1].get("qualities", [])
                    if "native" in qualities and "default" not in qualities:
                        quality = "native"

            # Pre-rendered size levels — sorted ascending by width
            raw_sizes = data.get("sizes", [])
            sizes = sorted(
                [{"width": int(s["width"]), "height": int(s["height"])} for s in raw_sizes
                 if "width" in s and "height" in s],
                key=lambda s: s["width"],
            )

            # Tile pyramid scale factors (tiles[0].scaleFactors)
            tiles_arr = data.get("tiles", [])
            scale_factors: list[int] = []
            tile_size = 256
            if tiles_arr and isinstance(tiles_arr[0], dict):
                scale_factors = [int(f) for f in tiles_arr[0].get("scaleFactors", [])]
                tile_size = int(tiles_arr[0].get("width", 256))

            return {
                "width": int(data.get("width", 0)),
                "height": int(data.get("height", 0)),
                "version": version,
                "quality": quality,
                "sizes": sizes,
                "scale_factors": scale_factors,
                "tile_size": tile_size,
            }
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise


def choose_scale_levels(
    info: dict,
    targets: tuple[int, ...] = (1024, 2048, 4096),
) -> list[dict]:
    """Pick the best pre-rendered IIIF size levels for a multi-scale sequence.

    Strategy:
      1. If info["sizes"] is non-empty, select the level closest to each target
         width — these are already rendered by the server, cheapest to fetch.
      2. If sizes is empty but scale_factors is available, derive levels from
         full_w // factor for each factor, then pick closest to targets.
      3. Fallback: use target widths directly (server scales on the fly).

    Returns list of {"width": int, "height": int} dicts, ascending by width,
    deduplicated and capped at full_w.
    """
    full_w = info["width"]
    full_h = info["height"]
    aspect = full_h / full_w if full_w else 1.0

    candidates: list[dict] = info.get("sizes", [])

    if not candidates:
        # Derive from scale_factors
        for f in info.get("scale_factors", []):
            if f > 0:
                w = full_w // f
                h = int(w * aspect)
                if w > 0:
                    candidates.append({"width": w, "height": h})

    if not candidates:
        # Pure fallback: use targets directly
        return [
            {"width": t, "height": int(t * aspect)}
            for t in targets if t <= full_w
        ]

    chosen: list[dict] = []
    seen_widths: set[int] = set()
    for target in targets:
        if target > full_w:
            continue
        best = min(candidates, key=lambda s: abs(s["width"] - target))
        if best["width"] not in seen_widths:
            chosen.append(best)
            seen_widths.add(best["width"])

    return sorted(chosen, key=lambda s: s["width"])




def _self_check() -> None:
    """Colour pre-pass, CLAHE, override rules and AOI triage — no network, no real map.

    Run: python work/ocr/scripts/iiif_tiles.py --self-check
    """
    from PIL import Image as _Image

    # Density tiers, unchanged by the colour pass being absent.
    _d = {(0, 0, 10, 10): 0.005,   # blank  → skip
          (10, 0, 10, 10): 0.05,   # sparse → low_res
          (20, 0, 10, 10): 0.40}   # dense  → omitted (full render)
    assert auto_tile_overrides(_d, skip_below=0.01, low_res_below=0.08) == {
        "0_0_10_10": "skip", "10_0_10_10": "low_res"
    }

    tiles = [(0, 0, 100, 100), (100, 0, 100, 100)]

    # Left half a saturated blue wash, right half bare paper.
    img = _Image.new("RGB", (200, 100), (245, 240, 230))
    for x in range(100):
        for y in range(100):
            img.putpixel((x, y), (70, 110, 200))
    colours = compute_tile_colours(img, tiles, 200, 100)
    assert colours[(0, 0, 100, 100)] > 0.9, colours
    assert colours[(100, 0, 100, 100)] < 0.1, colours

    # A monochrome scan must produce no signal at all: acting on one would
    # demote tiles on every grey map in the archive.
    grey = _Image.new("RGB", (200, 100), (128, 126, 124))
    assert max(compute_tile_colours(grey, tiles, 200, 100).values()) < 0.05

    # Demotion is one step and never promotes.
    dense = {tiles[0]: 0.5, tiles[1]: 0.5}
    assert auto_tile_overrides(dense) == {}
    assert auto_tile_overrides(dense, colours={tiles[0]: 0.9, tiles[1]: 0.0}) == {
        "0_0_100_100": "low_res"
    }
    sparse = {tiles[0]: 0.05}
    assert auto_tile_overrides(sparse) == {"0_0_100_100": "low_res"}
    assert auto_tile_overrides(sparse, colours={tiles[0]: 0.9}) == {"0_0_100_100": "skip"}
    blank = {tiles[0]: 0.0}
    assert auto_tile_overrides(blank, colours={tiles[0]: 0.0}) == {"0_0_100_100": "skip"}

    # ── CLAHE pre-pass ──────────────────────────────────────────────────────
    import numpy as _np

    def _std(i) -> float:
        return float(_np.asarray(i.convert("L"), dtype=_np.float32).std())

    def _grey(a) -> "_Image.Image":
        return _Image.fromarray(_np.dstack([a.astype(_np.uint8)] * 3))

    rng = _np.random.default_rng(7)

    # A faded scan: full texture squeezed into a 20-level band. This is the
    # case the flag exists for, so require a real gain, not a nudge.
    faded = _grey(118 + rng.random((512, 512)) * 20)
    faded_bytes = faded.tobytes()
    faded_std = _std(faded)
    lifted = apply_clahe(faded, 2.0, 8)
    assert lifted.size == faded.size and lifted.mode == "RGB"
    assert _std(lifted) > 2.0 * faded_std, (faded_std, _std(lifted))

    # Pure function: the caller's image is not mutated in place.
    assert faded.tobytes() == faded_bytes

    # An already-crisp ink-on-paper tile must not be wrecked. CLAHE's clip is
    # what buys this; a plain histogram equalization would not.
    crisp = _grey(_np.where(rng.random((512, 512)) > 0.8, 20, 235))
    before, after = _std(crisp), _std(apply_clahe(crisp, 2.0, 8))
    assert 0.9 * before < after < 1.1 * before, (before, after)

    # A uniform image has one occupied bin: no divide-by-zero, no NaN, and it
    # stays uniform (a blank margin tile must not become noise).
    for flat in (_Image.new("RGB", (64, 64), (128, 128, 128)),
                 _Image.new("RGB", (64, 64), (0, 0, 0)),
                 _Image.new("RGB", (64, 64), (255, 255, 255))):
        out = apply_clahe(flat, 2.0, 8)
        assert _std(out) == 0.0, (flat.getpixel((0, 0)), _std(out))

    # Degenerate geometry: 1x1, a single global block, a non-square grid.
    assert apply_clahe(_Image.new("RGB", (1, 1), (40, 40, 40)), 2.0, 8).size == (1, 1)
    assert _std(apply_clahe(faded, 2.0, 1)) > faded_std
    assert apply_clahe(faded, 2.0, (4, 16)).size == (512, 512)

    # Luminance only: a saturated wash keeps its hue, so the water/vegetation
    # score compute_tile_colours reads cannot move even if the pre-pass were
    # ever misplaced upstream of it.
    wash = _Image.new("RGB", (200, 100), (70, 110, 200))
    for x in range(100, 200):
        for y in range(100):
            wash.putpixel((x, y), (245, 240, 230))
    wash_tiles = [(0, 0, 100, 100), (100, 0, 100, 100)]
    plain = compute_tile_colours(wash, wash_tiles, 200, 100)
    equalized = compute_tile_colours(apply_clahe(wash, 2.0, 8), wash_tiles, 200, 100)
    assert plain[(0, 0, 100, 100)] > 0.9 and equalized[(0, 0, 100, 100)] > 0.9, (plain, equalized)
    assert plain[(100, 0, 100, 100)] < 0.1 and equalized[(100, 0, 100, 100)] < 0.1, (plain, equalized)

    # ── AOI triage ──────────────────────────────────────────────────────────
    # Corners in any order normalise to a corner-ordered rect.
    assert parse_aoi_px("300,80,100,20") == (100, 20, 300, 80)
    assert parse_aoi_px(" 10 , 10 , 20.6 , 20.4 ") == (10, 10, 21, 20)
    try:
        parse_aoi_px("106.7,10.7")
    except ValueError as e:
        assert "--aoi-px" in str(e), e
    else:
        raise AssertionError("parse_aoi_px accepted a 2-value spec")

    # One row of three 100px tiles; the AOI covers the middle one and clips
    # 20px into the first, leaving the third untouched by it.
    row = [(0, 0, 100, 100), (100, 0, 100, 100), (200, 0, 100, 100)]
    assert aoi_tile_overrides(row, (80, 0, 200, 100)) == {"200_0_100_100": "skip"}

    # Fully inside → untouched; fully outside → skip; straddling → untouched.
    assert aoi_tile_overrides(row, (100, 0, 200, 100)) == {
        "0_0_100_100": "skip", "200_0_100_100": "skip"
    }

    # Touching the boundary is outside: tile 1 ends exactly where the AOI starts.
    assert aoi_tile_overrides(row, (100, 0, 150, 50)) == {
        "0_0_100_100": "skip", "200_0_100_100": "skip"
    }

    # An AOI covering everything changes nothing.
    assert aoi_tile_overrides(row, (0, 0, 300, 100)) == {}
    assert aoi_tile_overrides(row, (-1000, -1000, 5000, 5000)) == {}

    # An AOI covering nothing skips every tile.
    assert aoi_tile_overrides(row, (9000, 9000, 9100, 9100)) == {
        "0_0_100_100": "skip", "100_0_100_100": "skip", "200_0_100_100": "skip"
    }

    # Never promotes: an existing skip/low_res inside the AOI is left alone,
    # and an existing low_res outside it is demoted, not preserved.
    prior = {"0_0_100_100": "skip", "100_0_100_100": "low_res",
             "200_0_100_100": "low_res"}
    assert aoi_tile_overrides(row, (0, 0, 200, 100), prior) == prior | {
        "200_0_100_100": "skip"
    }
    # The caller's dict is not mutated.
    assert prior["200_0_100_100"] == "low_res"

    # ── level0 addressing ────────────────────────────────────────────────────
    info = {"width": 12102, "height": 8982, "scale_factors": [1, 2, 4, 8, 16, 32, 64],
            "tile_size": 256}
    B = "https://x/iiif/m"

    # size = ceil(region / sf) on both axes, written `w,h` — that is the key the
    # tiler wrote to R2, and `w,` alone misses it and falls through to the
    # upstream proxy (2cf6dd0). A clipped edge tile is smaller on both axes.
    assert level0_tile_url(B, 0, 0, 8192, 8192, 32).endswith("/0,0,8192,8192/256,256/0/default.jpg")
    assert level0_tile_url(B, 8192, 8192, 3910, 790, 32).endswith(
        "/8192,8192,3910,790/123,25/0/default.jpg"), "a clipped tile must round both sides up"

    # Coarsest factor that still delivers the width the caller asked for.
    assert _pick_scale_factor(info, 12102, 1024) == 8
    assert _pick_scale_factor(info, 2400, 1024) == 2
    assert _pick_scale_factor(info, 512, 1024) == 1, "never upscale to reach `size`"

    # A factor the server advertises but never wrote must degrade, not fail.
    assert _descending_from(64, info) == [64, 32, 16, 8, 4, 2, 1]
    assert _descending_from(1, info) == [1]
    assert _descending_from(4, {"scale_factors": []}) == [1]

    # A sheet narrower than every target yields no level at all — the caller
    # (ocr.py cmd_scout) must refuse it with a message, not index an empty list.
    thumb = {"width": 800, "height": 628, "sizes": [{"width": 800, "height": 628}]}
    assert choose_scale_levels(thumb, targets=(1024, 2048, 4096)) == []
    assert choose_scale_levels({"width": 800, "height": 628}, targets=(1024, 2048)) == []
    real = {"width": 7561, "height": 5601, "sizes": [{"width": 7561, "height": 5601}, {"width": 1890, "height": 1400}]}
    assert [l["width"] for l in choose_scale_levels(real, targets=(1024, 2048, 4096))] == [1890], "every target rounds to the 1890 level; dedup keeps one"

    # ── level0 per-tile disk cache ──────────────────────────────────────────
    # The property: a second assembly of the same region fetches nothing and
    # returns the same pixels. Without it every pass over a sheet re-downloads
    # the whole pyramid, which on the 1942 sheet was 12 min of the 17 min run.
    import tempfile as _tf, shutil as _sh

    _real_get, _real_cache = requests.get, CACHE_DIR
    _calls = {"n": 0}

    class _Resp:
        ok = True
        def __init__(self, b): self.content = b

    def _fake_get(url, timeout=None):
        _calls["n"] += 1
        buf = BytesIO()
        _Image.new("RGB", (256, 256), (200, 30, 30)).save(buf, format="JPEG")
        return _Resp(buf.getvalue())

    _tmp = Path(_tf.mkdtemp())
    try:
        globals()["CACHE_DIR"] = _tmp
        requests.get = _fake_get
        _INFO_CACHE["http://x/iiif/fake"] = {
            "width": 512, "height": 512, "tile_size": 256, "scale_factors": [1],
        }
        a = fetch_crop_level0("http://x/iiif/fake", 0, 0, 512, 512, size=128)
        first = _calls["n"]
        assert first == 4, f"cold assembly should fetch 4 tiles, fetched {first}"
        b = fetch_crop_level0("http://x/iiif/fake", 0, 0, 512, 512, size=128)
        assert _calls["n"] == first, "warm assembly must fetch nothing"
        assert a.tobytes() == b.tobytes(), "cached assembly must be pixel-identical"

        # A truncated cache file is refetched, not pasted as garbage.
        next(_tmp.glob("l0_*.jpg")).write_bytes(b"not a jpeg")
        c = fetch_crop_level0("http://x/iiif/fake", 0, 0, 512, 512, size=128)
        assert _calls["n"] == first + 1, "a corrupt tile must be refetched once"
        assert c.tobytes() == a.tobytes()
    finally:
        requests.get = _real_get
        globals()["CACHE_DIR"] = _real_cache
        _INFO_CACHE.pop("http://x/iiif/fake", None)
        _sh.rmtree(_tmp, ignore_errors=True)

    print("[ok] iiif_tiles self-check passed")


if __name__ == "__main__":
    import sys

    if "--self-check" in sys.argv:
        _self_check()
    else:
        print(__doc__)
        sys.exit(1)
