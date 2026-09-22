# Lessons

Rules this project has paid for more than once. Each one names the failure that taught it and the
date, so it can be checked rather than believed. The full story of any of them is in
`docs/roadmap-record.md` under that date.

**Read this before starting a pass that will run unattended, write to the database, or produce a
number.** Every elaborate pass in the record ended by finding a basic thing broken, and it was
usually one of these.

## Verifying

**Verify the thing, not the gate.** A gate can be green over a broken thing, and on 2026-09-13 that
happened three times in one day: 56 published sheets drew nothing while the catalog reported them
fine, a CHECK constraint seeded in migration 083 had never once fired because `held_by = 'map'`
against NULL is NULL and a CHECK rejects only false, and a coverage denominator was seeded from the
wrong catalogue. The same shape again on 2026-09-04: an OCR overview assembled with a checkerboard
of white holes over 31.8% of the sheet, and the model scored 7/7 on it. Look at the artefact.

**A wrong number looks like data, not like a bug.** This is why the two rules above are worth the
time. A sheet placed 470 m out, a coverage bar drawing a held cell as a gap, a street index a few
hundred metres off — none of them throw, and all of them read as a fact about the corpus. Most of
the test suite exists to catch exactly this class.

**A refused probe reads exactly like a probe that was answered "no".** `backfill_iiif_widths.py`
asked the edge whether a derivative existed using urllib's default User-Agent, got 403, and its
"not 200 means missing" rule turned that into 93 phantom gaps. Curl, same URLs, same second: 6. If a
script decides what work to do by probing a network service, make the refusal distinguishable from
the answer (2026-09-13).

**A transport error must never report success.** `vma_worker.py --once` caught
`requests.RequestException` on its claim call, printed "queue empty" and returned 0 — so a DNS blip
stranded a running job with a dead subprocess while an unattended drain reported it done
(2026-09-04).

**Check a cached route with a cache-buster before believing it did not deploy.** The sitemap looked
wrong for an hour after the 7.3 deploy and was not: `max-age=3600` at the edge, and the same URL
with a buster was already correct (2026-09-15). Related: a freshly written R2 object is not
immediately readable through the worker — 404 on all three widths straight after rclone reported
success, 200 a few seconds later (2026-09-13).

## Measuring

**Measure before tuning.** `--auto-priority` was not merely weak, it was inverted: fed a 1024 px
overview it rated the dense city centre *below* the margins at every resolution up to 2048, so it
would have skipped exactly the tiles worth reading. The colour pre-pass scored 0.000 on every tile
of the 1882 sheet, and the reason was not its saturation gate but that every saturated pixel on that
sheet is hue 0–60° while it looks at 60–260° (2026-09-04).

**A fixed pixel tile is a different amount of ground on every sheet.** 2048 px is 1.7 km on the 1923
sheet and 5.7 km on the 1959 one, which is why coarse sheets looked empty and got blamed on their
scans. Ground per call is the unit that matters; the rule that followed may make a sheet finer,
never coarser (2026-09-04).

**Run-to-run variance is not nothing.** The same OCR configuration twice on one sheet gave 6 labels
and 5, and the disagreement was mostly the same feature transcribed differently. Never treat a
single run's small delta as a result (2026-09-04).

**A three-point fit has zero degrees of freedom, so its RMSE is identically 0.** A sheet on 3 GCPs
can be badly wrong while reporting nothing at all. A residual of 0 is the absence of a measurement,
not a good measurement — this is `three-point-residuals`' whole reason for existing.

**Say which number you mean before comparing it to another.** Four numbers can all be correct and
all differ: for L7014 an ArcGIS index says 627 cells, PCL publishes 535 scans, we hold 461, and 9
are `maps` rows. For the Indochine survey its own record declares 81 while the union of CartoMundi's
two catalogues gives 79 — a floor, not the truth (2026-09-13).

**Check which edition you are comparing against.** CartoMundi catalogues the Tonkin 1:25,000 three
times. Against serie 175 our rows matched 8 of 62 with a thirty-year offset, which reads exactly
like a bad attribution; against serie 243 it is 60 of 62. The existing attribution was right all
along and was nearly overwritten (2026-09-13).

**Do not oversell a small signal.** Three confirmed survivors out of 28 named institutions on one
sheet is a dozen-scale lead city-wide. It is a seed and a cross-check on a fit somebody else made,
never a fit on its own (2026-09-11).

## Writing

**Nothing under `scripts/` may write on a bare invocation.** `--apply`, never `--dry`. This item has
now been closed three times on a count that was too low — four scripts, then nine, then sixteen —
so its exit condition is the grep, not a number: `grep -rn "includes('--dry')" scripts/` returns
only `lib/cli.mjs`'s own guard.

**A replaced scan invalidates pixel work; a changed georeference invalidates ground work.** Observed
once already: re-scanning the 1959 sheet emptied `maps.triage`, and had the triage survived, the
saved neatline would have cropped the *old* scan's pixels while looking entirely valid
(2026-09-10). This is `stale-after-change`.

**A sheet number is not a token — four of them contain a space.** A backfill keyed its updates on
`` `${series_key} ${sheet_number}` `` and split on the space, so `"0 bis"` came back as sheet `"0"`
and that cell was written with the wrong row's printing. It was invisible only because the two
sheets involved share a year; `5`/`5 bis` differ by five years and would have shown it immediately.
Separator is NUL now (2026-09-13).

**Two `npm run build` runs in one shared worktree lose each other's output.** `build` wipes
`.svelte-kit/output` before writing it, so two builds a minute apart leave a half-overwritten tree
and the deploy that runs last publishes it — same commit, different bytes, nothing in either log
saying so. In a shared worktree, announce a build and hold all writes until it is deployed
(2026-09-13).

**CSS fails silently, twice over.** A `var(--token)` nothing declares does not error — the whole
declaration is dropped, which is how `gap: var(--space-sm)` rendered as no gap in three files for
weeks. And an opacity animation with a `forwards` fill keeps the stacking context it creates
forever, which sealed every fixed drawer and modal on every editorial page under the nav,
unreachable by any z-index (2026-09-14). `tests/screens.spec.ts` now pins the first.
