"""usage: georef_grid.py cfg.json  -> gcp args file, prints residuals. cfg: tag, zone, vx[list px], E0 (km at vx[0]), hy[list px], N0 (km at hy[0], decreasing downward), step_km"""
import sys, json, numpy as np
from pyproj import Transformer
c=json.load(open(sys.argv[1])); st=c.get('step_km',10); s=8
def assign(px,v0,sign):
    px=np.array(sorted(px),float); d=np.median(np.diff(px)); 
    # step estimate: smallest gap cluster
    gaps=np.diff(px); d=np.median(gaps[gaps<1.5*gaps.min()])
    k=np.round((px-px[0])/d).astype(int)
    b,a=np.polyfit(k,px,1)
    res=px-(a+b*k); good=np.abs(res)<45
    return k,px,good,a,b
kx,px,gx,ax,bx=assign(c['vx'],c['E0'],1); ky,py,gy,ay,by=assign(c['hy'],c['N0'],-1)
# refit on inliers, and fill missing lines from the model
def full(k,p,g):
    b,a=np.polyfit(k[g],p[g],1); out={}
    for kk in range(k.min(),k.max()+1):
        m=a+b*kk; hit=[pp for pp,ok,k2 in zip(p,g,k) if k2==kk and ok]
        out[kk]=hit[0] if hit and abs(hit[0]-m)<45 else m
    return out,(a,b)
X,mx=full(kx,px,gx); Y,my=full(ky,py,gy)
print('x step px',round(mx[1]),'y step px',round(my[1]),'rejected x',int((~gx).sum()),'y',int((~gy).sum()))
epsg={48:"EPSG:3148",49:"EPSG:3149"}[c['zone']]
t=Transformer.from_crs(epsg,"EPSG:4326",always_xy=True)
g=[]
for i,xp in X.items():
  for j,yp in Y.items():
    lon,lat=t.transform((c['E0']+st*i)*1000,(c['N0']-st*j)*1000); g.append((xp,yp,lon,lat))
open(f"gcp{c['tag']}.txt",'w').write(' '.join(f"-gcp {x/s:.1f} {y/s:.1f} {lo:.6f} {la:.6f}" for x,y,lo,la in g))
json.dump([dict(px=[x,y],lonlat=[lo,la]) for x,y,lo,la in g],open(f"gcp{c['tag']}.json",'w'))
print(len(g),'gcps; lon/lat range',min(p[2] for p in g),max(p[2] for p in g),min(p[3] for p in g),max(p[3] for p in g))
