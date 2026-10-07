import json,urllib.request,collections,concurrent.futures as cf
rows=json.load(open('georef_rows2.json'))
def probe(x):
    for i in {x['r2id'],x['allmaps_id']}-{None}:
        rq=urllib.request.Request(f"https://annotations.allmaps.org/images/{i}",headers={'User-Agent':'curl/8.7.1'})
        try:
            if urllib.request.urlopen(rq,timeout=15).status==200:return True
        except Exception as e:
            if getattr(e,'code',0)!=404:return 'err'
    return False
with cf.ThreadPoolExecutor(12) as ex: res=list(ex.map(probe,rows))
for x,r in zip(rows,res):x['in']=r
json.dump(rows,open('georef_rows2.json','w'))
print(collections.Counter((x['status'],x['in']) for x in rows))
