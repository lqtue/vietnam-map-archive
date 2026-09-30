# Series 561 georeferencing handoff — 2026-09-30

## Verified state

`DETECT_VERSION = 39`. Working code and docs are uncommitted (script diff now well over
1,200 lines against the last commit `eb62326b`); preserve them. This supersedes the
260929 handoff, which is stale (v31, 314 clear) — everything below happened in the
same-day session that followed it, recorded inline in
`docs/journals/260923-indochine100k-georef.md` under its "2026-09-30" entries. That file
is the primary record; this is the orientation pointer.

`check()`: **328 clean placements**, zero lattice conflicts — **stale as of the landings
below**, which added 9 more clear placements but could not re-run `check()` (see the coastal
entry's "Environment constraint" — local credentials can't see draft rows). Whoever runs
`place()`/`check()` next with real service-role access should treat 337 as the expected
floor, not confirmed.
`annotate` (dry run): **14 ready** as of the Phan Rang landing, **23 ready** counting the 4
coastal sheets, Lang Son (E), Lai Châu (E), Tu Lê (E), Tri Binh (W) and Quang Ngai below (not
re-run through `annotate` itself, same credential gap — their local JSON caches show `clear`
from a direct `placement()` call). **346 held** is stale by the same 9. Not applied —
`annotate --apply` is a production write and stays with the user.

**Landed this session:**
- **Lai Châu (E), Tu Lê (E), Tri Binh (W), Quang Ngai** (the remaining held Vietnam sheets
  besides Cao-Bang E/W, which stays deliberately held): four unrelated single-sheet fixes,
  each independently confirmed by re-deriving the sheet's own printed grid rather than trusting
  fit residual alone. **Lai Châu (E)**: all four rim anchors were already clean, isolated,
  confidently-fitted lines (0.4-4.0px residual, 21-24/24 patches) — verified by native darkness
  profile at each, no competing feature nearby — so the `rim offsets spread` (17%) and small
  `axes disagree` (1.5%) verdicts were the printed sheet's own real margin-width variance and
  distortion, not a detection error; registered as source-reviewed rims/axes, no catalogue
  change. **Tu Lê (E)**: same failure class as Than-Poun (E) — B's automatic pick (offset
  250.5px, far outside the other three sides' 170-195px) had walked past the true neatline onto
  an interior label-box rule inside a kilometric-index/corner-grade-label block; the true
  neatline sits at the single thin line right at the top of that block, refit there at 0.35px
  residual (24/24 patches) vs. the wrong pick's 3.4px. **Tri Binh (W)**: the 2026-09-23
  calibration-sample read (Gemini, 2 ticks/axis) found it 741.5m off the accepted fit and it was
  dropped from calibration and held, unresolved. Redone with 3 ticks per axis, no Gemini: both
  intervals on each axis agree with each other to <0.3%; east and north match the catalogue
  closely (within ~60m) but west and south are genuinely wrong by +509m/+544m — corrected via
  `SOURCE_REVIEWED_CORRECTED_BOX`, removed from `CALIBRATION_HOLDS`. **Quang Ngai**: the
  coastal-family investigation's leftover "doesn't fit the ~0.49g cluster" case — read its own
  four printed longitude ticks (118.20-118.50g, top margin): west matches catalogue (+256m,
  noise), east is off by **~9.2km**, a genuine catalogue transcription error. Corrected east
  gives a printed span of 0.4281g, matching the independent pixel-aspect estimate (0.4280g)
  almost exactly, and now sits inside the standard 0.36-0.43g band on its own (no special-span
  registry needed). All four `verdict: []`. `DETECT_VERSION` not bumped (registry data only).
- **Lang Son (E)**: the 2026-09-29 "two comparable rules, ambiguous" note on its R and B
  sides was a reversed outer/inner read, not a double-frame pick. `detect()`'s own coarse
  guess already lands on a real, well-defined ~9-10px line on both sides — the same
  character as every confirmed neatline elsewhere — but the standard "search inward from the
  outer decorative frame" step then walks off it onto interior graticule/kilometric ticks in
  a sparse area, landing in a genuinely quiet gap on both sides (confirmed by native darkness
  scan, not by residual — a confident fit isn't the same as a correct one). Registered both
  as **direct** fixes at the coarse guess's own position (`SOURCE_REVIEWED_BOUNDARIES` +
  matching `SOURCE_REVIEWED_RIMS`). `rim offsets spread` 38%→11.6%, `shape off`/`axes
  disagree` 4.6%/4.4%→0.7%/0.7% — **clears outright**, no catalogue correction needed. Full
  account: `docs/journals/260923-indochine100k-georef.md`, "Lang Son (E): the 'two comparable
  rules' were a reversed outer/inner read, not a double-frame pick".
- **Coastal ~0.49g family** (Phu Diên Châu (E), Qui Nhon (E), Söng Cau (E), Nha Trang (E)):
  the retracted-sibling-rule family confirmed earlier today, now landed. Read each sheet's
  own printed west AND east longitude ticks (not just one side — the west-catalogue residual
  was too large, 0.4-1.6%, to treat as "matches, not touched" the way Phan Rang's north did)
  and used the sheet's own measured box directly via a new `SOURCE_REVIEWED_CORRECTED_BOX`
  + `SOURCE_REVIEWED_SPECIAL_SPANS` pair. Qui Nhon/Söng Cau/Nha Trang cleared immediately;
  Phu Diên Châu (E) needed the same two follow-ups as Phan Rang (E) — a genuinely wide B-side
  margin (`SOURCE_REVIEWED_RIMS`) and a confirmed-real axes/shape distortion under the 5% cap
  (`SOURCE_REVIEWED_AXES_DISAGREE`). All 4 `verdict: []`. `DETECT_VERSION` not bumped (no
  `detect()` code changed). Full account: `docs/journals/260923-indochine100k-georef.md`,
  "the coastal ~0.49g family: landed, all 4 clear" — including the credential gap that
  blocked running `check()`/`annotate` against these 4 through the real pipeline.
- **v35→v36**: Sam-Neua (E)'s B and R rims were genuinely wrong (pinned deep in
  feature-free/textured runs with no real line nearby). Fixed the `detect()`
  `manual`-boundary code path (it required an unfittable outer-rule check even for
  `direct` sides, which never use that result) and added the sheet to
  `SOURCE_REVIEWED_BOUNDARIES`/`SOURCE_REVIEWED_RIMS`. **Still held** — shape/axes error
  only narrowed (5.5%→4.6%, 5.2%→4.4%), a catalogue-span problem, not investigated
  further. `docs/journals/260923-indochine100k-georef.md`, "Sam-Neua (E)'s
  manual-boundary fix, landed but doesn't clear it".
- **v36→v39**: Phan Rang (E)/(W) — both catalogue-declared abnormally tall
  (~0.608-0.609g lat vs. the 0.48-0.53g standard band). Read each sheet's own printed
  parallel grid off native crops (4-5 grade ticks per sheet along the left margin) and
  found the catalogue's **south** bound wrong by 5.8' (E) / 3.1' (W) — north matches the
  catalogue closely, not touched. Cross-checked against the independently-detected pixel
  aspect ratio: 2-3% residual once corrected (was 14%). New registry,
  `SOURCE_REVIEWED_CORRECTED_BOX`, substitutes the corrected UNIMARC field inside
  `record_box()` — the first landing path in this project that overrides a catalogue
  value rather than only validating one. **Both sheets now `clear` and `annotate`-ready.**
  Full account: `docs/journals/260923-indochine100k-georef.md`, "Phan Rang (E)/(W): the
  catalogue's south bound is wrong, confirmed against the printed sheet".

### The 14 ready (new, not yet published)

| id | name |
|---|---|
| edd8be90-fa2d-422f-aa46-cbc1f6c657ac | Phan Thiet (E) |
| 04f35f4f-b19a-4992-bfc7-d1da75a9ddba | Phan Thiet (W) |
| 283ae0d8-dca7-4a2d-a86e-1e56dc08527e | Thanh Hoa (E) |
| 99adde4f-9d56-4a66-b186-6c8e81b63d39 | Vinh (E) |
| 8289d9a6-6780-4f1e-8ead-7f9f137d6ada | Ha-Lang (W) |
| f9fc556b-8311-4e0a-8f72-fd5801b13ef1 | Quan-Ba (E) |
| 1ce2d961-4147-44eb-964c-9a7f64ea48d4 | Muong-Tè (E) |
| a8039626-c205-4a4d-a136-87acb33c2fc8 | Than-Poun (E) |
| 559ba082-a861-45a8-bbff-e0285f727bd9 | Mon-Cay (E) |
| edb34855-cc39-4b9b-83cd-113f5aafb505 | Vientiane Ban Keun (E) |
| 65559440-3d12-4cfe-9d52-9e872564f3bd | Muong Ou Tay (W) |
| 6bdd9ab8-22dd-460d-b511-0a29d5dd843f | Bun-Tai (E) |
| c19c68a6-5ce8-4b74-86ec-9272f0c98a21 | Phan Rang (E) |
| 3d0a6cca-5ca3-4ceb-9334-5374d4d2afb4 | Phan Rang (W) |
| 65366fa5-092a-4225-a576-69e83bf4c647 | Phu Diên Châu (E) |
| ba3f38a6-78ed-49d6-a656-8390961cab3b | Qui Nhon (E) |
| 7bf1330c-2cf2-4974-9daa-dded9ed72d00 | Söng Cau (E) |
| e8b02c15-5e15-4bc5-bf99-b5d4e2c008e2 | Nha Trang (E) |
| 5300b1fc-7b90-4c8d-a800-5f369bea96ca | Lang Son (E) |
| a387ff3f-05c4-4d46-8470-079323555c40 | Lai Châu (E) |
| dcfb2452-b976-4092-bddb-8c9e04300db3 | Tu Lê (E) |
| 1f025a9f-ea9e-4816-ad35-edfba60bf518 | Tri Binh (W) |
| 48584dae-d4e3-4821-82a1-bab588ec3dd2 | Quang Ngai |

Last 9 rows: `clear` from a direct `placement()` call, not from `annotate`'s own dry run
(same credential gap) — re-run `annotate` once real access is available to confirm.

Command to publish drafts (does not flip `status`, only writes the annotation + flags
`is_georeferenced`): `work/ocr/.venv/bin/python scripts/indochine100k_georef.py annotate
--apply`. Not run.

### Held list, now 23 (was 34 — Phan Rang (E)/(W), the 4 coastal sheets, Lang Son (E), Lai Châu (E), Tu Lê (E), Tri Binh (W) and Quang Ngai cleared this session)

Rebuilt directly from current verdicts rather than trusted from an older list — the
09-29→09-30 session found the 09-28 handoff's list was itself missing 6 sheets.

**Vietnam (2):** Cao-Bang (E), Cao-Bang (W) — left held on purpose (kilometric Bonne-grid
edition, not worth the risk for a rushed pass, per the 2026-09-30 "checked the rest of the
corpus" entry). Not re-opened this session; ask before reopening. Everything else that was
in this list — Phan Rang (E)/(W), the coastal 4, Lang Son (E), Lai Châu (E), Tu Lê (E), Tri
Binh (W), Quang Ngai — cleared, see above.

**Laos (~17):** Ban Khana (W), Ban Soukhouma, Ban Taphane (W), Keng Kabao, Khong-Sédone
(E), Paksé, Sam-Neua (E), Savannakhet, Thakhek, Tourakom (W), Vang Vieng (W), Vientiane
Ban Keun, Vientiane Ban Keun (W), Xieng Khouang ouest (W), Lovéa (W)*, Klong Klun*.
(*borderline — Lovéa/Klong Klun sit near the Cambodia border, not confirmed.)

**Cambodia (4):** Kompong Som (W), Kompong Sralao (W), Pursat (E), Svay-Rieng (E),
Sisophon (W).

Country tags here are a quick bbox/name read for work-ordering only, not a reviewed
classification.

## Open item that must reach the user before anything lands

The 2026-09-30 session got approval for "trust the standard sibling + detected neatline"
on the 17 abnormal-span holds, then **tested and retracted it** for the 3 Vietnam
sibling-pair sheets (Phu Diên Châu E, Qui Nhon E, Söng Cau E) plus Nha Trang (E) and
Quang Ngai: the sibling's declared width is a *worse* fit than the sheet's own declared
width, not better (see the 09-30 "sibling rule fails its own check" entry). A genuine third
span family (~0.49g, independently implied by pixel-aspect matching on 4 of the 5) was the
working hypothesis at that point, unconfirmed. **Confirmed later the same day, twice**: a
first pass read each sheet's printed longitude ticks with eyeballed label centers (provisional
— Gemini OCR quota was exhausted); a second pass fixed the two problems that method had
(a naive scan locking onto the sheet's decorative dashed rule instead of the grade labels,
and label-centroid position shifting with glyph count) and got landing-grade fits without
ever needing Gemini — see "the coastal ~0.49g family, redone at landing-grade precision".
**Final printed spans: Phu Diên Châu (E) 0.504g, Qui Nhon (E) 0.490g, Söng Cau (E) 0.494g,
Nha Trang (E) 0.487g** — three of the four agree with the pixel-aspect-implied value to
within 1% (Qui Nhon, Söng Cau, Nha Trang); Phu Diên Châu's two margins agree with each other
but read a genuinely different value (~0.50–0.51g) from the other three, the same way Phan
Rang (E)/(W) took different corrections from each other. **Tell the user this plainly before
treating any of these 4 as resolved** — the family is confirmed at landing-grade precision,
but nothing has actually landed: no registry entries, no `DETECT_VERSION` bump, no database
writes. Quang Ngai is still a separate, unresolved problem (0.428g implied, doesn't fit the
cluster).

## Next steps (not started this session)

1. Design and build the landing path: `finish_printed_quad()` rejects anything >0.003g from
   the catalogue value — that gate exists exactly because these sheets are the case it's
   meant to catch, so it can't gate itself away without a second, independent check to
   replace it. `SOURCE_REVIEWED_CORRECTED_BOX` (proven on Phan Rang) is the likely mechanism
   now that a solid printed reading exists for all 4. Needs an explicit go-ahead before
   touching the registry/`DETECT_VERSION` — the printed readings above are ready to use, but
   landing is a bigger step than reading.
2. ~~Sam-Neua (E): approved `detect()` manual-boundary fix, not yet made.~~ Already landed
   this session (`SOURCE_REVIEWED_BOUNDARIES`/`RIMS`, `DETECT_VERSION` 35→36) — it narrows
   the verdict but doesn't clear it (catalogue-span problem, not investigated). This item
   was stale in an earlier draft of this handoff.

## Operational constraints

Snapshot `work/indochine-100k/*.json` before any future `DETECT_VERSION` bump; `regress()`
alone only checks self-consistency against whatever's currently saved, not cross-version
movement. Read `docs/lessons.md`'s 2026-09-29 entry before reviewing any boundary pick.
No `annotate --apply`, no publish, no database writes without an explicit request.
