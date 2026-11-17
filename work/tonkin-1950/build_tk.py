# Tonkin 1950 drafts: GCPs at the 0.2-grade graticule crossings (Paris meridian), shifted by the
# series-wide offset measured on 9 control points; mask = detected neatline.
import json, sys, numpy as np
HERE=__file__.rsplit('/',1)[0]; sys.path.insert(0, HERE)
sys.path.insert(0, __file__.rsplit('/',3)[0]+'/scripts/lib')
from georef_annotation import annotation
from tk_fit import FR, GRID, S
from extents import good, cr
PARIS=2.33722917
DE, DN = 438/(111000*np.cos(np.radians(21))), 51/111000   # offset.py, n=9
# one series frame: neighbours' measured edges averaged (extents.py), so masks share their seams
XE=[114.36,114.90,115.44,115.978,116.524]; YE=[23.941,23.307,22.677,22.046]
FR.update({'viet-tri':(90,)+FR['viet-tri'][1:], 'hoa-binh':(96,)+FR['hoa-binh'][1:]})
geo=lambda gx,gy:(round(gx*0.9+PARIS+DE,6), round(gy*0.9+DN,6))
rows={r['slug'].replace('ban-do-hanh-chinh-cac-tinh-trung-chau-bac-viet-',''):r for r in json.load(open(f'{S}/rows.json'))}
out=[]
for k,(c,r) in GRID.items():
    row=rows[k]; info=json.load(open(f'{S}/thumbs/tk-{k}.info.json')); w,h=info['width'],info['height']
    keep,M,_=good(cr[k])
    L,R,T,B=[4*v for v in FR[k]]
    if M is not None and len(keep)>=4:
        gcps=[((4*x,4*y),geo(cc['gx'],cc['gy'])) for cc in keep for x,y in [cc['px']]]
        how=f'{len(keep)} graticule crossings'
        A=np.array([[cc['gx'],cc['gy'],1] for cc in keep]); P=np.array([cc['px'] for cc in keep],float)*4
        Mi,*_=np.linalg.lstsq(A,P,rcond=None)
        mask=[tuple(np.array([gx,gy,1])@Mi) for gx,gy in [(XE[c],YE[r]),(XE[c+1],YE[r]),(XE[c+1],YE[r+1]),(XE[c],YE[r+1])]]
    else:
        mask=[(L,T),(R,T),(R,B),(L,B)]
        gcps=list(zip(mask,[geo(XE[c],YE[r]),geo(XE[c+1],YE[r]),geo(XE[c+1],YE[r+1]),geo(XE[c],YE[r+1])]))
        how='4 neatline corners from the series frame (vertical grid lines too faint)'
    mask=[(min(max(x,0),w-1),min(max(y,0),h-1)) for x,y in mask]
    ann=annotation(row['iiif_image'],w,h,gcps,mask)
    json.dump(ann,open(f'{HERE}/annotations/{row["id"]}.json','w'),indent=1)
    out.append(dict(sheet=k,map_id=row['id'],gcps=len(gcps),how=how)); print(k,how)
json.dump(out,open(f'{HERE}/sheets.json','w'),indent=1,ensure_ascii=False)
