# Series 325 graticule probe: why 11 of 20 fresh sheets failed (2026-10-19)

Source: the overlay PNG of each failed sheet, viewed by eye. "Measured" marks a cause checked with numbers; the rest are what the picture shows.
Run: both systems (Paris grades, Greenwich 5′) tried per sheet; Greenwich passed on none. 9 ok, 8 clean.

| # | Category | Sheets | Evidence |
|---|---|---|---|
| A | Data defect: the image is a different sheet from the record | Cap St. Jacques (E) (`6b244862`) | Record: sheet 230 E, box 106.87–107.21 E, 10.3–10.8 N. Image title: MUONG HUN XIENG HUNG Ouest, "N° 22 W". Not a method failure. |
| B | Grade lines present at the right places but too faint for `LINE_THR` 14 | Tuy-Hoa, Poulo-Canton (W) | **Measured.** Mean-profile depth at the expected rows is 5–15 against a threshold of 14. At threshold 5 the candidates appear at the expected rows. Horizontal lines are the worst. |
| C | Lines thin and broken under dense relief and hachures | Viêt-Trì (E), Thât-Khê (E), Cao-Bang (E) | Seen by eye: lines visible only in blank patches. **Not measured**; may be the same cause as B. |
| D | Blank sea inside the border, so the "texture step" finds no border | Hon-Gio | Grade lines were traced correctly (match the margin labels); only border L failed. |
| E | Map extent not the rectangle inside the frame | Vang-Vieng (W), Savannakhet | Vang-Vieng: notched, stepped frame. Savannakhet: town and river spill outside the left frame. Savannakhet's grade lines traced correctly; border L failed. |
| F | A frame rule is traced as the grade line, or the border traces land on the image edge | Cap Pak-Loung | `lon117.8` traced on the right frame rule, ~30 px (900 px scale) from where the label puts the line; blue border lines at the image edge. |
| G | Lines found and look right, but the affine gate rejects them | Kompong-Cham (E) | Not diagnosed: left border irregular (river outside frame), border traces at the image edge; or paper distortion. |

Also seen:
- Tuy-Hoa prints both graticules: the 0.2 g lines and 5′ degree lines (about 190 px apart at 900 px scale), overlapping. `pick_border` also took an interior line as the right border there.
- Greenwich "not found" on every failed sheet probably comes from the same faintness as B, so that run did not test the Greenwich idea.

## Tried after the table (same 20 sheets, which are no longer fresh)
- Greenwich 5′ system beside Paris: kept (probe tries both). Passed on 0 sheets; uninformative while faint lines go undetected.
- Faint-line mode (`faint=True`: per-sheet threshold, floor 5): **only as a fallback** when both normal passes fail. Applied to every sheet it dropped 9 ok to 2. As fallback: +1 ok (Viêt-Trì, border suspect, S gap −514 m), 0 clean.
- Printed-frame-rule border fallback: **removed**. 0 of the 4 target sheets (Hon-Gio, Tuy-Hoa, Vang-Vieng, Savannakhet) turned clean. Kill result met.
  Why: on Tuy-Hoa, Savannakhet and Vang-Vieng the nearest strong frame rule is 60–200 px (2600 px work width) from the border window the catalogue box predicts (±~23 px).
  The search window is centred on the catalogue box, so a wrong catalogue box defeats any border snapping.
  Hon-Gio got past the border but then fails the line fit on `lon115.8`, a line close to the frame.
- Score: 10 ok, 8 clean of 20. Bar was 14 clean.
- A border finder that does not start from the catalogue box would be a redesign, not a tweak. Not started.

## Eye check of the 8 clean sheets (overview overlays; Ya Li and Tchépone also zoomed)
- Ya Li (`03d09a78`): **west border is wrong.** The trace sits on the 116.8 g grade line (x≈91 at 900 px), ~4 km east of the printed map border (inner corner mark at x≈36). The grade lines and the affine look right; only the corners are off.
- Tchépone: the east border sits on the inner border rule (zoomed). Right.
- Tây-Ninh, Phu-Tinh-Gia, Gia Ray, Ha-Tinh, Yên-Bay, Ban-Tur: borders and grade lines look right at overview scale. Not zoomed.
- So 7 of 8 clean look right. Effective score: 7 of 20, not 8.
- **The border check is circular.** The border search window is centred on the catalogue box (±~440 m), and `border_suspect` compares the border to that same box. A wrong catalogue box gives a "clean" wrong border, as on Ya Li. The independent evidence is the grade-line affine, not the corners.

## Lines-first solve (`--method lines`), dev set of 31 sheets, 2026-10-19
Placement (grade lines, comb finder, catalogue only names the lines): **22 ok vs 18 ok with the old method.** Gains: My Tho (W), Hon-Gio, Thât-Khê, Phiafay, Kompong-Cham, Savannakhet. Losses: Ke-Bao, Mahaxay. Ya Li's west border moved to the real neatline (gap −4126 m): the circular check now fails where it should.
Still failing: Vang-Vieng, Tuy-Hoa, Cap Pak-Loung, Cap St. Jacques (data defect), Cao-Bang, Poulo-Canton, Ba-Xa.

**Border by "innermost strong frame rule" is wrong.** Of the 7 sheets checked right by eye, 5 now have a wrong border (zoomed crops):
- Yên-Bay (E), Ha-Tinh (E): the border lands on the OUTER rule, 1.2 km beyond the map. The real neat line is a thin weak rule just inside the ticked band, below the strength floor.
- Tây-Ninh (W): the border lands on a grade line 1.6 km inside the map; the thin neat line is again missed.
- Gia Ray, Tchépone: flagged the same way (not zoomed).
Only Phu-Tinh-Gia and Ban-Tur kept unflagged borders.
The old texture step finds the neat line correctly because it looks for where map ink starts, but its window is centred on the catalogue box.

Not run: the fresh 20. The method did not pass the dev must-pass, so it would only spend the fresh set.
Next, if continued: keep the comb finder for placement; find the neat line as the thin rule or texture step within ~20 px (900 scale) inside the band's innermost strong rule, instead of a catalogue window. Blank-sea sheets (Hon-Gio, Tuy-Hoa) still need a different rule.
