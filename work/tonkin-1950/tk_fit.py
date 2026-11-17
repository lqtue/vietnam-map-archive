import numpy as np, json
import os
S=os.environ['SERIES_WORK']   # thumbs/ (info.json + 800px), med/ (quarter-res JPEGs), rows.json
C=np.cos(np.radians(21))
# (thumb px x, y) -> (lon, lat); thumbs are the 800px 'sizes' level
PTS={
 'ha-noi':[(('m',550,2365),(105.8577,21.0427)),(('m',1393,1750),(106.060,21.186)),(('m',1522,1665),(106.0874,21.2047))],
 'hung-yen':[(('m',780,2065),(105.916,20.545)),(('m',1365,1595),(106.054,20.650)),(('m',1865,2595),(106.174,20.433))],
 'hai-phong':[((175,100),(106.327,20.940)),((690,240),(106.682,20.862)),((190,870),(106.340,20.447))],
}
# neatline from frame.py, quarter-res px
FR={'ha-noi':(110,2131,147,2662),'hung-yen':(118,2145,141,2671),'hai-phong':(108,2127,140,2655)}
def sim(px,geo):
    # complex least squares: z = a*w + b
    w=np.array([complex(x,-y) for x,y in px]); z=np.array([complex(lo*C,la) for lo,la in geo])
    A=np.c_[w,np.ones_like(w)]; (a,b),*_=np.linalg.lstsq(A,z,rcond=None)
    return a,b,np.abs(A@[a,b]-z)*111000
GRID={'viet-tri':(0,0),'ha-noi':(1,0),'bac-giang':(2,0),'an-chau':(3,0),'hoa-binh':(0,1),'hung-yen':(1,1),'hai-phong':(2,1),'quang-yen':(3,1),'ninh-binh':(1,2),'bui-chu':(2,2),'vinh-bac-viet':(3,2)}
def uv(k,*xy):
    info=json.load(open(f'{S}/thumbs/tk-{k}.info.json')); f=info['width']/info['sizes'][-1]['width']
    if xy[0]=='m': f=4; xy=xy[1:]
    x,y=xy
    L,R,T,B=[v*4 for v in FR[k]]; return (x*f-L)/(R-L),(y*f-T)/(B-T)
rows=[];rhs=[]
for k,pts in PTS.items():
    c,r=GRID[k]
    for xy,(lo,la) in pts:
        u,v=uv(k,*xy)
        rows.append([1,c+u,0,0]); rhs.append(lo); rows.append([0,0,1,-(r+v)]); rhs.append(la)
p,*_=np.linalg.lstsq(np.array(rows),np.array(rhs),rcond=None)
res=(np.array(rows)@p-rhs).reshape(-1,2)*[111000*C,111000]
if __name__=='__main__': print('grid lon0 %.4f dlon %.4f lat0 %.4f dlat %.4f'%tuple(p))
if __name__=='__main__': print('res m',np.hypot(*res.T).round(0))
FR.update({'viet-tri':(58,2141,136,2674),'bac-giang':(116,2141,147,2667),'an-chau':(88,2155,149,2668),'hoa-binh':(60,2121,140,2681),'quang-yen':(93,2165,136,2651),'ninh-binh':(102,2135,150,2671),'bui-chu':(160,2183,149,2664),'vinh-bac-viet':(100,2140,143,2665)})
def to_med(k,lon,lat):
    lon0,dlon,lat0,dlat=p; c,r=GRID[k]; L,R,T,B=FR[k]
    u=(lon-lon0)/dlon-c; v=(lat0-lat)/dlat-r; return round(L+u*(R-L)),round(T+v*(B-T))
if __name__=='__main__':
    import sys
    for a in sys.argv[1:]:
        k,lo,la=a.split(':'); print(k,to_med(k,float(lo),float(la)))
