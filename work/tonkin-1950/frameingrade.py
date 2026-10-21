# Where is each sheet's printed frame (black neatline), in grade, measured from the nearest printed grid line
# (blue plate) over a distance of at most one grid cell? No fit is extrapolated. Neighbouring sheets that abut
# should show the same grade on the shared edge.
import json, sys, numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter1d
HERE='/Users/airm1/Work/Projects/vma-tonkin1950/work/tonkin-1950'; SP=sys.argv[1]
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
res={}
for sheet,vid in ids.items():
    cs=[c for c in cr[sheet] if min(c['score'])>=1.5]
    if len(cs)<4: print(sheet,'too few strong crossings'); continue
    d=np.asarray(Image.open(f'{SP}/{vid}.jpg').convert('RGB')).astype(np.float32); d=d[...,2]-d[...,0]
    poly=np.array(masks[sheet]['polygon'])/S if masks[sheet]['polygon'] else None
    if poly is None: print(sheet,'no mask'); continue
    H,W=d.shape; V={};Hh={}
    for gx in sorted({c['gx'] for c in cs}):
        pts=[(c['px'][1]*Q,c['px'][0]*Q) for c in cs if c['gx']==gx]
        if len(pts)>=2: V[gx]=line(d,pts,int(poly[:,1].min())+30,int(poly[:,1].max())-30)        # x = b0 + b1*y
    for gy in sorted({c['gy'] for c in cs}):
        pts=[(c['px'][0]*Q,c['px'][1]*Q) for c in cs if c['gy']==gy]
        if len(pts)>=2: Hh[gy]=line(d.T,pts,int(poly[:,0].min())+30,int(poly[:,0].max())-30)   # y = b0 + b1*x
    # frame edges from the mask (TL TM TR BR BM BL), scan px
    TL,TM,TR,BR,BM,BL=poly
    def edge_x(P,Q_,ys): return [np.interp(y,[P[1],Q_[1]],[P[0],Q_[0]]) for y in ys]
    out={}
    ys=np.linspace(TL[1]+500,BL[1]-500,5)                                    # left and right edges, away from the corners
    for side,(P,Q_) in (('W',(TL,BL)),('E',(TR,BR))):
        gr=[]
        for y in ys:
            xe=edge_x(P,Q_,[y])[0]; xs={g:v[0]+v[1]*y for g,v in V.items()}
            g0=min(xs,key=lambda g:abs(xs[g]-xe)); others=sorted(xs.items()); 
            sp=np.mean(np.diff([x for _,x in others])/np.diff([g for g,_ in others])) if len(others)>1 else None   # px per grade
            gr.append(g0+(xe-xs[g0])/sp)
        out[side]=(np.mean(gr),np.std(gr))
    xs_=np.linspace(TL[0]+500,TR[0]-500,5)
    for side,(P,Q_) in (('N',(TL,TR)),('S',(BL,BR))):
        gr=[]
        for x in xs_:
            ye=np.interp(x,[P[0],Q_[0]],[P[1],Q_[1]]); ys_={g:v[0]+v[1]*x for g,v in Hh.items()}
            g0=min(ys_,key=lambda g:abs(ys_[g]-ye)); oth=sorted(ys_.items()); sp=np.mean(np.diff([y for _,y in oth])/np.diff([g for g,_ in oth]))
            gr.append(g0+(ye-ys_[g0])/sp)
        out[side]=(np.mean(gr),np.std(gr))
    res[sheet]=out
    print(f"{sheet:14s} W {out['W'][0]:8.4f} E {out['E'][0]:8.4f} N {out['N'][0]:7.4f} S {out['S'][0]:7.4f}   within-edge sd (grade): W {out['W'][1]:.4f} E {out['E'][1]:.4f} N {out['N'][1]:.4f} S {out['S'][1]:.4f}   [{len(V)} vertical, {len(Hh)} horizontal lines]")
json.dump({k:{s:list(v) for s,v in o.items()} for k,o in res.items()},open(f'{HERE}/frame_in_grade.json','w'),indent=1)
GRID={'viet-tri':(0,0),'ha-noi':(1,0),'bac-giang':(2,0),'an-chau':(3,0),'hoa-binh':(0,1),'hung-yen':(1,1),'hai-phong':(2,1),'quang-yen':(3,1),'ninh-binh':(1,2),'bui-chu':(2,2),'vinh-bac-viet':(3,2)}
by={v:k for k,v in GRID.items()}; print('\nshared edges: difference in grade, then in km (1 grade = 100 km north-south, 100*cos(lat) km east-west; negative = overlap)')
for (c,r),k in by.items():
    if (c+1,r) in by and k in res and by[(c+1,r)] in res: b=by[(c+1,r)]; dg=res[b]['W'][0]-res[k]['E'][0]; print(f"  {k:12s} | {b:12s} gap {dg:+.4f} gr = {dg*100*0.934:+6.2f} km")
    if (c,r+1) in by and k in res and by[(c,r+1)] in res: b=by[(c,r+1)]; dg=res[k]['S'][0]-res[b]['N'][0]; print(f"  {k:12s} / {b:12s} gap {dg:+.4f} gr = {dg*100:+6.2f} km")
