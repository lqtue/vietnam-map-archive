import sys, math, urllib.request, io
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
w,s,e,n=map(float,sys.argv[1:5]); z=int(sys.argv[5]); out=sys.argv[6]
def tx(lon): return (lon+180)/360*2**z
def ty(lat): r=math.radians(lat); return (1-math.log(math.tan(r)+1/math.cos(r))/math.pi)/2*2**z
x0,x1=int(tx(w)),int(tx(e)); y0,y1=int(ty(n)),int(ty(s))
im=Image.new('RGB',((x1-x0+1)*256,(y1-y0+1)*256))
for x in range(x0,x1+1):
  for y in range(y0,y1+1):
    req=urllib.request.Request(f'https://tile.openstreetmap.org/{z}/{x}/{y}.png',headers={'User-Agent':'vma-georef-check/1.0 (research)'})
    im.paste(Image.open(io.BytesIO(urllib.request.urlopen(req,timeout=30).read())).convert('RGB'),((x-x0)*256,(y-y0)*256))
# crop to bbox & write geotiff via EPSG:3857
im.save(out+'.png')
def lon(x): return x/2**z*360-180
def lat(y): return math.degrees(math.atan(math.sinh(math.pi*(1-2*y/2**z))))
open(out+'.bounds','w').write(f"{lon(x0)} {lat(y1+1)} {lon(x1+1)} {lat(y0)}")
print(x0,x1,y0,y1)
