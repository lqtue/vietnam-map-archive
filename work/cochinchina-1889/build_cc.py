# Cochinchina plates: mask-only drafts (no graticule to place them by); Tan An keeps its graticule annotation.
import json, sys, shutil
sys.path.insert(0, __file__.rsplit('/',1)[0]); sys.path.insert(0,__file__.rsplit('/',3)[0]+'/scripts/lib')
from georef_annotation import annotation
sys.path.insert(0, __file__.rsplit('/',2)[0]+'/tonkin-1950')
import frame as fr
import os
S=os.environ['SERIES_WORK']; HERE=__file__.rsplit('/',1)[0]; OUT=f'{HERE}/allmaps-drafts'
masks=json.load(open(f'{S}/cc_masks.json'))
OUTLINE_OK={'baria','gocong','bentre','tra-vinh','vinh-long','sa-dec','mytho'}   # judged by eye on the contact sheet
rows={r['slug'].replace('plan-topographique-de-l-arrondissement-de-',''):r for r in json.load(open(f'{S}/rows.json')) if 'arrondissement' in r['slug']}
log=[]
for k,row in rows.items():
    if k=='tan-an':
        shutil.copy(f'{HERE}/annotations/{row["id"]}.json', f'{OUT}/{row["id"]}.json')
        log.append(dict(plate=k,map_id=row['id'],mask='neatline (README)',gcps=24)); continue
    info=json.load(open(f'{S}/thumbs/cc-{k}.info.json')); w,h=info['width'],info['height']
    if k in OUTLINE_OK: poly=[(4*x,4*y) for x,y in masks[k][:-1]]; how='arrondissement outline (ink density)'
    else:
        f,_=fr.frame(f'{S}/med/cc-{k}.jpg'); L,R,T,B=[4*f[s][2] for s in 'LRTB']
        poly=[(L,T),(R,T),(R,B),(L,B)]; how='neatline box (outline not separable)'
    poly=[(min(max(x,0),w-1),min(max(y,0),h-1)) for x,y in poly]
    json.dump(annotation(row['iiif_image'],w,h,[],poly),open(f'{OUT}/{row["id"]}.json','w'),indent=1)
    log.append(dict(plate=k,map_id=row['id'],mask=how,gcps=0)); print(k,how,len(poly))
json.dump(log,open(f'{OUT}/../allmaps-drafts.json','w'),indent=1)
