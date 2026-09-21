#!/usr/bin/env python3
"""Exploratory river-color masks on four pinned 1024px full-resolution crops.

Inputs are the IIIF tile assemblies listed in docs/journals/260920-colour-transfer.md.
The thresholds and seed points below are specific to these windows. This is a
visual feasibility probe, not a full-sheet detector or accuracy measurement.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.cluster.vq import kmeans2


# (seed x,y), minimum B-R, minimum B-G, maximum R-G, closing radius.
SETTINGS = {
    "1923": ((800, 850), -0.080, -0.090, 0.040, 9),
    "1959": ((500, 900), 0.150, -0.050, -0.170, 7),
    "1968": ((740, 320), 0.080, 0.000, -0.050, 7),
}
YEARS = ("1923", "1942", "1959", "1968")


def disk(radius: int) -> np.ndarray:
    yy, xx = np.ogrid[-radius : radius + 1, -radius : radius + 1]
    return xx * xx + yy * yy <= radius * radius


def detect(image: Image.Image, year: str) -> tuple[np.ndarray, np.ndarray, dict]:
    if year == "1942":
        return detect_1942(image)
    (sx, sy), min_br, min_bg, max_rg, close = SETTINGS[year]
    a = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    r, g, b = a.transpose(2, 0, 1)
    raw = (b - r > min_br) & (b - g > min_bg) & (r - g < max_rg)
    closed = ndimage.binary_closing(raw, structure=disk(close))
    labels, n = ndimage.label(closed)
    if n == 0:
        return raw, np.zeros_like(raw), {"seed_label": 0, "pixels": 0}

    # A seed can fall on printed lettering or hatching. Select the nearest
    # positive pixel within 60 px, then keep its connected component.
    yy, xx = np.ogrid[: image.height, : image.width]
    near = closed & ((xx - sx) ** 2 + (yy - sy) ** 2 <= 60**2)
    if not near.any():
        return raw, np.zeros_like(raw), {"seed_label": 0, "pixels": 0}
    ys, xs = np.where(near)
    i = np.argmin((xs - sx) ** 2 + (ys - sy) ** 2)
    label = int(labels[ys[i], xs[i]])
    selected = labels == label
    selected = ndimage.binary_fill_holes(selected)
    return raw, selected, {"seed_label": label, "pixels": int(selected.sum())}


def detect_1942(image: Image.Image) -> tuple[np.ndarray, np.ndarray, dict]:
    """Find the pale-water cluster, then fence it with the printed dark banks.

    Color alone connected the channel to roads and paper across this crop.
    The two seeds select the main river and its separate southern channel.
    """
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    flat = rgb.reshape(-1, 3)
    sample_ids = np.random.default_rng(12).choice(len(flat), 100_000, replace=False)
    centers, _ = kmeans2(flat[sample_ids], 10, minit="++", iter=35, seed=12)
    labels = ((flat[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
    labels = labels.reshape(rgb.shape[:2])
    water_cluster = int(((centers - [200, 193, 162]) ** 2).sum(axis=1).argmin())
    raw = labels == water_cluster
    candidate = ndimage.binary_closing(raw, structure=disk(3))
    dark_bank = ndimage.binary_dilation(
        rgb.mean(axis=2) / 255 < 0.55, structure=np.ones((3, 3), bool)
    )
    candidate &= ~dark_bank
    components, _ = ndimage.label(candidate)
    keep: set[int] = set()
    for sx, sy in ((300, 565), (500, 850)):
        near = candidate[sy - 40 : sy + 41, sx - 40 : sx + 41]
        ys, xs = np.where(near)
        if not len(xs):
            continue
        i = np.argmin((xs - 40) ** 2 + (ys - 40) ** 2)
        keep.add(int(components[sy - 40 + ys[i], sx - 40 + xs[i]]))
    keep.discard(0)
    selected = np.isin(components, list(keep))
    return raw, selected, {
        "water_cluster": water_cluster,
        "cluster_rgb": np.round(centers[water_cluster]).astype(int).tolist(),
        "pixels": int(selected.sum()),
    }


def clean_mask(mask: np.ndarray, year: str, raw: np.ndarray) -> np.ndarray:
    """Remove mask noise without painting over the printed riverbank.

    The 1942 pale-water color also catches stippled shore. In a 21px window,
    solid river has high color-cluster occupancy; the dotted shore does not.
    Gate on that texture before a small closing and component check.
    """
    if year == "1942":
        occupancy = ndimage.uniform_filter(raw.astype(np.float32), size=21)
        mask = mask & (occupancy > 0.35)
        radius = 3
        padded = np.pad(mask, radius, mode="edge")
        mask = ndimage.binary_closing(padded, structure=disk(radius))[
            radius:-radius, radius:-radius
        ]
        components, count = ndimage.label(mask)
        if count:
            sizes = np.bincount(components.ravel())
            keep = sizes >= 1_000
            keep[0] = False
            mask = keep[components]
    mask = ndimage.binary_fill_holes(ndimage.median_filter(mask, size=3))
    components, count = ndimage.label(mask)
    if count:
        sizes = np.bincount(components.ravel())
        keep = sizes >= 100
        keep[0] = False
        mask = keep[components]
    return mask


def save_overlay(image: Image.Image, mask: np.ndarray, path: Path) -> None:
    rgba = image.convert("RGBA")
    color = Image.new("RGBA", image.size, (255, 0, 80, 105))
    alpha = Image.fromarray(mask.astype("uint8") * 255)
    rgba.alpha_composite(Image.composite(color, Image.new("RGBA", image.size), alpha))
    rgba.convert("RGB").save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("/private/tmp"))
    parser.add_argument("--out-dir", type=Path, default=Path("/private/tmp"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for year in YEARS:
        src = args.input_dir / f"vma-river-fullres-{year}.png"
        image = Image.open(src).convert("RGB")
        raw, selected, info = detect(image, year)
        cleaned = clean_mask(selected, year, raw)
        save_overlay(image, selected, args.out_dir / f"vma-river-uncleaned-{year}.png")
        save_overlay(image, cleaned, args.out_dir / f"vma-river-detected-{year}.png")
        Image.fromarray(cleaned.astype("uint8") * 255).save(
            args.out_dir / f"vma-river-mask-{year}.png"
        )
        print(
            year, "color", int(raw.sum()), "selected", info["pixels"],
            "cleaned", int(cleaned.sum()), "changed", int((cleaned != selected).sum()),
            "of", image.width * image.height,
        )


if __name__ == "__main__":
    main()
