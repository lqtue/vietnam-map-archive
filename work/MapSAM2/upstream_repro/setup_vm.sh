#!/bin/bash
# Step 0 of the MapSAM2 check: put upstream MapSAM2 on a Colab T4, exactly as upstream pins it.
# Run on the Colab VM only. Nothing here touches VMA data or keys.
#
#   upstream code : https://github.com/Xue-Xia/MapSAM2 @ 30110f02e23e2e804198763ab59885caa94cc7ee
#   python / torch: 3.12 / 2.4.0 (upstream's environment.yml; Colab's own is 3.13 / torch 2.14,
#                   which cannot load upstream's bundled sam2_train/_C.so)
#   data          : ETH Research Collection, doi 10.3929/ethz-b-000691430 (In Copyright - Non-Commercial)
#   checkpoint    : sam2_hiera_small.pt from upstream's checkpoints/download_ckpts.sh URL
set -euo pipefail
cd /content

PIN=30110f02e23e2e804198763ab59885caa94cc7ee
[ -d MapSAM2 ] || git clone -q https://github.com/Xue-Xia/MapSAM2
git -C MapSAM2 checkout -q "$PIN"
git -C MapSAM2 rev-parse HEAD

# 1. Python 3.12 venv with upstream's own pip pins (the pip: block of environment.yml).
pip install -q uv 2>/dev/null || true
[ -d /content/venv ] || uv venv --python 3.12 /content/venv
python3 - <<'PY'
t = open('/content/MapSAM2/environment.yml').read()
i = t.index('- pip:')
req = [l.strip()[2:] for l in t[i:].splitlines()[1:] if l.strip().startswith('- ')]
open('/content/req_pip.txt', 'w').write('\n'.join(req) + '\n')
print(len(req), 'pins')
PY
uv pip install -q --python /content/venv/bin/python -r /content/req_pip.txt
/content/venv/bin/python -c "import torch;print('torch',torch.__version__,torch.version.cuda,torch.cuda.is_available(),'bf16',torch.cuda.is_bf16_supported())"

# 2. Checkpoint (same URL as upstream's download_ckpts.sh).
mkdir -p MapSAM2/checkpoints
[ -f MapSAM2/checkpoints/sam2_hiera_small.pt ] || \
  wget -q -O MapSAM2/checkpoints/sam2_hiera_small.pt \
  https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_small.pt
sha256sum MapSAM2/checkpoints/sam2_hiera_small.pt

# 3. Dataset (1.06 GB zip, MD5 9ee5355eef7424154d1ee51b8eabed9b per the repository record).
mkdir -p MapSAM2/data
if [ ! -d MapSAM2/data/Siegfried_Railway_Vineyard ]; then
  # The site's /bitstreams/<id>/download link returns an HTML error page (HTTP 500) for scripts on
  # 2026-11-16; the DSpace API 'content' endpoint serves the file.
  curl -sL -A research-client/1.0 -o /content/srv.zip \
    https://www.research-collection.ethz.ch/server/api/core/bitstreams/17c9d1c3-8f74-487c-9508-fa9cae6d716b/content
  rm -f /content/srv.zip.bad
  ls -l /content/srv.zip
  md5sum /content/srv.zip
  unzip -q /content/srv.zip -d MapSAM2/data
fi
ls MapSAM2/data
