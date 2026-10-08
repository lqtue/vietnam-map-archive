"""go.py TAG SCALE_K ZONE x0 x1 y0 y1 xref Eref yref Nref   (px in upright frame; Eref/Nref km of the gridline nearest xref/yref; N decreases downward)
 detects ridge peaks in the box, keeps the 10 km progression, writes grid/gcpTAG.json, prints lines."""
import sys,os,json,numpy as np
THR=float(os.environ.get('THR',12))
from PIL import Image
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks
from scipy.ndimage import binary_opening
Image.MAX_IMAGE_PIXELS=None
tag=sys.argv[1];k=int(sys.argv[2]);zone=int(sys.argv[3]);x0,x1,y0,y1=map(int,sys.argv[4:8]);xref,Eref,yref,Nref=map(float,sys.argv[8:12])
from common import WORK, to_lonlat
S=WORK
img=Image.open(S+f'up/{tag}.jpg').convert('L');W,H=img.size;s=4
g=np.asarray(img.resize((W//s,H//s),Image.BOX),dtype=np.float32)
def rot(gimg,phi):
    h,w=gimg.shape;c=np.array([w/2,h/2]);cs_,sn=np.cos(phi),np.sin(phi)
    a,b,d,e=cs_,-sn,sn,cs_;cx=c[0]-(a*c[0]+b*c[1]);cy=c[1]-(d*c[0]+e*c[1])
    im=Image.fromarray(gimg.astype(np.uint8)).transform((w,h),Image.AFFINE,(a,b,cx,d,e,cy),Image.BILINEAR,fillcolor=255)
    return np.asarray(im,dtype=np.float32)
def vscore(gr):
    sub=gr[y0//s:y1//s,x0//s:x1//s];r=np.clip(uniform_filter1d(sub,41,axis=1)-sub,0,None)>THR
    c=r.sum(0).astype(float);return (c**2).sum()
best=(vscore(g),0.0)
for deg in np.arange(-2.0,2.01,0.1):
    if abs(deg)<1e-9:continue
    sc=vscore(rot(g,np.radians(deg)))
    if sc>best[0]:best=(sc,deg)
for deg in np.arange(best[1]-0.1,best[1]+0.101,0.025):
    sc=vscore(rot(g,np.radians(deg)))
    if sc>best[0]:best=(sc,deg)
PHI=np.radians(best[1]);print('deskew deg',round(best[1],3))
g0=g;g=rot(g,PHI) if abs(best[1])>0.03 else g
if g is g0:PHI=0.0
rv=np.clip(uniform_filter1d(g,41,axis=1)-g,0,None);rh=np.clip(uniform_filter1d(g,41,axis=0)-g,0,None)
cs=binary_opening(rv[y0//s:y1//s,x0//s:x1//s]>THR,np.ones((60,1))).sum(0);rs=binary_opening(rh[y0//s:y1//s,x0//s:x1//s]>THR,np.ones((1,60))).sum(1)
step0=2354*100/k
def prog(sig,off,span):
    pk,_=find_peaks(sig,height=sig.max()*0.1,distance=int(step0*0.5/s));pos=pk*s+off
    best=None
    for st in np.arange(step0*0.97,step0*1.03,step0*0.0005):
        for p0 in pos:
            sc=(abs(((pos-p0+st/2)%st)-st/2)<14).sum()
            if best is None or sc>best[0]:best=(sc,st,p0)
    sc,st,p0=best;kk=np.round((pos-p0)/st);ok=abs(pos-(p0+kk*st))<14
    b,a=np.polyfit(kk[ok],pos[ok],1)
    return pos[ok],kk[ok],a,b,len(pos)
def prog_mf(sig,off):
    sm=np.convolve(sig,np.ones(3),'same');L=len(sig);best=None
    for st in np.arange(step0*0.985,step0*1.015,step0*0.001):
        stp=st/s;n=int(L/stp)
        for ph in np.arange(0,stp,0.5):
            idx=(ph+stp*np.arange(n+1)).astype(int);idx=idx[idx<L-1]
            sc=sm[idx].sum()
            if best is None or sc>best[0]:best=(sc,stp,ph)
    sc,stp,ph=best;a=ph*s+off;b=stp*s
    pos=np.array([a+b*i for i in range(int(L/stp)+1)]);kk=np.arange(len(pos),dtype=float)
    vals=np.array([sm[max(0,int((p-off)/s)-1):int((p-off)/s)+2].max() if 0<=int((p-off)/s)<L else 0 for p in pos])
    ok=vals>0.3*np.median(vals)
    return pos[ok],kk[ok],a,b,len(pos)
def prog_lock(sig,off,ref,stp_px):
    sm=np.convolve(sig,np.ones(3),'same');L=len(sig)
    b=stp_px;a=ref
    for win in (70,35,18):
        idx=[];pp=[]
        lo=int(np.ceil((off-a)/b));hi=int(np.floor((off+L*s-a)/b))
        for i in range(lo,hi+1):
            p=a+b*i;c=int((p-off)/s)
            if c<4 or c>=L-4:continue
            w=int(win/s);seg=sm[max(0,c-w):c+w+1];j=max(0,c-w)+int(seg.argmax())
            if seg.max()>0.3*np.median(sm[sm>0]) :idx.append(i);pp.append(j*s+off)
        bb,aa=np.polyfit(idx,pp,1);a,b=aa,bb
    pos=np.array([a+b*i for i in range(lo,hi+1)]);return pos,np.arange(lo,hi+1,dtype=float),a,b,len(pos)
def axis(sig,off,ref,Eref):
    if os.environ.get('LOCK'):
        pos,kk,a,b,n=prog_lock(sig,off,ref,float(os.environ['LOCK']))
        lo=int(np.ceil((off-a)/b));hi=int(np.floor((off+len(sig)*s-a)/b))
        full=[a+b*i for i in range(lo,hi+1) if off+4*s<a+b*i<off+(len(sig)-4)*s]
        near=int(np.argmin([abs(p-ref) for p in full]));return full,near,b,len(full),len(full)
    try:pos,kk,a,b,n=prog(sig,off,0)
    except Exception:pos=np.array([]);kk=pos;a=b=n=0
    exp_n=len(sig)*s/step0
    if len(pos)<0.7*exp_n or os.environ.get('MF'):
        pos,kk,a,b,n=prog_mf(sig,off)
        bb,aa=np.polyfit(kk,pos,1);a,b=aa,bb
    lo=int(np.ceil((off-a)/b));hi=int(np.floor((off+len(sig)*s-a)/b))
    full=[]
    for i in range(lo,hi+1):
        p=(a+b*i-off)/s;j=int(round(p))
        inside=kk.min()<=i<=kk.max()
        if 2<=j<len(sig)-2 and (inside or sig[max(0,j-3):j+4].max()>=0.1*sig.max()):full.append(a+b*i)
    near=int(np.argmin([abs(p-ref) for p in full]))
    return full,near,b,len(pos),n
vx,nx,bx,mx,tx=axis(cs,x0,xref,Eref);hy,ny,by,my,ty=axis(rs,y0,yref,Nref)
print(tag,'vx',len(vx),'step',round(bx,1),f'{mx}/{tx} peaks','hy',len(hy),'step',round(by,1),f'{my}/{ty}')
print('vx',[round(v) for v in vx]);print('hy',[round(v) for v in hy])
E=[Eref+10*(i-nx) for i in range(len(vx))];N=[Nref-10*(i-ny) for i in range(len(hy))]
gc=[]
for j,y in enumerate(hy):
    for i,x in enumerate(vx):
        lo,la=to_lonlat(zone,E[i],N[j]);X=x/s-g.shape[1]/2;Y=y/s-g.shape[0]/2;xo=(np.cos(PHI)*X-np.sin(PHI)*Y+g.shape[1]/2)*s;yo=(np.sin(PHI)*X+np.cos(PHI)*Y+g.shape[0]/2)*s
        gc.append({'px':[round(float(xo),1),round(float(yo),1)],'lonlat':[lo,la]})
json.dump(gc,open(S+f'grid/gcp{os.environ.get("OUT",tag)}.json','w'))
print('E',E[0],'..',E[-1],'N',N[0],'..',N[-1],'| lon',round(gc[0]['lonlat'][0],3),'..',round(gc[-1]['lonlat'][0],3),'lat',round(gc[0]['lonlat'][1],3),'..',round(gc[-1]['lonlat'][1],3),len(gc),'gcps')
