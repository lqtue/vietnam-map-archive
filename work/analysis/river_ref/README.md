# River reference windows, 1882 + 1898

**2026-10-01.** Step 1 and the scoring half of step 3 of the `river-reconstruction` gate
(`docs/river-reconstruction.md`). **No window is traced yet; no score exists.** Everything here
is source pixels from `iiif.maparchive.vn` fixed tiles.

- `windows.json` — 10 windows on 1882, 9 on 1898, each with a case (open river, quay, creek,
  basin, bridge/label gap, dry land) and a split. `calibrate` windows may fit the appearance
  model; `heldout` are scored once. `seen: true` marks a window already used in a 2026-10-01
  diagnostic — **not clean held-out**, whatever its split says. The unseen held-out windows
  are 1882 `chinois_quay`, `creek_nw`, `bridge_basin`, `arsenal_basin` and 1898 `quay_canal`,
  `creek_north`, `bridge_label`, `dry_salmon`, `hatched_bank`.
- `export.py` — fetches every crop to `crops/` (gitignored), writes `crops.json` (box, tile count,
  RGB SHA-256; committed) and creates an empty `traces/<sheet>-<id>.geojson` where none exists.
- `traces/` — the hand traces, committed. GeoJSON Polygons in **source pixels** (not lng/lat):
  `class: "water"` (extra rings are land islands, landings, piers) or `class: "ignore"`
  (bridge, label, fold, anything a person cannot decide). Land is the complement, so a boundary
  crossing the window is clipped to it. Set the top-level `"reviewed": true` when done; an
  empty reviewed file is a valid all-land window (the dry controls).
- `score.py <proposal_dir>` — proposals are `<sheet>-<id>.png`, window-sized, nonzero = water.
  Prints IoU, missed water (share of traced water), false water (share of traced land) and
  mean shoreline distance in px, pooled per sheet, case and split. `--selfcheck` runs the
  synthetic checks.

Not built: the trace editor (any tool that exports source-pixel polygons works; QGIS with an
engineering CRS is enough), the bank-aware proposal, and the multi-reviewer agreement check.
Two people tracing the same window is what tells you whether 5 px of shoreline error is the
method or the tracing.
