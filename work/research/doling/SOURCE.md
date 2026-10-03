# Source and citation — Historic Vietnam

All data in this directory is derived from:

> Doling, Tim. *Historic Vietnam*. https://www.historicvietnam.com

WordPress export `historicvietnam.WordPress.2026-01-23.xml`, supplied by the author.
**268 published posts, 3,107,637 characters, 2013-11-03 to 2026-01-23.**

**Permission.** Tim Doling agreed on 2026-09-22 that the archive may use and cite this
material. Cite him on every surface that shows a row derived from it — the extraction
carries `post_title`, `post_date` and `post_url` per row precisely so that no row can be
displayed without its citation.

**He is a secondary source.** Careful and well-researched, but prose about maps rather than
a map. Anything from here that reaches `place_names` or `footprint_submissions` goes in with
a source tag identifying it as Doling, never merged indistinguishably with a name read off a
sheet. The gazetteer has to be able to say which is which, and a reader has to be able to
tell a toponym this archive measured from one it was told.

**The raw export is not in this repo.** It lives outside the working tree and is not
redistributed here; this directory holds only derived, reviewable tables.

## Files

| File | What it is |
|---|---|
| `street-name-pairs.csv` | 89 candidate colonial ↔ modern name pairs, classified, one row per distinct pair, each with the sentence it came from and its post citation |
| `gallica-variants.json` | 63 place names → attested colonial spellings, keyed by the modern name, for `spellingVariants(name, extra)` in `src/lib/server/gallica.ts` |
| `nlv-queries.txt` | 138 quoted phrases for `scripts/scout_nlv_press.mjs`, both sides of each pair, tagged colonial/modern |

Regenerate: `node scripts/oneoff/extract_doling_placenames.mjs --press`
Self-check:  `node scripts/oneoff/extract_doling_placenames.mjs --check`

## Why the two press feeds are different shapes

They are different kinds of archive, and `docs/pipelines.md` already says so.

**Gallica (BnF) has OCR'd full text.** `src/lib/server/gallica.ts` queries it with SRU
CQL and takes `extra` spellings per place name, so the feed is keyed by the modern name
with the colonial forms as values. Its OCR is mostly unaccented, which `spellingVariants`
already handles — it unaccents each form itself.

**The NLV archive has no text at all.** *"There is no text, only the scan"* — a hit carries
a headline, a date and a crop box, nothing more. So it can never be a **source** of place
names, only a **consumer** of them, and its feed is a flat list of quoted phrases. Quoted
because Veridian's `txq` ANDs an unquoted query's words; `scripts/nlv-queries.txt` records
what that mistake cost.

Neither file has been applied. The counts in `nlv-queries.txt` are blank until a harvest
run measures them.
