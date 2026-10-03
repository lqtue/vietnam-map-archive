"""Contact sheet of river_pass.py's review bodies (128 in water.png), for the owner to call water or dry.

    work/ocr/.venv/bin/python work/ocr/scripts/review_sheet.py --sheet 1898

Writes work/image-processing/results/<map_id>/river/review.jpg: one row per body, the raw native crop on the left
and the same crop with the body's outline (orange) and the water edge (cyan) on the right, numbered in
run.json's review_bodies order (1-based). The owner's answer for a body is a point inside it in
river_ref/confirmed.json. A body whose padded crop touches a heldout window with seen:false is not
drawn: its number is listed on the sheet and in the printout, nothing else.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as nd

ROOT = Path(__file__).resolve().parents[3]
REF = ROOT / "work" / "image-processing" / "experiments" / "river-reference"
sys.path.insert(0, str(REF))
from view import touches  # noqa: E402

PAD, TILE_W, TILE_H = 120, 640, 420


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    a = ap.parse_args()
    Image.MAX_IMAGE_PIXELS = None
    spec = json.loads((REF / "windows.json").read_text())["sheets"][a.sheet]
    pin = json.loads((REF / "native.json").read_text())[a.sheet]
    out = ROOT / "work" / "image-processing" / "results" / spec["map_id"]
    run = json.loads((out / "river" / "run.json").read_text())
    mask = np.asarray(Image.open(out / "river" / "water.png"))
    im = Image.open(ROOT / pin["path"]).convert("RGB")
    W, H = im.size
    rows, hidden = [], []
    for n, b in enumerate(run["review_bodies"], 1):
        x, y, w, h = b["box"]
        box = [max(0, x - PAD), max(0, y - PAD), min(W, x + w + PAD), min(H, y + h + PAD)]
        if touches([box[0], box[1], box[2] - box[0], box[3] - box[1]], a.sheet):
            hidden.append(n)
            continue
        s = min(TILE_W / (box[2] - box[0]), TILE_H / (box[3] - box[1]), 1.0)
        size = (round((box[2] - box[0]) * s), round((box[3] - box[1]) * s))
        raw = im.crop(box).resize(size, Image.LANCZOS)
        m = Image.fromarray(mask[box[1]:box[3], box[0]:box[2]]).resize(size, Image.NEAREST)
        m = np.asarray(m)
        lit = np.asarray(raw).copy()
        for v, col in ((255, (0, 200, 255)), (128, (255, 110, 0))):
            b_ = m == v
            lit[b_ & ~nd.binary_erosion(b_)] = col
        tile = Image.new("RGB", (2 * TILE_W + 30, size[1] + 24), "white")
        tile.paste(raw, (0, 24))
        tile.paste(Image.fromarray(lit), (TILE_W + 30, 24))
        ImageDraw.Draw(tile).text((4, 6), f"#{n}  box {b['box']}  {b['cells']} cells", fill=(0, 0, 0))
        rows.append(tile)
    foot = 24 if hidden else 0
    sheet = Image.new("RGB", (2 * TILE_W + 30, sum(r.height + 10 for r in rows) + foot), "white")
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + 10
    if hidden:
        ImageDraw.Draw(sheet).text((4, y + 4), "not drawn (touches a heldout window): " + ", ".join(f"#{n}" for n in hidden), fill=(160, 0, 0))
    sheet.save(out / "river" / "review.jpg", quality=88)
    print(f"{len(rows)} bodies drawn, hidden: {hidden}")


if __name__ == "__main__":
    main()
