"""Inspect a colour-pass water mask against the pinned VMA IIIF windows.

Inputs are a VMA IIIF render and a mask from colour_blocks.py
--export-water-mask. This reports coverage only, not accuracy: the positive
windows do not yet have hand-traced water boundaries.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=HERE / "river-overlay.jpg")
    args = parser.parse_args()

    manifest = json.loads((HERE / "river-windows.json").read_text())
    image = Image.open(args.image).convert("RGB")
    mask = Image.open(args.mask).convert("L")
    if image.size != mask.size:
        parser.error("image and mask sizes differ")
    scale = manifest["image"]["width"] / image.width
    if abs(manifest["image"]["height"] / image.height - scale) > 0.01:
        parser.error("render aspect ratio does not match the source scan")

    for control in manifest["binary_controls"]:
        x, y, w, h = control["box"]
        box = tuple(round(v / scale) for v in (x, y, x + w, y + h))
        predicted_water = np.asarray(mask.crop(box)).astype(bool)
        share = float(predicted_water.mean())
        print(f'CONTROL\t{control["id"]}\t{control["expected"]}\t'
              f'{predicted_water.sum()}/{predicted_water.size}\t{share:.4%}')

    tile_width = 500
    label_height = 36
    row_height = 500 + label_height
    sheet = Image.new("RGB", (tile_width * 2, row_height * len(manifest["windows"])), "white")
    draw = ImageDraw.Draw(sheet)
    for index, window in enumerate(manifest["windows"]):
        x, y, w, h = window["box"]
        box = tuple(round(v / scale) for v in (x, y, x + w, y + h))
        crop = image.crop(box)
        wet = mask.crop(box)
        coverage = float(np.asarray(wet).astype(bool).mean())
        original = crop.copy()
        original.thumbnail((tile_width, 500))
        alpha = Image.new("RGBA", crop.size, (255, 0, 0, 0))
        alpha.putalpha(wet.point(lambda value: 105 if value else 0))
        overlay = Image.alpha_composite(crop.convert("RGBA"), alpha).convert("RGB")
        overlay.thumbnail((tile_width, 500))
        row = index * row_height
        sheet.paste(original, (0, row + label_height))
        sheet.paste(overlay, (tile_width, row + label_height))
        draw.text((8, row + 10), f'{window["id"]}: {coverage:.1%} mask coverage', fill="black")
        print(f'{window["id"]}\t{window["role"]}\t{coverage:.4%}\t{box}')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out, quality=90)
    print(args.out)


if __name__ == "__main__":
    main()
