# Score neatline.py against Tue's hand-edited Allmaps masks (annotations-live/): corner error in
# full-resolution px. None of the four edits fed the detector, so a pass here could have failed.
# usage: score.py <dir with <map id>.jpg quarter-res scans>
import json, re, sys, numpy as np
HERE=__file__.rsplit('/',1)[0]; sys.path.insert(0,HERE)
import neatline as n
ids=json.load(open(f'{HERE}/allmaps-ids.json')); names={r['map_id']:r['sheet'] for r in json.load(open(f'{HERE}/sheets.json'))}
EDITED=['viet-tri','ha-noi','bac-giang','an-chau']; TOL=15
for vid in ids:
    k=names[vid]
    try: e,(W,H)=n.sheet(f'{sys.argv[1]}/{vid}.jpg')
    except FileNotFoundError: continue
    t=json.load(open(f'{HERE}/annotations-live/{vid}.json'))['target']
    fw=t['source']['width']; s=fw/W
    tue=np.array([[float(v) for v in p.split(',')] for p in re.search(r'points="([^"]+)"',t['selector']['value']).group(1).split()])
    mine=np.array(n.mask6(e))[[0,2,3,5]]*s
    err=np.hypot(*(mine-tue).T)
    print(f"{k:14s} {'EDITED' if k in EDITED else 'unedited':8s} TL TR BR BL err px:",err.round(0),'PASS' if err.max()<=TOL else 'fail')
