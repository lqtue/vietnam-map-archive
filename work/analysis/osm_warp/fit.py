"""Piecewise warp: global affine + regularised grid residual, fitted on the raw-evidence score Q (q_maps.py)."""
from fastq import *
from scipy.optimize import minimize
from scipy.interpolate import RBFInterpolator
CELL = 512
C0 = np.array([WD / 2, H / 2])
def search(P, idx, centre=(0., 0.), rng=96, step=8, base=None):
    """exhaustive translation search for samples idx. base = per-sample displacement already applied (n,2).
    returns best (dx,dy) RELATIVE to base, peak mean score, median of grid, support count at best."""
    g = np.arange(-rng, rng + 1, step, float)
    GX, GY = np.meshgrid(g + centre[0], g + centre[1])
    GX, GY = GX.ravel(), GY.ravel()
    sub = Pre(P.x[idx], P.y[idx], P.ang[idx], P.sigma)
    bx = 0 if base is None else base[idx, 0][:, None]; by = 0 if base is None else base[idx, 1][:, None]
    sc = np.zeros(len(GX))
    for i in range(0, len(GX), 125):
        v = sub.eval(bx + GX[i:i + 125][None, :], by + GY[i:i + 125][None, :])
        sc[i:i + 125] = v.mean(0)
    j = int(sc.argmax())
    return GX[j], GY[j], sc[j], float(np.median(sc)), sc
def refine(P, idx, d0, base=None, rng=6, step=2):
    return search(P, idx, centre=d0, rng=rng, step=step, base=base)[:4]
def cell_ids(x, y):
    return (y // CELL).astype(int), (x // CELL).astype(int)
class Warp:
    """d(p) = affine(p) + tps(p); apply(x,y) -> displaced source px."""
    def __init__(self, t=(0, 0), M=np.zeros((2, 2)), tps=None):
        self.t = np.array(t, float); self.M = np.array(M, float); self.tps = tps
    def disp(self, x, y):
        p = np.column_stack([x, y]) - C0
        d = self.t + p @ self.M.T
        if self.tps is not None: d = d + self.tps(np.column_stack([x, y]))
        return d
    def affine_only(self): return Warp(self.t, self.M)
    def apply(self, x, y):
        d = self.disp(x, y); return x + d[:, 0], y + d[:, 1]
def fit_affine(P, idx, v0, obj_sigma, scale=None, maxiter=500):
    """maximise mean Q (blur obj_sigma) over samples idx; Nelder-Mead from v0 = (tx,ty,M00,M01,M10,M11)."""
    xs, ys = P.x[idx], P.y[idx]
    sub = Pre(xs, ys, P.ang[idx], obj_sigma)
    p = np.column_stack([xs, ys]) - C0
    def f(v):
        d = v[:2] + p @ v[2:].reshape(2, 2).T
        return -float(sub.eval(d[:, 0], d[:, 1]).mean())
    if scale is None: scale = np.array([8, 8, 2e-3, 2e-3, 2e-3, 2e-3]) if obj_sigma >= 2 else np.array([4, 4, 5e-4, 5e-4, 5e-4, 5e-4])
    v = _nm(f, np.asarray(v0, float), scale, maxiter)
    return Warp(v[:2], v[2:].reshape(2, 2)), -f(v)
def _nm(f, v0, scale, maxiter=500):
    # simplex Nelder-Mead with an explicit initial simplex (scales differ by 4 orders of magnitude)
    sim = np.vstack([v0] + [v0 + np.eye(6)[i] * scale[i] for i in range(6)])
    r = minimize(f, v0, method='Nelder-Mead', options={'initial_simplex': sim, 'xatol': 1e-4, 'fatol': 1e-6, 'maxiter': maxiter})
    return r.x
def lstsq_affine(cx, cy, tx, ty, w):
    A = np.column_stack([np.ones(len(cx)), cx - C0[0], cy - C0[1]])
    sw = np.sqrt(w)[:, None]
    bx, *_ = np.linalg.lstsq(A * sw, tx * sw[:, 0], rcond=None); by, *_ = np.linalg.lstsq(A * sw, ty * sw[:, 0], rcond=None)
    return np.array([bx[0], by[0], bx[1], bx[2], by[1], by[2]])    # t, M row-major (dx = M00 px + M01 py)

def rigid_search(x, y, ang, nsub=5000, sig=3, seed=1, trange=192, tstep=16, ths=np.arange(-1.5, 2.51, 0.25)):
    """coarse (theta about C0, tx, ty) search on broad-blurred Q; returns best (tx,ty,theta_deg), score, median."""
    rng = np.random.default_rng(seed)
    sel = rng.choice(len(x), min(nsub, len(x)), replace=False)
    P = Pre(x[sel], y[sel], ang[sel], sig)
    p = np.column_stack([x[sel], y[sel]]) - C0
    g = np.arange(-trange, trange + 1, tstep, float); GX, GY = np.meshgrid(g, g); GX = GX.ravel(); GY = GY.ravel()
    best = (-1, 0, 0, 0); allsc = []
    for th in np.radians(ths):
        R = np.array([[math.cos(th) - 1, -math.sin(th)], [math.sin(th), math.cos(th) - 1]]); rot = p @ R.T
        sc = np.zeros(len(GX))
        for i in range(0, len(GX), 200):
            sc[i:i + 200] = P.eval(rot[:, 0:1] + GX[i:i + 200][None, :], rot[:, 1:2] + GY[i:i + 200][None, :]).mean(0)
        allsc.append(sc); j = int(sc.argmax())
        if sc[j] > best[0]: best = (sc[j], GX[j], GY[j], math.degrees(th))
    return best[1], best[2], best[3], best[0], float(np.median(np.concatenate(allsc)))
