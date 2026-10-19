# Khánh Hội and Vĩnh Hội (Quận 4): phase 0 chain, 2025 back to the 1882 plate

Bet 1c in `docs/NOW.md`. Draft of 2026-10-19; nothing here is final until the village trace is checked.

**Question.** Can one area be traced from the 2025 reform back to the 1882 topographic plan, each step a
typed link with a source, and how many steps have a source that is independent of the others?

**Answer so far.** 3 of 6 steps firm, 1 weak, 2 not independent. Table below.

**So what.** The kill test for bet 1c turns on 1976–2004: that stretch still rests on one wiki. Pre-1945 and
1959 are well covered; the plate itself is placed (3 control points, affine, no residuals).

## Links, newest first

"Source family" means sources that may copy each other count once. NAC2 captions and the TTLTQG II archive
guide come from one archive, so they count as one family; Baudrit (1943) and the 1959 book are separate.

| # | From → to | Type | Act and date | Sources | Independent? |
|---|---|---|---|---|---|
| 1 | Phường Khánh Hội, Vĩnh Hội, Xóm Chiếu (2025) ← old wards P1, 2, 3, 4, 8, 9, 13, 15, 16, 18 | `built_from` | NQ 1685/NQ-UBTVQH15, 16/6/2025 | act text via luatvietnam (digest); OSM polygons (overlap matches the act for Khánh Hội and Vĩnh Hội) | **No.** OSM was likely drawn from the act, so it is an echo, not a witness |
| 2 | P5 → P2, P12 → P13 (2021); P6 → P9, P10 → P8, P14 → P15 (2025) | `merged_into` | NQ 1111/NQ-UBTVQH14, 9/12/2020; NQ 1278/NQ-UBTVQH15, 14/11/2024 | vi.wiki footnotes, press snippets; OSM snapshots 2020-12, 2021-02, 2025-06 are consistent | **Weak.** Act texts unread for Quận 4 |
| 3 | numbered wards, 1976–2004 | `renumbered`, `merged_into` | 301/UB 20/5/1976; 67-HĐBT 1981; 147-HĐBT 1982; 258-HĐBT 1985 | vi.wiki only; NAC2 #47 names 67-HĐBT but gives no Quận 4 content | **No** |
| 4 | Quận Tư (1959) = all of today's Quận 4; 41 phường for the city | `defined_by` | 110-NV, 27/3/1959; 504-BNV/HC/NĐ, 22/4/1959; 1434-BNV/HC/NĐ, 31/10/1960 | NAC2 #38, #39 and the archive-site page; the 1959 book (Trần Văn Đĩnh) prints the same boundary | **Yes**, with a date conflict: the book prints 27-2-59 |
| 5 | Khánh Hội village → Saigon city (part 1895, rest 1907) | `annexed_to` | 15/3/1895; 16/8/1907 | NAC2 #23–25; guide A; Baudrit (1943) for 1895 | **Yes.** Saigoneer gives 31/12/1907 for the formal step: conflict |
| 5b | Tam Hội, Vĩnh Hội → Khánh Hội | `merged_into` | 2/5/1888 | NAC2 #18, #24 | **Conflict.** The 1895 and 1907 texts still name Tam Hội as a village |
| 6 | Khánh Hội, Tạm Hội, Vĩnh Hội in tổng Dương Minh, hạt 20 | `part_of` | 13/12/1880 (hạt 20); 1880–81 (tổng) | the plate (read: names, village limits, canton name); NAC2 #15; guide A | **Yes**, plate and text are independent |

## Map link (draft)

- Plate placement: 3 control points, none near Quận 4, so Quận 4 is extrapolated. By eye the fit is within
  a village width. Needs 2 or 3 points near Khánh Hội to give a measured error.
- 1882 village of Khánh Hội, drawn by hand in the app on 2026-10-19 (footprint `60b21abf-afb9-4563-8301-8ed44ce4f53d`,
  "Shape 1", status submitted, 50 vertices) from the dash-dot line: 0.97 km², all inside Quận 4. It agrees
  with my first draft (IoU 0.88); the two differ mostly on the north-east edge.
- Overlap with the 2025 wards: Khánh Hội 60.9%, Xóm Chiếu 33.5%, Vĩnh Hội 5.6%. By the old numbered wards:
  P8 25%, P9 23%, P4 18%, P13 33%.
- **Land from river (phase 0b step 1), 2026-10-19.** `land_from_water.py`: water is the blurred b* channel
  below the paper's by 5 (the plain `colour.py` blue catches only the bank lines and the flood leaks across
  the river), land is the region reached from a seed in Khánh Hội, closed in the south by a straight line
  (modern; Kênh Tẻ is not on the plate). One crop (2400 × 1500 px at native size; 3.34 m/px by the plate's
  3-point fit). Against the three 2025 OSM wards joined, on the river sides only: edge-to-edge distance
  median 36 px (120 m), 90th percentile 58 px (195 m), maximum 103 px (345 m); a village is about 2 km
  across. Kill (more than a village width) not hit. Area IoU 0.74, lower because OSM wards run to mid-river
  in the north and extend south of my chord. The distance mixes mask error with the plate's placement error
  (step 4), so it is an upper bound on the mask's own error. Checked by eye only; no second reader.
- Vĩnh Hội and Tạm Hội are not traced: their shared limit near "Cầu 12" is unclear.
- The 2025 ward polygons come from OpenStreetMap (attic query, `[date:"2025-08-01"]`); old wards from
  `[date:"2025-06-01"]`. A gap in an OSM snapshot may mean the ward was not yet drawn.

## Traps

- A ward is not a village: link types say `overlaps` with an area share, never `same_as`.
- Kênh Tẻ was dug 1904–07, so Quận 4's southern edge is not on the plate.
- Tone marks (Hòa, Hoà, Hóa) break name matches; the 1880 decree prints "Xuân Hóa".

## Open

1. Check the trace; trace Vĩnh Hội and Tạm Hội.
2. Add control points near Khánh Hội and re-measure the overlap.
3. Step 3: find primary text of 301/UB, 147-HĐBT, 258-HĐBT. The vbpl.vn scan of 258 now returns 404.
4. The 1895/1907 and 1888 conflicts: read the footnoted decrees in the NAC2 captions.
5. The 1959 phường list for Quận Tư (NAC2 #38 lists wards by quận; not yet extracted).
