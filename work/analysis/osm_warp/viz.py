"""Safe crops of the native sheet with overlays. Refuses any box touching a seen:false window."""
from common import *
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
def touches(box, pad=0):
    x, y, w, h = box
    return any(x - pad < bx + bw and bx - pad < x + w and y - pad < by + bh and by - pad < y + h for bx, by, bw, bh in BLIND)
_im = None
def crop(box):
    global _im
    if touches(box): raise SystemExit(f'refused: {box} touches an unseen window')
    if _im is None: _im = Image.open(OUT / 'native.png').convert('RGB')
    return np.asarray(_im.crop((box[0], box[1], box[0] + box[2], box[1] + box[3])))
