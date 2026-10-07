import numpy as np, json
from pyproj import Transformer
vx=[6636,8220,9772,11336,12912,14472,15928,17608]   # detected, i=1..8
hy={1:11244,2:9672,3:8080,4:6520,5:4904,6:3328,7:1792}
# robust line models
i=np.arange(1,9); a=np.polyfit(i,vx,1); xm=lambda k:np.polyval(a,k)
xs={k:(vx[k-1] if abs(vx[k-1]-xm(k))<45 else xm(k)) for k in range(1,9)}; xs[0]=xm(0)
j=np.array(sorted(hy)); b=np.polyfit(j,[hy[k] for k in j],1); ym=lambda k:np.polyval(b,k)
ys={k:(hy[k] if abs(hy[k]-ym(k))<45 else ym(k)) for k in hy}
print('xm',a,'ym',b, {k:round(xs[k]-xm(k)) for k in xs}, {k:round(ys[k]-ym(k)) for k in ys})
t=Transformer.from_crs("EPSG:3148","EPSG:4326",always_xy=True)
g=[]
for ii in range(0,9):
  for jj in range(1,8):
    lon,lat=t.transform(500000+10000*ii,1100000+10000*jj)
    g.append((xs[ii],ys[jj],lon,lat))
s=8
with open('gcp01.txt','w') as f: f.write(' '.join(f"-gcp {x/s:.1f} {y/s:.1f} {lo:.6f} {la:.6f}" for x,y,lo,la in g))
print(len(g),g[0],g[-1])
