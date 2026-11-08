# Series-led admin units and Saigon's states

Status: proposal, 2026-10-19. Phase 0 is under way; its working note is
`work/image-processing/experiments/admin-lines/khanh-hoi-chain.md`. Serves bet 1c in `docs/NOW.md`.

**Question.** Can one small Saigon area be traced from the 2025 reform back to the 1882 plate, each step
a typed link with a source, and how many of those steps have a source that does not copy the others?

**Answer wanted.** "N of M steps have an independent source" for the pilot area, with the map link
(village → old ward → 2025 ward) measured by area, not by name.

**So what.** The link is VMA's core claim. Admin units are the first record beyond the 1882 sheet, and the
2025 reform is the case the press and a research reader both care about. A count of independent steps is a
check that could fail; a chain of agreeing sources that copy each other is an echo.

## The idea gate

1. **Bet:** 1c (admin units over time, Saigon).
2. **Smallest test:** one area (Khánh Hội, Vĩnh Hội, Tạm Hội), one plate, one number (steps with an
   independent source).
3. **Kill:** no primary text found for 301/UB, 67-HĐBT, 147-HĐBT and 258-HĐBT (vbpl.vn, Công báo,
   printed gazettes) by 2026-11-30 → publish N of M with that gap stated, and Phases 1–3 do not start.
   Found 2026-10-27: 67-HĐBT, 147-HĐBT and 258-HĐBT in full (67 has no Quận 4 content); 301/UB not found.

## What it joins

- **Line 1, names and boundaries.** Names from decrees, books and lists; boundaries and printed names read
  from the map series. Joined by typed links, each with a source and a check.
- **Line 2, a city's states.** Who or what stood at a place on a date (directories, admin books).
- **A derivation graph** (which map is drawn from which). It says which agreements are independent witnesses.

**The rule.** Past names must come from sources independent of the maps, or a match proves nothing. A
source family is a set of sources that may copy each other (the NAC2 captions and the TTLTQG II archive
guide are one family). A family counts once.

**Counting N of M.** Fixed before counting, so the count cannot be recut until it passes:

- A step is one dated act or one typed link between two dated units. M is the rows of the working note's
  table as of 2026-10-26 (1, 2, 3, 4, 5, 5b, 6: M = 7). A later find joins M only by a dated edit here.
- A step counts in N when two source families agree that it happened. A map may be one of the two for a
  step it prints; it never adds a step.
- Two sources are one family if they share, or may share, an input. Same family is the default unless a
  reason is cited. In phase 0 the plate is one family, and Bigrel (c. 1873) stays out of N until its
  derivation is checked.
- "Weak" (act text unread) and "conflict" (sources disagree that it happened) are recorded and not
  counted. A date conflict alone is recorded beside the step and does not remove it.

Under this rule the note's table gives **3 of 7**: steps 4, 5 and 6 count; 2 is weak; 5b is a conflict;
1 and 3 are not independent.

## The pilot area

Khánh Hội, Vĩnh Hội and Tạm Hội (today's Quận 4), tổng Dương Minh on the 1882 *Plan topographique du 20e
Arrondissement*. Chosen over Xuân Hòa, which had too little written evidence. It has dated acts from 1880
to 1959, three villages with printed limits on the plate, and 2025 ward polygons in OpenStreetMap.

## Link types

Each link names its act, its date, its source family and whether an independent source exists.

| Type | Example |
|---|---|
| `part_of` | village in tổng Dương Minh, hạt 20 (13/12/1880) |
| `merged_into` | Tam Hội, Vĩnh Hội into Khánh Hội (2/5/1888) |
| `annexed_to` | part of Khánh Hội to Saigon (15/3/1895); the rest (16/8/1907) |
| `defined_by` | Quận Tư by street boundaries (110-NV, 27/3/1959) |
| `built_from` | 2025 ward from old numbered wards (NQ 1685/NQ-UBTVQH15) |
| `overlaps` | 1882 village and a ward, with the area share |

Never `same_as`: a ward is not a village, and the 2025 ward reuses a village name but is built from other
units. The link is the overlap, and only geometry shows it.

## Phases

**0. Finish the chain for the area.** Report "N of M steps have an independent source".

- *0a, text chain.* Done in draft: acts and sources per step.
- *0b, map link.* Four steps, in this order:
  1. **Land from river.** Done 2026-10-19, but not reproducible. Water was the blurred b* channel 5 below
     the paper's; plain `colour.py` blue leaks across the river. Land is the region reached from a seed
     in Khánh Hội, closed in the south by a straight line labelled modern (Kênh Tẻ was dug in 1904–07,
     after the plate). Against the 2025 OSM wards, river sides only: median 120 m, maximum 345 m, area
     IoU 0.74; the kill (more than a village width) was not hit. The script, `land_from_water.py`, was
     never committed and is lost (checked 2026-10-26), so the result is a recorded run, not reproduced.
     Rewrite and commit it before any number from this step is published.
  2. **Split by the village limits.** Cut the land along the black dash-dot lines into Khánh Hội, Vĩnh Hội and
     Tạm Hội. Hand-traced now (Khánh Hội is drawn: footprint `60b21abf…`, 0.97 km²); the machine reads these
     lines poorly near the city. With land first, only the inner lines remain to draw.
  3. **Overlap.** Each village against the old numbered wards (OSM, 2025-06) and the three 2025 wards
     (OSM, 2025-08). The 2025 match is partly an echo, since OSM was likely drawn from the act.
  4. **Measure the placement.** The plate has 3 control points, none near Quận 4. Add 2 or 3 near
     Khánh Hội so the overlap carries an error in metres.
- *Kill for 0:* the gate's kill above.

**1. Derivation edges for the sheets that cover the area.** Which map is drawn from which. Use printed
statements first (the 1882 plan states a reduction of 1:20,000 surveys; the Olivier plan states 1795
origin), then content-based inference, always labelled. Model: PROV-O `wasDerivedFrom`, `used` in the
planned `activities` table (`data-model-target.md`). *Kill:* most sheets state no source → infer from
content and label it.

**2. Printed names on the series, matched to the chain.** Names read from the sheets (OCR labels, human
check) against the names in the acts. Tone marks (Hòa, Hoà, Hóa) break matches; normalise first. *Kill:*
fewer than half of the printed names readable and matchable → fix OCR before going on.

**3. States for one street at three dates.** Occupants from directories (Annuaire de la Cochinchine,
Vivien 1899–1905, Aspar c. 1921, Chronicle & Directory, the 1924 and 1928–29 indicateurs). Street-name pairs
come first, because a directory address needs the street's name at that date (for example Chasseloup-Laubat →
Hồng Thập Tự → Xô Viết Nghệ Tĩnh → Nguyễn Thị Minh Khai; the 1955 act is blog-only). *Kill:* fewer than half
the addresses resolve → find street-name pairs first.

## Sources and licences

- Public repo: acts, dates, source names and page numbers only. No Library file, no OCR text, no excerpt of
  the 1959 book or the archive guide (both copyrighted). `docs/private/` is gitignored.
- OSM polygons are ODbL; cite the attic query and its date.
- NAC2 captions are cited as scholarship; their images are web-size and not used for work.
- Do not write that no open record covers 1862–2004; OpenHistoricalMap has about 170 units for 1976–2004.
  The narrower sentence carries its check date (19 Oct 2026, Vietnam bounding box).
- VMA's own words: not "time machine" (`docs/CONCEPT.md`).

## Open conflicts

- 110-NV: 27/3/1959 (NAC2, archive guide) or 27/2/1959 (the 1959 book alone).
- The 1907 annexation: 16/8 (NAC2) or 31/12 (Saigoneer, digest).
- 1888 merger of Tam Hội into Khánh Hội, while the 1895 and 1907 texts still name Tam Hội.
- Phường 4's lineage, 1976–1988 (vi.wiki says both dissolved in 1981 and new in 1988); the 1982 act (en.wiki
  names P16 only, vi.wiki P16 and P18).
- Decrees 213-QP (1962) and 227-QP (1965), listed by the archive guide and unchecked.
- Whether the Indochine 100k and L7014 sheets print village or district lines.

## Not in this plan

Admin units for all of Vietnam (parked; needs a line-type model for 1:25k bounds), Walk, the 4D city.
