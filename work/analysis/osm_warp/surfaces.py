"""Per-cell score surfaces S_c(shift) = mean Q (blur sigma 2 q px) over +-112 px in 8 px steps. A cell's surface uses only
its own samples, so any subset of cells can be fitted from the cache without leakage."""
from run_fit import *
GR = 208; GS = 8
def main():
    d, _ = load()
    g = np.arange(-GR, GR + 1, GS, float); GX, GY = np.meshgrid(g, g); GX = GX.ravel(); GY = GY.ravel()
    out = {}
    cells = sorted(set(zip(d['cy'], d['cx'])))
    for k, c in enumerate(cells):
        idx = np.where((d['cy'] == c[0]) & (d['cx'] == c[1]))[0]
        if len(idx) < NMIN: continue
        P = Pre(d['x'][idx], d['y'][idx], d['ang'][idx], 2)
        sc = np.zeros(len(GX))
        for i in range(0, len(GX), 100):
            sc[i:i + 100] = P.eval(GX[i:i + 100][None, :] + 0 * idx[:, None], GY[i:i + 100][None, :] + 0 * idx[:, None]).mean(0)
        out[c] = dict(n=len(idx), S=sc.reshape(len(g), len(g)).astype(np.float32), cen=(float(d['x'][idx].mean()), float(d['y'][idx].mean())))
        print(k, len(cells), c, round(float(sc.max()), 3), flush=True)
    pickle.dump(dict(g=g, cells=out), open(SP / 'surfaces.pkl', 'wb'))
if __name__ == '__main__': main()
