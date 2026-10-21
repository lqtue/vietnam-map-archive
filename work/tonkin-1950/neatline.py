# Neatline of a Tonkin 1950 sheet as tilted lines, each half of a fold-out fitted on its own.
# A neatline is a thin dark line with paper on both sides: a ridge, so a thick binding band or the
# page edge (a step, not a ridge) cannot pass for one. Returns a 6-point mask (TL TM TR BR BM BL).
import numpy as np, sys, json
from PIL import Image
D=6          # px either side of the line that must be paper (quarter-res scans, ~2900 px wide)
CONTRAST=30  # grey levels the paper must be brighter than the line
ANG=np.arange(-2.5,2.51,0.05)
INNER=0.6    # an inner line counts if it is this fraction as strong as the best
INNER_MIN=1.0  # ...and at least this strong (a 5 px window, so 1.0 = a line on 20% of the rows); a faint
             # best line is kept as is, or contour lines inside it would win
REACH=150    # px inward of the best line to look for it

def ridge(path):
    v=np.asarray(Image.open(path).convert('RGB')).max(-1).astype(np.int16)  # black is dark; red and blue ink are not
    rx=np.minimum(np.roll(v,D,1),np.roll(v,-D,1))-v   # across a near-vertical line
    ry=np.minimum(np.roll(v,D,0),np.roll(v,-D,0))-v   # across a near-horizontal line
    return rx>CONTRAST, ry>CONTRAST

def find(m, lo, hi, a0, a1, inward):
    """Near-vertical line x = x0 + t*(y-ymid) with x0 in [lo,hi), over rows a0:a1 of mask m: the best
    line, then the innermost line (toward the map, inward=+1 left/top, -1 right/bottom) that is
    nearly as strong, since a thick bar or an outer frame can sit outside the neatline.
    Returns (coverage, angle deg, x at ymid, ymid)."""
    yy,xx=np.nonzero(m[a0:a1]); yy=yy+a0; ym=(a0+a1)/2; prof=[]
    for ang in ANG:
        sh=np.round((yy-ym)*np.tan(np.radians(ang))).astype(int)
        p=np.bincount(xx-sh+400,minlength=m.shape[1]+800)/(a1-a0)
        # a line is ~3 px wide: sum a 5 px window so one thick bar does not beat a thin straight one
        prof.append(np.convolve(p,np.ones(5),'same')[lo+400:hi+400])
    prof=np.array(prof); a,i=np.unravel_index(prof.argmax(),prof.shape); best=prof[a,i]
    cand=[(ANG[b],j) for b in range(len(ANG)) if abs(ANG[b]-ANG[a])<=0.4
          for j in np.nonzero(prof[b]>=max(INNER*best,INNER_MIN))[0] if prof[b,j]==prof[b,max(0,j-8):j+9].max()
          and 0<=inward*(j-i)<=REACH]
    ang,j=max(cand,key=lambda c:(inward*c[1],prof[list(ANG).index(c[0]),c[1]])) if cand else (ANG[a],i)
    return (prof[list(ANG).index(ang),j],ang,lo+j,ym)

def refine(m, c, a0, a1):
    """Least-squares x = x0 + t*(y-ymid) through the mask points within 5 px of the coarse line."""
    cov,ang,x0,ym=c; yy,xx=np.nonzero(m[a0:a1]); yy=yy+a0
    t=np.tan(np.radians(ang)); near=np.abs(xx-(x0+(yy-ym)*t))<=5
    yy,xx=yy[near],xx[near]
    for _ in range(3):
        A=np.c_[np.ones_like(yy),yy-ym]; (b0,b1),*_=np.linalg.lstsq(A,xx,rcond=None)
        keep=np.abs(xx-(b0+b1*(yy-ym)))<=2
        if keep.sum()<20: break
        yy,xx=yy[keep],xx[keep]
    return b0,b1,ym      # x = b0 + b1*(y-ym)

def edge(m, lo, hi, a0, a1, inward):
    c=find(m,lo,hi,a0,a1,inward); return c[0],refine(m,c,a0,a1)

def sheet(path):
    rx,ry=ridge(path); H,W=rx.shape
    # vertical edges: left/right, each over the full height (a fold-out's vertical fold is where the
    # top and bottom edges break, the left and right edges stay one line each)
    L=edge(rx,0,W//5,H//20,H-H//20,1); R=edge(rx,4*W//5,W,H//20,H-H//20,-1)
    # horizontal edges, found on the transpose; each half on its own
    ryt=ry.T; HT=ryt.shape[0]
    out=dict(L=L,R=R)
    xl=L[1][0]; xr=R[1][0]; xm=(xl+xr)/2
    for name,lo,hi,inw in (('T',0,H//6,1),('B',5*H//6,H,-1)):
        for half,(a0,a1) in (('l',(int(xl)+40,int(xm)-60)),('r',(int(xm)+60,int(xr)-40))):
            out[name+half]=edge(ryt,lo,hi,a0,a1,inw)
    return out,(W,H)

def x_at(l,y): b0,b1,ym=l[1]; return b0+b1*(y-ym)
def y_at(l,x): b0,b1,xm=l[1]; return b0+b1*(x-xm)
def corner_v_h(v,h):
    """Intersect x = v(y) with y = h(x) by iteration."""
    y=y_at(h,x_at(v,0))
    for _ in range(5): x=x_at(v,y); y=y_at(h,x)
    return x,y
def mask6(e):
    TL=corner_v_h(e['L'],e['Tl']); TR=corner_v_h(e['R'],e['Tr'])
    BL=corner_v_h(e['L'],e['Bl']); BR=corner_v_h(e['R'],e['Br'])
    xm=(e['L'][1][0]+e['R'][1][0])/2
    TM=(xm,(y_at(e['Tl'],xm)+y_at(e['Tr'],xm))/2); BM=(xm,(y_at(e['Bl'],xm)+y_at(e['Br'],xm))/2)
    return [TL,TM,TR,BR,BM,BL]

MIN_COVER=0.5   # every edge must reach this; below it the sheet goes to a person (Vĩnh Bắc Việt: blank sea)

if __name__=='__main__':
    # usage: neatline.py <dir of <map id>.jpg scans> -> masks.json (6-point polygons in full-res px)
    d=sys.argv[1]; HERE=__file__.rsplit('/',1)[0]; out={}
    for r in json.load(open(f'{HERE}/sheets.json')):
        e,(W,H)=sheet(f"{d}/{r['map_id']}.jpg")
        s=json.load(open(f"{HERE}/annotations-live/{r['map_id']}.json"))['target']['source']['width']/W
        weak=[k for k,v in e.items() if v[0]<MIN_COVER]
        out[r['sheet']]=dict(map_id=r['map_id'],weak_edges=weak,
            polygon=None if weak else [[round(x*s),round(y*s)] for x,y in mask6(e)])
        print(r['sheet'],'-> Tue' if weak else 'ok',weak)
    json.dump(out,open(f'{HERE}/masks.json','w'),indent=1)
