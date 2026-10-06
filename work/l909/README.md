# L909 catalogue-backed city index

The source snapshot records PCL’s explicitly labelled L909 city-map items from
https://maps.lib.utexas.edu/maps/vietnam.html, checked 2026-10-06. It contains 21
items for 19 distinct cities; the Nha Trang and Qui Nhon versos belong to their
existing city cells. PCL’s two Saigon sheets are L9012 and are excluded.

The existing served Sài Gòn L909 scan adds a twentieth known city. The additive
import `scripts/oneoff/import_l909_series_cells.mjs` created 20 `series_cells`
and 21 PCL `cell_printings` records in production on 2026-10-06. Read-back:
3 publicly served cities, 17 other cities with a known external source. A
second apply added zero records. No maps, rights, printing identities or
geographic extents were changed or inferred. Source editions and dates remain
catalogue assertions, including null years where the catalogue says `196-`.
Hà Nội and Huế source edition labels differ from existing map metadata; review
of the collars remains open.

This is a partial catalogue inventory, not the complete historical survey.
`src/lib/core/seriesIndexScope.ts` carries that qualification into the catalog,
coverage page and explore list. Retain it until a complete source-backed
historical inventory has been established. `l909-index` remains on ROADMAP for
that work and for catalogue cell extents.

## Ingesting the indexed scans

`node --env-file=.env scripts/oneoff/ingest_l909_pcl.mjs` prints the missing-image
plan. `--download` stages and decodes the source JPEGs locally; `--apply`
mirrors them and inserts draft map/source records. The source URL and a local
journal make retries reuse the same map UUID. Existing maps are excluded from
writes. Native JPEG bytes are retained under the IIIF service's native-width
full-image key, alongside its tile pyramid, thumbnails and 2048px overview.
Read-back checks the native JPEG SHA-256, service dimensions, overview,
thumbnail and a pyramid tile before adding each map and source link.

The two verso indexes are separate scan workspaces with the same city sheet
identifier and `scan_side = verso`; they do not add city cells or infer a
reviewed printing identity. Catalogue editions/dates remain assertions until
reviewed. Ingest leaves maps as drafts, with no georeference or OCR job queued.

## Ingest result — 6 October 2026

All 19 previously missing indexed scans were ingested as drafts: 17 city-map
rectos and the Nha Trang / Qui Nhon versos. The series now has 22 scan
workspaces across its 20 indexed cities: 3 existing public maps and 19 new
drafts. All new images have a source-item link, dimensions, native JPEG
SHA-256 and an opaque asset-version UUID. Native image checksums, 800px
thumbnails, 2048px overviews and representative pyramid tiles passed for
every image. The original three map records are unchanged. A repeat dry run
found zero remaining indexed source images.

The local source images total 183,239,795 bytes. The checked record/asset
manifest is `work/l909/ingested-scans.json`. Preparation and georeferencing
remain to be done before publishing the new drafts.
