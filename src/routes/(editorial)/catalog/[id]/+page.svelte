<!--
  /catalog/[id] — the shareable record for one map.

  Server-rendered (see +page.server.ts) so link previews work. Everything
  interactive lives one click away in /explore?map=<id>.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';
  import PageHero from '$lib/ui/PageHero.svelte';
  import { onMount } from 'svelte';
  import {
    allmapsTileUrl,
    allmapsEditorSourceUrl,
    ohmEditorUrl,
  } from '$lib/core/iiif/annotationUrl';
  import { placeHref } from '$lib/core/utils/placeKey';
  import { exploreHref, mapRef } from '$lib/core/utils/mapSlug';
  import { page } from '$app/stores';
  import { SITE_ORIGIN } from '$lib/core/site';
  import { jsonLd } from '$lib/core/utils/jsonLd';

  import SheetZoom from '$lib/features/catalog/SheetZoom.svelte';
  import SupersededSheet from '$lib/features/catalog/SupersededSheet.svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchUserRole, type UserRole } from '$lib/data/supabase/role';

  export let data;
  $: map = data.map;
  /* False only for a draft, which the loader serves to signed-in readers alone.
     `!== false` so an older cached payload without the field reads as published
     rather than banner-ing every sheet. */
  $: published = data.published !== false;
  /** IGN's own half-sheets, when this row is a third party's join of them. */
  $: originals = data.originals ?? [];
  /** Places this sheet names, from the gazetteer. Empty until the map is OCR'd. */
  $: places = (data.places ?? []) as Array<{
    name_key: string;
    name: string;
    mentions: number;
  }>;

  // The R2 worker advertises level2 but is really level0 plus a proxy, so an
  // arbitrary width can 404. `thumbnail` is a size we know exists; the derived
  // 800px URL is only a fallback for maps that never got one.
  $: shareImage =
    map.thumbnail ??
    (map.iiif_image ? `${map.iiif_image.replace(/\/$/, '')}/full/800,/0/default.jpg` : null);

  /* Falls back to the host when the row has no `holding_institution` — thirteen
     published maps are in that state, all with a usable `source_url`. */
  $: sourceHost = (() => {
    try {
      return new URL(map.source_url ?? '').hostname.replace(/^www\./, '');
    } catch {
      return 'the source';
    }
  })();

  $: subtitle = [map.year_label ?? map.year, map.creator, map.holding_institution]
    .filter(Boolean)
    .join(' · ');
  /* A description is written intro-first, with source notes and caveats after a
     blank line. The <p> below rendered the whole thing as one run-on, and the
     meta description carried all of it — search results cut at ~155 characters,
     so the intro is what belongs there. */
  $: paragraphs = (
    map.dc_description ??
    `${map.name} — a historical map of ${map.location ?? 'Vietnam'} in the Vietnam Map Archive.`
  )
    .split(/\n\s*\n/)
    .map((t) => t.trim())
    .filter(Boolean);
  $: blurb = paragraphs[0];

  $: shareUrl = SITE_ORIGIN + $page.url.pathname;

  /**
   * The record as schema.org sees it. A scanned sheet is a `Map`, and the
   * fields a catalogue already keeps — who drew it, when, who holds it now,
   * under what rights — are the ones that let a result carry more than a
   * title. Every value is dropped when the column is null rather than sent as
   * an empty string, which reads as a claim that the answer is "nothing".
   */
  $: mapSchema = jsonLd(
    Object.fromEntries(
      Object.entries({
        '@context': 'https://schema.org',
        '@type': 'Map',
        name: map.name,
        alternateName: map.original_title ?? undefined,
        description: blurb,
        url: shareUrl,
        image: shareImage ?? undefined,
        inLanguage: 'en',
        dateCreated: map.year ? String(map.year) : undefined,
        temporalCoverage: map.year_label ?? (map.year ? String(map.year) : undefined),
        creator: map.creator ? { '@type': 'Organization', name: map.creator } : undefined,
        publisher: map.dc_publisher
          ? { '@type': 'Organization', name: map.dc_publisher }
          : undefined,
        holdingArchive: map.holding_institution
          ? { '@type': 'ArchiveOrganization', name: map.holding_institution }
          : undefined,
        identifier: map.shelfmark ?? undefined,
        license: map.rights ?? undefined,
        contentLocation: map.location ? { '@type': 'Place', name: map.location } : undefined,
        isPartOf: {
          '@type': 'Collection',
          name: 'Vietnam Map Archive',
          url: `${SITE_ORIGIN}/catalog`,
        },
      }).filter(([, v]) => v !== undefined)
    )
  );

  // Tracing this sheet into OpenHistoricalMap needs the warped map as XYZ
  // tiles. Allmaps' tile server does the warping from the annotation we
  // already host, so there is nothing to generate here — only a URL to hand over.
  $: tileSource = map.annotation_url ?? map.allmaps_id;
  $: tileUrl = map.georef_done && tileSource ? allmapsTileUrl(tileSource) : null;
  $: bbox = (map.bbox ?? null) as number[] | null;
  $: ohmUrl = tileUrl && ohmEditorUrl(tileUrl, bbox);

  // Reopening a published sheet's control points. Staff only: an edit in the
  // Allmaps Editor lands on annotations.allmaps.org, which is what every map
  // without its own `annotation_url` renders from — so it moves a live map.
  const { supabase, session } = getSupabaseContext();
  let role: UserRole = 'user';
  onMount(async () => {
    role = (await fetchUserRole(supabase, session?.user?.id)) ?? 'user';
  });
  $: canFixGeoref = role === 'admin' || role === 'mod';
  $: editorSource = allmapsEditorSourceUrl(map, map.map_iiif_sources ?? [], data.editorSourceId);
  $: editorUrl = editorSource
    ? `https://editor.allmaps.org/#/collection?url=${encodeURIComponent(editorSource)}`
    : null;

  let copied = false;
  async function copyTileUrl() {
    if (!tileUrl) return;
    await navigator.clipboard.writeText(tileUrl);
    copied = true;
    setTimeout(() => (copied = false), 1500);
  }

  const facts = (m: typeof map) =>
    [
      ['Year', m.year_label ?? m.year],
      ['Original title', m.original_title],
      ['Creator', m.creator],
      ['Publisher', m.dc_publisher],
      ['Held by', m.holding_institution],
      ['Shelfmark', m.shelfmark],
      ['Rights', m.rights],
      ['Collection', m.collection],
      ['Place', m.location],
      ['Type', m.map_type],
      ['Format', m.physical_description],
      ['Subject', m.dc_subject],
    ].filter(([, v]) => v) as [string, string][];
</script>

<svelte:head>
  <title>{map.name} — Vietnam Map Archive</title>
  {#if !published}
    <!-- A draft is reachable so contributors can look at the scan, not so a
         crawler can index a record the archive has not stood behind yet. -->
    <meta name="robots" content="noindex, nofollow" />
  {/if}
  <meta name="description" content={blurb} />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="Vietnam Map Archive" />
  <meta property="og:url" content={shareUrl} />
  <meta property="og:title" content={map.name} />
  <meta property="og:description" content={blurb} />
  {#if shareImage}
    <meta property="og:image" content={shareImage} />
    <!-- The stored thumbnail is 800px on its long edge. Declaring it lets a
         crawler build the large card without fetching the file first; without
         the dimensions several of them fall back to the small one. -->
    <meta property="og:image:width" content="800" />
    <meta property="og:image:alt" content={map.name} />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:image" content={shareImage} />
    <meta name="twitter:image:alt" content={map.name} />
  {:else}
    <meta name="twitter:card" content="summary" />
  {/if}
  <meta name="twitter:title" content={map.name} />
  <meta name="twitter:description" content={blurb} />
  <!-- The only markup here is the <script> tag `jsonLd` writes; every value
       inside it goes through JSON.stringify with `<` escaped, so nothing in
       the payload can open a tag. -->
  <!-- eslint-disable-next-line svelte/no-at-html-tags -->
  {@html mapSchema}
</svelte:head>

<div class="page">
  <PageHero eyebrow="Archive" title={map.name} sub={subtitle} />

  <main class="editorial-main share-page">
    {#if !published}
      <p class="share-draft">
        {$t(
          'This sheet is a draft: it is not published, and this page is visible only because you are signed in.'
        )}
      </p>
    {/if}

    <SheetZoom iiifImage={map.iiif_image} preview={shareImage} title={map.name} />

    {#each paragraphs as para, i (i)}
      <p class="share-blurb">{para}</p>
    {/each}

    <div class="share-actions">
      <!-- Only /explore: it lays the warped sheet on the world, which is the one
         thing this page cannot do. There is no "open the scan" button because
         the scan is on this page — the button existed for a week, pointing at
         /scan?map=, and that address now redirects back here. -->
      {#if map.georef_done}
        <a class="btn" href={exploreHref(map)}>{$t('Open on the map')}</a>
      {/if}
      <a class="btn" href="/catalog">{$t('Browse the archive')}</a>
      {#if map.source_url}
        <a class="btn" href={map.source_url} target="_blank" rel="noopener noreferrer">
          {$t('View the original at {institution}', {
            institution: map.holding_institution ?? sourceHost,
          })}
        </a>
      {/if}
    </div>

    {#if tileUrl}
      <section class="share-trace">
        <h2>{$t('Trace this sheet in OpenHistoricalMap')}</h2>
        <p>
          {$t(
            'The sheet is served as warped map tiles, so it can sit under the OpenHistoricalMap editor while you draw. The button opens the editor with it already set as the background; if the editor does not pick it up, add it by hand under Background → Custom with this URL.'
          )}
        </p>
        <div class="share-actions">
          <a class="btn" href={ohmUrl} target="_blank" rel="noopener"
            >{$t('Open in OpenHistoricalMap')}</a
          >
          <button class="btn" type="button" on:click={copyTileUrl}>
            {copied ? 'Copied' : 'Copy tile URL'}
          </button>
          {#if canFixGeoref && editorUrl}
            <a class="btn" href={editorUrl} target="_blank" rel="noopener">
              Fix georeference in Allmaps
            </a>
          {/if}
        </div>
        {#if canFixGeoref && !editorUrl}
          <p class="share-georef-warn">
            No IIIF manifest or original image source on this map, so the Allmaps Editor has nothing
            to open. Add one in the catalog edit modal first.
          </p>
        {/if}
        {#if canFixGeoref && map.annotation_url}
          <p class="share-georef-warn">
            This map renders from our own mirrored annotation, so an edit in Allmaps will not show
            here until someone runs <strong>Fetch latest from Allmaps</strong> in the catalog edit modal.
          </p>
        {/if}
        <code class="share-tile-url">{tileUrl}</code>
      </section>
    {/if}

    <SupersededSheet {originals} />

    {#if places.length}
      <section class="share-places">
        <h2>{$t('Places named on this sheet')}</h2>
        <ul>
          {#each places as p (p.name_key)}
            <li><a href={placeHref(p.name_key)}>{p.name}</a></li>
          {/each}
        </ul>
        <p class="share-places-note">
          {$t(
            'Read by optical character recognition from the sheet itself, then corrected by hand where a reviewer has reached it.'
          )}
        </p>
      </section>
    {/if}

    {#if facts(map).length}
      <dl class="share-facts">
        {#each facts(map) as [label, value] (label)}
          <div class="share-fact">
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        {/each}
      </dl>
    {/if}
  </main>
</div>

<style>
  .share-trace {
    margin: 0;
    text-align: left;
  }
  .share-trace h2 {
    margin: 0 0 var(--space-2);
    font-size: var(--text-base);
  }
  .share-trace p {
    margin: 0 0 var(--space-3);
    font-size: var(--text-sm);
    color: var(--color-gray-500);
  }
  .share-georef-warn {
    margin: var(--space-2) 0 0;
    font-size: var(--text-xs);
    color: var(--color-gray-500);
  }
  .share-tile-url {
    display: block;
    overflow-x: auto;
    padding: var(--space-2);
    border: var(--border-thin);
    border-radius: var(--radius-md);
    background: var(--color-gray-100);
    font-size: var(--text-xs);
    white-space: nowrap;
  }

  .share-places {
    margin: 0;
    text-align: left;
  }
  .share-places h2 {
    margin: 0 0 var(--space-2);
    font-size: var(--text-base);
  }
  .share-places ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-2);
  }
  .share-places a {
    display: inline-block;
    padding: 2px var(--space-2);
    border: var(--border-thin);
    border-radius: var(--radius-pill);
    background: var(--color-white);
    color: inherit;
    font-size: var(--text-sm);
    text-decoration: none;
  }
  .share-places a:hover {
    background: var(--color-gray-50);
  }
  .share-places-note {
    margin: var(--space-2) 0 0;
    font-size: var(--text-xs);
    color: var(--color-gray-500);
  }

  /* `.editorial-main` (editorial.css) carries the centring, the padding and
     the column; only the narrower measure and the tighter rhythm — the direct
     children here include the paragraphs of one description, not cards — are
     this page's own. */
  .share-page {
    max-width: 56rem;
    gap: var(--space-6);
  }

  .share-draft {
    margin: 0;
    padding: var(--space-3);
    border: var(--border-thin);
    border-radius: var(--radius-md);
    background: var(--color-gray-100);
    font-size: var(--text-sm);
    color: var(--color-gray-500);
  }

  .share-blurb {
    margin: 0;
    font-size: var(--text-lg);
    line-height: 1.6;
    color: var(--color-text);
  }

  .share-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
  }

  .share-facts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    gap: var(--space-4);
    margin: 0;
    padding-top: var(--space-4);
    border-top: var(--border-thin);
  }

  .share-fact dt {
    font-size: var(--text-sm);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-gray-500);
  }

  .share-fact dd {
    margin: var(--space-1) 0 0;
    color: var(--color-text);
  }
</style>
