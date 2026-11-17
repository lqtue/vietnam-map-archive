#!/bin/bash
# Semap Mask2Former inference env on a Colab T4: py3.10 venv, torch 2.1 + mmcv 2.1 (mmseg 1.2.2 / mmdet 3.3 need mmcv<2.2).
set -e
cd /content
pip -q install uv
uv python install 3.10 >/dev/null
rm -rf /content/mm; uv venv -q --python 3.10 /content/mm; export UV_PYTHON=/content/mm/bin/python
source /content/mm/bin/activate
uv pip install --python /content/mm/bin/python -q torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu121
uv pip install --python /content/mm/bin/python -q "numpy<2" mmengine==0.10.4 ftfy regex
uv pip install --python /content/mm/bin/python -q mmcv==2.1.0 -f https://download.openmmlab.com/mmcv/dist/cu121/torch2.1/index.html
uv pip install --python /content/mm/bin/python -q mmdet==3.3.0 mmsegmentation==1.2.2 pillow
python -c "import torch, mmcv, mmseg, mmdet; print('torch', torch.__version__, torch.cuda.is_available(), 'mmcv', mmcv.__version__, 'mmseg', mmseg.__version__)"
python -c "from mmcv.ops import MultiScaleDeformableAttention; print('mmcv ops ok')"
# The model, from the Semap Zenodo record (CC BY 4.0).
[ -f model.zip ] || curl -sL -o model.zip https://zenodo.org/api/records/19048095/files/model.zip/content
unzip -oq model.zip -d semap && find semap -maxdepth 3 -type f | head
