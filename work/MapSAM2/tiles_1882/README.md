# 1882 training tiles — owner checklist

Step 1 of the buildings-only MapSAM2 test (train on 1882, score on 1898). Upstream 2D training
needs every building in a tile labelled, so each tile below must be complete when you finish.
Boxes and counts: `tiles.json`. Images and masks are data and stay out of git (`out/`).

**Under the rule (no tile touches any window in `windows.json`, heldout or calibrate) only five
tiles exist: t01 and t03 as val, t02, t04, t05 as train, and t05 is nearly empty.** Dense building
area is almost all inside those windows. t06 to t10 overlap *calibrate* windows only (water or road
layers, never buildings). They are a proposal waiting for a yes: `export_tiles.py` leaves them out
unless you pass `--include-relaxed`, and then writes to `out_with_relaxed/`. Do not edit them until
you decide.

## How to edit (read from the code, not clicked through)

Sign in as admin or mod. One sheet, two tabs:

`/scan?mode=shapes&tab=validate&map=0e02b9d9-9d40-4cca-8e41-8c8373d54d3b`
`/scan?mode=shapes&tab=draw&map=0e02b9d9-9d40-4cca-8e41-8c8373d54d3b`

| Job | Where | How |
|---|---|---|
| Fix an outline | Validate | click the polygon, drag its green vertices, then **Approve** (an edit is held until the verdict and is lost if you switch sheet) |
| Delete residue (a plot, a dash, a stripe) | Validate | **Reject**. The row stays in the database as `rejected`; the export skips it |
| Add a missed building | Draw | bottom bar **Polygon**, click the corners, double-click to finish. It saves at once as a `building`, status `submitted`. Limit 300 per hour |
| Split a merged row | both | there is no split tool: Reject the merged row, then redraw the parts in Draw |

Things that bite:
- **After every Approve or Reject the view jumps.** The Validate list is in import order (all 1,311
  rows were created within one second, so order is by random id), and a verdict selects the next row
  and zooms to it. A tile's rows sit at scattered positions (t06: 29 rows spread over positions
  764 to 1,274), so you lose your place each time. There is no way round it in the app today. Do the
  additions in Draw first (no jump), then walk the Validate rows, using the overlay image to find
  your way back. That is about 32 verdicts across the five tiles (t05 has none).
- **Approve last.** Once approved, an imported row leaves the Validate list, and Draw only edits
  rows you drew yourself, so you cannot reopen it. Rows you add in Draw stay editable (Edit tool,
  drag, Delete key).
- Volunteer rows already approved (t05 Palais, one in t09) cannot be edited unless you drew them.
  Leave them; the export counts them as they are.
- The canvas has no position in the URL and no coordinate readout. To reach a tile, open
  `out/review/locator.png` (magenta = tile, black = test area, do not touch; the held-out windows
  are blacked out there and not marked in the app, so do not trace inside those boxes), pan to
  it, and match the lettering below. A tile is 1024 px, about 8.5% of the sheet width.
- Rule I used for "building": any roofed structure drawn as a solid or hatched footprint (sheds,
  houses, compounds, the Palais). Plot lines, courts and gardens are not. Tell me if you want a
  different rule before you start.
- Training sees the mask at 256 px (upstream `out_size`), so a building under about 8 source px
  across may vanish. Trace it anyway; it costs nothing.

## The tiles

Colour-pass rows today are all `needs_review`, none rejected. "Missed" is my count by eye from
`out/review/<id>_overlay.png`; the pass finds the pink houses and almost none of the blue and grey
military sheds.

| Tile | Box x,y | Split | Rows | Lettering to find it | Fix |
|---|---|---|---|---|---|
| t01 | 6300,2610 | val | 11 | ÉVÊCHÉ, Ancien Camp des Lettres | reject the big outline round the lower plot; add Évêché's 3 buildings and about 8 brown sheds in the lower plot |
| t02 | 6420,3776 | train | 1 | Imprimerie Nationale, Rue de Kerlan, Hôpital Maritime | nearly empty: add about 30 (brown houses, grey print works, blue hospital blocks) |
| t03 | 8728,4720 | val | 5 | Magasins de la Marine, Rue Tay Ninh | reject the red dashes on the city limit (top right); add about 12 sheds |
| t04 | 7512,3312 | train | 15 | Camp des Indigènes, Rue Laubat | tidy the loose pink houses; add about 12 grey sheds |
| t05 | 5000,2000 | train | 1 | Palais du Gouverneur | nothing to do (volunteer row; hard negative: tree hatching) |

About 65 buildings to add and 30 outlines to fix or reject in these five. Provisional, not exported
by default (rows today, then what I saw):

| Tile | Box x,y | Rows | Lettering | Fix |
|---|---|---|---|---|
| t06 | 2520,3760 | 29 | Rue Lefebvre, Rue Dayot | reject the thin stripe at the lower left; split merged blobs; add about 12 |
| t07 | 1176,2864 | 22 | Marché de Cau Ong Lanh, Poste de Police | reject the irregular blobs in the pale lot; add about 15 small houses |
| t08 | 3864,1520 | 22 | Jardin, Rue de la Grandière | reject the specks in the garden hatch; add about 8 |
| t09 | 7448,5552 | 15 | Sainte-Enfance, Rue Shang-Hai | unmerge the main building and chapel; add about 8 small sheds |
| t10 | 6424,5168 | 7 | Cité Ouvrière de l'Arsenal, Rue d'Espagne | reject the pale polygons in the empty lot; add about 35 grey sheds |

Reserved for the 1882 test window, untouched: **R1** `4760,4790,600,600` (dense shophouse blocks,
Rue Pellerin) and **R2** `8500,2590,600,600` (pink blocks round the Poste de Police). Both are clear of
every window and of every volunteer trace. Do not trace them. I looked at R2 at 1/3 scale with the
colour-pass outlines drawn, and R1 only on 1/6 overviews, also with outlines; neither at native size.

## Re-export after editing

```bash
python work/MapSAM2/tiles_1882/export_tiles.py --require-reviewed   # exit 1 while any needs_review building touches a tile
python work/MapSAM2/tiles_1882/export_tiles.py --include-relaxed    # only after you approve t06 to t10
python work/MapSAM2/tiles_1882/export_tiles.py --self-check         # synthetic case, no network
```

It reads the current geometry (read-only GETs), so what you saved in the app is what it exports.
Mask = union of `building` rows that are not `rejected`, clipped to the tile, 255 on 0.
A tile is done when its `needs_review` count in `out/stats.json` is 0.

Output, upstream's layout, once per variant (`out/raw` and `out/inpainted` share the masks):

```
out/<variant>/{train,val}/<id>.png   out/<variant>/annotation/{train,val}/<id>.png
out/ocr/<id>.png   out/review/<id>_overlay.png   out/review/locator.png   out/stats.json
```

Checked against upstream `func_2d/dataset.py` at `30110f0`: it lists `.png`, pairs the mask by the
same filename under `annotation/<mode>/`, opens it as grey, and binarises at 0.5 after scaling, so
0/255 PNGs are right. Each crop is checked for white holes (a missing level-0 tile) before it is written.

Python: `work/ocr/.venv` has no `cv2`. I used a scratch venv (`uv venv --python 3.12`;
`opencv-python-headless`, numpy, pillow, shapely, requests, scipy, python-dotenv) and linked the
repo `.env` into the worktree. Both live outside git; the output folders regenerate with one command.

## What the OCR mask is

Run `post0910` (EVAL-BASELINE names it the seed run for 1882; 304 rows, validated, pending and
rejected all used, since the text is on the sheet whatever the transcription). It holds street and
institution names only, no lot numbers, so the inpainted variant removes names, not every digit.
`global_w/h` is the axis-aligned box of rotated text, so each row is drawn as an oriented rectangle
(`label_w` x `label_h` where kept, else solved from the box; `rotation_deg` is counter-clockwise).
Rows longer than 1500 px or taller than 250 px are group boxes spanning a street and are skipped.
`cv2.inpaint` (Telea) leaves faint smears along street bands: the inpainted set is a comparison
variant, not a clean map.
