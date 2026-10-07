"""auto_grid.py NN SCALE_K -> prints vx, hy (full-res px) of the 10 km gridlines, fits equal spacing"""
import sys,json,numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter1d
Image.MAX_IMAGE_PIXELS=None
tag,k=sys.argv[1],int(sys.argv[2])
from common import WORK
S=WORK
img=Image.open(S+f'up/{tag}.jpg').convert('L');W,H=img.size;f=4
g=np.asarray(img.resize((W//f,H//f),Image.BOX),dtype=np.float32)
step=2354*100/k   # px per 10 km at this scale (~598 dpi)
def longrun(r,axis):
    # r bool array; for each column (axis=0 runs down rows), longest run allowing gaps<=4
    m=r if axis==0 else r.T
    out=np.zeros(m.shape[1],int)
    for x in range(m.shape[1]):
        c=m[:,x];idx=np.flatnonzero(c)
        if len(idx)<2:continue
        br=np.flatnonzero(np.diff(idx)>5);st=np.r_[0,br+1];en=np.r_[br,len(idx)-1]
        out[x]=(idx[en]-idx[st]).max()
    return out
bg=uniform_filter1d(g,41,axis=1);rv=(np.clip(bg-g,0,None)>12)
bg=uniform_filter1d(g,41,axis=0);rh=(np.clip(bg-g,0,None)>12)
def lines(lr,n):
    thr=0.22*n;cand=np.flatnonzero(lr>=thr)
    # cluster
    cl=[];cur=[]
    for c in cand:
        if cur and c-cur[-1]>3:cl.append(cur);cur=[]
        cur.append(c)
    if cur:cl.append(cur)
    pos=[(sum(x*lr[x] for x in c)/sum(lr[x] for x in c))*f for c in cl]
    return np.array(pos),[max(lr[x] for x in c) for c in cl]
def fit(pos,step):
    best=None
    for s in np.arange(step*0.97,step*1.03,step*0.001):
        for p0 in pos:
            ph=((pos-p0+s/2)%s)-s/2;sc=(abs(ph)<14).sum()
            if best is None or sc>best[0]:best=(sc,s,p0)
    sc,s,p0=best;k0=np.round((pos-p0)/s);ok=abs(pos-(p0+k0*s))<14
    kk=k0[ok];pp=pos[ok];b,a=np.polyfit(kk,pp,1)
    return a,b,int(kk.min()),int(kk.max()),sc,len(pos)
from scipy.signal import find_peaks
lr=longrun(rv,0);pos,_=lines(lr,g.shape[0])
a,b,k0,k1,sc,tot=fit(pos,step);vx=[round(a+b*i) for i in range(k0,k1+1)]
cols=[int(x/f) for x in vx if 0<=x/f<g.shape[1]]
def runs(m,c):
    ix=np.flatnonzero(m[:,max(0,c-1):c+2].any(1))
    if len(ix)<2:return (0,0)
    br=np.flatnonzero(np.diff(ix)>5);st=np.r_[0,br+1];en=np.r_[br,len(ix)-1];j=(ix[en]-ix[st]).argmax();return (ix[st[j]],ix[en[j]])
ext=[runs(rv,c) for c in cols];ln=np.array([e[1]-e[0] for e in ext]);good=ln>=0.6*ln.max()
y0=min(e[0] for e,gd in zip(ext,good) if gd);y1=max(e[1] for e,gd in zip(ext,good) if gd)
x0,x1=min(cols),max(cols)
rs=rh[y0:y1,x0:x1].sum(1)
vp,_=find_peaks(rs,height=rs.max()*0.35,distance=int(step/f*0.5));hpos=vp*f+y0*f
best=None
for s2 in np.arange(b*0.985,b*1.015,b*0.0005):
    for p0 in hpos:
        ph=((hpos-p0+s2/2)%s2)-s2/2;scr=(abs(ph)<14).sum()
        if best is None or scr>best[0]:best=(scr,s2,p0)
scr,s2,p0=best;kk=np.round((hpos-p0)/s2);ok=abs(hpos-(p0+kk*s2))<14
bh,ah=np.polyfit(kk[ok],hpos[ok],1)
lo=int(np.ceil((y0*f-0.35*bh-ah)/bh));hi=int(np.floor((y1*f+0.35*bh-ah)/bh))
hy=[round(ah+bh*i) for i in range(lo,hi+1)]
# drop lines with no ink along them
def frac(m,pos,axis,a0,a1):
    p=int(pos/f)
    if not (0<=p<(m.shape[0] if axis else m.shape[1])):return 0
    return (m[p-1:p+2,a0:a1] if axis else m[a0:a1,p-1:p+2]).any(1 if axis==0 else 0).mean()
hy=[y for y in hy if frac(rh,y,1,x0,x1)>=0.45]
vx=[x for x in vx if frac(rv,x,0,int(hy[0]/f),int(hy[-1]/f))>=0.45]
print(tag,'vx',len(vx),round(b,1),'hy',len(hy),round(bh,1),'matched',sc,'/',tot,'|',scr,'/',len(hpos))
res={'vx':vx,'hy':hy};print(json.dumps(res))
json.dump(res,open(S+f'allmaps/auto{tag}.json','w'))
