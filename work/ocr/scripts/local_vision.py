"""Local (offline) vision passes for the OCR pipeline — no API calls.

Two passes the M-series runs for free, in parallel, with no rate limit:

  detect_legend_boxes(image)  — scipy.ndimage ruled-rectangle finder.
                                Locates legend / cartouche / title inset boxes.
  spot_numerals(image, ...)   — Tesseract digit spotting. Finds legend-reference
                                numbers scattered on the map body.

Why local for exactly these two: geometry (bordered boxes) and digits are the
parts of map OCR that classical/local tools do as well as a frontier VLM —
and for free. Semantic text (place names, legend descriptions) stays on Gemini
because faded/rotated/multilingual recognition is where the frontier model earns
its keep. See docs/guides/pipelines.md.

ponytail: pure scipy + Tesseract, chosen because cv2/PaddleOCR have no clean
Python 3.14 wheel today. Upgrade path if digit recall is too low — swap
spot_numerals() for a PaddleOCR detector in a 3.11 venv; keep the same
[{text, bbox, confidence}] return shape and nothing downstream changes.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


# ── Legend / cartouche box detection (pure scipy.ndimage) ──────────────────────

def detect_legend_boxes(
    image: Image.Image,
    *,
    ink_thresh: int = 200,
    min_area_frac: float = 0.008,
    max_area_frac: float = 0.6,
    min_side_frac: float = 0.05,
    edge_coverage: float = 0.35,
) -> list[dict]:
    """Find ruled rectangular boxes (legend / cartouche / title insets).

    Detects long horizontal + vertical ink lines, joins them into frames, and
    keeps components whose four bbox edges are each mostly inked — i.e. a drawn
    rectangle, not a dense text blob. Coordinates are in the passed image's pixel
    space; the caller scales them back to source resolution.

    Only finds *bordered* boxes. Borderless legends won't trip it — that's the
    honest limit; fall back to a manual region or the whole-image legend pass.

    Returns [{"bbox": (x, y, w, h), "score": 0-1}] sorted by score descending.
    """
    from scipy import ndimage

    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    H, W = gray.shape
    ink = gray < ink_thresh

    # A ruled border line runs continuously for a good fraction of the box.
    line_len = max(15, int(min(W, H) * 0.04))
    h_struct = np.ones((1, line_len), dtype=bool)
    v_struct = np.ones((line_len, 1), dtype=bool)
    h_lines = ndimage.binary_erosion(ink, structure=h_struct)
    v_lines = ndimage.binary_erosion(ink, structure=v_struct)
    lines = h_lines | v_lines
    # Erosion trims each line end by ~line_len/2, leaving corner gaps that big.
    # Dilate by the same amount so the four sides bridge and label as one frame.
    lines = ndimage.binary_dilation(lines, iterations=max(3, line_len // 2))

    labels, n = ndimage.label(lines)
    img_area = float(W * H)
    boxes: list[dict] = []
    for sl in ndimage.find_objects(labels):
        if sl is None:
            continue
        ys, xs = sl
        x, y = xs.start, ys.start
        w, h = xs.stop - xs.start, ys.stop - ys.start
        if w < min_side_frac * W or h < min_side_frac * H:
            continue
        area_frac = (w * h) / img_area
        if not (min_area_frac <= area_frac <= max_area_frac):
            continue
        comp = labels[sl] > 0
        # Frame test: each of the four bbox edges should be substantially inked.
        band = max(2, int(min(w, h) * 0.03))
        top = comp[:band, :].mean()
        bottom = comp[-band:, :].mean()
        left = comp[:, :band].mean()
        right = comp[:, -band:].mean()
        score = float(min(top, bottom, left, right))
        if score < edge_coverage:
            continue
        boxes.append({"bbox": (int(x), int(y), int(w), int(h)), "score": round(score, 3)})

    boxes.sort(key=lambda b: b["score"], reverse=True)
    return boxes


# ── Numeral spotting (Tesseract, digits only) ──────────────────────────────────

def spot_numerals(
    image: Image.Image,
    *,
    min_conf: float = 40.0,
    min_len: int = 1,
    max_len: int = 4,
) -> list[dict]:
    """Detect standalone numerals via Tesseract sparse-text mode.

    Digit whitelist + psm 11 (sparse text) — the model is told to find scattered
    tokens and only emit numbers, so place names never leak in. Rotated glyphs
    are missed; legend refs are near-upright, so that's acceptable.

    Returns [{"text": "12", "bbox": (x, y, w, h), "confidence": 0-1}] in image px.
    """
    import pytesseract
    from pytesseract import Output

    cfg = "--psm 11 -c tessedit_char_whitelist=0123456789"
    data = pytesseract.image_to_data(image, config=cfg, output_type=Output.DICT)

    out: list[dict] = []
    for i, raw in enumerate(data["text"]):
        t = raw.strip()
        if not t or not t.isdigit():
            continue
        if not (min_len <= len(t) <= max_len):
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            continue
        if conf < min_conf:
            continue
        out.append({
            "text": t,
            "bbox": (int(data["left"][i]), int(data["top"][i]),
                     int(data["width"][i]), int(data["height"][i])),
            "confidence": round(conf / 100.0, 3),
        })
    return out


# ── Self-check ─────────────────────────────────────────────────────────────────

def _demo() -> None:
    """Runnable check: draw a bordered box + digits, assert both passes find them."""
    from PIL import ImageDraw, ImageFont

    img = Image.new("L", (800, 600), color=255)
    d = ImageDraw.Draw(img)
    # A ruled legend box in the lower-left quadrant.
    box = (60, 360, 300, 200)  # x, y, w, h
    d.rectangle([box[0], box[1], box[0] + box[2], box[1] + box[3]], outline=0, width=3)
    # Scattered numerals across the map body.
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    for (nx, ny, txt) in [(120, 80, "12"), (500, 150, "7"), (650, 420, "134")]:
        d.text((nx, ny), txt, fill=0, font=font)

    boxes = detect_legend_boxes(img)
    assert boxes, "detect_legend_boxes found nothing"
    bx, by, bw, bh = boxes[0]["bbox"]
    # Top box should overlap the drawn rectangle's region.
    assert abs(bx - box[0]) < 40 and abs(by - box[1]) < 40, f"box off: {boxes[0]}"
    print(f"[ok] legend box: {boxes[0]}")

    nums = spot_numerals(img, min_conf=10)
    found = {n["text"] for n in nums}
    assert {"12", "7"} & found, f"expected some of 12/7/134, got {found}"
    print(f"[ok] numerals: {sorted(found)}")
    print("[ok] local_vision self-check passed")


if __name__ == "__main__":
    _demo()
