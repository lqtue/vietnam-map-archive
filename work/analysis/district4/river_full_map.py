#!/usr/bin/env python3
"""Run the exploratory river-color detector over an entire IIIF sheet at 1:1.

Downloads each native 256px level0 tile once, processes 1024px cores with a
32px overlap halo, and writes a disk-backed candidate mask plus review previews.
The crop-tuned thresholds are deliberately unchanged: this run tests transfer
across each full sheet, not a validated georeference.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ocr" / "scripts"))
from iiif_tiles import level0_tile_url  # noqa: E402

from river_probe import SETTINGS, disk  # noqa: E402


MAPS = {
    "1923": ("1bce28f0-aa82-48eb-8e33-8f0b07182c2f", 16064, 14027),
    # 1942 is the 2026 rescan its GCPs were placed on, not the older 7479x6314
    # image: twice the linear resolution, colour-matched, and it removes the
    # 1.994 factor between source pixels and the annotation.
    "1942": ("eca788e5-6780-4dca-bf23-7651a1c48aba-20260911", 14915, 12602),
    "1959": ("34d4edb2-f7df-4c47-a65a-f6b471400396", 14000, 10773),
    "1968": ("3a446d85-25a8-4e81-9cfc-8de357c3a5df", 10816, 13523),
}
TILE = 256
CORE = 1024
HALO = 32

# Metres per source pixel, from each sheet's live scan (docs/journals/260920-colour-transfer.md).
MPP = {"1923": 0.8452, "1942": 0.8473, "1959": 0.9974, "1968": 1.2729}

# The tighten pass is specified in ground units, not pixels, so one setting covers
# four scans at four resolutions. Water is a solid fill or a dense hatch; the wash,
# the fold creases, the neat-line, the title lettering and the roads are not.
OCC_WINDOW_M = 18.0    # occupancy neighbourhood: rejects the dithered colour wash
OCC_MIN = 0.80         # 1923 wash measures 0.2-0.75, real water 1.0
SEED_RADIUS_M = 8.0    # erosion radius: keeps water wider than ~16 m, kills thin lines
MIN_AREA_M2 = 2000.0   # residue floor
FRAME_SEARCH = 0.18    # the neat-line is looked for in this margin of each edge
FRAME_MIN_COVER = 0.60 # below this the detection is rejected, not trusted


def download_tiles(year: str, root: Path, workers: int) -> tuple[int, int]:
    map_id, width, height = MAPS[year]
    base = f"https://iiif.maparchive.vn/iiif/{map_id}"
    info = requests.get(f"{base}/info.json", timeout=30).json()
    if (info["width"], info["height"]) != (width, height):
        raise RuntimeError(f"{year} IIIF scan changed: {info['width']}x{info['height']}")
    tile_dir = root / "tiles"
    tile_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(x, y, min(TILE, width - x), min(TILE, height - y))
            for y in range(0, height, TILE) for x in range(0, width, TILE)]
    missing = [job for job in jobs if not (tile_dir / f"{job[0]}_{job[1]}.jpg").exists()]
    print(f"{year}: {len(jobs)} native tiles, {len(missing)} to fetch", flush=True)

    def fetch(job: tuple[int, int, int, int]) -> None:
        x, y, w, h = job
        url = level0_tile_url(base, x, y, w, h, 1)
        path = tile_dir / f"{x}_{y}.jpg"
        # The tile server resets connections under concurrency. Retry with a
        # backoff rather than hammering it: without the sleep a reset kills the
        # whole run, and the sheet has to start over.
        for attempt in range(5):
            try:
                response = requests.get(url, timeout=25)
                response.raise_for_status()
                image = Image.open(BytesIO(response.content))
                if image.size != (w, h):
                    raise ValueError(f"{url}: returned {image.size}, expected {(w, h)}")
                tmp = path.with_suffix(".part")
                tmp.write_bytes(response.content)
                tmp.replace(path)
                return
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch, job) for job in missing]
        for done, future in enumerate(as_completed(futures), 1):
            future.result()
            if done % 200 == 0 or done == len(missing):
                print(f"{year}: fetched {done}/{len(missing)}", flush=True)
    return width, height


def region(tile_dir: Path, width: int, height: int,
           x: int, y: int, w: int, h: int) -> Image.Image:
    left, top = max(0, x - HALO), max(0, y - HALO)
    right, bottom = min(width, x + w + HALO), min(height, y + h + HALO)
    image = Image.new("RGB", (right - left, bottom - top))
    for ty in range((top // TILE) * TILE, bottom, TILE):
        for tx in range((left // TILE) * TILE, right, TILE):
            tile = Image.open(tile_dir / f"{tx}_{ty}.jpg").convert("RGB")
            sx0, sy0 = max(left, tx), max(top, ty)
            sx1, sy1 = min(right, tx + tile.width), min(bottom, ty + tile.height)
            image.paste(tile.crop((sx0 - tx, sy0 - ty, sx1 - tx, sy1 - ty)),
                        (sx0 - left, sy0 - top))
    return image


PALETTE_1942 = Path(__file__).with_name("river_palette_1942.json")


def water_palette() -> tuple[np.ndarray, int]:
    """The frozen 1942 colour clusters, not a fresh fit.

    These were fitted once on the pinned 1024px crop and written to
    `river_palette_1942.json`. Reading them back keeps every run identical and
    removes the dependency on a file under /private/tmp, which is the only
    thing that made the earlier version unreproducible.
    """
    data = json.loads(PALETTE_1942.read_text())
    return np.asarray(data["centers"], dtype=np.float32), int(data["water_index"])


def candidate(image: Image.Image, year: str,
              palette: tuple[np.ndarray, int] | None) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    if year == "1942":
        assert palette is not None
        centers, water = palette
        best = np.full(rgb.shape[:2], np.inf, dtype=np.float32)
        labels = np.zeros(rgb.shape[:2], dtype=np.uint8)
        for i, center in enumerate(centers):
            distance = ((rgb - center) ** 2).sum(axis=2)
            better = distance < best
            labels[better] = i
            best[better] = distance[better]
        raw = labels == water
        closed = ndimage.binary_closing(raw, structure=disk(3))
        dark_bank = ndimage.binary_dilation(
            rgb.mean(axis=2) / 255 < 0.55, structure=np.ones((3, 3), bool)
        )
        occupancy = ndimage.uniform_filter(raw.astype(np.float32), size=21)
        result = closed & ~dark_bank & (occupancy > 0.35)
        result = ndimage.binary_closing(result, structure=disk(3))
    else:
        _, min_br, min_bg, max_rg, close = SETTINGS[year]
        r, g, b = rgb.transpose(2, 0, 1) / 255.0
        raw = (b - r > min_br) & (b - g > min_bg) & (r - g < max_rg)
        result = ndimage.binary_closing(raw, structure=disk(close))
    return ndimage.median_filter(result, size=3)


def preview(mask: np.memmap, width: int, height: int, factor: int) -> np.ndarray:
    pw, ph = math.ceil(width / factor), math.ceil(height / factor)
    out = np.zeros((ph, pw), np.uint8)
    starts = np.arange(0, width, factor)
    block_widths = np.minimum(factor, width - starts)
    for py in range(ph):
        strip = np.asarray(mask[py * factor:min(height, (py + 1) * factor)])
        totals = np.add.reduceat(strip, starts, axis=1).sum(axis=0)
        out[py] = np.rint(totals / (strip.shape[0] * block_widths) * 255).astype(np.uint8)
    return out


def write_review(mask: np.memmap, width: int, height: int,
                 root: Path, map_id: str, stem: str) -> int:
    """Write the downsampled density preview and the tinted overview overlay."""
    factor = math.ceil(width / 2048)
    small = preview(mask, width, height, factor)
    Image.fromarray(small).save(root / f"{stem}-preview.png")
    overview_url = f"https://iiif.maparchive.vn/iiif/{map_id}/full/800,/0/default.jpg"
    overview = Image.open(BytesIO(requests.get(overview_url, timeout=30).content)).convert("RGBA")
    rgba = Image.fromarray(small).resize(overview.size, Image.Resampling.BOX)
    tint = Image.new("RGBA", overview.size, (255, 0, 80, 100))
    overview.alpha_composite(Image.composite(tint, Image.new("RGBA", overview.size), rgba))
    overview.convert("RGB").save(root / f"{stem}-overlay.jpg", quality=90)
    return factor


def run(year: str, output_root: Path, workers: int) -> None:
    map_id, _, _ = MAPS[year]
    root = output_root / year
    root.mkdir(parents=True, exist_ok=True)
    width, height = download_tiles(year, root, workers)
    palette = water_palette() if year == "1942" else None
    mask_path = root / "candidate.uint8"
    mask = np.memmap(mask_path, dtype=np.uint8, mode="w+", shape=(height, width))
    tile_dir = root / "tiles"
    cores = [(x, y, min(CORE, width - x), min(CORE, height - y))
             for y in range(0, height, CORE) for x in range(0, width, CORE)]
    for i, (x, y, w, h) in enumerate(cores, 1):
        image = region(tile_dir, width, height, x, y, w, h)
        found = candidate(image, year, palette)
        ox, oy = x - max(0, x - HALO), y - max(0, y - HALO)
        mask[y:y + h, x:x + w] = found[oy:oy + h, ox:ox + w]
        if i % 40 == 0 or i == len(cores):
            print(f"{year}: processed {i}/{len(cores)} cores", flush=True)
    mask.flush()
    factor = write_review(mask, width, height, root, map_id, "candidate")
    (root / "run.json").write_text(json.dumps({
        "year": year, "map_id": map_id, "source_size": [width, height],
        "native_tile_size": TILE, "core": CORE, "halo": HALO,
        "preview_factor": factor, "candidate_pixels": int(mask.sum()),
        "settings": {"1942": "frozen palette " + PALETTE_1942.name}
                    if year == "1942" else {"thresholds": list(SETTINGS[year][1:])},
        "candidate_mask": mask_path.name,
        "status": "candidate only; crop thresholds, no global river selection or accuracy score",
    }, indent=2) + "\n")
    print(f"{year}: candidate pixels {int(mask.sum())}; preview {root / 'candidate-overlay.jpg'}")
    del mask
    tighten_only(year, output_root, width, height)


def tighten_only(year: str, output_root: Path,
                 width: int | None = None, height: int | None = None) -> None:
    """The selection pass over an existing candidate, without refetching tiles."""
    map_id, w, h = MAPS[year]
    width, height = width or w, height or h
    root = output_root / year
    box = frame_box(map_id, width, height)
    if box is None:
        print(f"{year}: neat-line rejected (covers < {FRAME_MIN_COVER:.0%}); no frame mask")
    stats = tighten(year, root, width, height, box)
    river = np.memmap(root / "river.uint8", np.uint8, "r", shape=(height, width))
    write_review(river, width, height, root, map_id, "river")
    record = json.loads((root / "run.json").read_text())
    record["tighten"] = {
        **stats,
        "settings_m": {"occupancy_window": OCC_WINDOW_M, "occupancy_min": OCC_MIN,
                       "seed_radius": SEED_RADIUS_M, "min_area": MIN_AREA_M2},
        "mpp": MPP[year],
        "river_mask": "river.uint8",
        "status": "selection only; no hand-drawn reference, no IoU or bank error",
    }
    (root / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{year}: river pixels {stats['river_pixels']} "
          f"({stats['river_pixels'] / int(np.asarray(river).size) * 100:.2f}% of scan); "
          f"kept {stats['components_kept']}/{stats['components_before']} components")


def frame_box(map_id: str, width: int, height: int) -> tuple[int, int, int, int] | None:
    """The printed neat-line, from the darkest rule near each edge of the overview.

    Returns source-pixel (x0, y0, x1, y1), or None when the result covers less
    of the sheet than `FRAME_MIN_COVER`. That rejection is the point: on 1968
    this picks up an interior rule and would cut half the map, so a bad box has
    to fail loudly rather than silently crop a river away.
    """
    # A level0 service serves only the sizes it advertises, and `maxWidth` is a
    # hard cap: the 1942 rescan tops out at 800, so a hardcoded 1600 returns an
    # error body rather than an image. Ask info.json what exists and take the
    # largest, which is ample for locating a margin.
    base = f"https://iiif.maparchive.vn/iiif/{map_id}"
    info = requests.get(f"{base}/info.json", timeout=30).json()
    widths = [s["width"] for s in info.get("sizes", []) if s.get("width")]
    cap = info.get("maxWidth")
    if cap:
        widths = [w for w in widths if w <= cap]
    if not widths:
        return None
    grey = Image.open(BytesIO(requests.get(
        f"{base}/full/{max(widths)},/0/default.jpg", timeout=60).content)).convert("L")
    dark = 255.0 - np.asarray(grey, np.float32)
    h, w = dark.shape

    def edges(profile: np.ndarray) -> tuple[int, int]:
        limit = int(len(profile) * FRAME_SEARCH)
        return (int(np.argmax(profile[:limit])),
                len(profile) - 1 - int(np.argmax(profile[::-1][:limit])))

    y0, y1 = edges(dark.mean(axis=1))
    x0, x1 = edges(dark.mean(axis=0))
    if (x1 - x0) * (y1 - y0) < FRAME_MIN_COVER * w * h:
        return None
    sx, sy = width / w, height / h
    return int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy)


def tighten(year: str, root: Path, width: int, height: int,
            box: tuple[int, int, int, int] | None = None) -> dict:
    """Turn the colour candidate into a river selection.

    Three rejections, in ground units so one setting covers all four scans:
    local occupancy drops the dithered colour wash, an erosion drops everything
    thinner than a river, and reconstruction from those seeds puts the full
    width back. Anything not connected to a seed, and anything under the area
    floor, is residue and goes.

    This is a selection step, not an accuracy result: no hand-drawn reference
    is involved anywhere in it.
    """
    mpp = MPP[year]
    window = max(3, int(round(OCC_WINDOW_M / mpp)) | 1)
    radius = max(2, int(round(SEED_RADIUS_M / mpp)))
    min_area = int(round(MIN_AREA_M2 / (mpp * mpp)))
    halo = window // 2 + radius + 2
    strip = 2048

    cand = np.memmap(root / "candidate.uint8", np.uint8, "r", shape=(height, width))
    solid = np.memmap(root / "solid.uint8", np.uint8, "w+", shape=(height, width))
    seed = np.memmap(root / "seed.uint8", np.uint8, "w+", shape=(height, width))
    # ponytail: strip-wise because a float32 occupancy over the whole 1923 sheet
    # is 900 MB and this environment has already killed a 4096px run with 137.
    for y0 in range(0, height, strip):
        y1 = min(height, y0 + strip)
        t0, t1 = max(0, y0 - halo), min(height, y1 + halo)
        block = np.asarray(cand[t0:t1], bool)
        occupancy = ndimage.uniform_filter(block.astype(np.float32), window)
        kept = block & (occupancy >= OCC_MIN)
        eroded = ndimage.binary_erosion(kept, structure=disk(radius))
        off = y0 - t0
        solid[y0:y1] = kept[off:off + (y1 - y0)]
        rows = eroded[off:off + (y1 - y0)]
        if box is not None:
            # Seed only inside the neat-line. The margin band, the title
            # lettering and the legend rules then have no seed and drop out at
            # reconstruction, while a river that runs off the sheet is still
            # seeded inside and rebuilt outwards rather than cut at the frame.
            fx0, fy0, fx1, fy1 = box
            outside = np.ones_like(rows)
            top, bottom = max(fy0 - y0, 0), max(min(fy1 - y0, y1 - y0), 0)
            outside[top:bottom, fx0:fx1] = 0
            rows = rows & ~outside.astype(bool)
        seed[y0:y1] = rows
    solid.flush()
    seed.flush()

    # Reconstruction is global, so it cannot be done strip-wise: label once on
    # disk, then keep a label only if a seed lands in it and it clears the floor.
    label = np.memmap(root / "label.int32", np.int32, "w+", shape=(height, width))
    count = int(ndimage.label(np.asarray(solid), output=label))
    area = np.zeros(count + 1, np.int64)
    seeded = np.zeros(count + 1, bool)
    for y0 in range(0, height, strip):
        y1 = min(height, y0 + strip)
        labels = np.asarray(label[y0:y1])
        area += np.bincount(labels.ravel(), minlength=count + 1)
        hit = labels[np.asarray(seed[y0:y1], bool)]
        if hit.size:
            seeded |= np.bincount(hit, minlength=count + 1) > 0
    table = seeded & (area >= min_area)
    table[0] = False

    river = np.memmap(root / "river.uint8", np.uint8, "w+", shape=(height, width))
    for y0 in range(0, height, strip):
        y1 = min(height, y0 + strip)
        river[y0:y1] = table[np.asarray(label[y0:y1])]
    river.flush()
    (root / "label.int32").unlink()
    return {"occupancy_window_px": window, "seed_radius_px": radius,
            "min_area_px": min_area, "neat_line_box": list(box) if box else None,
            "components_before": count,
            "components_kept": int(table.sum()),
            "river_pixels": int(river.sum())}


def self_check() -> None:
    """Offline checks on the three things that can silently go wrong."""
    centers, water = water_palette()
    assert centers.shape == (10, 3), centers.shape
    assert np.allclose(centers[water], [200.51, 193.65, 162.69], atol=0.01), centers[water]

    # The halo must cover every neighbourhood the 1942 path reads: a 21px
    # uniform filter (10), a 3x3 median (1) and two disk(3) closings (6).
    assert HALO >= 10 + 1 + 3 + 3, HALO
    # ... and the 1923 path's closing, which is the widest disk in SETTINGS.
    assert HALO >= max(s[4] for s in SETTINGS.values()), SETTINGS

    # Tiling covers the sheet exactly once, with no gap and no double write.
    for width, height in ((14915, 12602), (16064, 14027), (1, 1)):
        cores = [(x, y, min(CORE, width - x), min(CORE, height - y))
                 for y in range(0, height, CORE) for x in range(0, width, CORE)]
        seen = np.zeros((height, width), np.uint8)
        for x, y, w, h in cores:
            seen[y:y + h, x:x + w] += 1
        assert seen.min() == 1 and seen.max() == 1, (width, height, seen.min(), seen.max())

    # preview() sums each block into uint8 via add.reduceat, which does not
    # promote. A factor over 255 would wrap silently.
    for width in (w for _, w, _ in MAPS.values()):
        assert math.ceil(width / 2048) <= 255
    height, width, factor = 9, 7, 4
    mask = np.zeros((height, width), np.uint8)
    mask[:4, :4] = 1                       # one full block, then partials
    got = preview(mask, width, height, factor)
    assert got.shape == (3, 2), got.shape
    assert got[0, 0] == 255 and got[1, 0] == 0 and got[0, 1] == 0, got

    # tighten() on a synthetic sheet carrying one of each thing it must judge:
    # a wide solid bar (river), a thin line (fold, neat-line, road), a dithered
    # wash (the 1923 flood) and a small solid blob (residue). Only the bar is
    # allowed to survive.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        height, width = 400, 400
        synthetic = np.memmap(root / "candidate.uint8", np.uint8, "w+",
                              shape=(height, width))
        synthetic[50:110, :] = 1        # 60 px bar
        synthetic[200:203, :] = 1       # 3 px line
        synthetic[150:170, 20:40] = 1   # 20x20 blob, under the area floor
        synthetic[250:400:2, ::2] = 1   # 25% dither
        synthetic.flush()
        stats = tighten("1959", root, width, height)
        river = np.memmap(root / "river.uint8", np.uint8, "r", shape=(height, width))
        bar = int(river[50:110].sum())
        assert bar > 0.6 * 60 * width, bar
        assert int(river[:50].sum()) == 0 and int(river[110:].sum()) == 0, "kept non-river"
        assert stats["components_kept"] == 1, stats

        # The same sheet with a neat-line that excludes the bar: nothing is
        # seeded inside the frame, so nothing survives.
        stats = tighten("1959", root, width, height, (0, 200, width, height))
        river = np.memmap(root / "river.uint8", np.uint8, "r", shape=(height, width))
        assert int(river.sum()) == 0, int(river.sum())
    print("self-check ok")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", choices=tuple(MAPS) + ("all",))
    parser.add_argument("--self-check", action="store_true",
                        help="offline checks on the palette, tiling, preview and tighten")
    parser.add_argument("--tighten-only", action="store_true",
                        help="rerun the selection pass on an existing candidate mask")
    parser.add_argument("--out", type=Path, default=Path("/private/tmp/vma-river-full"))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if not args.year:
        parser.error("--year is required unless --self-check is given")
    for year in MAPS if args.year == "all" else (args.year,):
        if args.tighten_only:
            tighten_only(year, args.out)
        else:
            run(year, args.out, args.workers)


if __name__ == "__main__":
    main()
