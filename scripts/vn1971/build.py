"""build.py TAG MAP_ID -> annotations/<MAP_ID>.json (thin-plate spline, neatline mask) + allmaps/maskTAG.png.
Store it with georef_write.mjs --method utm-grid (see store.sh); nothing is sent from here."""
import sys,os,json,urllib.request,numpy as np
from PIL import Image,ImageDraw
Image.MAX_IMAGE_PIXELS=None
tag,mid=sys.argv[1],sys.argv[2]
from common import WORK
S=WORK
g=json.load(open(S+f'grid/gcp{tag}.json'))
base=f'https://iiif.maparchive.vn/iiif/{mid}'
info=json.load(urllib.request.urlopen(urllib.request.Request(base+'/info.json',headers={'User-Agent':'curl/8.7.1'}),timeout=60))
W,H=info['width'],info['height']
img=Image.open(S+f'up/{tag}.jpg');assert img.size==(W,H),(img.size,W,H)
f=4;a=np.asarray(img.convert('L').resize((W//f,H//f),Image.BOX),dtype=np.float32)
xs=sorted({p['px'][0] for p in g});ys=sorted({p['px'][1] for p in g})
def cell(v):  # px per 10 km: the sorted GCP coordinates cluster per gridline (the scan is a little skewed)
    c=[[v[0]]]
    for x in v[1:]:
        if x-c[-1][-1]>200:c.append([x])
        else:c[-1].append(x)
    m=[np.mean(k) for k in c];return float(np.median(np.diff(m)))
stx=cell(xs);sty=cell(ys)
def first_line(prof,lo,hi):
    # prof indexed by small px; scan lo..hi (small px, may run either direction); first local peak above 60% of window max
    idx=range(lo,hi,1 if hi>lo else -1);v=[prof[i] for i in idx];m=max(v)
    for k,i in enumerate(idx):
        if v[k]>=0.6*m and (k+1==len(v) or v[k+1]<=v[k]):return i
mid_y=slice(int(ys[0]/f),int(ys[-1]/f));mid_x=slice(int(xs[0]/f),int(xs[-1]/f))
px=(255-a[mid_y,:]).mean(0);py=(255-a[:,mid_x]).mean(1)
sm=lambda p:np.convolve(p,np.ones(3)/3,'same')
px,py=sm(px),sm(py)
OVR=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'masks.json'))).get(tag,{})
EW=float(os.environ.get('EDGEWIN',OVR.get('edgewin',1.0)));w=int(EW*stx/f);wy=int(EW*sty/f);t=int(0.15*stx/f);ty=int(0.15*sty/f)
# the map frame is the outermost line (>= 30% of the strongest ink in the window, so a thin inner
# neatline counts) between 0.15 and 1.0 cell outside the outer gridline, then the lines within 0.1 cell
# of it (the frame is two lines); none found -> 0.1 cell out.
# (it used to be pushed out to 0.45 cell regardless, which put paper margin and footer text inside the mask)
def edge(prof,pos,w,dirn,t,cell):
    c=int(pos/f);lo=c+dirn*t;hi=c+dirn*w
    seg=range(max(1,min(lo,hi)),min(len(prof)-2,max(lo,hi))+1)  # the window may run off the scan
    if len(seg)<3:return pos+dirn*0.1*cell
    m=max(prof[i] for i in range(c-3,c+4))
    floor=max(0.3*m,2*float(np.median([prof[i] for i in seg])))  # clear of the noise from map detail
    cands=[i for i in seg if prof[i]>=floor and prof[i]>=prof[i-1] and prof[i]>=prof[i+1]]
    if not cands:return pos+dirn*0.1*cell
    cands.sort(key=lambda i:dirn*i);e=cands[0]
    for i in cands[1:]:  # thick outer frame = the next lines out, but a table rule further out is not
        if abs(i-e)<=0.1*cell/f:e=i
    return e*f
L=edge(px,xs[0],w,-1,t,stx);R=edge(px,xs[-1],w,1,t,stx);T=edge(py,ys[0],wy,-1,ty,sty);B=edge(py,ys[-1],wy,1,ty,sty)
import os
L=max(L,0);T=max(T,0);R=min(R,W);B=min(B,H)
MASK=os.environ.get('MASK',OVR.get('mask'))
if MASK:  # L,T,R,B in px; an empty entry keeps the detected side
    L,T,R,B=[float(v) if v else d for v,d in zip(MASK.split(','),(L,T,R,B))]
mask=[[L,T],[R,T],[R,B],[L,B]]
POLY=os.environ.get('MASKPOLY',OVR.get('poly'))
if POLY:  # vertices read off a preview of the scan; MASKSCALE = scan px per preview px
    k_=float(os.environ.get('MASKSCALE',OVR.get('scale',1)));mask=[[float(a)*k_,float(b)*k_] for a,b in (p.split(',') for p in POLY.split(';'))]
print(tag,W,H,'mask',mask,'grid',xs[0],xs[-1],ys[0],ys[-1])
from lib.georef_annotation import annotation
os.makedirs(S+'annotations',exist_ok=True)
ann=annotation(base,W,H,[((q['px'][0],q['px'][1]),tuple(q['lonlat'])) for q in g],mask,{"type":"thinPlateSpline"},ndigits=1)
json.dump(ann,open(S+f'annotations/{mid}.json','w'),indent=1)
p=img.resize((1600,int(1600*H/W)));d=ImageDraw.Draw(p);k=1600/W
d.polygon([(x*k,y*k) for x,y in mask],outline=(255,0,0),width=3)
for q in g:d.ellipse([q['px'][0]*k-3,q['px'][1]*k-3,q['px'][0]*k+3,q['px'][1]*k+3],fill=(0,0,255))
p.save(S+f'allmaps/mask{tag}.png')
