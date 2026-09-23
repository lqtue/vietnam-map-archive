export interface BlogPost {
  slug: string;
  title: string;
  date: string;
  category: 'update' | 'research' | 'community' | 'announcement';
  excerpt: string;
  /**
   * Dated correction, rendered above the post body. A post is a record of what
   * we believed on its date; where a claim has since turned out wrong, or the
   * thing it describes was renamed or never shipped, the note says so rather
   * than the post being quietly rewritten.
   */
  note?: string;
  content: string; // HTML
}

export const posts: BlogPost[] = [
  {
    slug: 'what-we-are-doing-now-2026-09',
    title: 'What We Are Doing Now: Fixing the Ground Before Building Higher',
    date: '2026-09-23',
    category: 'update',
    excerpt:
      'The next stretch of work is deliberately unglamorous: correct a 470-metre datum error, make map and building quality measurable, finish two large surveys, and prepare the OCR corpus that will make search useful. Here is what that means, and where people are still indispensable.',
    content: `
<p><strong>The Vietnam Map Archive is in a foundations pass.</strong> The visible ambitions have not changed: search the words printed inside historical maps, compare how the city changed, and let a person move through those changes on the ground. But the work immediately in front of us is more basic. Before building those surfaces higher, we are checking that the maps are in the right place, that a quality number means what it claims to mean, and that the catalogue maintains itself as it grows.</p>
<p>This turn came from experience rather than caution in the abstract. Recent work found an OCR run that could not read maps from one of our image hosts, a map overview with nearly a third of its area blank that still received a perfect machine score, and published sheets that drew nothing. The lesson is simple: a plausible result is not yet a trustworthy one.</p>

<h2>First: put the maps on the right ground</h2>
<p>The most urgent repair is <a href="/blog/two-map-series-2026-09">Series L7014</a>, the US Army Map Service survey of Vietnam at 1:50,000. Most of its live mosaic is about <strong>470 metres northwest</strong> of where it belongs. Its sheets use the Indian 1960 datum; one coordinate conversion silently left many of them unchanged.</p>
<p>The corrected rebuild now contains 436 sheets and has passed its geographic audit with no failures. That audit also found a separate Huế sheet 5.4 kilometres from its printed grid cell; a correctly placed duplicate has replaced it. What remains is to tile and upload the corrected mosaic, verify the delivered result, and only then retire the old one. The old build stays recoverable until the replacement has passed.</p>
<p>The same investigation found a second, quieter version of the problem. The rectangles used to show all 627 cells in the survey index—including sheets we do not hold—were drawn from the uncorrected datum too. They are not the map images, but they make the coverage diagram look convincingly wrong. Those rectangles will be rebuilt through the same tested conversion as the mosaic.</p>

<h2>Make quality measurable</h2>
<p>A map placed with three control points can report a perfect fit even when it is badly placed: three points determine an affine transformation exactly, leaving no independent evidence with which to test it. Eleven sheets still have that problem. Adding a fourth point to each will turn a mathematically inevitable zero into a residual we can actually inspect.</p>
<p>The same principle applies to shapes. We can ask a model to find buildings and parcels on an 1882 cadastral sheet, but today we have no complete hand-traced patch against which to measure false positives. A small block bounded by Rue Mac, Rue No. 15 and Rue Pellerin is almost complete: nine approved traces are already there, with roughly one or two features left for a person to confirm. Once that patch is exhaustive, we can report precision as well as recall. Until then, tuning the model would mostly be tuning our confidence.</p>

<h2>Finish surveys as surveys</h2>
<p>Two Indochine 1:100,000 surveys are next in the catalogue pipeline: Series 561, covering 1947–59, and Series 325, covering 1900–47. Together their indexes describe 340 grid cells. Thirty-four draft records have been created for Series 561; Series 325 has not started. Before the larger ingest continues, we are resolving the source licence and fixing the catalogue bookkeeping that currently recognises only 20 of those 34 drafts as held.</p>
<p>The earlier Indochine 1:25,000 survey is much further along. Of 207 known sheets, 205 now have a georeference. Sixty-two remain drafts because placement is not publication: a person still needs to look at each one, check that its image and tiles really render, and publish only those that pass.</p>

<h2>Then read what is printed inside them</h2>
<p>Search is thin because the source corpus is thin. Only six of 39 georeferenced sheets in the working set currently carry text extractions. The next OCR pass begins with human triage: mark the map frame, identify blank and water areas that should not consume a model call, then queue the prepared sheets. After the run, an alphabetical dictionary will make repeated errors—broken street names, truncated landmarks, or a bare “Rue”—visible in a way that reviewing one bounding box at a time does not.</p>
<p>That work feeds the public surfaces directly: searching a place name across maps, landing on the occurrence on the sheet, and connecting historical spellings to the gazetteer and the press archive. The goal is not merely more OCR. It is an extraction whose source, run and disagreements remain inspectable.</p>

<h2>Where help matters</h2>
<p>Several of these jobs cannot honestly be automated away. A human must decide whether the 1882 trace window is complete, inspect the 62 Tonkin sheets, place additional control points, and trace District 4 before we can measure its buildings across time. Those are not chores left over after the “real” technical work. They are the observations that make the technical work testable.</p>
<p>So that is what we are doing now: fewer new promises, more independent checks; correcting the ground beneath the archive, enlarging the evidence, and recording failure as carefully as success. The next public features will be better for the pause—and, more importantly, we will be able to say how we know.</p>
`,
  },
  {
    slug: 'two-map-series-2026-09',
    title: 'Two Map Series, 536 Sheets: Vietnam at 1:50,000 and 1:25,000 (1903–1989)',
    date: '2026-09-14',
    category: 'announcement',
    excerpt:
      "The archive now holds surveys, not just sheets. Two of them go onto the map as one row each — the US Army's Series L7014, 461 of its 627 sheets, and the French Indochine 1:25,000 of Tonkin, now 75 of its 79 — with a public page for every sheet a survey contains, held or not. The search box now takes the grid reference those sheets were written in — and the larger of the two surveys is, as we write this, drawn 470 metres out of place.",
    content: `
<p><strong>461 map sheets went onto the map this week</strong>, and 28 more of a second survey behind them: 94 georeferenced sheets eight days ago, 583 today. The 461 are one survey — the US Army Map Service's <strong>Series L7014</strong>, Vietnam at 1:50,000, published 1963 to 1989, at a scale where individual villages, roads and river bends are drawn.</p>
<p>And the archive learned what a <em>series</em> is, which is the part that will matter longer. Two surveys are now one row each in the layer panel — L7014, and the French <strong>Indochine 1:25,000 of Tonkin and Thanh Hóa</strong> (1903–27), which has been here since May as separate rows to add one at a time — 53 of them a week ago, 84 today. Tap a row and the whole survey goes on the map with one opacity slider for all of it.</p>
<p>A link can do the tapping: <a href="/explore?series=l7014#@16.1,107.2,5.7z,0r">Series L7014 over the whole country</a> · <a href="/explore?series=indochine-1-25-000-tonkin-thanh-hoa#@20.65,106.10,8.2z,0r">the Indochine 1:25,000 over the Tonkin delta</a>.</p>

<figure>
  <a href="/explore?series=l7014#@16.1,107.2,5.7z,0r">
  <img
    src="/images/blog/l7014-series-on-map.webp"
    alt="Vietnam seen from above with the AMS L7014 topographic sheets drawn over it as a quilt of small square scans — dense across the Tonkin delta in the north, running down the Annamite coast, and filling the Mekong delta in the south, with blank ground inland where the archive holds no sheet."
    loading="lazy"
    width="1000"
    height="1084"
  />
  </a>
  <figcaption><strong>One row, 461 sheets.</strong> <a href="/explore?series=l7014#@16.1,107.2,5.7z,0r">Open it on the map →</a> Each small square is a single 15′ × 15′ sheet, warped and drawn at its own place on the ground. The breaks in the quilt are sheets the archive does not hold — most of them over Laos and Cambodia, which the survey also covers.</figcaption>
</figure>

<h2>Two surveys, opposite routes</h2>
<p>L7014 is <strong>pre-tiled</strong>. The Perry-Castañeda Library publishes its sheets as GeoPDFs carrying their own georeference — control points, the printed neatline, the edition and date — so a script clips each sheet to its neatline, warps it, and tiles the series into one raster archive we host. Where two sheets were warped the same way their edges agree to between 2.5 and 14 metres, inside the series' own drafting accuracy, and what you notice at such a seam is a difference in scan brightness rather than in geometry. <em>Warped the same way</em> turned out to be load-bearing — see below.</p>
<p>Tonkin is <strong>warped live</strong>, by Allmaps, in your browser, from 84 ordinary archive records covering 75 of the survey's 79 grid cells. That should be 84 times the work and is not: a warped-map layer is a <em>set</em> of georeferenced maps rather than one, so the whole survey costs one layer, one position in the stack and one opacity control — no pipeline, no multi-gigabyte archive, no rebuild when a sheet is added. Which is how it went from 53 cells to 75 in a single day, with nothing to rebuild and nothing to redeploy.</p>
<p>Those 22 cells arrived as <strong>half-sheets</strong>. Most of this survey was issued as two sheets cut down the middle meridian of the cell, and on that cut edge there is no printed frame to measure from — no thick neatline, no thin companion, no graticule band, just paper and one hair-thin rim line. The detector that places these sheets anchors on the thick line, so every half-sheet had failed it. It now takes the rotation from the other three sides (that is a property of how the scan was laid on the glass, not of any one edge), averages down the whole span until the one line running the full height stands out of the map content, and reads the missing edge off the survey's own lattice — then checks that derivation by whether the sheet comes out the right shape. 17 sheets placed with no human clicking a corner, their two ground scales agreeing to between 0.01% and 1.11%.</p>
<p>Which route a survey takes is decided by what the source library published. L7014 <em>had</em> to be pre-tiled, because most of its sheets are not archive records at all; Tonkin did not, because all of its are.</p>

<h2>The hole over Saigon</h2>
<p>Of the 535 L7014 sheets that library scanned, <strong>24 are plain JPEGs with no georeference attached</strong> — and they are, with some irony, exactly the ones over Saigon, Biên Hòa, Cần Giờ, Huế, Đà Nẵng and Hải Phòng. The cities. So the mosaic has a hole punched in it precisely where most people will look first.</p>
<p>Those 24 are being placed by hand, four clicks a sheet, and become normal archive records as they are done — nine so far. One row adds both halves, mosaic underneath and hand-placed city sheets on top, because they are complementary rather than alternative. Offered as two rows they would read as a choice between two things, and picking either would be wrong.</p>

<h2>And the mosaic is in the wrong place</h2>
<p>Now the part that is not an announcement, because it is the kind of thing an archive should say out loud rather than fix quietly: <strong>most of the L7014 mosaic you can put on the map right now sits about 470 metres northwest of where it belongs.</strong> The fix is written and tested; the rebuilt archive has not been uploaded yet.</p>
<p>These sheets print their graticule on <strong>Indian 1960</strong>, a datum that differs from WGS 84 by roughly 470 m of ground here. 336 of the GeoPDFs declare it, and the warp duly asked PROJ to convert. For a point outside the partial area of use of the transformation PROJ picked, it returns the coordinate <em>unchanged</em> and reports success — so 285 sheets were written out with no shift applied, and nothing anywhere failed. The one check that should have caught it structurally could not: it compares the sheet's control points against the graticule the sheet itself prints, and when the datum is wrong both sides move together. On one sheet it scores an error of 0.000000000002.</p>
<p>What found it was the seams. Over all 750 adjacent joins in the live archive the median is 19 m — but <strong>56 are over 300 m</strong>, which is where a shifted sheet meets an unshifted one, and <strong>every one of the 33 joins where a hand-placed city sheet meets the mosaic measures 447–504 m</strong>. A seam is the cheapest measurement in this whole pipeline: it needs no outside data at all, only two sheets that claim to share an edge. Four sheets would not have been enough to see a fault that splits the series 285 against 151.</p>
<p>The repair is to stop asking the sheet. The warp now lays the neatline down under both readings — the declaration, and Indian 1960 with the shift spelled out by hand — and keeps whichever one lands on the sheet's own printed 15′ cell, refusing a sheet that misses on both rather than quietly taking the nearer miss. The candidates are ~470 m apart and the lattice is good to ~15 m, so the choice is never close. Across all 437 sheets the median miss goes from 430 m to 0 m, p95 9 m, worst 115 m. The hand-placed city sheets were never affected — their own control points fit to 2.3–19.0 m — so until the archive is re-warped, the step you can see where a city sheet meets the mosaic is the mosaic moving, not the city sheet.</p>
<p>None of this was visible in the picture. It looked like a map of Vietnam either way.</p>

<h2>The same 470 metres, typed into a search box</h2>
<p>The location search took a place name. It now also takes the thing these sheets were actually written in:</p>
<p><code>XS 8965 4123</code> &nbsp;·&nbsp; <code>48Q XD 850 418</code> &nbsp;·&nbsp; <code>YD 850 418</code></p>
<p>That is a military grid reference, and it is the coordinate of the war — what the sheets print in their margin, and what every after-action report, unit history and memoir quotes. It is also the same trap as the mosaic, seen from the reader's side: a wartime grid uses the lettering of modern MGRS and different numbers, because it is a UTM grid on Indian 1960. Typed into anything that assumes WGS 84 it resolves to a point roughly 480 m east-southeast — on the map, in the right neighbourhood, four blocks from what the reference meant, with nothing anywhere saying so.</p>
<p>So a grid reference returns <em>two</em> results rather than one, labelled, wartime reading first: <strong>Indian 1960</strong>, <em>as printed on US Army sheets</em>, then <strong>WGS 84</strong>, <em>modern GPS datum</em>. The archive cannot know which sheet a reference was copied off, and choosing on the reader's behalf would be the same error with better manners.</p>
<p>Two things make it usable off the page rather than off a conversion table. <strong>The letters carry the zone</strong>, so the bare reference works: the three column-letter sets are disjoint, and Vietnam is 1,683 km tall against a 2,000 km row cycle, so within this country a bare grid is unambiguous — and the zone is written back into the result, so you can see what was assumed. <strong>The digit count is precision, not decoration</strong>: four figures name a 1 km square, six a 100 m square, ten a 1 m square, and the camera lands on the square rather than on a point the reference never claimed.</p>
<p>It is pinned against squares the historical record fixes independently — Saigon is XS, Khe Sanh XD, the Ia Drang YA, Huế YD, Đà Nẵng BT — because a one-off in the row offset moves every decoded reference exactly 100 km, which reads as a different bug entirely. Then the decode itself, against a place whose position is known from outside this archive: <code>48Q XD 850 418</code> lands <strong>205 m</strong> from the Khe Sanh combat base on Indian 1960 and <strong>377 m</strong> from it read as WGS 84, the two readings 526 m apart.</p>
<p>Decimal degrees, DMS and bare UTM are taken too. A DMS pair is offered on the sheet datum as well, because that is how a printed graticule reads; a bare decimal pair is not, because it came off a phone.</p>

<h2>A page for the sheets we do not have</h2>
<p>A count of what the archive holds is only half a fact. "9 sheets" means one thing if the survey has 12 and quite another if it has 627.</p>
<p>So each survey's own printed index is imported as its denominator, and every series has a public coverage page: one row per sheet the survey contains, held or not, in three states — <strong>held</strong>, <strong>scan identified but not yet fetched</strong>, and <strong>no known scan</strong>. Every sheet has a URL whether or not we have it. A researcher after one specific sheet can find out that it exists, what it is numbered, and that we do not hold it.</p>

<figure>
  <a href="/catalog/series/series-l7014-vietnam-1-50-000">
  <img
    src="/images/blog/l7014-coverage-page.webp"
    alt="The coverage page for Series L7014: a heading reading 627 sheets, catalogued 1966 to 1984, then a Coverage card saying the archive holds 461 of this survey's 627 sheets — 74 per cent — above a three-colour bar and a table of sheet numbers, names, status and source."
    loading="lazy"
    width="1400"
    height="910"
  />
  </a>
  <figcaption><strong>What the survey contains, not what we hold.</strong> 461 held, 123 whose scans are identified at Texas Tech but not yet fetched, 43 with no known scan anywhere. <a href="/catalog/series/series-l7014-vietnam-1-50-000">The whole table →</a> The Indochine 1:25,000's <a href="/catalog/series/indochine-1-25-000-tonkin-thanh-hoa">own page</a> now reads 75 held of 79 — the last four, Phu-Vinh-Tuong, Phuc-Yên, Phù-Lô and Hà-Dông, have no digitised copy at IGN, CartoMundi or Gallica.</figcaption>
</figure>

<p>Building those indexes turned up the usual archival mess. The Texas library publishes L7014 twice — a flat alphabetical list and a clickable index diagram — and <em>neither is complete</em>: the flat page is missing two sheets immediately north of Saigon, the diagram is missing thirty-seven the flat page has, and the prose on one misprints two sheet numbers. The index is read from both and merged, and where the printed number and the filename disagree, the filename wins.</p>
<p>The Indochine survey's denominator came from elsewhere: <a href="https://www.cartomundi.fr/">CartoMundi</a>, the Aix-Marseille catalogue of European map series, which says that survey is <strong>79 sheets</strong>. We now hold 75 of them, all published and drawn. The remaining four are not a georeferencing problem: probed against IGN's deposit, CartoMundi and Gallica, none of the three has a digitised copy, so going further means finding another holding library. Reading its catalogue also turned up <strong>25 further Indochina series</strong> — Cochinchine and Annam at 1:25,000, the Tonkin delta, the 1:100,000 of Indochina — now leads in the review queue rather than a list in someone's notes.</p>
<p>One decision worth recording: what counts as a series is a database question, not a file someone edits. Three rules, all read off the data — the sheets carry a sheet number, more than one is georeferenced, and this reader may see them. Adding a survey means ingesting sheets. Nothing is deployed.</p>

<h2>Credit where it is due</h2>
<p>The archive scanned none of these sheets. It placed them, counted them and put them on one row; the paper, the cameras and the cataloguing were other people's work, most of it given away for nothing.</p>
<ul>
<li><strong><a href="https://maps.lib.utexas.edu/maps/topo/vietnam/">Perry-Castañeda Library Map Collection</a>, University of Texas at Austin</strong> — scanned Series L7014 and published it openly, most sheets as GeoPDFs carrying their own control points. 452 of the 461, and the reason the mosaic exists.</li>
<li><strong>The Virtual Vietnam Archive, Vietnam Center and Sam Johnson Vietnam Archive, Texas Tech University</strong> — holds scans of 123 sheets the Texas collection never published. The yellow band on the coverage bar, and the next thing to fetch.</li>
<li><strong><a href="https://www.ign.fr/">IGN</a>, France's national mapping agency, via its <a href="https://nakala.fr/">Nakala</a> deposit</strong> — photographed the Indochine 1:25,000. Every one of our 84 sheets is its scan: 22 fetched from Nakala directly, and 62 assembled by someone else from its two printed half-sheets, which we established by the blue pencil and the library stamp on the paper rather than by arithmetic. All 84 are CC BY 4.0 in IGN's name. Who did the assembling we still do not know; if it was you, you are owed a line here too.</li>
<li><strong><a href="https://www.cartomundi.fr/">CartoMundi</a> (Aix-Marseille Université)</strong> — the catalogue that tells us the Indochine 1:25,000 is 79 sheets rather than however many we happen to hold.</li>
<li><strong><a href="https://allmaps.org/">Allmaps</a></strong> — open-source georeferencing and in-browser warping. The Tonkin series draws through it live, with no pipeline of ours involved.</li>
<li><strong>OpenStreetMap contributors</strong>, via <strong><a href="https://protomaps.com/">Protomaps</a></strong> — the modern map underneath, which is what makes a 1966 sheet checkable rather than merely pretty.</li>
</ul>
<p>Series L7014 is a US Army Map Service product and carries no copyright. Where a holding library's terms apply, they are recorded on the sheet's own catalogue page.</p>
		`,
  },
  {
    slug: 'measuring-the-ocr-2026-09',
    title: 'The Gate That Could Not Read Vietnamese, and the One Printed on the Sheet Itself',
    date: '2026-09-10',
    category: 'research',
    excerpt:
      'A fix that recovered a third more street names moved every number on our official quality gate by exactly zero. So we built a new gate out of the street directory the sheets already print — free ground truth, no human labelling — and it immediately found a published, georeferenced sheet that had never really been read.',
    content: `
<p>This is a post about measurement rather than about a model. The reading itself is in decent shape; what was broken was our ability to tell.</p>

<h2>What "reading a sheet" actually involves</h2>
<p>A scanned city plan arrives as one enormous photograph — the 1959 <em>Đô thành Sài Gòn</em> sheet is about 13,000 pixels across. Nothing reads that whole. It gets cut into tiles and read a strip at a time, and either side of that sit two steps that need a person: someone accepting the crop before any money is spent, and someone accepting the labels afterwards.</p>

<figure>
  <div class="fig-plate">
    <svg viewBox="0 0 700 650" role="img" aria-label="Nine steps from scanned sheet to published label: scan, layout pass, triage by a person, job queued, body pass, tidy up, the extractions table, review by a person, and publication.">
      <defs>
        <marker id="bp-ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
          <path class="f-head" d="M 0 1 L 10 5 L 0 9 z"></path>
        </marker>
      </defs>

      <text class="f-t f-lane" x="14" y="14">FROM PHOTOGRAPH TO SEARCHABLE NAME</text>

      <text class="f-t f-num" x="42" y="58" text-anchor="end">1</text>
      <rect class="f-box-quiet" x="60" y="24" width="600" height="52" rx="3"></rect>
      <text class="f-t f-title" x="76" y="47">The scanned sheet</text>
      <text class="f-t f-sub" x="76" y="64">One photograph, roughly 13,000 pixels across. Too big to read whole.</text>

      <text class="f-t f-num" x="42" y="124">2</text>
      <rect class="f-box" x="60" y="90" width="600" height="52" rx="3"></rect>
      <text class="f-t f-title" x="76" y="113">Layout pass</text>
      <text class="f-t f-sub" x="76" y="130">One low-resolution look: where is the map, the legend, the inset, the street directory?</text>
      <text class="f-t f-lab f-red" x="644" y="113" text-anchor="end">MACHINE · $0.01</text>

      <text class="f-t f-num" x="42" y="190">3</text>
      <rect class="f-box f-box-person" x="60" y="156" width="600" height="52" rx="3"></rect>
      <text class="f-t f-title" x="76" y="179">Triage</text>
      <text class="f-t f-sub" x="76" y="196">A person accepts the crop and the tile grid. Nothing is queued without this.</text>
      <text class="f-t f-lab f-blue" x="644" y="179" text-anchor="end">PERSON</text>

      <text class="f-t f-num" x="42" y="256">4</text>
      <rect class="f-box-quiet" x="60" y="222" width="600" height="52" rx="3"></rect>
      <text class="f-t f-title" x="76" y="245">The job waits</text>
      <text class="f-t f-sub" x="76" y="262">Pressing Run OCR writes a row in a queue. A worker somewhere has to pick it up.</text>

      <text class="f-t f-num" x="42" y="322">5</text>
      <rect class="f-box" x="60" y="288" width="600" height="52" rx="3"></rect>
      <text class="f-t f-title" x="76" y="311">The body pass</text>
      <text class="f-t f-sub" x="76" y="328">One call per row of tiles. Each label comes back as text, a box, an angle and a kind.</text>
      <text class="f-t f-lab f-red" x="644" y="311" text-anchor="end">MACHINE · $$</text>

      <text class="f-t f-num" x="42" y="388">6</text>
      <rect class="f-box" x="60" y="354" width="600" height="52" rx="3"></rect>
      <text class="f-t f-title" x="76" y="377">Tidy up</text>
      <text class="f-t f-sub" x="76" y="394">Merge the same label read twice on two overlapping tiles. Free — no model call.</text>

      <text class="f-t f-num" x="42" y="454">7</text>
      <rect class="f-box-quiet" x="60" y="420" width="600" height="52" rx="3"></rect>
      <text class="f-t f-title" x="76" y="443">The table</text>
      <text class="f-t f-sub" x="76" y="460">One row per label, each carrying its position on the full sheet.</text>

      <text class="f-t f-num" x="42" y="520">8</text>
      <rect class="f-box f-box-person" x="60" y="486" width="600" height="52" rx="3"></rect>
      <text class="f-t f-title" x="76" y="509">Review</text>
      <text class="f-t f-sub" x="76" y="526">A person validates, corrects or rejects, row by row. This is the slow step.</text>
      <text class="f-t f-lab f-blue" x="644" y="509" text-anchor="end">PERSON</text>

      <text class="f-t f-num" x="42" y="586">9</text>
      <rect class="f-box" x="60" y="552" width="600" height="52" rx="3"></rect>
      <text class="f-t f-title" x="76" y="575">On the map</text>
      <text class="f-t f-sub" x="76" y="592">Searchable labels, a page per place name, links to the traced shapes underneath.</text>

      <line class="f-line" x1="360" y1="76" x2="360" y2="88" marker-end="url(#bp-ar)"></line>
      <line class="f-line" x1="360" y1="142" x2="360" y2="154" marker-end="url(#bp-ar)"></line>
      <line class="f-line" x1="360" y1="208" x2="360" y2="220" marker-end="url(#bp-ar)"></line>
      <line class="f-line" x1="360" y1="274" x2="360" y2="286" marker-end="url(#bp-ar)"></line>
      <line class="f-line" x1="360" y1="340" x2="360" y2="352" marker-end="url(#bp-ar)"></line>
      <line class="f-line" x1="360" y1="406" x2="360" y2="418" marker-end="url(#bp-ar)"></line>
      <line class="f-line" x1="360" y1="472" x2="360" y2="484" marker-end="url(#bp-ar)"></line>
      <line class="f-line" x1="360" y1="538" x2="360" y2="550" marker-end="url(#bp-ar)"></line>

      <text class="f-t f-sub" x="14" y="634">A blue edge marks a step that needs a person. Steps 2 and 5 are the only ones that cost money.</text>
    </svg>
  </div>
  <figcaption><strong>The pipeline, nine steps.</strong> Two of them are human. The one that scales with cost is step 5, and how finely the sheet was cut up in step 3 decides what step 5 can see.</figcaption>
</figure>

<h2>What the output actually looks like</h2>
<p>Here is one tile of the 1959 sheet — about a square kilometre of Chợ Lớn — with every label the pass returned drawn over it. The sheet is printed in red, so the machine's marks are in blue.</p>

<figure>
  <img
    src="/images/blog/ocr-1959-labels-tile.jpg"
    alt="One tile of the 1959 Đô thành Sài Gòn sheet with 161 OCR label boxes drawn over it in blue: 70 thick boxes around assembled street names such as Đường Nguyễn Trãi and Đại Lộ Hùng Vương, and 91 thin boxes around single-word fragments."
    loading="lazy"
    width="1080"
    height="1080"
  />
  <figcaption><strong>161 labels on one tile.</strong> The 70 thick boxes are assembled names — <em>Đường Nguyễn Trãi</em>, <em>Đại Lộ Hùng Vương</em>, <em>Đại Lộ Đồng Khánh</em>. The 91 thin ones are single words: a street name set along its own street, broken by the buildings drawn across it, and returned in pieces. Both are counted, and telling them apart is most of what "quality" means here.</figcaption>
</figure>

<h2>The gate that moved by zero</h2>
<p>Our official quality gate is 85 labels a person checked by hand, on one 1882 French sheet. Every core change to the pipeline has been scored against it, and it has correctly rejected two changes that made things worse — including, last month, a prompt fix that was itself correct.</p>
<p>Then we fixed a deduplication bug. The merge step had been quietly deleting real streets: <em>Lê Lợi</em>, <em>Hàm Nghi</em>, <em>Công Lý</em> and <em>Phan Chu Trinh</em> — four of the most prominent streets on the 1959 sheet — were simply not in the database, while the row count looked entirely healthy. Fixing it recovered a third more distinct names.</p>
<p>Re-scored on the gate, that fix moved recall, character accuracy, box overlap and category accuracy by <strong>exactly zero</strong>.</p>
<p>It could not have done otherwise. <em>Rue Catinat</em> and <em>Rue Charner</em> survive a character comparison; <em>Đại Lộ Lê Lợi</em> and <em>Đại Lộ Lê Lai</em> differ by one letter and a diacritic. A gate built on one French sheet cannot see a Vietnamese failure, and for a year we had been steering by it.</p>

<h2>The gate the sheets print themselves</h2>
<p>The replacement was already on the paper. Many of these sheets print their own street directory in the margin: every street name, and the grid square it sits in. That is ground truth, written by the surveyors, and it costs about three cents to read.</p>
<p>Two numbers come out of comparing it to what the body pass found. <strong>How many of the names the sheet says it prints did we actually read?</strong> And <strong>of those, how many sit in the square the index claims?</strong> The second is worth having because it is two unrelated readings of one sheet checking each other — it scores the body pass, the index pass and the printed grid at once.</p>
<p>Same dedupe fix, seen by the new gate: names found rose from <strong>0.7493 to 0.7947</strong> — both a three-run vote merge, the highest-confidence score the gate produces for a sheet. It saw what the old gate structurally could not.</p>
<p>Then we pointed it at a second sheet.</p>

<figure>
  <div class="fig-plate">
    <svg viewBox="0 0 700 300" role="img" aria-label="On the 1959 sheet, a single pass found 267 of 375 printed street names. On the 1968 sheet, a first pass found 9 of 367; a finished pass found 120.">
      <text class="f-t f-lane" x="14" y="16">OF THE STREET NAMES A SHEET PRINTS, HOW MANY DID WE READ?</text>

      <text class="f-t f-title" x="14" y="46">1959 Đô thành Sài Gòn</text>
      <rect class="f-quiet" x="170" y="56" width="490" height="24" rx="2"></rect>
      <text class="f-t f-lab" x="163" y="72" text-anchor="end">printed</text>
      <text class="f-t f-sub" x="668" y="72" text-anchor="end">375</text>
      <rect class="f-green" x="170" y="86" width="349" height="24" rx="2"></rect>
      <text class="f-t f-lab" x="163" y="102" text-anchor="end">read</text>
      <text class="f-t f-title f-green" x="527" y="103">267 · 71%</text>
      <text class="f-t f-sub" x="170" y="120">single pass — the three-run vote merge for this sheet reads 79%</text>

      <line class="f-hair" x1="14" y1="140" x2="686" y2="140"></line>

      <text class="f-t f-title" x="14" y="168">1968 Sài Gòn</text>
      <rect class="f-quiet" x="170" y="178" width="480" height="24" rx="2"></rect>
      <text class="f-t f-lab" x="163" y="194" text-anchor="end">printed</text>
      <text class="f-t f-sub" x="658" y="194" text-anchor="end">367</text>
      <rect class="f-red" x="170" y="208" width="12" height="24" rx="2"></rect>
      <text class="f-t f-lab" x="163" y="224" text-anchor="end">before</text>
      <text class="f-t f-title f-red" x="190" y="225">9 · 2.5%</text>
      <rect class="f-green" x="170" y="238" width="157" height="24" rx="2"></rect>
      <text class="f-t f-lab" x="163" y="254" text-anchor="end">now</text>
      <text class="f-t f-title f-green" x="335" y="255">120 · 32.7%</text>

      <text class="f-t f-sub" x="14" y="281">Both sheets are published and georeferenced. 1968's two bars are the same sheet, before and after this week's finished pass.</text>
    </svg>
  </div>
  <figcaption><strong>The 1968 sheet has gone from effectively unread to partly read.</strong> It held only 14 body labels before this week, which is why just 9 of 367 names turned up at all. 1959's bar here is its single-pass score, not the three-run merge quoted above — comparing sheets means comparing runs measured the same way.</figcaption>
</figure>

<p>A pass finished on the 1968 sheet this week. The first number — how many of the 367 printed names did we actually read — rose from 0.0245 to <strong>0.3270</strong>: 120 names, up from 9. The second number, whether a found name sits in the square the index claims, holds at <strong>0.9603</strong> at ±1 cell, on the 151 labels the two sources could be matched against. Recall is flat across the sheet too — 0.19–0.46 by row, 0.22–0.62 by column — which is worth a sentence on its own: it rules out a bad crop or a wrong tile priority as the explanation, since either would show up as a hole in one place, not a shortfall spread everywhere.</p>
<p>One caveat, and one that turned out not to be. The region the tile grid crops to covers only 80.7% of the printed reference grid, so part of what the directory indexes was never tiled — though when we later tiled that missing band on purpose, it returned two names for a fifth of a dollar, the worst value on the sheet. The other caveat was mine and it was wrong: I wrote that the sheet prints two street-name blocks and that only one had been read, so the denominator was partial and flattered the score. The second block is not a street directory at all. It is headed <em>Guide to Numbered Features</em> — 244 hospitals, ministries, markets and embassies, indexed by number. The street directory is the other block, and it had been read whole: its four printed columns span the read windows exactly, and the one band that came back empty is a short column that genuinely ends early. So 0.327 was measured against a complete denominator, and it flatters nothing.</p>
<p>Which is worth saying plainly, because it is the same mistake in the other direction. I had assumed a number was too generous and went looking for the missing half of its denominator; there wasn't one. Folding that second block in would have made the figure <em>worse</em> founded, not better — predictions are filtered to streets and waterways, so 244 institution names would have entered the denominator unmatchable and printed 0.196 while nothing about the read had changed. A gate can be wrong by being too harsh, and a caveat you cannot check is not humility.</p>
<p>What did move the number was ground per call. Holding everything else fixed and cutting the tile from 1120 px to 800 — 1427 metres of city per call down to 1019 — took name recall from 0.365 to <strong>0.418</strong> over the same rectangle, and distinct street names from 127 to 171, a third more. About nine cents per additional name. All three passes together read <strong>146 of the 367</strong> printed names. Recall stayed flat across the sheet, so the finer grid lifted the whole thing rather than filling in a hole.</p>

<h2>Accuracy was never the problem</h2>
<p>Of the labels the model does return, the quality is fine. Against the 85 hand-checked ones, running the sheet twice on offset tile grids and merging by vote reads:</p>

<div class="table-wrap">
  <table>
    <thead>
      <tr><th>What is measured</th><th>Result</th><th>Read it as</th></tr>
    </thead>
    <tbody>
      <tr><td>Labels found, loose box</td><td class="n">0.906</td><td>90.6% of the checked labels were found</td></tr>
      <tr><td>Labels found, tight box</td><td class="n">75 / 85</td><td>The gap is box tightness, not missed words</td></tr>
      <tr><td>Character accuracy</td><td class="n">0.979</td><td>Two characters wrong in a hundred</td></tr>
      <tr><td>Kind of thing (street, building, …)</td><td class="n">0.880</td><td>Most errors are building versus institution</td></tr>
      <tr><td>Angle of the lettering</td><td class="n">3.49°</td><td>Good enough to draw with</td></tr>
      <tr><td>Precision</td><td class="n">—</td><td>Deliberately ignored; see below</td></tr>
    </tbody>
  </table>
</div>

<p>Precision is uninterpretable here and it is worth saying why. The checked list is a <em>partial</em> sample of the labels on the sheet, so a correct reading that happens to be missing from it counts as an error. Anything that raises recall lowers precision. We do not tune against it, and a drop in it is not a regression.</p>
<p>The one accuracy result that does look like a real defect is a single sheet losing its accents. Vietnamese sheets keep 76–100% of their diacritics, French sheets run 23–42% — and the 1895 sits at 8–14%, on the same model, the same prompt and the same language as its three neighbours.</p>

<figure>
  <div class="fig-plate">
    <svg viewBox="0 0 700 240" role="img" aria-label="Diacritic retention by sheet: the two Vietnamese sheets run 0.76 to 1.00, three French sheets run 0.23 to 0.42, and the 1895 French sheet sits alone at 0.08 to 0.14.">
      <text class="f-t f-lane" x="14" y="16">SHARE OF ACCENTS KEPT, BY SHEET</text>

      <line class="f-hair" x1="150" y1="34" x2="150" y2="196"></line>
      <line class="f-hair" x1="277" y1="34" x2="277" y2="196"></line>
      <line class="f-hair" x1="405" y1="34" x2="405" y2="196"></line>
      <line class="f-hair" x1="532" y1="34" x2="532" y2="196"></line>
      <line class="f-hair" x1="660" y1="34" x2="660" y2="196"></line>

      <rect class="f-green" x="558" y="46" width="102" height="14" rx="7"></rect>
      <text class="f-t f-lab" x="143" y="57" text-anchor="end">1959 · Vietnamese</text>

      <rect class="f-green" x="538" y="72" width="122" height="14" rx="7"></rect>
      <text class="f-t f-lab" x="143" y="83" text-anchor="end">1968 · Vietnamese</text>

      <rect class="f-blue" x="308" y="98" width="56" height="14" rx="7"></rect>
      <text class="f-t f-lab" x="143" y="109" text-anchor="end">1882 · French</text>

      <rect class="f-blue" x="303" y="124" width="41" height="14" rx="7"></rect>
      <text class="f-t f-lab" x="143" y="135" text-anchor="end">1942 · French</text>

      <rect class="f-blue" x="267" y="150" width="92" height="14" rx="7"></rect>
      <text class="f-t f-lab" x="143" y="161" text-anchor="end">1923 · French</text>

      <rect class="f-red" x="191" y="176" width="31" height="14" rx="7"></rect>
      <text class="f-t f-lab f-red" x="143" y="187" text-anchor="end">1895 · French</text>
      <text class="f-t f-sub f-red" x="232" y="187">alone, and unexplained</text>

      <text class="f-t f-lab" x="150" y="212" text-anchor="middle">0</text>
      <text class="f-t f-lab" x="277" y="212" text-anchor="middle">0.25</text>
      <text class="f-t f-lab" x="405" y="212" text-anchor="middle">0.50</text>
      <text class="f-t f-lab" x="532" y="212" text-anchor="middle">0.75</text>
      <text class="f-t f-lab" x="660" y="212" text-anchor="middle">1.0</text>
      <text class="f-t f-sub" x="14" y="234">Each bar is the range measured across that sheet's runs. Diacritics track the sheet's language, hard — not the run.</text>
    </svg>
  </div>
  <figcaption><strong>One sheet against three controls.</strong> A single anomaly with the variables held still is the most useful kind of lead. It may turn out to be scan quality rather than anything in the model.</figcaption>
</figure>

<h2>The real state of the archive's text</h2>
<p>Which brings us to the finding that matters. Reading is accurate; coverage is largely unmeasured. Of the 39 published sheets, seven print a directory, and two of those have had it read.</p>

<figure>
  <div class="fig-plate">
    <svg viewBox="0 0 700 140" role="img" aria-label="Of 39 published sheets, 2 have a measured score, 5 print a directory that has not been read yet, and 32 print none at all.">
      <text class="f-t f-lane" x="14" y="16">39 PUBLISHED SHEETS · CAN WE SCORE THEM?</text>

      <rect class="f-green" x="20" y="30" width="34" height="34"></rect>
      <rect class="f-ochre" x="54" y="30" width="85" height="34"></rect>
      <rect class="f-quiet" x="139" y="30" width="541" height="34"></rect>

      <rect class="f-green" x="20" y="86" width="11" height="11"></rect>
      <text class="f-t f-title" x="38" y="96">2 scored</text>
      <text class="f-t f-sub" x="38" y="112">71% and 33%</text>

      <rect class="f-ochre" x="230" y="86" width="11" height="11"></rect>
      <text class="f-t f-title" x="248" y="96">5 one step away</text>
      <text class="f-t f-sub" x="248" y="112">they print a directory; about $0.03 each to read</text>

      <rect class="f-quiet" x="496" y="86" width="11" height="11"></rect>
      <text class="f-t f-title" x="514" y="96">32 unknowable</text>
      <text class="f-t f-sub" x="514" y="112">no printed index — no denominator</text>
    </svg>
  </div>
  <figcaption><strong>The coverage gap.</strong> A sheet with no printed directory can still be read — it just cannot be graded without a person sitting down and checking labels by hand, which is exactly the cost the new gate was built to avoid.</figcaption>
</figure>

<p>So the work in front of us is not a better prompt. It is five index reads on the sheets that have a printed directory and no score, finishing the fine-grid pass on the 1968 sheet, and a review queue that stands at 2 accepted rows out of 1,663 on the 1959 sheet. Two items that were on this list when it was written are off it now, both because they were measured: the second street-name block does not exist, and the wider crop is real geometry worth two names.</p>

<h2>Two things we got wrong along the way</h2>
<p>The row count. It was the number we watched, and it is the number that hid the bug: a wrong merge removes a name while a shattered label adds rows, and both move the total in a direction that looks fine. The 1959 sheet held 452 street rows and 367 distinct names against a printed claim of 384 — a good-looking result with four of the city's main avenues missing from it. Count distinct names, never rows.</p>
<p>And the cleanup. Getting to the numbers above meant deleting 627 superseded rows from the live table. Human review decisions were carried across first — 26 of 60 transferred, the other 34 being rejections of duplicate numerals the new run no longer produces — and the full pre-change snapshot is on disk, so it is reversible. It was still a destructive write made without pausing to ask.</p>
		`,
  },
  {
    slug: 'routes-design-ocr-2026-09',
    title: 'Sixteen Pages, One Palette, and an OCR Change That Failed Its Own Test',
    date: '2026-09-08',
    category: 'update',
    excerpt:
      'Twenty-three pages merged into sixteen with modes as query params, a palette taken off the sheets themselves plus a dark theme, a front page that plays the pipeline as a live map, and an OCR prompt that measured worse than the one it replaced — so it was rejected.',
    content: `
<p>Four weeks of work, one post. The first three items are cleanup a reader might notice; the fourth is the one worth reading.</p>

<h2>Twenty-three pages became sixteen</h2>
<p>The tools had accumulated a route each — a page for browsing, a page for annotating, a page for authoring a story, four more for the image-space work. Modes are now query params on two pages: <code>/explore?mode=browse|annotate|story</code> and <code>/scan?mode=inspect|triage|trace|review</code>.</p>
<p>The grouping is by <em>shell</em> rather than by verb, which is the whole point. /explore is the surface with a geographic map on it; /scan is the surface with a scanned image on it. Switching modes inside one of them keeps the OpenLayers map, the basemap source and the warped tiles alive instead of tearing them down and rebuilding them. Every retired path 301s, so old links and bookmarks still land. The three admin pages became one console with tabs, and <code>/directory</code> now lists every page in the app from the same list the command palette reads, so adding a page means adding one row.</p>

<h2>One design system, and a dark theme</h2>
<p>The app had two palettes: a warm one for the editorial pages and a cool, bright one that the map sidebars had inherited from an earlier pass. They now come from one set of tokens taken off the sheets themselves — plate tones, paper and ink. Emoji iconography is gone, buttons are one system rather than four, and the map tools use the same inks as the pages.</p>
<p>Dark mode is written as <code>light-dark(light, dark)</code> on every colour token, so there is one value per ink and no second theme to drift out of step. Four things deliberately do not flip: the yellow surfaces, the ink slab under the footers, and the plates that pin a subtree to its light face. Contrast is asserted in a test against the token file rather than eyeballed, because a dark theme fails quietly — the page still renders, it just cannot be read.</p>

<h2>The front page is a live map now</h2>
<p>It plays the pipeline in five beats: the modern city, the 1882 cadastral sheet warping over it, the 46 shapes traced off that sheet, the labels a person has checked, then the masthead. It is the archive demonstrating itself rather than a screenshot claiming to.</p>
<p>Three things keep a decorative map from costing what a tool costs: it renders at pixel ratio 1 (at a Retina screen's own ratio OpenLayers asks for about four times the tiles), it is skipped entirely when the browser reports a metered connection, and a reload composes the final frame at once instead of replaying the sequence.</p>

<h2>The OCR result, including the part that failed</h2>
<p>The row-sequence OCR call had a bug: it was sending its own hardcoded prompt instead of the one the run selected. Fixing the plumbing meant the selected prompt (v8) finally reached the model — and it scored <em>worse</em> than the hardcoded fallback it replaced. Same sheet, same model, same tiling, one variable: recall fell from 0.77 to 0.63 and character accuracy dropped 2.7 points. The fix was correct and the prompt it delivered was rejected as the default. That is what the eval gate is for.</p>
<p>A rewritten prompt did pass. <code>seq-v1</code> — v8 with the per-tile fragment rule replaced by whole-label assembly, and abbreviations transcribed as printed — matched 39 of the 43 human-checked labels at IoU 0.5, with character accuracy 0.990 and diacritic recall 1.0, in about seven minutes a sheet. Running it twice, once on the tile grid and once on the grid shifted half a tile, then merging the two by vote, reaches 41 of 43. A third pass adds nothing, so the recipe stops at two.</p>
<p>One more finding, from filling in the prompt-by-model square: the two variables do different jobs. The newer model moved the <em>boxes</em>; the prompt moved the <em>reading</em>. On the same model, two prompts boxed nearly the same labels (38 versus 39) but one read 31 of them correctly to the other's 40.</p>
<p>Caveat worth repeating: the ground truth is 43 labels a person validated on a single sheet. It is enough to reject a change that makes things clearly worse, which is what it just did. It is not enough to certify one that looks slightly better.</p>
		`,
  },
  {
    slug: 'inside-the-sheets-2026-09',
    title: 'Searching Inside the Sheets, and Asking the Model What a Sheet Is Made Of',
    date: '2026-09-05',
    category: 'update',
    excerpt:
      'A place-time index and a page per attested place name, so a label on a map is a searchable, citable URL. Plus a layout pass that looks at a whole sheet once and says which rectangle is the map, the legend, the title block or the name list.',
    content: `
<p>Two related pieces of work. One makes what the OCR has already read findable; the other decides what the OCR should look at next.</p>

<h2>Search that reaches inside a map</h2>
<p>Until now the archive could search titles and metadata — the things a librarian wrote about a sheet. What it could not search is what is printed <em>on</em> the sheet. That is now indexed: every extracted label and traced shape carries a real-world position, a record of which georeference produced it, and that georeference's own error in metres. "What was here in 1923" is a query rather than a re-computation.</p>
<p>On top of it sits a page per attested place name, server-rendered, one URL each, grouping the spellings the sheets themselves used — the same place appears as several strings across a century of surveys and reforms, and the gazetteer keeps them together instead of picking a winner. The command palette (⌘K anywhere) searches four things now: pages, maps, places and labels, and a label result opens the viewer at the spot it was read.</p>
<p>There is also a period-press panel: given a label, it queries Gallica and the National Library of Vietnam for newspaper hits within a few years of the sheet's date. It is a lead generator, not a citation — it tells you the name was in print, and leaves the reading to you.</p>

<h2>The layout pass</h2>
<p>A colonial sheet is not all map. There is a title block, a legend, sometimes a list of street names down one side, an inset, a scale bar, a north arrow, a stamp. Running OCR over the whole scan wastes calls on furniture and mixes a legend key into the place names.</p>
<p>So one low-resolution look at the whole sheet now asks the model where each of those things is, in nine categories, and returns a labelled rectangle for each. It runs as a queued job rather than a page action, because the model key lives on the worker and deliberately not in the web app. A person can drag any rectangle to correct it; a dashed edge means the model proposed it and a solid one means a person accepted or drew it.</p>
<p>The rectangle that matters for tiling is <code>main_map</code>, and it beats the neatline when both exist. The neatline is the printed border of the sheet — a legend printed inside that border is inside the neatline too, so cropping to the neatline does not exclude it. Tiles are also sized by ground distance now rather than by pixels, so the same tile covers the same amount of city on a 1:2,000 plan and a 1:25,000 survey.</p>

<h2>And a status page</h2>
<p>Counts of maps, jobs and failures that used to need hand-run SQL are now a page. The first useful thing it said: triage is the top blocker. OCR only queues sheets a person has triaged, and that queue is where the corpus run is waiting — not on the model, not on the pipeline.</p>
		`,
  },
  {
    slug: 'self-hosted-basemap-2026-09',
    title: 'Our Own Basemap, After Two Tile Servers Said No',
    date: '2026-09-01',
    category: 'update',
    excerpt:
      'CARTO started stamping "API KEY REQUIRED" across every tile and the OSM Foundation\'s policy does not cover a busy site, so the modern map under the historical sheets is now one PMTiles archive we host ourselves. Also: ten failed deploys, and what caused them.',
    content: `
<p>A historical map needs a modern one underneath it, or there is nothing to line it up against. Ours came from a third party until that stopped working twice.</p>

<h2>What broke</h2>
<p>The keyless raster endpoint we were using began stamping <strong>API KEY REQUIRED</strong> diagonally across every tile — fair enough, it was never promised to us. The obvious fallback, the OSM Foundation's own tiles, has a usage policy that does not cover a site with real traffic. Both roads end in either a bill or a breach.</p>

<h2>What replaced it</h2>
<p>One PMTiles archive in our own object storage, built from Protomaps' daily OpenStreetMap extract, drawn by a deliberately quiet OpenLayers style: land, water, roads, buildings, boundaries, place labels, and nothing that competes with a 140-year-old sheet on top of it. No API key, no quota, no third-party policy.</p>
<p>The first cut covered Saigon only — 37 MB, and cheap. It also left 21 of the georeferenced sheets, every Huế and Hanoi one, floating on bare land fill with no city under them, which is a good illustration of how a "we only work on Saigon" assumption gets baked into infrastructure. It was replaced a few days later by an extract spanning Hanoi to the Mekong: 348 MB, zoom 0–15.</p>
<p>Two details worth writing down. The storage key carries the build date, because the archive sits behind a long edge cache — writing a new build over the same key would strand every reader on stale bytes, so a rebuild is a new name and a config change. And it is served straight off the bucket on its own domain rather than through our worker: PMTiles is nothing but byte-range reads, and the worker could not cache them, because the cache API refuses to store a 206 Partial Content response. Off the worker, those reads are the CDN's to cache.</p>

<h2>Ten failed deploys, for the record</h2>
<p>The same week ate ten builds on two mistakes, both worth knowing if you deploy a SvelteKit app to Cloudflare Pages.</p>
<ul>
<li>A <code>wrangler.toml</code> in the repo root that declares the build output directory <em>replaces the dashboard's entire environment</em> — including the secrets. The site built and then could not reach its own database. There is no root <code>wrangler.toml</code> now, on purpose.</li>
<li><code>$env/dynamic/private</code> returns undefined in Pages Functions. Private values have to come through <code>$env/static/private</code>, which resolves at build time, which in turn means every environment that builds needs every secret present or the build fails on the first import.</li>
</ul>
<p>Related, and the reason this took longer to diagnose than it should have: a blank page immediately after a deploy is usually edge propagation, not a bug. Chunks 404 for a minute or two, and one missing chunk on a client-rendered page is a blank document. Wait, hard-reload, then debug.</p>
		`,
  },
  {
    slug: 'cleanup-2026-08',
    title: '3,194 Lines Deleted, a Job Queue, and a Rule the Linter Enforces',
    date: '2026-08-31',
    category: 'update',
    excerpt:
      'A cleanup week with nothing a reader can see: dead code deleted, the library restructured into layers with the import direction enforced by lint, status changes moved into the database, and the copy-paste pipeline commands replaced by a job queue and a worker that holds no credentials.',
    content: `
<p>Every visible feature this project ships gets slower to build if this work never happens. One commit range removed 3,194 lines and added 155.</p>

<h2>Layers, enforced</h2>
<p>The library is now five directories with one allowed import direction: pure helpers, then data access, then the map runtime, then the product surfaces, then the routes. Generic UI primitives may import none of it. The rule is a lint error rather than something a reviewer is supposed to notice, which is the only version of an architecture rule that survives a busy week. Features declare their shared seams the same way — one feature reaching into another's internals now fails the same check.</p>

<h2>Status changes belong to the database</h2>
<p>Validating an extraction, approving a footprint, claiming a job: those used to be an API route reading a row, deciding, and writing it back. They are now functions inside Postgres, callable only by the service role. The queue claims work with a locking select that skips locked rows, so two workers cannot take the same job. Anything that writes has one code path instead of one per caller.</p>

<h2>Enqueue, never execute</h2>
<p>Pipeline work used to be a CLI command the page printed for you to paste into a terminal. It is now a row in a job queue: the page returns immediately, and a worker claims the job when one is free. The worker holds <em>no database credentials</em> — it authenticates with a minted key and talks to the API, which owns the writes. A machine with a GPU can run the segmentation jobs and nothing else, from a notebook, without ever seeing the service key.</p>

<h2>The leak this found</h2>
<p>Consolidating visibility onto one model — draft, public, featured — surfaced that draft maps were readable anonymously. Unpublished scans, some from institutions whose terms we are careful about, were one API call away from anyone. Fixed the next day; drafts are now visible only to a signed-in user, and a published map must carry a georeference or it cannot be published at all.</p>
<p>Alongside it: contributions are rate-limited, submitted stories go through a review queue instead of appearing directly, and a share page for each published map is server-rendered so a link preview works without running JavaScript.</p>

<h2>Tests, finally</h2>
<p>A browser smoke suite that reads production without writing to it, a set of pure checks that ride the same runner, and — separately — write-path tests against a local database stack that refuses to run unless the URL it is given is a loopback address. Continuous integration runs the type-checker and the build on every push. The write tests found a broken trigger on their first run, which is the return on the whole exercise.</p>
		`,
  },
  {
    slug: 'ocr-audit-2026-08',
    title: 'Nine Faults in the OCR Pipeline, and a Gate So the Next Change Is Measured',
    date: '2026-08-10',
    category: 'research',
    excerpt:
      'An audit of the OCR pipeline found nine problems, including two coordinate conventions living in one database column and a permission that let any signed-in user rewrite a label. The more useful outcome is the eval harness: a core-loop change now has to beat a measured baseline before it ships.',
    content: `
<p>The OCR pipeline reads place names off a scanned sheet and writes them, with a box, to the database. It worked, which is different from being correct. An audit went through it looking for the failures that return plausible output while quietly dropping or corrupting data.</p>

<h2>What was wrong</h2>
<ul>
<li><strong>Two coordinate conventions in one column.</strong> Parts of the pipeline wrote boxes normalised to a 0–1000 grid and parts wrote something else, into the same field. A box read under the wrong convention lands somewhere else on the sheet and is not obviously wrong when you look at a list. One contract now, everywhere.</li>
<li><strong>Anyone signed in could rewrite any label.</strong> The update permission on the extractions table was not restricted. It is now admin and moderator only, at the database level rather than in application code.</li>
<li><strong>A human correction could be overwritten by the model.</strong> Derived reads did not check the review status of the row they were reading, so a re-run could quietly undo a person's fix. Reads are gated on status now, and a human decision wins.</li>
<li><strong>Manual boxes collided.</strong> A hand-drawn box was keyed in a way that clashed with the model's rows on re-insert. Keyed by location now.</li>
<li><strong>A malformed reply retried without the image.</strong> When the model returned unparseable JSON, the retry re-sent the prompt but not the picture, so the retry was asking about nothing.</li>
</ul>
<p>Four smaller ones are in the audit report in the repository. None of these was a crash. All of them produced output that looked like output.</p>

<h2>The gate</h2>
<p>The more durable outcome is that the pipeline is now measured. There is a ground truth — 43 extractions on the 1882 cadastral sheet that a person checked one by one — and a harness that scores a run against it: how many of the known labels a run finds, how accurate the text is on the ones it matches, how well the boxes agree, and whether the diacritics survived.</p>
<p>Two honest limits, both written into the report. The ground truth is a <em>partial</em> subset of what is actually printed on the sheet, so precision is not a trustworthy number: a correct reading the humans never got round to validating counts as a false positive. And it is one sheet. What the harness can do is reject a change that makes things clearly worse, and refuse to let anyone argue from taste about a change that makes things slightly better. That is worth more than it sounds; the first thing it did was kill a step we had already half-built.</p>

<h2>Also that week</h2>
<p>A density pre-pass that scores each tile of a sheet and sets its priority, so the expensive calls go where the text is. Legend extraction, so a numbered key on the sheet can be joined to the entries it names. And a level-aware join between a label and the shape it sits inside, which is the piece that lets a traced building carry the name printed on it rather than a separate guess.</p>
		`,
  },
  {
    slug: 'explore-and-trip-2026-06',
    title: 'A Front Door for the Maps, and a URL for a Printed QR Code',
    date: '2026-06-01',
    category: 'update',
    excerpt:
      'The viewer got an entry point that asks what you came for, a coverage lookup that answers whether the archive has anything where you are standing, and a guided tour. Story playback moved to its own stable URL so a printed QR code has something durable to point at.',
    content: `
<p>Two small releases, both about arriving rather than about capability.</p>

<h2>An entry point</h2>
<p>The map viewer opened onto a map and a catalog and expected you to know what to do. It now opens with a chooser — browse the archive, look up where you are, or take a short guided tour — and remembers that you have seen it, so it appears once.</p>
<p>The coverage lookup is the useful half: it answers the first question a visitor from Ho Chi Minh City actually has, which is whether the archive holds anything covering the ground under their feet. Sometimes the answer is no, and it is better to say so in a sentence than to leave someone panning around an empty map.</p>

<h2>A URL that can be printed</h2>
<p>Story playback — a route with stops, meant to be walked with a phone — is now its own page per story, at a stable address. The reason is physical: a QR code on a printed card or a wall label cannot be re-pointed after it is printed. Everything else in the app is free to move; that URL is not.</p>
<p>Honest state: one story exists to play. The tool works, the format works, and there is a single walk in the archive to try it on.</p>

<h2>Two weeks later, the boring half</h2>
<p>Mid-June cleaned up what the release exposed. The catalog had three search implementations that behaved differently; they are one engine now. The coverage lookup learned about draft maps, so staff see the unpublished sheets they are working on and the public does not. Map editing came back into the catalog for admins and moderators, where it belongs, instead of living on a separate page. And the "Looking up maps…" spinner that never stopped spinning when a lookup returned nothing was fixed — the version of a bug that makes an app feel broken rather than empty.</p>
		`,
  },
  {
    slug: 'layer-stack-2026-05',
    title: 'Rebuilding the Map Viewer Around a Single Concept: the Layer Stack',
    date: '2026-05-24',
    category: 'update',
    excerpt:
      'A short post on a long refactor. The map viewer had grown three overlapping mental models — active map, base map, compare set — each with their own UI surface, each leaking into the others. We collapsed them into one Photoshop-style layer stack with a single store, then redesigned mobile around two labeled bottom drawers.',
    note: 'September 2026 — the route in this post, <code>/view</code>, is now <code>/explore</code>: a later merge folded twenty-three pages into sixteen and turned modes into query params. The layer stack itself is unchanged and is what /explore still renders.',
    content: `
<p>If you opened <code>/view</code> a week ago and tried to put one historical map under another and a third on top to compare, you would have used three different buttons in three different places, talking to three different stores, rendered by three different components. It worked, but only if you already understood the model. New users didn't. Even we kept tripping on it.</p>
<p>This post is about the cleanup: what was wrong, what we replaced it with, and the mobile UX that fell out of doing the work properly.</p>

<h2>What was wrong</h2>
<p>The state for "what the map is showing" was split across three stores:</p>
<ul>
<li><strong><code>mapStore.activeMapId</code></strong> — the single overlay historical map (set by clicking a catalog row)</li>
<li><strong><code>mapStore.baseMapId</code></strong> — a separate slot for a historical map used as the base layer (set by a "B" button)</li>
<li><strong><code>compareStore.ids[]</code></strong> — additional overlays for compare/stack modes (set by a "+" button)</li>
</ul>
<p>Three writes, three renderers (<code>HistoricalOverlay</code>, <code>HistoricalBaseLayer</code>, a manual <code>StackedOverlay</code> loop), three concepts the user had to keep straight. On top of that, the bottom map toolbar had its own "view mode" (Overlay/Lens/Dual) AND "compare mode" (Split/Stack) — and Split and Dual rendered the same thing, while Stack and the default "show two overlays" did the same thing differently. The opacity slider in the toolbar only controlled one of the layers; the others were hard-coded at 0.6. So toggling between modes changed which thing was opaque-controllable in confusing ways.</p>
<p>This is what happens when features land sequentially without revisiting the model.</p>

<h2>The new mental model</h2>
<p>One concept: a <strong>layer stack</strong>, exactly like Photoshop. There's a <em>base</em> at the bottom (Maps, Satellite, or None) and zero-to-ten <em>overlays</em> stacked on top. Each overlay has its own opacity slider, visibility toggle, remove button, and drag handle for reordering. The catalog has two actions per row: click the row replaces the stack with this one map, and the "+" button adds to the stack alongside whatever's there.</p>
<p>Display mode (Stacked / Lens / Side-by-side) is now orthogonal to the stack contents — it's how the stack is shown, not what's in it. Side-by-side drops the topmost overlay in the right pane, so you can flick between "with this top map" and "without" by looking left vs. right. The top two layers get a small L / R badge so it's obvious which one is which.</p>
<p>Internally, this collapsed three stores into one (<code>layersStore</code>) and three renderers into one (<code>LayerRenderer</code>). Persistence to <code>localStorage</code> means your stack survives a refresh, which is a small thing that matters a lot when you're comparing maps.</p>

<h2>The cleanup was bigger than the new feature</h2>
<p>The actual layer-stack work was maybe a third of this commit. The other two thirds were deletion: <code>compareStore</code>, <code>CompareTray</code>, <code>HistoricalOverlay</code>, <code>HistoricalBaseLayer</code>, <code>StackedOverlay</code>, <code>MapToolbar</code>, the floating basemap toggle, the active-info card, the "Back to Catalog" sidebar link, and a couple hundred lines of orphaned CSS in <code>tool-page.css</code>. Net change: +2,543 / −2,334 across 34 files. Roughly break-even line-wise; substantially less surface area.</p>
<p>One of the warnings about premature abstraction is that the abstractions stop being neutral — they start nudging future code into shapes that fit them. <code>compareStore</code> was that. Anything to do with multiple maps got routed through "compare," which made it hard to think of layers as a generic stack. Deleting it freed us to think about layers as layers.</p>

<h2>Mobile got rebuilt around two drawers</h2>
<p>Once layers were a stack, the desktop sidebar split into two halves — layer controls on top, browse catalog on the bottom — at a 40/60 ratio. On mobile, we couldn't fit both at once, but tabs felt wrong: users coming from the map don't want to lose the map to read a list. So the answer was two bottom drawers, stacked: one labeled <strong>🗺️ Layers</strong>, the other <strong>📋 Browse</strong>. Both labels are always visible at the bottom of the screen. Tap one, it slides up to 70vh; tap again or tap the backdrop, it slides back down. The labels stay pinned at the bottom of each drawer so you never lose orientation.</p>
<p>This came out of a small reusable component, <code>MobileDrawer.svelte</code>, that takes a label, an icon, and an open boolean. Most of the complexity that used to live in <code>ToolLayout</code>'s mobile branch is now just two instances of that component plus an open-drawer state.</p>

<h2>Why this post exists</h2>
<p>VMA is a small project run on volunteer time. The pace of feature work means it's easy to add things and never look back. But complexity compounds — every new feature that lands on a confused model multiplies the confusion. Spending a week to rip out three half-baked abstractions and replace them with one good one is rarely the loudest commit, but it's often the most useful. The next person to touch the viewer — possibly future-me, possibly a new contributor — will hopefully look at <code>layersStore</code>, understand it in two minutes, and add their feature without breaking anything else.</p>
<p>If you want to try it: open <a href="/explore" target="_blank">/explore</a>, click any map in the catalog to load it, click "+" on another to stack them, drag layers to reorder, and switch between Stacked / Lens / Side-by-side from the panel header. On a phone, the two drawers sit at the bottom and behave like the rest of mobile internet. That's it. That's the whole interface.</p>
		`,
  },
  {
    slug: 'scout-pipeline-2026-05',
    title: 'Scouting 3,373 Maps: Building a Discovery Pipeline for Vietnam Cartography',
    date: '2026-05-16',
    category: 'update',
    excerpt:
      'We built a multi-source discovery pipeline that pulls Vietnam-related map records from BnF Gallica, Humazur, David Rumsey, and the Library of Congress into a single reviewable grid. 3,373 candidates surfaced — 758 high-confidence — now curatable from /admin?tab=scout with thumbnails, scoring, and one-click bulk-ingest into the catalog.',
    note: 'September 2026 — the queue holds 985 candidates today, not 3,373: dedup and rejection pruned it. The 758 high-score bucket was never curated in an afternoon or otherwise. What actually came out of the scout is one batch of 62 Tonkin sheets, and those are still unpublished drafts. The page moved from /admin/scout to /admin?tab=scout.',
    content: `
<p>Until this week, adding maps to VMA was a one-by-one job: paste a IIIF manifest URL into the admin form, click "Fetch from Allmaps," fill in the gaps, save. That works fine for the maps we already know about. It doesn't work for the ones we don't — and the colonial Vietnam corpus is scattered across at least a dozen institutions worldwide, most of which have public catalogs but no obvious entry point.</p>
<p>So we built a scout. <strong>3,373 candidate maps</strong> are now sitting in a reviewable queue at <code>/admin?tab=scout</code>, pulled from four institutions in one pass, scored for relevance, and ready to bulk-ingest with thumbnails and full Dublin Core metadata.</p>

<h2>What "scout" means here</h2>
<p>Each source has its own API quirks, but the shape of the work is the same: query for Vietnam-related material, normalize the metadata, dedup against what's already in the VMA catalog, derive a thumbnail, and score the result for relevance. We hit four sources:</p>
<ul>
<li><strong>BnF Gallica</strong> via the SRU API — 468 records. This also picks up federated partners (Bordeaux 3, Bibliothèques de Paris, Sorbonne, Institut catholique de Paris) for free.</li>
<li><strong>Humazur</strong> (Université Côte d'Azur, Omeka S) — 2,827 records from the <em>Cartothèque ASEMI</em> set (417 pure maps) and the <em>Indochine française</em> set (1,500+ mixed maps and photos, filtered for cartographic items).</li>
<li><strong>David Rumsey Map Collection</strong> at Stanford — 53 Vietnam-tagged records out of ~994 raw hits.</li>
<li><strong>Library of Congress</strong> — 48 records across the Vietnam keywords.</li>
</ul>
<p>What we deliberately didn't scout: Internet Archive (3,500+ hits but no clean map filter), Cartomundi (their catalog is a JavaScript app with no API — would need a headless browser), Princeton GeoBlacklight (geographically indexed by bounding box, not by keyword — returns zero for "vietnam" as a subject query), Harvard LibraryCloud (endpoint quirks we didn't have time to chase), and HathiTrust (Cloudflare-blocked). Each of those is technically reachable; none was worth the effort relative to what the first four already give us.</p>

<h2>Scoring is heuristic, but useful</h2>
<p>Not all 3,373 are actually maps worth ingesting. The Indochine française set on Humazur, especially, is full of colonial-era <em>photographs</em> — pagoda interiors, market scenes, railway stations — that mention Vietnamese places in their metadata but aren't cartographic. So we apply a relevance score and a category guess to every record:</p>
<ul>
<li><strong>+20</strong> for a Vietnamese place name in the title, subject, or coverage fields</li>
<li><strong>+20</strong> for a year between 1850 and 1955 (the colonial core), <strong>+10</strong> for pre-1850</li>
<li><strong>+15</strong> for a map-type keyword in the title (<em>plan</em>, <em>carte</em>, <em>topographique</em>, <em>cadastral</em>, <em>atlas</em>, <em>levé</em>)</li>
<li><strong>−60</strong> for photo-subject keywords without any map term (<em>vue</em>, <em>intérieur</em>, <em>rue</em>, <em>pagode</em>, <em>village</em>, <em>monument</em>, …)</li>
<li><strong>−50</strong> for world maps with Vietnam as a projection center, <strong>−30</strong> for railway plates</li>
</ul>
<p>The result, across 3,373 records: 758 score ≥40 (likely maps), 100 score 20–39 (borderline), 1,540 score 0–19 (unclear, often non-cartographic atlas pages), and 975 score below zero (correctly flagged photos and railway scenes). A human still has to look, but the high-score bucket is now small enough to review in an afternoon instead of a week.</p>

<h2>Thumbnails took most of the engineering</h2>
<p>A grid of unlabeled rows is unusable. A grid of <em>thumbnails</em> is fast to scan. So the loader had to produce a thumbnail for each candidate before they ever hit the UI, and that turned out to be the harder problem.</p>
<p>Gallica is easy — every ARK has a stable thumbnail URL at <code>https://gallica.bnf.fr/&lt;ark&gt;/f1.thumbnail</code>. David Rumsey returns thumbnail URLs (<code>urlSize2</code>) directly in its search response. The Library of Congress includes <code>image_url</code> in each result.</p>
<p>Humazur is where it got interesting. Omeka S, the platform it runs on, doesn't expose thumbnails on the item object — they live on the <em>media</em> object that the item points to. So the backfill script has to fetch <code>/api/items/{id}</code>, read the first <code>o:media[@id]</code>, fetch <code>/api/media/{media_id}</code>, and pluck out <code>o:thumbnail_urls.medium</code>. Three round-trips per candidate, throttled at 150ms each. On the top-200 high-score Humazur rows, the success rate was 97%. The rest of the 2,400+ Humazur records can be backfilled in the background.</p>
<p>One bug we caught in the process: our initial Humazur scout was building manifest URLs out of media IDs (<code>iiif/&lt;media_id&gt;/manifest</code>) when the correct pattern is <em>item</em> ID (<code>iiif/&lt;item_id&gt;/manifest</code>). Every Humazur manifest URL was returning 404. The loader silently fixes this at insert time so the stored URLs are correct.</p>

<h2>The review UI</h2>
<p>The page at <code>/admin?tab=scout</code> is a thumbnail grid with filters along the top (status, source, category, minimum score, title search), facet counts that update as you filter, and per-card Approve / Reject / Revert buttons. Selecting multiple cards lets you bulk-approve, bulk-reject, or — for already-approved candidates — bulk-ingest as draft <code>maps</code> rows. Each ingested map carries an <code>extra_metadata.scout_candidate_id</code> reference so we can always trace a catalog row back to the source record that produced it.</p>
<p>The ingest itself reuses the same metadata model we just standardized in last week's <code>holding_institution</code> work: each ingested row gets <code>source_type</code> mapped from the holding institution (Bibliothèque nationale de France → <code>bnf</code>, David Rumsey → <code>rumsey</code>, others → <code>other</code>), a populated <code>holding_institution</code> field separate from <code>collection</code> (which is the sub-collection at the holder), and the IIIF manifest URL ready for further enrichment via the "Fetch metadata from IIIF manifest" button in MapEditModal.</p>

<h2>Why this matters for the project</h2>
<p>VMA's core constraint is volunteer attention. Every minute spent hunting for a candidate map in BnF's catalog is a minute not spent georeferencing, OCR-ing, or annotating. By front-loading discovery into a tool that produces a curatable queue, we shift the work from "find one map at a time" to "review a batch and approve in bulk." The first pass already surfaces roughly twice as many viable candidates as VMA's current catalog of 100 map rows, 39 of them published — and that's before we extend the scout to Vietnamese-language sources (the National Archives have a digital catalog, and so does Hanoi's Institute of Sino-Nôm Studies).</p>
<p>It's also a small piece of infrastructure that scales: each new source is one normalize function and one entry in the scout runner. Adding a fifth source — say, EFEO's <em>Bibliothèque Numérique</em> when we get around to it — is an afternoon of work, not a rebuild.</p>

<h2>What's next</h2>
<p>Two things follow from this:</p>
<ol>
<li><strong>Curate and ingest the high-score bucket.</strong> 758 candidates is a real afternoon's work, but a quiet one — most are obvious approves. Once they're in the catalog as drafts, the existing pipeline (georeference → OCR → annotate) picks up from there.</li>
<li><strong>Extend to Vietnamese-language and regional sources.</strong> The biggest gap right now is anything held inside Vietnam. EFEO's collection, the Institut d'Asie Orientale at Lyon, and any digitized holdings from Hanoi or Ho Chi Minh City archives would push the corpus toward 5,000+ unique candidates.</li>
</ol>
<p>If you've been waiting for a way to help VMA without doing pixel-level work, scout review is exactly that — fast, judgment-based, and visible in its impact. Drop us a note and we'll get you admin access to <code>/admin?tab=scout</code>.</p>
		`,
  },
  {
    slug: 'tonkin-topographic-series-2026-05',
    title: 'Ingested: 62 Tonkin Topographic Sheets (1903–1927)',
    date: '2026-05-14',
    category: 'announcement',
    excerpt:
      "A batch of 62 colonial-era topographic sheets covering the Red River delta — Hà Nội, Hải Phòng, Nam Định, Thanh Hóa, and surrounding provinces — has been tiled to R2 and ingested as drafts. All from the Service Géographique de l'Indochine, surveyed between 1903 and 1927.",
    note: 'September 2026 — all 62 sheets are georeferenced now, but every one is still <code>draft</code>, so none of them is visible to a reader who is not signed in. Nothing in this batch has been published, OCR-ed or traced, and the toponym layer for northern Vietnam described at the end of this post does not exist.',
    content: `
<p>We've ingested <strong>62 new sheets</strong> from the Service Géographique de l'Indochine — the French colonial mapping bureau that produced the most systematic topographic survey of northern Vietnam before WWII. The collection covers the Red River delta and surrounding provinces, with most sheets surveyed between 1903 and 1927 at roughly 1:100,000 scale.</p>

<h2>What's in the batch</h2>
<p>The sheets span the densely populated lowland north: Hà Nội itself (sheet 20, 1903), the port of Hải Phòng (31, 1904), and the major delta cities — Nam Định (55), Thái Bình (56), Ninh Bình (59), Phát Diệm (69), Thanh Hóa (75). Inland coverage extends to Sơn Tây (12), Bắc Ninh (10), Hưng Yên (42), and the Quảng Yên coastal zone (25, 32). A handful of named sheets sit outside the numbered grid: <em>Hà châu</em>, <em>Nhà nam</em>, <em>Bảo Lộc</em>, <em>Cẩm Lý</em>, and a cover plate that we've kept in the archive for completeness.</p>
<p>For anyone tracing genealogy or urban history in northern Vietnam, this is the layer beneath everything: the administrative boundaries, village names, and road networks that the post-1954 state inherited and reshaped. Place names are in pre-reform romanization (no diacritics), which is itself a useful diff against modern toponymy.</p>

<h2>Pipeline notes</h2>
<p>This is the first batch processed entirely through the consolidated bulk-upload pipeline. Each sheet now flows in one pass: <code>tile_map.sh</code> writes a DZI pyramid to R2 under <code>iiif.maparchive.vn/iiif/&lt;uuid&gt;</code>, the maps row is inserted with the sheet number preserved in <code>extra_metadata.sheet_number</code>, and the thumbnail URL is derived from the smallest pyramid level the worker advertises in <code>info.json</code>. No separate backfill step.</p>
<p>The previous version of the script split parsing across two passes — upload first, then run a clean-up to strip leading sheet numbers and fetch thumbnails. That worked but hid a latent bug: a <code>set -e + pipefail</code> shell trap silently aborted the cleanup on the first row whose name didn't have a leading number, which meant later uploads weren't being cleaned. Folding everything into the upload script eliminates the second pass and the failure mode at once.</p>

<h2>What's next for these sheets</h2>
<p>None of the new maps are georeferenced yet — they're in <code>draft</code> status until the corners are placed. The sheets are gridded enough that GCP propagation should work well: once we manually georeference one or two anchors per band, the rest can inherit corners arithmetically the same way the L7014 series did. After that, the OCR pipeline can scout the sheets for place names, and the toponym layer for northern Vietnam starts to materialize.</p>
<p>If you can read the older romanization confidently and want to help validate place-name extractions, this is exactly the kind of contributor work we're set up to support — though the sheets have to be published before there is anything to validate. The <a href="/catalog">catalog</a> shows what is published today.</p>
		`,
  },
  {
    slug: 'mid-april-2026-platform-notes',
    title: 'Platform Notes: Universal IIIF, Gemini OCR, and the MapShell Refactor',
    date: '2026-04-18',
    category: 'update',
    excerpt:
      "Self-hosted tiles on R2 for better performance, a Gemini-powered OCR pipeline for toponym discovery, and a core architecture refactor around MapShell. April's updates focus on scaling our data foundation and unifying the user experience.",
    note: 'September 2026 — three corrections. The OCR pass is called “Project Scout” here; a month later we shipped an unrelated map-discovery tool also called Scout, and the name in this post is the confusing one. The tile-speed figure was an impression from clicking around, not a benchmark. And the Label tool listed under MapShell was retired in the route merge.',
    content: `
<p>Stability in a research archive comes from two places: the reliability of the data sources and the clarity of the interface. This week's updates address both, moving us away from reliance on institutional IIIF servers and toward a unified architecture that can support our next phase of growth.</p>

<h2>Universal IIIF: Solving the "Paris Latency" Problem</h2>
<p>For months, our performance has been throttled by the physical distance between our users and the primary scans hosted at the BnF in Paris. While Gallica is an invaluable partner, their IIIF Image API wasn't designed for high-concurrency tile requests from Southeast Asia. Furthermore, the mismatch between IIIF v2 (Gallica) and IIIF v3 (modern standards) required increasingly complex workarounds in our client code.</p>
<p>We've solved this by deploying a custom <strong>Cloudflare Worker and R2 backend</strong>. When a map is mirrored to our internal <code>iiif.maparchive.vn</code> service, we fetch the source image, tile it ourselves, and host it on the edge. The worker acts as a universal IIIF translator, serving perfect v3-compliant <code>info.json</code> manifests regardless of the original source. The result is a nearly 10x improvement in tile load times and a much simpler display layer.</p>

<h2>Project Scout: Gemini OCR for Map Discovery</h2>
<p>Georeferencing a map is only the first step. To make these maps searchable, we need to extract the text—street names, administrative boundaries, and landmark labels. Doing this by hand across a whole collection is impossible.</p>
<p>We've introduced <strong>Project Scout</strong>, an OCR pipeline powered by Gemini 3 Flash. Unlike standard OCR, Scout is tuned for the specific typography and layout of historical maps. It runs in two passes: a low-resolution "Scout Pass" to identify major features and a high-resolution "Detail Pass" for precise bounding boxes. We're already seeing high-accuracy extractions from the 1882 cadastral survey, which are being used to seed our search index and knowledge graph.</p>

<h2>MapShell: A Unified Architecture</h2>
<p>As we added more tools—Trace, Label, Review, Georef—our frontend code began to fragment. Each tool was managing its own OpenLayers instance, leading to inconsistent behavior and state drift.</p>
<p>The new <strong>MapShell</strong> architecture modularizes the map engine. By using Svelte context to share a single, robust map instance across components, we've unified the user experience. Whether you're in the Catalog, the Annotation tool, or the Story viewer, the map behaves the same way, respects the same global state, and shares the same high-performance overlay logic. This refactor reduced the codebase size while making it significantly easier to build new collaborative features.</p>

<h2>Route Groups and Editorial Polish</h2>
<p>Finally, we've reorganized the application's URL structure using SvelteKit route groups. This separates our <code>(editorial)</code> pages (like this blog, the about page, and the catalog) from the full-screen <code>(app)</code> tools. This separation allows us to apply distinct layout strategies—like the clean, typography-focused look of the editorial site vs. the dense, data-rich interface of the contribution tools—without cluttering the code with conditional logic.</p>
<p>The roadmap for the rest of April is clear: batch processing the remaining colonial maps through the R2 mirror and scaling up the OCR extraction to build our first comprehensive street-name index.</p>
`,
  },
  {
    slug: 'platform-notes-april-2026',
    title: 'Platform Notes: Retiring a Pipeline and Rebuilding the Data Foundation',
    date: '2026-04-10',
    category: 'update',
    excerpt:
      'The L7014 pipeline is done and its code is gone. In its place: a modular maps data layer with proper source provenance, multi-IIIF support, and metadata backfilled for all 37 maps in the collection. What we built, why we built it that way, and what it reveals about running a research archive as software.',
    content: `
<p>Most software projects accumulate features. Research archives accumulate debt. The distinction matters: features add capability; debt is the difference between what the code says and what the project actually needs. This month we settled a significant account.</p>

<h2>Retiring the L7014 pipeline</h2>
<p>The US Army L7014 georeferencing pipeline — five API routes, two utility modules, a datum correction library, a propagation algorithm — has been removed from the codebase. Not archived, not commented out. Deleted.</p>
<p>This is the right outcome. The pipeline completed its mission: 500+ sheets georeferenced, datum-corrected from Indian 1960 to WGS84, uploaded to Internet Archive, served over IIIF. The work is done and permanent. The code that produced it does not need to persist in a codebase built around different problems. Keeping it would have meant maintaining it, explaining it to contributors, and treating a completed batch job as if it were ongoing infrastructure. It wasn't. It was a one-time construction project and the building is standing.</p>
<p>The two functions that were genuinely generic — building a W3C Georeference Annotation from IIIF source and GCP corners, and fetching IIIF info.json with retry logic — have been moved to <code>src/lib/iiif/iiifImageInfo.ts</code>, where they belong. Everything else is gone. The codebase is materially smaller and the remaining code is materially clearer about what the project does.</p>

<h2>What the cleanup revealed</h2>
<p>Removing the pipeline exposed a design assumption that had been quietly propagating errors. The <code>allmaps_id</code> column — the Allmaps annotation identifier that links a map image to its georeferencing — had been copied onto two other tables, <code>label_tasks</code> and <code>footprint_submissions</code>, as a convenience. The idea was that queries involving footprints wouldn't need a join to the maps table to find the annotation URL.</p>
<p>In practice, the copies drifted. When an annotation was updated, the copy wasn't. We found a footprint submission where the <code>map_id</code> foreign key pointed to "Saigon &amp; Surroundings (1882)" but the denormalized <code>allmaps_id</code> pointed to the "Plan Cadastral (1882)" — a different map entirely. The join was cheap. The denormalization was expensive and wrong.</p>
<p>Both copies have been removed. The join is now required. The principle is the same one that governs how we store building footprints: a fact belongs in one place, and dependent data is computed on demand. Pixel coordinates + georeferencing annotation = geographic coordinates. Map UUID + maps table = annotation URL. Neither result needs to be stored separately.</p>

<h2>The maps data layer</h2>
<p>The more substantial work was rebuilding how maps are described and sourced. The original <code>maps</code> table had nine columns: an ID, name, type, summary, description, thumbnail, featured flag, year, and the Allmaps annotation identifier. This was enough to display a catalog and load an overlay. It was not enough to treat a map as an archival object with provenance.</p>
<p>Fourteen columns have been added, grouped into three concerns.</p>
<p><strong>Source provenance.</strong> <code>source_type</code> (the originating institution: BnF, EFEO, Internet Archive, etc.), <code>collection</code> (the human-readable collection name), <code>source_url</code> (the canonical page at the institution — a citable URL, not an API endpoint), and <code>ia_identifier</code> for Internet Archive items specifically. A BnF Gallica map now carries a link to its Gallica record. A researcher citing a building footprint derived from that map can trace the provenance chain: footprint → annotation → map → Gallica record. That chain didn't exist before.</p>
<p><strong>IIIF metadata.</strong> <code>iiif_manifest</code> and <code>iiif_image</code> store the manifest and image service URLs. These were previously implicit — reconstructed from the Allmaps annotation on every request. They're now first-class fields, with a corresponding <code>map_iiif_sources</code> table that lets a map have multiple IIIF image sources: the original BnF scan, a re-uploaded copy on Internet Archive for better tile performance, a self-hosted version for maps with restrictive access terms. One is designated primary; the others are ordered fallbacks. The primary source's URLs are kept in sync on the parent row via a database trigger.</p>
<p><strong>Classification and coverage.</strong> <code>map_type</code> separates what the map is (cadastral, topographic, city plan, panorama) from the city it depicts. <code>bbox</code> stores the geographic bounding box for spatial queries. <code>status</code> tracks the lifecycle: pending georeferencing → georeferenced → processing → published. The old <code>type</code> column, which contained city names like "Saigon-HCMC", remains for backward compatibility while we migrate.</p>

<h2>Multiple IIIF sources per map</h2>
<p>The multi-source design deserves a note. This is not about redundancy for its own sake. It's about the gap between where a map lives archivally and where it should be served from operationally.</p>
<p>BnF Gallica serves excellent scans, but the IIIF Image API response times from Paris are slow for tile-by-tile loading from Southeast Asia. For most of our maps, the scan lives on BnF; a IIIF-compatible copy lives on Internet Archive, which has edge caching. The system records both sources, marks one primary, and can switch without losing the provenance link to the original institution.</p>
<p>The same pattern applies to maps with complicated access terms. EFEO maps, for instance, may be freely downloadable but not freely redistributable. Keeping the BnF or EFEO source as the canonical record, with a self-hosted copy for serving, lets the display layer do the right thing without the data layer pretending the institutional relationship doesn't exist.</p>

<h2>Metadata backfill: 37 maps, 20 minutes</h2>
<p>The new fields are only useful if they're populated. For all 37 maps in the current collection, we ran an automated backfill: fetch the Allmaps annotation, extract the IIIF image service URL, detect the source institution from URL patterns, fetch the IIIF manifest, parse title/creator/date/rights, compute a thumbnail URL, and write everything back. For the 20 BnF Gallica maps, the canonical Gallica page URL is derivable from the manifest URL arithmetically — the ark identifier is the same, the path prefix is different. All 20 were filled in without manual lookup.</p>
<p>The 17 Internet Archive maps require manual source attribution. These were often scanned from physical copies at various institutions and uploaded without structured provenance metadata — the IA manifest might say "1882" as a title. We're going through these individually to establish where the original scan came from. That's the remaining gap.</p>

<h2>What changed in the codebase structure</h2>
<p>Beyond the maps domain, the reorganization consolidated several modules that had accumulated around the pipeline and early prototyping: a <code>pipeline/</code> module became two functions in <code>iiif/</code>; a <code>studio/</code> module became one file in <code>annotate/</code>; a <code>viewer/</code> module merged into <code>map/</code>; a <code>core/</code> module merged into <code>utils/</code>. Styles moved from a <code>lib/styles/</code> directory that required relative imports to <code>src/styles/</code> with a <code>$styles</code> alias. Seven orphaned components were deleted. The type checker now reports zero errors on the full build.</p>
<p>None of these changes are visible to users. They're the kind of changes that make the next visible change easier to ship.</p>

<h2>What's next</h2>
<p>The maps data layer is the foundation for the catalog redesign — filter by city, by type, by collection, by coverage area. That's the next front-end milestone. In parallel: the <code>supabase/types.ts</code> generated types need regenerating to reflect the new schema, and the admin map-editing UI needs updating to surface the new fields. We're also mid-way through attributing the 17 IA maps to their original institutions — if you know where the 1863 "Plan du port de Saigon" or the 1882 "Saigon &amp; Surroundings" were first scanned, tell us.</p>
		`,
  },
  {
    slug: 'buildings-as-ground-control',
    title: 'Buildings as Ground Control: A New Method for Vectorizing Colonial Maps',
    date: '2026-03-13',
    category: 'research',
    excerpt:
      'The 1882 and 1898 Saigon maps share hundreds of the same buildings. We use those stable structures as automatic ground control points — letting maps georeference each other, and producing a 1880–1900 building dataset as a byproduct.',
    note: 'September 2026 — most of this did not ship as described. The colour-profile SAM pipeline was deleted from the repository; footprint segmentation now runs on a fine-tuned SAM2 fork, on Colab. The building-to-building matching — Hu moments, RANSAC, an automatic georeference of the 1898 sheet — was never built, and there is no 1880–1900 change dataset. The 91 city blocks below came from one 1,200 px crop and remain the whole of the result. Every one of the 46 footprints in the archive today was traced by hand.',
    content: `
<p>The two most important maps we have of colonial Saigon — an 1882 cadastral survey and its 1898 revision — have never been compared as spatial data. They've been studied individually, scanned, and put online. But no one has asked: which buildings appear in both? Which ones were built or demolished in those sixteen years? And can that shared knowledge help us georeference the maps themselves?</p>
<p>The answer to the last question turns out to be yes, at least on paper.</p>

<h2>The standard approach and its cost</h2>
<p>Georeferencing a historical map means manually clicking corresponding points between the old map and a modern coordinate reference. You click a church corner on the 1882 map, click the same spot on a modern satellite image, repeat 15–20 times, and a polynomial transform snaps the old map into place. This works. It takes about an hour per map, requires you to find recognizable landmarks that still exist, and has to be done again from scratch for every new map even if it covers the same area.</p>
<p>Vectorization — tracing the actual building outlines as digital polygons — is a separate problem that usually comes after georeferencing and is even more labour-intensive. For 500 buildings across two maps, manual tracing would take weeks.</p>

<h2>What SAM changes</h2>
<p>Meta's Segment Anything Model (SAM) is a vision foundation model that segments objects in images with no training data. Feed it a map tile and it finds every visually distinct region — building blocks, streets, courtyards, open land — as clean polygon masks. It works well on printed maps because the visual contrast is high and consistent: orange fills, grey hatching, cream open space, black outlines. The 1882 and 1898 Saigon maps happen to use exactly this kind of legible polychrome symbology, consistently applied across both surveys.</p>
<p>The pipeline fetches tiles directly from the IIIF Image API — no full-image downloads, no TIFF conversion. A 12,000 × 9,000 pixel scan becomes roughly 540 overlapping 512×512 JPEG tile requests, each processed by SAM independently, with tile-local coordinates offset back to full-image pixel space. The result is several thousand pixel-space building polygons per map, stored in a database with no geographic coordinates attached yet.</p>

<h2>The pixel-first architecture</h2>
<p>That last point is deliberate. We store building outlines as pixel coordinates — x and y positions on the original scan — rather than longitude and latitude. Geographic coordinates are computed on demand by passing the pixel polygon through the Allmaps georeferencing annotation for that map. The annotation holds the ground control points; the transform is applied at read time.</p>
<p>This means fixing or improving a georeferencing annotation automatically improves every building footprint derived from it. The spatial reference lives in the annotation, not in the building polygon. The two concerns — where the map sits on Earth, and what shapes are on it — are handled independently.</p>

<h2>Buildings as their own ground control</h2>
<p>Here is where things get interesting. Once you have pixel-space building polygons for both the 1882 and 1898 maps, you can ask: which buildings appear in both? A building that existed in 1882 and was still standing in 1898 will have nearly the same shape in both surveys — same proportions, same footprint, same relationship to the street. Mathematically, its polygon will have similar Hu moments (a rotation- and scale-invariant shape descriptor) in both maps.</p>
<p>We match building shapes across the two pixel-space polygon sets, use RANSAC to reject mismatches, and end up with a set of stable buildings identified as corresponding pairs. Each pair gives us one ground control point: the pixel location in the 1882 map and the pixel location in the 1898 map are the same real-world building. If the 1882 map is already georeferenced, those pixel positions can be converted to longitude/latitude and used directly as GCPs for the 1898 map — <strong>automatically, with no manual clicking</strong>.</p>
<p>The first map in the series still needs manual georeferencing. Every subsequent map can be handled by the buildings themselves.</p>

<h2>The change dataset falls out for free</h2>
<p>The matching step classifies every building polygon along the way:</p>
<ul>
<li><strong>Stable</strong> — matched in both maps, similar shape. Built before 1882, still standing in 1898.</li>
<li><strong>New</strong> — present in 1898, absent in 1882. Constructed between the two surveys.</li>
<li><strong>Demolished</strong> — present in 1882, absent in 1898. Removed in the same period.</li>
<li><strong>Modified</strong> — partial overlap. Flagged for review.</li>
</ul>
<p>Each polygon gets a <code>valid_from</code> and <code>valid_to</code> date. This is the 1880–1900 Saigon building dataset — the first machine-readable spatial record of the colonial city — and it emerges directly from the georeferencing step, not as a separate effort.</p>

<h2>What this means for maps that don't fit WGS84</h2>
<p>There's a broader implication worth naming. The vector-to-vector method doesn't require either map to be georeferenced to WGS84. If your goal is to compare two maps of the same place — to find what they agree on and what each one shows that the other doesn't — the comparison can happen entirely in feature space. Geographic coordinates are optional.</p>
<p>This matters for indigenous and pre-colonial maps, which often organise space by relational distance, travel time, or political logic rather than metric coordinates. Conventional georeferencing asks: how wrong is this map compared to WGS84? The implicit answer frames spatial difference as error. Vector-to-vector comparison asks instead: what do these two representations of the same territory share? The shared features define their own reference frame, internal to the maps, and WGS84 can be layered on later where it's useful — not required as a precondition for learning anything.</p>
<p>For Vietnam specifically: a pre-colonial Vietnamese road map (<em>lộ đồ thư</em>) and a French colonial cadastral survey of the same territory could be compared by stable features — river confluences, coastal inlets, major settlements — without either being subordinated to the other's coordinate logic. The French map would serve as the georeferenced anchor not because it is more correct but because it is more densely pinned to WGS84. The Vietnamese map would retain its own spatial epistemology.</p>

<h2>Pipeline advances since the first draft</h2>
<p>Several refinements emerged from reading the NYPL Building Inspector paper (Arteaga 2013) and Morlighem's TU Delft thesis on automated 3D city model reconstruction from historical maps (2021).</p>
<p><strong>Colour classification.</strong> Raw SAM output accepts everything — streets, courtyards, text characters — as candidate building polygons. The 1882/1898 Saigon maps use a consistent five-class polychrome legend: salmon for private property (<em>particulières</em>), green for communal holdings, cream for unassigned domain land, blue-grey hatching for military buildings, dark grey hatching for local-service buildings. We now classify each SAM polygon by the average RGB of its interior pixels against this calibrated palette, discarding anything closer to the paper background than to any property class. The property class is stored in the <code>feature_type</code> field, so the full cadastral typology survives into the database rather than everything being labelled "building".</p>
<p><strong>Two-phase segmentation.</strong> A single pass at any one scale misses either large city blocks (too small a region) or individual buildings (too coarse a downscale). We now run a dedicated <em>plot pass</em> at 8× downscale (4096 px region → 512 px SAM input) and separate <em>building passes</em> at 2× and 1×. At 8× downscale, building-boundary ink lines (2–3 px wide) fall below the rendering threshold and disappear, causing whole city blocks to appear as single solid polygons. At 2× and 1×, those lines are preserved and SAM segments individual footprints. The deduplication step keeps both levels when a small building polygon is contained within a larger block polygon — a hierarchical pair, not a duplicate.</p>
<p><strong>Shape regularisation (building passes only).</strong> Individual buildings are nearly always rectangular; SAM traces them with slightly jagged outlines following ink roughness. We snap near-rectangular polygons (area/MBR ratio ≥ 0.75) to their minimum bounding rectangle. City blocks are explicitly excluded from this step: colonial Saigon blocks follow diagonal street grids and have trapezoidal or L-shaped outlines that must be preserved as traced.</p>

<h2>First test results</h2>
<p>The plot pass ran successfully on a 1,200 × 1,200 px crop of the 1882 map interior. 91 city-block polygons were retained after deduplication, classified as: 46 <em>particulier</em> (private), 24 <em>non affectées</em> (unassigned domain), 14 <em>communal</em>, 7 <em>local service</em> (flagged for review — these are cross-hatched and SAM fragments them). The preview below shows the processed tiles with polygons colour-coded by class.</p>
<figure>
  <img src="/images/blog/vectorize-preview-plot.jpg" alt="SAM plot-pass output on 1882 Saigon cadastral map — city blocks colour-coded by property class" style="width:100%;border:1px solid #ccc;border-radius:4px;" />
  <figcaption style="font-size:0.85em;color:#666;margin-top:0.5em;">Plot-pass output on a 1,200 × 1,200 px crop of the 1882 Saigon cadastral map. Salmon = <em>particulières</em> (private), green = communal, cream = unassigned domain. Each coloured shape is a single city block captured as one polygon at 8× downscale. The building-pass run (finer scale) will fill in individual footprints within each block.</figcaption>
</figure>

<h2>Where this stands</h2>
<p>The 1882 map is georeferenced and on Internet Archive. The plot pass is validated. The building pass is next, followed by the full-map run, then the 1898 preparation (Pixelmator seam correction on the BnF Gallica composite scan). Once both maps are vectorized, the vector-to-vector matching step — Hu moment descriptors, mutual-best-match, RANSAC — produces the change classification and auto-georefs the 1898 map simultaneously.</p>
<p>If you're working on historical city reconstruction — Hanoi, Phnom Penh, Manila, any city with a colonial-era cadastral survey — this architecture is designed to be forked.</p>
		`,
  },
  {
    slug: 'march-2026-update',
    title: "March 2026 Update: Maps, Methods, and What's Next",
    date: '2026-03-10',
    category: 'update',
    excerpt:
      "Featured in Saigoneer. Automated 500+ L7014 maps. Now planning the knowledge graph, 3D pipeline, and community tier system. Here's where things stand.",
    note: 'September 2026 — no tier system was ever built: there are no Photo Hunter or Cartographer roles, and no photogrammetry mission has run on any of the five landmarks. The 500+ L7014 sheets are georeferenced and served from Internet Archive, but were never ingested into this catalog, which holds 39 published sheets. The knowledge graph is still a design document. This was also the only monthly digest.',
    content: `
<p>This was meant to be the first monthly digest. The rule: two paragraphs, no slide decks, no meetings requested. What shipped, what didn't, what's next.</p>

<h2>What shipped</h2>
<p>The <strong>L7014 pipeline is complete and archived</strong>. 500+ US Army maps of Vietnam are georeferenced, datum-corrected (Indian 1960 → WGS84), and served over IIIF. The propagation algorithm — using seed maps to extrapolate corners across the regular grid — eliminated manual GCP placement for roughly 90% of the series. This work is done; the pipeline code has been retired now that the series is fully processed.</p>
<p>We were <strong>featured in Saigoneer</strong> (January 2026), Vietnam's leading English-language culture publication. The coverage framed the project clearly: we're not building a map app, we're building the spatial memory of a city most of the world has only seen in wartime. It brought the first readers who were not already looking for us.</p>

<h2>What didn't ship</h2>
<p>The knowledge graph is fully designed (schema, predicates, temporal encoding, source types) but not yet built. Community tracing UI exists as a label studio but lacks the gamification layer needed to attract contributors at scale. The 3D pipeline is planned in detail — we've adapted the Morlighem (TU Delft 2021) method to our IIIF output — but Phase 3 starts after Phase 1 footprints are in hand.</p>

<h2>What's next</h2>
<p><strong>Phase 1</strong> focus: ingest 30–50 colonial maps from BnF Gallica/EFEO, vectorize map features into geometry, build the community tracing UI with Photo Hunter + Cartographer tiers, launch the first photogrammetry missions for 5 landmark buildings (Notre Dame, City Hall, Central Post Office, Opera House, Ben Thanh Market). First public footprint dataset target: 1900 Saigon core.</p>
<p>We're actively looking for: a part-time French-reading researcher to work with ANOM/BnF archival sources, OSM mappers interested in historical Saigon tracing, and Blender artists for landmark 3D modelling. If that's you — or if you know a funder with a confirmed fit (French Institute, EFEO, Wikimedia, Asia Foundation) — say hello.</p>
		`,
  },
  {
    slug: 'dissecting-space-six-layer-methodology',
    title: 'Dissecting Space: The Six-Layer Method Behind the Archive',
    date: '2026-03-05',
    category: 'research',
    excerpt:
      "How we treat a historical city as a data stack — translating the modern world's six-layer spatial model into a framework that works with 19th-century maps, panoramic paintings, and archival photos.",
    note: 'September 2026 — the four contribution tiers in this post do not exist and no data or model weights have been published to Hugging Face. The L5 knowledge graph has no schema and no API in the codebase; “CRUD API in development” was optimistic. The height-uncertainty figures (±3 m → ±1.5 m) are what we expected from reading the method, not anything measured. L1 vectorization now means a fine-tuned SAM2 fork run on Colab, and it has produced no reviewed footprints yet. A second correction, 2026-09-19: the Indian 1960 \u2192 WGS 84 difference is stated here as \u201cup to 200 m\u201d. Measured since, it is about <strong>470 m</strong> \u2014 probed directly, <code>106.00,16.00</code> moves 470 m while <code>109.25,13.25</code> moves 0, and the shipped L7014 archive has 285 of 437 sheets sitting ~470 m northwest for exactly this reason. The mechanism described is right and the magnitude was understated by more than double.',
    content: `
<p>Every city is simultaneously a physical object, a set of economic relationships, a carrier of memory, and a political argument. Reconstructing one from archival sources requires separating these layers and building them in the right order. This post explains how we do that for 1880–1930 Saigon.</p>

<h2>The six-layer model</h2>
<p>We start from how the modern world is understood as spatial data:</p>
<p><em>Macro signal (satellite) → LiDAR → Road & facade → Building blocks → POI & economic activity → Human interaction</em></p>
<p>Each layer depends on the one below it. You can't model facade geometry without knowing where the buildings are. You can't place a business without a building to put it in. The dependency is strict.</p>
<p>Reconstructing a historical city means finding a substitute for each modern data source — or accepting that some layers must be built differently, or with lower resolution, from archival evidence.</p>

<h2>The historical translation</h2>
<p><strong>L1 — Historical maps (replaces satellite macro signal).</strong> The foundation is not satellite imagery — it's the historical map itself, georeferenced to modern coordinates and vectorized into geometry. Our pipeline handles the US Army L7014 series (500+ sheets) automatically via GCP propagation, and ingests French colonial maps (BnF Gallica, ANOM, EFEO) with manual control points. Georeferencing places the map; vectorization extracts what's on it as usable geometry. Both halves are needed. Status: georeferencing done for L7014, colonial maps ongoing, vectorization not yet started — the bigger half of this layer remains.</p>
<p><strong>L2 — LoD1 city mass (replaces LiDAR).</strong> Modern cities have LiDAR point clouds that directly produce mass 3D models. Colonial Saigon has none. Our substitute: two panoramic paintings of Saigon, from 1882 and 1898, that show the full city skyline with directly observable building heights. These are exceptionally rare primary sources — the commercial photography of the era almost never captured the roofline of an entire district. Combined with the Morlighem (TU Delft 2021) pipeline for automated building detection, they allow us to produce LoD1 box models for the full 1900 city core with height confidence scores. Status: method designed, panoramas documented, pipeline adaptation beginning.</p>
<p><strong>L3 — Road & facade → LoD2.</strong> The road network and basic facade geometry. In the modern world this comes from street-level camera passes and LiDAR returns off building surfaces. In the historical context, road geometry is extracted from the vectorized L1 maps; facade types (roof shapes, arcade structures, materiality) are inferred from archival photo evidence. The output is LoD2 — buildings with typed roofs and simplified surface geometry. Status: design phase.</p>
<p><strong>L4 — Building blocks → LoD3 mesh.</strong> For roughly 30 landmark buildings, we run structure-from-motion photogrammetry (COLMAP) on archival photo collections: EFEO surveys, BnF Gallica postcards (the 1900–1930 Saigon postcard industry produced enough multi-angle coverage to support SfM), Manhhai collection, family archives. Output: full textured 3D meshes. The 1900–1930 postcard industry turns out to be a gift — commercial incentive to photograph buildings from flattering angles produced exactly the overlapping coverage photogrammetry needs. Status: schema designed, first photo collection missions underway.</p>
<p><strong>L5 — Knowledge graph (POI & economic activity).</strong> Named places, businesses, institutions, ownership records, land use — stored as a typed graph with controlled predicates and ISO 8601 partial-date temporal encoding ('1905', '1905-03') for uncertain dates. The KG links directly to vectorized building geometries from L1. It is not just an additional layer — it is the connective tissue that gives the geometry its meaning. A building footprint without a name, an owner, and a political context is just a polygon. Status: schema complete, CRUD API in development.</p>
<p><strong>L6 — Human interaction.</strong> GPS-triggered narratives, community annotations on historical maps, oral history links, crowdsourced photo tagging. This is where most users experience the archive — and where community knowledge flows back into L5 as citable entries. The KG provides context to this layer; this layer feeds new facts into the KG. Status: GPS story system live, annotation tool live, KG integration not yet connected.</p>

<h2>Why the order matters</h2>
<p>The dependency rule is not a suggestion. L1 must exist before L3 (road geometry comes from the vectorized map). L2 heights are calibrated against L4 photo evidence. L5 entities anchor to L1 building geometries. L6 community contributions are only meaningful if L5 has the ontology to absorb them.</p>
<p>Build out of order and you accumulate debt that compounds upward. Our phase sequence — L1 vectorization and L6 community tools first, then L5 KG, then L2–L4 3D — reflects these dependencies. The 3D work (L2–L4) starts only after we have the vectorized footprints from L1 that the Morlighem pipeline needs as input.</p>

<h2>The HITL flywheel</h2>
<p>Community contributors tag historical photos to locations (raw material for L3–L4) and trace building outlines on georeferenced maps (L1 vectorization). This data trains a machine learning model. The model suggests outlines that contributors validate faster than they could trace from scratch. Faster contribution → more data → better model → faster contribution. The data and model weights are published openly on Hugging Face.</p>
<p>The four contribution tiers map to the stack: <strong>Photo Hunters</strong> feed L3–L4 with photo evidence; <strong>Cartographers</strong> vectorize L1 map features; <strong>Architects</strong> build L4 meshes via photogrammetry; <strong>Historians</strong> populate L5–L6 with KG entities and citations.</p>

<h2>The datum problem (a technical note)</h2>
<p>The US Army L7014 maps use the Indian 1960 datum (EPSG:3148), based on the Everest 1830 spheroid. Modern GPS and web maps use WGS84. The difference in Vietnam is up to 200m — enough to put a road in the middle of a field. We apply a Helmert 3-parameter geocentric shift (towgs84=+198,+881,+317) as specified in EPSG transform 1052. PROJ and QGIS do not always apply this automatically — the explicit proj4 string with towgs84 parameters is required. Skipping it produces maps that look correct until you overlay on satellite imagery and notice the roads are a city block off.</p>
<p>French colonial maps (ANOM, BnF Gallica, EFEO) have more varied coordinate situations: Paris meridian, local Vietnamese geodetic references, sometimes nothing documented. These require manual GCPs and Allmaps annotation — more labor-intensive but fully compatible with the same pipeline.</p>

<h2>What we've learned so far</h2>
<p>The propagation algorithm works: one manual georeference → 10 automated neighbors, error rate under 1% validated against independent seeds. The Morlighem pipeline is proven on Dutch and Belgian maps (>84% building detection, >99% valid CityJSON) and we expect it to adapt, with colour calibration work, to French colonial Saigon's symbology. The 1882 and 1898 panoramas are a more significant calibration source than we initially understood — they reduce height uncertainty from roughly ±3m to approximately ±1.5m for the 1900 core.</p>
<p>The methodology and the code are public. If you're working on a colonial-era map archive for another city, it is forkable — and worth reading with the note at the top of this post in hand.</p>
		`,
  },
  {
    slug: 'how-the-georef-pipeline-works',
    title: 'How GCP Propagation Georeferences a Whole Map Series',
    date: '2026-02-01',
    category: 'research',
    excerpt:
      'A plain-language explanation of the GCP propagation algorithm that turns a 500-sheet military map series into an automatically georeferenced archive.',
    note: 'September 2026 — this describes the L7014 batch, which is served from Internet Archive and was never ingested into this catalog: none of the 39 published sheets here is an L7014 sheet. The under-1% error figure compares propagated annotations against our own seed georeferences, not against independent ground truth, so it measures internal consistency rather than accuracy. The pipeline code was deleted in April 2026. A second correction, 2026-09-19: the Indian 1960 \u2192 WGS 84 difference is stated here as \u201cup to 200 m\u201d and \u201croughly 170 metres\u201d. Measured since, it is about <strong>470 m</strong> \u2014 probed directly, <code>106.00,16.00</code> moves 470 m while <code>109.25,13.25</code> moves 0, and the shipped L7014 archive has 285 of 437 sheets sitting ~470 m northwest for exactly this reason. The mechanism described is right and the magnitude was understated by more than double.',
    content: `
<p>Georeferencing a historical map means answering: where on Earth does this pixel sit? For a single map, you place control points by hand — match corners and landmarks to known coordinates — and a polynomial transform handles the rest. For 500 maps in a uniform series, doing this by hand would take months. We don't do it by hand.</p>

<h2>The key insight</h2>
<p>The US Army's L7014 Vietnam topographic series (1:50,000 scale, produced 1950s–1970s) is a <em>regular grid</em>. Each sheet covers exactly the same number of degrees of latitude and longitude. If you georeference one sheet precisely, you can compute the coordinates of every adjacent sheet purely from arithmetic — no image matching required.</p>
<p>We call this <strong>GCP propagation</strong>. The process: manually georeference ~10% of sheets (seeds) distributed evenly across the grid. For each seed, fit an affine transform to four corner ground control points. Then compute the expected lat/lon corners of every adjacent sheet by adding the known Δlon/Δlat. Build an Allmaps annotation from those computed corners. The result: one manual georeference propagates to cover roughly 10 neighboring sheets, and those propagate further.</p>

<h2>The datum problem</h2>
<p>These maps use the Indian 1960 datum (EPSG:3148), based on the Everest 1830 spheroid. Modern GPS and web maps use WGS84. The difference is not negligible — up to 200m in parts of Vietnam. We apply a Helmert 3-parameter geocentric shift (towgs84=+198,+881,+317 for mainland South Vietnam) before computing any coordinates. This is the correction specified in EPSG transform 1052 for the EPSG:3148 → WGS84 conversion.</p>
<p>One practical note: PROJ and QGIS don't always apply this shift automatically when reading EPSG:3148. We have to pass the explicit proj4 string with the towgs84 parameters. Skipping this produces maps that are systematically off by roughly 170 meters — which looks fine until you overlay it on satellite imagery and notice the roads don't match.</p>

<h2>The output</h2>
<p>Every georeferenced sheet is stored as a W3C Web Annotation (Georeference Annotation) JSON file in Supabase Storage, compatible with the Allmaps viewer. 500+ sheets processed. Error rate under 1% on propagated annotations validated against manually-georeferenced seeds. The series is complete.</p>
<p>The method generalizes: any uniform map series with known sheet dimensions can be processed the same way — Hanoi, Phnom Penh, Manila, anywhere the sheets were drawn to a grid.</p>
		`,
  },
  {
    slug: 'saigoneer-feature',
    title: "We're in Saigoneer — and What It Means",
    date: '2026-01-15',
    category: 'announcement',
    excerpt:
      "Saigoneer covered us in January 2026. Here's the project vision in plain language — recovering the body and soul of a city lost to wartime imagery.",
    note: 'September 2026 — the Photo Hunter tier was never built, and there is still no way to attach a photograph or a memory to a place. What a newcomer can actually do today: trace footprints at /scan?mode=trace, check what the OCR read at /scan?mode=triage, or place a sheet at /contribute/georef.',
    content: `
<p>Vietnam Map Archive was featured in Saigoneer on January 15, 2026. If you're reading this because of that article: welcome. Here's the short version of what we're doing and why.</p>

<h2>The problem</h2>
<p>Most of the world's mental image of Vietnam is the war. Napalm, jungle, helicopters. But Saigon in 1900 was a modernizing colonial metropolis — grand boulevards, a cathedral, an opera house, a postcard industry producing tens of thousands of images. That city is almost entirely absent from digital public memory. The maps exist, scattered across French national archives, American military repositories, and private collections. They're just disconnected from each other, from modern geography, and from the people whose families lived there.</p>

<h2>What we're doing</h2>
<p>We're connecting the maps to each other (georeferencing), to documents (knowledge graph), and eventually to three-dimensional space (3D reconstruction from archival photos). The method is human-in-the-loop: contributors trace buildings and check what the model read, and those corrections are what a better model would be trained on. The data is openly licensed either way.</p>
<p>The 1880–1930 focus is deliberate. This is the period when the French colonial administration physically remade Saigon — filling in canals to build boulevards, moving Chinese merchant communities to control land, building public monuments to assert cultural dominance. Understanding this period is not just historical curiosity. It's the origin of the city's current geography and the root of debates about public space, heritage, and memory that are active right now in Ho Chi Minh City.</p>

<h2>How to help</h2>
<p>Right now, the most useful thing is to <strong>find historical photos</strong> of Saigon buildings and tag them to locations. No technical skill required. If you recognize a street, a building, a neighborhood from your family's history — that knowledge is irreplaceable and we need it. The tool for it is designed and not built, so for the moment that means emailing us rather than clicking anything.</p>
<p>If you're a researcher, a GIS mapper, a Blender artist, or a foundation program officer — there's a specific role for you. The strategy and roadmap documents are public. Read them and reach out.</p>
		`,
  },
];

export function getPost(slug: string): BlogPost | undefined {
  return posts.find((p) => p.slug === slug);
}

export const CATEGORY_LABELS: Record<BlogPost['category'], string> = {
  update: 'Update',
  research: 'Research',
  community: 'Community',
  announcement: 'Announcement',
};

export const CATEGORY_COLORS: Record<BlogPost['category'], string> = {
  update: 'var(--color-blue)',
  research: 'var(--color-green)',
  community: 'var(--color-orange)',
  announcement: 'var(--color-purple)',
};
