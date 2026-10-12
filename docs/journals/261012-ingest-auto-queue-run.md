# 2026-10-12 — Ingest queues its own processing: the code, and why the measured run did not happen

Branch `ingest-auto-queue`. Part A (the code) is done and tested. Part B (a measured run on up to 20
real maps) was **stopped before any production write**, for two independent reasons found by
reading the candidate queue. Nothing was ingested, queued, approved or processed on production;
there are no per-map timings to report and none are invented here.

## What changed (Part A)

- `POST /api/admin/scout` inserts a `layout` job (`payload.then = 'ocr'`) for each sheet it creates
  that has an Image API endpoint, and says so in the reply (`layout_queued`).
- `/api/pipeline/results`, once a `layout` job reports `done`, calls `queueOcrAfterLayout`
  (`src/lib/server/pipelineQueue.ts`). It queues `ocr` with the saved `main_map` crop as `neatline`,
  the `legend` / `name_list` blocks as `exclude`, `auto: true`, `auto_priority: true`; every other
  default stays the worker's. If the layout pass found no `main_map` it queues nothing and replies
  `ocr not queued: layout found no main_map`, which matches `enqueue_ocr_all.mjs` (a person draws the
  crop). Pattern followed: `execute` queuing `warp` after `mirror_annotation`, 23505 swallowed.
- The chain is opt-in per job (`then`), so the Detect button in `/scan?mode=prepare` still stops for a
  human to correct regions before any tile is paid for.
- No `summary` kind, no flag, no migration. Georeferencing is not chained.
- Tests: one new write test (ingest creates the layout job and only where there is an image; a
  finished layout queues ocr with the right crop/exclude; a layout without `then` queues nothing).
  `npm run check` 0/0, `npm run lint` clean, `npm run test:write` 39/39 on the local stack
  (Docker via colima was started for it), `npm run test` 472 passed / 1 skipped / 1 failed — the
  failure is `catalog-series.spec.ts` "compact disclosures", `getByLabel('Place')` hidden in the
  catalog filter UI; the change touches no UI and the test was not run on `main` to confirm it
  predates it.

## Why Part B stopped

Candidates the owner has approved and not yet ingested (`review_status = 'approved'`, `map_id` null;
the earlier HTTP 400 was `status` not being a column — it is `review_status` since mig 095): **5**.
The status tally read the first 1,000 rows only (PostgREST cap): 993 pending, 5 approved, 2 ingested
(the two 1942 Saigon / Cholon plates). The approved list itself was queried directly and is complete.

| Candidate | Source | Year | Manifest | `raw.iiif_image` | Note |
|---|---|---|---|---|---|
| `e8166887` Atlas général de l'Indo-Chine française | Humazur | 1909 | yes | no | The owner's own `review_note`: the manifest is a stub with no image service, the atlas is a 417 MB PDF, "plate ingestion not scheduled" |
| `1c9bfdc1` Plan topographique de la province de Mytho | Gallica | 1902 | yes | no | thumbnail only |
| `9a068e07` Plan topographique de la province de Mytho | Gallica | 1890 | yes | no | thumbnail only |
| `966aa45e` Plan topographique de la province de Chaudoc | Gallica | 1890 | yes | no | thumbnail only |
| `f2405e6a` Plan topographique de l'arrondissement de Soc Trang | Gallica | 1888 | yes | no | thumbnail only |

1. **Ingest only runs through the authenticated admin route.** The insert logic is inline in
   `POST /api/admin/scout` (it needs `requireRole`'s session); there is no library function a script
   can call, and re-implementing it in a script was ruled out. The owner would click Ingest in
   `/admin?tab=scout`.
2. **None of the five has a usable image.** `maps.iiif_image` is written from `raw.iiif_image`, which
   all five lack, and `map_images` (which would hold the manifest) is only written when that image
   URL exists. Ingest would still succeed — the guard is "no manifest *and* no image" — and produce a
   draft with a thumbnail and no `iiif_image`. `layout` and `ocr` both refuse such a map
   ("Map has no iiif_image"), so there is nothing for the worker to run on. Giving the four Gallica
   sheets an image means tiling them to R2 (`tile_to_r2`, vips + rclone), an R2 write outside what
   this run was allowed. The new code correctly queues nothing for them (`layout_queued: false`).

The two previously ingested plates went through that route and were then hosted on
`iiif.maparchive.vn`; they are public and have no jobs, so they are not candidates for this run either
(and would have been an edit to public rows).

## Left for the owner

- Decide whether to ingest the four Gallica sheets (they are approved) and host their scans; then a
  measured run is 4 maps, not 20. The Humazur atlas cannot be ingested as IIIF at all.
- If ingest should hand Gallica sheets an image endpoint itself, `scoutDerive.mjs` derives only the
  Library of Congress case today; a Gallica derivation would be the follow-up that makes this
  automation reach them.
- No worker was run, no Gemini spend, no timings, no label counts, no title/cartouche agreement
  check. The comparison against the manual baseline therefore has no automated-side data yet.
