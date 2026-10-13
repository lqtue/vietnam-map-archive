# MapSAM2 × VMA — Technical Documentation

How SAM2 fine-tuning works, what MapSAM2 does on top of it, how VMA's data feeds in, and where the improvement opportunities are.

**Inference update, 2026-10-12:** the standard VMA image predictor runs tiles independently.
Cross-tile memory is now an opt-in `memory_predictor.py` adapter, retaining instance prompts
and using confidence-gated deterministic retrieval. It is not the complete semantic pipeline
described in the paper. [COMPARISON.md](COMPARISON.md) documents the current metadata/memory
experiment; the architecture and training notes below are background, not evidence of accuracy.

> **Path note:** file names such as `sam_lora_image_encoder.py`, `func_2d/*.py`, `yolo.py`, `train_2d.py` and `train_3d.py` refer to the **upstream MapSAM2 repository**, cloned separately (on Colab, passed as `--mapsam2-dir`). They are not files in this repo. VMA's inference, mask conversion, prompt, memory, context, bundle and evaluation adapters live alongside this document.

---

## 1. SAM2 Architecture — What We're Building On

SAM2 (Segment Anything Model 2, Meta 2024) is a transformer-based segmentation model originally designed for video object segmentation. It has four major components that interact during inference:

```
Image
  │
  ▼
┌─────────────────────────┐
│   Image Encoder (Hiera) │  ← HieraDet: hierarchical vision transformer
│   Output: 3 feature maps│    (4096×256), (16384×64), (65536×32)
└────────────┬────────────┘
             │
┌────────────▼────────────┐   ┌─────────────────────────┐
│   Memory Attention       │◄──│   Memory Bank (6 slots) │
│   Conditions features   │   │   Stores past frame      │
│   on remembered frames  │   │   feature + mask pairs   │
└────────────┬────────────┘   └─────────────────────────┘
             │
┌────────────▼────────────┐   ┌─────────────────────────┐
│   Prompt Encoder        │   │   Prompts:               │
│   (frozen in fine-tune) │◄──│   bbox [x1,y1,x2,y2]    │
│   → sparse embeddings   │   │   or point [x,y] + label │
└────────────┬────────────┘   └─────────────────────────┘
             │
┌────────────▼────────────┐
│   Mask Decoder           │
│   Outputs:               │
│   - low_res_mask (256²)  │
│   - iou_prediction       │
│   - object_score_logit   │
└─────────────────────────┘
```

### Image Encoder (HieraDet)

The backbone is a hierarchical vision transformer that processes the full 1024×1024 image and outputs features at three resolutions:

| Feature level | Shape (seq, batch, dim) | Spatial meaning |
|--------------|------------------------|-----------------|
| Level 0 (fine) | 65536 × B × 32 | 256×256 grid |
| Level 1 (mid) | 16384 × B × 64 | 128×128 grid |
| Level 2 (coarse) | 4096 × B × 256 | 64×64 grid |

The coarse features (64×64) become the `image_embed` that goes into the mask decoder. The finer two become `high_res_feats` for detail recovery.

**Why this matters for historical maps:** SAM2 was trained on natural images. Historical map scans have flat color regions, sharp polygon boundaries, and symbology (hatching, text labels) that look nothing like natural scene texture. The image encoder may activate on the wrong visual features — this is exactly what LoRA fine-tuning corrects.

### Memory Bank

The memory bank stores `(feature, mask)` pairs from previous frames in a video sequence. For 2D static images (VMA's use case), this is used differently — it accumulates representations across training examples in the batch, providing a form of instance-level context. Config: 6 slots (`memory_bank_size=6`), retrieve top-2 per forward pass (`memory_retrieval_k=2`).

### Prompt Encoder

Takes a bounding box or set of points and converts them to positional embeddings that condition the mask decoder. **Frozen during MapSAM2 fine-tuning** — the prompt encoding mechanism transfers well across domains.

In MapSAM2 training, the prompt bbox is derived automatically from the ground-truth mask: the tightest bounding box around the white pixels. This means the model is trained to "given a bbox around this parcel, predict the precise polygon boundary."

### Mask Decoder

Cross-attends prompt embeddings against image features to produce:
- `low_res_multimasks`: 256×256 logit map (upsampled to 1024×1024 for loss)
- `iou_predictions`: predicted quality score
- `object_score_logits`: confidence that something is present

---

## 2. MapSAM2 — What It Adds

MapSAM2 wraps SAM2 with two modifications: LoRA adaptation of the image encoder, and a training script that generates automatic bbox prompts from GT masks.

### 2a. LoRA Fine-Tuning (`sam_lora_image_encoder.py`)

LoRA (Low-Rank Adaptation) inserts small trainable matrices into frozen attention layers without changing the original weights:

```
Original attention:  W_q (d × d)  ← frozen
LoRA insert:         W_q + A × B  ← A is (d × rank), B is (rank × d)

Only A and B are trained. For rank=4 and d=256:
  Original: 256×256 = 65,536 parameters
  LoRA:     256×4 + 4×256 = 2,048 parameters  (3% of original)
```

This is applied to every **Q** (query) and **V** (value) projection in every attention layer of the image encoder. The key projection (K) is left frozen.

```python
# In sam_lora_image_encoder.py:
class _LoRA_qkv(nn.Module):
    def forward(self, x):
        qkv = self.qkv(x)           # original frozen projection
        # Apply LoRA only to Q and V:
        qkv[:, :, :, :self.dim] += self.lora_b_q(self.lora_a_q(x))  # Q
        qkv[:, :, :, -self.dim:] += self.lora_b_v(self.lora_a_v(x)) # V
        return qkv
```

**Initialization:** A matrices use Kaiming uniform (small random values), B matrices are zero → at init, LoRA output is exactly zero, so training starts from the pretrained model. Learning rate needs to be reasonable (1e-4) so LoRA adapts gradually.

**What stays frozen:**
- Prompt encoder (entirely)
- Memory attention module
- Key projections in image encoder
- Position encodings

**What's trainable:**
- LoRA A,B matrices in image encoder (~2% of total params)
- Mask decoder (all weights)
- `obj_ptr_proj` (object pointer projection for memory bank)

### 2b. Automatic Prompt Generation

MapSAM2 doesn't require manually drawn bboxes — it derives them from the GT mask:

```python
# In func_2d/function.py (train_sam):
def get_bbox(mask):
    rows = torch.any(mask, dim=1); cols = torch.any(mask, dim=0)
    y1, y2 = rows.nonzero()[[0,-1]].squeeze()
    x1, x2 = cols.nonzero()[[0,-1]].squeeze()
    return torch.tensor([[x1, y1, x2, y2]])

bbox = get_bbox(gt_mask)  # tight box around ground truth polygon
sparse_emb, dense_emb = model.prompt_encoder(points=None, boxes=bbox, masks=None)
```

This means during training, the model always receives a perfect bbox hint. At inference, you provide the bbox manually (or derive it from another detector like YOLO — which is why `yolo.py` exists in the repo).

### 2c. Training Loop (2D mode)

```
For each batch (image, gt_mask):
  1. Image → HieraDet encoder → 3-level feature maps
  2. Features → Memory Attention (conditioned on memory bank) → conditioned features
  3. GT mask → get_bbox → Prompt Encoder → sparse + dense embeddings
  4. Conditioned features + embeddings → Mask Decoder → low_res_pred (256×256)
  5. low_res_pred → bilinear upsample → pred (1024×1024)
  6. loss = BCEWithLogitsLoss(pred, gt_mask, pos_weight=2.0)
  7. loss.backward(); optimizer.step()
  8. Update memory bank with current image features + predicted mask
```

The `pos_weight=2.0` on BCE loss means false negatives (missing polygon area) are penalized twice as much as false positives (spurious predictions). This biases the model to over-segment slightly rather than miss buildings — correct for historical maps where every parcel boundary matters.

---

## 3. VMA Data → MapSAM2 Format

### What VMA Stores

Each `footprint_submission` row contains:
- `pixel_polygon`: array of `[x, y]` pairs in IIIF pixel space (y+ = down)
- `feature_type`: building / land_plot / road / waterway / green_space / water_body / other
- `category`: SAM color class (particulier / communal / militaire / local_svc / non_affect) or volunteer label
- `map_id` + `allmaps_id`: links to the Allmaps georeference annotation
- `status`: submitted / needs_review / consensus / verified / rejected

### Export API: COCO Conversion

`GET /api/export/footprints?format=coco&map_id=X` does this transformation for each footprint:

```
IIIF pixel polygon
    │
    ├─ Compute bbox: xMin, yMin, xMax, yMax
    ├─ Add PAD pixels on each side → cropX, cropY, cropW, cropH
    ├─ Build IIIF URL: {base}/{cropX},{cropY},{cropW},{cropH}/{SIZE},/0/default.jpg
    │
    └─ Scale polygon to crop-relative rendered coordinates:
         scale = SIZE / cropW
         relX  = (polyX - cropX) * scale
         relY  = (polyY - cropY) * scale
```

The COCO output already has crop-relative polygon coordinates — no further coordinate math needed to render the mask.

### COCO → MapSAM2 Directory Conversion

The notebook converts COCO to this layout:

```
vma_dataset/
├── train/
│   ├── <footprint_uuid>.png   ← RGB IIIF crop (1024×w px)
│   └── ...
├── val/
│   └── ...
└── annotation/
    ├── train/
    │   ├── <footprint_uuid>.png   ← grayscale binary mask (0 or 255)
    │   └── ...
    └── val/
        └── ...
```

Mask rendering:
```python
mask = Image.new('L', (width, height), 0)       # black background
pts  = list(zip(seg[::2], seg[1::2]))            # [(x1,y1), (x2,y2), ...]
ImageDraw.Draw(mask).polygon(pts, fill=255)      # white filled polygon
```

MapSAM2's `HM2D` dataset loader then does:
```python
img  = Image.open(img_path).convert('RGB')
mask = Image.open(mask_path).convert('L')
mask_tensor = transforms.ToTensor()(mask)        # 0..1 float
mask_binary = (mask_tensor > 0.5).float()        # binary {0.0, 1.0}
```

---

## 4. Evaluation Metrics

MapSAM2 reports three metrics on the validation set after each epoch:

### Loss (BCE)
Standard binary cross-entropy with positive weight 2.0. Lower is better. Typical range: 0.05–0.4 for reasonable models.

### Dice Coefficient
```
Dice = 2 × |pred ∩ gt| / (|pred| + |gt|)
```
F1-equivalent for segmentation. Ranges 0–1; higher is better.
- < 0.5: model is struggling
- 0.6–0.75: reasonable for few-shot / limited data
- 0.75–0.85: good, comparable to published SAM2 fine-tune results
- > 0.85: excellent — may indicate easy maps or data leakage

### Enhanced IoU (eIoU)
IoU averaged across 5 thresholds (0.1, 0.3, 0.5, 0.7, 0.9). This measures robustness to the decision threshold rather than assuming the optimal 0.5. Better measure of calibration than single-threshold IoU.

```
eIoU = mean([IoU(pred > t, gt) for t in [0.1, 0.3, 0.5, 0.7, 0.9]])
```

---

## 5. Current Limitations & Improvement Opportunities

### 5a. Single-class binary model
**Current:** MapSAM2 trains one binary segmentation model — foreground (any polygon) vs background. Category information (`particulier`, `communal`, `militaire`) is ignored during training.

**Improvement:** Multi-class segmentation by training one model per category, or modifying the mask decoder to output N channels (one per category) with a multi-label loss. VMA has the category labels stored in `footprint_submissions.category`.

**Effort:** Medium — requires modifying `func_2d/function.py` loss computation and the mask decoder output head.

### 5b. Prompt at inference time
**Current:** Training uses GT-derived bboxes. At inference, you need to supply a bbox somehow — either manually, via YOLO detection, or via SAM2's automatic mask generator.

**Improvement:** The `yolo.py` in MapSAM2 integrates YOLO for automatic bbox proposal. For historical maps, candidate bboxes can come from a tile-based scan or, as VMA now does, from the OCR pass — `inference_tiles_as_video.py --mode prompted --ocr-run-id <run>` seeds SAM2 from `ocr_extractions` bboxes. SAM2 then refines them into precise polygon boundaries. (The older `scripts/vectorize.py` colour-profile scan has been deleted.)

**Effort:** Low — the YOLO integration already exists, and the Gemini/OCR seed path is already shipped. The open question is only whether a trained YOLO detector would beat the OCR seeds.

### 5c. Fixed 1024×1024 input
**Current:** SAM2 requires exactly 1024×1024 input. IIIF crops are resized to this regardless of original aspect ratio, potentially distorting elongated buildings or roads.

**Improvement:** Pad to square rather than stretch, then crop back after prediction. Or use SAM2's built-in padding mode.

**Effort:** Low — modify the `Resize` transform in dataset.py to pad instead of stretch.

### 5d. Memory bank not fully utilized for 2D maps
**Current:** The memory bank was designed for video — it remembers previous frames. For static 2D images, it stores features from earlier training batches. This provides some cross-image context but doesn't exploit the map's spatial structure.

**Improvement:** Tile adjacent map regions into a "video sequence" so the memory bank builds up spatial context across the scan. Related to `train_3d.py` in MapSAM2 which handles temporal sequences.

**Effort:** High — requires redesigning the data loader to produce spatial sequences.

### 5e. Data quality vs quantity tradeoff
**Current:** `STATUS=submitted` gives the most data but includes unreviewed traces. `STATUS=verified` is highest quality but smallest set.

**Improvement:** Two-stage training — pre-train on `submitted` (larger, noisier), fine-tune on `verified` (smaller, cleaner). Standard curriculum learning approach.

**Effort:** Low — just change `STATUS` between training runs and use the first run's checkpoint as `ft_ckpt` for the second.

### 5f. No data augmentation
**Current:** The dataset applies only `Resize + ToTensor`. No random flips, rotations, color jitter, or elastic deformations.

**Improvement:** Add augmentations in `func_2d/dataset.py`. For historical maps, useful augmentations include: horizontal flip, random rotation (maps can be at any orientation), brightness/contrast jitter (scan quality varies), and random crop within the padded region.

**Effort:** Low — add `torchvision.transforms` to the dataset transform pipeline. The mask must receive the same geometric transforms as the image (MapSAM2 already preserves RNG state between image and mask transforms).

### 5g. No geographic coordinate output
**Current:** The model predicts masks in IIIF crop pixel space. VMA has the Allmaps georeferencing data to convert these back to WGS84, but the pipeline doesn't do this automatically post-inference.

**Improvement:** After inference, map predicted mask pixels back through the IIIF → geo coordinate transform using `GcpTransformer` from `@allmaps/transform` (already used in the export API). Then store the result as a new `footprint_submission` with `status=needs_review` for volunteer validation.

**Effort:** Medium — requires a post-processing step and a pipeline that writes back to Supabase. **This shipped:** `inference_tiles_as_video.py --write-supabase` writes `footprint_submissions` (pixel space) and advances `map_pipeline_status`; the pixel → WGS84 transform happens downstream in the export API.

---

## 6. End-to-End Flow

```
VMA Supabase
  footprint_submissions (status=verified)
          │
          │ GET /api/export/footprints?format=coco
          ▼
    COCO JSON
    (IIIF crop URLs + polygon segmentation)
          │
          │ Download IIIF crops
          │ PIL polygon → binary mask
          ▼
  MapSAM2 dataset/
  ├── train/ (images)
  └── annotation/train/ (masks)
          │
          │ train_2d.py (LoRA fine-tune)
          ▼
  LoRA checkpoint (.pth)
  Best Dice/eIoU on val set
          │
          │ Inference on new map scan
          │ (bbox prompt per tile from grid scan or YOLO)
          ▼
  Predicted masks (pixel space)
          │
          │ GcpTransformer (Allmaps georef)
          ▼
  WGS84 polygons → footprint_submissions
  (status=needs_review → volunteer review → verified)
          │
          └─► Back to training data for next iteration
```

This loop is the core of VMA's crowdsourcing + AI pipeline: humans review AI output, reviewed data retrains the model, which produces better output for the next round.
