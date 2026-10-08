import sys,json
from common import WORK
S=WORK+'grid/'
out=sys.argv[1];g=[]
for p in sys.argv[2:]:g+=json.load(open(S+f'gcp{p}.json'))
json.dump(g,open(S+f'gcp{out}.json','w'));print(out,len(g))
