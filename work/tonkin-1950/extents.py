import json, numpy as np, sys
sys.path.insert(0,'.')
from tk_fit import FR, GRID
HERE=__file__.rsplit('/',1)[0]
cr=json.load(open(f'{HERE}/crossings.json'))   # snap.py's output, committed
def good(cs):
    keep=[c for c in cs if min(c['score'])>=1.5]
    if len(keep)<3: return keep,None,np.array([])
    for _ in range(4):
        A=np.array([[c['px'][0],c['px'][1],1] for c in keep],float); G=np.array([[c['gx'],c['gy']] for c in keep])
        M,*_=np.linalg.lstsq(A,G,rcond=None); r=np.hypot(*((A@M-G)/0.2*750).T)
        if len(keep)<=4 or r.max()<=8: break
        keep=[c for c,ri in zip(keep,r) if ri<r.max()]
    return keep,M,r
ext={}
for k,cs in cr.items():
    keep,M,r=good(cs); L,R,T,B=[v for v in FR[k]]
    if M is None: print(k,'too few strong crossings',len(keep)); continue
    corners={n:(np.array([x,y,1])@M).round(4).tolist() for n,(x,y) in dict(NW=(L,T),NE=(R,T),SE=(R,B),SW=(L,B)).items()}
    ext[k]=dict(n=len(keep),resid=r.round(1).tolist(),corners=corners,
      span=(sorted({c['gx'] for c in keep}),sorted({c['gy'] for c in keep})))
    print(k,GRID[k],len(keep),'W',round(corners['NW'][0],3),'E',round(corners['NE'][0],3),'N',round(corners['NW'][1],3),'S',round(corners['SW'][1],3),'spanx',ext[k]['span'][0])
json.dump(ext,open(f'{HERE}/extents.json','w'))
