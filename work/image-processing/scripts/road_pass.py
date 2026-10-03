"""Road pass v2, 1882: the carriageway between blocks, from the paper-coloured space between outlines.

    work/ocr/.venv/bin/python work/image-processing/scripts/road_pass.py --sheet 1882
    work/ocr/.venv/bin/python work/image-processing/scripts/road_pass.py --sheet 1882 --window ne_cream   # calibrate preview
    work/ocr/.venv/bin/python work/image-processing/scripts/road_pass.py --self-check

Needs sheet_features.py's paper.npy, river_pass.py's water.png and cells.npz. Writes
work/image-processing/results/<map_id>/river/: road.png (native, 255 = road), road-preview.jpg, road-run.json.
`--window` refuses a heldout window with seen:false (view.py's rule).

The representation (docs/research/river-reconstruction.md, "Road pass, 1882" and "Road pass v2"): a street is
the unfilled space between block outlines, so the pass finds that space and keeps what is
street-shaped.
  1. ink: grey / local paper below INK_GREY, grown by INK_PAD. That catches outlines, kerb lines,
     hatch (salmon, blue, green and grey alike), lettering and the red tramway. Small isolated ink
     components (under GLYPH px across: letters, numbers, the city-limit crosses) are not walls.
  2. free space: not ink, not water (river_pass), inside the neatline, outside the furniture.
  3. faces (v2): free space that survives an opening by R_FACE (strips at least 2 * R_FACE + 1 px
     across), grown back to its walls through free space only (geodesic, so a face never crosses a
     kerb line). Hatch is ruled ink every 4-5 px and leaves no face; v1's 9 px core (a 19 px street)
     missed every carriageway between kerbs, which are 12-20 px.
  4. open ground is cut out with a margin: free space deeper than FAT px (the blank land outside the
     city limit), and, beside water, deeper than FAT_Q px (a blank yard between a block line and the
     water is not a quay road, which is a strip of about 15-35 px).
  5. across a red tramway (it is not an edge) road on both sides is joined.
  6. components: a blank block is a paper-coloured face closed by its outline, so it is also a face.
     It is compact; a street is a long thin network. A component is kept if area / inscribed radius^2
     reaches SHAPE_MIN, or it is as large as a network (NET_AREA). A component that is narrow
     everywhere (inscribed radius <= R_CORE: no 19 px core, v1's rule) must also be large
     (NARROW_AREA): a lone narrow strip is a plot or a pavement ring, a street network is not.
  7. kerbs (v2): in a street seen in cross-section, a wall between two strips, thin (<= 2 * DK - 1 px of
     ink) with a strip-shaped face either side, is a kerb. From each road pixel a ray goes both ways
     along the axis (of four) with the shortest chord, to the first wall. Both walls kerbs: the strip is
     the carriageway (`inner`). One kerb and one outline: it is a pavement if it is narrower than
     W_NARROW (the carriageway is what is left), or any wider strip beside an inner one (a boulevard's
     lettered strip between kerbs is the road, the wide promenades either side are not). No kerb on
     either side: a plain street, kept.
  8. bridges: a dark hatched deck beside water is road if road lies on two sides of it (a crossing) or
     water on most of its perimeter (a pier or landing stage, which the owner labels a bridge).
What it cannot do: tell a blank block that leaks through an outline gap from a street, a kerb line the
scan lost, lettering that touches a wall (it cuts the strip), a two-strip street with a kerb on one
side only (both strips stay if each is wider than W_NARROW), and a street drawn as a closed outline
with lettering inside it (read as a block).
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
REF = ROOT / "work" / "image-processing" / "experiments" / "river-reference"
sys.path.insert(0, str(Path(__file__).parent))
from sheet_features import paper_at  # noqa: E402

INK_GREY, INK_PAD, GLYPH = 0.92, 1, 60
R_FACE, R_CORE, FAT, FAT_Q, YARD_EDGE, RIM, RIM_R = 3, 9, 70, 36, 10, 30, 10
RULED_DEEP = 14                 # a face deeper than this inside a ruled cell is faint hatch; narrower is a street between hatched blocks
BRIDGE_REACH, BRIDGE_INK, BRIDGE_MIN, BRIDGE_MAX = 14, 0.8, 150, 8000   # px: deck reach from water, grey/paper of its hatch, area range
DECK_SOLID, SOLID_GREY = 1.01, 0.45   # a candidate deck whose pixels are darker than SOLID_GREY (grey / paper) over more than this share is solid lettering, not a hatched pier (1.01 = off)
PIER_WATER = 0.4                # share of a deck's rim (4 px) that is water for it to be a pier: a crossing has about half, a quay-side building a quarter
RED_OD = 0.65                   # od(R) below this share of od(G): red ink, not black
TILE, MARGIN = 1024, 2 * FAT + 40
SHAPE_MIN, NET_AREA, NARROW_AREA, SPECK = 20.0, 200_000, 15_000, 500
LANE_R, LANE_RATIO = 24, 12.0   # a street fragment (a tramway or lettering cut it) is thin, a little shorter than a street
GARDEN_COH, GARDEN_WIN, GARDEN_FRAC, GARDEN_MIN = 0.3, 7, 0.45, 60   # cells; coherence below GARDEN_COH is stipple, not line work
MK_RATIO, MK_AREA, MK_R, KERB_MAX = 6.0, 200, 30, 8   # a face is a strip for kerb tests at this ratio and area, and no deeper than MK_R; a kerb is a wall at most KERB_MAX px thick
STRIP_MIN, STRIP_MAX = 7, 60   # px across: the narrowest and widest strip that can lie beyond a kerb
RAY_MAX, W_NARROW, PAVE_LEN, VOTE, PAVE_RATIO, INNER_MIN, SAME_STRIP = 90, 19, 40, 9, 1.5, 600, 40
W_PAVE, HATCH_RATIO, HATCH_GAP, HATCH_BLOCK = 40, 1.25, 3, 6   # a pavement against a block is at most W_PAVE wide; hatch is ink that closes over HATCH_GAP and still holds a disk of HATCH_BLOCK   # px: widest cross-section; narrow strip; a pavement lies this near an inner strip; shortest pavement piece
W_PLAIN = 13                    # a strip with no kerb pair round it, no wider than W_PLAIN (chord, px), is a pavement or plot sliver, not a carriageway
SHEET_CONSTS = ("INK_GREY", "INK_PAD", "GLYPH", "KERB_MAX", "RED_OD", "RULED_DEEP", "DECK_SOLID", "FAT")   # properties of the sheet's drawing, not of the method; the values above are 1882's, and
                                # `sheets.<id>.road.consts` in river_ref/windows.json overrides any of them (1882's are written out there too)
CELL = 32
AXES = ((0, 1), (1, 0), (1, 1), (1, -1))
BIG = 1 << 20


def disk(r):
    return np.hypot(*np.mgrid[-r:r + 1, -r:r + 1]) <= r


def next_dist(T, dy, dx, cap):
    """Steps (>= 1) from each pixel to the next True pixel of T along (dy, dx); `cap` where there is none."""
    h, w = T.shape
    r, c = np.arange(h)[:, None], np.arange(w)[None, :]
    if (dy, dx) == (0, 1):
        X = T
    elif (dy, dx) == (1, 0):
        X = T.T
    elif (dy, dx) == (1, 1):          # shear so that the diagonal is a column
        Y = np.zeros((h, w + h), bool)
        Y[r, c - r + h] = T
        X = Y.T
    else:
        Z = np.zeros((h, w + h), bool)
        Z[r, c + r] = T
        X = Z.T
    n, m = X.shape
    col = np.arange(m, dtype=np.int32)[None, :]
    nxt = np.minimum.accumulate(np.where(X, col, BIG)[:, ::-1], axis=1)[:, ::-1]
    nxt = np.concatenate([nxt[:, 1:], np.full((n, 1), BIG, np.int32)], 1)
    d = np.where(nxt >= BIG, cap, np.minimum(nxt - col, cap)).astype(np.int16)
    if (dy, dx) == (0, 1):
        return d
    if (dy, dx) == (1, 0):
        return d.T
    return d.T[r, c - r + h] if (dy, dx) == (1, 1) else d.T[r, c + r]


def both_ways(T, dy, dx, cap):
    """next_dist along (dy, dx) and along its opposite."""
    return next_dist(T, dy, dx, cap), next_dist(T[::-1, ::-1], dy, dx, cap)[::-1, ::-1]


def fat_region(dist, r0, extra=3):
    """Pixels inside the inscribed disk (grown by `extra`) of any pixel deeper than r0: open ground with its
    rim, which a distance threshold alone leaves as a band along the walls. `dist` is the EDT of free space."""
    deep = dist > r0
    out = np.zeros(dist.shape, bool)
    if not deep.any():
        return out
    ys, xs = np.nonzero(deep.any(1))[0], np.nonzero(deep.any(0))[0]
    pad = int(dist.max()) + extra + 2
    sl = (slice(max(0, ys[0] - pad), ys[-1] + pad + 1), slice(max(0, xs[0] - pad), xs[-1] + pad + 1))
    dist = dist[sl]
    cur = np.where(dist > r0, dist, -np.inf).astype(np.float32)
    for _ in range(int(dist.max()) + extra + 1):
        prv = cur
        cur = prv.copy()
        for dy, dx, c in ((0, 1, 1), (1, 0, 1), (0, -1, 1), (-1, 0, 1), (1, 1, 1.4143), (1, -1, 1.4143), (-1, 1, 1.4143), (-1, -1, 1.4143)):
            a = prv[max(dy, 0):prv.shape[0] + min(dy, 0), max(dx, 0):prv.shape[1] + min(dx, 0)] - c
            cur[max(-dy, 0):cur.shape[0] + min(-dy, 0), max(-dx, 0):cur.shape[1] + min(-dx, 0)] = np.maximum(
                cur[max(-dy, 0):cur.shape[0] + min(-dy, 0), max(-dx, 0):cur.shape[1] + min(-dx, 0)], a)
        if (cur == prv).all():
            break
    out[sl] = cur >= -extra
    return out


def strip_faces(face, dist):
    """Faces that can be the far side of a kerb: not compact, not specks, not open ground. Open ground (a blank
    block, a plaza) is cut with its rim first, so that the outline of a big blank block is not taken for a kerb."""
    face = face & ~fat_region(dist, MK_R)
    lab, n = nd.label(face)
    if not n:
        return face
    idx = np.arange(1, n + 1)
    area = nd.sum(face, lab, idx)
    mx = np.zeros(n)
    for i, t in enumerate(nd.find_objects(lab)):
        mx[i] = nd.distance_transform_edt(np.pad(lab[t] == i + 1, 1)).max()
    ok = (area >= MK_AREA) & (area / np.maximum(mx, 1) ** 2 >= MK_RATIO)
    return np.concatenate([[False], ok])[lab]


def run_layers(T, dy, dx):
    """Cross-section of T along (dy, dx), for every True pixel of T: the length (px) of its run, and how many
    strips lie beyond it each way, a strip being a run of T of STRIP_MIN..STRIP_MAX px across and the wall
    between neighbours at most KERB_MAX px thick (a kerb line; hatch or a block is thicker or has slits).
    Returns (length, n_before, n_after), zero outside T."""
    h, w = T.shape
    r, c = np.arange(h)[:, None], np.arange(w)[None, :]
    if (dy, dx) == (0, 1):
        X = T
    elif (dy, dx) == (1, 0):
        X = T.T
    elif (dy, dx) == (1, 1):
        Y = np.zeros((h, w + h), bool)
        Y[r, c - r + h] = T
        X = Y.T
    else:
        Z = np.zeros((h, w + h), bool)
        Z[r, c + r] = T
        X = Z.T
    n, m = X.shape
    step = float(np.hypot(dy, dx))
    flat = np.zeros((n, m + 2), bool)
    flat[:, 1:-1] = X
    flat = flat.ravel()
    ed = np.flatnonzero(np.diff(np.concatenate([[0], flat.view(np.int8), [0]])))
    st, en = ed[0::2], ed[1::2]
    ln = (en - st) * step
    row = st // (m + 2)
    k = len(st)
    if not k:
        z = np.zeros((h, w), np.float32)
        return z, z.astype(np.int8), z.astype(np.int8), z, z
    adj = np.zeros(k, bool)                     # adj[i]: run i follows run i - 1 across a wall thin enough for a kerb
    if k > 1:
        adj[1:] = (row[1:] == row[:-1]) & ((st[1:] - en[:-1]) * step <= KERB_MAX)
    isstrip = (ln >= STRIP_MIN) & (ln <= STRIP_MAX)
    before = adj & np.concatenate([[False], isstrip[:-1]])                       # the run before is a strip
    after = np.concatenate([adj[1:] & isstrip[1:], [False]])                     # the run after is a strip

    def chain(v):                                # consecutive True ending at each index
        cs = np.cumsum(v)
        return cs - np.maximum.accumulate(np.where(~v, cs, 0))
    nb = chain(before)
    na = chain(after[::-1])[::-1]
    wb = np.where(before, np.concatenate([[0], ln[:-1]]), 0)     # width of the neighbouring strip each way
    wa = np.where(after, np.concatenate([ln[1:], [0]]), 0)
    L, WB, WA = (np.zeros(flat.size, np.float32) for _ in range(3))
    NB, NA = np.zeros(flat.size, np.int8), np.zeros(flat.size, np.int8)
    L[flat] = np.repeat(ln, en - st)
    WB[flat] = np.repeat(wb, en - st)
    WA[flat] = np.repeat(wa, en - st)
    NB[flat] = np.repeat(np.minimum(nb, 3), en - st)
    NA[flat] = np.repeat(np.minimum(na, 3), en - st)
    out = []
    for a in (L, NB, NA, WB, WA):
        a = a.reshape(n, m + 2)[:, 1:-1]
        if (dy, dx) == (0, 1):
            pass
        elif (dy, dx) == (1, 0):
            a = a.T
        elif (dy, dx) == (1, 1):
            a = a.T[r, c - r + h]
        else:
            a = a.T[r, c + r]
        out.append(a)
    return out


def cross_sections(T):
    """For every pixel of T the chord of least length through it over four axes: its length, the number of
    strips beyond it before / after (the two sides of the chord), and the width of the nearest one each way;
    zero outside T and where the chord is longer than RAY_MAX."""
    best = np.full(T.shape, np.inf, np.float32)
    nb, na = np.zeros(T.shape, np.int8), np.zeros(T.shape, np.int8)
    wb, wa = np.zeros(T.shape, np.float32), np.zeros(T.shape, np.float32)
    for dy, dx in AXES:
        L, b, a, xb, xa = run_layers(T, dy, dx)
        sel = T & (L < best)
        best = np.where(sel, L, best)
        nb, na, wb, wa = np.where(sel, b, nb), np.where(sel, a, na), np.where(sel, xb, wb), np.where(sel, xa, wa)
    best[~T | (best > RAY_MAX)] = 0
    return best, nb, na, wb, wa


def pavement(road, mk, hatch):
    """Pixels of `road` that are pavement. Each pixel sits in a strip with a chord across it. Strips beyond it
    on both sides: the carriageway (`inner`), kept. Strips beyond on one side only: the pavement if the strip
    beyond is an inner one (a boulevard's lettered strip between kerbs is the road, the wide promenades either
    side are not), or if it is under W_NARROW and the strip beyond is PAVE_RATIO times wider (a street with
    a pavement, then its carriageway), or if a hatched block lies against its outer wall and it is no wider
    than HATCH_RATIO times the strip beyond (the pavement round a block; the carriageway is the strip not
    against one). A strip with a kerb beyond on neither side is a plain street, kept.
    Returns (pavement, inner)."""
    width, nb, na, wb, wa = cross_sections(mk)
    ok = mk & (width > 0)
    vote = lambda m: nd.uniform_filter(m.astype(np.float32), VOTE) > 0.5     # a chord's class flips pixel to pixel along a slanted street
    inner_t = ok & vote(ok & (nb >= 1) & (na >= 1))
    lab, n = nd.label(inner_t)                    # a tramway or a junction makes a blip of "inner"; a carriageway is long
    if n:
        inner_t = np.concatenate([[False], nd.sum(inner_t, lab, np.arange(1, n + 1)) >= INNER_MIN])[lab]
    one = ok & ~inner_t & vote(ok & ((nb >= 1) ^ (na >= 1)))
    beyond = np.where(nb >= 1, wb, wa)                                 # width of the strip across the kerb
    against = nd.distance_transform_edt(~hatch) <= width / 2 + 8        # a hatched block lies against the strip's outer wall
    smaller = one & (((width <= W_NARROW) & (width * PAVE_RATIO <= beyond)) |
                     (against & (width <= W_PAVE) & (width <= HATCH_RATIO * beyond)))
    plain = ok & ~inner_t & vote(ok & (width <= W_PLAIN))              # a strip too narrow for a carriageway, with no kerb pair round it
    inner, outer = inner_t & road, one & road
    pave = np.zeros_like(road)
    beside = np.zeros_like(road)
    if outer.any() and inner_t.any():
        # beside an inner strip: one lies across the kerb, so within a chord's width and a wall of this pixel, but not
        # along the same strip (geodesically close through T): a strip is not beside its own inner stretch
        near_e = nd.distance_transform_edt(~inner_t) <= width + KERB_MAX + 4
        same = nd.binary_dilation(inner_t, nd.generate_binary_structure(2, 1), iterations=SAME_STRIP, mask=mk)
        beside = near_e & ~same
    def pieces(cand):
        """Candidate pixels in pieces of at least PAVE_LEN px."""
        cand = nd.binary_opening(cand, np.ones((3, 3), bool))
        lab, n = nd.label(cand, np.ones((3, 3)))
        if not n:
            return np.zeros_like(cand)
        size = np.concatenate([[0], nd.sum(np.ones_like(lab), lab, np.arange(1, n + 1))])
        return (size[lab] >= PAVE_LEN) & cand
    pave = pieces(outer & (smaller | beside)) if outer.any() else pave
    pave |= pieces(plain & road)
    return pave & ~inner, inner_t


def road_tile(s, p, water, wall, ruled):
    """One tile of road, from float RGB `s`, local paper `p`, bool water / wall (outside the map) / ruled.
    Returns (road, deck, glyph, mk, hatch) at tile size: the road before shape selection, candidate bridge decks,
    the small ink components treated as lettering, the strip-shaped faces for the kerb test, and hatched ground.
    The caller keeps the interior (margins are context)."""
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
    cross = nd.generate_binary_structure(2, 1)
    face = nd.binary_dilation(nd.binary_opening(free, disk(R_FACE)), cross, iterations=R_FACE + 1, mask=free)
    # faint hatch: a deep face inside a ruled cell is a block, not a street (a street between hatched blocks is narrower)
    face &= ~nd.binary_dilation((dist > RULED_DEEP) & ruled, cross, iterations=RULED_DEEP + 2, mask=free)
    # open ground: the blank land outside the city limit (FAT), and a yard beside water (FAT_Q); cut with a margin
    beside = nd.distance_transform_edt(~water) <= dist + 20        # water is (nearly) the nearest wall
    cut = fat_region(dist, FAT) | fat_region(np.where(beside, dist, 0), FAT_Q, extra=YARD_EDGE)
    if cut.any():       # a union of disks leaves a rim along the field's walls (and in its corners): follow it along narrow ground
        cut = nd.binary_dilation(cut, cross, iterations=RIM, mask=face & (dist <= RIM_R))
    face &= ~cut
    # a red tramway is not an edge: road on both sides is joined across it
    redz = nd.binary_dilation(nd.binary_closing(red & ink, disk(5)), disk(2))
    face |= nd.binary_closing(face, disk(12)) & redz & ~wall
    # candidate bridge decks: dark hatched blobs beside water (kept only if road lies on two sides, or it is a pier, see add_bridges)
    near = nd.binary_dilation(water, disk(BRIDGE_REACH)) & ~water
    deck = nd.binary_opening(near & nd.binary_closing(grey < BRIDGE_INK, disk(3)) & ~wall, disk(3))   # a deck is a blob; a hatch strip along a bank is not
    if DECK_SOLID <= 1:
        lab, n = nd.label(deck, np.ones((3, 3)))
        for i, t in enumerate(nd.find_objects(lab)):
            m = lab[t] == i + 1
            if (grey[t][m] < SOLID_GREY).mean() > DECK_SOLID:
                deck[t] &= ~m
    hatch = nd.binary_opening(nd.binary_closing(ink, disk(HATCH_GAP)), disk(HATCH_BLOCK))      # lines 4-5 px apart fuse into a solid band; a line or two lines do not reach HATCH_BLOCK across
    return face, deck, glyph, strip_faces(face, dist), hatch


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


def add_bridges(road, deck, water=None):
    """A bridge is road: a candidate deck (a dark hatched blob beside water) that touches the selected road on
    two separate sides is added, so a street crosses its creek; so is a deck with water round most of its
    rim (a pier or landing stage, which the owner labels a bridge). Done after selection so that a deck
    cannot join a street to the blank lots beside it."""
    lab, n = nd.label(deck, np.ones((3, 3)))
    out = road.copy()
    for i, t in enumerate(nd.find_objects(lab)):
        t = (slice(max(0, t[0].start - 8), t[0].stop + 8), slice(max(0, t[1].start - 8), t[1].stop + 8))
        d = lab[t] == i + 1
        if not BRIDGE_MIN <= d.sum() <= BRIDGE_MAX:
            continue
        crossing = nd.label(nd.binary_dilation(d, disk(5)) & road[t])[1] >= 2
        rim = nd.binary_dilation(d, disk(4)) & ~d
        pier = water is not None and rim.any() and water[t][rim].mean() >= PIER_WATER
        if crossing or pier:
            out[t] |= nd.binary_fill_holes(nd.binary_closing(d, disk(4)))
    return out


def select(road, keep_min=SHAPE_MIN, net_area=NET_AREA):
    """Keep street-shaped components of a road mask: area / inscribed radius^2 (a long thin network is large,
    a block is not) at least keep_min, or an area that only a network reaches; a component with no 19 px core
    (inscribed radius <= R_CORE) must also reach NARROW_AREA. Returns the mask and stats."""
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
    ok &= (mx > R_CORE) | (area >= NARROW_AREA)
    stats = [{"id": int(i), "area": int(a), "inscribed": float(m), "ratio": float(r), "kept": bool(k)}
             for i, a, m, r, k in zip(idx, area, mx, ratio, ok)]
    return np.concatenate([[False], ok])[lab], stats


def blind(box, sheet):
    from view import touches
    return touches(box, sheet)


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
    sys.path.insert(0, str(REF))
    if a.window:
        bx, by, bw_, bh_ = next(v["box"] for v in spec["windows"] if v["sheet"] == a.sheet and v["id"] == a.window)
        if blind([bx, by, bw_, bh_], a.sheet):
            sys.exit(f"refused: {a.window} touches an unseen heldout window")
    Image.MAX_IMAGE_PIXELS = None
    rgb = np.asarray(Image.open(ROOT / pin["path"]).convert("RGB"))
    assert hashlib.sha256(rgb.tobytes()).hexdigest() == pin["rgb_sha256"], "native raster differs from native.json"
    base = ROOT / "work" / "image-processing" / "results" / sheet["map_id"]
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
    for k, v in rs.get("consts", {}).items():
        assert k in SHEET_CONSTS, f"{k} is not a sheet constant"
        globals()[k] = v
    globals()["MARGIN"] = 2 * FAT + 40       # tile context: open ground is cut from disks of radius FAT
    x, y, bw, bh = rs.get("neatline", sheet["neatline"])
    wall[y:y + bh, x:x + bw] = False
    pad = rs.get("furniture_pad", 0)
    for fx, fy, fw, fh in sheet["furniture"].values():
        wall[max(0, fy - pad):fy + fh + pad, max(0, fx - pad):fx + fw + pad] = True
    if a.window:        # a preview computes on nothing it cannot show: the unseen boxes are walls
        from view import blind_boxes
        for ux, uy, uw, uh in blind_boxes(a.sheet):
            wall[uy:uy + uh, ux:ux + uw] = True
        tiles = [(bx, by, bx + bw_, by + bh_)]
    else:
        tiles = [(x0, y0, min(w, x0 + TILE), min(h, y0 + TILE)) for y0 in range(0, h, TILE) for x0 in range(0, w, TILE)]
    road, deck, mk, hatch = (np.zeros((h, w), bool) for _ in range(4))
    for x0, y0, x1, y1 in tiles:
        c0, c1, r0, r1 = max(0, x0 - MARGIN), min(w, x1 + MARGIN), max(0, y0 - MARGIN), min(h, y1 + MARGIN)
        s = rgb[r0:r1, c0:c1].astype(np.float32)
        p = paper_at(paper, np.arange(r0, r1) + 0.5, np.arange(c0, c1) + 0.5)
        m, dk, _, k, ht = road_tile(s, p, water[r0:r1, c0:c1], wall[r0:r1, c0:c1], ruled[r0:r1, c0:c1])
        sl, si = (slice(y0, y1), slice(x0, x1)), (slice(y0 - r0, y1 - r0), slice(x0 - c0, x1 - c0))
        road[sl], deck[sl], mk[sl], hatch[sl] = m[si], dk[si], k[si], ht[si]
    del rgb, paper, cells, coh, ruled, wall, ruled_c, garden_c      # the tile stage is over; the rest is masks
    road &= ~garden
    del garden
    road, stats = select(road)
    # kerbs: pavement strips come out of the selected road; tiles overlap by KMARGIN so a strip is seen whole
    pave, inner = np.zeros((h, w), bool), np.zeros((h, w), bool)
    km = 120
    for x0, y0, x1, y1 in tiles:
        c0, c1, r0, r1 = max(0, x0 - km), min(w, x1 + km), max(0, y0 - km), min(h, y1 + km)
        pv, inn = pavement(road[r0:r1, c0:c1], mk[r0:r1, c0:c1], hatch[r0:r1, c0:c1])
        sl, si = (slice(y0, y1), slice(x0, x1)), (slice(y0 - r0, y1 - r0), slice(x0 - c0, x1 - c0))
        pave[sl], inner[sl] = pv[si], inn[si]
    road &= ~pave
    lab, n = nd.label(road)
    if n:
        road = np.concatenate([[False], nd.sum(road, lab, np.arange(1, n + 1)) >= SPECK])[lab]    # specks the cut leaves
    road = add_bridges(road, deck, water)
    print(len(stats), "components,", sum(s["kept"] for s in stats), "kept;", int(pave.sum()), "pavement px;", round(time.time() - t0), "s")
    if a.window:
        Image.fromarray((road[by:by + bh_, bx:bx + bw_] * 255).astype(np.uint8)).save(out / f"road-{a.window}.png")
        return
    Image.fromarray(road.astype(np.uint8) * 255).save(out / "road.png", compress_level=6)
    from view import blank
    pv = np.asarray(Image.open(ROOT / pin["path"]).convert("RGB"))[::8, ::8].astype(np.float32)
    mv = road[::8, ::8]
    pv[mv] = pv[mv] * 0.4 + np.array([255, 150, 0]) * 0.6
    Image.fromarray(blank(pv.astype(np.uint8), a.sheet, 8)).save(out / "road-preview.jpg", quality=85)
    run = {"sheet": a.sheet, "native_sha256": pin["rgb_sha256"], "sheet_consts": {k: globals()[k] for k in SHEET_CONSTS},
           "settings": {k: globals()[k] for k in ("INK_GREY", "INK_PAD", "GLYPH", "R_FACE", "R_CORE", "FAT", "FAT_Q", "YARD_EDGE", "RIM", "RIM_R", "RULED_DEEP", "RED_OD", "BRIDGE_REACH", "BRIDGE_INK", "BRIDGE_MIN", "BRIDGE_MAX", "PIER_WATER", "SHAPE_MIN", "NET_AREA", "NARROW_AREA", "SPECK", "LANE_R", "LANE_RATIO", "GARDEN_COH", "GARDEN_WIN", "GARDEN_FRAC", "GARDEN_MIN", "MK_RATIO", "MK_AREA", "RAY_MAX", "W_NARROW", "PAVE_LEN", "VOTE", "PAVE_RATIO", "W_PAVE", "HATCH_RATIO", "HATCH_GAP", "HATCH_BLOCK", "INNER_MIN", "SAME_STRIP", "STRIP_MIN", "STRIP_MAX", "KERB_MAX", "MK_R")},
           "road_px": int(road.sum()), "pavement_px": int(pave.sum()), "inner_px": int(inner.sum()), "components": len(stats), "kept": sum(s["kept"] for s in stats),
           "seconds": round(time.time() - t0, 1)}
    (out / "road-run.json").write_text(json.dumps(run, indent=1) + "\n")
    print(json.dumps(run, indent=1))


def finish(img, water=None):
    """The whole pass on one small synthetic image (paper-coloured, ink dark): tile stage, selection, kerbs, bridges."""
    n, m, _ = img.shape
    water = np.zeros((n, m), bool) if water is None else water
    p = np.tile(np.array([220.0, 208.0, 185.0], np.float32), (n, m, 1))
    face, deck, glyph, mk, hatch = road_tile(img.astype(np.float32), p, water, np.zeros((n, m), bool), np.zeros((n, m), bool))
    road, _ = select(face)
    pave, _ = pavement(road, mk, hatch)
    road &= ~pave
    return add_bridges(road, deck, water), glyph, face


def self_check():
    """Synthetic sheets: each new rule has a case that fails when its constant is changed."""
    paper = np.array([220.0, 208.0, 185.0])
    black = np.array([40.0, 38.0, 36.0])

    def canvas(n, m):
        return np.tile(paper, (n, m, 1))

    def hatch(img, y0, y1, x0, x1):
        img[y0:y1:5, x0:x1] = paper * 0.7

    def hline(img, y0, x0, x1, t=2):
        img[y0:y0 + t, x0:x1] = black

    def vline(img, x0, y0, y1, t=2):
        img[y0:y1, x0:x0 + t] = black

    # 1. street y 280-320 with a pavement strip and kerb line, a closed blank block, a ruled block, a letter, a tramway, a creek with a deck
    n, m = 640, 900
    img = canvas(n, m)
    hline(img, 278, 0, m)
    hline(img, 321, 0, m)
    hline(img, 292, 0, m, 1)
    hline(img, 100, 100, 500)
    hline(img, 277, 100, 500)
    vline(img, 100, 100, 279)
    vline(img, 500, 100, 279)
    hatch(img, 330, 600, 60, 560)
    img[300:316, 120:136] = black
    img[0:n, 400:403] = (190, 90, 60)
    water = np.zeros((n, m), bool)
    water[250:380, 560:600] = True
    water[296:318, 560:600] = False
    img[296:318:3, 560:600] = black
    img[296:318, 560:562] = black
    road, glyph, face = finish(img, water)
    assert glyph[300:316, 120:136].any(), "a letter is not a wall"
    assert road[305, 300] and road[305, 128], "carriageway, including under the letter"
    assert not road[285, 300], "the pavement strip between block line and kerb is land"
    assert road[305, 401], "road is joined across a red tramway"
    assert not road[400, 300], "hatch is not street"
    assert not road[200, 300], "the closed blank block is compact, the street is not"
    assert road[305, 575], "bridge joins road on both sides"
    # 2. a boulevard: wide promenade, kerb, a 14 px lettered carriageway, kerb, wide promenade; hatch beyond the outlines
    img = canvas(240, 1700)
    hatch(img, 0, 40, 0, 1700)
    hatch(img, 142, 240, 0, 1700)
    for y in (40, 82, 98, 140):
        hline(img, y, 0, 1700, 1 if y in (82, 98) else 2)
    road, _, _ = finish(img)
    assert road[91, 800], "the strip between two kerbs is the carriageway, even 14 px wide"
    assert not road[60, 800] and not road[120, 800], "the wide promenades beside an inner strip are land"
    # 2b. a block, a 20 px pavement against it, a kerb, a 20 px carriageway, a thick line, then open ground: of two strips of
    #     a width the one against the hatch is the pavement
    img = canvas(300, 1700)
    hatch(img, 0, 40, 0, 1700)
    hline(img, 40, 0, 1700)
    hline(img, 62, 0, 1700, 1)
    hline(img, 83, 0, 1700, 3)
    road, _, _ = finish(img)
    assert road[73, 800] and not road[52, 800], "the strip against a block is the pavement, the other the carriageway"
    # 3. a 14 px lane joining a street is road; an isolated 14 px plot is not
    img = canvas(500, 1800)
    hatch(img, 0, 120, 0, 1800)
    hatch(img, 160, 500, 0, 1800)
    hline(img, 120, 0, 1800)
    hline(img, 160, 0, 500)
    hline(img, 160, 522, 698)
    hline(img, 160, 718, 1800)
    for x in (500, 520, 698, 714):
        vline(img, x, 160, 500)
    hline(img, 200, 900, 1700)
    hline(img, 215, 900, 1700)
    vline(img, 900, 200, 217)
    vline(img, 1700, 200, 217)
    img[160:500, 502:518] = paper                                  # the lane
    img[160:500, 700:714] = paper                                  # a 14 px strip between block lines with red tramway dashes across it:
    for y in range(190, 500, 30):                                  # pavement or plot sliver, not a carriageway (W_PLAIN), dashes or not
        img[y:y + 8, 700:714] = (190, 90, 60)
    road, _, _ = finish(img)
    assert road[140, 900] and road[300, 510], "a narrow lane joining a street is road"
    assert not road[208, 1300], "an isolated narrow plot is not"
    assert not road[300, 707] and not road[400, 707], "a plain strip of 12 px, even cut by dashes and joined to a street, is a pavement or sliver"
    # 4. beside water: a quay strip of 30 px is road, a blank yard 90 px deep is not
    img = canvas(400, 1300)
    hatch(img, 0, 100, 0, 1300)
    hline(img, 100, 0, 1300)
    water = np.zeros((400, 1300), bool)
    water[190:, :650] = True
    water[130:, 650:] = True
    road, _, _ = finish(img, water)
    assert road[115, 1000], "the quay road between a street line and the water"
    assert not road[150, 300], "a blank yard beside water is open ground"
    # 5. a pier: a hatched deck with water on three sides is road, a hatched shed on the bank is not
    img = canvas(300, 400)
    water = np.zeros((300, 400), bool)
    water[:, 150:] = True
    water[100:140, 100:] = False
    img[100:140:3, 100:250] = black
    img[100:140, 100:102] = black
    water[:, 150:] = True
    water[100:140, 100:200] = False                                  # the deck sits in the water, land to its left
    img[200:240:3, 20:70] = black
    road, _, _ = finish(img, water)
    assert road[120, 190], "a deck with water on three sides is a pier, which the owner labels a bridge"
    assert not road[220, 40], "a hatched shed away from the water is not"
    # 5b. bold lettering in the water is not a pier: a solid black blob with water all round it is road only when DECK_SOLID is off
    img = canvas(300, 400)
    water = np.zeros((300, 400), bool)
    water[:, 150:] = True
    water[100:140, 100:200] = False
    img[100:140, 100:200] = black
    global DECK_SOLID
    keep = DECK_SOLID
    try:
        DECK_SOLID = 1.01
        road, _, _ = finish(img, water)
        assert road[120, 190], "with the solidity test off a deck with water on three sides is a pier"
        DECK_SOLID = 0.65
        road, _, _ = finish(img, water)
        assert not road[120, 190], "a solid black blob is lettering, not a pier"
    finally:
        DECK_SOLID = keep
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
