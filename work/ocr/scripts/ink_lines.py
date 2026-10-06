import sys, os, numpy as np
from scipy import ndimage as ndi
from scipy.stats import spearmanr
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import ink_vs_labels as I
def one(MID):
    mid=MID
    m=I.get(f"maps?select=triage&id=eq.{mid}")[0]; nx,ny,nw,nh=m["triage"]["neatline"]
    img=Image.open(f"{I.SCR}/{mid[:8]}.png"); s=img.width/nw
    gray,ink,glyph,_,_=I.ink_maps(img)
    def line_fp(L,ang):
        k=np.zeros((L,L),bool); c=L//2
        for t in np.linspace(-c,c,4*L):
            k[int(round(c+t*np.sin(ang))),int(round(c+t*np.cos(ang)))]=True
        return k
    def remove_lines(ink,L=25,n=12):
        lines=np.zeros_like(ink)
        for a in np.arange(n)*np.pi/n:
            lines|=ndi.binary_opening(ink,structure=line_fp(L,a))
        return ink & ~ndi.binary_dilation(lines,iterations=1)
    def coherence(gray,sig=6):
        gx=ndi.sobel(gray,1);gy=ndi.sobel(gray,0)
        jxx=ndi.gaussian_filter(gx*gx,sig);jyy=ndi.gaussian_filter(gy*gy,sig);jxy=ndi.gaussian_filter(gx*gy,sig)
        return np.sqrt((jxx-jyy)**2+4*jxy**2)/(jxx+jyy+1e-6)
    C=I.CELL; H,W=gray.shape; gh,gw=H//C,W//C
    agg=lambda a:a[:gh*C,:gw*C].reshape(gh,C,gw,C).mean((1,3))
    nolines=remove_lines(ink)
    coh=coherence(gray)
    f={"ink_frac":agg(ink),"ink minus lines":agg(nolines),
       "ink minus lines, low-coherence":agg(nolines&(coh<0.6))}
    for status in ("validated","validated,pending"):
        ch=np.zeros((gh,gw))
        for r in I.labels(mid,status):
            j=int(((r["global_x"]+r["global_w"]/2-nx)*s)//C); i=int(((r["global_y"]+r["global_h"]/2-ny)*s)//C)
            if 0<=i<gh and 0<=j<gw: ch[i,j]+=len(r["text_corrected"] or r["text"] or "")
        print(status,{k:round(spearmanr(v.ravel(),ch.ravel())[0],2) for k,v in f.items()})
    print("ink removed as lines: %.0f%%"%(100*(1-nolines.sum()/ink.sum())))

for MID in sys.argv[1:]:
    print(MID[:8]); one(MID)
