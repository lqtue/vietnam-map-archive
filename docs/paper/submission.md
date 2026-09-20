# EarthArXiv submission packet

Generated from `draft.md` on 2026-09-20 — regenerate rather than edit by hand, so the abstract here
can never drift from the one in the manuscript. The PDF to upload is
`docs/paper/blind-by-construction.pdf` (20 pages, A4).

**Do the Zenodo deposit first.** §11 promises a data DOI; posting before it exists means a v2 whose
only change is a DOI. `work/zenodo/zenodo-metadata.json` is the form-fill for it.

## Fields

**Title**

Blind by construction: verifying a georeferenced map series when the check shares the error

**Subtitle / running head**

Two colonial map series of Vietnam, 514 sheets

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

Georeferencing a historical map series is usually described as a per-sheet problem: identify control points, fit a transformation, report a residual. For a series, the control is frequently already present — embedded in a GeoPDF, printed as graticule corners, or recoverable from a neatline and a sheet index — and the difficult work moves to verification: establishing that a whole collection has been placed coherently, and that the resulting evidence can detect its own errors. We report a documented archive failure that makes the distinction concrete. In the Vietnam Map Archive, a substantial subset of US Army Map Service L7014 sheets was published under a wrong datum; a controlled reproduction measures CRS displacements of 395–528 m across 269 sheets, with a median of 455 m. The archive's per-sheet graticule check rejected 11 of 437 sheets and passed all 269 displaced ones, because a sheet's control points and the graticule it prints are translated together by the same wrong datum. The fault was not hidden by noise; the check was blind to it by construction. Working from two colonial series and 514 pipeline-georeferenced sheets, we develop a taxonomy that classifies verification checks by scope and by the information each has already committed to, and show which error class each therefore cannot report. Two instruments detect this displacement: a free seam census, which requires no external reference but sees the fault only because it is partial across the series, and an outside CRS decision that refuses rather than accept the smaller miss. A lattice occupancy check separately catches a sheet that passes every per-sheet test while sitting on another sheet's cell, 75 km from the city it is named for. The claim is deliberately narrow: naming a check's scope and its committed inputs is a precondition for interpreting the residual it reports.

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
