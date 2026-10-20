# Corpus: every map of Vietnam we know of

Status: proposal, 2026-10-21. Serves bet 3 in `docs/NOW.md`, and feeds 1c: tracing Saigon's states
through the map series needs to know which maps exist, not only which ones VMA hosts.

**Question.** What maps of Vietnam do the world's libraries hold, and how much of it does VMA know about?

**Answer wanted.** One table, one row per source: what the source holds for Vietnam (measured), how
much of it is in the catalogue, how much in the scout queue, and the script that reads it again.

**So what.** A link is only worth as much as the maps it can link against. Today the count of "what
exists" is a guess, and the scout queue treats every record as a to-do for ingest. The corpus is a
record in its own right: a map VMA will never host still says a sheet was printed, where, when and by
whom, and that is evidence for 1c.

## The idea gate

1. **Bet.** 3 (corpus to link against), feeding 1c. NOW.md has bet 3 as *Later*; Tue opened it on
   2026-10-21.
2. **Smallest test.** One source, David Rumsey, read in full. One number: Vietnam records found
   against the 52 in the scout queue.
3. **Kill.** If reading a source in full adds fewer than 50 Vietnam records beyond what VMA already
   knows, stop harvesting by hand, source by source, and look for a union catalogue to read instead.

## What we know today (2026-10-21, production)

- **Catalogue (`maps`): 1,589 rows.** CartoMundi 704, UT Austin PCL 687, IGN 84, BnF 27, David Rumsey
  15 (via Wikimedia Commons), TTU 6, Humazur 4, one each from NLV, LoC, Commons, MSU, AGSL, ANOM;
  56 with no holder.
- **Scout queue (`scout_candidates`): 1,067 rows.** Humazur 445, Gallica 441, UWM 56, Rumsey 52, LoC 48,
  CartoMundi 25 (one row per series). Seven approved or ingested; the rest pending.
- **Series printings (`cell_printings`): 1,670 rows** over 1,151 cells in 8 series: where a printed
  sheet is held, whether or not VMA has the scan.

## The Rumsey test

The search `="Vietnam"` returns **1,024** records. Reading them all showed two faults:

- **The old scout read 10 records per keyword.** Luna pages with `os` (offset) and `bs` (batch size);
  the script sent `so` and `dh`, which Luna ignores, then stopped because a page held fewer than 50.
  Fixed in `scripts/scout/scout_all_sources.mjs`.
- **Most hits are not maps of Vietnam.** 794 of 1,024 match only in a note on the whole atlas
  (*Hydrographie Française*, 507 sea charts of the world). 230 name a place in Vietnam or Indochina in
  the title or a place field. The scout keeps only those.

**Result, 2026-10-21.** Eighteen keywords read in full (the 15 shared ones plus *Indochina*,
*Cochinchina*, *Viet Nam*) give 250 records; two Portugal charts that matched *hue* inside *Huelva*
and 14 plates VMA already holds come out, leaving 234. Loaded into the queue: **Rumsey went from 52
rows to 243, 191 of them new**, every one with a thumbnail, a manifest and a year. The other 9 are
older rows the new filter would drop (most likely the 1950 plates and the Portugal charts) and stay
for a reviewer to reject. The test passes its kill line (191 > 50).

What they are: 159 atlas plates, 31 charts, 14 separate maps, 14 text pages; 1600s to 1970s, peaks in
the 1870s (25) and 1920s (35). Many are regional maps where Vietnam is one country among several
(*Hindoostan and Farther India*, *China, Indo-China and part of Malaysia*); they count, as coverage.
The scorer files 210 of 243 as `unknown`, because it reads Gallica's subject words, not Rumsey's
`Type` field.

The 15 Rumsey maps VMA holds came through Wikimedia Commons and carry no Rumsey id, so dedup cannot
see them: they are the 15 plates of Rumsey publication 14320 (*Bản Đồ Hành-Chính Các Tỉnh Trung-Châu
Bắc-Việt*, 1950) and are dropped before load.

## Sources

One row per source. *Measured* is what the source itself reports for Vietnam; blank means not
measured yet. Update the row whenever a harvest runs.

| Source | Holds for Vietnam | Measured | Catalogue | Scout | Read by | Next |
|---|---|---:|---:|---:|---|---|
| CartoMundi (Aix-Marseille) | 25 Indochina series | 3,522 sheets | 704 | 25 series | `oneoff/scout_cartomundi_series.mjs` | Sheet level for each approved series |
| UT Austin PCL | AMS series (L7014, L909, …) | | 687 | | L7014 scripts | — |
| IGN | Indochina topographic | | 84 | | | |
| BnF Gallica (+ Bordeaux 3, Paris, Sorbonne) | plans, charts | | 27 | 441 | `scout/scout_all_sources.mjs` | Check it reads every page |
| Humazur (Côte d'Azur) | Cartothèque ASEMI, Indochine française | | 4 | 445 | `scout/scout_humazur.mjs` | Check it reads every page |
| David Rumsey | atlases, charts, 1950 Bắc Việt book | 250 (`="Vietnam"` alone: 1,024) | 15 | 243 | `scout/scout_all_sources.mjs` | Review; scorer to read `Type` |
| Library of Congress | | | 1 | 48 | `scout/scout_all_sources.mjs` | Check it reads every page |
| UWM AGSL | | | 1 | 56 | `scout/scout_all_sources.mjs` | Check it reads every page |
| USGS Store (NGA GeoPDFs) | L7014, L909, JOG 1501, L7015/16 | 618 products | | | branch `l909-sources` | Into the queue as one row per series, like CartoMundi |
| ANU | L7014 masters | 159 | | | `oneoff/scout_anu_l7014.mjs` | No new cell; a printing record only |
| TTU Vietnam Center | L7014 and others | | 6 | | L7014 scripts | |
| ANOM | | | 1 | | | Not looked at |
| Wikimedia Commons | re-hosts (Rumsey, others) | | 1 + 15 | | | |
| Internet Archive | | ~3,500 noisy hits | | | | Skipped: no clean filter |
| NLV press | newspapers, not maps | 2,921 articles | | | `scout/scout_nlv_press.mjs` | Period sources, not the map corpus |

Not looked at yet: Old Maps Online (a union index, which may answer the kill line), EFEO, Leiden
(KITLV), the British Library, Stanford EarthWorks.

## Steps, in order

1. **Rumsey in full** — done 2026-10-21. Fixed paging, every Luna field kept in `raw.fields` as the
   record's first metadata (scale, full title, size, place fields), the publication a plate belongs
   to in `collection`, 243 rows in the queue. The loader no longer sends `review_status`, which on a
   re-scout would have reset approved rows to pending.
2. **Check every other scout reads all its pages.** For each source, the total it reports against the
   rows the script keeps. The Rumsey fault was silent for months; the others may share it. One
   afternoon.
3. **USGS NGA into the queue**, one row per series, from the list already on `l909-sources`.
4. **The sources not looked at**, biggest first, after Old Maps Online answers whether one index
   covers them.

## Two questions the queue mixes

`review_status` answers "will VMA host this?" A rejection today can mean "not Vietnam" or "Vietnam,
but not worth a scan". Only the first leaves the corpus. Until the corpus page needs the split, the
reviewer writes which one in `review_note`; nothing is deleted.

## The corpus page — later

It would read three tables already there: `maps` (held), `cell_printings` (series sheets held
elsewhere), `scout_candidates` (known, not reviewed or not hosted). Counts by source, decade and
region, and the gaps between them. Build it once steps 1–3 have run, so it shows a corpus worth
counting.
