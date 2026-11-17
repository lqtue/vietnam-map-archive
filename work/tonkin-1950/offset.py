import json, numpy as np, sys
sys.path.insert(0,'.')
from tk_fit import PTS, S
from extents import good, cr
PARIS=2.33722917
d=[]
for k,pts in PTS.items():
    keep,M,_=good(cr[k])
    for xy,(lo,la) in pts:
        if xy[0]=='m': x,y=xy[1],xy[2]
        else:
            f=json.load(open(f'{S}/thumbs/tk-{k}.info.json'))['width']/800/4; x,y=xy[0]*f,xy[1]*f
        gx,gy=np.array([x,y,1])@M; plon,plat=gx*0.9+PARIS,gy*0.9
        d.append(((lo-plon)*111000*np.cos(np.radians(21)),(la-plat)*111000)); print(k,np.round(d[-1]))
d=np.array(d); print('mean E,N m',d.mean(0).round(0),'sd',d.std(0).round(0),'n',len(d))
