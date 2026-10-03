"""Diagnostic sweep of the 1882 river ink cut on a fixed VMA IIIF render.

Requires a colour-blocks --no-drop-water run with --source-width 12102.
Outputs masks for visual review; the three binary controls are not a full test set.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import Polygon


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "ocr" / "scripts"))
from colour_blocks import water_region  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--polygons", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--thresholds", type=float, nargs="+", default=[0.07, 0.09, 0.11])
    args = parser.parse_args()
    manifest = json.loads((HERE / "river-windows.json").read_text())
    points = json.loads((HERE / "hydrology-points.json").read_text())["points"]
    run = json.loads(args.polygons.read_text())
    rgb = np.asarray(Image.open(args.image).convert("RGB"))
    scale = manifest["image"]["width"] / rgb.shape[1]
    assert run["image_sha256"] == __import__("hashlib").sha256(rgb.tobytes()).hexdigest()
    feats = [{"geom": Polygon(poly["coords"]), "feature_type": poly["feature_type"]}
             for poly in run["polygons"]]
    args.out.mkdir(parents=True, exist_ok=True)
    for threshold in args.thresholds:
        mask, land, _named = water_region(feats, rgb, scale, points, line_rb=threshold)
        path = args.out / f"water-rb-{threshold:.2f}.png"
        Image.fromarray(mask.astype(np.uint8) * 255).save(path)
        checks = []
        for control in manifest["binary_controls"]:
            x, y, w, h = control["box"]
            x0, y0, x1, y1 = [round(n / scale) for n in (x, y, x + w, y + h)]
            checks.append(f'{control["id"]}={mask[y0:y1, x0:x1].mean():.3%}')
        print(f"{threshold:.3f}\t{mask.sum()} water px\t{land.sum()} land px\t"
              + "\t".join(checks), flush=True)


if __name__ == "__main__":
    main()
