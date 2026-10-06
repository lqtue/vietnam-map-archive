# Framework audit follow-up — 2026-10-05

This record finishes the repository-number and documentation reconciliation after the framework
landscape audit. Database checks were read-only, using the service role so drafts were counted.
Historical totals remain dated records: querying today's database cannot reproduce an earlier snapshot.
The ink measurement remains provisional and deferred until the author finishes OCR editing.

## Current inventory

Read at **2026-10-05 15:43 UTC**. Each table was paged in ranges of 1,000, ordered by `id`, until
the last short page. Counts across tables are sequential reads, not a transaction snapshot.

| Population | Count |
|---|---:|
| `maps`, all statuses | 1,499 |
| `maps.status = public` | 1,033 |
| `maps.status = featured` | 5 |
| `maps.status = draft` | 460 |
| `maps.status = archived` | 1 |
| Published maps (`public` + `featured`) | 1,038 |
| `ocr_labels`, all review statuses | 15,133 |
| Distinct `ocr_labels.map_id` | 24 |
| Pending OCR rows | 11,487 |
| Rejected OCR rows | 3,147 |
| Validated OCR rows | 499 |
| OCR rows with non-null `footprint_id` | 8 |
| `scout_candidates`, all rows | 1,067 |
| `georef_versions`, all rows | 604 |
| Distinct versioned maps | 591 |

These OCR totals include rejected rows and legend entries; they are not counts of distinct place
names or a reviewed map-text benchmark. The 8 polygon links are a storage-field count, not
cross-edition entity links and not a precision/recall measurement. The earlier public-key count
(10,574 rows, 492 validated) was a different visibility population read earlier that day.
The recorded 274 maps (September), 859 maps (October 1), 13,525 extractions and 14,506 labels
cannot be re-derived as historical snapshots from today's mutable rows.

For reproduction, select `id,status` from `maps`; `id,map_id,review_status,footprint_id` from
`ocr_labels`; `id,map_id,stamp,gcp_count,rmse_m,rmse_method,origin` from `georef_versions`.
Use an exact head count on `scout_candidates`. Never print credentials or reviewer identity columns.

## Placement and migration checks

`supabase migration list` showed matching local and remote entries through **111**, including 103.
The local `111_map_regions.sql` file was initially untracked. The concurrent region work committed
it during this pass in `520209a7` (`feat(catalog): list all covered provinces`), so it is now tracked.
This pass did not stage or commit that work.

1882 has two database history rows, both with 8 GCPs and origin `unrecorded`:
`2026-09-22T08-08-00-262Z` and `2026-09-23T06-34-13-510Z`. Their named `gcp-roundtrip-rms`
values are 6.61543 m and 15.1354 m. These are a different measure from similarity-fit RMSE.
Rehashing the live 1882 mirror with the shared `describeAnnotation()` implementation gives
`93c4487e621f83c9`, 8 GCPs and a 12102 × 8982 source. `evidence-chain-plan.md` now cites that
version instead of presenting the older `245d98f7f8d61572` as current. No upstream sync was run.
The 604-row inventory shows that the version table is populated; it does not establish complete
coverage of every Storage annotation or every writer. The four missing writers remain open in
`knowledge-system-plan.md` §5 and ROADMAP `georef-versions`.

Re-run against the currently served annotations:

```bash
work/ocr/.venv/bin/python work/analysis/district4/georef_error.py --maps \
  0e02b9d9-9d40-4cca-8e41-8c8373d54d3b \
  eca788e5-6780-4dca-bf23-7651a1c48aba
```

| Sheet | GCPs | Scan dimensions | Declared model | Similarity RMSE / worst | Affine RMSE / worst |
|---|---:|---|---|---|---|
| 1882 | 8 | 12102 × 8982 | helmert | 12.3 / 19.9 m | 11.4 / 16.3 m |
| 1942 | 8 | 14915 × 12602 | polynomial | 33.6 / 53.0 m | 26.5 / 45.4 m |

The script prints **1882 DID NOT REPRODUCE** because its embedded baseline is still the old
10-GCP set (12.74 m). The new output reproduces the October 1 recorded 8-GCP result; the baseline
warning is expected after that point-set change. No code or baseline was changed in this pass.
1942's 33.6 m is the comparison similarity residual; the declared affine model gives 26.5 m.
Neither figure is held-out positional accuracy. The historical 112 m value remains prose-backed
only; its exact nine-point annotation has not been reproduced here.

The historical 65.0% calculation is internally consistent with the saved September coverage table:
`(6,111 + 2,685) / 13,525 = 65.034%`. That checks its arithmetic, not the historical classifications.
The 9.0 m minimum is also recorded for 1968 in `work/analysis/district4/georef_error.md`; the
earlier audit's claim that it existed only in `related-work.md` was too strong. The 958 distinct
names figure still has no identified run and must not be used as an established result.

## Boundaries

The existing literature audit's full-text and funding uncertainties remain explicitly labelled.
This follow-up makes no new literature-novelty verdict, supervisor-availability claim, or fork
security assessment. It does not run a linkage evaluation, rerun the 1882/1898 overlap, or
re-measure ink; those are separate measurements, and the last depends on finished OCR editing.
