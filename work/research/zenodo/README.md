# Zenodo release preparation — L7014 verification artifacts

This directory is a release preparation record. It is not a Zenodo deposition and
contains no DOI. The source scans and generated rasters remain outside the repository;
the release should contain derived geometry, verification tables, provenance, and the
regeneration record listed below.

## Readiness

**Prepared locally; not ready to publish.** The required derived artifacts exist under
the ignored `work/l7014/` tree, and a reviewable package is staged in `package/`.
`package/SHA256SUMS` records hashes relative to that package. The paper's claim audit now
marks the Zenodo section `B`: the DOI and final public deposition still do not exist.

## Required release contents

| release item | current artifact | status |
|---|---|---|
| L7014 lattice | `work/l7014/lattice.json` (627 cells) | present |
| source sheet manifest | `work/l7014/sheets.json` | present |
| faulty mosaic geometry | `work/l7014/build/l7014-faulty.geojson` | present |
| corrected mosaic geometry | `work/l7014/build/l7014-fixed.geojson` | present |
| faulty geometry with hand sheets | `work/l7014/build/l7014-faulty-hand.geojson` | present |
| corrected geometry with hand sheets | `work/l7014/build/l7014-fixed-hand.geojson` | present |
| cached annotation GCP inputs | `work/l7014/gcp/*.json` (9 files) | present |
| raw seam tables | `work/l7014/regen/seams-{faulty,fixed}{,-hand}.csv` | present |
| per-sheet datum split | `work/l7014/regen/datum-split.csv` | present |
| fit and correction provenance | `work/l7014/regen/REGEN.md` and `regen/*.log` | present |
| environment record | `work/l7014/regen/environment.log` | present, incomplete `projinfo --version` probe |
| source manifest hashes | `SHA256SUMS` and `package/SHA256SUMS` | prepared here |

## Provenance boundaries

- The recorded regeneration ran from commit `7ee5d947303bdc9183ae8fffc2290bd88ea861ec`
  plus the two uncommitted changes described in `work/l7014/regen/REGEN.md`.
- The input GeoPDFs, JPG scans, and generated COGs are not release contents. They are
  referenced by path and provenance in `REGEN.md`; source rights and size make copying
  them into Zenodo inappropriate.
- `REGEN.md` records both the seven-hundred-plus seam run and the hand-sheet extension.
  The package description must distinguish the free `pdf/pdf` and `jpg/jpg` seams from
  the `jpg/pdf` joins whose lattice placement is partly committed by construction.

## Completed preparation

The package is assembled in `package/` with the regeneration logs and source inventory.
Its relative `SHA256SUMS` verifies from that directory.

## Blocking work before publication

1. Decide the final metadata and license treatment for derived geometry and annotations;
   do not imply redistribution rights for institutional scans.
2. Reconcile the release contents with the corrected paper claims. The current
   `docs/paper/claim-audit.md` explicitly requires immutable or regenerable versions of
   these artifacts before submission.
3. Only after review, create a Zenodo deposition and insert its DOI into the paper.

## Reproduction entry point

The exact commands, inputs, run results, and known limitations are in
`work/l7014/regen/REGEN.md`. The relevant scripts are:

```text
scripts/l7014_mosaic.py
scripts/l7014_hand.py
scripts/l7014_seams.py
```
