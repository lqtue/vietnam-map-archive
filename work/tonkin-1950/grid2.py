# Printed grid lines of a Tonkin 1950 sheet, found on the red channel (the grid is cyan, which absorbs red), over the
# whole sheet with a tilt search, then traced and fitted per fold-out half. Replaces grademap.grid, whose seeds were up to
# 35 px off and whose channel (blue minus red) is faint on some sheets. Each line carries its fit error, and a sheet passes
# the gate only if its lines are straight (rms <= 60 m) and adjacent lines equally spaced (the two halves within 0.5 %).
import sys, json, numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter1d
HERE=__file__.rsplit('/',1)[0]
masks=json.load(open(f'{HERE}/masks.json')); cr=json.load(open(f'{HERE}/crossings.json'))
ids={r['sheet']:r['map_id'] for r in json.load(open(f'{HERE}/sheets.json'))}
S=3.1455; Q=4/S; M=S*6.2      # M: metres per scan px
def _peaks(a,lo,hi,ang0=None):
    """a: rows run along the lines, shape (H, W). Best tilt over the sheet, then strong peaks across: [(pos at the middle row, strength)], tilt."""
    H,W=a.shape; best=None
    for ang in (np.arange(-1.3,1.31,0.05) if ang0 is None else [ang0]):
        sh=np.round((np.arange(H)-H/2)*np.tan(np.radians(ang))).astype(int)
        b=np.take_along_axis(a,(np.arange(W)[None,:]+sh[:,None])%W,1); med=np.median(b,0); hp=med-uniform_filter1d(med,41); hp[:lo]=0; hp[hi:]=0
        pk=[(j,float(hp[j])) for j in range(lo,hi) if hp[j]>0 and hp[j]==hp[max(0,j-10):j+11].max()]
        top=sorted(pk,key=lambda t:-t[1])[:5]
        if best is None or sum(v for _,v in top)>best[0]: best=(sum(v for _,v in top),ang,hp.copy())
    _,ang,hp=best
    return hp,ang
def _trace(a,pos,ang,lo,hi,nwin=12):
    """Follow a line along rows lo:hi in two passes. Pass 1 looks +-30 px around the prediction; pass 2 looks +-8 px
    around pass 1's straight fit, so a stronger neighbour cannot win. Returns (b0,b1,rms,n): pos(row)=b0+b1*row,
    rms in scan px, n windows used. Windows where the line is hidden (weak) are dropped."""
    edges=np.linspace(lo,hi,nwin+1).astype(int)
    def windows(pred_of,half):
        rows=[];cols=[];st=[]
        for u,v in zip(edges[:-1],edges[1:]):
            rc=(u+v)/2; pred=pred_of(rc); c=np.arange(int(pred)-half,int(pred)+half+1)
            if c[0]<0 or c[-1]>=a.shape[1]: continue
            t=np.tan(np.radians(ang)) if pred_of is first else slope[0]
            sh=np.round((np.arange(u,v)-rc)*t).astype(int)
            prof=np.median(np.take_along_axis(a[u:v],(c[None,:]+sh[:,None]),1),0); prof=prof-uniform_filter1d(prof,15)
            rows.append(rc); cols.append(c[int(prof.argmax())]+0.0); st.append(float(prof.max()))
        rows,cols,st=np.array(rows),np.array(cols),np.array(st); k=st>=0.4*np.median(st); return rows[k],cols[k]
    def fit(rows,cols):
        for _ in range(4):
            A=np.c_[rows,np.ones(len(rows))]; (b1,b0),*_=np.linalg.lstsq(A,cols,rcond=None); r=cols-(A@[b1,b0]); k=np.abs(r)<=max(3,2.5*r.std())
            if k.all() or k.sum()<4: break
            rows,cols=rows[k],cols[k]
        return b0,b1,float(np.sqrt(np.mean((cols-(b0+b1*rows))**2))),len(rows)
    first=lambda rc:pos+(rc-a.shape[0]/2)*np.tan(np.radians(ang)); slope=[np.tan(np.radians(ang))]
    b0,b1,_,_=fit(*windows(first,30)); slope[0]=b1
    return fit(*windows(lambda rc:b0+b1*rc,8))
def grid(sheet,SP):
    vid=ids[sheet]; a=-np.asarray(Image.open(f'{SP}/{vid}.jpg').convert('RGB')).astype(np.float32)[...,0]
    p=np.array(masks[sheet]['polygon'])/S; x0,x1=int(p[:,0].min())+30,int(p[:,0].max())-30; y0,y1=int(p[:,1].min())+30,int(p[:,1].max())-30
    xm=int(p[1][0]); cs=[c for c in cr[sheet] if min(c['score'])>=1.5]
    out=dict(V={},H={},fold=xm,diag=[])
    # horizontal lines: peaks across rows over the whole width, then traced per half
    def label(hp,seeds):
        # seeds (from crossings.json) can be ~40 px off and the line spacing is ~1000 px: look for the strongest peak
        # within 120 px of each seed, take the median shift, then look again within 40 px of the shifted seed
        mx=hp.max(); win=lambda c,w:(max(0,int(c)-w),min(len(hp),int(c)+w+1))
        first=[]
        for g,sd in seeds.items():
            u,v=win(sd,120); first.append(u+int(hp[u:v].argmax())-sd)
        shift=np.median(first); lab={}
        for g,sd in seeds.items():
            u,v=win(sd+shift,40); j=u+int(hp[u:v].argmax())
            if hp[j]>=0.15*mx: lab[g]=j
        return lab
    hp,ang=_peaks(a.T[x0:x1],y0,y1); hp=np.r_[np.zeros(0),hp]
    seeds={g:np.median([c['px'][1]*Q for c in cs if c['gy']==g]) for g in sorted({c['gy'] for c in cs})}
    lab=label(hp,seeds)
    for g,pos in lab.items():
        for half,(lo,hi) in (('L',(x0,xm-50)),('R',(xm+50,x1))):
            b0,b1,rms,n=_trace(a.T,pos,ang,lo,hi); out['H'].setdefault(g,{})[half]=(b0,b1,rms,n)
    hpv,angv=_peaks(a[y0:y1],x0,x1)
    seeds={g:np.median([c['px'][0]*Q for c in cs if c['gx']==g]) for g in sorted({c['gx'] for c in cs})}
    lab=label(hpv,seeds)
    for g,pos in lab.items():
        b0,b1,rms,n=_trace(a,pos,angv,y0,y1); out['V'][g]=(b0,b1,rms,n)
    return out
def gate(gr):
    """Quality gate, returns (passes, notes). Lines straight and equally spaced; tilts of lines of the same half alike."""
    notes=[]; V,H=gr['V'],gr['H']
    if len(V)<2: notes.append(f'only {len(V)} vertical lines')
    if len(H)<2: notes.append(f'only {len(H)} horizontal lines')
    for g,(b0,b1,r,n) in V.items():
        if r*M>60: notes.append(f'V{g} not straight (rms {r*M:.0f} m)')
    for g,hv in H.items():
        for h,(b0,b1,r,n) in hv.items():
            if r*M>60: notes.append(f'H{g}{h} not straight (rms {r*M:.0f} m)')
    for h in ('L','R'):
        gs=sorted(g for g in H if h in H[g])
        if len(gs)>=3:
            x=sum(gr['fold']+(-1 if h=='L' else 1)*500 for _ in [0])  # a column inside the half
            ys=[H[g][h][0]+H[g][h][1]*x for g in gs]; sp=np.diff(ys)
            if abs(sp[0]-sp[1])/sp.mean()>0.005: notes.append(f'H spacings in half {h} differ: {sp[0]*M/1000:.2f} vs {sp[1]*M/1000:.2f} km')
    return (not notes),notes
if __name__=='__main__':
    SP=sys.argv[1]
    for sheet in ids:
        if not masks[sheet]['polygon']: continue
        gr=grid(sheet,SP); ok,notes=gate(gr)
        print(f"{sheet:13s} {len(gr['V'])} V lines {sorted(gr['V'])}  {len(gr['H'])} H lines {sorted(gr['H'])}  gate {'PASS' if ok else 'FAIL'}  {notes}")
