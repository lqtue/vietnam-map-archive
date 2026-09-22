# 260902 — what two map creators' feeds say about reach

**Date:** 2026-09-02 · **Severity:** low (research) · **Component:** product · **Status:** acted on
in part

Read two creators' Threads exports end to end: Tomey (`@tomeyinhanoi`, hanoimaps.github.io /
saigonmaps.github.io, 54 pages) and Craig Campbell (`@that.map.guy.craig`, Pastmaps, 92 pages).
Engagement counts are visible in both exports, so this is measured reach rather than taste.

## What travels

- **A derived-data reveal beats a map.** Craig's best post by roughly five times shows an invisible
  1100 AD city grid pulled out of LiDAR at Cahokia Mounds — one image, one satellite comparison. The
  pattern under every high performer: a named place, a coordinate, and a thing you could not see
  before.
- **Tool launches travel; biography does not.** Tomey's top product post adds French-era street-name
  history to his map site. His most *reposted* post ever is the launch of a search over the National
  Library of Vietnam's press archive. His multi-part street-namesake threads underperform those by
  ten to twenty times, and teasers with no artifact score in the single digits.
- **"This ordinary thing you walk past was X"** is the cheap, repeatable win: a manhole cover whose
  bend follows the Thăng Long citadel's southern moat; West Lake as a seaplane base.
- **Reposts, not replies, carry Tomey's reach** — utility is what gets forwarded.

## Acted on today

- `--clahe` contrast pre-pass in the OCR tile path, off by default until the eval set measures it.
  Craig runs adaptive contrast on every sheet purely so computer vision can read faded copperplate,
  and credits it with unblocking a very large ingest. Our corpus is full of washed-out colonial
  scans.
- **← / → step the year, ↑ / ↓ the opacity** on /explore, camera held still. Tomey ships exactly
  this as a feature announcement. It turns the layer stack we already had into a time scrubber,
  which is the morphology pitch in one keystroke.

## Queued, with a reason

- **Colonial ↔ current street names with namesake notes.** Tomey's single best product post, sourced
  from one book appendix, not a scrape. Feeds the place-time index directly.
- **Per-place hub pages.** Craig's traffic engine, and he reports it ported cleanly to new
  countries. We already server-render `/map/[id]`; the increment is `/place/<name>` off the label
  index shipped in E1.
- **Heritage-building point layer** from the HCMC conservation lists (~600 villas, District 3 heavy,
  published by decree). The cheapest possible seed for E5's OSM tags.
- **A credits and attribution page.** We hold `holding_institution` already. Craig also received a
  commercial-use licensing request for one specific sheet, which says rights must be answerable per
  record, not per site.
- **Classical-CV neatline / survey-grid detection to auto-seed GCPs.** He unblocked 200k maps with
  ~210 lines of pre-LLM algorithms after LLM approaches failed. Only worth it past ~101 maps, but it
  is the answer to E4's georef bottleneck at scale.

## Duplicates — do not build

Multi-map layer stacking with reordering, search-on-pan with previews, and share links are all
things we already have. The only increment in his search is result counts that update with the
viewport.

## Cautions

- **A public georeferenced corpus with an open API gets mirrored.** He blocked three million bad
  requests in under a day and found a botnet replaying an offline copy of his site with JavaScript
  enabled, which corrupted his analytics.
- **Right-to-be-forgotten requests arrive** once there are accounts; design deletion before volume.
- **His pricing experiments failed loudly** — a 2× test looked like a win until split by country,
  where UK and Ireland subscription starts fell over 70%.

## Lesson

The archive's marquee surface should be the derived layer, not the scans. Craig's paying customers
"solely" want his LiDAR and never open the historical maps. Our equivalent is the dated vector
fabric — canal infill, block grain, built-area over time. That is already Track E's E2; his data
says lead with it rather than treating it as a byproduct.
