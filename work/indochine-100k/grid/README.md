# Series 561 sheet grid

Generate locally with:

```bash
work/ocr/.venv/bin/python scripts/indochine100k_grid.py --apply
```

The geometry comes from [CartoMundi's IGN series 561 sheet endpoint](https://www.cartomundi.fr/ctmd-services/public/etablissement/3/serie/561/feuille/exemplaire/all),
saved as the 492-record WKT extract in `../sources/serie-561-wkt.json`.
Each WKT footprint is matched by its unique `fkey` to the existing series-561
catalogue and then to VMA map rows by `extra_metadata.cartomundi_fkeys[0]`.
The WKT is already WGS 84 longitude/latitude; no Paris-meridian conversion
is applied to it. Collection 297 in the user-supplied example belongs to
**series 233**, so its footprints were not mixed into this grid.

- `cells.geojson`: union of source WKT footprints for each of 197 numbered
  cells, with ID `561:<number>`.
- `halves.geojson`: the source WKT for each W/E slot, IDs `561:<number>:W`
  and `561:<number>:E`. A null geometry marks an unrepresented half; a
  source record with no known half belongs to the numbered cell only.
- `map-crosswalk.json`: one entry per source catalogue record, including
  `fkey`, VMA `map_id` if present, cell ID, slot ID if known, CartoMundi
  `geometry_key`, and `grid_code`.

All 360 current VMA series-561 map rows matched exactly once among 492
catalogue records. Fifty W/E slots lack a source record with that half.
Cells **153 and 154** have substantial spatial overlap because CartoMundi
assigns their western records the same geometry key. Both carry a
`spatial_conflicts` flag for review; the generator does not choose one.

These polygons identify a sheet's place in the survey. They do not map its
image pixels to ground coordinates or approve any georeference. The separate
placement and visual checks in `scripts/indochine100k_georef.py` still apply.
