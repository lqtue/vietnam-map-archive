# 1882 extraction — one plan, with implementation gaps made explicit

**2026-10-12.** The owner compared the clean archived 91-block blog preview with residue in
current proposals and asked to consolidate the delivery plan, then implement all gaps including
MapSAM2 memory and investigate metadata context. Current scope and verification are in the
[consolidated plan](../image-processing-1882-plan.md); this is a decision record, not a new result.

Decisions: preserve saved corrections; offer a reversible Simplify preview; trace complete
independent parcel windows before tuning; compare text-aware boundary refinement and
colour-prompted SAM2, including memory and metadata ablations; review whole parcels first,
then roads, then lots/buildings. The existing Colab worker writes proposals, so the comparison
needs an interactive notebook with saved artifacts and no database writes. GPU startup and
independent reference tracing still need the owner.

The contour-only and rectangle text-blanking failures remain constraints on new experiments.
The previous evaluator used independent best matches in both directions and omitted
per-type filtering in its window report. The revised scorer fixes both before reporting precision.

The live counts and simplification trial were independently reproduced from a paged snapshot;
local artifact counts are distinguished from that frozen database state. No new segmentation accuracy claim,
reference polygons, GPU run or database write was produced by consolidating the documents.

## Local implementation and verification

Implemented the preview/edit guard, class-aware one-to-one evaluation, explicit metadata context,
real cross-tile memory, bounded text-aware refinement and contour export. Regularization now
preserves holes/components, model mask output retains substantive components and closed rings,
and import refuses holes the current table cannot represent. Closed road/water rings render as
areas; open centrelines remain lines and are not invented as spatial polygons.

The paged snapshot reproduces 814 pending imported plots and 496 buildings, with 778 plots matching
raw outlines under the documented IoU/boundary rule. The Shapely simplification figures reproduce
the supplied trial; this does not validate a tolerance or certify map accuracy. See
`work/MapSAM2/audit_snapshot.py` and local `results/seg-comparison-20261012/baseline-audit.json`.

The new 152-block street/water prior is included as a candidate. Its seven-plot overlap is not a
held-out parcel score. A read-only timing reader checks the producing session's outline hashes and
keeps review latency separate from correction effort. No edits were made to that session's code
or review records.

A real, randomly initialized SAM2.1 model exercised memory encoding, retrieval, attention and
prediction on CPU; the LoRA wrapper preflight also passed. Synthetic geometry/controller tests,
the mocked Validate browser flow and migration 121's disposable SQL fixture passed. Verification
also includes `npm run check` (0 errors/warnings), the production build with its bundle check,
17 targeted Playwright checks and 12 Python comparison checks with the real-model smoke enabled.
The actual
1882 T4 run and independent owner references remain required. The notebook/archive were prepared
locally; no database rows, approvals, production migrations or deployment were changed.
