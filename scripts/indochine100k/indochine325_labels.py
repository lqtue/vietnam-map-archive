#!/usr/bin/env python3
"""Series 325: read the printed grade labels (114G,40 / 19G,40) next to the graticule lines.

Compares a local reader (Tesseract, digit whitelist) with Gemini (thinking off) on the same crops.
The truth is the grade the catalogue box predicts for each line, so this measures the reader, not the
placement. Needs probe output from indochine325_graticule.py in work/indochine-100k/325-graticule/.

    work/ocr/.venv/bin/python scripts/indochine100k/indochine325_labels.py crops    # fetch label crops
    work/ocr/.venv/bin/python scripts/indochine100k/indochine325_labels.py compare  # run both readers
    work/ocr/.venv/bin/python scripts/indochine100k/indochine325_labels.py --self-test
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indochine100k_georef as geo  # noqa: E402

T = geo.T
GRAT = geo.WORK / "325-graticule"
CROPS = GRAT / "labels"
GEMINI_LOG = CROPS / "gemini-calls.jsonl"
TOL = 0.0051                        # a read matches when it is within half a hundredth of a grade


def parse_grade(text):
    """'114G,40' / '114,40' / '11440' / '19 G 40' -> 114.40; '115G' alone -> 115.0; None if no number."""
    t = re.sub(r"[^0-9.,G]", " ", (text or "").replace("°", "G"))
    m = re.search(r"(\d{2,3})\s*G?\s*[,.]?\s*(\d{2})(?!\d)", t)
    if m:
        return int(m[1]) + int(m[2]) / 100
    m = re.search(r"(?<!\d)(\d{2,3})\s*G?(?!\d)", t)
    return float(m[1]) if m else None


def label_boxes(res):
    """Where each line's label should sit, in full-resolution pixels: {name: [(side, (x0, y0, x1, y1))]}.

    The rough outer frame lines (border_candidates, work scale) bracket the margins; crops are generous
    so the label falls inside whatever the frame style."""
    s = res["scale"]
    W, H = res["size"]
    bc = res["border_candidates"]
    L, R, Tp, B = (bc[k] * s for k in "LRTB")
    lines = res.get("lines") or {}
    out = {}
    hits = res.get("expected_hits") or {}
    for axis, key, names, vals in (("lon", "lon", res["expected_lon"], hits.get("lon")),
                                   ("lat", "lat", res["expected_lat"], hits.get("lat"))):
        for i, g in enumerate(names):
            ln = lines.get(f"{key}{g}")
            if ln:    # traced line: c is the position at ymid, in work px
                at_mid = ln["c"] * s
            elif vals and vals[i] is not None:
                at_mid = vals[i] * s
            else:
                continue
            if axis == "lon":
                out[f"lon{g}"] = [("top", (at_mid - 200, Tp - 10, at_mid + 200, Tp + 240)),
                                  ("bottom", (at_mid - 200, B - 240, at_mid + 200, B + 10))]
            else:
                out[f"lat{g}"] = [("left", (L - 260, at_mid - 110, L + 60, at_mid + 110)),
                                  ("right", (R - 60, at_mid - 110, R + 260, at_mid + 110))]
    return out


def clip(box, W, H):
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    return max(0, x0), max(0, y0), min(W, x1), min(H, y1)


def fetch_crops(res):
    base = "https://iiif.maparchive.vn/iiif/" + res["id"]
    W, H = res["size"]
    items = []
    for name, sides in label_boxes(res).items():
        for side, box in sides:
            x0, y0, x1, y1 = clip(box, W, H)
            if x1 - x0 < 60 or y1 - y0 < 40:
                continue
            path = CROPS / res["id"] / f"{name}_{side}.png"
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                T.fetch_crop_level0(base, x0, y0, x1 - x0, y1 - y0, x1 - x0, max_workers=6).save(path)
            items.append(dict(sheet=res["id"], name=name, side=side, path=str(path),
                              expected=float(name[3:]) if name.startswith("lon") else float(name[3:])))
    return items


def read_local(path):
    import pytesseract
    im = Image.open(path).convert("L")
    im = ImageOps.autocontrast(im.resize((im.width * 2, im.height * 2), Image.Resampling.LANCZOS))
    out = []
    for psm in (7, 11):
        cfg = f"--psm {psm} -c tessedit_char_whitelist=0123456789,.G"
        out.append(pytesseract.image_to_string(im, config=cfg))
    return out


def read_gemini(path):
    import gemini_client as G
    reply = G.extract_labels(
        Image.open(path).convert("RGB"),
        system_prompt="Read the printed graticule coordinate on a map margin.",
        user_prompt=("Read the grade coordinate printed beside the thin graticule line in this crop. "
                     "It looks like 114G,40 or 19G,40: a small superscript G, then a comma, then the decimal "
                     "digits. Ignore km-grid labels (those end in K). Return the value as digits with a decimal "
                     "point, e.g. 114.40 or 19.40, or an empty string if none is legible."),
        schema={"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]},
        model=G.DEFAULT_MODEL, thinking=False, log_path=GEMINI_LOG, cache_dir=None)
    return reply.get("value")


def judge(value, expected):
    if value is None:
        return "none"
    return "right" if abs(value - expected) < TOL else "wrong"


def compare(items, use_gemini=True):
    rows = []
    for it in items:
        t0 = time.perf_counter()
        local_raw = read_local(it["path"])
        t_local = time.perf_counter() - t0
        vals = [parse_grade(r) for r in local_raw]
        # any of the psm variants matching counts as the local read; else the first parse
        local = next((v for v in vals if v is not None and abs(v - it["expected"]) < TOL), next((v for v in vals if v is not None), None))
        row = dict(it, local_raw=[r.strip() for r in local_raw], local=local, local_s=round(t_local, 3),
                   local_result=judge(local, it["expected"]))
        if use_gemini:
            t0 = time.perf_counter()
            try:
                raw = read_gemini(it["path"])
            except Exception as e:  # keep going; the failure is a result
                raw = f"ERROR {e!r}"
            t_g = time.perf_counter() - t0
            g = parse_grade(raw)
            row.update(gemini_raw=raw, gemini=g, gemini_s=round(t_g, 2), gemini_result=judge(g, it["expected"]))
        rows.append(row)
        print(it["name"], it["side"], "local", row["local_result"], row["local"], "|", "gemini",
              row.get("gemini_result"), row.get("gemini"), flush=True)
    return rows


def summarise(rows):
    out = {}
    for who in ("local", "gemini"):
        if f"{who}_result" not in rows[0]:
            continue
        res = [r[f"{who}_result"] for r in rows]
        per_line = {}
        for r in rows:
            per_line.setdefault((r["sheet"], r["name"]), []).append(r[f"{who}_result"])
        out[who] = dict(
            crops=len(rows), right=res.count("right"), wrong=res.count("wrong"), none=res.count("none"),
            lines=len(per_line), lines_with_a_right_read=sum("right" in v for v in per_line.values()),
            lines_with_a_wrong_read=sum("wrong" in v for v in per_line.values()),
            median_s=float(np.median([r[f"{who}_s"] for r in rows])))
    if "gemini_result" in rows[0]:
        out["fallback"] = dict(
            local_then_gemini_lines_right=sum(
                any(r["local_result"] == "right" or r["gemini_result"] == "right" for r in rows
                    if (r["sheet"], r["name"]) == k)
                for k in {(r["sheet"], r["name"]) for r in rows}))
    return out


def self_test():
    assert parse_grade("114G,40") == 114.40
    assert parse_grade("114 ,40") == 114.40
    assert parse_grade("1940") == 19.40
    assert parse_grade("19G,40") == 19.40
    assert parse_grade("115G") == 115.0
    assert parse_grade("") is None and parse_grade(None) is None
    assert judge(114.40, 114.4) == "right" and judge(114.60, 114.4) == "wrong" and judge(None, 1) == "none"
    print("self-test ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", choices=["crops", "compare", "local"])
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    results = [json.loads(p.read_text()) for p in sorted(GRAT.glob("*-*-*-*-*.json"))]
    results = [r for r in results if "border_candidates" in r and r.get("expected_lon") is not None]
    CROPS.mkdir(parents=True, exist_ok=True)
    items = []
    for r in results:
        items += fetch_crops(r)
    print(len(results), "sheets,", len(items), "crops")
    if a.cmd == "crops":
        return
    rows = compare(items, use_gemini=a.cmd == "compare")
    (GRAT / "label-compare.json").write_text(json.dumps(dict(summary=summarise(rows), rows=rows), indent=1))
    print(json.dumps(summarise(rows), indent=1))


if __name__ == "__main__":
    main()
