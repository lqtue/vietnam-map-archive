# River and road reference windows, 1882 + 1898

**2026-10-01.** Step 1 and the scoring half of step 3 of the `river-reconstruction` gate
(`docs/research/river-reconstruction.md`), and the same for the road stage. Everything here is source
pixels from `iiif.maparchive.vn` fixed tiles.

**Current scope:** the [1882 plan](../../../../docs/image-processing-1882-plan.md) freezes
water v3 for hand review. Road batch 7 and the 1898 follow-ups below are historical
work, deferred by that plan; do not label or tune those batches as part of consolidation.

**The reference is now point labels, not traces** (owner, 2026-10-01):

- `label.py points 1882` — random points in the heldout windows → `points-1882.json` (committed).
  `--unseen` restricts it to heldout windows with `seen: false`, the only clean test; a window that
  has been looked at moves to `calibrate` (`arsenal_quay`, 2026-10-01). `--only ID,ID` restricts a batch to named windows
  (batches 5, 6 and 7 are road-only batches). Batch 5 (seed 5, around v1's edge) stays unlabelled; batch 6 (seed 6, around `road-a772ecd1.png`, the frozen v2) was labelled and scored (v2: 84.3%); its three windows are now calibrate / seen and batch 6 is spent. **Batch 7 (seed 7, 90 points, `mid_boulevard`, `centre_dense`, `avalanche_quay`, around `road-a3b0458f.png`, the frozen v3) is pending owner labels**; results and commands in `docs/research/river-reconstruction.md`.
- `label.py serve 1882` — labelling page at http://127.0.0.1:8791. It shows a crosshair close up
  and in context, never a proposal, window or case. Keys `w` water, `r` road, `l` land, `s` unsure
  (on a line), `u` undo → `labels/1882.jsonl` (committed). 1882: 300 labelled by the owner.
- `score.py --points 1882 <whole-sheet mask.png> [--layer road] [--seed N[,N...]]` — score once per frozen version (a comma list pools batches); `--spent` keeps only points in calibrate / seen:true windows, the evidence a version may be tuned on.
  The water pass is `work/image-processing/scripts/river_pass.py`; results in `docs/research/river-reconstruction.md`.

The tracing workflow below still works, and is kept for any window that needs a pixel shoreline.

- `windows.json` — 1882: 14 water windows and 12 road windows (`"layer": "road"`; `west_dense`, `msg_quay`, `ne_boulevard` were added 2026-10-02 after v1 was frozen and **reclassified calibrate / seen the same day** after a diagnosis of batch 6; `mid_boulevard`, `centre_dense`, `avalanche_quay` are the clean heldout road windows for v3, `seen: false`); 1898: 9 water
  windows and 7 road windows (`road_boulevard`, `road_dense`, `road_quay`, `road_outskirts`, `road_creek` heldout, `seen: false`; `cal_centre`, `cal_edge` calibrate; 2026-10-02, batch seed 2 of 90 points pending owner labels, drawn around `road-fadb75b3.png`). `sheets.<id>` also carries the sheet's legend, neatline, furniture and `ruling` (the
  machine-ruling constants river_pass.py reads; 1882's are its defaults). Each has a case and a split. `calibrate` windows may fit the appearance model;
  `heldout` are scored once. `seen: true` marks a window already used in a 2026-10-01
  diagnostic — **not clean held-out**, whatever its split says. The four 1882 water windows and
  six road windows added later on 2026-10-01 were placed on the bare sheet, before any proposal existed.
- `export.py` — fetches every crop to `crops/` (gitignored), writes `crops.json` (box, tile count,
  RGB SHA-256; committed) and creates an empty `traces/<sheet>-<id>.geojson` where none exists.
  `export.py --full 1882` writes the whole sheet at native to `work/image-processing/results/<map_id>/native.png`
  (gitignored) and pins its SHA-256 in `native.json`; every 1882 window crop hashes identically
  when cut from it, as does every 1898 one: `export.py --verify <sheet>` re-cuts each window from
  `native.png` and compares the hashes (hashes only). Both read raw tile bytes (`river_pair/eda.py`), never the re-encoding cache.
- `view.py SHEET out.jpg [--scale 8 | --box X Y W H]` — look at a sheet without leaking a heldout
  window: boxes with `seen: false` are painted black, and a crop that touches one is refused. The
  feature and river previews use its `blank`. Setting `seen: true` is the record that someone looked.
- `edge_profile.py 1882 MASK.png [--all]` — where a road mask's straight edges sit against the ink stroke they follow (stroke width and centre offset per side of the wall), on road windows that are calibrate or `seen: true`; `--all` adds the water windows. v2 (`road-a772ecd1.png`; v3 changes only narrow strips, not edges): the edge is 2.7-3.2 px on the road side of the stroke centre (`docs/research/river-reconstruction.md`, "Road pass v2: where the edge sits against the stroke").
- `traces/` — the hand traces, committed, GeoJSON Polygons in **source pixels**. Classes:
  `water` (in water windows; extra rings are islands, landings, piers), `block` (in road windows:
  every face that is **not** road) and `ignore` (both). Water windows: land is the complement.
  Road windows: road is the complement of `block`. Top-level `"reviewed": true` marks a done file;
  an empty reviewed water file is a valid all-land window.
- `score.py <proposal_dir> [--layer road]` — proposals are `<sheet>-<id>.png`, window-sized,
  nonzero = water (or road). Prints IoU, missed, false (share of traced complement) and mean edge
  distance in px, pooled per sheet, case and split. `--selfcheck` runs the synthetic checks.

## Boundary rules (decided before tracing; the passes follow the same rules)

| Thing | Water layer | Road layer |
|---|---|---|
| Printed bank or street edge line | the edge is the **centre of the line**, thick or thin (1882 draws each block's lower-right sides ≈3 px, upper-left ≈1.5 px: a shadow line; the difference is under 1 px) | same |
| Bridge | `ignore` | road (leave untraced) |
| Quay road along water | land | road, stops at the water |
| Lettering | in water: `ignore`; on land: nothing to trace | in a street: road (leave untraced) |
| Red city-limit dashes, red tramway | not an edge; trace through them | same |
| Water drawn over parcel hatching (a creek crossing a coloured lot) | **water**: the hatch is ownership, not surface. Expect the pass to miss it, the hatch reads as ruling (2026-10-01) | water is not road; the lot is `block` |
| Pavement: thin kerb line a few px inside a street, parallel to the block edge | land (a quay pavement against water follows the quay rule) | **land**: the road is the carriageway, its edge the kerb line; where no kerb is drawn, the block's outer line (owner, 2026-10-01; labels from seed 2 on; seed-1 pavement points predate the rule) |
| Park paths, garden interiors | land (except ponds and streams) | inside a block: part of the `block` |
| Thin blank strip enclosed by ink in a street | land | `block` (owner: these are real plots) |
| Roundabout islands, plaza planters | land | `block` |
| Fold, stain, anything undecidable | `ignore` | `ignore` |

## Tracing in QGIS

1. `python3 qgis.py prep` (writes a `.pgw` beside each crop; y is negated because QGIS is y-up).
2. New project; Project → Properties → CRS → tick *No CRS (or unknown/non-Earth projection)*.
   Drag in `crops/1882-*.png`; they land at source pixels beside each other. Or drag in the whole
   sheet with **no** world file (QGIS places it at x = column, y = −row, the same frame) plus
   `crops/windows-1882.geojson`, the window outlines, and trace inside those.
3. Layer → Create Layer → New GeoPackage Layer: file `trace.gpkg`, table `1882`, Polygon, one
   text field `class`. (A GeoPackage survives closing QGIS; a scratch layer does not.)
   Layer Properties → Attributes Form → `class` → Default value `'water'`, and Settings →
   Digitizing → *Suppress attribute form pop-up*, so each shape needs no typing; change the
   default to `'block'` for the road windows.
4. Snapping (magnet icon): own layer, vertex + segment, 8 px, and **topological editing** on, so
   neighbouring blocks share edges.
5. Draw at about one screen pixel per source pixel or closer. Add Polygon (Ctrl+.), click along the
   line centre, right-click to close. Islands: Advanced Digitizing → *Add Ring*. Change one shape's
   class in the attribute table (`ignore`).
   - **Water windows:** trace the water.
   - **Road windows:** trace every block, plot, island and water body as `block`; leave streets
     empty. Run blocks **20 px or more past the window edge**, or the gap scores as road.
6. Layer → Export → Save Features As → GeoJSON, `1882.geojson`, into one folder, then
   `python3 qgis.py import <folder> [--dry dry_blue_parcels,dry_city_blocks]` writes
   `traces/*.geojson` with `"reviewed": true`. A feature is filed under every window of its layer
   that it overlaps. Windows with no polygons are left untouched unless named in `--dry`.
   Re-import any time.

Do one window first and import it, so the alignment can be checked before the rest.
The river pass is `work/image-processing/scripts/river_pass.py`, the road pass `road_pass.py` (v3; 1882 and 1898 via `--sheet`; sheet constants in `sheets.<id>.road.consts`; `--window ID` previews one window and refuses an unseen heldout one; `sheets.<id>.road` in `windows.json` is its frame and sheet constants; 1898 is untuned beyond the calibrate windows and unscored). Not built: the multi-reviewer agreement check. Two people tracing
the same window is what tells you whether 5 px of edge error is the method or the tracing.
