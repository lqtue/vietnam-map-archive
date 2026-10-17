# MapSAM2 in VMA

For whoever runs segmentation. Kind: guide. Setup: [VMA_SETUP.md](VMA_SETUP.md); how SAM2 works:
[TECHNICAL.md](TECHNICAL.md).
Moved here from `docs/guides/pipelines.md` on 2026-10-17, word for word.

## MapSAM2 inference (`work/MapSAM2/`)

SAM2/MapSAM2 segmentation: IIIF tiles → masks → polygons → `footprints`. Colab (GPU) or
local M1 (base SAM2 only).

An offline colour-pass `blocks.geojson` is also reviewable: import it as a named
`needs_review` run with `scripts/import-seg-geojson.mjs --map-id <uuid> --run-id
<name> --input <blocks.geojson>`, then use `/scan?mode=shapes&tab=validate`.
The importer refuses duplicate map/run pairs, keeping one reproducible set of
proposals behind each review and tuning result.

No venv is checked in or currently set up for this pipeline — create one per your platform and
install the SAM2 deps. Training/LoRA details, the paper reading and the improvement backlog are in
**`work/MapSAM2/TECHNICAL.md`**; Colab config is in `work/MapSAM2/VMA_SETUP.md`.

```bash
# Local test (base SAM2, small region)
python work/MapSAM2/inference_tiles_as_video.py \
  --map-id <uuid> --checkpoint /path/to/sam2.1_hiera_small.pt \
  --region 4800,4300,1024,1024 --out-json test.json --preview

# Full Colab run with LoRA + OCR seeds + Supabase write
python work/MapSAM2/inference_tiles_as_video.py \
  --map-id <uuid> --checkpoint /path/to/mapsam2_lora.pth \
  --lora --mapsam2-dir /content/MapSAM2 \
  --mode prompted --ocr-run-id <run_id> \
  --tile-size 1024 --overlap 128 --text-mask --watershed \
  --out-json footprints.json --write-supabase

# The 1882 cadastral, prompted from both seed sources. Generate the prior first
# (free, local, no GPU): modern_prior.py --map-id <uuid> --blocks --out <dir>
python work/MapSAM2/inference_tiles_as_video.py \
  --map-id 0e02b9d9-9d40-4cca-8e41-8c8373d54d3b \
  --checkpoint /path/to/mapsam2_lora.pth --lora --mapsam2-dir /content/MapSAM2 \
  --mode prompted --ocr-run-id post0910 --prior <dir>/blocks.geojson \
  --tile-size 1024 --overlap 128 --text-mask --watershed \
  --out-json footprints.json --write-supabase

# Evaluate (SODUCO baseline: best pipeline COCO PQ 51.1%, Chen et al. 2024 -- the F1=0.59 this line carried is unsourced, corrected 2026-09-19)
python work/MapSAM2/evaluate.py --predictions footprints.json --map-id <uuid> [--iou-thresholds 0.5,0.75]
```

Key flags: `--mode automatic|prompted`, `--lora`, `--encoder vit_s`, `--mapsam2-dir` (path to the **upstream** MapSAM2 clone), `--text-mask` (erase OCR bbox regions), `--watershed` (Meyer post-processing), `--region x,y,w,h`, `--device cpu|cuda|mps`, `--prior <blocks.geojson>`.

Modes: `automatic` = SAM2AutomaticMaskGenerator grid-scan; `prompted` = SAM2ImagePredictor with box
seeds, which need **`--ocr-run-id` or `--prior` or both** (best with LoRA).

**Two seed sources, and on any sheet so far the second is the larger one.**
`--ocr-run-id` seeds from `ocr_labels`, area categories only, and those
seeds carry their label so the polygon is named at birth. `--prior` seeds from
`modern_prior.py --blocks` — 2023 buildings buffer-dissolved into blocks and
warped into the sheet's own pixel grid — and those arrive nameless, so nothing
downstream stamps a name on them. They **union**, they do not replace: a block a
label already sits on is worth prompting from two boxes rather than one. Measured
on the 1882 cadastral: run `post0910` yields **92** area seeds after clipping to
`main_map`, the block prior **965** from 52,431 modern buildings — that count is
at `BLOCK_BUFFER_M = 4`, and it moves with that value, so read the ratio rather than the number.

`load_seeds_from_prior` had existed since the module was written and had no
caller until 2026-09-10; `--prior` is that caller. The **worker does not forward
it** — `_seg_argv` builds its argv from a fixed list of payload keys, and a
prior is a local file path belonging to the machine rather than to the job, the
same reason `--tile-metres` is not forwarded either. A Colab seg run that wants
a prior passes it by hand.

Scripts: `inference_tiles_as_video.py` (orchestrator; `--write-supabase` also advances
`map_pipeline_status` seg_queued → seg_done), `masks_to_polygons.py` (`mask_to_polygon`,
`masks_to_polygons` IoU dedup, `shift_polygons`), `evaluate.py` (F1 + geometric quality vs
`footprints` review_status=verified).

Polygons written to `footprints.coords` as `[[x,y],...]` pixel-space arrays.

## Tiles-as-video

The MapSAM2 paper's unifying insight: treat a set of static tiles from one map as a **video**, so
SAM2's memory attention shares context across tiles instead of segmenting each in isolation. The
paper measures memory attention alone at **+14.3% IoU on vineyards, +16.1% on railways**.

**Status: shipped in shape, not in mechanism.** `inference_tiles_as_video.py` is the VMA entry point
and tiles the region sequentially, but still runs SAM2's default FIFO memory. The paper's
**self-sorting memory bank** (MedSAM-2, Zhu et al. 2024) is the open change:

- admit candidate embedding `E_t` if IoU confidence `c_t` > threshold;
- keep the top-`K` most **dissimilar**, `D_i = Σ_{j≠i}(1 − sim(E_i, E_j))`, `M_t = TopK(D_i)`;
- for the next tile `F_{t+1}`, resample the top-`k` most **similar**, `p_{i,t} ∝ sim(F_{t+1}, E_i)`.

Highest single-change EV in the backlog, and the most complex.

## Gemini as the prompt source

The paper uses a fine-tuned YOLO to produce instance-level bbox prompts, and is reported here as
showing prompt quality is worth **+12.8% F1** (holding the segmenter fixed, varying only YOLO's
training size). **That figure is UNVERIFIED — checked 2026-09-19 and could not be confirmed.**
MapSAM2's full text is not indexed by scite and the arXiv record (10.48550/arxiv.2510.27547) is not
open there. What *is* confirmed is that MapSAM2 cites the YOLO paper (10.1109/cvpr.2016.91) from its
Methods section, so the shape of the claim is plausible; the number is not sourced. Do not quote
+12.8% externally until someone reads the table. The memory-attention ablation in the same paper
**is** verified against its Table 2 (+14.3 IoU vineyard, +16.1 railway, both 10-shot) — cite that
instead. VMA substitutes Gemini:

- open-vocabulary, no training, several categories in one call;
- returns the **text** as well as the box — one call, two signals, so OCR and prompt generation are
  the same pass;
- on a corpus of ~46 annotated Saigon footprints, a 10-shot YOLO is the weaker option.

**Status: shipped.** `--mode prompted --ocr-run-id <run>` seeds SAM2 from `ocr_labels` bboxes,
and `--prior <blocks.geojson>` adds the modern block prior beside them. `--text-mask` erases those
regions from the image so label ink is not segmented as building.

The reverse direction closes the loop: once polygons exist, `join_labels.py` assigns each label to
the polygon it names (migration 050). Bidirectional — labels prompt the segmenter, footprints then
claim the labels.

## Ordering the sequence

Spatial ordering on the Gemini side is the cheap analogue of the paper's self-sorting memory: order
tiles so dense urban-core frames come first and sparse edge tiles inherit accumulated context.

**Status: partially shipped, and one variant measured and rejected.** `batch --row-sequence`
(default on, `--max-row-frames 4`) sends each row-strip as one sequence call to
`extract_labels_sequence()`. A denser ordering was never implemented. The adjacent idea — reading
each tile together with its four grid neighbours — *was* built, measured and reverted; see
EVAL-BASELINE.md for the numbers and the two root causes (bad `frame_idx` attribution; centroid
ownership leaking inside the 300px overlap band).
