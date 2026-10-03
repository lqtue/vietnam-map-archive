#!/usr/bin/env python3
"""Build the 1882 river-window contact sheet from VMA's fixed IIIF tiles."""

import hashlib
import json
import sys
import argparse
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "work/ocr/scripts"))

from iiif_tiles import fetch_crop_level0, get_image_info, level0_tile_url  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-out", type=Path,
                        help="also assemble the 6051-pixel working image from VMA IIIF tiles")
    args = parser.parse_args()
    manifest = json.loads((HERE / "river-windows.json").read_text())
    base = manifest["iiif_service"]
    declared = manifest["image"]
    info = get_image_info(base)
    if (info["width"], info["height"]) != (declared["width"], declared["height"]):
        raise ValueError("VMA IIIF dimensions changed; source-pixel windows need review")
    tx, ty, tw, th = declared["sample_tile"]["region"]
    sample_url = level0_tile_url(base, tx, ty, tw, th, 1)
    sample = requests.get(sample_url, timeout=15)
    sample.raise_for_status()
    if hashlib.sha256(sample.content).hexdigest() != declared["sample_tile"]["sha256"]:
        raise ValueError("VMA IIIF sample tile changed; source-pixel windows need review")

    if args.render_out:
        stats = {}
        render = fetch_crop_level0(base, 0, 0, info["width"], info["height"],
                                   info["width"] // 2, stats=stats, max_workers=8)
        if stats.get("coverage") != 1.0:
            raise RuntimeError(f"incomplete VMA IIIF render: {stats}")
        args.render_out.parent.mkdir(parents=True, exist_ok=True)
        render.save(args.render_out)
        print(f"working image: {render.size}, complete VMA IIIF tiles → {args.render_out}")

    tile, header, columns = 460, 42, 2
    rows = (len(manifest["windows"]) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile, rows * (tile + header)), "#f4f0e7")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, window in enumerate(manifest["windows"]):
        x, y, width, height = window["box"]
        if x < 0 or y < 0 or x + width > info["width"] or y + height > info["height"]:
            raise ValueError(f"window outside VMA IIIF image: {window['id']}")
        stats = {}
        crop = fetch_crop_level0(base, x, y, width, height, width, stats=stats, max_workers=4)
        if stats.get("coverage") != 1.0:
            raise RuntimeError(f"incomplete VMA IIIF tiles for {window['id']}: {stats}")
        position = ((index % columns) * tile, (index // columns) * (tile + header))
        sheet.paste(crop.resize((tile, tile)), (position[0], position[1] + header))
        draw.text((position[0] + 8, position[1] + 10),
                  f"{window['id']}  {window['box']}", fill="#222222", font=font)
        print(f"{window['id']}: complete VMA IIIF crop")

    sheet.save(HERE / "river-windows.jpg", quality=85, optimize=True)


if __name__ == "__main__":
    main()
