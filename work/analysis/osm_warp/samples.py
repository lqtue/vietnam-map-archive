"""Resample the OSM centrelines (source px) every 8 px with local direction, way id and 100 px piece id.
Keeps only samples that are inside the neatline, outside furniture, off water, and >= KERNEL_PAD+SHIFT_MAX
from every seen:false window (so no search or lookup can reach a blanked area)."""
from common import *
from scipy.ndimage import binary_dilation, distance_transform_edt
STEP = 8
def main():
    g = json.load(open(STREETS))
    X=[];Y=[];A=[];WAY=[];PIECE=[];CLS=[]
    piece = 0
    for wi, f in enumerate(g['features']):
        gm = f['geometry']; hw = f['properties']['highway']
        lines = [gm['coordinates']] if gm['type'] == 'LineString' else gm['coordinates']
        for c in lines:
            c = np.array(c, float)
            if len(c) < 2: continue
            seg = np.hypot(*(c[1:] - c[:-1]).T); cum = np.r_[0, np.cumsum(seg)]
            L = cum[-1]
            if L < STEP: continue
            s = np.arange(STEP / 2, L, STEP)
            x = np.interp(s, cum, c[:, 0]); y = np.interp(s, cum, c[:, 1])
            # direction over +-24 px of arc so a polyline's noise vertices do not spin it
            s0 = np.clip(s - 24, 0, L); s1 = np.clip(s + 24, 0, L)
            dx = np.interp(s1, cum, c[:, 0]) - np.interp(s0, cum, c[:, 0]); dy = np.interp(s1, cum, c[:, 1]) - np.interp(s0, cum, c[:, 1])
            ang = np.degrees(np.arctan2(dy, dx)) % 180
            X.append(x);Y.append(y);A.append(ang);WAY+= [wi]*len(s);CLS+=[hw]*len(s)
            PIECE.append(piece + (s // 100).astype(int)); piece += int(s[-1] // 100) + 1
    x=np.concatenate(X);y=np.concatenate(Y);a=np.concatenate(A);pc=np.concatenate(PIECE);way=np.array(WAY);cls=np.array(CLS)
    ok = (x >= 0) & (x < WD) & (y >= 0) & (y < H)
    nx, ny, nw, nh = neatline()
    ok &= (x >= nx) & (x < nx + nw) & (y >= ny) & (y < ny + nh)
    ok &= ~in_boxes(x, y, 0) if False else True
    fm = np.zeros(len(x), bool)
    for bx, by, bw, bh in furniture_boxes(S1882.get('road', {}).get('furniture_pad', 100)):
        fm |= (x >= bx) & (x < bx + bw) & (y >= by) & (y < by + bh)
    ok &= ~fm
    ok &= ~in_boxes(x, y, KERNEL_PAD + SHIFT_MAX)
    water = np.asarray(Image.open(OUT / 'river/water.png').convert('L'))[::Q, ::Q][:HQ, :WQ] > 0
    wd = binary_dilation(water, iterations=4)          # 16 px
    ok &= ~wd[np.clip((y / Q).astype(int), 0, HQ-1), np.clip((x / Q).astype(int), 0, WQ-1)]
    sv = cls == 'service'
    print('samples', len(x), 'kept', ok.sum(), 'non-service kept', (ok & ~sv).sum(), 'km', ok.sum()*STEP*MPP/1000)
    np.savez(SP / 'samples.npz', x=x[ok], y=y[ok], ang=a[ok], way=way[ok], piece=pc[ok], cls=cls[ok])
main()
