# Vietnam Map Archive

**[maparchive.vn](https://maparchive.vn)**

Historical maps of Vietnam, put back in place. We take scans of old city plans,
pin them to real coordinates so they line up with the city as it is now, and
read the names and shapes printed on them — so a street name from an 1882
survey becomes something you can search for, and a building traced off a 1959
sheet becomes a shape with a location.

Saigon in the French colonial period is where the work goes deepest; Hanoi, Huế
and the rest of the country are in the archive too. A SvelteKit application over
[Allmaps](https://allmaps.org), [OpenLayers](https://openlayers.org) and
Supabase, with an OCR and segmentation pipeline behind it, all of it
human-reviewed before anything is published.

Version history: **[maparchive.vn/changelog](https://maparchive.vn/changelog)**
in plain language, [`CHANGELOG.md`](CHANGELOG.md) with the engineering detail.
Currently **7.4**.

---

## What it does

- **Stack sheets over the modern city** — up to ten georeferenced maps at once, each with its own
  opacity, in three display modes: Stacked, Lens and Side-by-side.
- **Search inside the maps** — one search box over the catalogue, the gazetteer of attested place
  names, and the labels read off the sheets themselves. A label hit opens the map at the spot.
- **A page per place name** — every spelling a place was printed under, grouped, with the sheets
  that carry it.
- **Read the names off a sheet** — a prepare pass a person accepts, then Gemini Flash over IIIF
  tiles, then row-by-row human review. Nothing published is unreviewed.
- **Trace what is drawn on it** — buildings, roads and waterways, by hand or seeded from a
  fine-tuned SAM2, both ending in the same review queue.
- **Tell a story on the map** — author a route with stops and text, publish it, play it back at
  `/trip/<id>` (which is what printed QR codes point at).
- **Find more maps** — Scout crawls external IIIF collections (BnF Gallica, David Rumsey, Humazur,
  AGS Library…) and surfaces candidates for one-click import.

Everything above is a public read; contributing needs an account, and the
pipelines need staff.

## Quick start

```bash
npm install
npm run dev          # http://localhost:5173
```

The dev server talks to the real Supabase project, so a fresh clone gets the
live archive read-only. Writes need the local stack (below).

### Verification

```bash
npm run check        # type-check — the primary gate, kept at 0 errors / 0 warnings
npm run lint         # prettier --check . && eslint .
npm run test         # 354 tests: 18 read-only Playwright smokes + 336 pure checks
npm run db:test      # start a local Supabase stack and seed it
npm run test:write   # write-path smokes, local stack only — refuses a non-loopback URL
```

`npm run test` is mostly not a browser suite. The pure checks ride the Playwright
runner because it is already installed, and they pin the things that fail
*quietly*: the two copies of the tile-density signal (one TypeScript for the
browser, one Python for the worker) against identical bytes, the grid arithmetic
that decides where a street from a printed index lands, the palette against WCAG
AA in both themes, and the predicate that decides whether an OCR run is allowed
to spend money.

## How it fits together

Two map surfaces, and every tool is a mode of one of them:

- **`/explore`** — the geographic surface. One OpenLayers map owned by `MapShell`, warped historical
  sheets over a self-hosted vector basemap. Modes: `browse`, `studio`, `story`.
- **`/scan`** — the pixel surface. `ImageShell` over a IIIF canvas, for work in a scan's own
  coordinates. Modes: `prepare`, `text`, `shapes`, and the unlisted `inspect`. The names they
  shipped under — `triage`, `ocr`, `trace`, `review` — still resolve, because they are in bookmarks
  and in links already sent.

Modes are query parameters rather than routes on purpose: the map, the basemap
and the warped tiles stay loaded across a mode change instead of being torn down
and rebuilt.

Source is layered, and the rule is enforced by lint rather than by review:

```
core → data → map → features → routes
```

`core` is pure (no OpenLayers, no Supabase), `ui` is leaf primitives with no
domain imports, `$lib/server` is blocked from the client by SvelteKit itself, and
routes stay thin — load and wire, no business logic. A feature may reach another
feature only through a declared seam.

## Routes

| Route | What it is |
| --- | --- |
| `/` | The archive's front page: a slider between 1882 and today, featured sheets, and a live demo of the pipeline further down |
| `/catalog` | Faceted catalogue with full-text search; inline map editing for staff |
| `/catalog/<slug>` | One sheet's record page: the full tiled scan plus its title, date and places, server-rendered for crawlers and link previews. Addressed by name since migration 088; a uuid and every retired slug 301 here |
| `/catalog/place/[name]` | The gazetteer: one page per attested place name |
| `/catalog/series`, `/catalog/series/[key]`, `/catalog/series/[key]/[number]` | A survey as one thing: every series, one series' index, and a page for each sheet it contains — held or not |
| `/explore` | The map viewer — browse, studio, author stories. `?mode=annotate` is the name Studio shipped under and still resolves |
| `/scan` | The scan viewer — prepare, text, shapes (and the unlisted inspect) |
| `/trip/[id]` | Story playback |
| `/contribute` | How to help |
| `/contribute/georef` | Georeference a sheet in the Allmaps Editor |
| `/admin` | One staff console: `?tab=bulk` · `?tab=scout` · `?tab=status` |
| `/changelog` | Version history |
| `/directory` | Every page in the archive, in one list |
| `/screens` | Every design-system component, from fixtures — look here before building a second one |
| `/about`, `/blog`, `/blog/[slug]`, `/login`, `/profile` | Editorial and account pages |

Retired paths 301 in `src/hooks.server.ts`, including `/view`, `/studio`,
`/create`, `/image`, the old `/contribute/*` tools, `/admin/*`, and the
id-carrying `/map/<id>` and `/place/<name>`. Old links and printed references
still land somewhere real.

`vmabeta.pages.dev` 301s to `maparchive.vn` — one address for the site. Preview
deploys at `<hash>.vmabeta.pages.dev` are matched exactly and stay reachable.

## Accounts and roles

Sign-in is **Google OAuth** — no passwords to store or leak. An account is
created on first sign-in. Roles live in `profiles`: `user`, `mod`, `admin`. Draft
sheets are readable by any signed-in user and never anonymously; publishing
requires that a sheet is actually georeferenceable.

## Adding maps

Status is the only visibility model: `draft → public → featured`. Publishing a
sheet enqueues its own follow-up work — mirroring the annotation, tiling to R2 —
rather than leaving someone to remember it.

1. **From a IIIF manifest** (`/catalog`, staff) — paste a manifest URL from Gallica, the Internet
   Archive, Rumsey, EFEO, Humazur. The server parses it, derives the canonical image-service URL and
   the Allmaps ID, and probes the annotation server to see whether it is already georeferenced.
2. **In bulk** (`/admin?tab=bulk` + `scripts/bulk_upload_local.sh`) — for our own scans. Rows, tiles
   and thumbnail in one pass.
3. **From Scout** (`/admin?tab=scout`) — `scripts/scout_*.mjs` crawl external IIIF endpoints; a
   moderator records why a candidate is worth having and imports it.

Georeferencing happens in the Allmaps Editor, which has no webhook, so a
`sync_allmaps` job picks the finished work up. `/admin?tab=status` is where you
see what is stuck.

## Pipelines

Nothing runs on the web server. A route that starts pipeline work inserts a
`pipeline_jobs` row and returns 202; a worker claims it.

```bash
source work/ocr/.venv/bin/activate
python work/worker/vma_worker.py --worker $(hostname)   # poll forever
python work/worker/vma_worker.py --once                 # drain one job
```

The worker needs `VMA_API_URL` and `VMA_WORKER_KEY` and **no database
credentials** — claiming a job and reporting its results both go through
`/api/pipeline/*`. It takes whatever kinds the machine can run, so a worker left
running finishes what publishing enqueued.

- **OCR** — `work/ocr/`, its own venv. Gemini Flash over IIIF tiles into `ocr_extractions`, proposed
  and accepted at `/scan?mode=prepare`, then checked row by row at `/scan?mode=text`. Prompt changes
  are gated on a measured quality baseline, not on how the output looks:
  `work/ocr/EVAL-BASELINE.md`.
- **Segmentation** — `work/MapSAM2/`, a fine-tuned SAM2 fork. Runs on Colab, where the GPU is, using
  the same worker with `--kinds seg`. Polygons land in `footprint_submissions` and are validated at
  `/scan?mode=shapes`.

The two meet on one full-image pixel grid, which is what lets an OCR label be
joined to the shape it names.

## Environment

```
PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY   # the publishable key
SUPABASE_SERVICE_KEY                            # admin API routes only — the secret key
IA_S3_ACCESS_KEY, IA_S3_SECRET_KEY              # Internet Archive upload
VMA_API_URL, VMA_WORKER_KEY                     # worker machines only, never the web app
```

`.env.example` has the shape. Worker keys are minted with
`scripts/mint-worker-key.mjs`.

## Deployment

```bash
npm run deploy                                    # build + wrangler pages deploy
npx wrangler pages dev .svelte-kit/cloudflare     # local Cloudflare preview
```

Three rules, each of which cost a run of dead builds to learn — the full account
is in [`docs/deploy.md`](docs/deploy.md):

- **There is no root `wrangler.toml`, on purpose.** One that carries `pages_build_output_dir`
  replaces the dashboard's entire environment, secrets included. The R2 tile worker's own
  `worker/wrangler.toml` is separate and fine.
- **Environment lives in the Cloudflare dashboard**, per environment, and resolves at build time
  through `$env/static/private`. Every environment that builds needs all of it present.
- **Never import a Node builtin bare.** `import('path')` fails the Functions bundle and publishes
  nothing; use the `node:` prefix.

A blank page in the minute after a deploy is edge propagation, not a bug. Wait,
hard-reload, then debug.

## Documentation

Start with **[`CLAUDE.md`](CLAUDE.md)** — the map of the repo and its rules,
written for both people and coding agents. Then:

| Doc | What it is |
| --- | --- |
| `docs/ROADMAP.md` | The one tracker, open work only: the foundations pass, the OCR drain, Tracks C/E/F, burn-down |
| `docs/roadmap-record.md` | Frozen record of closed passes — what each one measured and what it turned up |
| `docs/lessons.md` | The rules paid for more than once, each with the failure that taught it |
| `docs/system-guidelines.md` | Layering rule, page structure, component patterns, known debt (§11) |
| `docs/db-guidelines.md` | Schema conventions every migration follows, table by table |
| `docs/api.md` | Every server route, its auth class, its contract |
| `docs/deploy.md` | Cloudflare Pages, and the ten dead builds behind each rule |
| `docs/design-system.md` | Tokens, the CSS file map, the page template |
| `docs/digitalize-guide.md` | Operator guide for `/scan?mode=prepare` — including the failure modes that return plausible output while dropping data |
| `docs/pipelines.md` | OCR + MapSAM2 commands, and what not to re-attempt |
| `docs/admin-tooling.md` | Map editing, bulk upload, Scout, the R2 worker |
| `docs/time-machine-plan.md`, `docs/platform-design.md` | The temporal-fabric plan; the shared-platform proposal |
| `docs/strategy.md`, `docs/theory.md`, `docs/user-guide.md` | Vision and outward-facing prose |
| `docs/journals/` | Dated research notes |
| `work/MapSAM2/TECHNICAL.md`, `work/ocr/EVAL-BASELINE.md` | Model notes; the measured OCR quality gate |
| `docs/archive/` | Frozen. Historical plans and the record of the August 2026 cleanup — not current |

## Stack

SvelteKit 2 with Svelte 5 in **legacy syntax** (`$:`, `export let`, stores — not
runes; the house style is in `src/lib/CLAUDE.md`). TypeScript. OpenLayers 10 as the only
map engine, with `@allmaps/openlayers` warping the historical sheets. Supabase
for Postgres, auth and storage, with status transitions written as Postgres
functions rather than in the API. Cloudflare Pages for the app, R2 for IIIF tiles
and for the ~348 MB PMTiles basemap that spans Hanoi to the Mekong — no
third-party tile service, no API key, no usage policy to outgrow. Fonts are
self-hosted too.

## Contributing

The archive is worth more with more sheets in it and more names read off them.
`/contribute` says what needs doing; georeferencing needs no code, and
`docs/digitalize-guide.md` is the operator guide for the reading pipeline.

## Licence

**Code: [MIT](LICENSE). The archive's own data:
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).**

The code is permissive because the people who should be reusing it — libraries,
universities, other archive projects — all have legal review, and a copyleft
licence is the one that review rejects. The data carries an attribution
requirement because it is the part that took two years: the georeferences, the
names read off the sheets and checked by hand, the traced footprints, the
gazetteer. Use it, commercially or not, modified or not; credit the Vietnam Map
Archive Project and link back.

**The scanned sheets are not ours to license.** Each one belongs to the
institution holding the paper, under that institution's terms, recorded per
sheet and shown on its catalogue page. Check there before reusing an image.

The basemap is built from OpenStreetMap data (© OpenStreetMap contributors,
ODbL); the satellite imagery is Esri's. [`NOTICE.md`](NOTICE.md) has all of it
in full.

Questions: **vietnamma.project@gmail.com**
