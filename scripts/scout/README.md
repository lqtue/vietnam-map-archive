# Scout: press, legend timeline, place reports

For whoever finds period sources. Kind: guide.
Moved here from `docs/guides/pipelines.md` on 2026-10-17, word for word.

## NLV press harvest (`scripts/scout/scout_nlv_press.mjs`)

The National Library of Vietnam's newspaper archive (`baochi.nlv.gov.vn`, 81
titles, 1865–2013) has no API, but it runs **Veridian**, whose search is a plain
GET and needs no session:

```
baochi/cgi-bin/baochi?a=q&r=<1-based>&results=1&txq=<query>&txf=txIN&ssnip=img&o=50
                     &puq=<publication id>&dafyq=<from year>&datyq=<to year>
```

`r` is the index of the first result and `o` the page size (50 is the largest the
form offers). The script pages that, parses the results HTML, and appends
`work/research/press/nlv.jsonl` — one row per `oid`, the archive's own article key, deduped
against what is on disk. Neither the jsonl nor `--images` output is in git.

```bash
node scripts/scout/scout_nlv_press.mjs --selftest
node scripts/scout/scout_nlv_press.mjs --pubs                     # the 81 titles + ids
node scripts/scout/scout_nlv_press.mjs --queries scripts/scout/nlv-queries.txt
node scripts/scout/scout_nlv_press.mjs '"bản đồ"' --pub RbD,WHfY  # southern papers only
node scripts/scout/scout_nlv_press.mjs '"bản đồ"' --from 1920 --to 1945
node scripts/scout/scout_nlv_press.mjs --report
```

Measured 2026-09-13: the fifteen phrases in `scripts/scout/nlv-queries.txt` are **2,921
rows in about 90 seconds**, every query paged to 100%.

### The app queries it directly too

`src/lib/server/press.ts` used to reach the archive through
`baochi-tvqg.vercel.app`, the endpoint behind
<https://hanoimaps.github.io/news>. That site
(`github.com/hanoimaps/hanoimaps.github.io`, one repo, author Tran Minh Tri)
contains **no NLV code at all** — it is 150 lines of `fetch()`; the whole proxy
is a closed Vercel function. It is 8–16 s per call against 3–5 s direct
(up to 20 s on a cold CGI — the archive's own variance, not the page size),
states no result total, and exposes none of the filters. `/api/press` now queries the
library directly, which also made two things possible:

- **A decade curve for free.** The results page carries a decade facet, so
  "when was this place in the news" comes off the same response as the
  clippings — no second request. It is returned as `curve.nlv` and drawn as a
  strip above the list in `PressPanel`. Gallica has no facet and a curve there
  would be one request per decade, so the curve is the Vietnamese press only
  and the caption says so.
- **Thumbnails that are the clipping.** Each result states `crop=x,y,w,h`, the
  archive's snippet box — ~120 kB against ~1.4 MB for the whole newspaper page
  the panel used to load. It is the matched line for an advertisement but the
  article's *heading* for an article-level hit, so it is a thumbnail, not proof
  the phrase is in the picture — see the place report below.

**The archive answers on http only** — there is no https listener. A server-side
subrequest is fine with that, but a browser on an https page blocks a
mixed-content image, so thumbnails still go through the hanoimaps proxy, which
is https and passes `crop` straight through. That is now the only thing the
proxy is used for.

### Three things that decide what can be collected

- **`txq` ANDs words. It does not match phrases.** `bản đồ` and `đồ bản` both
  return **15,154** — every page carrying *bản* and *đồ* anywhere on it, nearly
  all of it noise. Quoting asks for the phrase: `"bản đồ"` is **838**. Every line
  in `scripts/scout/nlv-queries.txt` is quoted for that reason, and the count beside
  each line is its measured total. An unquoted query is a different and much
  noisier question; the 74,524 "results" the unquoted list first reported were
  this mistake.
- **Geography is not a query term.** `"bản đồ" "Sài Gòn"` is 41 rows: a Saigon
  paper printing a city map rarely names the city in the same breath. The paper
  itself is the evidence of where, so the HCMC corpus is a **publication** split —
  `--pub`, or `scripts/scout/nlv-southern-pubs.txt`, whose ids `--report` subtotals.
  Of the 2,921 rows, **928 are southern press, 1890–1988** (Sài Gòn 302, Công luận
  báo 177, Sài Gòn Giải phóng 77, Lục Tỉnh Tân Văn 70, …). That file is tagged by
  eye — the archive publishes no place-of-publication field.
- **There is no text, only the scan** — and its coordinates. A result carries the
  headline, the document type, the publication, the date (packed into the `oid`,
  so no Vietnamese date parsing), and `crop=x,y,w,h`: the archive's snippet box,
  which the proxy throws away. Both the crop
  and the full page come off the same image server:

  ```
  baochi/cgi-bin/imageserver/imageserver.pl?oid=<oid>&area=1&crop=<x,y,w,h>&width=<w>&color=all&ext=jpg
  baochi/cgi-bin/imageserver/imageserver.pl?oid=<oid>&area=1&width=2000&color=all&ext=png
  ```

  Full page at 2000px is ~220 kB and ~1.7 s; a crop is ~11 kB and ~0.3 s.

### Ceilings

- **Politeness, not throughput.** This is a national library's public search.
  Sequential, one request at a time, 1.2 s apart, one retry. Do not parallelise.
- **`--max` is a per-run page budget, not the size of the archive.** Each (query,
  publication, year-range) pair's next `r` is remembered in
  `work/research/press/offsets.json`, so re-running the same list continues where it
  stopped rather than re-paying for pages it already has. `--restart` ignores it.
- **The parser is regexes over Veridian's HTML.** `--fixture` saves one results
  page to `work/research/press/fixture-results.html` and `--selftest` pins the parser
  against it, asserting a full page's worth of rows and a non-zero total — so a
  template change fails loudly instead of reading as an archive with nothing in
  it. `--selftest` exits non-zero. Re-run `--fixture` if the page size changes.

## Legend timeline (`scripts/scout/legend_timeline.mjs` + `legend_press.mjs`)

Four Saigon sheets carry a numbered legend that OCR has read, which is four dated
lists of the same city's institutions:

| sheet | year | entries | language |
|---|---|---|---|
| Plan de la Ville de Saigon | 1878 | 29 | French |
| Saigon - Cholon | 1923 | 182 | French |
| Plan de Saigon - Cho Lon | 1942 | 235 | French |
| Đô thành Sài Gòn | 1959 | 156 | **Vietnamese** |

`legend_timeline.mjs` matches them to each other; `legend_press.mjs` hangs a
per-decade press curve off each match, from the NLV (Vietnamese) and Gallica
(French) archives. Output is `work/research/legend/{entries,timeline,press,baseline}.json`,
none of it in git.

```bash
node scripts/scout/legend_timeline.mjs --selftest
node scripts/scout/legend_timeline.mjs                 # read the DB, match, report
node scripts/scout/legend_press.mjs --baseline         # the corpus's own shape, once
node scripts/scout/legend_press.mjs --threads cross    # only threads crossing 1959
node scripts/scout/legend_press.mjs --report           # normalised; --raw for counts
```

### Matching across a language change

The 1959 sheet renamed everything, so this is not a string join. Both languages
write a legend entry as `<type> <proper name>`, and the proper name stays a proper
name across the rename — `Marché de Binh Tây` / `Chợ Bình Tây`, `Hôpital Grall` /
`Bệnh-viện Đồn Đất (Grall)`. So the key is **(canonical type, folded proper
name)**, with a ~27-word French↔Vietnamese type lexicon (`Marché↔Chợ`,
`Hôpital↔Bệnh-viện`, `Cimetière↔Nghĩa-địa`, `Commissariat↔Cảnh-Sát-cuộc`) and
nothing else translated. An institution whose *name* also changed lands in the
unmatched list rather than being guessed at.

Measured: 602 entries → 447 threads, 85 on more than one sheet, **12 surviving
into the 1959 Vietnamese legend**.

Three things the lexicon has to get right, each of which failed silently first:

- **Longest pattern first.** `bảo-sanh viện` must beat `viện`, `palais de justice`
  must beat `palais`, and `poste de police` must beat `poste` — a police post typed
  as a post office can never meet a 1959 `Cảnh-Sát-cuộc`. 17 entries were wrong
  this way. `bureaux` is listed beside `bureau`: the 1923 sheet uses the plural.
- **The connector comes off the name, not just the key.** `Marché de Binh Tây` →
  `Binh Tây`. The name is what gets sent to Gallica, and `adj "de Binh Tay"` is a
  different phrase — leaving it on cost two thirds of the hits.
- **Threads partition the entries.** A parenthetical naming another thread is a
  **link**, never a merge. `(Grall)` is one-to-one and is a rename; the seven 1942
  cemeteries carrying `(Phú Thọ)` are a consolidation into one 1959 municipal
  cemetery, and merging flattened that into the first case while claiming the same
  1959 row seven times. The selftest asserts the partition.

### Press curves, and why they are normalised

`legend_press.mjs` queries the **proper name**, not the whole entry: the type word
is noise the period press does not repeat (`"Chợ Bình Tây"` is 4 hits, `"Bình Tây"`
is 60). One NLV request returns the whole curve — Veridian's results page carries a
decade facet with counts. Gallica has no facet, so it is one request per decade.

- **Every Gallica query is scoped to Saigon** (`and (gallica adj "Saigon")`).
  Gallica is all of France: `Cimetière Européen` scored 52,075 before this. Querying
  the *full* entry instead does not work — the press writes `marché de Binh-Tây` with
  its own accents and hyphens, so `adj` over four words returns 0 where the name
  alone returns 145.
- **Specificity is measured, not guessed.** One extra request per name compares its
  scoped total against its unscoped one: `Binh Tay` 0.77, `Européen` 0.26. Under 0.4
  the row is flagged, because that curve is the word and not the place.
- **The numbers are corpus-corrected before they are read.** Both archives thin
  out after 1940 for reasons that have nothing to do with Saigon's markets, so
  every curve is divided by its archive's own shape per decade. The two
  denominators are **different universes** and are not comparable with each
  other — every Gallica query is already Saigon-scoped, so its baseline is
  documents naming Saigon (20,672); the NLV queries are unscoped, so its baseline
  is `"và"`, the commonest Vietnamese word, standing for how much text the archive
  holds per decade (196,639 — 80,288 pages for the 1930s against 3,676 for the
  1960s). **Not `"Sài Gòn"`**: as an exact phrase that is 21 hits in the whole
  1930s, because the period press wrote *Sàigòn* and *Sài-gòn*, and using it put
  normalised values above 1,000‰.
- `--report` then **indexes each row 0-99 against its own peak**, which is what
  makes the shape readable: per-mille is honest but unreadable on the NLV side,
  where every single place is a vanishing fraction of all Vietnamese print.
  `--rate` shows the per-mille and `--raw` the counts. A decade the baseline does
  not cover prints `?`, never `0` — Gallica is only asked about 1860–1959.
- The CQL builder is a **second copy** of the one in `src/lib/server/gallica.ts`
  (a `.mjs` script cannot import the TypeScript). `--selftest` pins it against the
  exact string `tests/press.spec.ts` asserts, because a drift between them would
  look like an archive with nothing in it.

Politeness is the same rule as the NLV harvest: sequential, ~1.2 s apart, one
retry, two public archives.

## Place report (`scripts/scout/place_report.mjs`)

A cited, dated evidence report for one place from both period archives.

```bash
node scripts/scout/place_report.mjs --selftest
node scripts/scout/place_report.mjs "Khánh Hội" --max 14
node scripts/scout/place_report.mjs "Khánh Hội" --variants "Khanh Hoi,Khánh-Hội"
```

Writes `work/research/reports/<slug>.md` (gitignored): the decade curve, a synthesis, then
every source numbered with its date, archive and URL. The synthesis is written by
Gemini from the evidence table **and nothing else**, with `[n]` citations into it,
so a reader checks rather than trusts.

The two archives answer in different media, and that is the whole design:

- **Gallica** has OCR'd full text, so `services/ContentSearch` returns the actual
  sentence — quotable as it stands.
- **The NLV returns no text at all.** Each clipping is *read* from the scan by a
  vision model before it can be cited, and every entry links its image.

Three things this gets right that a naive version gets wrong, all of them silent
failures that return confident, irrelevant evidence:

- **All three endpoints match loose words unless told otherwise, and each spells
  it differently**: NLV `txq` takes `"…"`, Gallica SRU takes `gallica adj "…"`,
  Gallica ContentSearch takes `"…"`. Unquoted, ContentSearch for `Khanh Hoi`
  returns 18 hits on *quan*, *Quant* and *quand* and one on the place.
- **The crop is not always the match.** Veridian crops the matched line for an
  advertisement but the article's *heading* for an article-level hit — the 1918
  *Lục Tỉnh Tân Văn* hit crops to the section header "TẠP TRỞ (Variétés)", which
  says nothing about the place. So the crop is widened for context and the model
  is asked whether the name is actually visible; on the Khánh Hội run **8 of 14
  were not**, and those are printed as "the name is not visible in this crop"
  rather than quoted as though the headline were the source.
- **A catalogue hit with no locatable sentence is a lead, not evidence**, and is
  dropped — so the Gallica count is smaller than the catalogue would report.

Even with all three, `adj "Khanh Hoi"` still matches Vietnamese prose where
*Khánh* is followed by *hỏi* ("Khánh asked"), because Gallica's index is
unaccented. The Khánh Hội synthesis caught those itself and named them as
typographical matches — which is the argument for the numbered table sitting
under the prose rather than instead of it.
