# 260921 — sourcing the two calibration panoramas

**Date:** 2026-09-21 · **Severity:** —  · **Component:** L2 mass model / District 4 4D plan · **Status:** both found, neither visually confirmed; "1901" label was wrong (it's 1898)

`docs/archive/pipeline-3d.md` and `docs/private/priority-2026q4.md:152` name two painting-map pairs
as the height-calibration source for the LoD1 mass model (no LiDAR for colonial Saigon): an 1881
B&W engraving paired with the 1882 cadastral, and a 1901 colour lithograph paired with the 1898
cadastral. Neither doc carried a findable source (title, holding institution, URL) for the actual
artwork — this is that lookup.

## 1881 pair — found

**"Saïgon d'après nature"**, by M. Favre (captain, marine infantry), engraved by Auguste Lepère,
published by Mouillot, Paris, 1881. 77 × 58 cm engraved print. Digitized on Gallica (BnF):
`https://gallica.bnf.fr/ark:/12148/btv1b53062212t`. Also listed under Wikimedia Commons'
*Old maps of Saigon* category and catalogued on isidore.science under the same ark.

This matches the doc's description (monochrome, elevated oblique, full-city view, 1881) closely
enough — creator "Favre," engraver "Lepère" — to treat as the same work, but nothing in the repo
previously recorded creator/engraver/publisher, so that match was not independently confirmed
before now; worth a visual check against whatever image the original plan-writer had in hand.

**Confirmed 2026-09-21**, via Gallica's OAI record (`/services/OAIRecord?ark=ark:/12148/btv1b53062212t`)
— the ark page itself is a JS shell; the notice fields live there. Every field above matches
exactly: title, creator ("Favre (18..-18..?; capitaine). Cartographe"), engraver ("Lepère, Auguste
(1849-1918). Graveur"), publisher ("Mouillot (Paris)"), date (1881), format ("1 flle ; 77 x 58 cm").
Adds a shelfmark not previously recorded: **BnF, département Cartes et plans, GE C-3950**, and the
linked catalogue record `http://catalogue.bnf.fr/ark:/12148/cb40761158r`. (The earlier 403 was this
session's own DNS resolver failing on `gallica.bnf.fr`, not a Gallica bot-block — `--resolve` to the
IP worked first try.) Still not visually confirmed — the OAI record has no image link beyond the
og:image thumbnail (`…/btv1b53062212t/f1.medres`); pulling the full-res scan is the remaining step
before this is wired into the pipeline.

## "1901" pair — found, and the year was off

**Untitled panoramic bird's-eye view of Saigon**, drafted by Gaston Pusch, published by Claude et
Cie. (Louis-Jean Claude's printing/bookselling house, 125-127 Rue Catinat, Saigon, active to
c. 1905), dated **1898**, not 1901. Multi-colour chromolithograph, 33.5 × 47.5 in — per the dealer
listing "the largest and most spectacular panoramic bird's-eye view of Saigon ever produced,"
viewed from a high point east of the city across the Saigon River. Listed by Geographicus Rare
Antique Maps: `https://www.geographicus.com/P/AntiqueMap/saigonview-claude-1898`.

This matches the doc's description (full-colour, oblique, whole-city, peak first-wave development)
closely enough on every point except the year to be the same work the plan meant — which means the
"1901" in `docs/archive/pipeline-3d.md` and `docs/private/priority-2026q4.md:152-153` is itself
another loose label, the same way "1882"/"1898" was loose for the painting years before that
correction. **The print is dated 1898, i.e. the same year as the cadastral it's meant to pair
with** — which is a tighter, more defensible pairing than a 3-year gap, not a weaker one.

**Access note:** geographicus.com also 403s WebFetch; this came from search-result snippets across
two independent queries that agree on drafter, publisher, dimensions, and date. Worth opening the
listing in a browser to pull the actual image and confirm before citing further.

## Bottom line

Both calibration sources are now traceable to specific, dated, sourced prints:

| Pair | Source | Date | Confirmed |
|---|---|---|---|
| "1882" | *Saïgon d'après nature*, Favre/Lepère, Gallica `btv1b53062212t` | 1881 | via search snippets, not a direct read |
| "1898" | Bird's-eye view, Pusch/Claude et Cie., Geographicus `saigonview-claude-1898` | **1898** (doc said 1901) | via search snippets, not a direct read |

Both listings 403 WebFetch, so nothing here has been visually confirmed against the actual image —
someone should open both URLs directly before wiring either into the pipeline. The "1901" label in
the archived plan and the private note should be corrected to 1898 once this is confirmed.
