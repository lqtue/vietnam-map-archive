# Semap model, zero-shot, on 1882 and 1959 (2026-11-17)

**Question.** Can a model trained on many other maps, with no labels of ours, find
blocks, streets and buildings on our Saigon sheets?

**Answer.** Yes for blocks and streets, and largely for buildings on 1959. Judged by eye
on three tiles; not yet scored against a traced reference.

**So what.** Bet 1b. It gives block outlines on 1882 with no labels at all. It also gives
a fourth line in the score table beside the colour pass, MapSAM2 and a U-Net, and a
candidate for the machine-made labels of `TECHNICAL.md` §8.

## The model

Petitpierre, *Generalizable Multiscale Segmentation of Heterogeneous Map Collections*
(arXiv 2603.05037, 2026). Mask2Former with a Swin-L encoder, trained on Semap: 1,439
hand-labelled patches from many collections, 78 of them from 19th-century European
cadastres, plus 12,122 synthetic maps. The classes are background, contours, built,
non-built, water and road network. Weights, config and data are on Zenodo
(10.5281/zenodo.16164781, version 1.0.2, record 19048095), **CC BY 4.0**. Cite the
dataset and the paper when the results are used.

## How it was run

- `setup.sh` builds a Python 3.10 environment on a Colab T4: torch 2.1.2 (cu121),
  mmcv 2.1.0, mmdet 3.3.0 and mmsegmentation 1.2.2. mmseg and mmdet need mmcv < 2.2,
  which pins torch 2.1. It then downloads `model.zip` (817 MB).
- `infer.py` runs the checkpoint as published, one pass per tile, with no multiscale
  step. It writes a class map, a side-by-side overlay and each class's share of pixels.
- Run it with `MPLBACKEND=Agg`: Colab's inline plotting backend breaks the mmdet import
  inside the separate environment.
- About 15 minutes of VM time in all, most of it installing.

Inputs:
- 1882 validation tiles **t01** and **t06** (`tiles_1882/tiles.json`), at full
  resolution (`s1`) and at half scale (`s05`: 2048 px around the tile, shrunk to 1024).
- One 1959 window on `do-thanh-sai-gon`, central District 1, at both scales.
- The reserved 1882 test windows R1 and R2 were **not** used.

## What it shows (`results/`)

Colours: red built, beige non-built, grey road, blue water, black contours.

- **1882 t01 and t06.** Streets come out as one clean grey network, which gives block
  outlines directly. Lots are sorted by the sheet's own colour code: hatched pink lots
  are built, empty lots non-built. The stream on t06 is water.
- **Errors on 1882:**
  - One open ground ("Ancien Camp des Lettres") is labelled built.
  - On t06, one block of plain lots is labelled built.
  - Single small buildings inside a lot are not separated: on this sheet the model's
    "built" means a built-up lot, not a house.
- **1959.** At half scale: the river, streets, single hatched buildings, courtyards and
  parks all come out separately. The stadium is labelled built. At full resolution,
  buildings and courtyards still separate, and parks lean non-built.

## Not done

- No score. The 1882 references are the owner's square edits, still in progress; score
  t01 and t06 when they are approved, against the 0.355 bar in
  `tiles_1882/README.md`.
- No multiscale inference (the paper's second gain) and no fine-tuning on our tiles.
