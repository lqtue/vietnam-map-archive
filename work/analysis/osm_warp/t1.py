from lib import *
s=load_samples(); x,y,a,cls=s['x'],s['y'],s['ang'],s['cls']
ns=cls!='service'
for sg in (0,2):
  q0=qlook(x[ns],y[ns],a[ns],sg)
  print('sigma',sg,'unwarped mean Q',np.nanmean(q0),'nan',np.isnan(q0).mean())
  rng=np.random.default_rng(0)
  nul=[]
  for i in range(6):
    r=rng.uniform(100,250,2)*rng.choice([-1,1],2)
    nul.append(np.nanmean(qlook(x[ns]+r[0],y[ns]+r[1],a[ns],sg)))
  print(' null shifts', np.round(nul,3))
  # global translation best
  best=(0,0,0)
  for dy in range(-96,97,8):
    for dx in range(-96,97,8):
      v=np.nanmean(qlook(x[ns]+dx,y[ns]+dy,a[ns],sg))
      if v>best[0]: best=(v,dx,dy)
  print(' best global shift',best)
