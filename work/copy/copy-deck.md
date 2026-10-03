# VMA copy deck

Every user-facing string in the app, grouped by surface. Generated 2026-09-12 for a copy
rewrite. `{N}` / `{name}` mark interpolated values. `[attr]`-style notes mark text that is a
tooltip, `aria-label`, `alt` or `placeholder` rather than visible prose.

Raw machine extract (with file paths, includes noise): see `work/copy/copy-raw.txt`.

---

# 1 · Editorial pages

## `/` Home

```
[title] Vietnam Map Archive — historical maps of Vietnam, open and georeferenced

[hero alt] The 1882 cadastral survey of Saigon laid over the modern city, fading between the two
[hero slider aria] How much of the 1882 sheet to show
[credit] Imagery © Esri, Maxar, Earthstar Geographics · Sheet: Plan Cadastral de Saïgon, 1882

Vietnam
Map Archive
{N} sheets of Saigon, Huế and Hanoi — 1791 to 1968 — laid back over the ground they drew.
Today / 1882

The Catalog
A featured sheet, whole. Pick another below, then open it in the viewer to lay it over
today's city, or inspect the high-resolution IIIF scan up close. Each record links back to
the library or collection that holds it.
[tabs aria] Which sheets
Opening the archive…
No favorites yet.
Heart any map and it lands here, on every device you sign in from.
Nothing here yet.
No maps match this view — try another tab or the catalog.
Browse the catalog
Inspect a scan
Open the map

Tools · Beta
Build something on top of the archive — a scrollytelling story across historical layers,
or your own points, lines and shapes on a sheet.
  Story Builder — Walk readers through a place, one layer at a time
  Studio — Draw on any map and save it as a set

Contribute
The archive is built by volunteers, and there are not many of us yet. Your name stays on
what you submit, and all of it is meant to be released openly.
  Prepare a sheet — Crop a neatline, check the toponyms the pipeline pulled
  Trace buildings — Outline buildings, roads and waterways
  Georeference — Pin a scan to real coordinates in the Allmaps Editor

About the project
Volunteers put those sheets on the ground they drew. Reading the names off them and tracing
what they show is where the work goes next: the aim is to get the buildings and street names
out of Vietnam's colonial-era maps and into open data, with a person checking the machine's
work. The 1882 cadastral survey of Saigon is where it starts, and where most of the work so
far sits. Everything published will be CC-BY / ODbL.
What's actually done →

Where things stand
The OCR pass has read {N} distinct place names off six sheets, {N} of which have been checked
by a person — so that queue has barely started.
{N} building outlines have been traced on the 1882 cadastral survey, and none are approved
yet. The last written update was in May.
All updates →

What will you find?
Most people come for one street and stay for the city. {N} sheets, 1791 to 1968.
```

## `/` Home — "How this works" demo section

```
How this works
A scan of an 1882 survey, pinned to real coordinates, laid back over the ground it drew —
then the plots traced off it and the names read off it. Drag the slider to move between the
two cities.
[alt] The 1882 cadastral survey of Saigon laid over the modern city around the Charner canal
Today / 1882
Open this sheet in the viewer
```

## `/about`

```
[title] About — Vietnam Map Archive
Old maps of Vietnam,
put back in place.

Where this stands
Counted from the database when this page loaded.
  {N} sheets placed on the map — {year}, to {year}
  {N} more georeferenced but not published, so nobody outside the project sees them yet
  {N} place names read off the sheets by the OCR pass — {N} checked by a person
  {N} building and street shapes traced by hand — {N} approved, so there is no dataset to
  download yet

What you can do today
Four things work, and they work in an ordinary browser. No account is needed for the first one.
  Browse the sheets and lay any of them over the modern city in the viewer.
  Trace a building — the same skill as tracing on OpenStreetMap.
  Check what the OCR read, one label at a time.
  Place a sheet that has no coordinates yet, in Allmaps Editor.

What is not built
The plan is larger than the archive. Written out so nobody has to guess which parts exist.
  No published dataset. Nothing traced has been reviewed and released. That is the next thing,
  and it needs people rather than code.
  No building histories. Who built a place, who owned it, what replaced it — there is no
  database for any of that, only a design.
  No 3D. Heights and roof shapes would come from two rare painted views of the city and a
  published reconstruction method. Nothing has been run.
  Barely any contributors. Single figures, and the review queues are nearly empty because
  almost nobody has filled them.
  No funding. No institution behind it, no grant won. The work is unpaid.

How it is kept
Data is openly licensed (CC-BY / ODbL) and the code is public. Every sheet credits the
institution holding the scan — the Bibliothèque nationale de France, Université Côte d'Azur,
UT Austin, the Library of Congress and others — and links back to their record. None of that
is a formal partnership. Any city with a map archive can fork the whole thing and run it
locally; that is the point of building it this way.

Get in touch
Tracing, checking labels, reading French or older Vietnamese romanization, or a grant that
might fit — all welcome, and a slow reply is likelier than a fast one. Saigoneer wrote about
the project in January 2026. The blog has the working notes, including the posts that turned
out to be wrong.
vietnamma.project@gmail.com
```

## `/contribute`

```
[title] Contribute — Vietnam Map Archive
Build the archive
together.

Prepare a sheet
Crop a map's neatline, set tile priorities, and check the place names the OCR pass read off
the sheet. Around 950 distinct names are waiting; 43 have been checked.
  Start preparing

Trace buildings
Outline buildings, roads, and waterways on a georeferenced map. 46 shapes have been traced so
far, all on the 1882 cadastral survey.
  Open the tracer

Georeference a map
Place ground control points in the Allmaps Editor to anchor a historical map to real-world
coordinates.
  See what needs georef

Review footprints
Approve or reject building traces from volunteers and the SAM2 pipeline. Nothing is approved
yet. Mods and admins only.
  Open the review queue

Catalog metadata
Complete bibliographic records: titles, shelfmarks, creators, dates, rights, and physical
descriptions.
  Edit the catalog
```

## `/contribute/georef`

```
[title] Georeference a map — Vietnam Map Archive
← Contribute
Pin a map
to the world.

How it works
  Pick a map below and hit Open in Allmaps.
  Drop at least 3 ground control points — match a spot on the map to the same spot on the
  modern world.
  Save in Allmaps. Nothing to send back: the archive checks Allmaps for finished maps and
  marks them georeferenced by itself.

Loading maps…
Needs georeferencing
Every map is georeferenced. Check back later — new ones land every few weeks.
Open in Allmaps
[badge] draft
[tooltip] R2-only source and no manifest: the editor has nothing to open
no source

Fix an existing georeference
Reopens the map's control points in Allmaps so you correct them rather than start over.
Same button as the share page, without having to know the map's id.
[placeholder] Find by name or year…
[aria] Find a georeferenced map
No georeferenced map matches.
Fix in Allmaps
```

## `/catalog`

```
[title] Catalog — Vietnam Map Archive
The Archive.
Submit a map
[placeholder] Search by title, creator, year, or description…
[aria] Clear
Show maps of / All areas
Type / All types
{N} in archive · {N} in scout queue
Include scout queue
Nothing matches.
Try another keyword, or clear a filter and start over.
Group by: None · Year · Area · Type · Collection · Status
[col] Map · Image
[aria] Thumbnail / Available on map / Static image only
{N} map(s)
No maps match those filters.
```

## `/catalog/[id]` (share page)

```
{name} — Vietnam Map Archive
Browse the archive
View the original at {institution}

Trace this sheet in OpenHistoricalMap
The sheet is served as warped map tiles, so it can sit under the OpenHistoricalMap editor
while you draw. The button opens the editor with it already set as the background; if the
editor does not pick it up, add it by hand under Background → Custom with this URL.
  Open in OpenHistoricalMap

Fix georeference in Allmaps
No IIIF manifest or original image source on this map, so the Allmaps Editor has nothing to
open. Add one in the catalog edit modal first.
This map renders from our own mirrored annotation, so an edit in Allmaps will not show here
until someone runs Fetch latest from Allmaps in the catalog edit modal.

Places named on this sheet
Read by optical character recognition from the sheet itself, then corrected by hand where a
reviewer has reached it.
```

## `/catalog/place/[name]` (gazetteer)

```
{name} — Vietnam Map Archive
{name} — everything the archive holds about one place name.
A landing page, not a tool: the sheets that name it, the span of years it is attested, the
other spellings it was written with, and one link into /explore at the spot.
attested · {N} map(s) · {N} mention(s)
Also written
On these maps
Position is warped through each sheet's own georeference, whose control points sit about {N} m
from where they claim to be on the least accurate of these maps.
Treat the spot as a neighbourhood, not a doorstep.
Sheet details
```

## `/blog`

```
[title] Blog — Vietnam Map Archive
[hero] Updates from the archive
Latest
Earlier posts

No newsletter
Everything's here. Bookmark this page, or check About for live project progress. If you'd
rather be pinged when something big lands, email vietnamma.project@gmail.com and we'll add
you to a short, infrequent announcement list.
```

## `/blog/[slug]`

```
{title} — Vietnam Map Archive
← All posts
Since this was written

Want to help?
Every traced building, tagged photo, and cited source is permanently attributed in the archive.
  Start contributing
  Read the project overview

About the project
Vietnam Map Archive puts historical maps of Vietnam on real coordinates and reads what is
printed on them. Saigon in the colonial period is where the deep work starts.
  Project overview

More posts

Get in touch
Funder, researcher, volunteer, or just curious?
vietnamma.project@gmail.com
```

## Blog post titles + "Since this was written" corrections

```
The Gate That Could Not Read Vietnamese, and the One Printed on the Sheet Itself
Sixteen Pages, One Palette, and an OCR Change That Failed Its Own Test
Searching Inside the Sheets, and Asking the Model What a Sheet Is Made Of
Our Own Basemap, After Two Tile Servers Said No
3,194 Lines Deleted, a Job Queue, and a Rule the Linter Enforces
Nine Faults in the OCR Pipeline, and a Gate So the Next Change Is Measured
A Front Door for the Maps, and a URL for a Printed QR Code
Rebuilding the Map Viewer Around a Single Concept: the Layer Stack
Scouting 3,373 Maps: Building a Discovery Pipeline for Vietnam Cartography
Ingested: 62 Tonkin Topographic Sheets (1903–1927)
Platform Notes: Universal IIIF, Gemini OCR, and the MapShell Refactor
Platform Notes: Retiring a Pipeline and Rebuilding the Data Foundation
Buildings as Ground Control: A New Method for Vectorizing Colonial Maps
Dissecting Space: The Six-Layer Method Behind the Archive
How GCP Propagation Georeferences a Whole Map Series
```

```
— corrections —

September 2026 — the route in this post, /view, is now /explore: a later merge folded
twenty-three pages into sixteen and turned modes into query params. The layer stack itself is
unchanged and is what /explore still renders.

September 2026 — the queue holds 985 candidates today, not 3,373: dedup and rejection pruned
it. The 758 high-score bucket was never curated in an afternoon or otherwise. What actually
came out of the scout is one batch of 62 Tonkin sheets, and those are still unpublished
drafts. The page moved from /admin/scout to /admin?tab=scout.

September 2026 — all 62 sheets are georeferenced now, but every one is still draft, so none of
them is visible to a reader who is not signed in. Nothing in this batch has been published,
OCR-ed or traced, and the toponym layer for northern Vietnam described at the end of this post
does not exist.

September 2026 — three corrections. The OCR pass is called "Project Scout" here; a month later
we shipped an unrelated map-discovery tool also called Scout, and the name in this post is the
confusing one. The tile-speed figure was an impression from clicking around, not a benchmark.
And the Label tool listed under MapShell was retired in the route merge.

September 2026 — most of this did not ship as described. The colour-profile SAM pipeline was
deleted from the repository; footprint segmentation now runs on a fine-tuned SAM2 fork, on
Colab. The building-to-building matching — Hu moments, RANSAC, an automatic georeference of the
1898 sheet — was never built, and there is no 1880–1900 change dataset. The 91 city blocks
below came from one 1,200 px crop and remain the whole of the result. Every one of the 46
footprints in the archive today was traced by hand.

September 2026 — no tier system was ever built: there are no Photo Hunter or Cartographer
roles, and no photogrammetry mission has run on any of the five landmarks. The 500+ L7014
sheets are georeferenced and served from Internet Archive, but were never ingested into this
catalog, which holds 39 published sheets. The knowledge graph is still a design document. This
was also the only monthly digest.

September 2026 — the four contribution tiers in this post do not exist and no data or model
weights have been published to Hugging Face. The L5 knowledge graph has no schema and no API in
the codebase; "CRUD API in development" was optimistic. The height-uncertainty figures
(±3 m → ±1.5 m) are what we expected from reading the method, not anything measured. L1
vectorization now means a fine-tuned SAM2 fork run on Colab, and it has produced no reviewed
footprints yet.

September 2026 — this describes the L7014 batch, which is served from Internet Archive and was
never ingested into this catalog: none of the 39 published sheets here is an L7014 sheet. The
under-1% error figure compares propagated annotations against our own seed georeferences, not
against independent ground truth, so it measures internal consistency rather than accuracy. The
pipeline code was deleted in April 2026.

September 2026 — the Photo Hunter tier was never built, and there is still no way to attach a
photograph or a memory to a place. What a newcomer can actually do today: trace footprints at
/scan?mode=trace, check what the OCR read at /scan?mode=triage, or place a sheet at
/contribute/georef.
```

## `/changelog`

```
[title] Version history — Vietnam Map Archive
Every version,
and what it changed.
Running now
Only two versions here carry a screenshot. The ones between them were never deployed anywhere
they could be photographed, and their code no longer runs against the archive as it is now — a
reconstruction would be a picture of something that never shipped.

Before the rewrite
The first version was one hand-written page of scans, published in April 2025 and still
online. Those versions live in their own repository; the numbering here continues from them.

[captions]
The front page with the header slider pushed to 1882. The same gesture the whole archive is
about, working before any JavaScript has run.
The 2025 site, still published. The row of years along the foot is the version's one new idea,
and the reason it earned a number.
```

## `/directory`

```
[title] All pages — Vietnam Map Archive
All the pages,
one list.
{N} not listed because this account cannot open {them}.
Sign in to see the contribution tools.
```

## `/login`

```
[title] Sign in — Vietnam Map Archive
Sign in
Continue with Google
Signing in lets you save favorites and contribute to the archive. Everything you add is
released as open data under CC-BY.
```

## `/profile`

```
[title] Your profile — Vietnam Map Archive
Your profile.
Sign out

Your contributions
Counting…
Pins placed
Buildings traced

Staff tools
Pages only staff can open. Start at System status — it says what the archive holds and what
is currently blocked.
  System status · Design system · Review queue · Scout review · Bulk upload

Preferences
Language
Switch between English and Tiếng Việt — translation is beta
```

---

# 2 · Global chrome

## NavBar

```
VMA
Catalog · About · Blog
Tools ▾
  Where to start: Map viewer · Inspect a scan · Story Builder · Studio · Contribute ·
  Georeference · Prepare a sheet · Check the text · Draw shapes · Review queue
  Staff: Review queue · Admin console · Design system
  Everything: All pages →
Search
Open the map
Sign in
Your profile
[aria] Open menu / Close menu / Navigation / Tools / Your profile
```

## Footer

```
Home · Catalog · Map viewer · Inspect a scan · Contribute · About · Blog ·
Version history · All pages · GitHub
Built openly with Allmaps, SvelteKit.
vietnamma.project@gmail.com
```

## Command palette

```
[aria] Search the archive / Search results / Close search
[placeholder] Search maps, places and pages…
On maps
OCR'd labels, which open /explore at the spot
esc · ↓ move · ↵ open · ⌘K anywhere
On the map · Place
```

## Palette / directory destinations

```
Catalog — Every map, faceted
Map viewer — Overlay historical maps on the city
Scan inspector — Read one sheet at full resolution
Story Builder — Author a guided walk
Studio — Annotate and animate
Contribute — The three jobs, and which suits you
Georeference a map — Pin a scan to the world
Prepare a sheet — Set the crop, then queue the reading
Check the text — Names, index, numbers
Draw shapes — Buildings, roads, and what the model drew
Review queue — Approve the shapes waiting
About — What the project is
Blog — Research and build notes
Version history — What changed, version by version
All pages — Every page in the archive, in one list
Your profile — Account, favourites, staff pages
System status — What the archive holds, what is stuck
Story queue — Approve what contributors submitted
Bulk upload — Add sheets in a batch
Scout — Candidate maps from other collections
Design system — Every token and component
```

## Period facets

```
Pre-colonial (≤1858)
Early colonial (1859–1887)
French Indochina (1888–1939)
War years (1940–1954)
Republic era (1955–1975)
Reunification+ (1976–)
```

## Basemap names / misc

```
Streets · Esri Satellite · Custom URL · None
Quần đảo Hoàng Sa (Việt Nam)
Quần đảo Trường Sa (Việt Nam)
Geolocation not supported
Loading IIIF image… / No image selected
Nothing matches.
Continue with Google
```

---

# 3 · `/explore` (map viewer)

## Privacy / first-run notice

```
Explore the archive
Browse VMA's historical maps of Vietnam — Saigon, Hanoi, Huế, Cambodia and beyond. Pick how
you want to start.
  Use my location — Centre on where I'm standing and surface the maps that cover it.
  Show all maps — Skip GPS — browse the whole archive and pick anywhere on Earth.

What happens when I share my location?
  What: approximate device location, only while this tab is open.
  Where: stays on your device — never sent to a server.
  Stop anytime: switch off GPS in the Controls panel, or revoke the permission in your browser.
Remember my choice on this device
```

## Left rail (archive)

```
Explore
[aria] Archive panes / Collapse panel / Hide panel
Browse the archive
{N} map(s) cover this spot
No archival map here
Tap a row to add it as a layer · tap again to remove.
← Back to maps at this location
Browse the full archive →
All · Picked {N}
```

## Filters

```
[placeholder] Search maps…
[aria] Clear / Filter by area / Filter by map type / Filter by period
Filters · {N}
All areas · All types · All periods
Reset filters
```

## Layer stack

```
[aria] Move layer up / Move up / Move layer down / Move down / Remove layer / Remove / Opacity
My layers
Tap a name to zoom · drag for opacity · eye hides a layer
Nothing stacked yet. Open Browse and tap + on a map to add it.
No stacked map matches those filters.
Top / Bottom
```

## Right rail (this sheet)

```
This sheet
[aria] Sheet panes / Collapse panel / Hide panel
Info · Legend · Control
Add a map layer to see its details.
Holding library
Add a map layer to read its legend.
Reading the legend…
This sheet has no numbered legend.
[aria] Show numbered legend references on the map
My location
```

## Controls panel

```
Display — Stacked / Lens / Side-by-side
Base — Maps / Satellite / None
URL
[aria] Lens size / Clear
Use my location
```

## Sheet actions + empty states

```
⬡ Traced (Traced footprints) · Scan · Studio · Share
No archival map of this exact spot — yet.
VMA's archive doesn't yet hold a map covering your point. Browse the full archive for maps
elsewhere, or suggest a source we should add.
Suggest a map here
```

## Press panel

```
[aria] Press clippings / Close
In the press
Searching the newspapers…
Nothing found — {query}.
```

---

# 4 · Studio and Stories

## Studio

```
My Annotations.
{N} feature(s) · Map: {name} / No map selected
[aria] Sign in to annotate / Back to library / Back to my projects / Editor mode / Collapse
panel / Hide editor / Project title
Annotate · Animate

Draw on the map:
  Click Point, Line, or Polygon
  Then click on the map to draw
  Or Import a GeoJSON file
[aria] Annotations / Import features from OpenStreetMap via Overpass
Import

Name · Details · Colour
Select an annotation to edit its name, notes, and colour.
[placeholder] Annotation name / Optional notes
```

## Studio — animation panel

```
Make a flythrough.
Set up the map — pick an overlay, set its opacity, frame the camera — then press + Keyframe
below.
Add at least two keyframes (different overlays or viewports), then press ▶ Play to glide
between them.
hold
[aria] Camera transition into this keyframe (ms) / Hold after arriving (ms) /
Overlay transition: cut = instant, fade = tween opacity / Move up / Move down /
Apply this keyframe instantly / Delete keyframe
```

## Studio — Overpass import

```
Import from OpenStreetMap
Layer
Overpass QL (statement body only)
Bbox is applied globally — write only the filter statements.
Bbox (S, W → N, E)
Or search a place
[placeholder] e.g. District 1, Hue, Cholon…
Preview on map: {N} feature(s)
Drag the rectangle corners to resize · drag inside to move
Cancel · Use this bbox
```

## Story Builder

```
Your stories.
[aria] Sign in to build a story / Walk this story on mobile / Back to library /
Back to my stories / Points / Deselect point / Story title / Saves as you type
Editing is desktop-only.
Tap a story here to play it. To author or edit one, open VMA on a laptop.
{N} point(s) · Walk
Story editor
Pick a point in the list to edit its title, description, challenge, and pinned layer.
Saved

Points · {N}
Tap Place point, then click the map to add your first stop.
New points pin to {layer}
No historical layer active — point uses base map.
[aria] Move up / Move down / Remove point

Title
Description (shown on arrival)
Hint (shown before arrival)
Challenge
Position
Pinned historical layer
Add a historical overlay from the left sidebar to pin one here.
— none — · (not loaded)
[placeholder] Point title / What should the reader notice here? / Optional hint

Question · Answer · Trigger radius (meters)
[placeholder] What is this building? / Expected answer
```

## Story seed content

```
Notre-Dame Cathedral — Neo-Romanesque cathedral built 1877–1880 with bricks shipped from
Marseille.
Central Post Office — Opened 1891 in the French Indochina style next to the cathedral.
Independence Palace — Rebuilt 1962–1966 on the site of the former Norodom Palace.
Saigon Opera House — Beaux-Arts theatre opened 1900 on the former Rue Catinat.
Bến Thành Market — Iconic four-gate covered market relocated here in 1914.
```

## `/trip/[id]` playback

```
{title} — Vietnam Map Archive
Loading your trip…
Trip unavailable

Walking trip
{N} stops · ~{N} min · On foot
  Allow location so we can guide you between stops.
  Some stops have small questions — look around to find them.
  Old maps fade in as you walk through them.

Itinerary · All stops · now
[aria] Trip player / Your answer
Walk to this stop / You're here
Finding GPS…
Look around:
Question · Submit
Not quite — try again.
Correct!
The answer was "{answer}".
Reach — Walk within {N} m and you'll check in automatically.
Visited. · ✓ Visited
← Prev · Mark visited · Next →
Trip complete

You made it.
{N} stops · {N} walked · {N} minutes
Save your trip
Log in to keep this on your profile.
Share
```

```
[preview variant]
Story complete
You visited all points in this story.
Hint:
Walk within {N} m of this point. Tap Mark visited to simulate arrival in preview.
```

---

# 5 · `/scan` (sheet tools)

## Shared rail

```
Scan
[aria] Map / Browse the archive / My layers / Scan modes / Collapse panel / Hide panel /
Show panel / Show editor / Toggle panel
Select a map to begin digitalization.
Couldn't load the map list: {error}
Browse catalog → / Browse the catalog →
Loading map…
Pick a map to inspect its scan.
Open on map · Studio
```

## Prepare — step 1 Layout

```
1 Layout
What the sheet is made of. A worker asks the model once, at low resolution; the answer lands
here for you to correct. Dashed edges are its proposal, solid ones yours.
Layout job — nothing happens until a worker claims it.
Layout job failed: {error}
Add region · Add one by hand
[aria] model confidence / Remove this region
Categories: sheet · main map · Title block · legend · name list · inset · scale bar ·
north arrow · stamp
```

## Prepare — step 2 Crop

```
2 Crop
Full image
This crop is the layout pass's main map region, adopted automatically — nobody drew it. Check
it against the sheet.
Coordinates
{w} × {h} px sheet. Paste x,y,w,h from another tool.
Neatline exceeds image bounds.
Drag the amber rectangle on the canvas to adjust.
```

## Prepare — step 3 Tiles

```
3 Tiles
Suggest
Size · overlap
Size / Overlap
Priority — click tiles on the map
  Normal — full res
  Low-res — {N} px · title, legend
  Skip — empty / border
```

## Prepare — step 4 Run OCR

```
4 Run OCR
Run options
Run ID [auto-generated] · Min confidence
Queued as job {id}. A worker has to claim it:
  python work/worker/vma_worker.py --kinds ocr
Queueing… / Run OCR
Queues a job — a worker runs it and the stage flips to ocr_done.
Existing runs
{N} items
```

## Prepare — save / accept

```
Accepted {date} — the batch script will take this sheet.
Proposed by the layout pass. Nothing is queued until you accept it.
Not saved. This triage lives only in this browser.
Saving… · Accept triage · Update saved triage · Save triage
```

## Prepare — canvas bottom bar

```
Drag the amber box · click a tile to set its priority
Drag a rectangle to add a bbox · Esc to cancel
Click a bbox to edit · j/k next · v validate
Add bbox
[aria] Rotate left 90° (Shift+R) · [ and ] turn 5° / Rotate right 90° (R) · [ and ] turn 5° /
Back to upright (0)
```

## Text mode — reading jobs

```
Names — Names printed on the map — streets, places, water, institutions.
Index — the sheet's own printed legend and name list
Numbers — Numerals on the map, against the index that explains them.
Other — Title block, scale bar, stamp — and anything on the map that is none of the above.
[aria] Reading jobs
```

## Text mode — filter bar / rows

```
[placeholder] Filter text…
[aria] Filter by status / Filter by run / Double-click to zoom / Text… / Extraction text /
Category / saving… / Label text…
Conf ≥ {N}%
suspect
[tooltip] Numerals the sheet's printed legend contradicts: not a number, a number the index
does not list, or one claimed twice
Categories · All
Status · Text · Cell · Cat · Conf · Verdict
Pending ({N}) · Validated ({N}) · Rejected ({N}) · All statuses · All runs · All
· missing · repeated
Loading…
Showing {N} of {N} — show more
No extractions for this map. Push a run to DB first:
  ocr.py batch --map-id … --db
No rows match the filters — try the confidence floor or the categories.
Nothing on this sheet for {job}.
Click row to select · double-click to zoom · j / k next/prev · v validate · x reject ·
e edit text · turn label · r turn sheet
Revert the last 15 minutes of validations? Click ⟲ again to confirm.
Undo
[aria] Save all pending text/category edits
[aria] Validate every pending row the filters currently show. Undo with ⟲ within 15 minutes.
[aria] Reject every pending row the filters currently show — the printed index read as map
marks, a run that landed in the wrong place. Undo from the notice.
[aria] Reload / Deselect
[aria] Drag the round handle to turn the label · , and . nudge 1° · click to reset
```

## Shapes — Draw

```
{name} — Shapes
[aria] Shapes / Shape tabs
Polygon — for buildings and closed shapes
Line — for roads and waterways
Select and edit a shape
Polygon · Line · Edit
Drawing · Enter or double-click to finish · Ctrl+Z undo · Esc cancel
Click to start drawing a {shape}
Click a shape to select · drag vertices to edit · Delete to remove
[placeholder] Filter by name… / Name…
[aria] Filter by type / Shape name / Feature type / Category / Confirm delete / Cancel /
Remove shape / Delete
All types · — Type — · — Category — · Other
No shapes match the current filter.
```

## Shapes — Segment

```
Stage
Ready. Run the Colab command below, then come back here.
Finish OCR review first. The segmentation step needs validated toponyms to run.
Command config
Checkpoint · MapSAM2 dir · Encoder
  vit_t (tiny) · vit_s (small) · vit_b (base) · vit_l (large)
Text mask · Watershed
Run: · Started: · Finished:
[aria] Colab command
```

## Shapes — Validate

```
Progress
All done for this map.
Needs review · Selected · Drag to edit
Orange = needs review · yellow = selected (and zoomed to) · green vertices = the Modify
handles, which are only attached to the selected polygon.
```

---

# 6 · Admin

## `/admin?tab=status`

```
System status · VMA Admin
System status in plain words.
What the archive actually holds right now, what is stuck, and what would unstick it.
Checking access… / Admin access required.
Last checked {time}
Could not load: {error}
Reading the archive…
Biggest blocker · Next
What failed
The most recent failures, newest first. The message is whatever the worker reported.
Map
[status tones] Good — Working as intended. / Warning — Partly done; needs attention but not
blocked. / Blocked — Nothing works here yet. / Neutral — A count with no judgement attached.
```

## `/admin?tab=bulk`

```
Bulk Upload — Admin
← Catalog
Bulk Map Upload
Insert many maps at once. Tiling still runs locally — this page gives you the script.
Checking access… / Admin only.
1. Defaults — Default collection
2. Maps
Paste from a spreadsheet (one row per line, tab- or comma-separated: path, name, year,
collection, map_type, location) — or just paste a list of paths and we'll auto-parse
name/year from the filename.
Local path · Name · Year · Collection · Map type · Location · Status
+ Add row · Clear all · Creating… / Create {N} map row(s)
3. Run this locally to tile + upload
Save as tile_batch.sh in your repo root, chmod +x, then run. After tiling, click the backfill
button below to set IIIF URLs and thumbnails on the new map rows.
Copy script · Backfill thumbnails (after tiling)
[aria] Remove row
```

## `/admin?tab=scout`

```
Scout · VMA Admin
Scout Review
External map candidates discovered via Gallica, Humazur, Rumsey, LoC and the AGS Library.
Approve → bulk-ingest as draft maps.
Keyboard: j / k move · a approve · r reject · x select · u revert
Checking access… / Admin access required.
Status: Pending · Approved · Rejected · Ingested · All
Source — all — · Category · Search title · Reset
[placeholder] Saigon, 1882… / reason for the batch (optional)… / or type a reason…
— why? (optional) · Confirm · Cancel
{N} selected · Select page · Clear
Ingest selected as draft maps
Loading… / No candidates match these filters.
Next →
no image
[tooltip] No IIIF manifest or image URL — ingest will refuse it
```

## `/admin?tab=stories`

```
Loading stories…
Queue's clear — no stories waiting on review.
{N} point(s) · updated {date}
```

## Map edit modal — header

```
Edit Map
Status: Draft · Public · Featured
⚠ Help needed · Priority
[aria] Essential fields filled / Close / Flag for community help /
Higher = surfaced first in tools / Map fields
```

## Map edit — About tab

```
Title & date
Display name * · Original title as printed on the map
Year (numeric, single year) · Date range or fuzzy
Authorship — Creator (cartographer / surveyor) · Publisher
What it shows — Location (city / region) · Map type · Coverage (geographic extent) ·
Subjects (keywords, comma-separated) · Description · Summary
Map types: — unknown — · Cadastral · Topographic · City Plan · Panorama · Other
Physical & language — Physical description (size, medium) · Language
Custom fields (e.g. sheet_number) · Field name · Value · + Add field
[placeholders] Full original map title · e.g. 1890 · e.g. 1882 or 1882–1885 ·
Cartographer or author · e.g. Service Géographique de l'Indochine · e.g. Saigon, Hanoi, Hue ·
e.g. Saigon and surroundings · cadastre, urban planning, colonial ·
Brief description of what this map shows, who made it, and why it matters. ·
e.g. 67 × 57 cm, colour lithograph · e.g. français, English
```

## Map edit — Source tab

```
Provenance
Source type (holding institution): — unknown — · BnF Gallica · Internet Archive · EFEO ·
Gallica · David Rumsey · Self-hosted · Other
Holding institution (where the original lives)
Collection (sub-collection at the holder)
Identifier (shelfmark / call number)
IA identifier (Internet Archive item)
Source URL (canonical record at the institution)
Rights (license / copyright)
[placeholders] e.g. Bibliothèque nationale de France · e.g. Département Cartes et plans ·
e.g. GE D-10312 · e.g. vma-map-1882-saigon · https://gallica.bnf.fr/ark:… ·
e.g. Public domain, CC BY-SA 4.0
```

## Map edit — Hosting tab

```
Auto-fill metadata from manifest
Fetches the map's IIIF manifest and fills empty Metadata fields (title, creator, date,
shelfmark, rights, language, source URL, holding institution). Existing values are never
overwritten.
Set the IIIF manifest URL on this map first.

Image Sources
⚠ maps.iiif_image points to R2 but no R2 source row exists — click "Mirror to R2" below to
re-sync.
Loading sources… · ★ PRIMARY · No IIIF sources yet.
Manifest URL · IIIF Image Service URL * · Label · Source Type (bnf · efeo · rumsey · other)

R2 / Tiling — Mirrored / Not mirrored
Clones the Allmaps annotation to Supabase Storage and sets iiif.maparchive.vn as the primary
tile source. After clicking, run the printed CLI command to upload tiles.
Annotation saved. Run this to upload tiles:
Source:

Georeference
Allmaps ID * (16-char hex, auto-derived from IIIF URL)
Annotation URL override — optional, used when self-hosting via R2
View Annotation ↗ · Open in Allmaps Editor ↗
[tooltip] Re-read the annotation from allmaps.org after editing the georeference there. The
current copy is kept as history.

Image Upload (Internet Archive) · Thumbnail:
Ground Control Points
Place GCPs to refine the georeferencing for this self-hosted map.
```

## Map edit — Pipeline tab

```
Workflow stage
Quick flags for downstream tooling. Catalog visibility (status, featured, public) lives in the
header bar above.
Georef done (available in Label Studio)
Legend done (pin legend validated)

Label Studio Config
Pin Legend Mode: Simple (comma-separated) · Transcription list (Number | Name)
Trace Categories (comma-separated) — Used to classify traced footprints in Label Studio

OCR Pipeline
Loading extraction counts… · No extractions stored yet for this map. · {N} items
Min confidence — 0–1; threshold for pin insertion
Run ID (optional)
Neatline crop (x,y,w,h) — Paste coords from neatline tool. Crops the tile grid to map content.
Target API calls — Auto-scales tile size
Prior run dir (optional) — Skip tiles that had 0 extractions in a previous run
Refresh · Reload · Loading…
All statuses · Pending ({N}) · Validated ({N}) · Rejected ({N})
No extractions match the current filter. Push a run to DB first using ocr.py batch --db.
{N} shown. Edit text/category inline, then click ✓ to validate or ✗ to reject.
[placeholders] Building, Temple, Market... · 1 | Abattoir Municipal / 2 | Treasury /
3 | Post Office · Particulier, Communal, Militaire... · e.g. 20260417T120000 ·
390,295,11239,8143 · work/image-processing/results/…/runs/… · Filter by run_id…
[tooltips] Validate all pending items with confidence ≥ 0.7 · Mark as validated ground truth ·
Reject (false positive)
```

## Georef sync panel

```
Sync georef status
Probe the Allmaps annotation server for every map with an allmaps_id but georef_done = false.
Volunteers who finish georef in the Allmaps Editor become visible to /scan?mode=prepare after
this runs. Idempotent.
```

## Neatline editor + datum

```
Loading annotation… · Failed to load: {error}
↺ Reset
Scroll to zoom · Drag background to pan
Corner · Pixel X · Pixel Y · Longitude · Latitude
Datum correction (Indian → WGS84)
If GCP coordinates were read from the map's printed graticule (Indochina / UTM 48 grid), they
are in the map's original datum — not WGS84 — and will be offset ~200–500 m. US Army AMS/
Series-L maps of southern Vietnam (including Hà Tiên area) use Indian 1960, Everest Modified —
select that preset and apply to shift all four GCP geo-coordinates to WGS84.
Source datum · Apply correction
✓ Coordinates updated — review then save
[aria] Zoom in / Zoom out / Reset zoom / Map preview

Datum presets:
Indian 1960 — EPSG:4131 · US Army AMS maps, southern Vietnam (Everest Mod.)
Indian 1960 — EPSG:4131 · Con Son Island variant (EPSG transform 1053)
Indian 1975 — EPSG:4240 (Thailand / northern Indochina, Everest 1830 orig.)
Indian 1954 — EPSG:4239 (alternative SE-Asia fit, Everest 1830 orig.)
Pulkovo 1942 / Gauss-Krüger (Soviet-era Vietnamese maps, Krassowsky)
```

---

# 7 · `/screens` (design system page)

```
Screens — VMA Design System
Screens
one page, whole system.

Colour
Never hardcode one. A hex literal in a component <style> block is a bug.

Type
Google Sans where the reader's machine has it, otherwise Be Vietnam Pro for headings, nav,
badges, labels and buttons and Inter for body text.
Saigon · Chợ Lớn · 1882

Page shell
Every (editorial) route roots at <div class="page x-page">, then PageHero, then
<main class="editorial-main">.
.page carries the mount fade as a CSS animation with both fill and a prefers-reduced-motion
guard — it used to be a mounted boolean flipped in onMount and read as class:mounted, which is
a round trip through JS for something the first frame already does, on a page that
server-renders. Six routes carried that boolean and four carried an identical copy of the CSS.
.editorial-main caps the measure at 1100px. .editorial-main.is-wide opens it to 1400 for a
dense table.

Surface
Borders, shadows and radii. The shadow is always solid, never blurred.
  --border-thin · 2px · Inline labels, dividers
  --border-thick · 3px · Cards, nav, structural

Buttons
Two names, because there are two things, and one modifier vocabulary — the same words .sb-btn
and .sb-pill use in the sidebar scope, so there is one set to learn. In September 2026 this was
twenty-seven selectors across nine families, with four tones spelled three different ways; it
is eleven now. Everything else was a context, not a design.
  .btn — an action: Default · .is-primary · .is-success · .is-danger · .is-ghost · disabled
  .is-lg — a page CTA: default · .is-sm · .is-xs
  .chip — a choice: A tab, a facet, a filter. It fills yellow under the cursor because it is a
  thing you are about to pick rather than a thing you are about to do, and .is-on is the one
  that is picked — the same word as .sb-pill.is-on.
  .is-icon — round, three sizes: 48px is the floating map control, 28px a card's action corner,
  22px a row toggle in a table. They were .ctrl-btn, .btn-icon-edit / .btn-icon-delete and
  .cmp-btn, three private families for one shape at three sizes.

Loading and empty states
One spinner for the whole app, in components/feedback.css. Size and colour tune through
--spinner-size, --spinner-thickness, --spinner-track and --spinner-ink — a variant is three
declarations, never a second @keyframes.
  Running…
.empty-state
One class, two faces. Inline by default — it sits under a list inside a card. .is-block is the
standalone face, for when it stands in the space the list would have filled; .error is the
failed one. It was three classes (.state-msg, a second .empty-state in layouts/tool-page.css,
and a third inside OcrSidebar) until Sept 2026.
  No results.
  Nothing here yet — try another tab or the catalog.
  Couldn't reach the archive.

Chips and badges
.badge-chip plus one tone. Six tones exist; there is no purple. .chip-yellow is a filled yellow
and keeps dark ink in both themes — .chip-white is the paper face it used to paint, which is
why four components carried a private yellow tint until Sept 2026.
  Label chip · Blue · Green · Yellow · Orange · Red · Gray · White
.badge-chip.is-sm — inside a table row
The dense face: base font, no offset shadow. A display-size chip in a table row reaches into
the row below. Four components had a private copy of this.
  Gallica · Cadastral

.stat-tile — Maps · 3.2 km Distance · Stops
Text highlight
.text-highlight belongs on one or two words of a hero title — never in body text.
  Vietnam across time.

Components
Everything in src/lib/ui/, rendered from fixtures. These import nothing from features/, map/ or
data/, so any page may use them.
  PageHero — The hero on every editorial page. You are looking at one above.
  Tabs — The one tab strip. Two tones because there are two design systems, not because there
  are two components: page is the editorial .chip, rail the sidebar .sb-pill. Pass a row an
  href and the strip becomes links with aria-current; without one it is a real tablist.
  .sb-search — Not a component — the one search field, in components/sidebar.css. Both /explore
  rails, both /scan rails, the two table toolbars and /catalog wear it. Two sizes past the
  default: .is-compact is the toolbar, where the field shares a row with a status select, and
  .is-page the full width of an editorial page. It was four designs — two of them a quarter-rem
  apart — until September 2026.
  SortHeader — A sortable column header for any .data-table. A real <button> in the <th> with
  aria-sort on the cell, so it is reachable from the keyboard — the four hand-rolled versions it
  replaced were not. Both carets always draw, one lit, so the header keeps its width when the
  direction flips. Sort state is $lib/core/utils/tableSort.ts.
  PaletteSearchField — The search box that opens the command palette. One field, three places —
  the home hero, the nav and the palette itself — so the thing a reader types into is the same
  object everywhere.
  CatalogGrid — The responsive grid CatalogCard and MapCard sit in. A wrapper with a slot and
  nothing else — it exists so the column rule is written once.
  MapCard — A map in a listing. Optional favourite and source badge.
  CatalogCard — Generic listing card with thumb, meta, description and action slots. A fixture,
  not a real record.
  LibraryGrid — Project and story libraries. Items need only id and title.
  FacetRail — Faceted filter column with counts.
  InlineRename — Click the title to edit it in place. This one is live.
  NameDialog — Naming flow. Live — the button really opens it. (Open dialog)
  NavDropdown — Nav menu disclosure. Takes a default slot of links. (First link · Second link)
  LocationSearch — Nominatim place lookup. Live — typing here really queries OpenStreetMap.
  AuthGate — Signed-out gate for the annotate and story modes. Not rendered here — its button
  starts a real Google sign-in.
  SnapSheet — Mobile bottom sheet. Not rendered here — it is fixed-position and would cover the
  page.
  NavBar · EditorialFooter — Mounted once by the editorial layout. Top and bottom of this page.

Cards
{N} distinct card patterns exist. {N} are reusable; {N} are locked to a single page and cannot
be used anywhere else. Almost all of them are the same object — a white box with a thick border
and a solid shadow. Check this list before writing another.
  Reusable — reach for these
  .section-card — The editorial default. Thick border, large radius, solid shadow. Padding is
  --card-pad, so a caller that wants a tighter one sets a property rather than declaring a fifth
  card.
  .section-card.is-sm — The column size: smaller radius, lighter shadow. The blog grid, a post's
  sidebar and the subscribe nudge were three separate cards that were each this one.
  Class · File · Used by
  Locked to one page — the duplication
  Scoped under {file}

Status tones
The .status-row variants from /admin?tab=status. Colour never carries meaning alone — the
sentence on the card says the same thing.
```

---

# 8 · Misc / API-visible strings

```
Places (LocationSearch heading)
Period (FacetRail heading)
Title block (layout category label)
Abattoir Municipal (example legend entry)
Cloudflare R2
No extractions found above threshold
All extractions already applied
Vietnam Map Archive — Building Footprints (segmentation training)
NameDialog: Title · Description · Save · [placeholder] Give it a title / Add a description (optional)
DataTable / SortHeader: Nothing matches.
Map viewer (MapViewerSidebar title) · My layers · Controls · Browse the archive
```
