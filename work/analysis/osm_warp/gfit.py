"""Global affine by differential evolution on the tabulated cell surfaces (no local-minimum trap, aliases excluded by +-112 bound)."""
from run_fit import *
from scipy.optimize import differential_evolution
from scipy.ndimage import map_coordinates as mc
def load_surfaces():
    z = pickle.load(open(SP / 'surfaces.pkl', 'rb')); return z['g'], z['cells']
def affine_de(g, cells, use, seed=0, bound_t=200, bound_m=0.03, verbose=False):
    cl = [c for c in use if c in cells]
    cen = np.array([cells[c]['cen'] for c in cl]) - C0
    S = np.array([cells[c]['S'] for c in cl]); n = np.array([cells[c]['n'] for c in cl], float)
    step = g[1] - g[0]; g0 = g[0]
    def pred(v):
        return v[:2] + cen @ v[2:].reshape(2, 2).T
    def f(v):
        p = pred(v); ix = (p[:, 0] - g0) / step; iy = (p[:, 1] - g0) / step
        ok = (ix >= 0) & (ix <= len(g) - 1) & (iy >= 0) & (iy <= len(g) - 1)
        kk = np.arange(len(cl), dtype=float)
        val = mc(S, [kk, np.clip(iy, 0, len(g) - 1), np.clip(ix, 0, len(g) - 1)], order=1)
        return -float((n * val * ok).sum() / n.sum())
    bounds = [(-bound_t, bound_t)] * 2 + [(-bound_m, bound_m)] * 4
    r = differential_evolution(f, bounds, seed=seed, popsize=40, maxiter=400, tol=1e-9, mutation=(0.4, 1.0), recombination=0.8, polish=False)
    if verbose: print('DE', r.x, -r.fun, 'null(zero shift)', -f(np.zeros(6)))
    return r.x, -r.fun
if __name__ == '__main__':
    g, cells = load_surfaces()
    best = []
    for seed in range(4):
        v, s = affine_de(g, cells, list(cells), seed=seed, verbose=True); best.append((s, v))
    print(sorted(best, key=lambda t: -t[0])[0])
