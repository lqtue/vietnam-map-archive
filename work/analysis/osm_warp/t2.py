from lib import *
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
x0,y0,w,h=2700,3600,1000,1000
gy,gx=np.mgrid[y0:y0+h:4,x0:x0+w:4]
X=gx.ravel().astype(float);Y=gy.ravel().astype(float)
B=np.load(SP/'ink_q.npy')
fig,ax=plt.subplots(1,3,figsize=(18,6))
ax[0].imshow(B[y0//4:(y0+h)//4,x0//4:(x0+w)//4],cmap='gray_r')
for a_,axx in ((40,ax[1]),(130,ax[2])):
    q=qlook(X,Y,np.full(len(X),a_)).reshape(gy.shape)
    axx.imshow(q,vmin=0,vmax=1); axx.set_title(f'Q dir {a_}')
s=load_samples(); m=(s['x']>x0)&(s['x']<x0+w)&(s['y']>y0)&(s['y']<y0+h)&(s['cls']!='service')
for axx in ax: axx.plot((s['x'][m]-x0)/4,(s['y'][m]-y0)/4,'r.',ms=2)
plt.savefig(SP/'t2.png',dpi=70)
