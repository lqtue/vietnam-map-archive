# 1898 Bertaux segmentation — normalized result

Source: run-6144-clipped/blocks.geojson in the Desktop 1898 review pack. Coordinates are full source-image pixels (16267 × 14859), origin at top left; they are not longitude/latitude. The sheet's current three-point georeference is not reliable for geographic use.

- Source polygons: 3178; exact duplicates removed: 1.
- blocks.normalized.geojson: 3177 unique valid polygons, with source wash classes mapped to review types and categories. Interior holes are preserved.
- blocks.queue-safe.geojson: 3170 polygons with one exterior ring for the Validate queue.
- blocks.import-ready.geojson: the same 3170 polygons with source classes for scripts/import-seg-geojson.mjs.
- audit.json: 7 held polygons and their coordinates for manual review.
- Review rendering of the clipped result: `../figures/00_whole_sheet.png`.

This pack is an export for review. No database import has been performed. The source run did not pin the input image hash or OCR run; its colour class mix is therefore not reproducible.
