"""province_mask.py TAG [OUTDIR] -> province polygon from colour: the target province is printed on bare
paper, its neighbours and the sea are tinted. Median-blur away lines and text, threshold the lightness
(Otsu) inside the stored neatline, keep the biggest bare-paper blob, trace it.
Needs numpy scipy opencv. Prints resourceMask as JSON (scan px); with OUTDIR also writes maskTAG.png
(the polygon over a preview). province_hints.json holds per-sheet fixes. Nothing is stored or sent. Test tool: not wired into build.py yet."""
import sys,os,re,json,numpy as np,cv2
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
WORK=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','work','vn1971')+'/'  # common.py would pull in GDAL
tag=sys.argv[1];out=sys.argv[2] if len(sys.argv)>2 else None
mid={m['sheet_number']:m['id'] for m in json.load(open(WORK+'maps.json'))}[tag]
sel=json.load(open(WORK+f'annotations/{mid}.json'))['items'][0]['target']['selector']['value']
neat=np.array([[float(v) for v in p.split(',')] for p in re.search(r'points="([^"]+)"',sel).group(1).split()])
img=Image.open(WORK+f'up/{tag}.jpg');W,H=img.size;f=8
a=np.asarray(img.resize((W//f,H//f),Image.BOX)).astype(np.float32)
hint={} if os.environ.get('NOHINT') else json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'province_hints.json'))).get(tag,{})  # med: median size; cut: polygons (x,y in a 2000 px wide preview) where a white neighbour leaks in
L=ndi.median_filter(a.mean(-1),size=hint.get('med',15))  # ponytail: grey only; a hue term if a sheet's tint is as light as paper
box=np.zeros(L.shape,np.uint8);cv2.fillPoly(box,[(neat/f).astype(np.int32)],1)
g4f=np.asarray(img.convert('L').resize((W//4,H//4),Image.BOX)).astype(np.float32)  # inner frame: the innermost line of the leading cluster of dark lines from each side
bx0,by0=neat.min(0)/4;bx1,by1=neat.max(0)/4;bw,bh=bx1-bx0,by1-by0
def line_at(prof,lo,step,span):  # prof: darkness by position; scan from lo in direction step; return the inner line of the first cluster
    idx=np.arange(len(prof));pk=[i for i in idx[1:-1] if prof[i]>=prof[i-1] and prof[i]>=prof[i+1] and prof[i]>0.35*prof.max()]
    pk=sorted(pk,key=lambda i:step*i)
    if not pk:return None
    first=pk[0];cl=[i for i in pk if abs(i-first)<span];return max(cl,key=lambda i:step*i)
ys_=slice(int(by0+0.2*bh),int(by1-0.2*bh));xs_=slice(int(bx0+0.2*bw),int(bx1-0.2*bw))
win=int(0.07*min(bw,bh));fr=[bx0,by0,bx1,by1]
pc=(255-g4f[ys_,:]).mean(0);pr=(255-g4f[:,xs_]).mean(1);sp=0.045*min(bw,bh)
for k,(prof,lo,hi,step) in enumerate(((pc,bx0-win/2,bx0+win,1),(pr,by0-win/2,by0+win,1),(pc,bx1-win,bx1+win/2,-1),(pr,by1-win,by1+win/2,-1))):
    lo,hi=int(max(lo,0)),int(min(hi,len(prof)-1));q=line_at(prof[lo:hi],0,step,sp)
    if q is not None:fr[k]=lo+q
frame=np.array(fr)*4/f  # frame rect in small (f=8) px
fb=np.zeros(L.shape,np.uint8);cv2.rectangle(fb,(int(frame[0]),int(frame[1])),(int(frame[2]),int(frame[3])),1,-1)
box=(box&fb).astype(np.uint8)
v=L[(box>0)&(L>215)].astype(np.uint8);  # paper-bright pixels only: rivers, frame and title would drag Otsu down
t=cv2.threshold(v.reshape(-1,1),0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[0]
white=((L>t)&(box>0)).astype(np.uint8)
k=W/2000/f  # hint px -> small px
for c in hint.get('cut',[]):cv2.fillPoly(white,[(np.array(c)*k).astype(np.int32)],0)
white[cv2.dilate((a.mean(-1)<120).astype(np.uint8),np.ones((3,3),np.uint8))>0]=0  # bold black borders (name plate, legend, tables) fence off their white insides
a4=np.asarray(img.resize((W//4,H//4),Image.BOX)).astype(np.float32);g4=a4.mean(-1);rb=a4[...,0]-a4[...,2]
ln=((g4<224)&(g4>110)&(abs(a4[...,0]-a4[...,1])<12)&(rb>2)&(rb<40)).astype(np.uint8)  # the printed province/country line: thick neutral olive-grey dashes; roads are red, rivers blue, grid and district lines too thin
ln=cv2.morphologyEx(ln,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
ln=cv2.morphologyEx(ln,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(21,21)))  # joins dashes across their gaps
nl,ll,sl,_=cv2.connectedComponentsWithStats(ln);ln=np.isin(ll,[i for i in range(1,nl) if sl[i,cv2.CC_STAT_AREA]>600]).astype(np.uint8)  # keep long chains only
wall=cv2.dilate(cv2.resize(ln,(white.shape[1],white.shape[0]),interpolation=cv2.INTER_AREA),np.ones((3,3),np.uint8))>0
if not os.environ.get('NOWALL'):white[wall]=0
white=cv2.morphologyEx(white,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(41,41)))  # cuts the paper strip between the two frames, and necks under ~330 scan px
n,lab,st,_=cv2.connectedComponentsWithStats(white)
areas=st[1:,cv2.CC_STAT_AREA];main=1+np.argmax(areas);big=(lab==main).astype(np.uint8)
for i in range(1,n):  # other blobs = pieces a river cut off, unless they are boxes (plate, legend, tables)
    if i==main or st[i,cv2.CC_STAT_AREA]<0.02*areas.max():continue
    m=ndi.binary_fill_holes(lab==i).astype(np.uint8);c=max(cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)[0],key=cv2.contourArea)
    if m.sum()/(cv2.contourArea(cv2.boxPoints(cv2.minAreaRect(c)))+1)>0.7:continue
    pa=np.argwhere(big);pb=np.argwhere(m);d,j=cKDTree(pa).query(pb);k_=np.argmin(d)  # ponytail: nearest pair, straight 3 px bridge; Allmaps takes one ring
    if d[k_]>hint.get('gap',60):continue  # 60 small px = 480 scan px: a river, not another part of the sheet; hint 'gap' widens it
    t_=np.zeros_like(big);cv2.line(t_,tuple(pa[j[k_]][::-1].tolist()),tuple(pb[k_][::-1].tolist()),1,3)
    if (t_.astype(bool)&wall).any():continue  # the printed line lies between the two parts
    cv2.line(big,tuple(pa[j[k_]][::-1].tolist()),tuple(pb[k_][::-1].tolist()),1,3);big|=m
if 'grow' in hint:  # aged paper: grow into paper up to 'grow' levels darker than the threshold, never across the printed line or a bold border
    cand=((L>t-hint['grow'])&(box>0)&~wall&(cv2.dilate((a.mean(-1)<120).astype(np.uint8),np.ones((3,3),np.uint8))==0)).astype(np.uint8)
    cand=cv2.morphologyEx(cand,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(41,41)))
    nc,lc,_,_=cv2.connectedComponentsWithStats(cand);ids=np.unique(lc[(big>0)&(lc>0)]);big=np.isin(lc,ids[ids>0]).astype(np.uint8)|big
big=ndi.binary_fill_holes(cv2.morphologyEx(big,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(21,21)))).astype(np.uint8)  # close seals crease slits
big=(cv2.dilate(big,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))&box).astype(np.uint8)  # the wall ate its own half-width
bd=30;fx0,fy0,fx1,fy1=[int(v) for v in frame]  # extend to the frame where the mask runs within 30 small px (240 scan px) of it for at least 10% of that side; shorter touches are chance
def snap(lo,hi,band_from_start,get,put):
    near=np.array([get(k,band_from_start).any() for k in range(lo,hi+1)]);lab_,n_=ndi.label(near)
    for r in range(1,n_+1):
        ks=np.flatnonzero(lab_==r)
        if len(ks)>=0.1*(hi-lo):
            for k in ks+lo:put(k,band_from_start)
for start in (True,False):
    def get(k,st,start=start):return big[k,fx0:fx0+bd+1] if start else big[k,fx1-bd:fx1+1]
    def put(k,st,start=start):
        xs=np.flatnonzero(get(k,st))+(fx0 if start else fx1-bd)
        if start:big[k,fx0:xs.max()+1]=1
        else:big[k,xs.min():fx1+1]=1
    snap(fy0,fy1,start,get,put)
    def get(k,st,start=start):return big[fy0:fy0+bd+1,k] if start else big[fy1-bd:fy1+1,k]
    def put(k,st,start=start):
        ys=np.flatnonzero(get(k,st))+(fy0 if start else fy1-bd)
        if start:big[fy0:ys.max()+1,k]=1
        else:big[ys.min():fy1+1,k]=1
    snap(fx0,fx1,start,get,put)
big=(big&box).astype(np.uint8)
cs,_=cv2.findContours(big,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
poly=cv2.approxPolyDP(max(cs,key=cv2.contourArea),1.5,True)[:,0,:]*f  # 1.5 small px = 12 scan px
rest=cv2.morphologyEx(((L>t)&(box>0)&(big==0)).astype(np.uint8),cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(41,41)))  # bare paper in the frame the mask left out: a missing part, or a plate
nr,lr,sr,_=cv2.connectedComponentsWithStats(rest);miss=0
for i in range(1,nr):  # boxes (plate, legend, tables) are not missing parts
    m=ndi.binary_fill_holes(lr==i).astype(np.uint8);c=max(cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)[0],key=cv2.contourArea)
    if m.sum()/(cv2.contourArea(cv2.boxPoints(cv2.minAreaRect(c)))+1)<=0.7:miss+=sr[i,cv2.CC_STAT_AREA]
tint=((L<t-6)&(big>0)).sum()/big.sum()  # tinted paper inside the mask: a leak
print(f'sheet {tag}: Otsu {t:.0f}, {len(poly)} vertices, {big.sum()/box.sum():.0%} of neatline, left-out {miss/box.sum():.1%}, tinted-in {tint:.1%}, frame/stored {(frame[2]-frame[0])*(frame[3]-frame[1])*f*f/((neat[:,0].max()-neat[:,0].min())*(neat[:,1].max()-neat[:,1].min())):.2f}',file=sys.stderr)
print(json.dumps(poly.tolist()))
if out:
    p=np.asarray(img.resize((W//f,H//f),Image.BOX)).copy()
    cv2.polylines(p,[(poly//f).astype(np.int32)],True,(255,0,0),2);cv2.rectangle(p,(int(frame[0]),int(frame[1])),(int(frame[2]),int(frame[3])),(0,0,255),1);  # blue = detected inner frame
    Image.fromarray(p).save(os.path.join(out,f'mask{tag}.png'))
