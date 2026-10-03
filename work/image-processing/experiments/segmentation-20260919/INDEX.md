# Segmentation review pack — 19 Sep 2026

Two sheets run through `work/image-processing/scripts/colour_blocks.py`, plus the material
they superseded. Nothing here has been imported.

| path | what it is |
|---|---|
| `1882/` | 0e02b9d9 Plan Cadastral 1882 — before/after the day's work, 888 → 1443 polygons. Start at `1882/README.md`. |
| `1898/` | 20ec4f9a Plan Cadastral 1898 (Bertaux) — the run, the two `review_figs.py` bugs, and the georeference finding. Start at `1898/REPORT.md`. |
| `*/normalized/` | the export for review: `blocks.normalized.geojson`, `blocks.queue-safe.geojson`, `audit.json`. |
| `_superseded/` | kept as evidence only. Safe to `rm -rf` once the journal entry is committed. |

## What to run next, in order

1. **Trace one window exhaustively** — every parcel, street and water surface
   inside one box on 1882, and one around the Arsenal quay / Palais de Justice.
   Score it with `seg_eval --window x,y,w,h`. Until this exists there is no
   precision figure for either sheet and no way to choose a polygonizer.
2. **Re-run 1898 with `--ocr-run-id 2026-09-13T1036-20ec4f9a`** so the manifest
   pins the OCR rows and the image hash. The class mix in
   `1898/normalized/audit.json` is one draw of a non-reproducible number.
3. **Re-georeference 1898** before anything geographic. Three GCPs on a
   1st-order polynomial cannot report a non-zero RMSE.

## Superseded

- `_superseded/colour-pass-1100/` — the 11:00 figure set; every frame is either
  byte-identical to one in `1882/figures/` or an older render of it.
- `_superseded/river-260918/` — the 18 Sep water pass, with the one-off
  `layers.py` / `make_figs.py` that `review_figs.py` replaced. Those two scripts
  exist nowhere else.
- `_superseded/1898-figures-wrong-image/` — the 1898 figures drawn from 1882
  pixels, the bug `b6c38c9f` fixed.
- `_superseded/rejected-hybrid/` — the arsenal/palace crops from the hull-vs-trace
  test. The trace and the hybrid were both rejected; see the journal entry.
