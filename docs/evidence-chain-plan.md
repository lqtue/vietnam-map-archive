# `evidence-chain` — implementation plan

This is the engineering plan for the evidence-backed research pages discussed in
September 2026. The open-work entry is `evidence-chain` in `docs/ROADMAP.md`
(§Evidence and legibility). `docs/search-plan.md` remains the plan for finding
labels, shapes, and period texts; this plan describes how to cite, connect,
review, and reuse their results.

## Outcome and first question

A reader should be able to open a statement about a place or feature, see the
particular source image region behind it, inspect who or what read that region,
and export the evidence used in a study. A correction must leave an older cited
version intelligible. A missing source or unreviewed machine reading must be
visible as such.

Build the first complete trail on the 1882 Saigon cadastral map documented in
`docs/research/worked-example-1882.md` (map `0e02b9d9-…`, Gallica `btv1b52508901z`),
where a reviewed OCR run (`v1b`), 46 approved footprints, a source record, and
a measured georeference already exist. Choose one named feature whose label and
trace can both be inspected. Add a second dated map only after checking that it
actually depicts the same feature. The first claim is modest: "this feature is
depicted here on this printing." A change-over-time claim is the *second* test,
because two depictions alone need interpretation.

## What already exists

Most of the chain is already in the schema. The pilot adds the claim layer and
closes three gaps; it does not rebuild what is below.

| Need | Already carried by | Gap |
|---|---|---|
| Pixel geometry as the durable citation | `footprints.pixel_polygon` (mig 016), the OCR box on `ocr_labels`; `geom` is derived and disposable (mig 066) | Which image the pixels refer to: `map_images` has no width, height, or fingerprint |
| Georeference version | `geom_src` — hash of the GCP set (mig 066); 1882 is `245d98f7f8d61572` | The hash is not reversible; a packet must carry the annotation JSON itself |
| Label ↔ shape link | `ocr_labels.footprint_id` (mig 050) | — |
| Machine vs human reading | `ocr_labels.run_id`, `review_status`, `text_corrected`, `reviewed_by`; `footprints.source`, `run_id`, `review_status` | No canonical-run marker; `v1b` is canonical by prose only |
| Known printings, held or not | `cell_printings` (mig 087) — one row per printing per institution, no FK so an unmatched printing survives; loaded from IGN, ANU, TTU | Raw payload, fetch time, content hash |
| Spelling variants | `place_names` view, `variants[]` (mig 067) | Groups spellings; does not prove one historical entity |
| Rights | `maps.rights`, `cell_printings.rights` | **Normalised, not verbatim** — mig 096 merged `domaine public` → `Public domain`. 1882 reads `Public domain` |
| Draft privacy | `map_images_select_visible_parent` (mig 097) | New tables copy this policy shape |

## Identity model

Do not collapse these into one `map` identity:

| Thing | Home | Rule |
|---|---|---|
| Survey and cell | `map_series` view, `series_cells` | A cell can exist without any held image. Standalone maps have no cell. |
| Printing and institutional copy | `cell_printings` for series; `maps` metadata for standalone sheets | A cell may have multiple dates, titles, parts, and holders. Do not invent a cell for a standalone map. |
| VMA-held map | `maps.id` | Canonical internal map ID; `slug` is an address. |
| Scan or IIIF service | `map_images` | One map can have several images/providers, not always in the same pixel space. |
| External catalogue record | `cell_printings` first; **new** `external_records` only if step 5's fixtures show it cannot carry raw payload + hash | One provider printing gets one home. Do not load IGN rows into a second table beside `cell_printings`. |
| Image region | existing pixel geometry + image identity (see gap above); **new** `evidence_anchors` only for readings with no OCR/footprint row | Stable pixel selector against a specific image. |
| Reading of a region | `ocr_labels`, `footprints`; later **new** `observations` for manual/other-source readings | Raw output and human review stay attributable. |
| Historical subject | **new** `subjects`, one reviewed row for the pilot | The `place_names` view groups spellings; it does not prove all mentions are one historical entity. |
| Research proposition | **new** `claims` and `claim_evidence` | An assertion cites supporting or conflicting readings and has a review state. |
| Rights statement | verbatim text on the pilot's source record; **new** `rights_statements` only when statements need separate object scope/version | A provider's posted license is evidence, not VMA's legal conclusion. |

The essential chain is:

```text
provider record ──describes──> printing/copy ──represented by──> held map
                                                        │
                                                    scan/image
                                                        │
                                               pixel geometry (label box, polygon)
                                                        │
                                          reading + run/reviewer
                                                        │
                                      claim <──supports/contradicts── evidence
                                                        │
                                            study/export snapshot
```

This is a relational graph in Postgres. The public series, sheet, place, and
feature pages are projections of these records. No graph database or universal
`node/edge` table is needed for the pilot.

## Required fields and invariants

1. **Source:** provider, provider ID, canonical URL, retrieval timestamp, raw
   payload/hash, and the specific VMA object linked after reconciliation. Store
   the provider's wording alongside any normalized value.
2. **Image region:** the reading's pixel geometry, plus the `map_images` row it
   was measured against and that image's dimensions. Ground geometry is derived
   through `geom_src`; pixel geometry remains the durable citation when a warp
   is corrected. Two images of one map are not assumed to share a pixel space:
   the 1882 R2, IA, and Gallica scans all measure 12102×8982, but the 1942 R2
   copy is a distinct 2× rescan.
3. **Reading:** category, transcribed text or geometry, origin (`machine`,
   `volunteer`, `editor`), run ID or reviewer, review state. Existing OCR and
   footprint rows are cited through their UUIDs. The pilot does not need a
   per-map canonical-run marker: each cited row carries its own `run_id`, and
   the packet records it. Add a marker when a query has to choose among runs.
4. **Cited rows cannot vanish, and a citation keeps what it cited.** Today an
   owner can delete an *approved* footprint (`footprints_delete_own_or_admin`
   has no status check), mods rewrite `pixel_polygon` in place, staff rewrite
   `ocr_labels.text_corrected` in place, and there is no history table. So:
   - `claim_evidence` references `ocr_labels` / `footprints` with typed FKs,
     `ON DELETE RESTRICT`. Deleting a cited row fails; the trace and review UIs
     must show that refusal rather than a generic error.
   - `claim_evidence.cited_value` (jsonb) snapshots the text, category, pixel
     geometry, review state, `run_id`, and `geom_src` at citation time. Edits to
     the live row stay allowed; the claim page shows "changed since cited" when
     the live row no longer matches the snapshot.
   - No history table and no edit-blocking trigger for the pilot. Add one if
     snapshots prove too coarse.
5. **Claim:** subject, predicate and value in typed fields where the pilot
   needs querying, readable wording, author, review state, and claim version.
   `claim_evidence` records `supports` or `contradicts`, the cited reading, and
   a short reason. An unsupported narrative sentence cannot appear as a reviewed
   claim.
6. **Time:** store survey/revision, printing, digitization, observation, and
   assertion dates separately, each with precision and source. Null means
   unknown. A map-year observation does not automatically create a real-world
   `valid_from`/`valid_to` interval. Approximate and disputed dates require an
   explicit qualifier, not a false precise date.
7. **Rights:** record a provider's statement verbatim, its source URL and
   retrieval time, and whether it applies to metadata, the map work, a scan,
   or a VMA derivative. The existing `rights` columns do not qualify — they were
   normalised by mig 096 — so the pilot refetches Gallica's own wording. Record
   a legal conclusion separately with its author and basis. `null` means no
   statement found, never permission or prohibition.
8. **Uncertainty:** retain OCR confidence, review verdict, georeference source
   and error measure, and identity-match confidence separately. Never turn
   these into one unexplained certainty score. **Name the error measure**: for
   1882 there are three figures in circulation — 12.7 m (similarity RMSE, 10
   GCPs, `worked-example-1882.md`, corrected 2026-09-19 from 11.3 m), 10.6 m
   (affine), and `geom_rmse` 16.50 (a stored per-map constant, not a per-point
   residual). The packet reports one with its method and source. Absence of a
   feature on a sheet is not evidence of real-world absence without a coverage
   and legibility assessment.

Use immutable IDs for citations. Corrections append a claim version or
supersede an earlier assertion; they do not silently alter a published study
snapshot. Keep the live view current while a snapshot records the exact IDs,
values, source hashes, georeference, method, and export date used by a study.

## Delivery order

### 1. Reconcile the 1882 source chain

Inventory the Gallica record, the VMA map, its three `map_images` rows, the
`v1b` OCR run, and the approved footprints. Before pinning `geom_src`, confirm
the stored annotation mirror matches the live Allmaps annotation —
`district4-mirror-sync` found four of the six District 4 mirrors stale and did
not record which. Refetch Gallica's verbatim rights statement. Record each link
with its reason.

**Exit:** each link is inspectable, the georeference the pilot will cite is the
one Allmaps serves, and the rights wording is the provider's own.

### 2. Claims, cited evidence, and one subject

One migration, following `docs/db-guidelines.md`: `subjects`, `claims`,
`claim_evidence` (invariant 4). RLS copies `map_images_select_visible_parent`:
a claim or its evidence is readable anonymously only when every cited map is
public. Create one reviewed subject for the selected feature and link its
attested name variants without merging every similar spelling. Add a claim
with its supporting label and footprint, then a deliberately conflicting or
uncertain reading. Keep machine readings visible as machine readings until a
person reviews them. Provide an editor path for revising a claim that keeps the
previous version.

**Exit:** deleting a cited footprint fails with a readable message; editing a
cited label shows "changed since cited" on the claim; a claim citing a draft map
is invisible to an anonymous caller and absent from every public API.

### 3. The public feature page

Render the claim from the sheet page: each citation opens the exact crop in the
existing sheet viewer, against the image its pixels were measured on. State what
each source depicts, distinguish interpretation from transcription, and show
disagreement.

**Exit:** a reader can follow a label or polygon from the claim to its provider
and exact pixels; changing the georeference leaves the pixel citation intact.

### 4. Publish a reproducible research packet

For the pilot question, export JSON plus CSV/GeoJSON where applicable: query
parameters, source/printing/image IDs and dimensions, source URLs, pixel
selectors, the `cited_value` snapshots, claim versions, the annotation JSON with
its `geom_src` and named error measure, methods, verbatim rights statements, and
known coverage gaps. Include stable page links and a generated citation. Freeze
the packet so a later OCR correction does not rewrite it.

**Exit:** another researcher can reproduce the displayed evidence from the
packet and identify what changed when the live page is updated.

### 5. Generalize only after the pilot

- **Second provider, series path.** Write two CartoMundi → IGN/Nakala fixtures,
  one ambiguous or unmatched, before any general matcher. Decide there whether
  `cell_printings` can carry raw payload, fetch time, and content hash, or
  whether `external_records` is needed. The CartoMundi snapshot
  (`src/lib/data/maps/cartomundiIndex.json`) is an import source, not an
  identity authority; re-import must not duplicate a provider ID.
- **Differing images.** Add image dimensions/fingerprint to `map_images` when a
  citation first spans two images of different size — 1942 is the known case.
- **Manual readings.** `observations` and `evidence_anchors` when a reading has
  no OCR or footprint row to cite.
- **Search.** Spatial/time search over reviewed readings and claims, reusing
  `/catalog`, `/catalog/place`, the series pages, `/api/search`, and
  `/api/export/footprints`. Add indexes for queries the pilot actually runs.
  Broaden to period texts after the same citation chain works for their
  page/image evidence.

**Exit:** one query can return reviewed depictions of a feature across maps,
with dates, image citations, contrary evidence, rights statements, and explicit
coverage gaps. The same schema supports a second source type without a new
parallel knowledge store.

## Neighbouring items

- `ocr-merge-evidence` produces the structured agreement data a claim will cite;
  it does not block the pilot, which cites reviewed `v1b` rows directly.
- `source-agreement` — a sheet reading and a period text agreeing is two
  `supports` rows on one claim. Build it on `claim_evidence` rather than beside it.
- `attested-variants` writes `place_names.variants[]`; the pilot's subject links
  to those variants, it does not copy them.

## Verification and boundaries

- Migration replay and generated types; use the local write-test stack for the
  delete refusal, the "changed since cited" check, export, and RLS.
- Check a draft map, a corrected OCR reading, a changed georeference, two
  printings of one cell, a provider record with no VMA match, and conflicting
  claims. These cases reveal identity and citation failures that a happy-path
  page cannot.
- Keep provider licenses as sourced evidence. Do not infer a reuse grant for
  the underlying cartographic work from a Nakala item field alone.
- Start with a curated pilot. Automated extraction can supply candidates, but
  it cannot publish historical conclusions or rights determinations by itself.

The first implementation deliverable is **one complete, citable feature page
and its frozen research packet**. That result tests the schema and the research
workflow together before corpus-wide ingestion.

## Checklist

Tick in place while the pilot runs; when `evidence-chain` closes, the roadmap
entry moves out and this section stays as the record. Step 5 gets its list only
after step 4's exit passes.

**Step 1 — reconcile the 1882 chain**

- [ ] Pick the pilot feature: a reviewed `v1b` label joined by `footprint_id`
      to an approved footprint — inside the traced `seg_eval --window` area
      if that tracing has landed, so one session serves both.
- [ ] Diff the stored annotation mirror against live Allmaps
      `9be3d4b042bc18fb`; sync if stale; record the `geom_src` to cite
      (`245d98f7f8d61572` as of 2026-09-30).
- [ ] Fetch Gallica's verbatim rights statement for `btv1b52508901z`, with
      URL and retrieval time.
- [ ] Record which `map_images` row the annotation is fit to (R2, IA and
      Gallica all 12102×8982).
- [ ] Write the inventory, one reason per link.

**Step 2 — claims and cited evidence**

- [ ] Migration: `subjects`, `claims`, `claim_evidence` (restrict FKs +
      `cited_value`); RLS on the `map_images_select_visible_parent` pattern.
- [ ] Regenerate types; `npm run check` stays 0/0.
- [ ] Trace/review UIs show a readable refusal on deleting a cited row.
- [ ] Seed one subject, one supported claim, one conflicting reading.
- [ ] Editor path for revising a claim, keeping the previous version.
- [ ] Write smokes: cited delete fails · "changed since cited" shows · a
      draft-map claim is invisible to anon.

**Step 3 — the public feature page**

- [ ] Claim page: each citation opens the exact crop on the right image.
- [ ] Agreement and disagreement shown; interpretation apart from
      transcription.
- [ ] Browser smoke: a claim opens its crop.

**Step 4 — the research packet**

- [ ] Export JSON (+ CSV/GeoJSON) with every field listed in step 4.
- [ ] Freeze it; prove an OCR correction afterwards leaves it unchanged.
- [ ] `docs/testing.md` entries and the test count in `CLAUDE.md`.
