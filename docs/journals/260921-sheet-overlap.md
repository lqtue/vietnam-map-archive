# Two sheets on one ground — 1882 and 1898 overlaid

**2026-09-21.** How closely do two Saigon plans sixteen years apart actually
overlap once each is warped by its own georeference, and what sets the floor?
Prompted by building a stacked-layer presentation of the corpus
(`work/proto/fabric/`) and noticing the two sheets did not sit on each other.

The short answer: **~50–100 m, and the limit is scan distortion, not the
transform.** An affine has one scale per axis and no more; on these two sheets
the two axis scales differ by 1.5% and 2.79%, which over a 14,000 px sheet is
~390 px of shape no affine can absorb.

## A wrong turn worth recording

The first attempt registered the sheets to **each other** through the place
names printed on both, on the assumption that 1898's georeference was unusable —
its own export README calls its three control points unreliable. That produced
`work/ocr/scripts/sheet_register.py`: RANSAC over a 4-dof similarity on names
unique to both sheets, then trimmed ICP on block centroids.

It works — 50 shared unique names, 35 inliers, 25.1 m from names alone, 16.1 m
after ICP — but it was solving a problem that did not exist. **Every sheet in the
District 4 series already has an Allmaps annotation with GCPs**, publicly
readable at `…/storage/v1/object/public/annotations/<mapId>.json`, which is
where `scale.py` and `georef_error.py` have been reading them all along. Warping
each sheet by its own GCPs is simpler, needs no shared names, and extends to any
sheet in the archive.

The script is kept, for two reasons: it is the only route for a sheet that has
**no** annotation, and the agreement between the two independent routes is a
check nothing else provides (below).

## The measurements

Affine fitted by least squares to each annotation's GCPs, ground in local
equirectangular metres about 10.775°N. The fit reproduces
`work/analysis/district4/georef_error.md` exactly on 1882 — RMSE 10.6 m, worst
17.4 m — which is the check that this reads the annotation the way the rest of
the repo does.

| sheet | GCPs | declared | affine RMSE | rotation | axis scales (m/px) | spread |
|---|---:|---|---:|---:|---|---:|
| 1882 Plan Cadastral | 10 | `helmert` | 10.6 m | **+89.64°** | 0.3445 / 0.3393 | 1.5% |
| 1898 Bertaux | 3 | `polynomial` 1 | **0.0 m** | −0.26° | 0.3415 / 0.3321 | **2.79%** |

**1898's 0.0 m is arithmetic, not accuracy.** Three GCPs are six equations for a
six-parameter affine, so it fits its own points perfectly and says nothing about
the sheet. `georef_error.md` makes the identical point about the 1923 sheet's
three points. Any comparison that quotes it as an error figure is wrong.

**The two sheets are ~90° apart on paper.** 1882 is drawn at +89.64°, 1898 north-up
at −0.26°. Sheet frames are not a display convention that can be ignored.

Agreement, both measured over the whole sheet:

- **Two independent routes for 1898** (own GCPs, versus name-registration onto
  1882 composed through 1882's GCPs) disagree by **median 48 m, max 117 m**.
  Neither is ground truth; they bound each other.
- **Block centroids**, 1898 to nearest 1882: **median 78 m, 44% within 50 m, 52%
  within 100 m.** A weak metric on its own — a 1898 block can be a subdivision of
  a 1882 one, so some of that distance is real change rather than error.
- **Shared place names, both ends warped to ground**: 33 pairs within 150 m,
  **median 25 m**; best are Rue de Kerlan 5 m, Rue Turc 9 m, Marché de Cầu Ông
  Lãnh 11 m, Casernes 12 m. Label centres are slack by construction — text is
  printed *near* a feature — so 25 m is an upper bound on the georeference error,
  not a measure of it.

## What this means for the work

**1898 needs more control points.** Three is the minimum that yields a number at
all, and it yields a fake one. This is the single highest-leverage manual task
on that sheet; nothing downstream can be better than it.

**Neither sheet's OCR run has been reviewed.** 1882's reviewed run `v1b` (84
validated · 68 rejected · 25 pending of 177) lives in Supabase, not in `work/`;
everything here used the later local `post0910` (287 rows). Note that `v1b` is
also the *smallest* run on the sheet — `rr0910` has 348. A root sheet wants a run
that is both reviewed and complete, so the review should be pointed at a fuller
run rather than at finishing `v1b`'s 25 pending rows.

**More layers are not blocked by georeferencing.** All seven District 4 sheets
carry annotations: 1882 (10 GCPs), 1895 (11), 1898 (3), 1923 (3), 1942 (12),
1959 (10), 1968 (15). What is missing per sheet is block geometry — only 1882 and
1898 have colour-block output. `260920-colour-transfer.md` already ran the colour
pass over 1923/1942/1959/1968 as a visual check, so the method transfers; those
runs need promoting to normalised exports before they can join a stack.

## Files

- `work/ocr/scripts/clean_blocks.py` — geometry/class hygiene on a colour-block
  export: centroid outside `map_content_bbox`, duplicate rings, neatline loops,
  and `building` polygons past 100,000 px² reclassed to `land_plot` (both sheets'
  building median is ~800–950 px²; 1898 carried a 2513×5041 "building"). 1882
  1443 → 1431, 1898 3177 → 3156.
- `work/ocr/scripts/sheet_register.py` — the name+ICP route described above.
- `work/proto/fabric/` — the stacked presentation. `build.py` warps by GCPs and
  emits `layers.json`; `index.html` draws it in CSS 3D, no libraries.

## Open

- A neatline arm survives on both sheets. The obvious thin-and-long test also
  catches canals, which are the most valuable geometry these sheets carry, so it
  is left in place and framed around (percentile bounds, not min/max).
- Whether a higher-order transform (the 1895 sheet declares `thinPlateSpline`)
  closes the axis-scale spread, or whether the spread is paper shrinkage that
  wants a physical model rather than more parameters.
