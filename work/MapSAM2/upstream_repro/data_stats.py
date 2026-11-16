"""Count tiles, empty masks and foreground share per split. Run with the VM venv's python.
usage: data_stats.py DATASET_DIR   (e.g. /content/MapSAM2/data/Siegfried_Railway_Vineyard/dataset_railway)
"""
import os, sys
import numpy as np
from PIL import Image

root = sys.argv[1]
for split in ['fewshot10/train', 'fewshot10/val', 'test']:
    parts = split.split('/')
    mdir = os.path.join(root, *parts[:-1], 'annotation', parts[-1])
    idir = os.path.join(root, *parts)
    names = sorted(os.listdir(mdir))
    empty, fg, size = 0, [], set()
    for n in names:
        m = np.array(Image.open(os.path.join(mdir, n)).convert('L')) >= 128
        size.add(m.shape)
        empty += int(m.sum() == 0)
        fg.append(m.mean())
    print(f'{split:16s} tiles={len(names):5d} empty_mask={empty:5d} ({100*empty/len(names):.1f}%) '
          f'mean_fg={100*np.mean(fg):.2f}% sizes={sorted(size)} images={len(os.listdir(idir))}')
