# Series 325 full georef (2026-11-26)

Series: Indochine 1:100,000, 1st éd. SGI 1900–47, 221 VMA rows. Prior probe: `325-graticule/README.md`
(7 of 20 fresh clean). Bet 3 in `docs/NOW.md`.

## What was done
Tue asked for the fast route, as with the other series. The bar, kill line and fresh-20 set drafted
earlier were **not** used, so this is a placement run, not a blind measurement.

1. `indochine325_graticule.py --method lines sample 221`: grade lines fitted per sheet (read-only).
2. Eye check: 12 random sheets of the 145 that passed (seed 20261126), overview overlays. 12 of 12 had the
   fitted grade lines on the printed tick labels. Not zoomed.
3. `indochine325_annotate.py --apply`: GCPs = the four corners the fitted affine gives, mask = the same quad,
   order 1, method `printed-corners`; pushed to Allmaps.

## Result
| | Sheets |
|---|---|
| Passed gates, stored and pushed | 159: 145 from the lines-first run (79 clean border, 66 border-suspect), plus 14 recovered from the holds with `--method old` (11 clean, 3 suspect), eye-checked at zoom |
| Holds | 60 failed the gates on both methods (list in `325-holds.md`). A refit that drops one failed line was tried on 16 sheets and recovered 0 (half sheets have only 2 interior lon lines); it was not kept |
| Data defect | Cap St. Jacques (E), image is another sheet (public, not placed); My - Tho (E) is archived with no IIIF source |

Drift check after the push: 144 maps checked, 0 differ; Vinh (E) failed once on a network error and was re-pushed.

Pak-Hin-Boun (W): the printed longitude label reads like 115°60′ while the fit (and the catalogue, Thakhek and Kam-Kout in the margins) say 113.6 grades. Kept as placed; likely a misread digit, not confirmed.

Cross-sheet check (read-only, stored `bbox` of the 159): no two sheets overlap by more than 40% of the smaller one, and no half-sheet pair overlaps beyond its shared edge. It would catch a wrong-image record like Cap St. Jacques (E).

## Caveats
- All 221 rows were already public, so storing a georef made it live at once (no draft step). Tue chose that: fix later in Allmaps.
- Gate results plus 12 overview checks are the only accuracy evidence; no error rate with an interval.
- 66 sheets are `border_suspect`: GCPs follow the grade lines, the mask may be off by a few hundred metres.
- Paris grades converted to degrees with no Indochine datum shift (about 100–200 m systematic, as for 561).
- Allmaps is push-only: re-running the writer or `allmaps_push.mjs` overwrites edits made in the Allmaps editor.

## Next
Place the holds by hand (Allmaps editor). Look at the 66 border-suspect sheets first in `/explore`.
