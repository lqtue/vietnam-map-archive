"""Pink (canton bands) and blue (water) by Lab distance from the paper colour.
Usage: colour.py <image> <out_dir> [pink_a* margin=8] [blue_b* margin=15]"""
import sys, numpy as np
from PIL import Image
from scipy import ndimage as ndi
src,out=sys.argv[1],sys.argv[2]
def lab(rgb):
    c=rgb/255.0; c=np.where(c>0.04045,((c+0.055)/1.055)**2.4,c/12.92)
    M=np.array([[0.4124,0.3576,0.1805],[0.2126,0.7152,0.0722],[0.0193,0.1192,0.9505]])
    xyz=c@M.T/np.array([0.95047,1.0,1.08883])
    f=np.where(xyz>0.008856,np.cbrt(xyz),7.787*xyz+16/116)
    return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],-1)
rgb=np.array(Image.open(src).convert('RGB')).astype(float)
L=lab(rgb); l,a,b=L[...,0],L[...,1],L[...,2]
pa,pb=np.median(a),np.median(b); print('paper a*,b* median %.1f %.1f'%(pa,pb))
for nm,arr in [('a*',a),('b*',b)]: print(nm,'pcts 1,5,50,95,99',np.percentile(arr,[1,5,50,95,99]).round(1))
thr_a=float(sys.argv[3]) if len(sys.argv)>3 else 8; thr_b=float(sys.argv[4]) if len(sys.argv)>4 else 15
pink=(a>pa+thr_a)&(l>55)
blue=(b<pb-thr_b)&(l>40)&(a<pa+2)
for name,m,col in [('pink',pink,(220,0,40)),('blue',blue,(0,60,220))]:
    m2=ndi.binary_opening(m,structure=np.ones((2,2)))
    lab_,n=ndi.label(m2,structure=np.ones((3,3)))
    sizes=np.sort(np.bincount(lab_.ravel())[1:])[::-1]
    print(name,'px %.2f%%'%(100*m2.mean()),'components',n,'largest',sizes[:6].tolist(),'top5 share %.0f%%'%(100*sizes[:5].sum()/max(1,sizes.sum())))
    ov=(rgb*0.3+255*0.7).astype(np.uint8); ov[m2]=col
    Image.fromarray(ov).save(f'{out}/{name}_overlay.jpg',quality=85)
