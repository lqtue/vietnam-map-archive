export interface BlogPost {
  slug: string;
  title: string;
  date: string;
  category: 'update' | 'research' | 'community' | 'announcement';
  excerpt: string;
  content: string; // HTML
}

export const posts: BlogPost[] = [
  {
    slug: 'layer-stack-2026-05',
    title: 'Rebuilding /view Around a Single Concept: the Layer Stack',
    date: '2026-05-24',
    category: 'update',
    excerpt:
      'A short post on a long refactor. The map viewer had grown three overlapping mental models — active map, base map, compare set — each with their own UI surface, each leaking into the others. We collapsed them into one Photoshop-style layer stack with a single store, then redesigned mobile around two labeled bottom drawers.',
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
<p>VMA's core constraint is volunteer attention. Every minute spent hunting for a candidate map in BnF's catalog is a minute not spent georeferencing, OCR-ing, or annotating. By front-loading discovery into a tool that produces a curatable queue, we shift the work from "find one map at a time" to "review a batch and approve in bulk." The first pass already surfaces roughly twice as many viable candidates as VMA's current catalog of 100 maps — and that's before we extend the scout to Vietnamese-language sources (the National Archives have a digital catalog, and so does Hanoi's Institute of Sino-Nôm Studies).</p>
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
    title: 'New Collection: 63 Tonkin Topographic Sheets (1903–1927)',
    date: '2026-05-14',
    category: 'announcement',
    excerpt:
      "A batch of 63 colonial-era topographic sheets covering the Red River delta — Hà Nội, Hải Phòng, Nam Định, Thanh Hóa, and surrounding provinces — has been tiled to R2 and added to the catalog. All from the Service Géographique de l'Indochine, surveyed between 1903 and 1927.",
    content: `
<p>We've added <strong>63 new sheets</strong> to the catalog from the Service Géographique de l'Indochine — the French colonial mapping bureau that produced the most systematic topographic survey of northern Vietnam before WWII. The collection covers the Red River delta and surrounding provinces, with most sheets surveyed between 1903 and 1927 at roughly 1:100,000 scale.</p>

<h2>What's in the batch</h2>
<p>The sheets span the densely populated lowland north: Hà Nội itself (sheet 20, 1903), the port of Hải Phòng (31, 1904), and the major delta cities — Nam Định (55), Thái Bình (56), Ninh Bình (59), Phát Diệm (69), Thanh Hóa (75). Inland coverage extends to Sơn Tây (12), Bắc Ninh (10), Hưng Yên (42), and the Quảng Yên coastal zone (25, 32). A handful of named sheets sit outside the numbered grid: <em>Hà châu</em>, <em>Nhà nam</em>, <em>Bảo Lộc</em>, <em>Cẩm Lý</em>, and a cover plate that we've kept in the archive for completeness.</p>
<p>For anyone tracing genealogy or urban history in northern Vietnam, this is the layer beneath everything: the administrative boundaries, village names, and road networks that the post-1954 state inherited and reshaped. Place names are in pre-reform romanization (no diacritics), which is itself a useful diff against modern toponymy.</p>

<h2>Pipeline notes</h2>
<p>This is the first batch processed entirely through the consolidated bulk-upload pipeline. Each sheet now flows in one pass: <code>tile_map.sh</code> writes a DZI pyramid to R2 under <code>iiif.maparchive.vn/iiif/&lt;uuid&gt;</code>, the maps row is inserted with the sheet number preserved in <code>extra_metadata.sheet_number</code>, and the thumbnail URL is derived from the smallest pyramid level the worker advertises in <code>info.json</code>. No separate backfill step.</p>
<p>The previous version of the script split parsing across two passes — upload first, then run a clean-up to strip leading sheet numbers and fetch thumbnails. That worked but hid a latent bug: a <code>set -e + pipefail</code> shell trap silently aborted the cleanup on the first row whose name didn't have a leading number, which meant later uploads weren't being cleaned. Folding everything into the upload script eliminates the second pass and the failure mode at once.</p>

<h2>What's next for these sheets</h2>
<p>None of the new maps are georeferenced yet — they're in <code>draft</code> status until the corners are placed. The sheets are gridded enough that GCP propagation should work well: once we manually georeference one or two anchors per band, the rest can inherit corners arithmetically the same way the L7014 series did. After that, the OCR pipeline can scout the sheets for place names, and the toponym layer for northern Vietnam starts to materialize.</p>
<p>If you can read the older romanization confidently and want to help validate place-name extractions, this is exactly the kind of contributor work we're set up to support. <a href="/archive">Browse the catalog</a> to see the new sheets.</p>
		`,
  },
  {
    slug: 'mid-april-2026-platform-notes',
    title: 'Platform Notes: Universal IIIF, Gemini OCR, and the MapShell Refactor',
    date: '2026-04-18',
    category: 'update',
    excerpt:
      "Self-hosted tiles on R2 for better performance, a Gemini-powered OCR pipeline for toponym discovery, and a core architecture refactor around MapShell. April's updates focus on scaling our data foundation and unifying the user experience.",
    content: `
<p>Stability in a research archive comes from two places: the reliability of the data sources and the clarity of the interface. This week's updates address both, moving us away from reliance on institutional IIIF servers and toward a unified architecture that can support our next phase of growth.</p>

<h2>Universal IIIF: Solving the "Paris Latency" Problem</h2>
<p>For months, our performance has been throttled by the physical distance between our users and the primary scans hosted at the BnF in Paris. While Gallica is an invaluable partner, their IIIF Image API wasn't designed for high-concurrency tile requests from Southeast Asia. Furthermore, the mismatch between IIIF v2 (Gallica) and IIIF v3 (modern standards) required increasingly complex workarounds in our client code.</p>
<p>We've solved this by deploying a custom <strong>Cloudflare Worker and R2 backend</strong>. When a map is mirrored to our internal <code>iiif.maparchive.vn</code> service, we fetch the source image, tile it ourselves, and host it on the edge. The worker acts as a universal IIIF translator, serving perfect v3-compliant <code>info.json</code> manifests regardless of the original source. The result is a nearly 10x improvement in tile load times and a much simpler display layer.</p>

<h2>Project Scout: Gemini OCR for Map Discovery</h2>
<p>Georeferencing a map is only the first step. To make these maps searchable, we need to extract the text—street names, administrative boundaries, and landmark labels. Doing this manually for the 500+ sheets in our collection is impossible.</p>
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
    content: `
<p>The two most important maps we have of colonial Saigon — an 1882 cadastral survey and its 1898 revision — have never been compared as spatial data. They've been studied individually, scanned, and put online. But no one has asked: which buildings appear in both? Which ones were built or demolished in those sixteen years? And can that shared knowledge help us georeference the maps themselves?</p>
<p>The answer to the last question turns out to be yes — and it changes how we think about the whole problem of historical map vectorization.</p>

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
<p>The full pipeline code is in the VMA repository. If you're working on historical city reconstruction — Hanoi, Phnom Penh, Manila, any city with a colonial-era cadastral survey — this architecture is designed to be forked.</p>
		`,
  },
  {
    slug: 'march-2026-update',
    title: "March 2026 Update: Maps, Methods, and What's Next",
    date: '2026-03-10',
    category: 'update',
    excerpt:
      "Featured in Saigoneer. Automated 500+ L7014 maps. Now planning the knowledge graph, 3D pipeline, and community tier system. Here's where things stand.",
    content: `
<p>This is the first monthly digest. The rule: two paragraphs, no slide decks, no meetings requested. What shipped, what didn't, what's next.</p>

<h2>What shipped</h2>
<p>The <strong>L7014 pipeline is complete and archived</strong>. 500+ US Army maps of Vietnam are georeferenced, datum-corrected (Indian 1960 → WGS84), and served over IIIF. The propagation algorithm — using seed maps to extrapolate corners across the regular grid — eliminated manual GCP placement for roughly 90% of the series. This work is done; the pipeline code has been retired now that the series is fully processed.</p>
<p>We were <strong>featured in Saigoneer</strong> (January 2026), Vietnam's leading English-language culture publication. The coverage framed the project clearly: we're not building a map app, we're building the spatial memory of a city most of the world has only seen in wartime. The response from the Vietnamese diaspora community was immediate and warm.</p>

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
<p>The methodology is public. The pipeline is open. If you're working on historical city reconstruction for another Southeast Asian city — or anywhere with a colonial-era map archive — this framework is forkable. That's the point.</p>
		`,
  },
  {
    slug: 'how-the-georef-pipeline-works',
    title: 'How We Automate Georeferencing of 500 Historical Maps',
    date: '2026-02-01',
    category: 'research',
    excerpt:
      'A plain-language explanation of the GCP propagation algorithm that turns a 500-sheet military map series into an automatically georeferenced archive.',
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
<p>The method generalizes: any uniform map series with known sheet dimensions can be processed the same way. Hanoi. Phnom Penh. Manila. Whoever runs this first for their city's archive owns the result permanently.</p>
		`,
  },
  {
    slug: 'saigoneer-feature',
    title: "We're in Saigoneer — and What It Means",
    date: '2026-01-15',
    category: 'announcement',
    excerpt:
      "Saigoneer covered us in January 2026. Here's the project vision in plain language — recovering the body and soul of a city lost to wartime imagery.",
    content: `
<p>Vietnam Map Archive was featured in Saigoneer on January 15, 2026. If you're reading this because of that article: welcome. Here's the short version of what we're doing and why.</p>

<h2>The problem</h2>
<p>Most of the world's mental image of Vietnam is the war. Napalm, jungle, helicopters. But Saigon in 1900 was a modernizing colonial metropolis — grand boulevards, a cathedral, an opera house, a postcard industry producing tens of thousands of images. That city is almost entirely absent from digital public memory. The maps exist, scattered across French national archives, American military repositories, and private collections. They're just disconnected from each other, from modern geography, and from the people whose families lived there.</p>

<h2>What we're doing</h2>
<p>We're connecting the maps to each other (georeferencing), to documents (knowledge graph), and eventually to three-dimensional space (3D reconstruction from archival photos). The method is HITL — Human-in-the-Loop — where community contributors trace buildings and tag photos, which trains AI that accelerates future contributions, which produces better data, which trains better AI. The community builds the data. The AI accelerates the community. The output is open and permanent.</p>
<p>The 1880–1930 focus is deliberate. This is the period when the French colonial administration physically remade Saigon — filling in canals to build boulevards, moving Chinese merchant communities to control land, building public monuments to assert cultural dominance. Understanding this period is not just historical curiosity. It's the origin of the city's current geography and the root of debates about public space, heritage, and memory that are active right now in Ho Chi Minh City.</p>

<h2>How to help</h2>
<p>Right now, the most useful thing is to <strong>find historical photos</strong> of Saigon buildings and tag them to locations. No technical skill required. If you recognize a street, a building, a neighborhood from your family's history — that knowledge is irreplaceable and we need it. The Photo Hunter tier is designed for exactly this: zero barrier, mobile-friendly, immediately meaningful.</p>
<p>If you're a researcher, a GIS mapper, a Blender artist, or a foundation program officer — there's a specific role for you. The strategy and roadmap documents are public. Read them and reach out.</p>
		`,
  },
];

export function getPost(slug: string): BlogPost | undefined {
  return posts.find((p) => p.slug === slug);
}

export const CATEGORY_LABELS: Record<BlogPost['category'], string> = {
  update: 'Monthly Update',
  research: 'Research',
  community: 'Community',
  announcement: 'Announcement',
};

export const CATEGORY_COLORS: Record<BlogPost['category'], string> = {
  update: 'var(--accent)',
  research: 'var(--status-ok)',
  community: 'var(--status-warn)',
  announcement: 'var(--accent)',
};
