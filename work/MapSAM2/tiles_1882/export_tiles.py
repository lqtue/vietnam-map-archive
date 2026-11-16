#!/usr/bin/env python
"""Training tiles for upstream MapSAM2 2D mode, from the 1882 Saigon cadastral (map 0e02b9d9).

Reads the CURRENT building geometry from Supabase (read-only: GET requests, nothing is written),
rebuilds every tile's mask, and writes upstream's layout, once per image variant:

    <out>/raw/{train,val}/<id>.png                  1024 px crop, native resolution
    <out>/raw/annotation/{train,val}/<id>.png       0 / 255 building mask
    <out>/inpainted/...                             same, with OCR text inpainted (cv2 TELEA)
    <out>/ocr/<id>.png                              text mask (oriented rectangles)
    <out>/review/<id>_overlay.png, locator.png      for the eye (locator has blind windows blanked)
    <out>/stats.json                                per tile: counts, % building, OCR boxes

Run with a Python that has numpy, pillow, shapely, requests, opencv-python-headless:

    python export_tiles.py                      # strict tiles only: none touches any window in windows.json
    python export_tiles.py --include-relaxed    # also the provisional tiles (overlap calibrate windows);
                                                # written to out_with_relaxed/, never into out/
    python export_tiles.py --require-reviewed   # exit 1 while any needs_review building touches a tile
    python export_tiles.py --self-check         # synthetic case, no network
    python export_tiles.py --update-tiles-json  # also copy today's counts into tiles.json

Held-out windows are never fetched or drawn: a tile that touches one is refused.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "work" / "core"))
REF = REPO / "work" / "image-processing" / "experiments" / "river-reference"
TILES_JSON = HERE / "tiles.json"
DEFAULT_OUT = HERE / "out"
SHAPE_PRECISION = (4420, 3800, 650, 550)  # docs/ROADMAP.md, the only parcel reference window

# ── geometry helpers (pure) ──────────────────────────────────────────────────


def boxes_hit(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def load_windows(sheet: str = "1882") -> dict:
    """{'heldout': [...], 'calibrate': [...], 'other': [...], 'blind': [...]} of [x, y, w, h]."""
    w = json.loads((REF / "windows.json").read_text())
    out = {"heldout": [], "calibrate": [], "other": [], "blind": []}
    for r in w["windows"]:
        if r["sheet"] != sheet:
            continue
        out["heldout" if r["split"] == "heldout" else "calibrate"].append(list(r["box"]))
        if r["split"] == "heldout" and not r["seen"]:
            out["blind"].append(list(r["box"]))
    out["other"].append(list(SHAPE_PRECISION))
    out["other"] += [list(v) for v in w["sheets"][sheet]["furniture"].values()]
    rw = REPO / "work/image-processing/experiments/river-1882/river-windows.json"
    if rw.exists():
        # every control box is also a windows.json window (checked 2026-11-16); listed here so a
        # control missing from windows.json would still count, as a calibrate-class box
        out["calibrate"] += [list(c["box"]) for c in json.loads(rw.read_text()).get("binary_controls", [])]
    return out


def check_tile(box, wins: dict) -> dict:
    """Which kinds of window the box touches. Held-out and other (reference, furniture) must be empty."""
    return {k: [b for b in wins[k] if boxes_hit(box, b)] for k in ("heldout", "calibrate", "other")}


def clip_ring(ring, box):
    return [(x - box[0], y - box[1]) for x, y in ring]


def building_mask(rows: list[dict], box) -> tuple[np.ndarray, dict]:
    """Union of building rows that are not rejected, clipped to the tile. 255 on 0.

    A union, so two rows tracing the same house change nothing. Holes are not supported (the table
    stores one outer ring). Returns the mask and per-status counts of rows that touch the tile.
    """
    import cv2
    from shapely.geometry import Polygon, box as sbox

    x0, y0, w, h = box
    tile = sbox(x0, y0, x0 + w, y0 + h)
    mask = np.zeros((h, w), np.uint8)
    counts = {"building": 0, "needs_review": 0, "rejected": 0}
    by_status: dict[str, int] = {}
    for r in rows:
        if r["feature_type"] != "building":
            continue
        ring = r["pixel_polygon"]
        if len(ring) < 3:
            continue
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty or not poly.intersects(tile):
            continue
        st = r["review_status"]
        by_status[st] = by_status.get(st, 0) + 1
        if st == "rejected":
            counts["rejected"] += 1
            continue
        counts["building"] += 1
        if st == "needs_review":
            counts["needs_review"] += 1
        # fill in tile coordinates; cv2 clips at the image edge
        cv2.fillPoly(mask, [np.round(np.array(clip_ring(ring, box))).astype(np.int32)], 255)
    counts["by_status"] = by_status
    return mask, counts


def ocr_rect(row: dict, label_h_guess: float = 45.0, rot_sign: float = -1.0) -> np.ndarray:
    """Oriented rectangle (4x2, source px) for one OCR row.

    `global_w/h` is the axis-aligned box of rotated text, so it is NOT the text: for 'Rue Thu duc'
    it is 789x706 at -41.5 deg, and filling it would wipe half a tile. Where the row kept
    `label_w/label_h` (text length and height) the box is exactly
    w = L|cos| + T|sin|, h = L|sin| + T|cos|. Otherwise L and T come from solving those two, or,
    near 45 deg where they are singular, from a guessed text height.

    `rotation_deg` is counter-clockwise on screen (text rising to the right is positive), the
    opposite of image coordinates, hence rot_sign = -1. Checked by eye on tile t01 (2026-11-16):
    'Rue Catinat' (+47.7) rises to the right, 'Chasseloup' (-45) falls to the right.
    """
    w, h = float(row["global_w"]), float(row["global_h"])
    cx, cy = row["global_x"] + w / 2, row["global_y"] + h / 2
    th = math.radians((row.get("rotation_deg") or 0.0) * rot_sign)
    c, s = abs(math.cos(th)), abs(math.sin(th))
    L, T = row.get("label_w"), row.get("label_h")
    if not (L and T):
        if abs(c * c - s * s) > 0.2:
            L = (w * c - h * s) / (c * c - s * s)
            T = (h * c - w * s) / (c * c - s * s)
        else:
            T = label_h_guess
            L = (w - T * s) / c if c >= s else (h - T * c) / s
        if L <= 0 or T <= 0 or L < T:  # the solve went wrong; fall back to the box itself
            L, T, th = w, h, 0.0
    L, T = float(L), float(T)
    ct, st = math.cos(th), math.sin(th)
    pts = []
    for dx, dy in ((-L / 2, -T / 2), (L / 2, -T / 2), (L / 2, T / 2), (-L / 2, T / 2)):
        pts.append((cx + dx * ct - dy * st, cy + dx * st + dy * ct))
    return np.array(pts)


MAX_TEXT_LEN, MAX_TEXT_HEIGHT = 1500.0, 250.0


def is_group_box(row: dict, rot_sign: float = -1.0) -> bool:
    """A row whose box spans a whole street or several blocks (e.g. 'Rue Chasseloup-Laubat' at
    3034 px, or a group whose label size equals its box), not one printed line. Skipped: the
    lettering sits at a few spots along it, and a band that long would repaint the street."""
    rect = ocr_rect(row, rot_sign=rot_sign)
    return math.dist(rect[0], rect[1]) > MAX_TEXT_LEN or math.dist(rect[1], rect[2]) > MAX_TEXT_HEIGHT


def ocr_mask(rows: list[dict], box, pad: int = 3, rot_sign: float = -1.0) -> tuple[np.ndarray, dict]:
    import cv2

    x0, y0, w, h = box
    mask = np.zeros((h, w), np.uint8)
    n = {"all": 0, "kept": 0, "rejected": 0, "skipped_group": 0}
    for r in rows:
        rect = ocr_rect(r, rot_sign=rot_sign)
        if rect[:, 0].max() < x0 or rect[:, 0].min() > x0 + w or rect[:, 1].max() < y0 or rect[:, 1].min() > y0 + h:
            continue
        if is_group_box(r, rot_sign):
            n["skipped_group"] += 1
            continue
        n["all"] += 1
        n["rejected" if r.get("review_status") == "rejected" else "kept"] += 1
        pts = np.round(rect - np.array([x0, y0])).astype(np.int32)
        cv2.fillPoly(mask, [pts], 255)
    if pad:
        mask = cv2.dilate(mask, np.ones((2 * pad + 1, 2 * pad + 1), np.uint8))
    return mask, n


def inpaint(img_rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    import cv2

    bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    out = cv2.inpaint(bgr, mask, 5, cv2.INPAINT_TELEA)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)


def overlay(img_rgb: np.ndarray, rows: list[dict], ocr_rows: list[dict], box, title: str) -> Image.Image:
    im = Image.fromarray(img_rgb).convert("RGB")
    d = ImageDraw.Draw(im)
    x0, y0 = box[0], box[1]
    colour = {"needs_review": (255, 0, 0), "rejected": (0, 90, 255)}
    for r in rows:
        if r["feature_type"] != "building":
            continue
        pts = [(x - x0, y - y0) for x, y in r["pixel_polygon"]]
        if max(p[0] for p in pts) < 0 or min(p[0] for p in pts) > box[2] or max(p[1] for p in pts) < 0 or min(p[1] for p in pts) > box[3]:
            continue
        d.polygon(pts, outline=colour.get(r["review_status"], (0, 170, 0)), width=2)
    for r in ocr_rows:
        if is_group_box(r):
            continue
        rect = ocr_rect(r)
        pts = [(x - x0, y - y0) for x, y in rect]
        d.polygon(pts, outline=(150, 150, 150) if r.get("review_status") == "rejected" else (255, 200, 0), width=1)
    d.rectangle([0, 0, 520, 16], fill=(255, 255, 255))
    d.text((3, 2), title + "  red=needs_review green=approved/submitted blue=rejected yellow=OCR", fill=(0, 0, 0))
    return im


def write_tile(root: Path, split: str, tid: str, img: np.ndarray, mask: np.ndarray) -> None:
    (root / split).mkdir(parents=True, exist_ok=True)
    (root / "annotation" / split).mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(root / split / f"{tid}.png")
    Image.fromarray(mask).save(root / "annotation" / split / f"{tid}.png")


# ── database and image access (read-only) ────────────────────────────────────


def _get_all(path: str) -> list[dict]:
    import requests
    from vma_core import db

    url, key = db._load_config()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    out: list[dict] = []
    while True:
        r = requests.get(f"{url}/rest/v1/{path}&limit=1000&offset={len(out)}", headers=headers, timeout=60)
        r.raise_for_status()
        page = r.json()
        out += page
        if len(page) < 1000:
            return out


def fetch_footprints(map_id: str) -> list[dict]:
    return _get_all(
        f"footprints?map_id=eq.{map_id}&select=id,pixel_polygon,feature_type,review_status,source,run_id,user_id&order=id"
    )


def fetch_ocr(map_id: str, run: str) -> list[dict]:
    return _get_all(
        f"ocr_labels?map_id=eq.{map_id}&run_id=eq.{run}"
        "&select=id,text,category,review_status,global_x,global_y,global_w,global_h,label_w,label_h,rotation_deg&order=id"
    )


def fetch_tile_image(map_id: str, box) -> np.ndarray:
    from vma_core import iiif

    base = iiif.get_iiif_base_from_supabase(map_id)
    if not base:
        raise SystemExit("no iiif base for the map")
    im = iiif.fetch_crop(base, box[0], box[1], box[2], box[3], size=box[2])
    if im.size != (box[2], box[3]):
        raise SystemExit(f"crop came back {im.size}, expected {(box[2], box[3])}")
    arr = np.array(im.convert("RGB"))
    assert_no_holes(arr, box)
    return arr


def assert_no_holes(arr: np.ndarray, box, block: int = 256) -> None:
    """fetch_crop may return a level-0 assembly with up to 10% of its tiles missing (white) and does
    not cache it, so a later run could differ. Scan paper is cream, never pure white: fail on any
    256 px block that is."""
    h, w = arr.shape[:2]
    for y in range(0, h, block):
        for x in range(0, w, block):
            if (arr[y:y + block, x:x + block] >= 254).all():
                raise SystemExit(f"crop {list(box)} has an all-white {block} px block at ({x},{y}): missing tile, run again")


# ── main ─────────────────────────────────────────────────────────────────────


def locator(cfg, wins, tiles, out: Path, scale: int = 8) -> None:
    from vma_core import iiif

    sys.path.insert(0, str(REF))
    import view  # blind-safe: blank() paints every unseen held-out box black

    w, h = cfg["image"]
    base = iiif.get_iiif_base_from_supabase(cfg["map_id"])
    im = iiif.fetch_crop(base, 0, 0, w, h, size=w // scale, fit=True)
    arr = view.blank(np.array(im), "1882", scale)
    pil = Image.fromarray(arr)
    d = ImageDraw.Draw(pil)
    for t in tiles:
        x, y, bw, bh = t["box"]
        d.rectangle([x / scale, y / scale, (x + bw) / scale, (y + bh) / scale], outline=(255, 0, 255) if not t["relaxed"] else (255, 140, 0), width=3)
        d.text((x / scale + 4, y / scale + 4), t["id"], fill=(255, 0, 255))
    for r in cfg["reserved_test"]:
        x, y, bw, bh = r["box"]
        d.rectangle([x / scale, y / scale, (x + bw) / scale, (y + bh) / scale], outline=(0, 0, 0), width=2)
        d.text((x / scale + 4, y / scale + 4), r["id"] + " (test, do not touch)", fill=(0, 0, 0))
    (out / "review").mkdir(parents=True, exist_ok=True)
    pil.save(out / "review" / "locator.png")


def run(args) -> int:
    cfg = json.loads(TILES_JSON.read_text())
    wins = load_windows()
    tiles = [t for t in cfg["tiles"] if args.include_relaxed or not t["relaxed"]]
    if args.only:
        tiles = [t for t in tiles if t["id"] in args.only]
    # rules: never a held-out, reference or furniture window; calibrate only when marked relaxed
    for t in tiles:
        hit = check_tile(t["box"], wins)
        bad = hit["heldout"] + hit["other"] + ([] if t["relaxed"] else hit["calibrate"])
        if bad:
            raise SystemExit(f"{t['id']} {t['box']} overlaps a window it must not touch: {bad}")
        if t["relaxed"] != bool(hit["calibrate"]):
            raise SystemExit(f"{t['id']}: relaxed={t['relaxed']} but calibrate overlaps={hit['calibrate']}")
    for r in cfg["reserved_test"]:
        hit = check_tile(r["box"], wins)
        if any(hit.values()):
            raise SystemExit(f"reserved {r['id']} overlaps a window: {hit}")
        for t in tiles:
            if boxes_hit(r["box"], t["box"]):
                raise SystemExit(f"reserved {r['id']} overlaps tile {t['id']}")
    out = Path(args.out) if args.out else (HERE / "out_with_relaxed" if args.include_relaxed else DEFAULT_OUT)
    rows = fetch_footprints(cfg["map_id"])
    ocr_rows = fetch_ocr(cfg["map_id"], cfg["ocr_run"])
    print(f"{len(rows)} footprint rows, {len(ocr_rows)} OCR rows ({cfg['ocr_run']})")
    # reserved areas must hold no volunteer trace (the plan's rule); report, do not fail
    from shapely.geometry import Polygon, box as sbox

    for r in cfg["reserved_test"]:
        b = r["box"]
        vol = [f["id"] for f in rows if f["source"] == "volunteer" and Polygon(f["pixel_polygon"]).intersects(sbox(b[0], b[1], b[0] + b[2], b[1] + b[3]))]
        r["volunteer_traces"] = len(vol)
        print(f"reserved {r['id']}: volunteer traces inside = {len(vol)}")
    stats = {}
    todo = 0
    for t in tiles:
        box = t["box"]
        img = fetch_tile_image(cfg["map_id"], box)
        mask, c = building_mask(rows, box)
        om, on = ocr_mask(ocr_rows, box)
        clean = inpaint(img, om)
        for variant, im in (("raw", img), ("inpainted", clean)):
            write_tile(out / variant, t["split"], t["id"], im, mask)
        for sub in ("ocr", "review"):
            (out / sub).mkdir(parents=True, exist_ok=True)
        Image.fromarray(om).save(out / "ocr" / f"{t['id']}.png")
        overlay(img, rows, ocr_rows, box, t["id"]).save(out / "review" / f"{t['id']}_overlay.png")
        names = sorted(
            {r["text"] for r in ocr_rows if r.get("review_status") != "rejected" and r["category"] in ("street", "institution", "place")
             and box[0] <= r["global_x"] + r["global_w"] / 2 < box[0] + box[2] and box[1] <= r["global_y"] + r["global_h"] / 2 < box[1] + box[3]}
        )
        stats[t["id"]] = {
            "box": box, "split": t["split"], "relaxed": t["relaxed"],
            "buildings": c["building"], "needs_review": c["needs_review"], "rejected": c["rejected"],
            "by_status": c["by_status"],
            "pct_building": round(100 * float((mask > 0).mean()), 2),
            "ocr_boxes": on["all"], "ocr_group_boxes_skipped": on["skipped_group"], "ocr_boxes_kept": on["kept"], "ocr_boxes_rejected": on["rejected"],
            "ocr_names": names[:6],
        }
        todo += c["needs_review"]
        print(t["id"], box, t["split"], {k: stats[t["id"]][k] for k in ("buildings", "needs_review", "rejected", "pct_building", "ocr_boxes")})
    locator(cfg, wins, tiles, out)
    (out / "stats.json").write_text(json.dumps({"reserved_test": cfg["reserved_test"], "tiles": stats}, indent=1))
    if args.update_tiles_json:
        for t in cfg["tiles"]:
            if t["id"] in stats:
                s = stats[t["id"]]
                t["stats"] = {k: s[k] for k in ("buildings", "needs_review", "rejected", "pct_building", "ocr_boxes")}
        TILES_JSON.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    print(f"needs_review buildings still touching these tiles: {todo}")
    if args.require_reviewed and todo:
        print("NOT READY: approve or reject every needs_review building first")
        return 1
    return 0


# ── self-check ───────────────────────────────────────────────────────────────


def self_check() -> None:
    import cv2

    box = (1000, 2000, 1024, 1024)
    sq = lambda x, y, s: [[x, y], [x + s, y], [x + s, y + s], [x, y + s]]
    rows = [
        {"feature_type": "building", "review_status": "approved", "pixel_polygon": sq(1100, 2100, 50)},       # A: kept
        {"feature_type": "building", "review_status": "needs_review", "pixel_polygon": sq(1100, 2100, 50)},   # duplicate of A
        {"feature_type": "building", "review_status": "rejected", "pixel_polygon": sq(1300, 2300, 60)},       # rejected: absent
        {"feature_type": "building", "review_status": "needs_review", "pixel_polygon": sq(980, 2900, 60)},    # crosses the left edge
        {"feature_type": "land_plot", "review_status": "approved", "pixel_polygon": sq(1500, 2500, 100)},     # wrong class
        {"feature_type": "building", "review_status": "approved", "pixel_polygon": sq(3000, 3000, 40)},       # outside the tile
    ]
    mask, c = building_mask(rows, box)
    assert c["building"] == 3 and c["needs_review"] == 2 and c["rejected"] == 1, c
    assert mask[100:150, 100:150].min() == 255                       # A drawn once
    assert (mask[300:360, 300:360] == 0).all()                        # rejected row leaves no pixels
    assert (mask[900:960, 0:40] == 255).all() and (mask[900:960, 42:60] == 0).all()  # clipped at the edge (fillPoly includes the boundary pixel)
    assert abs(int((mask > 0).sum()) - (51 * 51 + 41 * 61)) <= 2, int((mask > 0).sum())  # union, land_plot excluded; boundary pixel included
    # oriented text box: a 400 x 40 label at 45 deg must stay thin, not become its 296 x 296 bounding box
    L, T, th = 400.0, 40.0, 45.0
    cs = math.cos(math.radians(th))
    bw = L * cs + T * cs
    row = {"global_x": 0, "global_y": 0, "global_w": bw, "global_h": bw, "label_w": L, "label_h": T, "rotation_deg": th}
    rect = ocr_rect(row)
    assert abs(math.dist(rect[0], rect[1]) - L) < 1e-6 and abs(math.dist(rect[1], rect[2]) - T) < 1e-6
    area = cv2.contourArea(rect.astype(np.float32))
    assert abs(area - L * T) < 1, area
    # sign: +45 rises to the right in the picture, so the long edge goes up as x grows
    assert rect[1][0] > rect[0][0] and rect[1][1] < rect[0][1], rect
    assert is_group_box({"global_x": 0, "global_y": 0, "global_w": 2298, "global_h": 2079, "label_w": 3034, "label_h": 66, "rotation_deg": -42})
    assert not is_group_box(row)
    row2 = {**row, "label_w": None, "label_h": None, "rotation_deg": 30.0, "global_w": 400 * math.cos(math.radians(30)) + 40 * math.sin(math.radians(30)),
            "global_h": 400 * math.sin(math.radians(30)) + 40 * math.cos(math.radians(30))}
    r2 = ocr_rect(row2)
    assert abs(math.dist(r2[0], r2[1]) - 400) < 1e-3 and abs(math.dist(r2[1], r2[2]) - 40) < 1e-3
    # inpainting removes a painted word and leaves the rest
    img = np.full((1024, 1024, 3), (235, 220, 190), np.uint8)
    cv2.rectangle(img, (100, 100), (160, 110), (0, 0, 0), -1)
    om = np.zeros((1024, 1024), np.uint8)
    om[95:115, 95:165] = 255
    out = inpaint(img, om)
    assert out[100:110, 100:160].min() > 150 and (out[500:600, 500:600] == img[500:600, 500:600]).all()
    holes = np.full((1024, 1024, 3), (235, 220, 190), np.uint8)
    assert_no_holes(holes, (0, 0, 1024, 1024))
    holes[256:512, 512:768] = 255
    try:
        assert_no_holes(holes, (0, 0, 1024, 1024))
        raise AssertionError("white block not caught")
    except SystemExit:
        pass
    # windows: a tile on the heldout box is refused, one beside it is not
    wins = load_windows()
    assert check_tile((3500, 2600, 1024, 1024), wins)["heldout"]                      # creek_nw
    assert not any(check_tile((5000, 2000, 1024, 1024), wins).values())
    # layout
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "raw"
        write_tile(root, "train", "t00", img, mask)
        write_tile(root, "val", "t01", img, mask)
        for p in ("train/t00.png", "annotation/train/t00.png", "val/t01.png", "annotation/val/t01.png"):
            assert (root / p).exists(), p
        m = np.array(Image.open(root / "annotation/train/t00.png"))
        assert m.shape == (1024, 1024) and set(np.unique(m)) <= {0, 255}
    print("self-check ok")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None, help="default: out/, or out_with_relaxed/ with --include-relaxed")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--include-relaxed", action="store_true", help="also export tiles marked relaxed (they overlap calibrate windows)")
    ap.add_argument("--require-reviewed", action="store_true")
    ap.add_argument("--update-tiles-json", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
