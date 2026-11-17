# Cochinchina plates: mask = inside of the pink arrondissement border, at 1/4 scale.
import sys, json, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from shapely.geometry import box
from shapely.ops import unary_union
import os
S=os.environ['SERIES_WORK']   # thumbs/, med/ as for work/tonkin-1950
def pink(a):
    r,g,b=[a[...,i].astype(int) for i in range(3)]
    return (r>190)&(r-g>40)&(r-b>30)&(g<200)&(abs(g-b)<45)
def region(k, close=6, step=4):
    a=np.asarray(Image.open(f'{S}/med/cc-{k}.jpg').convert('RGB'))
    small=a[::2,::2].astype(float)            # 1/8 scale for the morphology
    g=small.mean(-1); paper=np.median(g)
    ink=(g<paper-35)|(np.abs(small[...,0]-small[...,2])-np.median(np.abs(small[...,0]-small[...,2]))>40)
    dens=ndi.uniform_filter(ink.astype(float),25)
    blank=dens<0.03
    lab,n=ndi.label(blank); sizes=ndi.sum(blank,lab,range(1,n+1))
    outside=lab==(1+int(np.argmax(sizes)))
    sys.path.insert(0, __file__.rsplit('/',2)[0]+'/tonkin-1950'); import frame as fr                 # neatline from thin dark lines on paper (the Tonkin detector)
    f,_=fr.frame(f'{S}/med/cc-{k}.jpg'); L,R,T,B=[f[s_][2]//2 for s_ in 'LRTB']; m_=12
    inner=np.zeros_like(outside); inner[T+m_:B-m_, L+m_:R-m_]=True
    q=ndi.binary_opening(~outside&inner,np.ones((3,3)),iterations=8)
    lab,n=ndi.label(q); sizes=ndi.sum(q,lab,range(1,n+1))
    filled=ndi.binary_fill_holes(lab==(1+int(np.argmax(sizes))))
    filled=np.kron(filled,np.ones((2,2),bool))[:a.shape[0],:a.shape[1]]
    lab,n=ndi.label(filled); sizes=ndi.sum(filled,lab,range(1,n+1))
    m=lab==(1+int(np.argmax(sizes)))
    sm=m[::step,::step]; boxes=[]
    for y,row in enumerate(sm):
        xs=np.flatnonzero(np.diff(np.r_[0,row.astype(int),0]))
        for x0,x1 in zip(xs[::2],xs[1::2]): boxes.append(box(x0*step,y*step,x1*step,(y+1)*step))
    poly=unary_union(boxes)
    if poly.geom_type!='Polygon': poly=max(poly.geoms,key=lambda g:g.area)
    poly=poly.simplify(6).exterior
    return a.shape, ink.mean(), m.mean(), list(poly.coords)
if __name__=='__main__':
    from PIL import ImageDraw
    out={}
    for k in sys.argv[1:]:
        shp,pf,mf,coords=region(k); out[k]=coords
        im=Image.open(f'{S}/med/cc-{k}.jpg').convert('RGB'); d=ImageDraw.Draw(im); d.line(coords+[coords[0]],fill=(0,90,255),width=8)
        im.thumbnail((900,900)); im.save(f'{S}/mask-{k}.jpg')
        print(k,'pink %.3f filled %.3f pts %d'%(pf,mf,len(coords)))
    json.dump(out,open(f'{S}/cc_masks.json','w'))
