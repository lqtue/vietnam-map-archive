# Neatline of a Tonkin 1950 sheet: the longest dark lines near each edge, tilt-tolerant.
import numpy as np, sys, json
from PIL import Image
def prof(m, angles):
    H,W=m.shape; ys=np.arange(H); yy,xx=np.nonzero(m); out=[]
    for ang in angles:
        sh=np.round((yy-H/2)*np.tan(np.radians(ang))).astype(int)
        p=np.bincount(xx-sh+300, minlength=W+600)[:W+600]/H; out.append((ang,p))
    return out
def edges(m, lo, hi):
    # best (angle, x) of a long line with x in [lo,hi)
    best=(0,0,0)
    for ang,p in prof(m, np.arange(-1.5,1.51,0.05)):
        seg=p[lo+300:hi+300]; i=int(seg.argmax())
        if seg[i]>best[0]: best=(seg[i],ang,lo+i)
    return best
def frame(path):
    a=np.asarray(Image.open(path).convert('RGB')).astype(int)
    s=a.sum(-1); d=s<450; br=s>560
    m=d&(np.roll(br,5,1)&np.roll(br,-5,1)|np.roll(br,5,0)&np.roll(br,-5,0))
    H,W=m.shape; out={}
    for side,(mm,lo,hi) in {'L':(m,0,W//6),'R':(m,5*W//6,W),'T':(m.T,0,H//6),'B':(m.T,5*H//6,H)}.items():
        out[side]=edges(mm,lo,hi)
    return out,(W,H)
if __name__=='__main__':
    for p in sys.argv[1:]:
        f,(W,H)=frame(p); print(p.split('/')[-1], W,H, {k:(round(float(v[0]),2),round(float(v[1]),2),v[2]) for k,v in f.items()})
