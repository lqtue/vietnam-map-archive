# Snap the 0.2-grade graticule crossings on each Tonkin 1950 sheet, starting from the draft grid fit.
import sys, json, numpy as np
from PIL import Image
sys.path.insert(0, __file__.rsplit('/',1)[0])
from tk_fit import S, p, GRID, FR, to_med
PARIS=2.33722917
def gray(k): return np.asarray(Image.open(f'{S}/med/tk-{k}.jpg').convert('L')).astype(float)
def resp(g, axis):
    # thin dark line response: darker than both neighbours 3 px away, across the line
    a=np.roll(g,3,axis); b=np.roll(g,-3,axis); return np.clip(np.minimum(a,b)-g,0,60)
def find(rv, x0, y0, half=300, win=70, gap=20):
    # vertical line near column x0, measured at row y0; rv is the vertical-line response
    H,W=rv.shape; ys=np.r_[max(0,y0-half):max(0,y0-gap), min(H,y0+gap):min(H,y0+half)]
    best=(0,None,None)
    for ang in np.arange(-1.2,1.21,0.1):
        sh=np.round((ys-y0)*np.tan(np.radians(ang))).astype(int)
        prof=np.zeros(2*win+1)
        for i,d in enumerate(range(-win,win+1)):
            xs=x0+d+sh; ok=(xs>=0)&(xs<W); prof[i]=rv[ys[ok],xs[ok]].mean() if ok.any() else 0
        i=int(prof.argmax()); sc=prof[i]/(np.median(prof)+1e-6)
        if sc>best[0]: best=(sc,x0-win+i,ang)
    return best
def crossings(k, off=(0,0), win=70):
    lon0,dlon,lat0,dlat=p; c,r=GRID[k]; L,R,T,B=FR[k]
    g=gray(k); rv=resp(g,1); rh=resp(g,0).T
    w_,e_=lon0+c*dlon, lon0+(c+1)*dlon; n_,s_=lat0-r*dlat, lat0-(r+1)*dlat
    gl=lambda lon:(lon-PARIS)/0.9
    out=[]
    for G in np.arange(np.ceil(gl(w_)*5)/5, gl(e_), 0.2):
        for Gy in np.arange(np.ceil(s_/0.9*5)/5, n_/0.9, 0.2):
            lon=G*0.9+PARIS; lat=Gy*0.9
            x0,y0=to_med(k,lon,lat); x0+=off[0]; y0+=off[1]
            if not (L+40<x0<R-40 and T+40<y0<B-40): continue
            sv,x,_=find(rv,x0,y0,win=win); sh_,y,_=find(rh,y0,x,win=win)
            out.append(dict(gx=round(G,1),gy=round(Gy,1),pred=(x0,y0),px=(x,y),score=(round(sv,2),round(sh_,2))))
    return out
if __name__=='__main__':
    for k in sys.argv[1:]: 
        for o in crossings(k): print(k,o)

PRIOR={'vinh-bac-viet':(0,240)}
def run_all():
    res={}
    for k in GRID:
        cs=crossings(k, PRIOR.get(k,(0,0)))
        strong=[c for c in cs if min(c['score'])>=3] or cs
        off=(int(np.median([c['px'][0]-c['pred'][0] for c in strong]))+PRIOR.get(k,(0,0))[0],
             int(np.median([c['px'][1]-c['pred'][1] for c in strong]))+PRIOR.get(k,(0,0))[1])
        cs=crossings(k, off, win=25); res[k]=cs
        dx=[c['px'][0]-c['pred'][0] for c in cs]; dy=[c['px'][1]-c['pred'][1] for c in cs]
        weak=[(c['gx'],c['gy'],c['score']) for c in cs if min(c['score'])<2.5]
        print(k,len(cs),'dx med',int(np.median(dx)),'range',min(dx),max(dx),'dy med',int(np.median(dy)),'range',min(dy),max(dy),'weak',weak,flush=True)
    json.dump(res,open(__file__.rsplit('/',1)[0]+'/crossings.json','w'),default=float)
