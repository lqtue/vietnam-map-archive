"""Pixel EDA for the 1882/1898 river pair, from VMA's fixed IIIF tiles.

Run with work/ocr/.venv/bin/python. Outputs native-crop checksums, descriptive
statistics, a contact sheet and dark-ink r-b histograms. This is not a river
segmentation score: the mixed windows have no traced boundaries.
"""

from __future__ import annotations

import gc
import hashlib
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "ocr" / "scripts"))
from iiif_tiles import get_image_info, level0_tile_url  # noqa: E402

RAW_CACHE = Path("/private/tmp/vma-river-iiif-raw-cache")


def fixed_tile_crop(base: str, full_width: int, full_height: int,
                    box: list[int], scale_factor: int = 1) -> tuple[Image.Image, int]:
    """Assemble only the needed region from byte-for-byte VMA fixed tiles.

    The shared IIIF helper re-encodes JPEGs when caching. That changes near-cut
    RGB values between a fresh and cached run, so this EDA caches response bytes.
    """
    x, y, w, h = box
    tile_size = 256 * scale_factor
    tile_boxes = [(tx, ty, min(tile_size, full_width - tx), min(tile_size, full_height - ty))
                  for ty in range(y // tile_size * tile_size, y + h, tile_size)
                  for tx in range(x // tile_size * tile_size, x + w, tile_size)]
    map_id = base.rsplit("/", 1)[-1]
    cache_dir = RAW_CACHE / map_id
    cache_dir.mkdir(parents=True, exist_ok=True)

    def read(tile_box: tuple[int, int, int, int]) -> tuple[tuple[int, int, int, int], Image.Image]:
        tx, ty, tw, th = tile_box
        path = cache_dir / f"sf{scale_factor}_{tx}_{ty}_{tw}_{th}.jpg"
        if path.exists():
            data = path.read_bytes()
        else:
            url = level0_tile_url(base, tx, ty, tw, th, scale_factor)
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data = response.content
            path.write_bytes(data)
        image = Image.open(BytesIO(data)).convert("RGB")
        if image.size != (math.ceil(tw / scale_factor), math.ceil(th / scale_factor)):
            raise ValueError(f"VMA tile dimensions differ from IIIF key: {tile_box} {image.size}")
        return tile_box, image

    start_x, start_y = x // tile_size * tile_size, y // tile_size * tile_size
    canvas = Image.new("RGB", (math.ceil((x + w - start_x) / scale_factor),
                               math.ceil((y + h - start_y) / scale_factor)))
    with ThreadPoolExecutor(max_workers=8) as pool:
        for (tx, ty, tw, th), tile in pool.map(read, tile_boxes):
            canvas.paste(tile, ((tx - start_x) // scale_factor,
                                (ty - start_y) // scale_factor))
    left = x // scale_factor - start_x // scale_factor
    top = y // scale_factor - start_y // scale_factor
    right = math.ceil((x + w) / scale_factor) - start_x // scale_factor
    bottom = math.ceil((y + h) / scale_factor) - start_y // scale_factor
    crop = canvas.crop((left, top, right, bottom))
    return crop, len(tile_boxes)


def percentile(values: np.ndarray) -> list[float]:
    return [round(float(v), 4) for v in np.percentile(values, (10, 50, 90))]


def describe(image: Image.Image) -> dict:
    rgb = np.asarray(image).astype(np.float32) / 255
    v = rgb.max(axis=2)
    rb = rgb[:, :, 0] - rgb[:, :, 2]
    dark = v < 0.8  # fixed diagnostic cut, not a sheet-fitted classifier
    bright = v > 0.8
    dark_rb = rb[dark]
    grey = rgb.mean(axis=2)
    gy, gx = np.gradient(grey)
    # Global gradient tensor: a compact directionality indicator. Both water
    # ripple and land hatch can be directional, so this is not a water score.
    use = np.hypot(gx, gy) > 0.02
    jxx, jyy, jxy = (float((f[use]).mean()) if use.any() else 0.0
                      for f in (gx * gx, gy * gy, gx * gy))
    coherence = ((jxx - jyy) ** 2 + 4 * jxy * jxy) ** 0.5 / max(jxx + jyy, 1e-12)
    return {
        "size": list(image.size),
        "rgb_median": [round(float(v), 1) for v in np.median(np.asarray(image), axis=(0, 1))],
        "bright_rgb_median": [round(float(v), 1) for v in np.median(np.asarray(image)[bright], axis=0)],
        "dark_share": round(float(dark.mean()), 4),
        "dark_rb_p10_p50_p90": percentile(dark_rb),
        "dark_rb_below_007_009_011": [round(float((dark_rb < t).mean()), 4)
                                        for t in (0.07, 0.09, 0.11)],
        "directional_coherence": round(float(coherence), 3),
    }


def histogram_plot(samples: dict[str, dict[str, np.ndarray]]) -> None:
    width, height = 1080, 600
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    colors = {"water_core": "#2262aa", "dry_blue": "#c46b2e"}
    for row, year in enumerate(("1882", "1898")):
        x0, x1 = 95, 1030
        y0, y1 = 45 + row * 285, 265 + row * 285
        draw.rectangle((x0, y0, x1, y1), outline="#999999")
        for name in ("water_core", "dry_blue"):
            values = samples[year][name]
            counts, _ = np.histogram(values, bins=100, range=(-0.05, 0.2), density=False)
            counts = counts / max(counts.sum(), 1)
            # Shared y scale *within the sheet* makes relative mode heights legible.
            peak = max(np.histogram(samples[year][n], bins=100, range=(-0.05, 0.2))[0].max()
                       / max(len(samples[year][n]), 1) for n in ("water_core", "dry_blue"))
            points = [(x0 + i * (x1 - x0) / 99, y1 - float(v) / max(peak, 1e-9) * (y1 - y0) * 0.9)
                      for i, v in enumerate(counts)]
            draw.line(points, fill=colors[name], width=3)
        for t in (0.07, 0.09, 0.11):
            x = x0 + (t + 0.05) / 0.25 * (x1 - x0)
            draw.line((x, y0, x, y1), fill="#777777", width=1)
            draw.text((x + 3, y0 + 4), f"{t:.2f}", fill="#555555")
        draw.text((10, y0 + 4), year, fill="#222222")
        draw.text((x0, y1 + 8), "dark-pixel red minus blue (0–1 RGB)", fill="#222222")
        draw.text((x0 + 475, y1 + 8), "blue: water  orange: blue-grey land", fill="#222222")
    canvas.save(HERE / "dark-rb-histograms.png")


def main() -> None:
    manifest = json.loads((HERE / "windows.json").read_text())
    records = {}
    histogram_samples: dict[str, dict[str, np.ndarray]] = {}
    contact = Image.new("RGB", (2 * 480, 4 * 365), "#f7f4eb")
    draw = ImageDraw.Draw(contact)
    for column, (year, sheet) in enumerate(manifest["sheets"].items()):
        base = f'https://iiif.maparchive.vn/iiif/{sheet["map_id"]}'
        info = get_image_info(base)
        if (info["width"], info["height"]) != (sheet["width"], sheet["height"]):
            raise ValueError(f"{year} IIIF dimensions changed")
        records[year] = {"iiif": base, "source_size": [info["width"], info["height"]],
                         "windows": {}}
        histogram_samples[year] = {}
        for row, window in enumerate(sheet["windows"]):
            x, y, w, h = window["box"]
            image, tile_count = fixed_tile_crop(base, info["width"], info["height"], window["box"])
            if image.size != (w, h):
                raise RuntimeError(f"rescaled VMA crop: {year} {window['id']}")
            record = describe(image)
            record["box"] = window["box"]
            record["class"] = window["class"]
            record["raw_vma_tile_count"] = tile_count
            record["rgb_sha256"] = hashlib.sha256(np.asarray(image).tobytes()).hexdigest()
            if window["id"] in ("water_core", "dry_blue"):
                record["resized_lanczos"] = {
                    str(factor): describe(image.resize((w // factor, h // factor), Image.LANCZOS))
                    for factor in (2, 4)
                }
                record["vma_pyramid"] = {}
                for factor in (2, 4):
                    smaller, count = fixed_tile_crop(base, info["width"], info["height"],
                                                     window["box"], factor)
                    record["vma_pyramid"][str(factor)] = {
                        **describe(smaller),
                        "raw_tile_count": count,
                        "rgb_sha256": hashlib.sha256(np.asarray(smaller).tobytes()).hexdigest(),
                    }
            records[year]["windows"][window["id"]] = record
            if window["id"] in ("water_core", "dry_blue"):
                rgb = np.asarray(image).astype(np.float32) / 255
                dark = rgb.max(axis=2) < 0.8
                histogram_samples[year][window["id"]] = (rgb[:, :, 0] - rgb[:, :, 2])[dark]
            tile = image.copy()
            tile.thumbnail((460, 335))
            contact.paste(tile, (column * 480 + 10, row * 365 + 25))
            draw.text((column * 480 + 10, row * 365 + 5),
                      f"{year} {window['id']} {window['box']}", fill="#222222")
            print(year, window["id"], record, flush=True)
            del image
            gc.collect()
    (HERE / "eda.json").write_text(json.dumps(records, indent=2) + "\n")
    contact.save(HERE / "contact.jpg", quality=90)
    histogram_plot(histogram_samples)


if __name__ == "__main__":
    main()
