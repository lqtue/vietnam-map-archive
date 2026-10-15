# What VMA is

The one description of the Vietnam Map Archive. App copy, the README, the strategy and the paper's
framing all take their words from here. If the words stop fitting, change this page first, then the
places listed at the end. The month's bets live in `NOW.md`, not here.

## The line

> **Vietnam's places, kept through time.**
> *Lưu giữ địa điểm Việt Nam qua thời gian.*

Working words. The final line and sentence, in both languages, will be written with a human writer;
until then the app keeps its current copy.

## The sentence

> VMA ties maps, documents, photos, studies and writings to the place and time they describe, so a
> researcher finds every source for a place together. It keeps what could be lost, from maps held
> abroad to buildings due to come down, and lets anyone see a place as its sources show it. A
> machine proposes each link and a person decides; every record says who checked it.

## Why

Three things, each worse than it was:

- **The sources are scattered.** Old maps of Vietnam sit in archives in France, the United States
  and Vietnam, many behind institutional walls; documents, photos and memoirs about the same streets
  sit somewhere else again, and a private collection online can vanish in a day.
- **The sources never agree.** Each map was drawn by someone, for a purpose: a map is a claim, not a
  photograph (Harley 1989), and so is a novel's street or a memoir's address. Agreement is also cheap
  now: a map redrawn from another, or an AI summary of a catalogue, agrees with its source for free.
- **The places are going.** Across Vietnam, places are changing faster than anyone records them.
  The 2025 administrative merge rewrote the map of provinces, districts and communes, and old names
  now sit on new ground; cities are being rebuilt, and a building that comes down leaves only what
  recorded it. A photo taken today is tomorrow's old record.

VMA began as a home for these sources, "as secure as a professional archive and as open as the
Internet" (the founder's letter, below). The check is what makes "secure" true; the opening is what
makes it useful.

## Three jobs

The place is the unit: every source is tied to a place on the ground and a time. The maps are the
frame; they are what turns a document's "rue Catinat, 1955" into a point anyone can find. The jobs
come from the founder's letter (preservation, open access, storytelling), in the order that matters.

| Job | Means | For | Today |
|---|---|---|---|
| **Link** — the core | Tie each source to a place and a time, say how they relate, record who checked it | researchers; the paper and the PhD | maps placed and names read; links in an offline test |
| **Keep** | Save what could be lost: maps held abroad, family photos, buildings due to come down | everyone, later | maps, yes; documents and photo sets not yet collected |
| **Show** | Let anyone see, and later walk, a place as its sources show it | the public | the map viewer, stories and journeys; Walk parked |

## How a link is made: four verbs

Each step needs the one before it: a name read off a sheet that is not in place cannot be linked
to today.

| Verb | Means | Where it lives |
|---|---|---|
| **place** | Pin a scan to real coordinates (georeference) | Allmaps, `/contribute/georef`, `/explore` |
| **read** | Turn what is printed into data: names (OCR) and shapes (tracing, SAM2) | `/scan?mode=text`, `/scan?mode=shapes` |
| **link** | Join a thing on one map to a thing on another map, in a source, or in the city today, and say how they relate | the gazetteer (`/catalog/place`); bet 1a, `place-links` |
| **check** | A person decides; record who, what and when; measure how often they were right | the review queues; bet 2, `review-events` |

## What a link is

A link has four parts. A link that leaves one out is a guess.

| Part | Example, 1882 survey |
|---|---|
| **From:** a thing on one map, at a place on the scan (a name read by OCR, or a traced outline) | the label "Marché Central" |
| **To:** a thing on another map, in a source (a document, photo, study or book), or in the city today | Chợ Bến Thành |
| **Relation:** how the two are connected | *moved* |
| **Who decided, and what they saw:** the reviewer, the time, the machine's candidates, and whether they were shown | a reviewer, a time, the top 3 candidates, shown or hidden |

The relation is the point: a link is not only "the same place". For a place today it is one of
same building · same site, new building · moved · gone · none · unsure
(`work/image-processing/experiments/place-links/README.md`). For a block between two maps it is one of
unchanged · reshaped · split · merged · complex · gone · new (`plans/digest-pipeline-plan.md`). For
a source it is one of set in · depicts · mentions · located at (draft): a scene of *The Quiet
American* is *set in* the Continental Hotel, which records a claim, not a fact about the building. A
reused name is not the same place, and the relation is where we say so.

Today only map-to-today links exist, offline on the 1882 survey; map-to-map block links are being
tested; map-to-source links are not built. Say so wherever links are mentioned.

## What it makes

VMA is a research tool. It makes three kinds of things. The records are the "as secure as a
professional archive" half of the founder's promise; the ways in are the "as open as the Internet"
half; the evidence is what makes "secure" true.

### 1. Records

Things anyone can search, cite and download. Each says where it came from and who checked it, and
outlives any page built on it.

| Record | Example | State |
|---|---|---|
| Old maps, put back in place | the 1882 survey of Saigon | public: `/catalog`, `/explore` |
| Names read off them, grouped into places (the gazetteer) | "Marché Central" | public: `/catalog/place`; partly checked |
| Shapes read off them | 1882 water, roads, blocks | water approved, not shipped |
| Sources: documents, photos, studies, writings, each tied to a place and a date | a photo of the market; a scene of *The Quiet American* on the 1968 map | stories exist; no typed source record yet |
| Links: map to map, map to today, map to source | Marché Central → Chợ Bến Thành, *moved* | offline test, 1882 survey |
| Administrative units over time: provinces, districts, wards and communes, with every rename, merge, split and boundary change, from the earliest map to the 2025 reform | Xuân Hoà ward → Xuân Hòa village on the 1882 topographic plan (not the cadastral plan) | planned; Saigon–Gia Định–Ho Chi Minh City first, then Vietnam |

The administrative record is the link applied to units. Its relations: renamed · merged · split ·
abolished · boundary moved · name reused. A ward that took an old village's name in 2025 is *name
reused* until a map shows the ground is the same. The official list starts in 2004 and has no
boundaries; no open, structured record covers 1862–2004 that we have found.

### 2. Ways in

Pages for using the records. They can be rebuilt; the records stay.

- **Find**, the way into Link: *what was here, and what was written about it?* One search returns every map,
  name, source and link for a place and a date. Today: `/api/context`, `/api/search`,
  `/catalog/place`.
- **Walk**, the way into Show: the city as those sources show it — stories and journeys, on foot or on screen
  (`plans/walk-plan.md`). Parked. When it opens, people first send photo sets of buildings that
  still stand (a place, a date, an open licence); a 3D model can be built from them later.

### 3. Evidence

Numbers about the records: how often a link is right, what a check costs in seconds, and which checks
only echo what they check (§The rule). This is the paper and the PhD case; other archives have
records and pages, few measure their checks. Bet 2, `review-events`.

## The rule

**A check counts only if it could have failed.** Three things look like a check and are not:

- a machine test that shares the error it is testing for (the paper, *Blind by construction*);
- a person who only agrees with the machine (so one item in five hides the suggestion);
- a second source copied from the first: two maps redrawn from one survey, or an AI summary of the
  catalogue it was written from.

Full argument: `plans/theory.md` §A Check Must Be Able to Fail.

## The goal

Show that historical maps which never agree can still be **linked** — map to map, map to source,
map to today — with a machine that proposes and a person who decides; **measure** what that costs
and how often it is right; and show **which checks are independent of what they check**. That
measured, linked record is the product and the PhD pitch (information science) at once. Beyond the
1882 sheet, the first such record is Saigon's administrative units over time.

## Scope

All of Vietnam. Saigon is where the work goes deepest: it is the city we live in and the one with
the best archives. The 1882 cadastral survey of Saigon is the worked example every claim points to.
Administrative units start with Saigon, from 1862, where the sources are in French and modern
Vietnamese; Hán-Nôm sources wait until someone can read and check them. Year ranges and sheet counts
come from the database; never type them into copy.

## The horizon

Where this could lead, not what VMA is today: a place-time record that answers *what was here,
when, and what was it called* (`plans/platform-design.md` §0), and past that a time-layered city
(`plans/strategy.md`, `plans/theory.md`): Ho Chi Minh City's planning maps laid over the old ones,
a 3D city built later from Walk's photo sets, the "body and soul" of the city and a ride on the
19th-century train (Saigoneer's words, 18 January 2026, not the letter's). Name it as the horizon. Never describe VMA as a digital
city, a 4D city or a reconstruction.

## In the founder's words

The [Letter of the Founder](https://docs.google.com/document/d/1YPQyCvCovQ0lu1x0d9xWxHvL_FGQLwpVMmCTizVTqLs) (Tuệ; linked from Saigoneer, 18 January 2026) says the same things
in a reader's words:

- the promise: "as secure as a professional archive and as open as the Internet" — *check* and *open*;
- the link: "You might have an old map from your grandfather. A researcher in France might have a
  rare document. A student in Hanoi might have a question that connects them both.";
- the place-time question: "a student in Huế can pull up a map from 70 years ago, find the street
  their grandmother lived on".

Use these as examples, never as promises of what works today. The letter's claims about the present
(that each map is already "meticulously georeferenced", and the team it names) are out of date; do
not repeat them.

## Words

| Say | Not |
|---|---|
| Vietnam Map Archive, VMA | `vmabeta` |
| put back in place, place, pin | "georeferenced", in public copy (fine in docs) |
| read: names, shapes | digitize, extract, in public copy |
| link | match, connect, join |
| a machine proposes, a person decides | "AI-powered", "automatic" |
| check, approve | validate, verify, in public copy. Status words: `src/lib/CLAUDE.md` §Review words |
| a small volunteer project | startup, institution |
| a research tool; records you can search, cite and download | "the platform", "data hub", in public copy |
| kept through time; what was here | "time machine", "time travel" (press may say it; we do not) |

## Where the words come from

The plain words are for readers. Each has a name in the literature, and the paper and the PhD
statement use that name, cited. Copies of all seven are in the owner's library (`08-information-science`, Harley in `01-hgis-methods`).

| VMA says | The field calls it | Source |
|---|---|---|
| link; a machine proposes, a person decides | record linkage: *link*, *non-link*, or *possible link*, which goes to *clerical review* | Fellegi & Sunter (1969), *JASA* 64(328) |
| a name as printed on one sheet | an *attestation*: one source's record that a name existed at a time; a place is the union of its attestations | Grossner & Mostern (2021), GeoHumanities '21, doi:10.1145/3486187.3490203 |
| who checked it, and from what | *provenance*: entities, activities and agents; *attribution*, *derivation* | W3C PROV-DM (2013) |
| a person who only agrees with the machine | *automation bias* | Parasuraman & Manzey (2010), *Human Factors* 52(3), doi:10.1177/0018720810376055 |
| a source copied from another | *source dependence*, *copying* | Dong, Berti-Equille & Srivastava (2009), *PVLDB* 2(1) |
| a map is a claim, drawn by someone for a purpose | maps as *representations of power*; critical cartography | Harley (1989), *Cartographica* 26(2), doi:10.3138/E635-7827-1757-9T53 |
| right enough for what it is used for | *fitness for use* | Wang & Strong (1996), *J. Management Information Systems* 12(4) |

Fellegi and Sunter's three decisions map onto the review words: a possible link is `proposed`
until a person makes it `approved` or `rejected`.

## Where these words appear

Change these together. Vietnamese goes in `work/copy/translate-vi.md`, then run
`node scripts/gen/gen-i18n.mjs`.

- Home: title, hero subtitle, meta description, "About the project" band — `src/routes/(editorial)/+page.svelte`
- About: hero and meta description — `src/routes/(editorial)/about/+page.svelte`
- Blog sidebar — `src/routes/(editorial)/blog/[slug]/+page.svelte`
- App manifest — `static/manifest.json`
- `README.md`, the first paragraph of `CLAUDE.md`, `docs/guides/user-guide.md`
