# Admin bounds by machine: 1882 topographic plan and Tonkin 1:25,000

**Question.** Can a machine read administrative bounds (village / commune, canton) off old maps
without hand tracing, for bet 1c (admin units over time, Saigon) and later the 1:25,000 series?

**Answer, 2026-10-15.** Partly on the 1882 plan, not on 1:25,000.

- 1882 *Plan topographique du 20e Arrondissement et ses environs* (map `3d065384…`): **canton bounds
  and water come out by colour alone** (pink wash, blue). **Village bounds** are black dash-dot lines;
  hand rules find them in open country but not near the city, where every dash touches other ink.
  Xuân Hòa, the first village bet 1c needs, gets almost nothing.
- Tonkin 1:25,000 (Sơn Tây, 1924, map `013daa15…`): every line type has its own rhythm (legend:
  sentier dashes ~12 px, Xã fine dots ~5 px, Tổng dash-dot ~16 px, Huyện long dashes ~18 px). The
  rhythm filter finds specks, not lines: at ~4.2 m/px a commune dot is 1–2 px, and rice-field symbols
  and contours add their own rhythm.

**So what.** Bet 1c traces Xuân Hòa by hand; the machine output is hints only. Reading bounds across
the 1:25,000 series needs a trained line-type model (classes from the legend), which is parked in
`docs/NOW.md` until nationwide admin units become a bet. Its kill test: if commune dots cannot be
told apart at the scan resolution, find sharper scans first.

## What was tried

All numbers are by eye on overlays; there is no answer key yet. The first hand trace of Xuân Hòa
becomes one.

| Script | Idea | Result |
|---|---|---|
| `colour.py` | Lab distance from the paper colour: pink a\*, blue b\* (plain hue fails; the blue is pale and near grey) | 1882: canton bands clean, no city fill; water as both banks of wide rivers, canals whole |
| `dash_chains.py` | Short thin dark strokes (6–36 px, < 5 px wide) that are not part of a longer faint stroke, chained end to end (≥ 4, aligned within 28°), gaps bridged up to 80 px; pink nearby = canton | 1882: 111 chains (10 canton). West (Phú Thọ, Lộc Hòa) good, no roads or text. Near the city, nothing |
| `rhythm.py` | Oriented complex filter tuned to the line's period (phase-free, zero-mean along the line, thin across); score = share of the line's ink that follows the rhythm; dense ink and OCR text boxes masked | 1882 (P = 23 px): west found, city ignored; near Xuân Hòa a few real hits and false ones on a canal, a double-dashed road and text. 1:25k: fails |

Dead ends, kept so nobody repeats them:

- Raw rhythm amplitude fires on the city grid (most ink wins); the share score fixes that.
- Checking that the gap between dashes is blank paper drops real dash-dot lines (the dot sits in the gap).
- OCR boxes of spaced canton names (`DƯƠNG MINH HÒA`, 1123 × 1663 px) cover whole villages; mask only
  boxes up to 450 px.

## Run

Inputs are local (not versioned). Full-resolution scan:
`work/core` `vma_core.iiif.fetch_crop(iiif_base, 0, 0, W, H, size=W)` from the `work/ocr/.venv`;
OCR boxes: `ocr_labels?map_id=eq.<id>` (`global_*` share the scan's pixel grid).

    PY=work/ocr/.venv/bin/python; D=work/image-processing/experiments/admin-lines
    $PY -I $D/colour.py topo_4000.jpg out/                     # 4000 px wide copy is enough
    $PY -I $D/dash_chains.py topo_native.png out/chains.jpg 4
    OCR=ocr_topo.json $PY -I $D/rhythm.py topo_native.png out/rhythm.jpg 23 900,1900,3400,3000 0.68 0.16

Periods: measure from clean chains (1882: dash-dot ~22–24 px, canton dashes ~12–14 px) or from the
sheet's legend swatches.
