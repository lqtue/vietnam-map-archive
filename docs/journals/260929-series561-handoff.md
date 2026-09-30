# Series 561 georeferencing handoff — 2026-09-29

## Verified state

Repo: `/Users/airm1/Work/Projects/vietnam-map-archive`.
`DETECT_VERSION = 31`. Working code and docs are uncommitted; preserve them.

The 2026-09-28 handoff's 13-sheet boundary-trial table is resolved: **11 landed clear**,
1 (Muong Ou Tay W) stays held on a genuine axis-scale gap now that its boundary is fixed,
and 1 (Lang Son E) was found wrong on re-review and reverted to its version-28 held
verdict. Full account, including the two-sheet miss on the first landing (version 29) and
the method that caught it: `docs/journals/260923-indochine100k-georef.md`, section
"2026-09-29 — thirteen more boundary trials, two wrong on landing, one caught after".

Total locally clear: **314** (303 from version 28, +11 this session).
Read-only `check`: 314 placements in 314 slots, zero lattice conflicts.
`regress`: 314 clear placements, zero corner movements over 2px (self-consistency only —
see the method note below).
A manual snapshot diff against a pre-bump copy of `work/indochine-100k/*.json` (the real
cross-version regression check) confirmed all 303 version-28 placements are unmoved and
exactly the 11 accepted sheets flipped from held to clear.
Logs: `/private/tmp/indochine-place-v29.log`, `-v30.log`, `-v31.log`.
**No annotations or database statuses changed.**

Tracked changes: `scripts/indochine100k_georef.py`,
`docs/journals/260923-indochine100k-georef.md`, `docs/lessons.md`, `docs/ROADMAP.md`, and
this handoff.

| Remaining holds (46) | Count |
| --- | ---: |
| Abnormal catalogue spans | 24 |
| Axis-scale only (Ban Khana W, Bun-Tai E, Mon-Cay E, Muong Ou Tay W) | 4 |
| Mixed failures with a rim-offset-spread component | 12 |
| Shape/aspect failures without rim spread (Tourakom W, Vang Vieng W, Kompong Som W) | 3 |
| Persistent exclusions (Kompong Sralao W, Pursat E, Tri Binh W) | 3 |

## Method note: what `regress()` does and doesn't catch

`regress()` re-runs `detect()` against whatever is currently saved in
`work/indochine-100k/*.json` — it is a self-consistency check on the *current* code, not a
comparison against the previous `DETECT_VERSION`. Bumping the version and running `place()`
overwrites the very files `regress()` would need to diff against.

**Before every future `DETECT_VERSION` bump**, snapshot the baseline first:

```
cp work/indochine-100k/*.json /some/scratch/dir/
```

Then after `place()`, diff every corner of every previously-clear sheet against that
snapshot (tolerance 2px) and confirm the held/clear set changed by exactly the intended
sheets. This session's snapshot lived at `/private/tmp/vma-v28-baseline/`; it is not
preserved past this session — take a fresh one before the next bump.

## Method note: verifying a boundary pick

Two review methods missed real errors this session before a third caught them:

- **Resized contact-strip images** (~1600px wide, aspect-preserving resize) passed Muong
  Phine (W) and Muong-Song-Khone (E)'s wrong pins.
- **Fixed-window native crops** (±160px around the pin) also passed them, because the
  crop was centred on the wrong line and the true edge — 52px away — fell outside the
  window or was compressed past legibility.
- **A per-pixel profile**, `pixels.mean(axis=0)` printed row by row (or
  `pixels[k-100:k+100].mean(axis=0)` localised to the anchor's own along-axis window, to
  avoid slope smear on a tilted line), caught both: the blank-paper plateau visibly ends
  16–52px away from the wrong pin.
- Fit residual does **not** discriminate: the wrong (grid-line) pins fit *straighter*
  (residual 0.3–0.5px) than the true neatline (residual ~3.2px) does.
- The profile method has its own failure mode: a naive global-max search over a wide
  window will pick an outer decorative rule over a correct inner boundary whenever the
  sheet has a genuine double frame line (common in this series). Use a **local-prominence**
  check instead — is there a rule within ~3px of the pin, with paper outward of it and
  content inward — and confirm visually when the sides fails that check on sparse/low-relief
  terrain (content there simply doesn't read darker than paper, which is not a placement
  defect: confirmed by eye for Pa-Kha E's L/R/T and Pa-Kha W's T this session).

Read `docs/lessons.md`'s new entry (2026-09-29) before reviewing any further boundary pick.

## Lang Son (E) — put back in holds

`5300b1fc-7b90-4c8d-a800-5f369bea96ca`, 5152×7210. The handoff's seed (`B: 6643`) was
visually confirmed twice (contact strip, then a ±80px native crop) but failed the
localised per-pixel profile:

- **B side**: the true neatline sits at local index ≈179 within the fetched strip, ~10px
  outward (toward paper) of the pinned 189. Confirmed by profile only; both look plausible
  in a native crop at this scale.
- **R side**: two comparable rules at local index ≈180 and ≈200, with the previous
  auto-detected pin sitting in the low-value gap between them (value ~31, no spike at all).
  This is a low-relief area of the sheet — the R-side window is blank/sparse for its full
  ~490px fetch, so there's no content baseline to distinguish "outer decorative" from
  "inner mapped boundary" the way other double-line sheets allowed.

Do not re-accept Lang Son (E) by re-seeding B alone; R needs an independent read (which of
the two rules is the neatline) before it can be trusted, and the sheet's overall verdict
(`shape off by 4.6%; rim offsets spread 38%; axes disagree 4.4%`) suggests more than one
side may need correction. Source overview and metadata: search
`/private/tmp/vma-remaining-overviews/18-5300b1fc.*` (this session's numbering).

## Muong Ou Tay (W) — boundary now fixed, scale gap remains

`65559440-3d12-4cfe-9d52-9e872564f3bd`. Its bottom boundary is now source-reviewed and
pinned (`SOURCE_REVIEWED_RIMS`/`BOUNDARIES`/`FRAMES`), which removed the rim-spread and
shape-off components of its verdict. It now holds on exactly `axes disagree 2.0%` — a real,
isolated scale mismatch, matching what the 2026-09-28 handoff anticipated ("needs
printed-coordinate investigation after its boundary is fixed"). That investigation has not
been done. Its top side's profile is flat on both sides of its spike (low-relief, similar
to Lang Son's R and Pa-Kha's sparse sides) — worth checking during that investigation in
case the top pin itself needs review, though it currently passes both profile methods.

## Other holds to investigate

Unchanged from the 2026-09-28 handoff: **Ban Khana (W)**, **Bun-Tai (E)**, **Mon-Cay (E)**
(scale-only, printed-tick investigation not started), the 24 abnormal-span holds, and the
remaining mixed-failure holds not covered by this session's 13-sheet batch. See that
handoff's "Other holds to investigate" section — none of that material changed.

## Operational constraints

Same as the 2026-09-28 handoff: read `docs/lessons.md` before a pass producing numbers,
`work/CLAUDE.md` before editing under `work/`. Crops, cache, and per-map JSON under
`work/indochine-100k/` are intentionally untracked; preserve them. Do not run
`annotate --apply`, publish, or change database statuses without an explicit request.
