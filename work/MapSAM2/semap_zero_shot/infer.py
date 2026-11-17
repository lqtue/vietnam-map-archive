"""Semap Mask2Former-Swin-L, zero-shot, on VMA tiles. Writes class maps, overlays and class shares."""
import glob, json, os
import numpy as np
from PIL import Image
from mmengine import Config
from mmseg.apis import init_model, inference_model

root = '/content/semap'
cfg_path = glob.glob(f'{root}/**/*.py', recursive=True)[0]
ckpt = glob.glob(f'{root}/**/*.pth', recursive=True)[0]
cfg = Config.fromfile(cfg_path)
cfg.model.backbone.init_cfg = None  # weights come from the checkpoint; no ImageNet download
model = init_model(cfg, ckpt, device='cuda:0')
print('classes:', model.dataset_meta.get('classes'))

NAMES = ['background', 'contours', 'built', 'non-built', 'water', 'road']
COLORS = np.array([[255,255,255],[0,0,0],[220,40,40],[240,200,120],[60,140,230],[150,150,150]], np.uint8)
os.makedirs('/content/out', exist_ok=True)
shares = {}
for p in sorted(glob.glob('/content/in/*.png')):
    name = os.path.basename(p)[:-4]
    res = inference_model(model, p)
    cls = res.pred_sem_seg.data[0].cpu().numpy().astype(np.uint8)
    Image.fromarray(cls).save(f'/content/out/{name}_cls.png')
    img = np.array(Image.open(p).convert('RGB'))
    over = (0.45 * img + 0.55 * COLORS[cls]).astype(np.uint8)
    Image.fromarray(np.concatenate([img, over], axis=1)).save(f'/content/out/{name}_overlay.jpg', quality=88)
    shares[name] = {NAMES[i]: round(float((cls == i).mean()), 3) for i in range(len(NAMES))}
    print(name, shares[name])
json.dump(shares, open('/content/out/shares.json', 'w'), indent=1)
