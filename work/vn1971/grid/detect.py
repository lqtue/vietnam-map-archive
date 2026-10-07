import sys, numpy as np
from PIL import Image
from scipy.signal import find_peaks
Image.MAX_IMAGE_PIXELS=None
img=Image.open(sys.argv[1]).convert('L'); W,H=img.size
s=4; g=np.asarray(img.resize((W//s,H//s),Image.BOX),dtype=np.float32)
dark=(g<150)
# vertical lines: columns with long dark runs; use column sums over interior
def peaks(sums,minfrac):
    p,_=find_peaks(sums,height=sums.max()*minfrac,distance=60)
    return p
cs=dark.sum(0); rs=dark.sum(1)
vx=peaks(cs,0.35); hy=peaks(rs,0.35)
print('size',W,H,'scale',s)
print('vert lines x(full px):',[int(v*s) for v in vx])
print('horz lines y(full px):',[int(h*s) for h in hy])
print('vals v',[int(cs[v]) for v in vx]); print('vals h',[int(rs[h]) for h in hy])
