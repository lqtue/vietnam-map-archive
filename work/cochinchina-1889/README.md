# Cochinchina arrondissement plans, 1881-89: georeferencing test

Bet 3 (a corpus to link against). Twelve plans from the Service du cadastre, ingested as drafts. One
test, one plate, one number. **Result: stop. Eleven of the twelve plates print no graticule.**

## What each plate prints

I looked at the edges of every plate in full-resolution crops scaled down 3 to 4 times. All four sides for
p-002 to p-005 and p-013; for the rest the top, bottom and one side, and for Tra Vinh and Sa Dec only the
thumbnail and the top edge.
"Compass" means the words NORD / SUD / EST / OUEST in the middle of each side. They are not ticks.

| Plate | Place (year read off plate) | Graticule or ticks | Notes |
|---|---|---|---|
| p-002 | Saigon (1885) | none, compass only | North arrow drawn inside the sheet, tilted |
| p-003 | Baria (1881) | none, compass only | |
| p-004 | Bien-Hoa (1881) | none, compass only | |
| p-005 | Cholon (1882) | none, compass only | "Nota: reduction of the field sheets at 1/20 000"; scale bar 0-20 km only |
| p-006 | Gocong (1881) | none, compass only | prints 1:100 000 |
| p-007 | Mytho (1885) | none, compass only | |
| p-008 | Bentre (1882) | none, compass only | |
| p-009 | Tra Vinh (1888) | none seen (thumbnail and top edge) | north arrow inside the sheet |
| p-010 | Vinh Long (1885) | none, compass only | |
| p-011 | Sa Dec (1885) | none seen (thumbnail and top edge) | north arrow inside the sheet |
| p-012 | Longxuyen (1886) | none, compass only | |
| **p-013** | **Tan An (printed 1887)** | **yes: full lat/long grid every 10'** | the only one; two-page spread |

The task brief gave Tan An as 1888; the plate reads 1887.

Kill result, as set: "most plates carry no usable graticule or tick labels". It fired (1 of 12).
Cholon, the planned pilot, cannot be done from a graticule: it has none. I did not switch it to a
landmark-only fit to get around that.

## What the Tan An graticule says

* Latitude labels 11°00' ... 10°30', true latitude, north-up.
* Longitude labels 1°10', 1°00', 0°50', 0°40', 0°30', 0°20', 0°10' **fall from left to right**. They count
  west of a meridian just east of the sheet. Paris (2°20'14" E of Greenwich) and Greenwich are both
  impossible readings: Tan An is at about 106.41 E, 104.07 E of Paris.
* Solved against modern river banks, the reference meridian is **about 106.693 E Greenwich**
  (106°41.6'), the Saigon meridian. Its uncertainty is about +-100 m (+-0.001 degrees), from how flat the
  calibration score is. Latitude carries a small offset of about 100 m (printed is north of true).
* The grid is straight lines per page but the spread is two pages: the lines tilt one way on the left page
  and the other on the right (about 0.4 degrees each), and the 0°40' line sits in the gutter. 24 intersections
  (6 meridians x 4 parallels) are the control points.
* Printed spacing is 8.52 m/px along a parallel and 8.31 m/px along a meridian, mean 8.4 m/px
  (0.119 px/m; about 1:100 000 at 300 ppi).

## Result table

| Plate | Projection / meridian | Fit pts | Check | Check residual (m) | px/m | Verdict |
|---|---|---|---|---|---|---|
| p-013 Tan An | plain lat/long grid, thin-plate spline; meridian 106.6927 E (Saigon), west-counting | 24 graticule intersections | 6 river windows, right page only | cross-river median **69**, max **408**; unsplit shift median **194**, max **416** | 0.119 | **Not shown to pass.** Passes the 150 m line only on the cross-river measure, from six windows; fails it unsplit. |
| p-002 to p-012 | none possible from a graticule | 0 | 0 | not measured | n/a | blocked: no graticule |

What each number is:

* **Fit points** (`points/p-013-tan-an-fit.csv`, role `fit`): the 24 intersections. A residual on these is
  circular and is not reported as accuracy. For information only, leaving one intersection out and
  predicting it from the other 23 gives a median of 48 m and a worst of 244 m; that measures how
  consistent the printed grid is with itself, nothing else.
* **Calibration.** One free shift (east and north) was set from one river window (12600-14400 x
  6400-7800 px, around Tan An town), and applied as a constant in `tan_an_graticule.py`. That window is not
  among the checks.
* **Check windows** (`points/p-013-tan-an-check.csv`, role `check`): the sheet is cut into 1500 px
  squares; in each, OpenStreetMap riverbank lines (projected through the grid) are slid over the plate's blue
  river mask, and the shift that fits best is that window's error. A river only fixes the shift across
  itself, so each shift is split in two and the cross-river part is the one that means something. Rows are
  windows, not point features, so `px/py/lon/lat` is the window centre.

## Why the 69 m should not be believed yet

* Six windows, all on the right page (the Vàm Cỏ Đông and Tây near Tan An, and the east boundary
  river). The left page, the swamp (Mộc Hóa), has no check at all: the river drawn in 1887 is not the one
  OpenStreetMap shows there (tiles in the session showed different channels).
* The estimator has failure modes. It locks on to a parallel line now and then (window 11400-12900 x
  900-2400 reads 408 m across, but by eye the bank there is within about 100 m). A different calibration
  shift moved two windows in or out of the set.
* A modern river is not an 1887 river; some of the difference is the river.
* Nothing below the 10°30' parallel (y > 7600 px) was checked: the model extrapolates there (the lower
  Vàm Cỏ meanders sit 20-40 px off by eye).
* No point features (junctions, towns) were matched. That needs a person at the map.

## Files

* `tan_an_graticule.py`: finds the grid, writes the fit CSV and the annotation. Reproduces exactly.
* `river_check.py`: the OSM river check; one cached Overpass query; reads the fit CSV.
* `annotations/bfc043c5-9023-4182-aa4e-807f4bffe762.json`: Allmaps annotation, Tan An, 16692 x 10052 px (the
  size `info.json` reports, equal to the JPEG), 24 GCPs, thin-plate spline, neatline mask. Parses with
  `@allmaps/annotation`.
* `points/`: fit and check CSVs, check summary.

Image-service ids come from the ingest log (drafts are invisible to the anon key; the slug query returns
`[]`). Tan An is `https://iiif.maparchive.vn/iiif/bfc043c5-9023-4182-aa4e-807f4bffe762`.
The other eleven (p-002...p-012, in order): f680349a-9970-48cb-ad0b-420bf7ff3365, d3ddd9b3-9276-4212-b51e-3f09606ec387,
48525b89-857b-4f66-96cb-7c94d98c473a, 2202a5ba-44d9-4fe2-ac0a-d1885b909c97 (Cholon), 62a29997-a0d3-433d-aeab-a40552d3f2b3,
ff6489cd-b5fe-4dea-9513-5468f5972eb3, e9fc1c66-a004-414e-8e17-4599445662fd, 2f1e6b96-249f-422c-82cf-151e6c2e9cbc,
8653da35-0366-49d3-b8e5-3f2512dcc84b, c110cf97-f0ba-4e55-97fa-f2241f8696b7, 2594e8c4-279f-4492-910d-be93f3bdbbf7.
Cholon's `info.json` width/height (9216 x 12794) matches its JPEG.

## To publish the Tan An georeference (not run)

The owner runs these; both lines are dry unless `--apply` is present. Do not publish before looking at it
in `/explore` against the modern map: the check above is thin.

```bash
node --env-file=.env scripts/georef_write.mjs --method printed-corners \
  --datum "Saigon meridian 106.6927E, west-counting longitudes; shift set on OSM rivers" \
  work/cochinchina-1889/annotations/bfc043c5-9023-4182-aa4e-807f4bffe762.json
# if the dry run is clean:
node --env-file=.env scripts/georef_write.mjs --apply --method printed-corners \
  --datum "Saigon meridian 106.6927E, west-counting longitudes; shift set on OSM rivers" \
  work/cochinchina-1889/annotations/bfc043c5-9023-4182-aa4e-807f4bffe762.json
```

`--allmaps` would also push to live.allmaps.org; leave it off until the placement has been looked at.
The writer never changes `status`: the sheet stays a draft until a person publishes it.

## What would make the other eleven possible

Not a graticule. Options, none tried: (1) match features (confluences, named chef-lieux, the coast) to a
modern base, which needs a person at the map and gives point checks that can be counted; (2) chain the plates
through shared borders, anchored by Tan An (I did not examine whether neighbouring plates overlap at the
edge; the sheets are cut to each arrondissement outline, so they may only touch). Neither is cheap, and both need the idea gate again.
