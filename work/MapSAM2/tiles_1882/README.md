# 1882 training tiles — blocks first

The model will learn to draw street blocks on the 1882 sheet from ten small squares of the map
(tiles). It learns only from what you draw. The lots inside a block wait for a later round.

**A tile is done when** every street block in it has one outline, no line runs inside a block, no line
crosses a street, and no line sits where there is no block.

Ten tiles: eight to train on, two (t01, t06) to check it on. Two more areas, **R1** and **R2**, stay
untouched for the final test. Do not draw in them, or in the black boxes on `out/review/locator.png`.

## How to work

Sign in, then open the sheet in the Validate tab:
`/scan?mode=shapes&tab=validate&map=0e02b9d9-9d40-4cca-8e41-8c8373d54d3b`

The colour pass drew lots, not blocks. The export joins lots that touch (or sit less than 10 px
apart) into one block, so **a good lot is fine as it is: just Approve it**. Do not Reject a good lot
because it is only a lot; that would cut a bite out of its block.

| To do this | Do this |
|---|---|
| Keep a lot that sits in a block correctly | **Approve** |
| Fix a wrong edge | click it, drag the green dots, then **Approve** |
| Remove one that is not a block (junk) | **Reject** |
| Add a block that has no outline | Draw tab (`tab=draw` in the link), **Polygon**, click the corners, double-click to finish |

About 6 in 10 rows are Approve and nothing more (141 of 232; 141 of 204 without the park tile t05).

## Your drawing rules

- The line follows the road edge, the kerb line. Pavement counts as land.
- One line round each block. Nothing inside it, nothing across a street.
- **A park is one shape.** Draw one outline round the whole garden (Jardin de la Ville, Jardin
  Botanique), and Reject the lawn and tree shapes the colour pass made inside it.

## Faults to look for, most common first

1. **Junk rows.** Outlines round water, creeks and the moat (t03, t04, t07), strips along the red city
   limit dashes (t03, t07), thin slivers along a street name (t03, t09 at Shang-Hai), tiny specks
   (t07, t08, t09), and the park lawns (t05, t08). Reject them.
2. **Notches and spikes.** The edge of a block jumps in or out because one lot at the corner is missing
   or wrong (t06 near the creek and lower left, t03 and t04 beside the moat). Drag the dots to the kerb,
   or Reject the one bad lot and draw it again.
3. **Edge on the wrong side of the kerb.** A few outlines run in the street, or a little inside the
   block (t10 Rue d'Espagne, t09). Drag them to the kerb line.
4. **A block with no outline.** Draw it in the Draw tab. Check the tile's corners and edges first.

## Tile by tile

"Rows" are the outlines waiting for you in the tile (a few sit in two tiles). Counts are my estimates
by eye, good to about a quarter. Fix means one or two rows in a block, not the whole block.

| Tile | Split | Find it by | Rows | Approve as is | Fix | Reject | Blocks to draw |
|---|---|---|---|---|---|---|---|
| t01 | check | ÉVÊCHÉ, Rue Catinat, Ancien Camp des Lettres | 22 | 21 | 1 | 0 | 1 |
| t02 | train | Imprimerie Nationale, Rue de Kerlan, Hôpital Maritime | 8 | 7 | 1 | 0 | 1 |
| t03 | train | Magasins de la Marine, Rue Tay Ninh | 20 | 12 | 2 | 6 | 1 |
| t04 | train | Camp des Indigènes, Rue Laubat | 10 | 6 | 2 | 2 | 1 |
| t05 | train | Palais du Gouverneur, in the Jardin | 28 | 0 | 0 | 28 | 1 (the park) |
| t06 | check | Rue Lefebvre, Rue Dayot, Rue Némésis | 60 | 52 | 7 | 1 | 2 |
| t07 | train | Marché de Cau Ong Lanh, Poste de Police | 25 | 15 | 2 | 8 | 2 |
| t08 | train | Jardin, Rue de la Grandière | 32 | 13 | 3 | 16 | 2 (one is the park) |
| t09 | train | Sainte-Enfance, Rue Shang-Hai | 14 | 4 | 2 | 8 | 1 |
| t10 | train | Cité Ouvrière de l'Arsenal, Rue d'Espagne | 13 | 11 | 2 | 0 | 2 |
| **All** | | | **232** | **141** | **22** | **69** | **14** |

232 Approve or Reject clicks (221 different outlines), about 20 outlines to drag, 14 blocks to draw.
Today's outlines make 111 blocks across the ten tiles (`out/review/<tile>_block_overlay.png` shows
them in magenta with a number on each block).

## Working in the app as it is

- **After every Approve or Reject the screen jumps** to some other row, anywhere on the sheet (the
  list is in import order; this will not be fixed for now). Plan for it:
  - Work **one tile at a time** with `out/review/locator.png` and the tile's picture open beside the
    app. After a jump, zoom out, find the tile by its street names, zoom in. A tile is about 8.5% of
    the sheet's width.
  - Do the **Draw tab first** (no jumps), then **Reject** the junk (it shortens the list), then
    **Fix**, and **Approve** last.
  - For the many "Approve as is" rows, tick several in the list (Ctrl-click, or Shift-click a range) and
    press **Approve selected**: one click, one jump.
- **Approve last.** An approved outline cannot be opened again. Your own drawings stay editable.
- Four big outlines drawn earlier by volunteers (whole military lands and the park) cannot be edited.
  The export ignores them; ignore them too.
- The app has no coordinates.

## When you are done

```bash
python work/MapSAM2/tiles_1882/export_tiles.py --require-reviewed
```
It stops and says so while any outline in the tiles is still waiting. When it passes, the masks are
in `out/block-boundary/`, in the layout the trainer reads. Lots stay in the database as they are.

## For whoever runs the trainer

- Target `block-boundary` (default): the lots that are not rejected are dissolved into blocks and the
  outer ring of each block is drawn 5 px wide. Nothing is drawn inside a block. 3.9 to 8.7% of pixels
  are line. `--target plot-boundary` draws every lot, `--target building` the buildings, `--target all`
  all three (`out/<target>/...`).
- **Why 10 px.** Lots inside a block are 2 to 9 px apart (116 of the 754 close pairs on these tiles;
  the corner gaps I looked at are 8 to 9). The nearest lots across a street are 12 px apart at the
  narrowest lane (Rue de Tay, t03), and lettered streets are wider. 10 px sits between. Over a
  range from 4 to 20 px the number of blocks falls from 128 to 100 and no street-name lettering is newly
  swallowed by a block (merging across lettered streets starts near 30 px), so the choice is not sharp;
  10 is the largest value I could show merges nothing across a street by eye on t01, t06 and t10.
  The closing uses mitred corners, so blocks keep square corners.
- 5 px because the trainer shrinks masks to 256 px by sampling about every fourth pixel; a thinner
  line breaks. Rows over 500,000 px² that volunteers drew (whole domains) are skipped.
- Calibrate windows may be touched, held-out windows never (`calibrate_overlap` in `tiles.json`;
  t06 to t10 touch calibrate windows only). The calibrate windows are the water and road layers'
  tuning boxes; a plot, block or building model scores nothing in them. The export refuses any tile
  that touches a held-out window, the shape-precision window, the legend, title or scale.
- Layout: `out/<target>/<raw|inpainted>/{train,val}/<tile>.png` and `.../annotation/{train,val}/<tile>.png`;
  checked against upstream `func_2d/dataset.py` at `30110f0`. The inpainted images take out street names
  only (OCR run `post0910`), with faint smears.
- Python: `work/ocr/.venv` has no `cv2`. A scratch venv (`uv venv --python 3.12`; opencv-python-headless,
  numpy, pillow, shapely, requests, scipy, python-dotenv) and a link to the repo `.env` did the work;
  both live outside git.
- `hand_labels.py` reproduces the hand-label counts (47 volunteer rows, none edited from the colour
  pass, no area exhaustive).

## Later: lots, then buildings

Lots are the plot-boundary target (`<tile>_plot_overlay.png`): about 100 inner lots are missing in the
ten tiles and the doubled and merged rows need fixing. Buildings: `<tile>_overlay.png`; about 145 are
missing, and the colour pass finds the pink houses and almost none of the grey and blue sheds.
