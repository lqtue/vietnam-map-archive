"""Global rigid+shift search (tx,ty,theta about the sheet centre) on broad-blurred Q, wide range."""
from run_fit import *
import itertools
d, _ = load()
rng = np.random.default_rng(1)
sel = rng.choice(len(d['x']), 7000, replace=False)
x, y, a = d['x'][sel], d['y'][sel], d['ang'][sel]
sig = int(sys.argv[1]) if len(sys.argv) > 1 else 3
P = Pre(x, y, a, sig)
p = np.column_stack([x, y]) - C0
g = np.arange(-240, 241, 16, float)
res = []
for th in np.radians(np.arange(-2.0, 2.01, 0.25)):
    R = np.array([[math.cos(th) - 1, -math.sin(th)], [math.sin(th), math.cos(th) - 1]])
    rot = p @ R.T          # displacement from rotation about C0
    GX, GY = np.meshgrid(g, g); GX = GX.ravel(); GY = GY.ravel()
    sc = np.zeros(len(GX))
    for i in range(0, len(GX), 200):
        v = P.eval(rot[:, 0:1] + GX[i:i+200][None, :], rot[:, 1:2] + GY[i:i+200][None, :])
        sc[i:i+200] = v.mean(0)
    res.append((np.degrees(th), sc.reshape(len(g), len(g))))
    j = sc.argmax(); print(f'theta {np.degrees(th):5.2f} best {sc.max():.4f} at ({GX[j]:.0f},{GY[j]:.0f}) median {np.median(sc):.4f}', flush=True)
np.save(SP / f'glob_surface_s{sig}.npy', np.array([r[1] for r in res]))
