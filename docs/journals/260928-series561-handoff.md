# Series 561 georeferencing handoff — 2026-09-28

**Superseded by [the 2026-09-29 handoff](260929-series561-handoff.md).** This
file's "Immediate next work" (the 13-sheet boundary-trial table) is resolved:
11 landed, 1 (Muong Ou Tay W) stayed held on a genuine axis-scale gap with its
boundary now fixed, and 1 (Lang Son E) was found wrong on re-review and
reverted. Kept for the version-24–28 verified-state record below, which is
still accurate.

## Verified state

Repo: `/Users/airm1/Work/Projects/vietnam-map-archive`.
`DETECT_VERSION = 28`. Working code and docs are uncommitted; preserve them.

360 ingested maps: 135 previously published, **168 additional pending maps clear
locally, 57 held**. Total locally clear: **303**, up from the original handoff's
192. Version 28 completed all 225 pending rows.

| Remaining holds | Count |
| --- | ---: |
| Abnormal catalogue spans | 24 |
| Axis-scale only | 3 |
| Mixed failures, including 3 persistent exclusions | 30 |

Read-only `check`: 303 placements in 303 slots, zero lattice conflicts.
`regress`: 303 clear placements, zero corner movements over 2px.
Logs: `/private/tmp/indochine-place-v28.log` and
`/private/tmp/indochine-regress-v28.log`.
**No annotations or database statuses changed.**

Tracked changes: `scripts/indochine100k_georef.py`,
`docs/journals/260923-indochine100k-georef.md`, `docs/ROADMAP.md`, and this handoff.
The main journal records versions 12–23; its final section records versions 24–28.

## Current implementation

Keep all existing geometry gates, including the 1.5% axis-scale gate.

- Source-reviewed special spans: 9 unusual cuts/full sheets; exact catalogue
  key, span, dimensions, and four measured rims are pinned.
- Source-reviewed printed quads: 33 sheets, each supported by eight independently
  read printed ticks. Four corners reflect the sheet's slanted geographic
  edges; rectangle extrema had exaggerated spans. Opposite-edge spacing and
  catalogue-extrema checks remain active. Do not substitute kilometre-grid
  lines, pencil marks, or label digits for geographic ticks.
- Source-reviewed frames/boundaries seed observed source rules. Normal patch
  fitting and four-anchor reproduction within 2px remain required. A source
  review removes only a rim-offset spread objection; aspect, scale, catalogue,
  and lattice checks remain active. Reviewed decorative variants are excluded
  from the cross-series frame-offset median, but their footprints remain checked.
- Direct boundaries remain valid where source ink establishes the map edge
  without a separate inset rim (including Pailin E/W).
- Automatic spread retries now preserve `reviewed_boundary` fits: Bac-Kan E
  exposed a retry replacing its correct top rim with another rule.
- `place()` now fails closed after placement errors. Old geometry is retained
  for diagnostics but gets a held verdict, `placement_error`, and
  `placement_attempt_version`. Failed records retry on the next run even if an
  old detector version matches. Offline failure/retry simulation passed:
  `/private/tmp/vma_place_failure_check.py`.

Version 28 added eight verified clear sheets: Blao W, Bac-Kan E, Bai-Thuong W,
Beng Lovéa E, Bô Kham E, Cam Pha ouest W, Dong-Hoi W, and Dô-Son W.
Beng's earlier bottom trial at 6588px was a decorative band; the accepted
boundary is 6502.0px. Do not restore the rejected candidate.

## Immediate next work: unaccepted boundary trials

No changes from this section are landed. Version 28 is the verified baseline.
Bump to 29 when accepting another detector change.

Source overviews and metadata for the 41 non-span holds from version 27:
`/private/tmp/vma-remaining-overviews/NN-id8.jpg` and `.json`.
These numbers remain useful even though eight sheets subsequently cleared.

Trial results: `/private/tmp/vma-mixed-trial-NN.json` and `.jpg`.
Marked four-side strips: `/private/tmp/vma-mixed-contact-NN.png`.

| Number | Sheet | Trial source seeds (pixels) |
| --- | --- | --- |
| 15 | Kratié E | L305, B6403 |
| 16 | Krau Chmar E | B6492 |
| 18 | Lang Son E | B6643 |
| 19 | Luc-An-Chau E | T661 |
| 20 | Luc-An-Chau W | B6526 |
| 22 | Muong Ou Tay W | B6552 |
| 23 | Muong Phalane E | B6663 |
| 24 | Muong Phine W | B6575 |
| 25 | Muong Song Khone W | B6638 |
| 26 | Muong-Song-Khone E | B6560 |
| 28 | Muong-Vène W | B6563 |
| 29 | Pa-Kha E | B6648 |
| 30 | Pa-Kha W | R4757, B6605 |

The marked strips for 15, 16, and 18 have been visually inspected and follow the
map boundaries. Contacts exist for 19, 20, 22, 23, and 24 but still need inspection.
Generate contacts for 25, 26, 28, 29, and 30 and inspect them before acceptance.
Kratié's first left trial at 363px was an interior grid line; the corrected
narrow search at seed 305 is the one to use.

**Trial offsets are artificially zero on changed sides.** Their huge spread
verdicts are diagnostic artifacts, not permission to waive any gate. Twelve of
these 13 trials pass aspect/scale; Muong Ou Tay W still has a 2.0% scale gap and
needs printed-coordinate investigation after its boundary is fixed.

Resume procedure:

1. Inspect all marked source strips, rejecting decorative/interior rules even
   when geometry happens to pass.
2. Use the existing `SOURCE_REVIEWED_BOUNDARIES`, `SOURCE_REVIEWED_FRAMES`, and
   `SOURCE_REVIEWED_RIMS` infrastructure. Determine observed outer-frame seeds,
   fit all four final boundaries, and pin the resulting four anchors. Do not
   accept the temporary zero-offset geometry directly.
3. `/private/tmp/vma_mixed_integrate_trial.py` demonstrates in-memory constant
   trials; adapt its sheet list before running. It currently targets the seven
   already-landed sheets. Those integrated trial files are not the next batch.
4. Run sequentially: `place`, then `check` and `regress`; compare against v28.
   Accept only actual source-supported corrections that pass the existing gates.

Generators: `/private/tmp/vma_mixed_boundary_batch2.py`, `batch3.py`, `batch4.py`
(with the shared `vma_mixed_boundary_` prefix),
`/private/tmp/vma_kratie_boundary.py`, and
`/private/tmp/vma_mixed_contacts_batch2.py`.
All started experiment processes completed before the handoff.

## Other holds to investigate

Three scale-only sheets remain: Ban Khana W, Bun-Tai E, and Mon-Cay E.

- **Ban Khana W** (`cd980a1a-5eba-4e85-b7c7-343a38e6ea5b`, fkey60086,
  5040×7320): printed cell 33W has longitude 111.0–111.4g, one half-sheet west
  of catalogue coordinates. Eight ticks also show latitude extrema about
  0.0065g south of the calibrated catalogue. A longitude shift alone still
  fails the existing extrema gate. No correction or new exclusion is landed.
  Evidence: `/private/tmp/vma_ban_khana_quad.py`, even-tick contact 01.
- **Bun-Tai E** (id prefix `6bdd9ab8`): review longitude110.6/110.8 and
  latitude23.8/23.6 ticks. The serif latitude digit can resemble 5; do not
  interpret the ambiguous crop as a 2g latitude change without further evidence.
  Even-tick contact 06 is available.
- **Mon-Cay E** (id prefix `559ba082`): geographic longitude117.2/117.4 ticks
  are visible; right latitude picks hit kilometre-grid ink. Review the actual
  outer ticks before constructing a quad. Even-tick contact15 is available.

Tick artifacts: `/private/tmp/vma-remaining-ticks/`, `vma-even-ticks/`,
`vma-outer-ticks/`, `vma-odd-outer-ticks/`, `vma-corrected-ticks/`.
These use the earlier 27-sheet scale-only numbering, distinct from the 41-sheet
boundary overview numbering. JSON values are hypotheses until the printed label
is read. Source tick generators and quad builders use corresponding
`/private/tmp/vma_*_ticks.py`, `*_quads.py` scripts; inspect them before reuse.

Other non-span overviews still require review: 11 Ha-Lang W (correct-looking
rims, 2.1% scale), 12 Keng Kabao (wide sheet), 13 Kompong Som W (printed
“coupure spéciale”), 17 Lai Châu E (correct-looking rims, ~1.5% scale),
27 Muong-Tè E (correct-looking rims, 2.2% scale), and 31–41. Number14 is the
persistent Kompong Sralao W overlap hold.

The 24 abnormal catalogue-span holds have prior detector candidates in
`/private/tmp/vma_abnormal_candidates.json` (all33 original span failures;
9 now accepted). Source overviews: `/private/tmp/vma-overview-id8.jpg`.
Determine the actual sheet/cut identity from printed ticks and titles. IGN WKT
matches catalogue geometry and is not independent accuracy evidence.

## Operational constraints

Read `docs/lessons.md` before a pass producing numbers and `work/CLAUDE.md` before
editing under work. Crops, cache, and per-map JSON under `work/indochine-100k/`
are intentionally untracked. Preserve them. `place()` regenerates local JSON;
persistent exclusions must live in `CALIBRATION_HOLDS`.

Do not run `annotate --apply`, publish, or change database statuses without an
explicit request. Sandbox source reads may fail DNS; use the normal escalation
flow for read-only network access. Avoid parallel placement mutations.

Method papers: `/Users/airm1/Downloads/GeorefHistMapSeries.pdf` and
`/Users/airm1/Downloads/23aiai.pdf`.
