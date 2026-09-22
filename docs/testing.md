# Test inventory

What `npm run test` actually runs, and why each check exists. Moved out of `CLAUDE.md` (Sept 2026).
Verbatim.

`npm run test` starts a dev server on 5173, or reuses one already running. It runs **363** tests:
the **twelve** smokes in `tests/smoke.spec.ts` (the twelfth, Sept 2026, pins that a retired
`/scan?map=<id>` link lands on that sheet's own page rather than dropping the id at `/catalog` — the
public viewer merged into `/catalog/[id]`, and every bookmark, every /explore action strip and the
catalog drawer pointed at the old address; it uses a synthetic uuid on purpose, because the redirect
is a URL rewrite that knows nothing about the row and pinning it to a real sheet would fail the day
that sheet is unpublished) and the **six** in `tests/catalog-series.spec.ts`, which are
**read-only** (they hit the real Supabase project but never write), plus 345 browser-less pure
checks that ride the same runner — `tests/press.spec.ts` (the Gallica CQL builder and the NLV year
window), `tests/explore-keys.spec.ts` (the /explore time scrubber, and whether a share link's hash
camera survives its own `?map=`), `tests/tween.spec.ts` (the annotate-mode easing that replaced
animejs), `tests/search-fold.spec.ts` (diacritic folding in the map picker),
`tests/triage-suggest.spec.ts` (level0 tile addressing and the triage proposal),
`tests/map-grid.spec.ts` (the printed reference grid, cell to point), `tests/coordinates.spec.ts`
(typing a position into the location search — and mostly the **military grid reference** the US Army
sheets of Vietnam carry, `48Q XD 850 418`. Those are UTM on the **Indian 1960** datum, and a reading
that ignores the datum lands ~480 m east-southeast: a point on a map, in the right neighbourhood,
four blocks from what the reference meant, with no error anywhere to say so. The 100 km square
letters are pinned against squares the historical record fixes independently — Saigon is XS, Khe
Sanh XD, the Ia Drang YA, Huế YD, Đà Nẵng BT — because a one-off in the row offset or the column set
moves every decoded reference exactly 100 km, which reads as a different bug entirely; the decode of
`XD 850 418` is then checked against the combat base's own coordinates. Also pins the two directions
a parser on a keystroke can fail: a place name that is read as a coordinate outranks the real place
results, and a square from another zone or another country is a position invented out of nothing),
`tests/street-index-grid.spec.ts` (that same cell-to-rectangle arithmetic, pinned against the Python
copy of it: `ocr street-index` reads a sheet's printed street directory and has to place each street
as it writes, because the box columns are NOT NULL, so `_cell_rect` in `ocr.py` and `cellBox` here
are checked against one committed fixture — a drift between them does not look like a bug, it looks
like a street a few hundred metres from where it belongs on a map where everything is a few hundred
metres from something; also pins the one asymmetry on purpose, that only the TypeScript side reads a
run of cells), `tests/triage-state.spec.ts` (what still stands between a sheet and an OCR run — the
predicate that decides whether money is spent, and whose old form queued nothing across the whole
corpus while reporting success), `tests/mpp-parity.spec.ts` (the two ground-metres-per-pixel
estimators against one sheet's real GCPs — `scale.py`'s affine fit over all the control points and
`collection_aoi.mjs`'s ground-area-over-pixel-area ratio, which had never been run on the same
input; they agree to 0.24%, and the 2.8x that sat in the docs for weeks was the same map measured on
two different scans, neither figure saying which, which is why the test also stands as the reason a
m/px number needs its scan's pixel size written beside it), `tests/density-parity.spec.ts` (the
tile-density signal against real 1882 ink, because it exists twice — measured TS for the browser
proposal, Python for the automated one — and a drift between them looks like a sheet that simply
came back thin), `tests/ingest-cells.spec.ts` (how a sheet of paper is named: the cell-number,
quadrant, part and printed-year parsers in `scripts/lib/cells.mjs`, which every institutional ingest
reads a catalogue through. They existed as copies in four scripts whose headers said "lifted
verbatim" with nothing enforcing it, and they had already drifted — measured over the 304 real IGN
copy records, three part classifiers disagreed on **79** of them, every assemblage, because
`ingest_indochine_nakala.mjs` had no assemblage branch and called each one 'whole'; it reached no
database only because that script's input file happens to be pre-filtered, and a re-fetch over serie
175, which is all assemblages, would have minted 79 two-half cells as whole sheets. The strings are
bytes copied out of the four real catalogues rather than cases re-derived from the parsers, because
a checker that shares the parser's blind spot passes while the corpus is wrong: ANU's lowercase-L
Roman numerals ("Sheet 6738 lll"), the five spellings of three Indochine `bis` cells, the note that
names the other half in its second clause, and the three four-digit decoys on a TTU collar — a datum
and two currency-of-information dates — that a greedy `\d{4}` files under the wrong decade entirely
reasonably. The full-corpus run, old parsers against new over all 304 IGN records, 160 ANU items and
both hand-read tables, is `node scripts/lib/cells.test.mjs`; the dumps it needs are 42 MB and
gitignored, so this is the half that rides CI), `tests/label-obb.spec.ts` (the OCR label rectangle:
an angle-and-size object whose axis-aligned box is derived, so the round trip through the columns is
asserted at every angle — including 45, where the box alone is blind — plus the corner drag that
resizes along the label's own axes), `tests/layout-regions.spec.ts` (the layout vocabulary and which
rectangle steers the tile grid), `tests/georef-editor-url.spec.ts` (which IIIF source Allmaps Editor
is handed when reopening a map's control points), `tests/iiif-source-size.spec.ts` (whether a IIIF
endpoint serves the scan an annotation was actually drawn on, and which endpoint a re-mirror should
aim at. Both halves are one bug, found by reading the live rows rather than the code: the mirror
rewrites an annotation's source URL with a string replace, which cannot touch `width`/`height`,
`resourceCoords` or the SvgSelector mask. The 1942 sheet is the case — its rescan lives under a
**dated** R2 key, `…-7651a1c48aba-20260911` at 14915x12602, while the bare map id still serves the
original 7479x6314, and Allmaps authors the georeference against the original. So a re-mirror that
assumes the bare id is internally consistent and **silently demotes the sheet back to the old scan**
— half the resolution, thumbnail and primary source row included, no error anywhere — while a
re-mirror that keeps the rescan aims IA-space coordinates at an image twice the size, which is the
whole georeference doubled. `r2MirrorBase` picks the second and `sourceSizeMismatch` refuses it with
a 409 before the first write, which is the only honest outcome: the rescan is affine-with-offset to
the original, so rescaling the mask is wrong by up to 75 px and re-georeferencing is a human
decision. Of the 252 R2-hosted sheets exactly one, this one, is on a non-canonical key, so the base
rule is a no-op everywhere else — which is precisely why nothing would have caught it. The check
that must **not** fire is pinned too: an R2 base with no `info.json` yet is the *first* mirror of a
sheet, whose tiles that very call tells the operator to build, and a guard blocking it would leave
the tool unable to onboard anything), `tests/bounds-probe.spec.ts` (which maps /explore asks Allmaps
about — only georeferenced ones without a bbox, which today is none of them: the predicate lives in
`core/geo/mapBounds.ts` because `useMapList` had its own copy that skipped the bbox rung entirely
and re-asked the annotation server about all 102 published sheets on every cold load),
`tests/series-load.spec.ts` (a whole survey in one layer: which of its sheets are fetched at all —
by bbox against the padded viewport, claimed before the await so a `moveend` inside the round trip
cannot double them — and how the ones that arrive are counted, `addGeoreferenceAnnotationByUrl`
resolving with `(string | Error)[]` so that a sheet which fails to parse comes back *inside* a
fulfilled promise and only a failed fetch rejects; count rejections alone and a half-drawn series
reports itself complete, which looks exactly like a survey with gaps in it),
`tests/layer-stack.spec.ts` (what the overlay stack holds and how a saved one is read back: that
nothing meaning "this sheet" — `?map=`, the Info rail, story playback, the year scrubber — ever
answers with a series row, whose synthetic `series:<key>` id resolves to no catalogue row and hands
out a share link that opens an empty page; plus the localStorage migration, since a survey was one
stack row per route until Sept 2026 and a reader who had L7014 on the map has two saved rows for one
survey — a ref that no longer parses takes the layer off the map with no error at all, and the fold
that puts the halves back together has to land on the *same* id the /explore list offers or the next
tap draws the survey twice), `tests/series-rows.spec.ts` (the /explore series list: that a raster
archive and the database series it is `halfOf` are one row and one layer, parts bottom-up so the
warped city sheets draw above the mosaic pixels they fill in for, and that its count and coverage
link say what the survey holds rather than what `maps` happens to know), `tests/ink.spec.ts`
(`inkAlpha` and the footprint fill it now backs — a wrong parse paints a footprint invisible),
`tests/wkb.spec.ts` (the EWKB point parser behind the home page's label layer — a byte-order slip
drops every label off West Africa instead of throwing), `tests/hero-fabric.spec.ts` (the home page
hero's frozen footprints and labels — generated data the hero draws with no runtime filter, so a bad
regeneration would paint the front page's third and fourth beats empty, or off West Africa, without
an error anywhere), `tests/theme.spec.ts` (both faces of the palette, parsed out of `tokens.css` and
checked for WCAG AA — a dark theme fails quietly, so the numbers are asserted rather than eyeballed)
and `tests/ocr-row-save.spec.ts` (one row's status write in the OCR review tables — the counts a
reviewer reads to decide a sheet is done, which the admin tab's hand-copy drove low by always
decrementing `pending`, plus the immutability the canvas controller depends on, since it keeps the
very row objects the sidebar hands it) `tests/map-slug.spec.ts` (how a sheet is addressed in a URL —
the browser's half of migration 088, which is all fallback: which of a row's identifiers becomes the
link when the row reached the UI without a slug, and which shapes an inbound `?map=` still resolves
in. Both failures are silent rather than loud — a label hit and a footprint submission arrive
carrying only `map_id`, so the uuid fallback is a working 301 and not dead code to be tidied away,
and a `?map=` shape that quietly stopped resolving opens /explore on an empty map with no error
anywhere. The three shapes are pinned together because they are three eras of the same link: the
slug /explore writes today, the uuid in every message sent before September 2026, and the
`allmaps_id` saved inside older stories), `tests/palette.spec.ts` (which pages the command palette
offers each role, and the gazetteer key a label resolves to — that key is computed twice, once in
Postgres and once in the client, and a mismatch is a 404; plus that every destination's `group` is
one /directory renders, since an unknown group would drop the row silently),
`tests/ocr-suspects.spec.ts` (the sheet's printed index used as an answer key against the numerals
on the map — a reference that is not a number, a number the index does not list, a number claimed
twice, plus the report the index gives on itself: the run it spans and the lines it is missing),
`tests/ocr-review-keys.spec.ts` (the review controller's keyboard: step, verdict, edit, turn),
`tests/screens.spec.ts` (whether `/screens` is telling the truth — every `ui/` component named
there, every card the inventory claims still in the file it names, and no retired element class back
from the dead; it reads the source rather than the page, because that is where the drift is),
`tests/table-sort.spec.ts` (the one sort behind every `.data-table` — blanks last in **both**
directions, `numeric` collation so `Rue 100` follows `Rue 11`, and that the value function runs once
per row rather than once per comparison, which is what the decorate-sort-undecorate is for),
`tests/ocr-jobs.spec.ts` (the four reading jobs of `?mode=text` — the property is that they
**partition** the loaded rows, because the tabs carry counts and that is a promise that clearing all
four clears the sheet; a row matching two jobs is checked twice and one matching none is never seen,
and neither looks like an error anywhere) and `tests/ocr-regions.spec.ts` (which part of the sheet a
row was read from — the axis /scan?mode=prepare reviews along. Placed by the row's **centre**, and a
printed block beats `main_map`, because the legend is printed inside the neatline and so "inside the
map" is true of it too; the same rule as `in_rects` in `ocr.py`, which is what decides whether the
tile pass writes the row at all. Pinned on one sheet's real `triage.regions`).
`tests/catalog-series.spec.ts` (the series band on /catalog and the drawer it opens — three things
that look right from the outside and were not: that the band is in the **server's HTML**, because
`/catalog/series` spent a day reachable only through a control inside an `ssr = false` tool and the
band is now the crawlable way in; that a band row keeps its `href` while opening a drawer, since
turning it into a `<button>` would have removed that path again with nothing on screen changing;
that the series filter matches `maps.collection` and not the label beside it, the same failure the
compact type `<select>` had when it wrote `map_type` where the filter read `type` and so did
nothing, visibly working; that "Open in map" carries a `#@lat,lng,zoomz` camera, because `?series=`
alone lands a country-sized layer on the reader's last camera and draws one corner of it; and that
the drawer paints **over** the sticky nav rather than under it) and `tests/screens.spec.ts`'s fourth
check (every `var(--token)` is one something declares — an undeclared custom property is not an
error anywhere, the declaration using it is silently dropped, and `gap: var(--space-sm)` against a
numeric scale had been rendering as no gap in three files since Sept 2026; the checker counts
Svelte's `style:--x={…}` as a declaration too, which is how two components legitimately set one from
the template). `tests/i18n.spec.ts` (the Vietnamese dictionary, which is keyed by the English source
string — the choice that makes a missing translation render as English rather than as
`home.hero.title`, and whose cost is that editing an English string silently orphans its Vietnamese
one. Four checks make that loud: every translated key is still called from somewhere, placeholders
match on both sides of a pair, no key carries the same placeholder twice, and a called key absent
from the dictionary is English on purpose rather than by accident. The extractor reads **both**
quote styles, because `.prettierrc` sets singleQuote and so Prettier flips a string to double quotes
exactly when its content holds an apostrophe — the strings most likely to be prose; a
single-quote-only regex was blind to them, reported them unused, and two sat translated-but-English
on production), `tests/series-sheets.spec.ts` (what a survey *contains*, read for display: the
status of a cell, the tally the coverage bar draws, the camera a scan-less cell opens over, and the
paged read behind the index. None of the four fails loudly — a wrong status is a plausible badge, a
dropped page of rows is a smaller denominator, and a bad camera is a map over the wrong ground. The
traps pinned by name: `source` is provenance, not possession, so a cell arriving as mosaic pixels
has no source URL and is still **held**; the three statuses must partition the survey, because the
bar draws them as three segments of one whole and the prose says "N of TOTAL"; a degenerate cell has
to ask for a zoom a basemap actually has rather than `Infinity`; and a survey that exactly fills a
page still has to stop), `tests/tile-size-segment.spec.ts` (the IIIF **size segment**, and the 404
that hid behind it — the largest single spec here, 29 checks over `worker/src/iiifKeys`.
`vips dzsave --layout iiif3` writes every derivative with an explicit `w,h`; IIIF's canonical "this
width, proportional height" is width-only, and width-only is what @allmaps/render and OpenLayers ask
for, so a width-only request missed R2 for *every* map in the bucket — maps with a `sources/` entry
hid it by proxying each tile to their origin, and maps without one, which is every self-hosted scan,
answered `{"error":"Source not found"}` and drew nothing. The cases are real keys read out of the
bucket, and the rounding is the part worth pinning: dzsave rounds **up**, not to nearest, and `.875`
rounds up under every rule, so the obvious edge tile cannot tell `ceil` from `round` — it did not,
for a year. Also pinned: a corner tile takes its height from the scale factor rather than from the
rounded width, whole-image regions collapse to `full`, `full/max` resolves to the widest derivative
the bucket really holds, a width wider than the image is clamped rather than promised, a
`/v<digits>` prefix becomes a key prefix without disturbing the rest, and anything the rewrite
cannot account for falls through to the proxy rather than being guessed at. Get any of it wrong and
nothing throws — the tile simply is not found again). Pure checks live here rather than in a second
framework because Playwright is already installed.
The four migration-088 checks in `tests/write.spec.ts` are the ones that matter, because the minting
rule lives in Postgres and nothing in the browser can be wrong about it: that a sheet alone gets its
bare name, that a second sheet of the same name pushes **both** onto the year rather than letting
the incumbent keep the bare slug by seniority, that the address the incumbent gave up still 301s to
it, that a true tie (same name, same year) falls back to a counter and only then, that a **rename
does not re-address** a sheet, and that a uuid and a retired slug both redirect while a name that
was never an address still 404s. The demotion is the half worth the test: get only the minting right
and the archive looks correct while every link to the older sheet has quietly moved. They also spell
`status` out on every fixture, because `maps.status` still defaults to `pending_georef` (migration
001) and migration 060 narrowed the check constraint without touching the default, so an insert that
omits it is rejected — which presents as a null row rather than as an error about status.

`tests/schemaCheck.ts` holds no tests of its own: it is the ~50-line JSON Schema subset walker
`tests/write.spec.ts` imports to check the shapes in `contracts/`, and it reports anything outside
that subset through `unsupportedKeywords` rather than passing it silently, so adding an unsupported
keyword to a contract fails loudly instead of going unchecked.

**Write paths** are covered separately by `npm run test:write` (`tests/write.spec.ts`, 33 tests)
against a **local** stack, never production: `npm run db:test` runs
`supabase start -x vector -x logflare` and seeds one staff user + one map via
`scripts/seed-test-db.mjs`. The suite throws unless `PUBLIC_SUPABASE_URL` is a loopback address, and
deletes every row it writes. Credentials come from `.env.test` (the CLI's published demo keys,
committed on purpose) which Vite loads for the `--mode test` dev server on port 5199. Server-route
auth is done by letting `@supabase/ssr` mint the session cookies, so chunking and encoding match the
app exactly. The same two commands run on every PR as the `write` job in `.github/workflows/ci.yml`,
which is the only place they are guaranteed to run: a dev machine without Docker cannot start the
stack, and migration 091 reached production that way — schema verified by hand, write path
unexercised until CI ran it.
Local ports are **54421** for the API and **54420** for the shadow DB, not the CLI defaults —
54321/54320 collide with another local project. `-x vector -x logflare` is needed under colima:
those containers bind-mount `/var/run/docker.sock`, which colima cannot provide.
