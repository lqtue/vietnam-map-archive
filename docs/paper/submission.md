# EarthArXiv submission packet

Generated from `draft.md` on 2026-09-20; subtitle and abstract re-synced 2026-09-30 — regenerate rather than edit by hand, so the abstract here
can never drift from the one in the manuscript. The PDF to upload is
`docs/paper/blind-by-construction.pdf` (25 pages, A4).

**Do the Zenodo deposit first.** §11 promises a data DOI; posting before it exists means a v2 whose
only change is a DOI. `work/zenodo/zenodo-metadata.json` is the form-fill for it.

## Fields

**Title**

Blind by construction: verifying a georeferenced map series when the check shares the error

**Subtitle / running head**

Three historical map series of Vietnam

**Author**

| field | value |
|---|---|
| name | Tue Quang Le |
| ORCID | 0009-0006-5863-6011 |
| affiliation | Independent researcher, Ho Chi Minh City, Vietnam |
| email | lequangtuevn@gmail.com |

**Licence** — CC BY 4.0, matching the derived-data release and the earlier preprint.

**Subject area** — Earth Sciences; secondary Geographic Information Sciences / Physical Sciences
and Mathematics. Cartography and spatial data quality are the nearest terms EarthArXiv carries.

**Keywords**

historical maps, georeferencing, map series, verification, reference frames, reproducibility, spatial data quality

**Abstract**

Historical map series often supply their own georeferencing control, but agreement with that control does not independently establish placement. We examine this problem through a documented Vietnam Map Archive failure and a controlled reproduction on US Army Map Service L7014 GeoPDFs. Of 510 source files, 62 lacked usable control, 11 failed the graticule check, and 437 entered the faulty build. All 269 sheets with reproduced CRS displacements of 395–528 m (median 455 m) passed that check. The check evaluates registration in the sheet's own geographic CRS and cannot validate the subsequent datum transformation to WGS 84. Comparing the same 715 PDF/PDF edges before and after correction, the number with median outline separation above 100 m falls from 189 to zero. This establishes improved inter-sheet agreement, not independent absolute accuracy: the CRS-selection check and comparison lattice share the adopted Helmert parameters. A second case, from the Service géographique de l'Indochine 1:25,000 series, shows why coherent corner readings can still assign two sheets to the same cell. A third, from the same survey's 1:100,000 series placed automatically from catalogue extents, shows the structure recurring in a pipeline built after the first two were understood: a sheet whose catalogue west and south edges were wrong by 509 m and 544 m passed every per-sheet gate at 0.69% shape error, and was found only because its printed graticule ticks, an input those gates do not use, were read for calibration. Together these cases support a taxonomy of verification scope, committed inputs, detectable faults, and blind spots; the taxonomy is drawn from three cases in one project and is offered as an organizing account of this failure mode, not a claim that it generalizes across archives or pipelines. The contribution is an account, structured for reproducibility, of how checks can remain silent under specific shared assumptions, with explicit separation of source control, build measurements, and serving-state evidence; the derived data and code supporting that reproduction are pending deposit (§11).

## Related identifiers

| relation | target | status |
|---|---|---|
| supplemented by | Zenodo derived-data release | **pending** — mint before posting, then paste into §11 |
| author's earlier preprint | https://doi.org/10.31223/X5NJ4B | live |
| project | https://maparchive.vn | live |

## Before you press submit

- [ ] Zenodo deposited, DOI pasted into §11 of `draft.md`, `node scripts/render-paper.mjs` re-run,
      `tectonic` re-run, PDF re-checked.
- [x] Janata & Cajthaml year — **resolved 2026-09-20, 2020 is correct and the draft already had
      it.** MDPI's page prints 2021 because volume 11 is a 2021 volume; the publisher's Crossref
      deposit gives 2020-12-30 and no print date. See `claim-audit.md`.
- [ ] Confirm the ORCID record lists this preprint once EarthArXiv assigns the DOI.
