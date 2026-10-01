"""Road pass v1, 1882: the carriageway between blocks, from the paper-coloured space between outlines.

    work/ocr/.venv/bin/python work/ocr/scripts/road_pass.py --sheet 1882
    work/ocr/.venv/bin/python work/ocr/scripts/road_pass.py --sheet 1882 --window ne_cream   # calibrate preview
    work/ocr/.venv/bin/python work/ocr/scripts/road_pass.py --self-check

Needs sheet_features.py's paper.npy, river_pass.py's water.png and cells.npz. Writes
work/ocr/outputs/<map_id>/river/: road.png (native, 255 = road), road-preview.jpg, road-run.json.

The representation (docs/river-reconstruction.md, "Road pass, 1882"): a street is the unfilled
space between block outlines, so the pass finds that space and keeps what is street-shaped.
  1. ink: grey / local paper below INK_GREY, grown by INK_PAD. That catches outlines, kerb lines,
     hatch (salmon, blue, green and grey alike), lettering and the red tramway. Small isolated ink
     components (under GLYPH px across: letters, numbers, the city-limit crosses) are not walls.
  2. free space: not ink, not water (river_pass), inside the neatline, outside the furniture.
  3. core: free space deeper than R_CORE px from any wall, and not in a machine-ruled cell
     (cells.npz). Hatch is ruled ink every 4-5 px and fills no core; faint hatch is caught by the
     cell test. Pavement strips (a thin kerb line a few px inside a street) are narrower than
     2 * R_CORE, so they are not core: the carriageway is what is left, which is the owner's rule
     (the kerb line, or where none is drawn the block outline, is the edge).
  4. the core grows back to its walls through free space only (geodesic, so it never crosses a
     kerb line into a pavement), which restores the carriageway to the line.
  5. open fields (free space deeper than FAT px: the blank land outside the city limit, a plaza
     bigger than any street) are cut out with a margin; a street flaring into one stops there.
  6. across a red tramway (it is not an edge) road on both sides is joined.
  7. components: a blank block is a paper-coloured face closed by its outline, so it is also free
     space. It is separated from the street by the outline, and is compact; a street is a long
     thin network. A component is kept if its area over its inscribed radius squared (long and
     thin = large) reaches SHAPE_MIN, or it is as large as a network (NET_AREA).
What it cannot do: tell a blank block that leaks through an outline gap from a street, lanes
narrower than 2 * R_CORE, a kerb line the scan lost, lettering that touches a wall, and a street
that is itself drawn as a closed outline with lettering inside it (read as a block).
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as nd

ROOT = Path(__file__).resolve().parents[3]
REF = ROOT / "work" / "analysis" / "river_ref"
sys.path.insert(0, str(Path(__file__).parent))
from sheet_features import paper_at  # noqa: E402

INK_GREY, INK_PAD, GLYPH = 0.92, 1, 60
R_CORE, FAT = 9, 70
BRIDGE_REACH, BRIDGE_INK, BRIDGE_MIN, BRIDGE_MAX = 14, 0.8, 150, 8000   # px: deck reach from water, grey/paper of its hatch, area range
RED_OD = 0.65                   # od(R) below this share of od(G): red ink, not black
TILE, MARGIN = 1024, 2 * FAT + 40
SHAPE_MIN, NET_AREA = 20.0, 200_000
LANE_R, LANE_RATIO = 24, 12.0   # a street fragment (a tramway or lettering cut it) is thin, a little shorter than a street
GARDEN_COH, GARDEN_WIN, GARDEN_FRAC, GARDEN_MIN = 0.3, 7, 0.45, 60   # cells; coherence below GARDEN_COH is stipple, not line work
CELL = 32


def disk(r):
    return np.hypot(*np.mgrid[-r:r + 1, -r:r + 1]) <= r


def road_tile(s, p, water, wall, ruled):
    """One tile of road, from float RGB `s`, local paper `p`, bool water / wall (outside the map) / ruled.
    Returns (road, deck, glyph) at tile size: the road before shape selection, candidate bridge decks, and
    the small ink components treated as lettering. The caller keeps the interior (margins are context)."""
    rel = np.clip(s / p, 0.02, 2)
    grey = rel.mean(2)
    od = -np.log10(rel)
    red = (od[..., 0] < RED_OD * od[..., 1]) & (od[..., 1] > 0.12)
    ink = nd.binary_dilation(grey < INK_GREY, disk(INK_PAD))
    lab, n = nd.label(ink, np.ones((3, 3)))
    if n:
        sl = nd.find_objects(lab)
        ext = np.array([max(t[0].stop - t[0].start, t[1].stop - t[1].start) for t in sl])
        glyph = ink & ~np.concatenate([[False], ext >= GLYPH])[lab]
    else:
        glyph = np.zeros_like(ink)
    free = ~(ink & ~glyph) & ~nd.binary_dilation(water, disk(2)) & ~wall
    dist = nd.distance_transform_edt(free)
    core = (dist > R_CORE) & ~ruled
    road = nd.binary_dilation(core, nd.generate_binary_structure(2, 1), iterations=R_CORE + 2, mask=free)
    fat = nd.distance_transform_edt(dist <= FAT) <= FAT       # within FAT of a fat core pixel
    road &= ~nd.binary_dilation(fat, disk(3))
    # a red tramway is not an edge: road on both sides is joined across it
    redz = nd.binary_dilation(nd.binary_closing(red & ink, disk(5)), disk(2))
    road |= nd.binary_closing(road, disk(12)) & redz & ~wall
    # candidate bridge decks: dark hatched blobs beside water (kept only if road lies on two sides, see add_bridges)
    near = nd.binary_dilation(water, disk(BRIDGE_REACH)) & ~water
    deck = nd.binary_opening(near & nd.binary_closing(grey < BRIDGE_INK, disk(3)) & ~wall, disk(3))   # a deck is a blob; a hatch strip along a bank is not
    return road, deck, glyph


def garden_cells(stipple):
    """Park lawns and tree masses are unruled, incoherent texture in big dense patches; the paths between
    them are paper and would read as streets, but the owner's rule makes a garden interior part of the
    block. A patch is where stipple cells fill GARDEN_FRAC of a GARDEN_WIN-cell window (paths are 2-3
    cells wide and still inside), at least GARDEN_MIN cells; scattered stipple elsewhere never reaches it."""
    g = nd.uniform_filter(stipple.astype(np.float32), GARDEN_WIN) > GARDEN_FRAC
    lab, n = nd.label(g)
    area = nd.sum(g, lab, np.arange(1, n + 1))
    g = np.concatenate([[False], area >= GARDEN_MIN])[lab]
    return nd.binary_closing(g, np.ones((3, 3)))


def add_bridges(road, deck):
    """A bridge is road: a candidate deck (a dark hatched blob beside water) that touches the selected road on
    two separate sides is added, so a street crosses its creek. Done after selection so that a deck cannot
    join a street to the blank lots beside it."""
    lab, n = nd.label(deck, np.ones((3, 3)))
    out = road.copy()
    for i, t in enumerate(nd.find_objects(lab)):
        t = (slice(max(0, t[0].start - 8), t[0].stop + 8), slice(max(0, t[1].start - 8), t[1].stop + 8))
        d = lab[t] == i + 1
        if not BRIDGE_MIN <= d.sum() <= BRIDGE_MAX:
            continue
        if nd.label(nd.binary_dilation(d, disk(5)) & road[t])[1] >= 2:
            out[t] |= nd.binary_fill_holes(nd.binary_closing(d, disk(4)))
    return out


def select(road, keep_min=SHAPE_MIN, net_area=NET_AREA):
    """Keep street-shaped components of a road mask: area / inscribed radius^2 (a long thin network is large,
    a block is not) at least keep_min, or an area that only a network reaches. Returns the mask and stats."""
    lab, n = nd.label(road)
    if not n:
        return road, []
    idx = np.arange(1, n + 1)
    area = nd.sum(road, lab, idx)
    mx = np.zeros(n)       # inscribed radius, one bounding box at a time (a sheet-wide float64 EDT is 0.9 GB)
    for i, t in enumerate(nd.find_objects(lab)):
        sub = np.pad(lab[t] == i + 1, 1)
        mx[i] = nd.distance_transform_edt(sub).max()
    ratio = area / np.maximum(mx, 1) ** 2
    ok = (ratio >= keep_min) | (area >= net_area) | ((mx <= LANE_R) & (ratio >= LANE_RATIO))
    stats = [{"id": int(i), "area": int(a), "inscribed": float(m), "ratio": float(r), "kept": bool(k)}
             for i, a, m, r, k in zip(idx, area, mx, ratio, ok)]
    return np.concatenate([[False], ok])[lab], stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet")
    ap.add_argument("--window")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    t0 = time.time()
    spec = json.loads((REF / "windows.json").read_text())
    sheet = spec["sheets"][a.sheet]
    pin = json.loads((REF / "native.json").read_text())[a.sheet]
    Image.MAX_IMAGE_PIXELS = None
    rgb = np.asarray(Image.open(ROOT / pin["path"]).convert("RGB"))
    assert hashlib.sha256(rgb.tobytes()).hexdigest() == pin["rgb_sha256"], "native raster differs from native.json"
    base = ROOT / "work" / "ocr" / "outputs" / sheet["map_id"]
    out = base / "river"
    paper = np.load(base / "features" / "paper.npy")
    cells = np.load(out / "cells.npz")
    h, w, _ = rgb.shape
    rows, cols = h // CELL, w // CELL
    ruled_c = (cells["loge"] > 4.0) & (cells["rule"] > 0.35)       # river_pass TEX_LOG_E, RULE_MAX
    coh = np.load(base / "features" / "texture.npz")["coherence"][:rows, :cols]
    garden_c = garden_cells((cells["loge"] > 4.0) & ~ruled_c & (coh < GARDEN_COH))
    ruled = np.zeros((h, w), bool)
    ruled[:rows * CELL, :cols * CELL] = np.kron(ruled_c | garden_c, np.ones((CELL, CELL), bool))
    garden = np.zeros((h, w), bool)      # a garden's paths are block, so its cells are cut from the road outright
    garden[:rows * CELL, :cols * CELL] = np.kron(nd.binary_erosion(garden_c, np.ones((3, 3))), np.ones((CELL, CELL), bool))
    water = np.asarray(Image.open(out / "water.png")) == 255
    wall = np.ones((h, w), bool)
    rs = sheet.get("road", {})
    x, y, bw, bh = rs.get("neatline", sheet["neatline"])
    wall[y:y + bh, x:x + bw] = False
    pad = rs.get("furniture_pad", 0)
    for fx, fy, fw, fh in sheet["furniture"].values():
        wall[max(0, fy - pad):fy + fh + pad, max(0, fx - pad):fx + fw + pad] = True
    if a.window:
        bx, by, bw_, bh_ = next(v["box"] for v in spec["windows"] if v["sheet"] == a.sheet and v["id"] == a.window)
        tiles = [(bx, by, bx + bw_, by + bh_)]
    else:
        tiles = [(x0, y0, min(w, x0 + TILE), min(h, y0 + TILE)) for y0 in range(0, h, TILE) for x0 in range(0, w, TILE)]
    road, deck = np.zeros((h, w), bool), np.zeros((h, w), bool)
    for x0, y0, x1, y1 in tiles:
        c0, c1, r0, r1 = max(0, x0 - MARGIN), min(w, x1 + MARGIN), max(0, y0 - MARGIN), min(h, y1 + MARGIN)
        s = rgb[r0:r1, c0:c1].astype(np.float32)
        p = paper_at(paper, np.arange(r0, r1) + 0.5, np.arange(c0, c1) + 0.5)
        m, dk, _ = road_tile(s, p, water[r0:r1, c0:c1], wall[r0:r1, c0:c1], ruled[r0:r1, c0:c1])
        road[y0:y1, x0:x1] = m[y0 - r0:y1 - r0, x0 - c0:x1 - c0]
        deck[y0:y1, x0:x1] = dk[y0 - r0:y1 - r0, x0 - c0:x1 - c0]
    road &= ~garden
    road, stats = select(road)
    road = add_bridges(road, deck)
    print(len(stats), "components,", sum(s["kept"] for s in stats), "kept;", round(time.time() - t0), "s")
    if a.window:
        Image.fromarray((road[by:by + bh_, bx:bx + bw_] * 255).astype(np.uint8)).save(out / f"road-{a.window}.png")
        return
    Image.fromarray(road.astype(np.uint8) * 255).save(out / "road.png", compress_level=6)
    sys.path.insert(0, str(REF))
    from view import blank
    pv = rgb[::8, ::8].astype(np.float32)
    mv = road[::8, ::8]
    pv[mv] = pv[mv] * 0.4 + np.array([255, 150, 0]) * 0.6
    Image.fromarray(blank(pv.astype(np.uint8), a.sheet, 8)).save(out / "road-preview.jpg", quality=85)
    run = {"sheet": a.sheet, "native_sha256": pin["rgb_sha256"],
           "settings": {k: globals()[k] for k in ("INK_GREY", "INK_PAD", "GLYPH", "R_CORE", "FAT", "RED_OD", "BRIDGE_REACH", "BRIDGE_INK", "BRIDGE_MIN", "BRIDGE_MAX", "SHAPE_MIN", "NET_AREA", "LANE_R", "LANE_RATIO", "GARDEN_COH", "GARDEN_WIN", "GARDEN_FRAC", "GARDEN_MIN")},
           "road_px": int(road.sum()), "components": len(stats), "kept": sum(s["kept"] for s in stats),
           "seconds": round(time.time() - t0, 1)}
    (out / "road-run.json").write_text(json.dumps(run, indent=1) + "\n")
    print(json.dumps(run, indent=1))


def self_check():
    """Synthetic sheet: a long street with a pavement strip and kerb line, a closed blank block, a ruled block, a
    letter in the street, a red tramway across it, and a creek with a hatched bridge deck."""
    n, m = 640, 900
    paper = np.array([220.0, 208.0, 185.0])
    img = np.tile(paper, (n, m, 1))
    black = np.array([40.0, 38.0, 36.0])

    def hline(y0, x0, x1, t=2):
        img[y0:y0 + t, x0:x1] = black

    def vline(x0, y0, y1, t=2):
        img[y0:y1, x0:x0 + t] = black
    # street y 280-320; its outlines, and a kerb line 12 px inside the upper one (pavement strip y 282-292)
    hline(278, 0, m)
    hline(321, 0, m)
    hline(292, 0, m, 1)
    # closed blank block above: compact, outlined on all four sides
    hline(100, 100, 500)
    hline(277, 100, 500)
    vline(100, 100, 279)
    vline(500, 100, 279)
    # ruled block below: lines every 5 px
    img[330:600:5, 60:560] = paper * 0.7
    # a bold letter standing in the street, a red tramway across it
    img[300:316, 120:136] = black
    img[0:n, 400:403] = (190, 90, 60)
    # a creek across the street with a hatched deck on the carriageway
    water = np.zeros((n, m), bool)
    water[:, 560:600] = True
    water[296:318, 560:600] = False
    img[296:318:3, 560:600] = black
    img[296:318, 560:562] = black
    p = np.tile(paper, (n, m, 1)).astype(np.float32)
    wall = np.zeros((n, m), bool)
    road, deck, glyph = road_tile(img.astype(np.float32), p, water, wall, np.zeros((n, m), bool))
    assert glyph[300:316, 120:136].any(), "a letter is not a wall"
    assert road[305, 300] and road[305, 128], "carriageway, including under the letter"
    assert not road[285, 300], "the pavement strip between block line and kerb is land"
    assert road[305, 401], "road is joined across a red tramway"
    assert not road[400, 300], "hatch is not street"
    keep, _ = select(road)
    assert keep[305, 300] and not keep[200, 300], "the closed blank block is compact, the street is not"
    assert not keep[400, 300], "hatch is not street"
    assert not keep[305, 575] and add_bridges(keep, deck)[305, 575], "bridge joins road on both sides"
    # garden cells: a big dense patch of stipple with a 2-cell path through it, against scattered stipple
    st = np.zeros((60, 60), bool)
    st[10:50, 10:50] = True
    st[:, 29:31] = False
    st[::7, 2] = True
    g = garden_cells(st)
    assert g[30, 30] and g[20, 20] and not g[5, 5] and not g[55, 55]
    print("self-check ok")


if __name__ == "__main__":
    main()
