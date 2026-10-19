# 1971 provincial sheets: can colour cut each sheet to its own province? (2026-10-19)

Side test, not a NOW.md bet. Nothing stored, posted to Allmaps or wired into `build.py`.

## Question

Each of the 44 South Vietnam 1971 provincial sheets (`work/vn1971/up/NN.jpg`) shows neighbouring provinces and sea around its own province, so sheets overlap on the map. Can the Allmaps `resourceMask` be the target province only, found from colour?

## Answer

Mostly, and with known failure types. The target province is printed on bare paper and its neighbours are tinted, so a median blur, an Otsu threshold on paper-bright pixels and the biggest bare-paper blob give the outline (`scripts/vn1971/province_mask.py`, hints in `province_hints.json`). Read by eye on all 44 outlines: 28 look right, 9 fail, 7 cannot be judged from the printed colour alone. Judged on thumbnails; only 20, 34 and 42 were opened at full size.

- **Looks right:** 03 04 06 08 09 12 13 14 15 17 20 21 23 24 26 28 29 30 31 32 33 35 36 37 39 40 43 44.
- **Fails:** 01 05 16 18 22 25 34 42, and 38 north (needs a hand cut).
- **Cannot tell** (needs the printed boundary read at full size): 02 (leak at upper right) 07 10 (a lobe at lower left) 11 19 27 41 (right-angle steps).

## Error types

| Type | Sheets | Why | What would fix it |
|---|---|---|---|
| Neighbour printed on white paper (no tint) | 38 north, 42, 27, 02, 10, 41, 07 | Colour has nothing to separate | Hand `cut` polygon, or read the printed province line (grey dashes) |
| Province split by a river, a piece lost | 01, 16, 18 | The bridge joins blobs only within `gap` (60 small px) and never across the printed line; widening `gap` did not recover 01 or 18 and made 16 worse | Hand polygon per piece |
| The province's own land is tinted | 42 (coastal plain), 22 (relief shading), 25 (aged paper, 13% tinted-in) | Tint is relief or age, not "neighbour" | `grow` helps 25 only; 22 and 42 need a hand polygon |
| **Stored neatline is short** | **34, 42** | Grid detection stopped short of the sheet edge. 34: GCPs reach x 10278 of a map frame near 13600; 42: x 11873 of a frame near 15500. The mask clips to that frame, so the east edge is a straight line that is not a boundary | Re-run grid detection for these two sheets. This is a **georef coverage** defect, not a mask one: the stored map covers only part of the sheet |
| Stain or crease | 05 | A slit cut through the mask | Larger close, or a hand fix |

Signals: `tinted-in` flagged only 25. `left-out` is weak: sheet 20 shows 12.6%, yet its outline is correct (the "missing" paper is a pale neighbour strip). Shape statistics flagged only 16 and 42.

## Dead ends

- A wider search window for the inner frame (0.35 of the sheet instead of 0.07) moved the frame to the page edge on about 40 sheets. Reverted. Do not retry.
- Allmaps' "remove colour" is a one-colour key, viewer-only (`packages/render/src/shaders/map/post.frag`), so it cannot be a stored mask.
- `gap` 140/200/400 for 01 and 18.

## So what

Colour gives a usable province mask for about two thirds of the sheets without a hand step. The rest need a hand polygon, and 34 and 42 need their grid redone first. No bet moved. `build.py` now takes the polygon as an option (`PROVINCE=1 sh scripts/vn1971/reg.sh NN`, mask read from `work/vn1971/province/NN.json`, output beside the stored annotation as `<map id>.province.json`). Built 15 and 38: GCPs and image identical to the stored annotation, only the mask differs (8 points → 200 and 440); both outlines look right on the preview (38's north follows the printed DMZ line, its west edge runs near the frame). Next: read one on Allmaps before any stored row is touched. Allmaps takes one ring per `resourceMask`; several masked maps per image would need a schema change (not decided).
