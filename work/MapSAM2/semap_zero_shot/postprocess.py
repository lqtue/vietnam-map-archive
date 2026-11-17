#!/usr/bin/env python
"""Clean-up of a Semap class map into block and lot polygons (1882 Saigon cadastral).

Input: a class map from the Semap model (uint8 PNG: 0 background, 1 contours, 2 built, 3 non-built,
4 water, 5 road_network) or an averaged probability map (`<name>_probs.npz`, float16 (6, H, W), key
`probs` or the first array; argmax is the class, the max probability is the confidence).

Output, in FULL-SHEET pixel coordinates (tile origin added, y down, origin upper left), one ring per
polygon, no holes (scripts/import-seg-geojson.mjs stores only an exterior ring):

    blocks_<tile>.geojson   kind 'block'
    lots_<tile>.geojson     kind 'lot', built 'built' | 'non-built', confidence = majority vote share
    <tile>_post_overlay.jpg source image, block outlines in blue, lots filled red (built) / yellow (non-built)

Steps (parameters are module constants, all in pixels of the 1882 sheet at full resolution):
  1. block = not road (5) and not water (4); closing with an 11 px disc fills gaps under 12 px (the
     narrowest street is 12 px, so it survives); opening with 5 px removes specks; components under
     MIN_BLOCK_PX2 are dropped; holes are filled (the importer takes no interior ring);
     outline traced and simplified with Douglas-Peucker at SIMPLIFY_PX. No straightening is done.
  2. lot lines = the model's contours class (1) plus thin dark ink found in the source image
     (blur, then black-hat on grey: the blur removes the hatching); strokes shorter than MIN_LINE_PX
     (letters, hatch bits) are dropped; lines
     are thickened by 1 px to close small dashes. Inside each block the pixels between lines are
     labelled by connected components. Components under MIN_LOT_PX2 (buildings drawn inside a lot,
     letters, slivers) and the line pixels themselves are absorbed by the nearest lot of the same
     block, so lots tile the block. A lot takes the majority of built (2) / non-built (3) pixels;
     the vote share is its confidence. A lot with no built or non-built pixel is dropped.

Run with a Python that has numpy, pillow, scipy, shapely, opencv-python-headless:

    python postprocess.py <cls.png | probs.npz> --image <source.png> --out <dir> [--tile t01] [--origin X Y]
    python postprocess.py --self-check                 # synthetic case, no network, no data files

The tile id is read from the file name (`1882_t01_s1_cls.png`) and its origin from tiles.json.
A tile that touches a reserved test window (R1, R2) is refused. Nothing is written to a database.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent
TILES_JSON = HERE.parent / "tiles_1882" / "tiles.json"

BG, CONTOUR, BUILT, NONBUILT, WATER, ROAD = range(6)

CLOSE_PX = 11          # closing disc: fills gaps under 12 px; a 12 px street is kept
OPEN_PX = 5            # opening disc: removes specks and one-pixel bridges between blocks
MIN_BLOCK_PX2 = 4000   # smallest block on t01/t06 is about 100 x 100 = 10,000; 4,000 keeps odd
                       # corner blocks (about 60 x 70) and drops fragments of road-class noise
MIN_LOT_PX2 = 2500     # about 50 x 50; lots on these tiles are 60-150 px across, the largest
                       # building drawn inside a lot is about 60 x 40 = 2,400
MIN_LINE_PX = 40       # an ink stroke must span this far (bbox diagonal); letters are about 20 px
INK_BLUR = 2.0         # Gaussian sigma before the black-hat: the diagonal hatching (period about
                       # 4 px) averages out to a flat tone, a drawn lot line stays a dark ridge
INK_KERNEL = 11        # black-hat structuring element: finds dark ridges up to 10 px wide
INK_THRESH = 28        # black-hat response (0-255): lines give 50-80, residual hatching up to about 25
LINE_GROW_PX = 3       # dilation (square) of the line mask: closes 1-2 px dashes
SIMPLIFY_PX = 1.5      # Douglas-Peucker tolerance for blocks and lots
FEATURE_TYPE = "land_plot"  # footprint type for both blocks and lots; `kind` tells them apart


# ── loading ─────────────────────────────────────────────────────────────────


def load_classes(path: Path):
    """Return (class map uint8 (H, W), confidence float32 (H, W) or None)."""
    if path.suffix == ".npz":
        z = np.load(path)
        key = "probs" if "probs" in z.files else z.files[0]
        p = z[key].astype(np.float32)
        return p.argmax(0).astype(np.uint8), p.max(0)
    cls = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if cls is None:
        raise SystemExit(f"cannot read {path}")
    if cls.ndim == 3:
        cls = cls[..., 0]
    return cls.astype(np.uint8), None


def disc(d: int):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d, d))


# ── blocks ──────────────────────────────────────────────────────────────────


def block_mask(cls: np.ndarray) -> np.ndarray:
    """uint8 0/1: street blocks, as one label image (1..n) is made by the caller."""
    m = ((cls != ROAD) & (cls != WATER)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, disc(CLOSE_PX))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, disc(OPEN_PX))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= MIN_BLOCK_PX2
    m = keep[lab].astype(np.uint8)
    # fill holes (road-class text inside a block, an enclosed court): the importer stores one ring
    return ndi.binary_fill_holes(m).astype(np.uint8)


def largest_ring(mask: np.ndarray):
    """Outer ring of the largest 8-connected part of a 0/1 mask, simplified, as (N, 2) float or None."""
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        return None
    c = max(cs, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, SIMPLIFY_PX, True)[:, 0, :].astype(float)
    return c if len(c) >= 3 else None


# ── lots ────────────────────────────────────────────────────────────────────


def ink_lines(gray: np.ndarray) -> np.ndarray:
    """Thin dark strokes in the source image, as 0/1; short strokes (letters, hatch bits) removed."""
    blur = cv2.GaussianBlur(gray, (0, 0), INK_BLUR)
    bh = cv2.morphologyEx(blur, cv2.MORPH_BLACKHAT, disc(INK_KERNEL))
    m = (bh >= INK_THRESH).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    diag = np.hypot(stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT])
    keep = diag >= MIN_LINE_PX
    keep[0] = False
    return keep[lab].astype(np.uint8)


def make_lots(cls: np.ndarray, blocks: np.ndarray, gray: np.ndarray | None):
    """Label image of lots (0 outside blocks, 1..n inside), tiling every block."""
    lines = (cls == CONTOUR).astype(np.uint8)
    if gray is not None:
        lines |= ink_lines(gray)
    lines = cv2.dilate(lines, np.ones((LINE_GROW_PX, LINE_GROW_PX), np.uint8))
    free = (blocks > 0) & (lines == 0)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(free.astype(np.uint8), connectivity=4)
    big = np.zeros(n, bool)
    big[1:] = stats[1:, cv2.CC_STAT_AREA] >= MIN_LOT_PX2
    seeds = np.where(big[lab], lab, 0)
    bn, blab = cv2.connectedComponents(blocks, connectivity=4)
    out = np.zeros(cls.shape, np.int32)
    for b in range(1, bn):
        ys, xs = np.nonzero(blab == b)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        inb = (blab[y0:y1, x0:x1] == b)
        s = np.where(inb, seeds[y0:y1, x0:x1], 0)
        if not s.any():
            s = inb.astype(np.int32) * (int(seeds.max()) + b + 1)  # no lot line: the block is one lot
        idx = ndi.distance_transform_edt(s == 0, return_distances=False, return_indices=True)
        filled = s[idx[0], idx[1]]
        out[y0:y1, x0:x1][inb] = filled[inb]
    return out


def lot_features(cls, conf, lots, origin):
    """Majority built / non-built vote per lot -> GeoJSON features. Drops lots with no vote."""
    feats = []
    for lab in np.unique(lots):
        if lab == 0:
            continue
        m = lots == lab
        nb, nn = int((cls[m] == BUILT).sum()), int((cls[m] == NONBUILT).sum())
        if nb + nn == 0:
            continue
        ring = largest_ring(m)
        if ring is None or abs(cv2.contourArea(ring.astype(np.float32))) < MIN_LOT_PX2 / 2:
            continue
        props = {
            "feature_type": FEATURE_TYPE, "kind": "lot",
            "built": "built" if nb >= nn else "non-built",
            "confidence": round(max(nb, nn) / (nb + nn), 3),
            "area_px": int(m.sum()),
        }
        if conf is not None:
            props["mean_prob"] = round(float(conf[m].mean()), 3)
        feats.append(feature(ring, origin, props))
    return feats


def block_features(cls, conf, blocks, origin):
    feats = []
    n, lab = cv2.connectedComponents(blocks, connectivity=4)
    for b in range(1, n):
        m = lab == b
        ring = largest_ring(m)
        if ring is None:
            continue
        props = {"feature_type": FEATURE_TYPE, "kind": "block", "area_px": int(m.sum()),
                 "confidence": round(float(conf[m].mean()), 3) if conf is not None else None}
        feats.append(feature(ring, origin, props))
    return feats


def feature(ring, origin, props):
    pts = [[round(float(x) + origin[0], 1), round(float(y) + origin[1], 1)] for x, y in ring]
    pts.append(pts[0])
    return {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [pts]}}


def collection(feats, tile):
    for f in feats:
        f["properties"]["source_tile"] = tile
    return {"type": "FeatureCollection", "features": feats}


def process(cls, conf, gray, origin, tile):
    blocks = block_mask(cls)
    lots = make_lots(cls, blocks, gray)
    bf = block_features(cls, conf, blocks, origin)
    lf = lot_features(cls, conf, lots, origin)
    return blocks, lots, collection(bf, tile), collection(lf, tile)


# ── overlay ─────────────────────────────────────────────────────────────────


def overlay(img_bgr, lots_fc, blocks_fc, origin):
    base = img_bgr.copy()
    fill = base.copy()
    to_px = lambda f: (np.array(f["geometry"]["coordinates"][0]) - origin).round().astype(np.int32)
    for f in lots_fc["features"]:
        col = (60, 60, 230) if f["properties"]["built"] == "built" else (40, 210, 240)  # BGR
        cv2.fillPoly(fill, [to_px(f)], col)
    out = cv2.addWeighted(fill, 0.4, base, 0.6, 0)
    for f in lots_fc["features"]:
        cv2.polylines(out, [to_px(f)], True, (30, 90, 30), 1, cv2.LINE_AA)
    for f in blocks_fc["features"]:
        cv2.polylines(out, [to_px(f)], True, (220, 60, 0), 2, cv2.LINE_AA)
    return out


# ── tiles ───────────────────────────────────────────────────────────────────


def hit(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def tile_origin(tile: str):
    """Origin of a tile id in full-sheet pixels, from tiles.json; refuses a reserved test window."""
    t = json.loads(TILES_JSON.read_text())
    box = next((x["box"] for x in t["tiles"] if x["id"] == tile), None)
    if box is None:
        raise SystemExit(f"tile {tile} not in {TILES_JSON}; pass --origin X Y")
    check_reserved(box, t)
    return (box[0], box[1])


def check_reserved(box, t=None):
    t = t or json.loads(TILES_JSON.read_text())
    for r in t["reserved_test"]:
        if hit(box, r["box"]):
            raise SystemExit(f"refused: the tile touches reserved test window {r['id']}")


def default_image(src: Path):
    stem = re.sub(r"_(cls|probs)$", "", src.stem)
    for d in (src.parent.parent / "in", src.parent):
        for ext in (".png", ".jpg"):
            p = d / (stem + ext)
            if p.exists():
                return p
    return None


def run(src: Path, image: Path | None, out: Path, tile: str | None, origin):
    m = re.search(r"(t\d\d)", src.name)
    tile = tile or (m.group(1) if m else src.stem)
    if origin is None:
        origin = tile_origin(tile)
    else:
        check_reserved([origin[0], origin[1], 1024, 1024])
    cls, conf = load_classes(src)
    image = image or default_image(src)
    img = cv2.imread(str(image), cv2.IMREAD_COLOR) if image else None
    if img is not None and img.shape[:2] != cls.shape:
        raise SystemExit(f"image {img.shape[:2]} and class map {cls.shape} differ in size")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img is not None else None
    if gray is None:
        print("no source image: lot lines come from the model's contours class only")
    _, _, bfc, lfc = process(cls, conf, gray, origin, tile)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"blocks_{tile}.geojson").write_text(json.dumps(bfc))
    (out / f"lots_{tile}.geojson").write_text(json.dumps(lfc))
    if img is not None:
        cv2.imwrite(str(out / f"{tile}_post_overlay.jpg"), overlay(img, lfc, bfc, origin),
                    [cv2.IMWRITE_JPEG_QUALITY, 88])
    nb = sum(f["properties"]["built"] == "built" for f in lfc["features"])
    print(f"{tile}: {len(bfc['features'])} blocks, {len(lfc['features'])} lots "
          f"({nb} built, {len(lfc['features']) - nb} non-built) -> {out}")


# ── self-check ──────────────────────────────────────────────────────────────


def self_check():
    """Two blocks split by a road. Left: model contour line -> a built and a non-built lot. Right:
    a lot line that exists only as ink in the image -> two lots, the lower one 70 % built."""
    H = W = 220
    cls = np.full((H, W), ROAD, np.uint8)
    cls[15:205, 15:105] = NONBUILT                 # left block, 90 x 190
    cls[15:105, 15:105] = BUILT                    # upper left lot built
    cls[103:106, 15:105] = CONTOUR                 # drawn lot line, 3 px
    cls[15:205, 125:205] = BUILT                   # right block, 80 x 190 (street between: 20 px)
    cls[110:205, 125:205][np.random.RandomState(0).rand(95, 80) < 0.3] = NONBUILT  # ~30 % noise below
    cls[50:54, 150:154] = ROAD                     # road-class speck inside a block: must be filled
    cls[3:11, 3:11] = NONBUILT                     # tiny island in the road: under MIN_BLOCK_PX2
    img = np.full((H, W), 235, np.uint8)
    img[107:109, 125:205] = 20                     # ink line, 2 px, 80 long
    assert (cls[107:109, 125:205] != ROAD).all()
    blocks, lots, bfc, lfc = process(cls, None, img, (1000, 2000), "tsyn")
    nb, nl = len(bfc["features"]), len(lfc["features"])
    assert nb == 2, f"expected 2 blocks, got {nb}"
    assert nl == 4, f"expected 4 lots, got {nl}"
    assert blocks[52, 152] == 1, "speck inside a block was not filled"
    props = sorted((f["properties"] for f in lfc["features"]), key=lambda p: p["area_px"])
    built = [p["built"] for p in props]
    assert built.count("built") == 3 and built.count("non-built") == 1, built
    nonb = next(p for p in props if p["built"] == "non-built")
    assert nonb["confidence"] > 0.95, nonb       # lower-left lot is pure non-built
    lower_right = [p for p in props if p["built"] == "built" and p["confidence"] < 0.9]
    assert len(lower_right) == 1 and 0.6 < lower_right[0]["confidence"] < 0.8, props
    f0 = bfc["features"][0]
    assert len(f0["geometry"]["coordinates"]) == 1, "block has an interior ring"
    xs = [p[0] for f in bfc["features"] for p in f["geometry"]["coordinates"][0]]
    assert min(xs) >= 1000 and max(xs) <= 1220, "origin not added"
    for f in lfc["features"]:
        assert f["properties"]["source_tile"] == "tsyn" and f["properties"]["kind"] == "lot"
    # a tile on a reserved test window is refused
    try:
        check_reserved([4760, 4790, 1024, 1024])
        raise AssertionError("reserved window not refused")
    except SystemExit:
        pass
    # end-to-end: a class PNG and an image on disk give the same counts and an overlay
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        cv2.imwrite(str(d / "x_t01_cls.png"), cls)
        cv2.imwrite(str(d / "x_t01.png"), cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
        run(d / "x_t01_cls.png", d / "x_t01.png", d / "o", "t01", (0, 0))
        assert (d / "o" / "blocks_t01.geojson").exists() and (d / "o" / "t01_post_overlay.jpg").exists()
        p = np.zeros((6, H, W), np.float16)
        p[cls, np.arange(H)[:, None], np.arange(W)[None, :]] = 1.0
        np.savez(d / "x_t01_probs.npz", probs=p)
        run(d / "x_t01_probs.npz", d / "x_t01.png", d / "o2", "t01", (0, 0))
        n2 = len(json.loads((d / "o2" / "lots_t01.geojson").read_text())["features"])
        assert n2 == 4, n2
    print("self-check ok: 2 blocks, 4 lots (3 built, 1 non-built), speck filled, island dropped, "
          "origin added, reserved window refused, probs input agrees")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", nargs="?", type=Path, help="class PNG or probs .npz")
    ap.add_argument("--image", type=Path, help="source image (default: guessed beside the input)")
    ap.add_argument("--out", type=Path, default=Path("post"))
    ap.add_argument("--tile", help="tile id (default: from the file name)")
    ap.add_argument("--origin", nargs=2, type=int, metavar=("X", "Y"),
                    help="tile origin in full-sheet pixels (default: tiles.json)")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        self_check()
        return
    if not a.src:
        ap.error("give a class PNG or probs .npz, or --self-check")
    run(a.src, a.image, a.out, a.tile, tuple(a.origin) if a.origin else None)


if __name__ == "__main__":
    sys.exit(main())
