# River and road reference windows, 1882 + 1898

**2026-10-01.** Step 1 and the scoring half of step 3 of the `river-reconstruction` gate
(`docs/river-reconstruction.md`), and the same for the road stage. **No window is traced yet; no
score exists.** Everything here is source pixels from `iiif.maparchive.vn` fixed tiles.

- `windows.json` — 1882: 14 water windows and 6 road windows (`"layer": "road"`); 1898: 9 water
  windows. Each has a case and a split. `calibrate` windows may fit the appearance model;
  `heldout` are scored once. `seen: true` marks a window already used in a 2026-10-01
  diagnostic — **not clean held-out**, whatever its split says. The four 1882 water windows and
  six road windows added later on 2026-10-01 were placed on the bare sheet, before any proposal existed.
- `export.py` — fetches every crop to `crops/` (gitignored), writes `crops.json` (box, tile count,
  RGB SHA-256; committed) and creates an empty `traces/<sheet>-<id>.geojson` where none exists.
  `export.py --full 1882` writes the whole sheet at native to `work/ocr/outputs/<map_id>/native.png`
  (gitignored) and pins its SHA-256 in `native.json`; every 1882 window crop hashes identically
  when cut from it. Both read raw tile bytes (`river_pair/eda.py`), never the re-encoding cache.
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
| Printed bank or street edge line | the edge is the **centre of the line** | same |
| Bridge | `ignore` | road (leave untraced) |
| Quay road along water | land | road, stops at the water |
| Lettering | in water: `ignore`; on land: nothing to trace | in a street: road (leave untraced) |
| Red city-limit dashes, red tramway | not an edge; trace through them | same |
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
Not built: the river and road passes, and the multi-reviewer agreement check. Two people tracing
the same window is what tells you whether 5 px of edge error is the method or the tracing.
