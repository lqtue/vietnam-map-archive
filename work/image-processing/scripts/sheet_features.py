"""Sheet-wide evidence layers for the river and road passes (1882 first, then 1898).

    work/ocr/.venv/bin/python work/image-processing/scripts/sheet_features.py --sheet 1882
    work/ocr/.venv/bin/python work/image-processing/scripts/sheet_features.py --self-check

Reads the native raster pinned in work/image-processing/experiments/river-reference/native.json (its sha is checked; build it
with `river_ref/export.py --full <sheet>`) and writes work/image-processing/results/<map_id>/features/:

  paper.npy    paper RGB per PAPER_CELL px cell (float32, rows x cols x 3), smoothed. Every other
               layer is measured against it, so ink and wash are relative to the local paper.
  wash.npz     at half resolution, because the scan and the tiles carry colour at half resolution
               (JPEG 4:2:0): `label` (0 none, j = pigment j), `conc` (wash optical density x 255),
               `ink` (ink OD x 255), `pigments` + `names` (unit OD directions read off the sheet's
               legend swatches, pinned in windows.json; pigment 0 is the ink).
               Each pixel is ink plus the one wash that fits it best: RGB has three channels, so
               no more than that is solvable.
  stroke.png   native, ink ridge pixels by stroke width: 1 thin, 2 thick, 3 wide (fill, lettering).
               1882 draws each block's lower-right sides thick and upper-left thin (a shadow line).
  texture.npz  per TEX_CELL px cell: theta (line direction, rad, image axes), coherence, density
               (share darker than LINE_RATIO), width (mean line width at that cut, px), spacing (width / density: the gap
               between parallel lines), dispersion (orientation spread over 3 x 3 cells).
  *.jpg        previews; run.json holds the sha, settings, pigment table and stroke histogram.

Nothing here decides water or road. These are the measurements those passes threshold, tuned on
the calibrate windows only.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates, maximum_filter, uniform_filter

ROOT = Path(__file__).resolve().parents[3]
REF = ROOT / "work" / "image-processing" / "experiments" / "river-reference"

PAPER_CELL = 64          # px; paper varies over hundreds of px (stains, fading), never per line
PAPER_CHROMA_TOL = 0.03  # L1 distance in r,g,b chromaticity from the sheet's paper; salmon is ~0.05 away
PAPER_V_MIN = 0.85       # of the sheet paper's brightest channel; darker pixels are not paper
PIGMENTS = ("ink", "blue", "green", "salmon")  # legend swatches; ink first, it is in every pixel's fit
MIN_CONC = 0.03          # wash OD below this is labelled none
INK_RATIO = 0.6          # grey below this share of the local paper grey is ink (strokes)
LINE_RATIO = 0.85        # fainter lines count for texture: river ripples and military ruling sit at
                         # 0.6-0.85, so at INK_RATIO the river core read as blank. At 0.85, measured
                         # spacing: ripples 13 px, military ruling 5 px, cream street ~45 px
THIN_MAX, THICK_MAX = 2.0, 4.0  # stroke width px (2 * edt - 1): measured 1-1.5 thin, 3 thick on ne_cream
TEX_CELL = 32            # px; blue military ruling is ~5 px apart, river ripples ~15-25
STRIP, PAD = 512, 16     # rows per strip (8 GB machine), context rows each side


def paper_model(rgb: np.ndarray, cell: int = PAPER_CELL) -> tuple[np.ndarray, np.ndarray]:
    h, w, _ = rgb.shape
    s = rgb[::8, ::8].reshape(-1, 3).astype(np.float32)
    v = s.max(1)
    p0 = np.median(s[v >= np.percentile(v, 60)], 0)
    ch0 = p0 / p0.sum()
    rows, cols = -(-h // cell), -(-w // cell)
    acc, n = np.zeros((rows, cols, 3)), np.zeros((rows, cols))
    for i in range(rows):
        b = rgb[i * cell:(i + 1) * cell].astype(np.float32)
        bh = b.shape[0]
        b = np.pad(b, ((0, 0), (0, cols * cell - w), (0, 0)))          # zero pad is never paper
        ch = b / np.maximum(b.sum(2, keepdims=True), 1)
        ok = (np.abs(ch - ch0).sum(2) < PAPER_CHROMA_TOL) & (b.max(2) >= PAPER_V_MIN * p0.max())
        acc[i] = (b * ok[..., None]).reshape(bh, cols, cell, 3).sum((0, 2))
        n[i] = ok.reshape(bh, cols, cell).sum((0, 2))
    good = n >= 0.05 * cell * cell
    est = np.where(good[..., None], acc / np.maximum(n, 1)[..., None], 0)
    out, filled = np.zeros_like(est), np.zeros_like(good)
    # normalised convolution; cells with no paper (solid wash, scan border) take wider neighbours
    for sigma in (1.5, 6, 24):
        num = np.stack([gaussian_filter(est[..., c] * good, sigma) for c in range(3)], -1)
        den = gaussian_filter(good.astype(float), sigma)
        take = ~filled & (den > 0.05)
        out[take] = num[take] / den[take, None]
        filled |= take
    out[~filled] = p0
    return out.astype(np.float32), p0


def paper_at(paper: np.ndarray, yc: np.ndarray, xc: np.ndarray, cell: int = PAPER_CELL) -> np.ndarray:
    """Paper RGB at native continuous coordinates (pixel k's centre is k + 0.5)."""
    yy, xx = np.meshgrid(yc / cell - 0.5, xc / cell - 0.5, indexing="ij")
    return np.stack([map_coordinates(paper[..., c], [yy, xx], order=1, mode="nearest")
                     for c in range(3)], -1).astype(np.float32)


def optical_density(rgb: np.ndarray, paper: np.ndarray) -> np.ndarray:
    return np.clip(-np.log10(np.maximum(rgb, 1) / paper), 0, None)


def swatch_od(rgb: np.ndarray, paper: np.ndarray, box) -> np.ndarray:
    x, y, w, h = box
    return optical_density(rgb[y:y + h, x:x + w].astype(np.float32),
                           paper_at(paper, np.arange(y, y + h) + 0.5, np.arange(x, x + w) + 0.5)).reshape(-1, 3).mean(0)


def legend_pigments(rgb: np.ndarray, paper: np.ndarray, legend: dict) -> tuple[list[str], np.ndarray]:
    """Unit OD directions of the sheet's own legend swatches, ink first.

    A data clustering found salmon, blue and the ink but never the pale green (K=6), so the
    printed key is the pigment list. Its blank swatch is returned separately as a paper check.
    """
    names = [n for n in PIGMENTS if n in legend]
    p = np.stack([swatch_od(rgb, paper, legend[n]) for n in names])
    return names, p / np.linalg.norm(p, axis=1, keepdims=True)


def unmix(od: np.ndarray, pig: np.ndarray):
    """Ink + the best-fitting single wash per pixel -> (label, wash conc, ink conc)."""
    f = od.reshape(-1, 3).T
    best = np.full(f.shape[1], np.inf)
    lab = np.zeros(f.shape[1], np.uint8)
    ink, conc = np.zeros(f.shape[1], np.float32), np.zeros(f.shape[1], np.float32)
    for j in range(1, len(pig)):
        m = np.stack([pig[0], pig[j]], 1)
        # ponytail: clipped least squares, not true NNLS; exact when both concentrations are >= 0
        c = np.clip(np.linalg.pinv(m) @ f, 0, None)
        r = np.linalg.norm(f - m @ c, axis=0)
        b = r < best
        best[b], lab[b], ink[b], conc[b] = r[b], j, c[0, b], c[1, b]
    lab[conc < MIN_CONC] = 0
    sh = od.shape[:2]
    return lab.reshape(sh), conc.reshape(sh), ink.reshape(sh)


def process(rgb: np.ndarray, paper: np.ndarray, pig: np.ndarray):
    """One pass in row strips: wash at half resolution, strokes at native, texture per cell."""
    h, w, _ = rgb.shape
    h2, w2 = h // 2, w // 2
    label, conc8, ink8 = (np.zeros((h2, w2), np.uint8) for _ in range(3))
    stroke = np.zeros((h, w), np.uint8)
    rows, cols = h // TEX_CELL, w // TEX_CELL
    t = {k: np.zeros((rows, cols), np.float32) for k in ("jxx", "jxy", "jyy", "density", "wsum", "wn")}
    for y0 in range(0, h, STRIP):
        y1 = min(h, y0 + STRIP)
        a, b = max(0, y0 - PAD), min(h, y1 + PAD)
        s = rgb[a:b].astype(np.float32)
        p = paper_at(paper, np.arange(a, b) + 0.5, np.arange(w) + 0.5)
        # wash, half resolution: 2 x 2 means over the strip's core rows
        core = s[y0 - a:y1 - a, :w2 * 2]
        e0, e1 = y0 // 2, (y1 - y0) // 2
        c2 = core[:e1 * 2].reshape(e1, 2, w2, 2, 3).mean((1, 3))
        p2 = paper_at(paper, y0 + 2 * np.arange(e1) + 1.0, 2 * np.arange(w2) + 1.0)
        lab, cc, ik = unmix(optical_density(c2, p2), pig)
        label[e0:e0 + e1] = lab
        conc8[e0:e0 + e1] = np.clip(cc * 255, 0, 255)
        ink8[e0:e0 + e1] = np.clip(ik * 255, 0, 255)
        # strokes, native
        g = s.mean(2)
        ink = g < INK_RATIO * p.mean(2)
        dt = distance_transform_edt(ink)
        ridge = ink & (dt >= maximum_filter(dt, 3))
        width = 2 * dt - 1
        cls = np.where(ridge, np.where(width <= THIN_MAX, 1, np.where(width <= THICK_MAX, 2, 3)), 0).astype(np.uint8)
        stroke[y0:y1] = cls[y0 - a:y1 - a]
        # texture, per cell: structure tensor of grey relative to paper
        rel = g / p.mean(2)
        gx = gaussian_filter(rel, 1.0, order=(0, 1))
        gy = gaussian_filter(rel, 1.0, order=(1, 0))
        r0, r1 = y0 // TEX_CELL, min(rows, y1 // TEX_CELL)
        if r1 <= r0:
            continue
        sl = slice(r0 * TEX_CELL - a, r1 * TEX_CELL - a)

        def cells(arr):
            return arr[sl, :cols * TEX_CELL].reshape(r1 - r0, TEX_CELL, cols, TEX_CELL).sum((1, 3))
        t["jxx"][r0:r1], t["jxy"][r0:r1], t["jyy"][r0:r1] = cells(gx * gx), cells(gx * gy), cells(gy * gy)
        faint = rel < LINE_RATIO
        fdt = distance_transform_edt(faint)
        fw = 2 * fdt - 1
        line = faint & (fdt >= maximum_filter(fdt, 3)) & (fw <= THICK_MAX)
        t["density"][r0:r1] = cells(faint.astype(np.float32)) / TEX_CELL ** 2
        t["wsum"][r0:r1], t["wn"][r0:r1] = cells(np.where(line, fw, 0)), cells(line.astype(np.float32))
    jxx, jxy, jyy = t["jxx"], t["jxy"], t["jyy"]
    coherence = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / np.maximum(jxx + jyy, 1e-9)
    theta = np.mod(0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2, np.pi)   # gradient -> line direction
    width = t["wsum"] / np.maximum(t["wn"], 1)
    spacing = np.where(t["density"] > 0, width / np.maximum(t["density"], 1e-9), 0)
    vec = coherence * np.exp(2j * theta)
    mag = uniform_filter(np.abs(vec), 3)
    dispersion = 1 - np.abs(uniform_filter(vec.real, 3) + 1j * uniform_filter(vec.imag, 3)) / np.maximum(mag, 1e-9)
    texture = {"theta": theta, "coherence": coherence, "density": t["density"], "width": width,
               "spacing": spacing, "dispersion": dispersion}
    return label, conc8, ink8, stroke, {k: v.astype(np.float32) for k, v in texture.items()}


def display_rgb(p: np.ndarray, od: float = 0.5) -> np.ndarray:
    """What pigment direction p looks like at a given OD on white."""
    return 255 * 10 ** (-od * p / p.max())


def previews(out: Path, rgb, paper, pig, label, conc8, ink8, stroke, tex, windows, sheet):
    """Preview images. Heldout windows with seen:false are painted black in every whole-sheet preview
    (river_ref/view.py), so opening them cannot leak those windows; `windows` are the stroke crops."""
    import sys
    sys.path.insert(0, str(REF))
    from view import blank
    h, w, _ = rgb.shape
    pv = np.asarray(Image.fromarray(paper.clip(0, 255).astype(np.uint8)).resize((w // 8, h // 8), Image.BILINEAR), float)
    Image.fromarray(blank(np.clip((pv - pv.reshape(-1, 3).mean(0)) * 6 + 128, 0, 255).astype(np.uint8), sheet, 8)).save(out / "paper.jpg", quality=88)
    lab, cc, ik = label[::4, ::4], conc8[::4, ::4] / 255, ink8[::4, ::4] / 255
    cols = np.array([display_rgb(p) for p in pig])
    alpha = np.clip(cc / 0.3, 0, 1)[..., None]
    img = 255 * (1 - alpha) + cols[lab] * alpha
    img = np.where((ik > 0.25)[..., None], 40, img)
    Image.fromarray(blank(img.astype(np.uint8), sheet, 8)).save(out / "wash.jpg", quality=88)
    hsv = np.stack([tex["theta"] / np.pi * 255, np.full_like(tex["theta"], 255),
                    np.clip(tex["coherence"] * np.clip(tex["density"] * 5, 0, 1), 0, 1) * 255], -1)
    a = Image.fromarray(blank(np.asarray(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")), sheet, TEX_CELL))
    sp = tex["spacing"]
    keep = (tex["coherence"] > 0.5) & (tex["density"] > 0.03)
    val = np.clip(sp / 30, 0, 1)
    b = np.where(keep[..., None], np.stack([255 * val, 80 + 0 * val, 255 * (1 - val)], -1), 255)
    sc = 4
    pair = Image.new("RGB", (a.width * sc * 2 + 10, a.height * sc), "white")
    pair.paste(a.resize((a.width * sc, a.height * sc), Image.NEAREST), (0, 0))
    pair.paste(Image.fromarray(blank(b.astype(np.uint8), sheet, TEX_CELL)).resize((a.width * sc, a.height * sc), Image.NEAREST), (a.width * sc + 10, 0))
    pair.save(out / "texture.jpg", quality=88)
    for name, (x, y, bw, bh) in windows.items():
        crop = rgb[y:y + bh, x:x + bw].astype(float) * 0.35 + 165
        st = stroke[y:y + bh, x:x + bw]
        for v, c in ((1, (0, 90, 255)), (2, (230, 0, 0)), (3, (110, 110, 110))):
            crop[st == v] = c
        Image.fromarray(crop.astype(np.uint8)).save(out / f"stroke-{name}.png")


def self_check() -> None:
    n = 512
    xx = np.arange(n)[None, :, None] / n
    paper = np.array([230, 215, 190.]) * (1 - xx) + np.array([214, 199, 174.]) * xx
    img = np.repeat(paper, n, 0)
    yy = np.arange(n)[:, None]
    img[:256, :256][(yy[:256] % 6 == 0).repeat(256, 1)] *= 0.25         # hatch, 6 px apart
    img[:256, 256:][(yy[:256] % 20 == 0).repeat(256, 1)] *= 0.25        # ripples, 20 px apart
    img[256:, 100] *= 0.25                                               # thin line
    img[256:, 299:302] *= 0.25                                           # thick line
    rgb = img.round().astype(np.uint8)
    pm, _ = paper_model(rgb)
    probe = paper_at(pm, np.array([448.5]), np.array([200.5]))[0, 0]
    assert np.abs(probe - img[448, 200]).max() < 6, (probe, img[448, 200])
    pig = np.array([[1, 1, 1], [1, .5, .2], [.2, .6, 1]], float)
    pig /= np.linalg.norm(pig, axis=1, keepdims=True)
    lab, cc, ik = unmix((0.3 * pig[0] + 0.2 * pig[2])[None, None], pig)
    assert lab[0, 0] == 2 and abs(cc[0, 0] - 0.2) < 0.01 and abs(ik[0, 0] - 0.3) < 0.01, (lab, cc, ik)
    _, _, _, stroke, tex = process(rgb, pm, pig)
    assert stroke[400, 100] == 1 and stroke[400, 300] == 2, (stroke[400, 98:103], stroke[400, 298:304])
    sa, sb = tex["spacing"][2:6, 1:7], tex["spacing"][2:6, 9:15]
    assert 4.5 < np.median(sa) < 7.5 and 15 < np.median(sb) < 25, (np.median(sa), np.median(sb))
    assert tex["coherence"][2:6, 1:7].min() > 0.8
    assert np.abs(np.sin(tex["theta"][2:6, 1:7])).max() < 0.2                # horizontal lines
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    t0 = time.time()
    pin = json.loads((REF / "native.json").read_text())[a.sheet]
    spec = json.loads((REF / "windows.json").read_text())
    map_id = spec["sheets"][a.sheet]["map_id"]
    Image.MAX_IMAGE_PIXELS = None
    rgb = np.asarray(Image.open(ROOT / pin["path"]).convert("RGB"))
    assert hashlib.sha256(rgb.tobytes()).hexdigest() == pin["rgb_sha256"], "native raster differs from native.json"
    out = ROOT / "work" / "image-processing" / "results" / map_id / "features"
    out.mkdir(parents=True, exist_ok=True)
    paper, p0 = paper_model(rgb)
    legend = spec["sheets"][a.sheet]["legend"]
    names, pig = legend_pigments(rgb, paper, legend)
    blank_od = float(np.linalg.norm(swatch_od(rgb, paper, legend["paper"])))
    t1 = time.time()
    label, conc8, ink8, stroke, tex = process(rgb, paper, pig)
    t2 = time.time()
    np.save(out / "paper.npy", paper)
    np.savez_compressed(out / "wash.npz", label=label, conc=conc8, ink=ink8, pigments=pig, names=np.array(names))
    Image.fromarray(stroke).save(out / "stroke.png", optimize=False, compress_level=6)
    np.savez_compressed(out / "texture.npz", **tex)
    wins = {w["id"]: w["box"] for w in spec["windows"]
            if w["sheet"] == a.sheet and w["id"] in ("ne_cream", "dense_grid", "blue_domain", "open_bank")}
    previews(out, rgb, paper, pig, label, conc8, ink8, stroke, tex, wins, a.sheet)
    share = np.bincount(label.ravel(), minlength=len(pig)) / label.size
    hist = np.bincount(stroke.ravel(), minlength=4)
    run = {"sheet": a.sheet, "map_id": map_id, "native_sha256": pin["rgb_sha256"],
           "settings": {k: globals()[k] for k in ("PAPER_CELL", "PAPER_CHROMA_TOL", "PAPER_V_MIN", "PIGMENTS",
                                                  "MIN_CONC", "INK_RATIO", "LINE_RATIO", "THIN_MAX", "THICK_MAX", "TEX_CELL")},
           "legend": legend,
           "paper_global_rgb": [round(float(v), 1) for v in p0],
           "blank_swatch_od": round(blank_od, 4),
           "pigments": [{"index": j, "name": names[j], "od_direction": [round(float(v), 3) for v in p],
                         "rgb_at_od_0.5": [int(v) for v in display_rgb(p)], "label_share": round(float(share[j]), 4)}
                        for j, p in enumerate(pig)],
           "stroke_ridge_px": {"thin": int(hist[1]), "thick": int(hist[2]), "wide": int(hist[3])},
           "seconds": {"paper_and_pigments": round(t1 - t0, 1), "process": round(t2 - t1, 1),
                       "total": round(time.time() - t0, 1)}}
    (out / "run.json").write_text(json.dumps(run, indent=1) + "\n")
    print(json.dumps(run, indent=1))


if __name__ == "__main__":
    main()
