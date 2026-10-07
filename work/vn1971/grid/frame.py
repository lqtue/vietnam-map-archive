import sys, numpy as np
from PIL import Image
from scipy.signal import find_peaks
Image.MAX_IMAGE_PIXELS=None
img=Image.open(sys.argv[1]).convert('L'); W,H=img.size; s=8
g=np.asarray(img.resize((W//s,H//s),Image.BOX),dtype=np.float32); d=g<140
cs=d.sum(0); rs=d.sum(1)
vp,_=find_peaks(cs,height=cs.max()*0.45,distance=20); hp,_=find_peaks(rs,height=rs.max()*0.45,distance=20)
print(W,H,'v',[int(p*s) for p in vp],'h',[int(p*s) for p in hp])
