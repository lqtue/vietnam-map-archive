# 1882 training tiles — plots first

The model will learn to draw plot boundaries on the 1882 sheet from ten small squares of the map
(tiles). It can only learn from what you draw, so **in each tile every plot must have its outline**.
A plot you leave out teaches it that plots do not exist there. Buildings are a second pass on the same
tiles (see the end).

Ten tiles: eight to train on, two (t01, t06) to check it on. Two more areas, **R1** and **R2**, are kept
untouched for the final test. Do not draw in them or in the black boxes on `out/review/locator.png`.

## How to work

Sign in, then open the sheet in the Validate tab:
`/scan?mode=shapes&tab=validate&map=0e02b9d9-9d40-4cca-8e41-8c8373d54d3b`

| To do this | Do this |
|---|---|
| Keep an outline that is right | **Approve** |
| Fix an outline | click it, drag the green dots, then **Approve** |
| Remove one that is wrong | **Reject** |
| Add a missing plot | open the Draw tab (`tab=draw` in the link), press **Polygon**, click the corners, double-click to finish |
| Split a plot that holds two or more | Reject it, draw each part in the Draw tab |

Know this before you start:
- **After every Approve or Reject the screen jumps** to some other row, anywhere on the sheet. The list
  is in import order, so there is no way round it. Draw the missing plots first (no jump), then go
  through the Validate rows, and use the picture of the tile to find your way back.
- **Approve last.** An approved outline cannot be opened again. Your own drawings stay editable
  (Edit button, drag, Delete key).
- Four big outlines drawn earlier by volunteers (whole military lands) cannot be edited. The export
  ignores them, so you can ignore them too.
- The app has no coordinates. Find a tile with `out/review/locator.png` and the street names below.
  A tile is about 8.5% of the sheet's width.

## Your drawing rules (as you gave them)

- The line follows the printed block or lot line.
- Pavement counts as land. The road side of a plot is the kerb line.
- Draw only lines that are plot edges. Where a plot edge runs along a street edge, that line is drawn
  and nothing else; do not add street lines.

A garden or park (Jardin de la Ville, Jardin Botanique) is **one question for you**: the colour pass
cut it into 15 to 30 lawn and tree shapes. I think the park should be one plot and the shapes should
be rejected. Tell me if you want it otherwise.

## The faults you will meet again and again

I looked at today's outlines on the tiles. In order of how often:
1. **Missing inner lines.** A whole block is one outline, but the map prints thinner lines between
   its lots (Imprimerie Nationale block in t02, the Évêché block in t01, the Sainte-Enfance block
   in t09, the shophouse rows in t06 and t07). Draw each lot.
2. **Doubled outlines.** Two outlines on the same plot, a few pixels apart. Reject one.
3. **Lines that are not on the map.** Straight chords across an empty plot (t10, t01), and strips along
   the red dashes of the city limit (t03, t07). Reject them.
4. **Water and moat.** Outlines round creeks and the hatched moat (t04, t06, t07). Reject.
5. **Tangles.** Several overlapping outlines in the shophouse clusters (t06 lower left, t07 left):
   reject them and draw the lots again.
6. **Bumps at lettering.** The line wobbles or pinches where a street name is printed (t03 by Rue de
   Tay, t09 by Shang-Hai). Drag the dots back to the printed line.
7. **Line on the wrong side of the kerb.** A few outlines sit a little inside or outside the printed
   line. Check the thick ones.

## Tile by tile

"Rows" is how many outlines are waiting for you in the tile (a few sit in two tiles). My rough split by
eye and by rule: fine as they are / fix / reject / merged (reject and redraw), and how many plots are
missing. Counts are estimates, good to about a quarter.

| Tile | Split | Find it by | Rows | Fine | Fix | Reject | Merged | Missing |
|---|---|---|---|---|---|---|---|---|
| t01 | check | ÉVÊCHÉ, Rue Catinat, Ancien Camp des Lettres | 22 | 9 | 5 | 8 | 0 | 8 |
| t02 | train | Imprimerie Nationale, Rue de Kerlan, Hôpital Maritime | 8 | 6 | 2 | 0 | 0 | 6 |
| t03 | train | Magasins de la Marine, Rue Tay Ninh | 20 | 8 | 4 | 7 | 1 | 5 |
| t04 | train | Camp des Indigènes, Rue Laubat | 10 | 3 | 2 | 5 | 0 | 6 |
| t05 | train | Palais du Gouverneur, in the Jardin | 28 | 5 | 6 | 14 | 3 | 2 |
| t06 | check | Rue Lefebvre, Rue Dayot, Rue Némésis | 60 | 36 | 8 | 8 | 8 | 15 |
| t07 | train | Marché de Cau Ong Lanh, Poste de Police | 25 | 8 | 6 | 5 | 6 | 20 |
| t08 | train | Jardin, Rue de la Grandière | 32 | 8 | 3 | 20 | 1 | 6 |
| t09 | train | Sainte-Enfance, Rue Shang-Hai | 14 | 8 | 3 | 2 | 1 | 6 |
| t10 | train | Cité Ouvrière de l'Arsenal, Rue d'Espagne | 13 | 5 | 3 | 2 | 3 | 5 |
| **All** | | | **232** (221 different outlines) | 96 | 42 | 71 | 23 | 79 |

So about 220 Approve or Reject clicks, about 40 outlines to drag, and about 100 plots to draw
(79 missing plus about 23 from merged ones). The park tiles t05 and t08 shrink a lot if you decide the
park is one plot. Hand drawing by volunteers is not an option: the 24 plots they drew are whole
institutional blocks and none of them covers a tile.

What today's outlines look like as the model's target: `out/review/<tile>_plot_overlay.png` (the
mask in magenta over the map). The lines follow block outlines well; they miss the inner lots and
add the faults above.

## When you are done

```bash
python work/MapSAM2/tiles_1882/export_tiles.py --require-reviewed
```
It stops and says so while any outline in the tiles is still waiting. When it passes, the tiles are
written to `out/plot-boundary/` in the layout the trainer reads. `--target building` writes the
building masks instead (`--target both` for both).

## For whoever runs the trainer

- Target `plot-boundary`: the outline of every plot that is not rejected, 5 px wide. 5 px because the
  trainer shrinks masks to 256 px by sampling about every fourth pixel; a thinner line breaks.
  4 to 13% of pixels are line, close to the railway set (5.6%). Rows over 500,000 px² (whole
  military lands) are skipped. The line is drawn only from plot edges, cut at the tile edge.
- Calibrate windows may be touched, held-out windows never. The calibrate windows are the water and
  road layers' tuning boxes; a plot or building model scores nothing in them. `export_tiles.py` refuses
  any tile that touches a held-out window, the shape-precision window, the legend, title or scale.
  Tiles t06 to t10 touch calibrate windows only (`calibrate_overlap` in `tiles.json`).
- Layout: `out/<target>/<raw|inpainted>/{train,val}/<tile>.png` and `.../annotation/{train,val}/<tile>.png`.
  Checked against upstream `func_2d/dataset.py` at `30110f0`. The inpainted images take out street
  names only (OCR run `post0910`), with faint smears.
- Python: `work/ocr/.venv` has no `cv2`. A scratch venv (`uv venv --python 3.12`; opencv-python-headless,
  numpy, pillow, shapely, requests, scipy, python-dotenv) and a link to the repo `.env` did the work;
  both live outside git.
- `hand_labels.py` reproduces the hand-label counts (47 volunteer rows, none edited from the colour
  pass, no area exhaustive).

## Second pass: buildings

Same tiles, `<tile>_overlay.png`. Add the missing ones in the Draw tab, Reject residue, Approve the
rest. About 65 are missing in t01 to t05 and about 80 in t06 to t10; the colour pass finds the pink
houses and almost none of the grey and blue sheds. Rule: any roofed building drawn solid or hatched.
Tile list and building counts: `tiles.json`.
