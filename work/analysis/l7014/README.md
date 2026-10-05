# L7014 catalog and processing inventory

Inventory first: reconcile the survey's cells, institutional source items, archive records and
local processing inputs before changing printing metadata or placement. The dated
[audit](../../../docs/journals/261003-l7014-audit.md) describes the earlier status snapshot and
the proposed closing work. This inventory was refreshed from read-only database reads at
16:11 ICT on 2026-10-03. No database rows or source masters were changed.

## What is organized

| Object | Count | Meaning |
|---|---:|---|
| Survey cells | 627 | Same cell keys in the survey index, corrected lattice and database |
| PCL source items | 535 | 510 PDFs and 25 JPEGs, covering 534 cells |
| TTU source items | 140 | PDFs plus 140 native JPEG processing inputs |
| ANU references | 159 | Recorded handles; reference-only under the user's decision |
| Reconciled source items | 834 | Institution items; printing identity remains unreviewed |
| Archive maps records | 671 | 519 public and 152 drafts, covering 584 cells |
| Gaps in known source inventories | 43 | Listed individually in the cell master |
| Preserved margin crops | 292 | Two crops for each of the 146 transcription candidates |
| Preserved rough neatline readings | 34 | Evidence only; not applied to operational corner files |

PCL has two source items for 6542-3, a PDF and a JPEG. That explains why its item count is one
greater than its cell count. A whitespace mismatch in the 6331-4 catalog filename and the compact
6342-4 filename are resolved through catalog entries rather than treated as missing scans.

## Where to look

The organized local pack is [work/l7014/inventory](../../l7014/inventory/). It contains:

- [Cell master](../../l7014/inventory/manifests/cell-master.csv): one row per cell, with source
  counts, maps ids, local paths and available reading evidence.
- [Source items](../../l7014/inventory/manifests/source-items.csv): one row per institutional
  item, with source URL, database source id and local master paths and hashes. Maps ids are
  candidates matched by cell and institution; they do not certify identical printing content.
- [File manifest](../../l7014/inventory/manifests/local-files.csv): paths, file sizes, SHA-256,
  image dimensions, and device/inode identity. PDF validity here means a PDF signature;
  JPEGs passed Pillow's `verify()`. Neither establishes correct printed content or placement.
- [Exact copy groups](../../l7014/inventory/manifests/exact-copy-groups.json): byte-identical
  files, distinguishing multiple paths to one file from separate physical copies.
- [Summary](../../l7014/inventory/summary.json): snapshot time, reconciliation checks and gaps.
- `catalogs/`: saved survey index, corrected lattice, PCL/ANU catalog records, database source
  items, selected map inventory fields and TTU ingest lists.
- `evidence/`: preserved margin crops and task lists, title transcriptions, ANU reads, rough
  neatline readings and the detector snapshot. Temporary-session originals were left intact.

Source masters stay in their existing locations. The manifest records both workspace and
external paths. The 510 PCL PDFs reached through two locations share the same device/inode
identities; those paths do not represent another full set of physical copies. Six earlier TTU
JPEGs have three separate byte-identical copies each, about 82 MB of extra bytes in total.
This is a cleanup candidate list, not permission to delete those copies.

## Inventory checks and unresolved evidence

All 535 cataloged PCL items have matching local files. All 140 known TTU PDFs have native
JPEGs. None of the inventoried files failed the signature/image checks. All locally assigned
cell keys belong to the survey. The 627 cell keys agree across the raw index, corrected lattice
and database; this does not fix the already documented database bbox datum fault.

The catalog pack exposes seven missing TTU `sheet_sources` entries: 5750-3, 6131-1, 6131-2,
6132-2, 6143-1, 6144-4 and 6232-1. Three TTU source PDFs have no TTU maps row: 5729-1, 5926-2
and 6542-3. Preserve them while reviewing their prior same-edition skip decisions.

The four margin readers did not produce completed output files. Their crop inputs and task
lists are preserved, so transcription can resume from durable inputs. The two rough-neatline
files are preserved and indexed without processing any scan. Printing identity, complete
transcription, placement review, full R2 object ownership and current external-catalog
completeness remain outside the file checks performed here.

## Processing order after catalog reconciliation

1. Review this source/item inventory and reconcile the seven missing source entries and three
   skipped TTU copies.
2. Finish printing transcription from the preserved evidence; retain unreadable or ambiguous
   fields explicitly. Keep the existing sheet names.
3. Decide which copies are the same printing and which must be retained. Preparation year,
   edition year and actual printing/reprint year must be distinguishable.
4. Place and visually review retained sheets, then present the reviewed publication inventory.
5. Correct coverage geometry and publication counts, then inventory R2 before storage cleanup.

## Rebuild the inventory

[build_inventory.py](build_inventory.py) reads a fresh local Supabase snapshot and existing
catalogs/files. A bare invocation prints its plan without writing. With `--apply` it writes only
the local inventory pack and copies saved reading evidence; it never modifies masters, the
operational neatline files or database rows.

```bash
work/ocr/.venv/bin/python work/analysis/l7014/build_inventory.py --apply \
  --snapshot /private/tmp/vma-l7014-status-snapshot.json
```

The snapshot's producer is the read-only `/private/tmp/vma-l7014-status-audit.mjs` from the audit
session. Temporary snapshot/script paths may not survive; obtain another paged, read-only
snapshot with top-level `at`, `maps`, `series_cells` as `cells`, and `sheet_sources` as `sources`
before rebuilding if it is gone. The preserved catalog pack remains usable without that script.
