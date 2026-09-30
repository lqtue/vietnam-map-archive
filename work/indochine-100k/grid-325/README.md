# Series 325 sheet grid

Generate locally with:

```bash
work/ocr/.venv/bin/python scripts/indochine100k_grid.py --series 325 --apply
```

Cell and half-sheet geometry comes from the WKT in `../sources/serie-325-wkt.json`,
extracted from [CartoMundi's IGN series 325 endpoint](https://www.cartomundi.fr/ctmd-services/public/etablissement/3/serie/325/feuille/exemplaire/all).
The endpoint returned 514 records; the local series catalogue contains 512
fkeys, and those all matched. The two endpoint-only records (Saigon and
Rach-Gia) are recorded in `excluded_extra_records` in the WKT snapshot and
left out of the VMA grid.

- `cells.geojson`: one source-WKT union per numbered cell, ID `325:<number>`.
- `halves.geojson`: W/E slots, IDs `325:<number>:W` and `325:<number>:E`.
  Null geometry means no matching record for that half in the local catalogue.
- `map-crosswalk.json`: one row per local catalogue record with its CartoMundi
  `fkey`, geometry and grid keys, numbered cell, half when known, and current
  VMA `map_id` when one exists.

The grid has 143 numbered cells, 286 half slots, 512 catalogue records, and
221 current VMA map matches. Sixty-one half slots have no source record. The
polygons locate a sheet in the survey; they do not georeference image pixels.
