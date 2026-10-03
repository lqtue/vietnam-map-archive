from run_fit import *
d, allS = load()
n = len(d['x'])
P1 = Pre(d['x'], d['y'], d['ang'], 1); P0 = Pre(d['x'], d['y'], d['ang'], 0)
ink = np.load(SP / 'ink_q.npy')
def metrics(Pe, x, y, idx):
    sub = Pre(x[idx], y[idx], d['ang'][idx], 0)
    q = sub.eval(np.zeros(len(idx)), np.zeros(len(idx)))
    xi = np.clip((x[idx] / Q).astype(int), 0, WQ - 1); yi = np.clip((y[idx] / Q).astype(int), 0, HQ - 1)
    return dict(meanQ=float(q.mean()), hit=float((q > 0.3).mean()), ink=float(ink[yi, xi].mean()), n=len(idx))
def evaluate(models, test_mask):
    idx = np.where(test_mask)[0]; out = {'unwarped': metrics(None, d['x'], d['y'], idx)}
    for k, m in models.items():
        x2, y2 = m.apply(d['x'][idx], d['y'][idx]); xx = d['x'].copy(); yy = d['y'].copy(); xx[idx] = x2; yy[idx] = y2
        out[k] = metrics(None, xx, yy, idx)
    return out
if __name__ == '__main__':
    t0 = time.time()
    smooth = (0.01, 0.1, 1.0)
    schemes = {}
    cy, cx = d['cy'], d['cx']
    schemes['checker'] = [((cy + cx) % 2 == 0), ((cy + cx) % 2 == 1)]
    schemes['halves_x'] = [d['x'] < WD / 2, d['x'] >= WD / 2]
    allres = {}
    for name, (A, B) in schemes.items():
        for tr, te, lab in ((A, B, 'A->B'), (B, A, 'B->A')):
            models, info = fit_model(d, P1, P0, tr, smooth, verbose=True)
            r = evaluate(models, te); allres[(name, lab)] = r
            print(name, lab, 'train cells reliable', len(info['reliable']), 'res cells', len(info['res']), 'aff t', np.round(info['aff'].t, 1), 'M', np.round(info['aff'].M, 4).ravel(), f'{time.time()-t0:.0f}s')
            for k, v in r.items(): print(f"   {k:14s} meanQ {v['meanQ']:.4f} hit {v['hit']*100:5.1f}% inkhit {v['ink']*100:5.1f}%  n={v['n']}")
    pickle.dump(allres, open(SP / 'cv_res.pkl', 'wb'))
