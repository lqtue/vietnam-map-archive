# Series 325 placed from its grade lines: result (2026-10-19)

Script: `scripts/indochine100k/indochine325_graticule.py` (read-only; no database writes). Bet 3 in `docs/NOW.md`.

## Question
Can the 221 VMA sheets of series 325 (Indochine 1:100,000, 1st édition, 1900–47) be placed from the grade lines each sheet prints, instead of the catalogue box?
Bar, set before the fresh run: 14 of 20 fresh sheets clean. Kill: fewer than 6.

## Answer
**No, not yet: 7 of 20 fresh sheets came out clean.** Above the kill line, well short of the bar.

| Run | ok | clean | Note |
|---|---|---|---|
| Tuning set, 10 sheets | 7 | | tuned on |
| Fresh set, 20 sheets, first run | 9 | 8 | the held-out number |
| Same 20, by eye | | **7** | Ya Li's west border is ~4 km off the printed neat line |
| Same 20 after Greenwich 5′, faint-line fallback, frame-rule border | 10 | 8 (7 by eye) | tuned on these 20; did not move it |

"ok" = the code's gates pass (affine residual ≤ 30 m, lon/lat scale ratio within 4 %, line fit ≤ 1.5 px). "Clean" = ok and the border is within [−350, +150] m of the catalogue box. Neither is "verified correct": only 8 overlays were looked at, 2 of them zoomed.

## So what
- Bet 3 stays **Later**. The method places about a third of the sheets it is given, and its border check cannot be trusted (below).
- The grade lines are good evidence; the border is the weak part.
- A day of work on a border finder that does not start from the catalogue box is the one open path. See *What would move it*.

## Why 11 of 20 failed (overlays viewed; only B was measured)
| Cause | Sheets |
|---|---|
| Image is a different sheet from its record | Cap St. Jacques (E): the image is "Muong Hun Xieng Hung Ouest, N° 22 W". **A data defect in the archive.** |
| Grade lines present but fainter than the detector threshold (depth 5–13 against 14) | Tuy-Hoa, Poulo-Canton (W) |
| Thin lines broken under dense hachures | Viêt-Trì (E), Thât-Khê (E), Cao-Bang (E) |
| Blank sea, so the border's texture step finds nothing | Hon-Gio |
| Map is not the rectangle inside the frame | Vang-Vieng (W), Savannakhet |
| A frame rule traced as a grade line | Cap Pak-Loung |
| Lines look right, affine gate rejects | Kompong-Cham (E), not diagnosed |

## What survives
1. **The catalogue-gap check is circular.** The border search window is centred on the catalogue box (±~440 m), and `border_suspect` compares the border to the same box. Ya Li passed as clean with a wrong border. The grade-line fit is the independent evidence; the corners are not.
2. **Lines first beats border first for placement.** Finding the grade lines as an equally spaced set (catalogue only names them) solves 22 of 31 dev sheets against 18 for the old method (`--method lines`).
3. **The border by "innermost strong frame rule" is wrong.** On 5 of the 7 sheets checked right by eye it lands on the outer rule or a grade line: the real neat line is thin and weak. The old texture step finds it, but only inside a catalogue-centred window.
4. **Tuy-Hoa prints both graticules**: grade lines and 5′ degree lines, overlapping. Greenwich 5′ passed on 0 sheets, but the faint-line problem blocked the test, so it is not tested.
5. **Reading the margin labels:** Gemini (thinking off) 49 right, 5 wrong, 30 empty of 84 crops, $0.0025 a call; Tesseract 7 right, 40 wrong. Not wired into the gate.
6. **Tried and worse:** darkness contrast for the border; candidate-line scoring by texture; a 30 px inward window; a per-sheet lower line threshold for every sheet (9 ok fell to 2; kept only as a fallback); snapping the border to the nearest printed rule inside the catalogue window (0 of 4 target sheets).

## What would move it
Keep the comb finder for placement. Find the neat line without a catalogue window: the thin rule, or the texture step, within ~20 px (900 px scale) inside the frame band's innermost strong rule. Re-run the dev set (must keep the 7 eye-checked sheets right), then one fresh 20 with no tuning after. Blank-sea sheets need their own rule.

## Files here
`<map-id>.json` and `.png`: result and overlay per sheet. `summary.json`: last run. `failure-categories.md`: the working notes. `label-compare.json`, `labels/`: margin-label reads.
Run: `work/ocr/.venv/bin/python scripts/indochine100k/indochine325_graticule.py probe [--method lines] <map-id> ...`
