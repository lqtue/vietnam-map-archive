# How neighbouring sheets meet: each sheet's mask (Tue's hand edit) placed on the ground through that
# sheet's own control points (order-1 polynomial, as Allmaps does). Gap > 0: bare ground between
# the two printed edges; < 0: the sheets overlap. Metres, measured across the seam at its two ends.
import json, re, math, numpy as np
HERE=__file__.rsplit('/',1)[0]
ids=json.load(open(f'{HERE}/allmaps-ids.json')); names={r['map_id']:r['sheet'] for r in json.load(open(f'{HERE}/sheets.json'))}
GRID={'viet-tri':(0,0),'ha-noi':(1,0),'bac-giang':(2,0),'an-chau':(3,0),'hoa-binh':(0,1),'hung-yen':(1,1),'hai-phong':(2,1),'quang-yen':(3,1),'ninh-binh':(1,2),'bui-chu':(2,2),'vinh-bac-viet':(3,2)}
R=6378137
def merc(lon,lat): return np.array([R*math.radians(lon), R*math.log(math.tan(math.pi/4+math.radians(lat)/2))])
def corners(pts):
    tl=min(pts,key=lambda p:p[0]+p[1]); br=max(pts,key=lambda p:p[0]+p[1]); tr=max(pts,key=lambda p:p[0]-p[1]); bl=min(pts,key=lambda p:p[0]-p[1]); return dict(TL=tl,TR=tr,BR=br,BL=bl)
G={}
for vid in ids:
    k=names[vid]; a=json.load(open(f'{HERE}/annotations-live/{vid}.json'))
    f=a['body']['features']; px=np.array([x['properties']['resourceCoords'] for x in f],float); mc=np.array([merc(*x['geometry']['coordinates']) for x in f])
    A=np.c_[px,np.ones(len(px))]; M,*_=np.linalg.lstsq(A,mc,rcond=None)
    res=np.hypot(*(A@M-mc).T)/1.0711
    pts=[[float(v) for v in p.split(',')] for p in re.search(r'points="([^"]+)"',a['target']['selector']['value']).group(1).split()]
    G[k]={c:np.r_[p,1]@M/1.0711 for c,p in corners(pts).items()}; G[k]['res']=res.max()   # metres on the ground
by={v:k for k,v in GRID.items()}
print('control-point fit, worst residual (m):',{k:round(float(G[k]['res'])) for k in G})
def seam(a,ea,b,eb,label,normal):
    # ea/eb: the two corners of the shared edge on each sheet; gap = mean separation along the normal
    d=[(G[b][eb[i]]-G[a][ea[i]]) for i in range(2)]
    s=[float(np.dot(x,normal)) for x in d]; t=[float(np.dot(x,[normal[1],-normal[0]])) for x in d]
    print(f'{label:28s} gap at ends {s[0]:+6.0f} {s[1]:+6.0f} m   slide along the seam {t[0]:+5.0f} {t[1]:+5.0f} m')
for (c,r),k in by.items():
    if (c+1,r) in by: seam(k,('TR','BR'),by[(c+1,r)],('TL','BL'),f'{k} | {by[(c+1,r)]}',[1,0])
    if (c,r+1) in by: seam(k,('BL','BR'),by[(c,r+1)],('TL','TR'),f'{k} / {by[(c,r+1)]}',[0,-1])
