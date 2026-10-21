# (module) printed grid lines of a sheet and a pixel -> grade mapper. Where each sheet's printed frame (black neatline), in grade, measured from the nearest printed grid line
# (blue plate) over a distance of at most one grid cell? No fit is extrapolated. Neighbouring sheets that abut
# should show the same grade on the shared edge.
import json, sys, numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter1d
HERE=__file__.rsplit('/',1)[0]
masks=json.load(open(f'{HERE}/masks.json')); cr=json.load(open(f'{HERE}/crossings.json'))
ids={r['sheet']:r['map_id'] for r in json.load(open(f'{HERE}/sheets.json'))}
S=3.1455; Q=4/S            # full-res px per scan px; quarter-res px -> scan px
def track(a,pos0,tilt,lo,hi,nwin=12,half=25):
    out=[]; edges=np.linspace(lo,hi,nwin+1).astype(int); mid=(lo+hi)/2
    for u,v in zip(edges[:-1],edges[1:]):
        rc=(u+v)/2; pred=pos0+(rc-mid)*np.tan(np.radians(tilt)); seg=a[u:v]; cols=np.arange(int(pred)-half,int(pred)+half+1)
        if cols[0]<0 or cols[-1]>=a.shape[1]: continue
        sh=np.round((np.arange(u,v)-rc)*np.tan(np.radians(tilt))).astype(int)
        prof=np.median(np.take_along_axis(seg,(cols[None,:]+sh[:,None]),1),0); prof=prof-uniform_filter1d(prof,15)
        out.append((rc,cols[int(prof.argmax())],float(prof.max())))
    return out
def line(a,seed_pts,lo,hi):
    # seed_pts: [(along, across)] in scan px; returns (b0,b1) with across = b0 + b1*along, robust refit on tracked positions
    A=np.c_[[p[0] for p in seed_pts],np.ones(len(seed_pts))]; (b1,b0),*_=np.linalg.lstsq(A,[p[1] for p in seed_pts],rcond=None)
    t=track(a,b0+b1*(lo+hi)/2,np.degrees(np.arctan(b1)),lo,hi)
    t=[q for q in t if q[2]>np.median([q[2] for q in t])*0.5]
    al=np.array([q[0] for q in t]); ac=np.array([q[1] for q in t],float)
    for _ in range(3):
        A=np.c_[al,np.ones(len(al))]; (c1,c0),*_=np.linalg.lstsq(A,ac,rcond=None); r=ac-(A@[c1,c0]); k=np.abs(r)<max(3,2.5*np.std(r)); al,ac=al[k],ac[k]
    return c0,c1

def grid(sheet,SP):
    """Tracked grid lines of a sheet in scan px: V[gx]=(b0,b1) with x=b0+b1*y, H[gy]=(b0,b1) with y=b0+b1*x."""
    vid=ids[sheet]; cs=[c for c in cr[sheet] if min(c['score'])>=1.5]
    d=np.asarray(Image.open(f'{SP}/{vid}.jpg').convert('RGB')).astype(np.float32); d=d[...,2]-d[...,0]
    poly=np.array(masks[sheet]['polygon'])/S; V={};Hh={}
    for gx in sorted({c['gx'] for c in cs}):
        pts=[(c['px'][1]*Q,c['px'][0]*Q) for c in cs if c['gx']==gx]
        if len(pts)>=2: V[gx]=line(d,pts,int(poly[:,1].min())+30,int(poly[:,1].max())-30)
    for gy in sorted({c['gy'] for c in cs}):
        pts=[(c['px'][0]*Q,c['px'][1]*Q) for c in cs if c['gy']==gy]
        if len(pts)>=2: Hh[gy]=line(d.T,pts,int(poly[:,0].min())+30,int(poly[:,0].max())-30)
    return V,Hh
def _interp(pos,x):
    # pos: {grade: position}; linear in the two nearest lines (extrapolates by at most about one cell)
    g=sorted(pos,key=lambda k:abs(pos[k]-x))[:2]; g0,g1=sorted(g)
    return g0+(x-pos[g0])*(g1-g0)/(pos[g1]-pos[g0])
def to_grade(V,Hh,x,y):
    return _interp({g:b0+b1*y for g,(b0,b1) in V.items()},x), _interp({g:b0+b1*x for g,(b0,b1) in Hh.items()},y)
