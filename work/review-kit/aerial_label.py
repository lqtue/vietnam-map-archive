"""Build the items of the `aerial-label-1950` review task: label points on a 1950 aerial as built / open / unsure.

    python3 aerial_label.py --frame Redsvn-Saigon-Aerial-1950-22.jpg --points label_points_0028.csv --out ~/vma-snapshots/aerial-label-0028
    python3 aerial_label.py ... --push        also send the task and items (needs VMA_API_URL and VMA_WORKER_KEY, or WORKER_TOKEN, in the environment)

points CSV: point_id, frame, x, y, stratum   (x, y in pixels of the ORIGINAL-orientation frame image)

Writes to --out: close_<id>.jpg and context_<id>.jpg (inspection copies), task.json, items.json (what is pushed)
and key.csv (item_id, point_id, stratum: server-side only, for scoring). Item ids are opaque hashes of the point id, so a
repeat ("p016r") cannot be told from its original in what the page receives. `stratum` is never written into an item.

Blind rule: the items carry no machine proposal and no map class. There is no proposal arm in this task (every item has
`proposal` NULL, so every verdict is arm "nocand" and blind_frac does not matter; it is sent as 0).

Rights: the photos' holder is unknown, so the crops must not be public. They are NOT uploaded to a bucket: each crop is a
base64 JPEG inside `payload.views[*].url`, which only the staff-gated /api/review/<task>/next sends. --out must be outside
the git repo. Keep it that way.

Method label_v1: close = 128 px square centred on (x, y) shown at 512 px (4x, Lanczos); context = 384 px square shown at 512.
The frame gets one contrast stretch (0.5% clipped each end) and each crop a mild unsharp mask, the same for every crop, so grey 1950 prints are
easier to read; nothing machine-made is drawn into the pixels. label_v0 (no enhancement) is `--plain`.
Parts of a crop outside the frame, and the printed data strip (bottom STRIP px of the frame), are filled mid-grey.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_record import bound as bound_hash  # noqa: E402

TASK_KEY = "aerial-label-1950"
METHOD = "label_v1"
M_PER_PX = 1.085          # ground metres per frame pixel
CLOSE_SIDE, CONTEXT_SIDE, OUT = 128, 384, 512
STRIP = 48                # printed data strip along the bottom of the frame
GREY = (128, 128, 128)
ENHANCE = True            # label_v1; set False by --plain (label_v0)
MAX_VIEW_B64 = 110_000    # two views must fit the endpoint's 262,144-byte item limit with room
QUESTION = "In March 1950, what is in the middle of the cross: a building, or open land?"
QUESTION_VI = "Tháng 3 năm 1950, tại giữa dấu thập là gì: nhà (công trình) hay đất trống?"


def item_id(point_id: str) -> str:
    """Opaque id: the page must not see that a point is a repeat."""
    return "a" + hashlib.sha1(f"{TASK_KEY}|{point_id}".encode()).hexdigest()[:9]


def read_points(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["x"], r["y"] = int(float(r["x"])), int(float(r["y"]))
    return rows


def judged(frame_name: str, x: int, y: int) -> list:
    """Exactly what is judged: where, and the crop sizes; hashed with the method version into `bound`."""
    return [frame_name, x, y, CLOSE_SIDE, CONTEXT_SIDE, OUT]


def enhance_frame(im):
    """One contrast stretch for the whole frame (0.5% clipped each end, data strip left out), so every crop is treated alike."""
    from PIL import ImageOps
    g = im.convert("L")
    w, h = g.size
    body = ImageOps.autocontrast(g.crop((0, 0, w, h - STRIP)), cutoff=0.5)
    g.paste(body, (0, 0))
    return g.convert("RGB")


def crop(im, x: int, y: int, side: int):
    from PIL import Image
    w, h = im.size
    base = im.convert("RGB").copy()
    base.paste(GREY, (0, h - STRIP, w, h))
    canvas = Image.new("RGB", (side, side), GREY)
    x0, y0 = x - side // 2, y - side // 2
    sx0, sy0, sx1, sy1 = max(x0, 0), max(y0, 0), min(x0 + side, w), min(y0 + side, h)
    if sx1 > sx0 and sy1 > sy0:
        canvas.paste(base.crop((sx0, sy0, sx1, sy1)), (sx0 - x0, sy0 - y0))
    big = canvas.resize((OUT, OUT), Image.LANCZOS)
    if ENHANCE:
        from PIL import ImageFilter, ImageOps
        big = big.filter(ImageFilter.UnsharpMask(radius=1.5, percent=40, threshold=2))
    return big, x0, y0


def jpeg_b64(img) -> tuple[bytes, str]:
    for q in (88, 82, 76, 70, 62, 55):
        b = BytesIO()
        img.save(b, "JPEG", quality=q)
        enc = base64.b64encode(b.getvalue()).decode()
        if len(enc) <= MAX_VIEW_B64:
            break
    return b.getvalue(), "data:image/jpeg;base64," + enc


def build(frame_path, points: list[dict], out) -> tuple[dict, list[dict], list[dict]]:
    from PIL import Image
    im = Image.open(frame_path)
    if ENHANCE:
        im = enhance_frame(im)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    items, key = [], []
    for p in points:
        iid = item_id(p["point_id"])
        views = {}
        for name, side in (("close", CLOSE_SIDE), ("context", CONTEXT_SIDE)):
            img, x0, y0 = crop(im, p["x"], p["y"], side)
            raw, uri = jpeg_b64(img)
            (out / f"{name}_{iid}.jpg").write_bytes(raw)
            bar_m = 100
            views[name] = {"url": uri, "x0": x0, "y0": y0, "side": side, "out": OUT, "bar_m": bar_m}
        items.append({"item_id": iid, "bound": bound_hash(judged(Path(frame_path).name, p["x"], p["y"]), METHOD),
                      "payload": {"m_per_px": M_PER_PX, "px": [p["x"], p["y"]], "views": views}})
        key.append({"item_id": iid, "point_id": p["point_id"], "stratum": p["stratum"]})
    task = {"key": TASK_KEY, "title": "Label points on a 1950 aerial", "question": QUESTION, "question_vi": QUESTION_VI,
            "method": METHOD, "seed": 20261118, "blind_frac": 0, "audience": "staff", "status": "draft"}
    (out / "task.json").write_text(json.dumps(task, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "items.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    with (out / "key.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["item_id", "point_id", "stratum"])
        w.writeheader()
        w.writerows(key)
    return task, items, key


def repo_root() -> Path:
    return Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=Path(__file__).resolve().parent, text=True).strip())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frame", required=True)
    ap.add_argument("--points", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--push", action="store_true", help="send the task and items to the app")
    ap.add_argument("--plain", action="store_true", help="no contrast stretch or sharpening (method label_v0)")
    a = ap.parse_args()
    if a.plain:
        globals().update(ENHANCE=False, METHOD="label_v0")
    out = Path(a.out).expanduser().resolve()
    root = repo_root()
    if out == root or root in out.parents:
        sys.exit(f"--out {out} is inside the git repo; the crops are third-party imagery and must stay outside it")
    task, items, _ = build(a.frame, read_points(a.points), out)
    print(f"wrote {len(items)} items to {out} (crops stay local; key.csv holds the strata)")
    if not a.push:
        return 0
    token = os.environ.get("VMA_WORKER_KEY") or os.environ.get("WORKER_TOKEN")
    url = os.environ.get("VMA_API_URL")
    if not token or not url:
        print("No VMA_WORKER_KEY (or WORKER_TOKEN) and VMA_API_URL in the environment: stopped after writing local files.")
        return 0
    import urllib.request
    from review_sync import chunks
    sent = 0
    for part in chunks(items):  # own call, not review_sync.push: that one reads .env through the worker config
        req = urllib.request.Request(f"{url.rstrip('/')}/api/pipeline/review-items", method="POST",
                                     data=json.dumps({"task": task, "items": part}, ensure_ascii=False).encode("utf-8"),
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            sent += json.load(r)["items"]
    print(f"pushed task {task['key']}: {sent} items (status draft: set it to open when ready)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
