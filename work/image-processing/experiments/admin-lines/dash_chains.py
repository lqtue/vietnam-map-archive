"""Dashed / dash-dot boundary lines as chains of short thin strokes that line up end to end.
Usage: dash_chains.py <full-res image> <out.jpg> [min dashes per chain=4]
ponytail: hand rules; misses any dash that touches other ink (see README)."""
import sys, numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
src,out=sys.argv[1],sys.argv[2]; MINCHAIN=int(sys.argv[3]) if len(sys.argv)>3 else 4
Image.MAX_IMAGE_PIXELS=None
rgb=np.asarray(Image.open(src).convert('RGB'))
r,g,b=[rgb[...,i].astype(np.int16) for i in range(3)]
mean=(r+g+b)//3; paper=np.median(mean)
loose=mean<paper-28
llab,_=ndi.label(loose,structure=np.ones((3,3))); lobj=ndi.find_objects(llab)
ink=(mean<120)&((np.maximum(np.maximum(r,g),b)-np.minimum(np.minimum(r,g),b))<70)
pinkish=(r-b>60)&(mean>140)
lab,n=ndi.label(ink,structure=np.ones((3,3))); objs=ndi.find_objects(lab)
D=[]
for i,sl in enumerate(objs,1):
    if sl is None: continue
    h=sl[0].stop-sl[0].start; w=sl[1].stop-sl[1].start
    if max(h,w)<5 or max(h,w)>40: continue
    ys,xs=np.nonzero(lab[sl]==i)
    if len(ys)<6 or len(ys)>160: continue
    ev,evec=np.linalg.eigh(np.cov(np.vstack([xs,ys]).astype(float))); ev=np.clip(ev,0,None)
    L=4*np.sqrt(ev[1]); W=4*np.sqrt(ev[0])+1
    if L<6 or L>36 or W>4.5 or L/W<2.6: continue
    y0,x0=ys.mean()+sl[0].start,xs.mean()+sl[1].start
    k=llab[int(y0),int(x0)]
    if k:
        ls=lobj[k-1]
        if max(ls[0].stop-ls[0].start,ls[1].stop-ls[1].start)>48: continue
    D.append((y0,x0,*evec[:,1],L/2))
D=np.array(D); cy,cx,ux,uy,hl=D.T; N=len(D)
E=np.vstack([np.c_[cx+ux*hl,cy+uy*hl],np.c_[cx-ux*hl,cy-uy*hl]]); owner=np.r_[np.arange(N),np.arange(N)]
parent=np.arange(N)
def find(a):
    while parent[a]!=a: parent[a]=parent[parent[a]]; a=parent[a]
    return a
edges=[]; c=np.cos(np.radians(28))
for a,bb in cKDTree(E).query_pairs(r=24):
    i,j=owner[a],owner[bb]
    if i==j or abs(ux[i]*ux[j]+uy[i]*uy[j])<c: continue
    vx,vy=cx[j]-cx[i],cy[j]-cy[i]; d=np.hypot(vx,vy)
    if d==0 or abs((vx*ux[i]+vy*uy[i])/d)<c: continue
    edges.append((i,j)); parent[find(i)]=find(j)
print('dash candidates',N,'links',len(edges))
# bridge: chain ends within 80 px, aligned with both end dashes
roots=np.array([find(i) for i in range(N)])
deg=np.zeros(N,int)
for i,j in edges: deg[i]+=1; deg[j]+=1
ends=np.where((deg==1))[0]
bridges=[]; cb=np.cos(np.radians(22))
et=cKDTree(np.c_[cx[ends],cy[ends]])
for a,bb in et.query_pairs(r=80):
    i,j=ends[a],ends[bb]
    if find(i)==find(j): continue
    vx,vy=cx[j]-cx[i],cy[j]-cy[i]; d=np.hypot(vx,vy)
    if d<20: continue
    if abs((vx*ux[i]+vy*uy[i])/d)<cb or abs((vx*ux[j]+vy*uy[j])/d)<cb: continue
    bridges.append((i,j)); parent[find(i)]=find(j)
roots=np.array([find(i) for i in range(N)])
ids,counts=np.unique(roots,return_counts=True)
span={}
for rt in ids:
    m=roots==rt; span[rt]=max(np.ptp(cx[m]),np.ptp(cy[m]))
keep={rt for rt,cnt in zip(ids,counts) if cnt>=MINCHAIN and span[rt]>=70}
pk=ndi.binary_dilation(pinkish,iterations=12); inpink=pk[cy.astype(int),cx.astype(int)]
canton={rt for rt in keep if inpink[roots==rt].mean()>0.5}
el=sum(np.hypot(cx[i]-cx[j],cy[i]-cy[j]) for i,j in edges+bridges if roots[i] in keep)
print('bridges',len(bridges),'chains kept',len(keep),'canton',len(canton),'village?',len(keep)-len(canton),'drawn length px %.0f'%el)
small=Image.fromarray((np.asarray(Image.fromarray(rgb).resize((rgb.shape[1]//2,rgb.shape[0]//2)))*0.35+255*0.65).astype(np.uint8))
dr=ImageDraw.Draw(small)
for lst,w in [(edges,3),(bridges,3)]:
    for i,j in lst:
        if roots[i] not in keep: continue
        col=(255,120,0) if roots[i] in canton else ((0,150,60) if lst is bridges else (200,0,60))
        dr.line([(cx[i]/2,cy[i]/2),(cx[j]/2,cy[j]/2)],fill=col,width=w)
small.save(out,quality=88)
