# Where is the printed railway, against where the modern railway (OpenStreetMap) lands through this sheet's own
# control points? Per ~1.2 km stretch of OSM line: the offset across the track (m, + = right of the OSM line's
# direction of travel) that best fits a thin black line on the scan. One number per stretch, with its strength.
import sys, io, json, re, contextlib, numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates
HERE=__file__.rsplit('/',1)[0]; sys.path.insert(0,HERE)
with contextlib.redirect_stdout(io.StringIO()): import seams as S
SC=3.1455      # full-res px per scan px (the 2900 px wide scans)
def project(vid):
    a=json.load(open(f'{HERE}/annotations-live/{vid}.json')); f=a['body']['features']
    px=np.array([x['properties']['resourceCoords'] for x in f],float); g=np.array([S.merc(*x['geometry']['coordinates']) for x in f])
    M,*_=np.linalg.lstsq(np.c_[g,np.ones(len(g))],px,rcond=None)
    ms=np.array([[S.merc(*p) for p in [x['properties'] for x in []]]]) if False else None
    t=a['target']; pts=[[float(v) for v in p.split(',')] for p in re.search(r'points="([^"]+)"',t['selector']['value']).group(1).split()]
    return M,np.array(pts)
def ways(osm,name):
    return [[(p['lon'],p['lat']) for p in w['geometry']] for w in json.load(open(osm))['elements'] if w.get('tags',{}).get('railway')=='rail' and w.get('tags',{}).get('service') is None and name in w.get('tags',{}).get('name','')]
def dark_ridge(path,W=5):
    # the railway is a thick grainy black band; the "+" and dotted boundary lines and text are thin or sparse.
    # So: the share of black ink (not red, not blue) in a W x W box.
    from scipy.ndimage import uniform_filter
    mx=np.asarray(Image.open(path).convert('RGB')).max(-1)
    return uniform_filter((mx<110).astype(np.float32),W)*100
def offsets(vid,osm,name,span=60,tmax=40,step=1.0):
    M,poly=project(vid); R=dark_ridge(f'{SPD}/{vid}.jpg')
    lo,hi=poly.min(0),poly.max(0); out=[]
    for w in ways(osm,name):
        P=np.array([np.r_[S.merc(lon,lat),1]@M for lon,lat in w])/SC          # scan px
        if len(P)<2: continue
        d=np.r_[0,np.cumsum(np.hypot(*np.diff(P,axis=0).T))]; n=int(d[-1]/step)
        if n<span: continue
        s=np.linspace(0,d[-1],n); X=np.interp(s,d,P[:,0]); Y=np.interp(s,d,P[:,1])
        T=np.c_[np.gradient(X),np.gradient(Y)]; T/=np.hypot(*T.T)[:,None]+1e-9; N=np.c_[-T[:,1],T[:,0]]   # N: left of travel in image coords (y down)
        ins=(X*SC>lo[0]+60)&(X*SC<hi[0]-60)&(Y*SC>lo[1]+60)&(Y*SC<hi[1]-60)
        ts=np.arange(-tmax,tmax+1)
        for a in range(0,n-span,span):
            sl=slice(a,a+span)
            if not ins[sl].all(): continue
            prof=np.array([map_coordinates(R,[Y[sl]+t*N[sl,1],X[sl]+t*N[sl,0]],order=1).mean() for t in ts])
            j=int(prof.argmax()); out.append(dict(x=float(X[sl].mean()*SC),y=float(Y[sl].mean()*SC),off_px=int(ts[j]),strength=float(prof[j]),med=float(np.median(prof)),nx=float(N[sl,0].mean()),ny=float(N[sl,1].mean()),second=float(np.sort(prof[np.abs(ts-ts[j])>6])[-1]),way=a))
    return out
SPD=None
if __name__=='__main__':
    SPD=sys.argv[1]; vid=sys.argv[2]; osm=sys.argv[3]; name=sys.argv[4]
    o=offsets(vid,osm,name); m_per=SC*6.2
    for r in o: print(f"x {r['x']:6.0f} y {r['y']:6.0f}  printed minus OSM: east {r['off_px']*r['nx']*m_per:+5.0f} south {r['off_px']*r['ny']*m_per:+5.0f} m  strength {r['strength']:5.1f} vs median {r['med']:4.1f}, best elsewhere {r['second']:4.1f}")
