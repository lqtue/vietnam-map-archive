# Prediction that can fail: where the grid says two stacked sheets overlap, the same printed content must appear in both,
# at the position the grid predicts. Template-match a strip of the upper sheet's bottom inside the lower sheet's top.
# usage: overlap.py <scan dir> <upper> <lower>
import sys, numpy as np
from PIL import Image
from scipy.signal import fftconvolve
sys.path.insert(0,__file__.rsplit('/',1)[0]); import grid2 as G
SP,A,B=sys.argv[1:4]; WIN=int(sys.argv[4]) if len(sys.argv)>4 else 45
def img(s): return np.asarray(Image.open(f'{SP}/{G.ids[s]}.jpg').convert('RGB')).max(-1).astype(np.float32)
def ncc(win,pat):
    p=pat-pat.mean(); n=p.size; ones=np.ones_like(pat)
    num=fftconvolve(win,p[::-1,::-1],'valid'); s1=fftconvolve(win,ones,'valid'); s2=fftconvolve(win**2,ones,'valid')
    return num/(np.sqrt(np.maximum(s2-s1**2/n,1e-3))*np.sqrt((p**2).sum())+1e-9)
def interp_pos(pos,x):
    g=sorted(pos,key=lambda k:abs(pos[k]-x))[:2]; g0,g1=sorted(g); return g0+(x-pos[g0])*(g1-g0)/(pos[g1]-pos[g0])
def to_grade(gr,x,y):
    h='L' if x<gr['fold'] else 'R'
    return interp_pos({g:b0+b1*y for g,(b0,b1,*_) in gr['V'].items()},x), interp_pos({g:hv[h][0]+hv[h][1]*x for g,hv in gr['H'].items() if h in hv},y)
def from_grade(gr,gx,gy,x0,y0):
    x,y=x0,y0
    for _ in range(4):
        pos={g:b0+b1*y for g,(b0,b1,*_) in gr['V'].items()}; g0,g1=sorted(sorted(pos,key=lambda k:abs(k-gx))[:2]); x=pos[g0]+(gx-g0)*(pos[g1]-pos[g0])/(g1-g0)
        h='L' if x<gr['fold'] else 'R'; hp={g:hv[h][0]+hv[h][1]*x for g,hv in gr['H'].items() if h in hv}; q0,q1=sorted(sorted(hp,key=lambda k:abs(k-gy))[:2]); y=hp[q0]+(gy-q0)*(hp[q1]-hp[q0])/(q1-q0)
    return x,y
ga,gb=G.grid(A,SP),G.grid(B,SP); ia,ib=img(A),img(B)
pa=np.array(G.masks[A]['polygon'])/G.S; pb=np.array(G.masks[B]['polygon'])/G.S
print(f'{A} over {B}: frame overlap predicted by the grid')
hits=[]
for xa in np.linspace(pa[5][0]+250,pa[3][0]-250,9):
    ys=np.interp(xa,[pa[5][0],pa[3][0]],[pa[5][1],pa[3][1]])           # A's bottom edge at this column
    ta=ia[int(ys)-34:int(ys)-2,int(xa)-70:int(xa)+70]                  # template: the last 32 rows inside A
    gx,gy=to_grade(ga,xa,ys-18); xb,yb=from_grade(gb,gx,gy,xa,pb[0][1]+20)   # where the grid says it is in B
    edge_b=np.interp(xb,[pb[0][0],pb[2][0]],[pb[0][1],pb[2][1]])
    if yb-edge_b<-5: print(f'  x {xa:5.0f}: grid puts it {edge_b-yb:.0f} px above B\'s frame, no overlap here'); continue
    u0,v0=int(yb)-16-WIN,int(xb)-70-WIN; win=ib[max(int(edge_b)-3,u0):int(yb)-16+32+WIN,max(0,v0):int(xb)+70+WIN]; r0=max(int(edge_b)-3,u0); v0=max(0,v0)
    c=ncc(win,ta); j=np.unravel_index(c.argmax(),c.shape); dy=r0+j[0]-(int(yb)-16); dx=v0+j[1]-(int(xb)-70)
    c2=c.copy(); c2[max(0,j[0]-6):j[0]+7,max(0,j[1]-6):j[1]+7]=-1
    hits.append((dx,dy,float(c[j]),float(c2.max()))); print(f'  x {xa:5.0f}: predicted B px ({xb:.0f},{yb:.0f}); best match offset ({dx:+d},{dy:+d}) px = ({dx*G.M:+.0f},{dy*G.M:+.0f}) m, NCC {c[j]:.2f} (next best {c2.max():.2f})')
good=[h for h in hits if h[2]>0.6 and h[2]-h[3]>0.08]
print(f'{len(good)} of {len(hits)} strips matched confidently')
if good: print('median offset from the grid prediction: dx %+.0f dy %+.0f px (%+.0f, %+.0f m)'%(np.median([h[0] for h in good]),np.median([h[1] for h in good]),np.median([h[0] for h in good])*G.M,np.median([h[1] for h in good])*G.M))
