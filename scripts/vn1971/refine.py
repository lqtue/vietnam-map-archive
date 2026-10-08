"""refine.py [NN ...]: pull each sheet's GCPs onto the printed grid lines the scan actually shows.

go.py fits a regular lattice and rotates it by one angle found from the vertical lines, so a scan whose
horizontal lines are tilted differently (shear from scanning in halves, or paper) ends up with GCPs
that are on a perfect lattice and off the real lines: up to 50 px (~300 m) across a sheet. linefit.py
measures it. Here, per GCP, the offset to the nearest printed vertical line (in x) and horizontal line
(in y) is measured on the scan; an affine model of those offsets over the sheet is fitted with
outliers dropped and applied. Three passes with a shrinking window. Originals: grid_before_refine/.
Pixels only; lon/lat (the grid values) never change."""
import glob, json, os, shutil, sys
import numpy as np
from PIL import Image
from common import WORK
Image.MAX_IMAGE_PIXELS = None


def measure(im, pts, win):
    out = []
    H, W = im.shape
    for x, y in pts:
        x, y = int(round(x)), int(round(y))
        if not (win + 160 < x < W - win - 160 and win + 160 < y < H - win - 160):
            out.append((np.nan, np.nan)); continue
        cx = np.r_[im[y-150:y-30, x-win:x+win+1], im[y+30:y+150, x-win:x+win+1]].astype(np.float32).mean(0)
        cy = np.c_[im[y-win:y+win+1, x-150:x-30], im[y-win:y+win+1, x+30:x+150]].astype(np.float32).mean(1)
        out.append((np.argmin(cx) - win, np.argmin(cy) - win))
    return np.array(out, float)


def affine_fit(P, D):
    ok = ~np.isnan(D)
    A = np.c_[P, np.ones(len(P))]
    for _ in range(4):
        c, *_ = np.linalg.lstsq(A[ok], D[ok], rcond=None)
        r = D - A @ c
        mad = np.nanmedian(np.abs(r[ok] - np.median(r[ok]))) or 1.0
        ok = ok & (np.abs(r) < max(3 * 1.4826 * mad, 3))
    return c


def refine(n):
    f = WORK + f'grid/gcp{n}.json'
    bak = WORK + f'grid_before_refine/gcp{n}.json'
    os.makedirs(WORK + 'grid_before_refine', exist_ok=True)
    if not os.path.exists(bak):
        shutil.copy(f, bak)
    g = json.load(open(bak))  # always from the original, so a second run changes nothing
    im = np.asarray(Image.open(WORK + f'up/{n[:2]}.jpg').convert('L'))
    P = np.array([p['px'] for p in g], float)
    total = np.zeros_like(P)
    for win in (100, 60, 40):
        cur = P + total
        m = measure(im, cur, win)
        if np.isnan(m).all():
            break
        total[:, 0] += np.c_[cur, np.ones(len(cur))] @ affine_fit(cur, m[:, 0])
        total[:, 1] += np.c_[cur, np.ones(len(cur))] @ affine_fit(cur, m[:, 1])
    for p, q in zip(g, P + total):
        p['px'] = [round(float(q[0]), 1), round(float(q[1]), 1)]
    json.dump(g, open(f, 'w'))
    return np.abs(total).max(0)


if __name__ == '__main__':
    for n in sys.argv[1:] or [os.path.basename(f)[3:-5] for f in sorted(glob.glob(WORK + 'grid/gcp*.json'))]:
        mx = refine(n)
        print(f'{n}: moved up to {mx[0]:.0f} px in x, {mx[1]:.0f} px in y')
