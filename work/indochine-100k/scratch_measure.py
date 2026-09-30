import sys, os, hashlib, pickle
sys.path.insert(0, "scripts")
sys.path.insert(0, "work/ocr/scripts")

CACHE = "work/indochine-100k/.fetch_cache"
os.makedirs(CACHE, exist_ok=True)

import tonkin_thinframe as TF
tg = TF.tg
T = tg.T

_orig = T.fetch_crop_level0
def cached_fetch(base, x, y, w, h, size, stats=None):
    key = hashlib.sha1(f"{base}|{x}|{y}|{w}|{h}|{size}".encode()).hexdigest()
    path = os.path.join(CACHE, key + ".pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            img, st = pickle.load(f)
        if stats is not None:
            stats.update(st)
        return img
    st = {}
    img = _orig(base, x, y, w, h, size, stats=st)
    with open(path, "wb") as f:
        pickle.dump((img, st), f)
    if stats is not None:
        stats.update(st)
    return img
T.fetch_crop_level0 = cached_fetch

# widen the search for the inner neatline: it sits further inside the thick
# decorative frame on this series than on Tonkin's
tg.ACROSS = (190, 300)
tg.MAXIN = 250

import numpy as np

def side_line_loose(d, ref, verbose=False):
    ps = TF.patches(d)
    lo, hi = int(ref) - TF.NEAR, int(ref) + TF.NEAR
    consensus = lo + int(np.argmax(np.mean([p for _, p in ps], axis=0)[lo:hi]))
    pick = lambda prof, c, w: max(0, int(c - w)) + int(np.argmax(prof[max(0, int(c - w)):int(c + w) + 1]))
    pts = [(mid, float(pick(prof, consensus, 12))) for mid, prof in ps]
    f = tg.fit(pts)
    if f is None:
        return None, "would not fit"
    m, c, *_ = f
    pts = [(mid, float(pick(prof, m * mid + c, 8))) for mid, prof in ps]
    f = tg.fit(pts)
    m, c, res, keep, tot = f
    if verbose:
        print(f"      consensus {consensus}  peaks {[int(p[1]) for p in pts]}")
    if res > 15.0:  # loosened from 3.0 for this diagnostic pass
        return None, f"thick line residual {res:.1f}px"
    anchor = float(np.mean([mid for mid, _ in ps]))
    ref2 = m * anchor + c
    grid = np.arange(d.shape[1], dtype=float)
    avg = np.mean([np.interp(grid, grid + (ref2 - (m * mid + c)), prof) for mid, prof in ps], axis=0)
    r, how = tg.rim_in(avg, int(round(ref2)), "inner"), ""
    if r is None:
        r, how = TF.rim_relaxed(avg, int(round(ref2))), " (relaxed floor)"
    if r is None:
        return None, "no rim found inside the thick line"
    return {"m": m, "c": c + (r - ref2), "res": res, "kept": keep, "found": tot,
            "offset": r - ref2, "how": how}, None

TF.side_line = side_line_loose

sheets = [
    ("f352f638-c8e5-4480-ba1b-2bf81043b1d5", "Ha Tinh Ouest 104W"),
    ("c19c68a6-5ce8-4b74-86ec-9272f0c98a21", "Phan Rang Est 214E"),
]
for mid, name in sheets:
    print(f"\n=== {name} ({mid}) ===")
    got, err, (W, H) = TF.measure(mid, verbose=True)
    print(f"  {W}x{H}")
    if err:
        print(f"  FAILED: {err}")
        continue
    for k, v in got["corners"].items():
        print(f"  {k}: {v[0]:.1f}, {v[1]:.1f} px")
    print(f"  rotation (tan): {got['rotation']:.5f}")
