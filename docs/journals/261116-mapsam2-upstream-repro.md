# MapSAM2 upstream repro (step 0) — 2026-11-16

## Question

Does upstream MapSAM2, run the upstream way on its own data, reproduce about the paper's number
on a free Colab T4?

## Answer

**Yes, for railway 10-shot.** Our test IoU is **73.69**, the paper's is **73.0** (Table 1). One run,
one seed. Vineyard was not measured: Colab reclaimed the VM during that run (see *What broke*).

## So what

Bet 1b's next step (train on our own maps) can trust the harness: upstream's `train_2d.py` with its
bf16 weights, 200 epochs and memory bank runs unchanged on a T4, in about 50 minutes, and lands on the
paper's number. If a later run on 1882 data does badly, the cause is not Colab, the T4, bf16 or the
environment. This does **not** test VMA's own pipeline: `inference_tiles_as_video.py` and the training
notebook still differ from upstream in the ways `work/MapSAM2/TECHNICAL.md` §7 lists. Next: the same
`train_2d.py`, on a fully labelled 1882 set, scored the same way.

## Pass bar (written and committed before the first run)

Table 1 gives 73.0 for MapSAM2 and Table 2 gives 56.7 without memory attention. "Reproduces" meant
our printed IoU x 100 was closer to 73.0 than to 56.7, so at least 64.9. We got 73.69. One seed
(upstream sets 42, but `cudnn.benchmark = True` makes runs non-identical anyway), so a miss of a
few points would have meant little. A hit within 1 point is a fair sign, not a proof of equal
accuracy.

## The paper's number

Source: arXiv 2510.27547, HTML v1 (`arxiv.org/html/2510.27547v1`), tables read from the page HTML.

Table 1, "Image segmentation accuracy (IoU) on the Siegfried Railway, Vineyard, and ICDAR 2021
Building Block datasets under full and few-shot settings". MapSAM2 (Ours) row:

| Railway Full | 10% | 1% | 10-shot | Vineyard Full | 10-shot | Building Block 10-shot |
|---|---|---|---|---|---|---|
| 90.9 | 89.8 | 84.7 | **73.0** | 77.3 | **67.6** | 75.8 |

Table 2, "Ablation study on the effectiveness of memory attention": railway 10-shot 73.0 with,
56.7 without; vineyard 10-shot 67.6 with, 53.3 without. The text says memory attention adds 16.1
(railway) and 14.3 (vineyard); the table's railway gap is 16.3. The paper does not define "IoU"
beyond Eq. 5 for time series. Setup in the paper: sam2_hiera_small, one Quadro RTX 5000 (16 GB),
AdamW 1e-4, 200 epochs, best validation checkpoint kept, LoRA rank 4, batch 2.

## Our number

Railway, 10-shot, test set of 1,679 tiles, checkpoint `epoch_193.pth` (best validation Dice; the
paper also keeps the best-validation checkpoint). Printed exactly:

```
✅ Test Results -- Total: 0.0956, IOU: 0.7369, DICE: 0.8298
```

| | IoU | Dice |
|---|---|---|
| Paper, Table 1 | 73.0 | not given |
| Ours | 73.69 | 82.98 |
| Gap | +0.7 | |

For context, validation (8 tiles) at epoch 193 read IOU 0.6437 / DICE 0.7758; at the last epoch
(199) 0.6206 / 0.7505. The 8-tile validation set is noisy and reads lower than the 1,679-tile test.
Not run: `epoch_last.pth` on the test set.

What "IOU" is in upstream's code: the model output is binarised at 0.5, IoU is computed per image
(1e-6 smoothing), averaged per batch of 2, then averaged over batches. The code's five-threshold
"enhanced" IoU therefore equals plain IoU at 0.5, because the prediction is already 0/1. We report it
as printed. No test tile has an empty mask (checked), so no empty-tile credit inflates it.

One thing to carry forward: `validation_sam` keeps a memory bank **across test tiles in file order**
(sorted names, batch 2). The score depends on tile order and on earlier predictions. That is how
upstream tests it, and we did the same.

## What we changed from upstream

**Code: nothing.** `git diff` against the pinned commit is empty (the patch file was zero bytes, so it is not kept). Pin: `Xue-Xia/MapSAM2` @
`30110f02e23e2e804198763ab59885caa94cc7ee`. Commands are the README's:

```
python train_2d.py -exp_name HM2D_railway -sam_ckpt ./checkpoints/sam2_hiera_small.pt \
  -sam_config sam2_hiera_s -b 2 -data_path ./data/Siegfried_Railway_Vineyard/dataset_railway/fewshot10
python train_2d.py -exp_name HM2D_railway -sam_ckpt ./checkpoints/sam2_hiera_small.pt \
  -sam_config sam2_hiera_s -b 2 -test_path ./data/Siegfried_Railway_Vineyard/dataset_railway \
  -ft_ckpt logs/HM2D_railway_2026_11_16_06_05_59/Model/epoch_193.pth -test
```

EPOCH stayed at upstream's 200, bf16 weights and autocast stayed (no fp16 switch was needed).

**Environment** (not code, but not Colab's default):
- Colab's own Python is 3.13 with torch 2.14, which does not match upstream's bundled
  `sam2_train/_C.so` or its pins. We built a Python 3.12.3 venv with `uv` and installed upstream's
  own `environment.yml` pip block (153 pins; torch 2.4.0+cu121, numpy 2.0.1, monai 1.3.2).
  `results/env_nvidia_smi_pipfreeze.txt` holds the key pins and `nvidia-smi` (taken during the
  vineyard run, so the GPU shows busy).
- `_C.so`: no import error. The 2D train and test path never calls the connected-components
  function (only the video predictor and mask post-processing do), so it was never loaded; that is
  not proof it loads.
- Flash attention is off on a T4 (Turing); SAM2 falls back to the math kernel (a `UserWarning` in
  the log). Slower, same result.
- Dataset link: the repository page's `/bitstreams/<id>/download` URL returned an HTML error page
  (HTTP 500) to scripts. The DSpace API `.../server/api/core/bitstreams/<id>/content` served the
  file. Size 1,060,544,048 bytes, MD5 `9ee5355eef7424154d1ee51b8eabed9b`, matching the record.
- Checkpoint `sam2_hiera_small.pt` from the URL in upstream's `download_ckpts.sh`
  (`dl.fbaipublicfiles.com/segment_anything_2/072824/`), SHA-256
  `95949964d4e548409021d47b22712d5f1abf2564cc0c3c765ba599a24ac7dce3`.

## Data and licence

Siegfried_Railway_Vineyard, Xia Xue, ETH Zurich, deposited 2024-09-10, DOI
`10.3929/ethz-b-000691430`, handle `http://hdl.handle.net/20.500.11850/691430`. Open access, **licence
"In Copyright - Non-Commercial Use Permitted"** (rightsstatements.org/page/InC-NC/1.0). The readme credits
the Siegfried Map to swisstopo (© swisstopo). 224 x 224 px tiles; railway: 10 train, 8 val
(`fewshot10`), 5,872 train, 1,679 test; every tile in our checks has a non-empty mask; mean
foreground 5.6% of the test tiles. We did not commit the dataset or any checkpoint.

## Timings (Colab free tier, one Tesla T4, driver 580, CUDA 12.1 wheels)

| Step | Time |
|---|---|
| Setup (clone, venv with 153 pins, 0.2 GB checkpoint, 1 GB data) | about 6 min |
| Train, 200 epochs | 2,139 s = **35.7 min** |
| per epoch, training pass only | **6.8 s** (mean of 200 `time_for_training`) |
| per epoch, training plus validation | **10.7 s** |
| Test, 1,679 tiles | 852 s = 14.2 min (0.5 s per tile) |
| Train plus test | 2,991 s = **49.9 min** |

The T4 held to about 1.0 s per batch of 2 at test time. bf16 on Turing is not a problem for speed
at this scale: ten 224-px tiles per epoch are resized to 1024.

## What broke

- The first launch used `cd /content && nohup ... &`, which backgrounded the whole list and kept the
  notebook cell's pipe open, so every later `colab exec` hung until the job ended. Fixed by an
  SSH-to-VM poll with a throwaway key in the scratchpad (nothing written to `~/.ssh`), and by
  launching `nohup bash script > log 2>&1 &` plainly.
- The dataset page link failed (above).
- **Vineyard was not measured.** About 40 minutes into the vineyard run (epoch 33 of 200 seen, val
  IOU 0.71 there, not a test number), Colab's VM went away: `colab sessions` showed no session, the
  SSH endpoint returned 404 and the logs on the VM were lost. I did not rerun it; the railway run
  was done and the rerun would have gone past the time budget. Vineyard is still open; the 2.5 h
  budget held for railway alone.
- Seeing `colab sessions` empty is the stop confirmation; the session was already gone. No `colab
  stop` was needed or sent after that.

## Files

`work/MapSAM2/upstream_repro/`: `setup_vm.sh`, `run_train_test.sh`, `data_stats.py`,
`clean_logs.py`, and `results/` (`train_railway.log`, `test_railway.log`, `env_nvidia_smi_pipfreeze.txt`).
The `.log` files keep only the lines upstream printed (tqdm progress removed), in order.
