#!/bin/bash
# Train then test upstream MapSAM2 on one Siegfried class, 10-shot, with upstream's README commands.
# Run on the Colab VM after setup_vm.sh.   usage: run_train_test.sh railway|vineyard
# Env: EPOCH (default: leave upstream's 200 alone). Any change to upstream is recorded by
#      `git diff` into /content/upstream_diff_<class>.patch.
set -uo pipefail
CLS=${1:-railway}
cd /content/MapSAM2
PY=/content/venv/bin/python
DS=./data/Siegfried_Railway_Vineyard/dataset_$CLS
EXP=HM2D_$CLS

if [ -n "${EPOCH:-}" ]; then
  sed -i "s/^EPOCH = 200/EPOCH = $EPOCH/" conf/global_settings.py
fi
git diff > /content/upstream_diff_$CLS.patch
echo "== diff vs pinned upstream:"; cat /content/upstream_diff_$CLS.patch

date +%s > /content/t_train_start_$CLS
$PY -u train_2d.py -exp_name $EXP -sam_ckpt ./checkpoints/sam2_hiera_small.pt -sam_config sam2_hiera_s \
  -b 2 -data_path $DS/fewshot10 > /content/train_$CLS.log 2>&1
echo "train exit $?" >> /content/train_$CLS.log
date +%s > /content/t_train_end_$CLS

CK=$(ls -1 logs/$EXP*/Model/epoch_[0-9]*.pth 2>/dev/null | sort | tail -1)
echo "best checkpoint: $CK" | tee -a /content/test_$CLS.log
date +%s > /content/t_test_start_$CLS
$PY -u train_2d.py -exp_name $EXP -sam_ckpt ./checkpoints/sam2_hiera_small.pt -sam_config sam2_hiera_s \
  -b 2 -test_path $DS -ft_ckpt "$CK" -test >> /content/test_$CLS.log 2>&1
echo "test exit $?" >> /content/test_$CLS.log
date +%s > /content/t_test_end_$CLS
echo ALLDONE >> /content/test_$CLS.log
