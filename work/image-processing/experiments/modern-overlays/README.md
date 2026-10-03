# Modern HCMC layers on the 1882 and 1898 sheets

**2026-10-01.** A look at whether 2023 geodata can seed the river/road/block/building work
(`docs/processing-plan-1882-1898.md`, "Using today's HCMC layers"). **Not a score**: no trace exists yet.
Data: `~/Work/Projects/hcmc-buildings/{hcmc_vector,hcmc_buildings_3d}.parquet` (government portal,
licence unresolved, so `out/` is gitignored). Run with the **system** `python3` (geopandas, pyarrow;
the `work/ocr` venv has neither), `.env` exported, after `river_ref/export.py`:

```sh
set -a; . ./.env; set +a
python3 work/image-processing/experiments/modern-overlays/overlay.py    # px GeoJSON + overlay-<sheet>-<window>.jpg
python3 work/image-processing/experiments/modern-overlays/seed_check.py # modern river, eroded, vs the hand-checked boxes
python3 work/image-processing/experiments/modern-overlays/seed_ink.py   # seed ink vs dry-land ink, native pixels
```

The warp is `modern_prior.fit_sheet`, an affine on the sheet's GCPs: 1882 11.5 m RMS, 1898 8.4 m.
Seed erosion of 60 px is 20 m, chosen to exceed that RMS; it was not tuned.
