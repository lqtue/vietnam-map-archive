"""Blind-safe viewing of a sheet: nothing inside a heldout window with seen:false can be drawn.

  view.py SHEET OUT.jpg [--scale 8]            whole sheet, heldout-unseen boxes painted black
  view.py SHEET OUT.jpg --box X Y W H [--zoom 1]  a crop; refuses if it touches such a box

`blind_boxes(sheet)` and `blank(img_array, sheet, scale)` are for other scripts that draw previews
or contact sheets (any raster, any scale) so they cannot leak a box either. A mask or overlay passes
through `blank` before it is saved for the eye. Setting a window's `seen` to true in windows.json
is the only way a box stops being blanked, and it is the record that someone looked.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def blind_boxes(sheet):
    return [w["box"] for w in json.loads((HERE / "windows.json").read_text())["windows"]
            if w["sheet"] == sheet and w["split"] == "heldout" and not w["seen"]]


def touches(box, sheet, pad=0):
    x, y, w, h = box
    return any(x - pad < bx + bw and bx - pad < x + w and y - pad < by + bh and by - pad < y + h
               for bx, by, bw, bh in blind_boxes(sheet))


def blank(arr, sheet, scale=1, origin=(0, 0), pad=0):
    """Paint every unseen heldout box black in `arr`, which shows source pixels origin.. at 1/scale."""
    arr = np.array(arr)
    for bx, by, bw, bh in blind_boxes(sheet):
        x0, y0 = (bx - pad - origin[0]) // scale, (by - pad - origin[1]) // scale
        x1, y1 = -(-(bx + bw + pad - origin[0]) // scale), -(-(by + bh + pad - origin[1]) // scale)
        arr[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = 0
    return arr


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    sheet, out = a[0], a[1]
    opt = lambda k, d: int(a[a.index(k) + 1]) if k in a else d
    Image.MAX_IMAGE_PIXELS = None
    pin = json.loads((HERE / "native.json").read_text())[sheet]
    im = Image.open(ROOT / pin["path"]).convert("RGB")
    if "--box" in a:
        i = a.index("--box")
        box = [int(v) for v in a[i + 1:i + 5]]
        if touches(box, sheet):
            sys.exit(f"refused: {box} overlaps an unseen heldout window")
        z = opt("--zoom", 1)
        c = im.crop((box[0], box[1], box[0] + box[2], box[1] + box[3]))
        if z != 1:
            c = c.resize((c.width * z, c.height * z), Image.NEAREST)
        c.save(out, quality=92)
    else:
        s = opt("--scale", 8)
        sm = im.reduce(s)
        Image.fromarray(blank(np.asarray(sm), sheet, s)).save(out, quality=88)
