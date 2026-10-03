# 1882 Plan Cadastral — segmentation, before and after (2026-09-19)

Everything here was measured on the pinned scan
`.tile_cache/ocr/full_c03b7f44a1d8d455c2b476d248651265.jpg` (12102 × 8982).
Score over the network instead and you are measuring the fetch — two runs of the
same command minutes apart have returned `land_plot` 0.375 and 0.243.

## The headline

| | before | after | |
|---|---:|---:|---|
| **building** mean | 0.122 | **0.355** | |
| **building** median | 0.050 | **0.314** | the number count cannot buy |
| **building** @ IoU 0.5 | 1 / 17 | **5 / 17** | |
| **building** @ IoU 0.3 | 3 / 17 | **9 / 17** | |
| land_plot mean | 0.331 | 0.343 | control — count effect only |
| land_plot @ 0.3 | 7 / 24 | 8 / 24 | |
| areal @ 0.5 | 7 / 41 | **11 / 41** | |
| areal @ 0.3 | 10 / 41 | **17 / 41** | |
| road cover | 0.14 | 0.14 | unchanged |
| waterway | 0.582 | 0.582 | unchanged |
| label recall | 0.78 | 0.78 | unchanged |
| polygons | 888 | 1443 | 888 parcels + 555 buildings |
| runtime | 80 s | 83 s | CPU, no GPU, no checkpoint |

For reference: SAM2 LoRA on the modern prior scores `building` **0.160**, and
that is a train-set score — the LoRA was fine-tuned on these same 17 traces.
The colour pass is trained on nothing.

**The caveat that bounds all of it:** 1443 predictions against 46 traces, and
`seg_eval` takes the best match per trace, so it is structurally blind to a
prediction that matched nothing. There is still **no precision figure for this
sheet**. `seg_eval --window x,y,w,h` now exists to produce one and needs one
window traced exhaustively — that is the single highest-value hour you could
spend on this.

## What is in here

```
before/   the run as it stood this morning — 888 polygons
          blocks.geojson · blocks.run.json · scores.txt
          deleted-72-sam-auto-rows.json   the lettering polygons purged from the DB
          nulled-60-ocr-joins.json        the label joins that pointed at them
after/    the same command after today's work — 1443 polygons
          blocks.geojson · blocks.run.json · scores.txt
figures/  15 review renders. orange = kept, blue = dropped, blue tint = the
          water region, green tint = the land mask bounding it.
          In the AFTER frames the small orange rings inside a parcel are the
          new building split.
```

**Where to look first:** `13_city_untouched_AFTER.png` against
`12_city_untouched_BEFORE.png`. Top-left of that frame is the split working —
individual buildings outlined inside their parcels. Bottom-left (Gendarmerie,
Trésor, Hôtel du Secrétaire Général) is where it does not, and the picture
shows why: those buildings are drawn as *outlines on the same tint*, not as a
redder wash. That is the same 10-of-17 the numbers report.

Note that frame is labelled a TRAP in the renderer — its BEFORE/AFTER pair used
to have to be identical, because the water work was not supposed to touch the
city. It is no longer identical **by design**: the split adds geometry there.

## To reproduce

```bash
cd ~/Work/Projects/vietnam-map-archive
set -a && . ./.env && set +a
export PYTHONPATH=work/ocr/scripts
python3 work/image-processing/scripts/colour_blocks.py \
  --map-id 0e02b9d9-9d40-4cca-8e41-8c8373d54d3b \
  --local-image .tile_cache/ocr/full_c03b7f44a1d8d455c2b476d248651265.jpg \
  --render 6051 --out <dir>
python3 work/image-processing/scripts/seg_eval.py \
  --map-id 0e02b9d9-9d40-4cca-8e41-8c8373d54d3b <dir>/blocks.run.json
```

Every pass is a default now. `--no-split-buildings` reproduces the `before/`
run; `--no-cream`, `--no-recut`, `--no-drop-water`, `--no-drop-slivers`,
`--no-drop-furniture` and `--no-swatch-labels` each restore the run they name,
and each flag's `--help` carries what turning it off costs.

## Full write-up

`docs/journals/260919-seg-audit.md` — the audit, the work list, and what each
item did or did not do, including the two nulls.
`work/ocr/EVAL-BASELINE.md` — the scored row, at the foot.
