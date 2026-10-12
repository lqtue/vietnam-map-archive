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

## Follow-up (same day): giving the four Gallica sheets an image

The owner chose Gallica's own IIIF Image server over tiling to R2 first (R2 tiling still happens on
publish, mig 058). Nothing was applied: no `--apply`, no production write, no job queued.

### The smoke failure is not this branch's

`tests/catalog-series.spec.ts:4` ("catalog begins with compact disclosures…") **also fails on
`main`** (detached worktree at `1f224d5c`, own dev server on port 5199 so no other session's server
on 5173 could be reused; the worktree was removed afterwards):

```
Error: expect(locator).toBeVisible() failed
Locator: getByLabel('Place')   Expected: visible   Received: hidden
> 19 |   await expect(page.getByLabel('Place')).toBeVisible();
```

The element resolves to the `<select title="Modern province, …">` and stays hidden after the
add-filter disclosure is opened. A catalog UI regression that predates this branch.

### The derivation

`deriveGallicaImage(rec)` in `scripts/scoutDerive.mjs`: ark from `source_url`, then `manifest_url`,
then `thumbnail`, only on `gallica.bnf.fr`, never for the Omeka-backed hosts (humazur, Bordeaux 3 —
`deriveManifestUrl` owns those) →
`https://gallica.bnf.fr/iiif/ark:/12148/<ark>/f1`. `deriveImageUrl` now returns the LoC form or this,
so `load_scout_to_db.mjs` and `fix_scout_iiif.mjs` pick it up unchanged.

One deliberate departure from the brief: the stored value is the **base** (`…/f1`), not
`…/f1/info.json`. `get_image_info` and `SheetZoom` append `/info.json` themselves, and every Gallica
`map_images` row in production (the 1942 pair included) holds the base. An `info.json` URL in
`maps.iiif_image` would make the worker request `…/info.json/info.json`. (The LoC case in
`deriveImageUrl` does store `info.json`; no ingested map has one, so it has not bitten. Worth
fixing before the first LoC ingest.)

`scripts/oneoff/backfill_gallica_iiif_image.mjs` (`willApply()`; dry by default) — dry-run output:

| Candidate | `raw.iiif_image` it would get |
|---|---|
| `1c9bfdc1` Mytho 1902 | `https://gallica.bnf.fr/iiif/ark:/12148/btv1b8458472s/f1` |
| `9a068e07` Mytho 1890 | `https://gallica.bnf.fr/iiif/ark:/12148/btv1b530577107/f1` |
| `966aa45e` Chaudoc 1890 | `https://gallica.bnf.fr/iiif/ark:/12148/btv1b530586464/f1` |
| `f2405e6a` Soc Trang 1888 | `https://gallica.bnf.fr/iiif/ark:/12148/btv1b531670480/f1` |

### Probe: could not be answered from here

One GET of each `…/f1/info.json`, 3 s apart:

| Candidate | HTTP | Size |
|---|---|---|
| `1c9bfdc1` | 403 | none |
| `9a068e07` | 403 | none |
| `966aa45e` | 403 | none |
| `f2405e6a` | 403 | none |

The 403 is not about these arks. From this machine **every** `gallica.bnf.fr` URL answers 403 with a
Cloudflare HTML challenge — the manifest, the ark page, the thumbnail, and `info.json` of the 1942
sheet that is already in production (`btv1b53197000p`), with curl and with python-requests. So the
derived URLs are unverified, not wrong; sizes are unknown. No attempt was made to get past the
challenge. The probe is `--probe` on the backfill script and should be re-run from a network Gallica
accepts (the machine that will run the worker is the one that matters).

### Failures are failures

`cmd_scout` (layout) already raised: `get_image_info` re-raises after its retries and `fetch_crop`
raises `RuntimeError` when a non-IA source refuses the region and the level-0 fallback. Pinned by
`work/ocr/scripts/test_fetch_failure.py` for 403, 429 and 500.

The OCR tile loop did **not**: a failed tile was printed and appended to `errors`, then the run went
on — dedup of what survived, a master file, `ocr_labels` upserted, `ocr_done` stamped, exit 0. A
Gallica that refused every tile would have ended as "0 extractions, done". `ocr.py` now calls
`_fail_on_tile_errors(errors, total)` straight after listing the failures: non-zero exit before
anything is written, the worker records the job as failed, and a re-run resumes from the tiles
already on disk. This also stops a quota-hit run from stamping `ocr_done` on a partial result.
