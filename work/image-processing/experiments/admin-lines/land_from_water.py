"""Land from water on the 1882 plate: water = blurred b* below the paper's, land = the region reachable
from a seed without crossing water. The black quay band along a bank is land, so it is added after.
An optional straight closure line (modern, e.g. Kenh Te, dug 1904-07, is not on the plate) can shut a gap.
Usage: land_from_water.py <crop.png> <out_land.png> <seed_row,seed_col> [x0,y0,x1,y1 closure line]
Without a closure line the land stops where the water does (colour alone)."""
import sys, numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
src, out, seed = sys.argv[1], sys.argv[2], [int(v) for v in sys.argv[3].split(',')]
line = [int(v) for v in sys.argv[4].split(',')] if len(sys.argv) > 4 else None
rgb = np.array(Image.open(src).convert('RGB')).astype(float)
c = rgb/255.0; c = np.where(c > 0.04045, ((c+0.055)/1.055)**2.4, c/12.92)
xyz = c@np.array([[0.4124,0.3576,0.1805],[0.2126,0.7152,0.0722],[0.0193,0.1192,0.9505]]).T/np.array([0.95047,1.0,1.08883])
f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787*xyz+16/116)
b = 200*(f[..., 1]-f[..., 2])                                  # b*: blue is low
water = ndi.gaussian_filter(b, 6)-np.median(b) < -5            # blur merges the pale river hatching
cl = Image.new('L', rgb.shape[1::-1], 0)
if line: ImageDraw.Draw(cl).line([tuple(line[:2]), tuple(line[2:])], fill=255, width=7)
free, _ = ndi.label(~(water | (np.array(cl) > 0)))
land = ndi.binary_fill_holes(free == free[seed[0], seed[1]])
ink = ndi.binary_dilation(0.2126*rgb[..., 0]+0.7152*rgb[..., 1]+0.0722*rgb[..., 2] < 85)
for _ in range(15):                       # grow the land through black ink only, 15 px at most: the quay band is bank
    land |= ndi.binary_dilation(land) & ink
Image.fromarray(land).save(out); print('land px', land.sum())
