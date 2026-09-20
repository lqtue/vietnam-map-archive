# Visual plan — *Blind by construction*

**Rule:** every typeset manuscript page gets one visual anchor: a data figure, an editable
schematic, a table, or a captioned pull-out. No decorative map imagery. Every quantitative figure
must derive from `figures.md`; every schematic must name the scope it does *not* test.

The final page count depends on the target venue template. This plan is a 12-page composition target
and must be reflowed only after the manuscript is typeset.

| target page | manuscript material | visual anchor | source / construction |
|---:|---|---|---|
| 1 | title + §1 | **Figure 1**, control-to-verification flow | editable Mermaid in `draft.md` |
| 2 | §2.1 | frame reused as input and yardstick | two-frame schematic: shared frame in amber, independent target in blue |
| 3 | §2.2–2.4 | **Figure 2**, evidence scopes | editable Mermaid in `draft.md` |
| 4 | §3 | corpus comparison | two-column series card: provenance, dates, input control, output |
| 5 | §4 | survey / cell / printing entity diagram | three-layer relation diagram; examples from `figures.md` §1 |
| 6 | §5 | L7014 pipeline | GeoPDF → neatline cutline → warp → PMTiles, with datum claim marked as unverified |
| 7 | §6 | Indochine frame reading | scan-edge cross section: thick neatline, graticule band, rim; measured offsets only |
| 8 | §7.1–7.2 | **Figure 12**, failure taxonomy + lattice collision inset | existing table in `draft.md`; inset depicts two sheets on one cell |
| 9 | §7.3 | seam census | histogram of 750 seams; separate 447–504 m band for 33 hand-sheet seams |
| 10 | §7.4–7.6 | datum-fault causal chain | declared CRS → fallback / area-of-use behaviour → 470 m shift → independent `pick_crs` |
| 11 | §7.7 + §8 | **Figure 13**, tile-key mismatch + negative-results panel | Mermaid in `draft.md`; small river-channel aperture diagram |
| 12 | §9–10 | **Figure 14**, reproducibility boundary | editable Mermaid in `draft.md`; include release DOI placeholder only after minting |

## Build order

1. Typeset the manuscript and confirm its real page count.
2. Produce Figures 3–11 as deterministic SVG/PDF from the cited measurements, not AI-generated
   graphics.
3. Replace Mermaid source with venue-compatible vector exports while retaining the Mermaid blocks as
   editable source.
4. Check every caption against `figures.md`, including present-versus-dry-run status for L7014.
