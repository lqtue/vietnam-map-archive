"""Score river proposals against hand traces, per window, case and sheet.

    work/ocr/.venv/bin/python work/analysis/river_ref/score.py <proposal_dir> [--layer road]
    work/ocr/.venv/bin/python work/analysis/river_ref/score.py --selfcheck

Truth: traces/<sheet>-<id>.geojson, Polygon features in SOURCE pixels, property
class = "water" (holes = land islands/landings) or "ignore" (bridge, label, fold,
anything undecidable). Land is the complement of water inside the window, so a
window crossed by a boundary is clipped, not extended. A trace file counts only
when its top-level "reviewed" is true, so an empty reviewed file is a valid
all-land window and an empty unreviewed one is skipped.
Proposal: <proposal_dir>/<sheet>-<id>.png, window-sized, nonzero = water.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_erosion, distance_transform_edt

HERE = Path(__file__).resolve().parent


def rasterise(features, box, cls):
    x0, y0, w, h = box
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    for f in features:
        if f["properties"].get("class") != cls:
            continue
        for i, ring in enumerate(f["geometry"]["coordinates"]):
            d.polygon([(x - x0, y - y0) for x, y in ring], fill=0 if i else 1)  # ring 0 outer, rest holes
    return np.array(img, bool)


def boundary(m):
    # border_value=1: the window edge is a clip, not a shoreline
    return m & ~binary_erosion(m, border_value=1)


def bank_distance(a, b):
    """Symmetric mean distance (px) between the shorelines of two masks; None if either has none."""
    ba, bb = boundary(a), boundary(b)
    if not ba.any() or not bb.any():
        return None
    return float((distance_transform_edt(~bb)[ba].mean() + distance_transform_edt(~ba)[bb].mean()) / 2)


def score(truth, pred, ignore):
    keep = ~ignore
    t, p = truth & keep, pred & keep
    return {"tp": int((t & p).sum()), "fn": int((t & ~p).sum()), "fp": int((p & ~t).sum()),
            "water": int(t.sum()), "land": int((~truth & keep).sum()), "bank_px": bank_distance(t, p)}


def pct(a, b):
    return "n/a" if not b else f"{100 * a / b:.1f}%"


def main(prop_dir, layer="water"):
    spec = json.loads((HERE / "windows.json").read_text())
    rows, skipped = [], []
    for w in spec["windows"]:
        if w.get("layer", "water") != layer:
            continue
        name = f"{w['sheet']}-{w['id']}"
        trace = json.loads((HERE / "traces" / f"{name}.geojson").read_text())
        pf = Path(prop_dir) / f"{name}.png"
        if not trace.get("reviewed") or not pf.exists():
            skipped.append(name)
            continue
        feats = trace["features"]
        pred = np.array(Image.open(pf).convert("L")) > 0
        assert pred.shape == (w["box"][3], w["box"][2]), (name, pred.shape)
        truth = rasterise(feats, w["box"], "water") if layer == "water" else ~rasterise(feats, w["box"], "block")
        r = score(truth, pred, rasterise(feats, w["box"], "ignore"))
        rows.append((w, r))
    groups = defaultdict(list)
    for w, r in rows:
        groups[(w["sheet"], w["case"], w["split"] + ("*" if w["seen"] else ""))].append(r)
    print(f"[{layer}] sheet case split(*=seen)  n  IoU    missed  false  edge px")
    for key, rs in sorted(groups.items()):
        tp, fn, fp = (sum(r[k] for r in rs) for k in ("tp", "fn", "fp"))
        land = sum(r["land"] for r in rs)
        banks = [r["bank_px"] for r in rs if r["bank_px"] is not None]
        print(*key, len(rs), pct(tp, tp + fn + fp), pct(fn, tp + fn), pct(fp, land),
              f"{np.mean(banks):.1f}" if banks else "n/a", sep="  ")
    print("skipped (unreviewed or no proposal):", ", ".join(skipped) or "none")


def selfcheck():
    n = 100
    yy, xx = np.mgrid[:n, :n]
    disc = (xx - 50) ** 2 + (yy - 50) ** 2 < 30 ** 2
    shifted = (xx - 55) ** 2 + (yy - 50) ** 2 < 30 ** 2
    r = score(disc, disc, np.zeros_like(disc))
    assert r["fn"] == r["fp"] == 0 and r["bank_px"] == 0
    r = score(disc, shifted, np.zeros_like(disc))
    assert r["fn"] > 0 and r["fp"] > 0 and 3 < r["bank_px"] < 7, r      # 5 px shift ~ 5 px shoreline error
    assert score(disc, ~disc, ~disc)["fp"] == 0                            # ignored area never scored
    # a window-wide water band touches the edge: no phantom shoreline there
    band = yy > 40
    assert bank_distance(band, band) == 0 and boundary(band).sum() == n    # only the row at y=41
    # rasterise: outer ring minus hole
    f = [{"properties": {"class": "water"}, "geometry": {"coordinates": [
        [[10, 10], [40, 10], [40, 40], [10, 40]], [[20, 20], [30, 20], [30, 30], [20, 30]]]}}]
    m = rasterise(f, [0, 0, 50, 50], "water")
    assert m[15, 15] and not m[25, 25] and not m[45, 45]
    m = rasterise(f, [10, 10, 20, 20], "water")                            # window offset applied
    assert m[5, 5] and not m[12, 12]
    print("selfcheck ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selfcheck"]:
        selfcheck()
    else:
        main(a[0], a[a.index("--layer") + 1] if "--layer" in a else "water")
