import sys, numpy as np
from PIL import Image
from scipy.signal import find_peaks
from scipy.ndimage import uniform_filter1d
Image.MAX_IMAGE_PIXELS=None
img=Image.open(sys.argv[1]).convert('L'); W,H=img.size
s=4; g=np.asarray(img.resize((W//s,H//s),Image.BOX),dtype=np.float32)
# ridge signal: local background (wide mean) minus pixel, along each axis
bgv=uniform_filter1d(g,41,axis=1); rv=np.clip(bgv-g,0,None)   # vertical lines show in x-direction
bgh=uniform_filter1d(g,41,axis=0); rh=np.clip(bgh-g,0,None)
# inside neatline box approx
x0,x1,y0,y1=[int(v) for v in sys.argv[2:6]]
cs=(rv[y0//s:y1//s, x0//s:x1//s]>12).sum(0); rs=(rh[y0//s:y1//s, x0//s:x1//s]>12).sum(1)
vp,_=find_peaks(cs,height=cs.max()*0.5,distance=100); hp,_=find_peaks(rs,height=rs.max()*0.5,distance=100)
print('v',[(int(p*s+x0),int(cs[p])) for p in vp]); print('h',[(int(p*s+y0),int(rs[p])) for p in hp])
