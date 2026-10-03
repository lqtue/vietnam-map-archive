"""Region-growing per-cell translation tracking (avoids lattice aliasing: each cell searches only +-RNG around
what its already-fitted neighbours predict), then affine (weighted lstsq) + thin-plate residual."""
from fit import *
from run_fit import load, NMIN, SUP_MIN
import heapq
RNG = 56
def cell_fit(d, P1, P0, idx, centre, rng, step):
    dx, dy, pk, md, sc = search(P1, idx, centre=centre, rng=rng, step=step)
    dx, dy, pk, _ = refine(P1, idx, (dx, dy))
    sub0 = Pre(d['x'][idx], d['y'][idx], d['ang'][idx], 0)
    sup = int((sub0.eval(np.full(len(idx), dx), np.full(len(idx), dy)) > 0.3).sum())
    return dict(d=np.array([dx, dy]), pk=pk, md=md, sup=sup, n=len(idx))
def find_seed(d, P1, P0, cells_idx):
    """strong cells: coarse +-112 search; seed = adjacent strong pair with consistent shifts and the most support."""
    strong = {}
    for c, idx in cells_idx.items():
        r = cell_fit(d, P1, P0, idx, (0., 0.), 112, 8)
        if r['sup'] >= 25 and r['pk'] > 3 * r['md']: strong[c] = r
    best = None
    for c, r in strong.items():
        for dy_ in (-1, 0, 1):
            for dx_ in (-1, 0, 1):
                c2 = (c[0] + dy_, c[1] + dx_)
                if c2 != c and c2 in strong and np.hypot(*(strong[c2]['d'] - r['d'])) <= 16:
                    tot = r['sup'] + strong[c2]['sup']
                    if best is None or tot > best[0]: best = (tot, c, c2)
    return best, strong
def track(d, P1, P0, train_mask, verbose=False):
    cells_idx = {}
    cy, cx = d['cy'][train_mask], d['cx'][train_mask]; ti = np.where(train_mask)[0]
    for c in set(zip(cy, cx)):
        idx = ti[(cy == c[0]) & (cx == c[1])]
        if len(idx) >= NMIN: cells_idx[(int(c[0]), int(c[1]))] = idx
    best, strong = find_seed(d, P1, P0, cells_idx)
    if best is None: raise RuntimeError('no seed')
    _, s1, s2 = best
    fitted = {s1: strong[s1], s2: strong[s2]}
    if verbose: print('seed', s1, strong[s1]['d'], s2, strong[s2]['d'], 'strong cells', len(strong))
    tried = set(fitted); rejected = {}
    heap = []
    def push_neighbours(c):
        for dy_ in (-1, 0, 1):
            for dx_ in (-1, 0, 1):
                n = (c[0] + dy_, c[1] + dx_)
                if n in cells_idx and n not in tried:
                    heapq.heappush(heap, (np.hypot(n[0] - s1[0], n[1] - s1[1]), n)); tried.add(n)
    push_neighbours(s1); push_neighbours(s2)
    while heap:
        _, c = heapq.heappop(heap)
        nb = [fitted[(c[0] + a, c[1] + b)] for a in (-1, 0, 1) for b in (-1, 0, 1) if (c[0] + a, c[1] + b) in fitted]
        if not nb: continue
        w = np.array([r['sup'] for r in nb], float); pred = (np.array([r['d'] for r in nb]) * w[:, None]).sum(0) / w.sum()
        r = cell_fit(d, P1, P0, cells_idx[c], tuple(pred), RNG, 4)
        r['pred'] = pred
        if r['sup'] >= SUP_MIN and r['pk'] > 2 * r['md']:
            fitted[c] = r; push_neighbours(c)
        else: rejected[c] = r
    for c, r in fitted.items(): r['cen'] = np.array([d['x'][cells_idx[c]].mean(), d['y'][cells_idx[c]].mean()]); r['idx'] = cells_idx[c]
    if verbose: print('fitted cells', len(fitted), 'rejected', len(rejected), 'of', len(cells_idx))
    return fitted, rejected, cells_idx
def build_models(fitted, smooth=(0.01, 0.1, 1.0)):
    cs = list(fitted); cen = np.array([fitted[c]['cen'] for c in cs]); T = np.array([fitted[c]['d'] for c in cs]); w = np.array([fitted[c]['sup'] for c in cs], float)
    keep = np.ones(len(cs), bool)
    for it in range(3):
        v = lstsq_affine(cen[keep, 0], cen[keep, 1], T[keep, 0], T[keep, 1], w[keep])
        t, M = v[:2], v[2:].reshape(2, 2)
        pred = t + (cen - C0) @ M.T; err = np.hypot(*(T - pred).T)
        keep = err < max(20, 2.5 * np.median(err[keep]))
    aff = Warp(t, M)
    tr_ = Warp(np.average(T, axis=0, weights=w))
    models = {'translation': tr_, 'affine': aff}
    rr = T - (t + (cen - C0) @ M.T)
    for s in smooth:
        tps = RBFInterpolator(cen / 1000, rr, kernel='thin_plate_spline', smoothing=s)
        models[f'grid_s{s:g}'] = Warp(t, M, lambda xy, tps=tps: np.clip(tps(xy / 1000), -64, 64))
    return models, dict(cen=cen, T=T, w=w, keep=keep, aff=aff, resid=rr)
