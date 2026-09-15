<script lang="ts">
  import { SITE_ORIGIN } from '$lib/core/site';
  import { jsonLd } from '$lib/core/utils/jsonLd';
  import { t } from '$lib/core/i18n';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import type { PageData } from './$types';
  import type { MapListItem } from '$lib/data/maps/types';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { addFavorite, removeFavorite } from '$lib/data/supabase/favorites';
  import { loadFavorites, resolveThumbnails } from '$lib/features/catalog/homeCatalog';
  import FeaturedSheet from '$lib/features/catalog/FeaturedSheet.svelte';
  import HeroDemo from '$lib/features/explore/HeroDemo.svelte';
  import Tabs from '$lib/ui/Tabs.svelte';
  import PaletteSearchField from '$lib/ui/PaletteSearchField.svelte';
  import { openPaletteWith, pageOwnsSearch } from '$lib/core/utils/commandPalette';
  import { tweenValue } from '$lib/core/utils/tween';
  import '$styles/layouts/home.css';

  const { supabase, session } = getSupabaseContext();

  /** The featured sheets and the count, server-rendered — see `+page.server.ts`. */
  export let data: PageData;

  let favoriteMaps: MapListItem[] = [];
  let favoriteIds: string[] = [];
  let thumbnails: Map<string, string> = new Map();
  /** Only the Favorites tab ever waits: the featured set is already in the HTML. */
  let loadingFavorites = false;
  let filterCollection: 'featured' | 'favorites' = 'featured';

  /**
   * The sheet the "how this works" section plays, and how to hold it.
   *
   * `bbox` is what to frame, so the demo shows the whole sheet with a margin
   * rather than a pinned detail of it — `HeroMap.fitSheet` works out the zoom
   * from the stage's own size, which is the only way one number is right on a
   * phone and on a 27-inch screen at once.
   *
   * It is **not** `maps.bbox`. That column is the bbox of the georeferenced
   * *mask*; what the warped layer actually draws is the whole scan — paper
   * edges, shelfmark, legend — which here runs 830 m further east than the
   * mask does, so fitting the column cropped the bottom of the sheet. These
   * are the scan's four corners `(0,0)…(width,height)` put through the
   * annotation's own transform. Swapping the sheet means recomputing them;
   * the cheap check is the shot itself, since anything clipped is visible in
   * `hero-1882.webp`.
   *
   * `rotation` holds the sheet square in the frame, which for this one is
   * essentially a quarter turn: the scan's own x-axis runs north, so at
   * rotation 0 the sheet stands on end and a 16:9 stage is mostly margin.
   * /explore is where to find it for another sheet — ⌘/ctrl-drag until the
   * sheet sits square, then take the `r` out of the address bar
   * (`#@<lat>,<lng>,<zoom>z,<rotation>r`).
   *
   * The sheet has to be georeferenced and mirrored (publishing enqueues
   * `mirror_annotation`), because HeroMap plays our own copy of the annotation.
   *
   * ponytail: hardcoded rather than queried. Picking "the sheet with the most
   * of everything" needs a join the front page has no other use for; when a
   * second sheet is this complete, that is the moment to write it. This one is
   * the only sheet carrying all three layers the demo shows — a georeference,
   * 46 traced footprints and 43 validated OCR labels — so it is the only one
   * where the sequence tells the truth.
   */
  const HERO_SHEET = {
    id: '0e02b9d9-9d40-4cca-8e41-8c8373d54d3b',
    /* Pinned alongside the uuid rather than looked up: this is a hard-coded
       sheet, and the slug is what the outbound link should say. The uuid stays
       as the identity — `maps.slug` can be re-minted, `maps.id` cannot. */
    slug: 'plan-cadastral-de-la-ville-de-saigon-cochinchine-francaise',
    view: {
      bbox: [106.687488, 10.759901, 106.716015, 10.797223] as [number, number, number, number],
      rotation: 1.5772,
    },
  };

  /**
   * The header used to be the live map itself, which put OpenLayers,
   * ol-pmtiles and Allmaps in the front page's first chunk — 179 kB of
   * JavaScript with ~390 kB of basemap behind it — before the masthead had
   * painted. It is two stills now, cross-faded by the slider in the column,
   * and the real map plays further down in `HeroDemo` for a reader who
   * scrolls to it. The two come out of one shoot, which is why the ends of the
   * slider line up to the pixel.
   *
   * They are a **pinned close-up, kept on purpose**. `HERO_SHEET` below now
   * frames the whole sheet, and the live section was refitted to it; the
   * header was left as it was. So `scripts/gen-hero-still.mjs`, which shoots
   * the live section, would replace these with the wide view — a decision,
   * not a repair. Re-run it only when you want the header to follow the demo
   * again.
   */
  const HERO_NOW = '/images/hero-now.webp';
  const HERO_1882 = '/images/hero-1882.webp';

  /**
   * The demo section's own assets, which are **not** the header's. These come
   * out of `scripts/gen-hero-video.mjs`, which records the live section — so
   * they are the wide camera the section actually uses, and the poster is the
   * clip's own first frame. Handing the section `HERO_1882` instead is what put
   * an enlarged sheet behind the live map: that still is the pinned close-up,
   * kept deliberately for the header above and wrong for the section below.
   */
  const HERO_CLIP = '/video/hero-demo.mp4';
  const HERO_CLIP_SMALL = '/video/hero-demo-800.mp4';
  const HERO_CLIP_POSTER = '/video/hero-demo-poster.webp';

  /**
   * The header image is full-bleed, so a 390px phone was being handed the whole
   * 1600px frame — 331 kB for the pair, a third of the front page at rest, most
   * of it pixels the screen cannot draw. `gen-hero-still.mjs` writes an 800px
   * cut beside each one; this is the naming convention, in the one place that
   * needs to know it.
   *
   * `wide` because the two shoots do not agree on it: the stills are 1600 and
   * the clip's poster is 1200, which is the width its own recording is encoded
   * at. Declaring the poster as 1600w would have the browser pick it for a
   * screen it cannot fill.
   */
  const twoCuts = (src: string, wide = 1600) =>
    `${src.replace('.webp', '-800.webp')} 800w, ${src} ${wide}w`;

  /**
   * How much of the 1882 sheet the header shows: 1 is the sheet, 0 is the
   * satellite image under it. It starts on the sheet — that is the archive,
   * and the city underneath is what the reader already knows.
   */
  let heroSheet = 1;

  /**
   * The header shows what it does, and keeps showing it until someone takes
   * the control. A slider that nobody drags is a slider nobody knows is there,
   * and this one carries the whole idea of the archive, so shortly after the
   * page settles it starts crossing between the 1882 sheet and the imagery and
   * goes on doing that until the reader's first touch.
   *
   * Two earlier versions, both wrong in the same direction: it ran once a tab
   * behind `vma-hero-swept-v1` (so anyone who had already opened the front page
   * in that tab never saw it — which is everyone testing it), and then once per
   * load (so anyone who looked away for four seconds missed it and had no way
   * to ask for it again). Explicitly requested to run until dragged, Sept 2026.
   *
   * The three parts not to "simplify":
   *   - it stops dead on the reader's first `pointerdown` or `keydown`, and
   *     never restarts. A control that keeps animating under a finger is
   *     fighting the person using it, and that first touch is the whole reason
   *     the loop exists;
   *   - it never runs under `prefers-reduced-motion`;
   *   - it holds at each end. Without the dwell it is a metronome, and the two
   *     states it is comparing never actually sit still long enough to be read.
   *
   * On WCAG 2.2.2 (moving content over five seconds needs a way to stop it):
   * the slider is that mechanism — it is visible, it is the obvious thing to
   * grab, and touching it ends the motion for good. `prefers-reduced-motion`
   * covers the vestibular case ahead of that.
   */
  const SWEEP_DELAY_MS = 1100;
  /** Time moving, both legs together. The dwell is on top of this. */
  const SWEEP_MS = 2800;
  /** Rest at each end, so both states can actually be looked at. */
  const SWEEP_HOLD_MS = 900;
  /** How far down the sweep goes. Not 0: the point is "this moves", not "look at a satellite photo". */
  const SWEEP_FLOOR = 0.12;

  let heroTouched = false;

  function sweepHeroSlider(): (() => void) | undefined {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;

    const leg = SWEEP_MS / 2;
    const cycle = SWEEP_MS + SWEEP_HOLD_MS * 2;

    let frame = 0;
    const timer = window.setTimeout(() => {
      const start = performance.now();
      const step = (now: number) => {
        if (heroTouched) return;
        // One cycle: down, dwell on the imagery, back up, dwell on the sheet.
        // `k` is 0 at the sheet and 1 at the imagery; the easing is the curve
        // the annotate-mode timeline uses, so neither turn is a corner.
        const at = (now - start) % cycle;
        let k: number;
        if (at < leg) k = at / leg;
        else if (at < leg + SWEEP_HOLD_MS) k = 1;
        else if (at < SWEEP_MS + SWEEP_HOLD_MS) k = 1 - (at - leg - SWEEP_HOLD_MS) / leg;
        else k = 0;
        heroSheet = tweenValue(1, SWEEP_FLOOR, k);
        frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    }, SWEEP_DELAY_MS);

    return () => {
      clearTimeout(timer);
      cancelAnimationFrame(frame);
    };
  }

  /**
   * The figures quoted in the copy below. A dated snapshot on purpose —
   * refresh them when they embarrass us, which is the point of putting them on
   * the front page. `labels` is distinct names, not rows: the OCR pass has been
   * re-run on some sheets and `ocr_extractions` holds 1,767 rows for 958 actual
   * labels, so quoting the row count would inflate the number by 85%.
   */
  /**
   * The front page's hand-kept numbers. `mapCount` beside them is a real query
   * over `maps`, and the two answer different questions on purpose: a catalogue
   * record is a sheet someone can open, while `sheetsDrawn` counts everything
   * the map can paint — 452 of which are cells of the L7014 mosaic and have no
   * `maps` row at all. Say which is which wherever both appear.
   */
  const STATS = {
    snapshot: 'September 2026',
    labels: 958,
    labelsChecked: 43,
    footprints: 46,
    l7014Held: 461,
    l7014Total: 627,
    sheetsDrawn: 583,
    sheetsDrawnBefore: 94,
  };

  /**
   * The three things to type into an empty search box. Every one of them
   * currently returns something — seven sheets for Hanoi, two OCR'd labels for
   * Khánh Hội, several sheets for the year — which is the whole point: a
   * suggestion that returns nothing is worse than none. Re-check them when the
   * corpus changes.
   *
   * The spellings are load-bearing, and not consistently: map search runs on
   * the `simple` tsvector config, so `Hanoi` hits the seven French and
   * American sheets whose titles romanise it while `Hà Nội` finds only the one
   * that does not — but `Ha Noi` spaced hits nothing at all. Labels do fold,
   * so `Khánh Hội` and `Khanh Hoi` are equivalent; the accented form is here
   * because it is what the sheet prints.
   */
  const HERO_TRIES = ['Hanoi', 'Khánh Hội', '1882'];

  /**
   * The key that opens the palette. Set in `onMount` rather than at init: the
   * page server-renders, and hydration reuses a text node without re-reading
   * it — so the correction has to happen after, as a normal update.
   */
  let paletteKey = '⌘K';

  /**
   * Counted by the server, so it is right in the HTML a crawler reads. The
   * fallback covers a failed query rather than a slow one — the alternative is
   * a sentence claiming the archive holds zero sheets.
   */
  const MAP_COUNT_FALLBACK = 39;
  $: mapCount = data.mapCount || MAP_COUNT_FALLBACK;

  /**
   * One sentence, three places: the meta description, the OG card and the
   * Twitter card. It used to carry the sheet count as a literal three lines
   * under the constant that already held it, which is the kind of pair that
   * drifts the day a fortieth sheet publishes.
   */
  $: metaDescription =
    `A small volunteer archive of historical maps of Vietnam — Saigon, Huế and Hanoi so far. ` +
    `${mapCount} sheets are georeferenced and readable in a browser; tracing and label work have only just started.`;

  /**
   * Absolute, because a share card is read by a crawler with no page to resolve
   * a relative path against. Off `$page.url` rather than a hardcoded host, so
   * a preview deploy links to itself and the production domain is not a
   * constant that has to be maintained in a second place.
   */
  $: shareImage = new URL(HERO_1882, $page.url).href;
  /* `og:url` only — the canonical tag itself is the root layout's, which emits
     one for every page. Two canonicals on a page is the same as none. The
     pathname is `/` or `/vi`, and both are addresses a crawler should keep. */
  $: canonical = SITE_ORIGIN + $page.url.pathname;

  /* The archive as a thing search engines can name, rather than a page they
     have to infer one from. No `SearchAction`: /catalog takes no `?q=`, and a
     target that does not filter is a claim Google would be right to distrust. */
  $: siteSchema = jsonLd({
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'Vietnam Map Archive',
    alternateName: 'VMA',
    url: SITE_ORIGIN,
    inLanguage: ['en', 'vi'],
    description: metaDescription,
  });

  $: displayedMaps = filterCollection === 'featured' ? data.featured : favoriteMaps;

  /**
   * Two client-side jobs, and neither blocks the page: the reader's favorites,
   * and the thumbnails for maps whose `thumbnail` column is empty — those have
   * to be read out of an annotation one at a time.
   */
  async function loadReaderData() {
    thumbnails = await resolveThumbnails(data.featured);

    if (!session?.user?.id) return;
    loadingFavorites = true;
    try {
      const favorites = await loadFavorites(supabase, session.user.id);
      favoriteMaps = favorites.maps;
      favoriteIds = favorites.ids;
      thumbnails = new Map([...thumbnails, ...(await resolveThumbnails(favorites.maps))]);
    } catch (err) {
      console.error('Failed to load favorites:', err);
    } finally {
      loadingFavorites = false;
    }
  }

  async function toggleFavorite(mapId: string) {
    if (!session?.user?.id) return;
    const userId = session.user.id;
    const wasFavorited = favoriteIds.includes(mapId);

    // Optimistic: reassign rather than mutate, or the heart does not repaint.
    favoriteIds = wasFavorited ? favoriteIds.filter((id) => id !== mapId) : [...favoriteIds, mapId];

    const ok = wasFavorited
      ? await removeFavorite(supabase, userId, mapId)
      : await addFavorite(supabase, userId, mapId);

    if (!ok) {
      favoriteIds = wasFavorited
        ? [...favoriteIds, mapId]
        : favoriteIds.filter((id) => id !== mapId);
      return;
    }

    // Keep the Favorites tab in step without a round trip. Anything favorited
    // from this page is on it, so the record is already here.
    if (wasFavorited) {
      favoriteMaps = favoriteMaps.filter((m) => m.id !== mapId);
      return;
    }
    const added = data.featured.find((m) => m.id === mapId);
    if (added && !favoriteMaps.some((m) => m.id === mapId)) favoriteMaps = [...favoriteMaps, added];
  }

  onMount(loadReaderData);
  onMount(sweepHeroSlider);

  /**
   * The hero's field and the nav's Search button open the same palette, and for
   * the height of the masthead both were on screen at once, 700px apart, both
   * captioned ⌘K. This claims the job while the hero's field is in view and
   * hands it back the moment it scrolls off, so there is one entry point at
   * any given scroll position rather than two.
   *
   * An observer rather than a scroll handler: the question is literally "is
   * this element visible", the browser answers it without a listener running
   * on every frame, and it stays right if the masthead's height changes.
   */
  let heroSearch: HTMLElement | undefined;
  onMount(() => {
    if (!heroSearch || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(([e]) => pageOwnsSearch.set(e.isIntersecting), {
      // The field has to be properly gone, not merely clipped at the top edge,
      // or the two swap back and forth while the reader scrolls through it.
      threshold: 0.6,
    });
    io.observe(heroSearch);
    return () => {
      io.disconnect();
      pageOwnsSearch.set(false);
    };
  });
  onMount(() => {
    if (!/mac/i.test(navigator.platform ?? '')) paletteKey = 'Ctrl K';
  });
</script>

<!-- The front page had a title and a description and nothing else, so the one
     URL people actually paste — the root — rendered as a bare link everywhere,
     while `/catalog/[id]` posted a proper card. Same tags, same shape. -->
<svelte:head>
  <title>{$t('Vietnam Map Archive — historical maps of Vietnam, open and georeferenced')}</title>
  <meta name="description" content={metaDescription} />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Vietnam Map Archive" />
  <meta property="og:url" content={canonical} />
  <meta property="og:title" content="Vietnam Map Archive" />
  <meta property="og:description" content={metaDescription} />
  <meta property="og:image" content={shareImage} />
  <meta property="og:image:width" content="1600" />
  <meta property="og:image:height" content="900" />
  <meta
    property="og:image:alt"
    content="The 1882 cadastral survey of Saigon laid over the modern city"
  />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Vietnam Map Archive" />
  <meta name="twitter:description" content={metaDescription} />
  <meta name="twitter:image" content={shareImage} />
  <!-- The only markup here is the <script> tag `jsonLd` writes; every value
       inside it goes through JSON.stringify with `<` escaped, so nothing in
       the payload can open a tag. -->
  <!-- eslint-disable-next-line svelte/no-at-html-tags -->
  {@html siteSchema}
</svelte:head>

<div class="page home-page">
  <header class="hero">
    <!-- Two stills of one frame, the slider below fading between them. The
         city sits underneath and only shows as the sheet comes off it, so it
         is `low` priority — the sheet is the LCP element and nothing else on
         this page should compete with it.

         One name for the pair, on the wrapper: it is a single picture in two
         states, and either one can be the visible one. Describing only the
         1882 layer left a reader who had dragged the slider to Today looking
         at an image with no description at all. -->
    <div
      class="hero-stills"
      role="img"
      aria-label={$t(
        'The 1882 cadastral survey of Saigon laid over the modern city, fading between the two'
      )}
    >
      <img
        class="hero-still"
        src={HERO_NOW}
        srcset={twoCuts(HERO_NOW)}
        sizes="100vw"
        alt=""
        width="1600"
        height="900"
        fetchpriority="low"
        decoding="async"
      />
      <img
        class="hero-still"
        src={HERO_1882}
        srcset={twoCuts(HERO_1882)}
        sizes="100vw"
        alt=""
        width="1600"
        height="900"
        fetchpriority="high"
        decoding="async"
        style:opacity={heroSheet}
      />
    </div>
    <div class="hero-still-scrim" aria-hidden="true"></div>
    <!-- The imagery is on screen whenever the slider is off 1882, so its
         credit has to be too. The live map below gets OL's own attribution
         control; a still image has no such thing. -->
    <p class="hero-credit">
      {$t('Imagery © Esri, Maxar, Earthstar Geographics · Sheet: Plan Cadastral de Saïgon, 1882')}
    </p>
    <div class="hero-content on-ink-plate">
      <h1 class="hero-title">
        Vietnam<br /><span class="text-highlight">Map Archive</span>
      </h1>
      <p class="hero-subtitle">
        {$t(
          '{N} sheets of Saigon, Huế and Hanoi — 1791 to 1984 — laid back over the ground they drew.',
          {
            N: mapCount,
          }
        )}
      </p>
      <!-- The field is a paper plate sitting on the masthead's dark ground, so
           `on-light-plate` inside the component keeps it off the paper ink. -->
      <div bind:this={heroSearch}>
        <PaletteSearchField kbd={paletteKey} />
      </div>

      <!-- One sentence, not three pills. Their job is to say what the field
           takes — a place, a name off a sheet, a year — and three pill-shaped
           targets said it with the weight of three more controls, next to a
           field that is already the largest thing in the column. Still three
           buttons for a screen reader and for the keyboard; they just stopped
           looking like the page's main event. -->
      <p class="hero-tries">
        Try {#each HERO_TRIES as term, i (term)}<button
            type="button"
            class="hero-try"
            on:click={() => openPaletteWith(term)}>{term}</button
          >{i < HERO_TRIES.length - 2 ? ', ' : i === HERO_TRIES.length - 2 ? ' or ' : ''}{/each}
      </p>

      <!-- The archive's whole gesture in one control: drag from today back to
           1882. It is in the column, not on a plate over the map, so it shares
           the left edge with the title and the field by layout rather than by
           a matching `clamp()`. Two images and an opacity — no map, no
           JavaScript beyond the bind. -->
      <label class="hero-fade">
        <span>{$t('Today')}</span>
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          bind:value={heroSheet}
          on:pointerdown={() => (heroTouched = true)}
          on:keydown={() => (heroTouched = true)}
          aria-label={$t('How much of the 1882 sheet to show')}
        />
        <span>1882</span>
      </label>
    </div>
  </header>

  <main class="main">
    <!-- ============ THE CATALOG ============ -->
    <section class="home-section" id="catalog">
      <div class="section-head">
        <div class="section-head-text">
          <h2 class="feature-title">{$t('The Catalog')}</h2>
          <p class="feature-description">
            {$t(
              "A featured sheet, whole. Pick another below, then open it in the viewer to lay it over today's city, or inspect the high-resolution IIIF scan up close. Each record links back to the library or collection that holds it."
            )}
          </p>
        </div>
        <!-- Only a signed-in reader has favorites, and the tab used to be there
             for everyone else too — a second tab whose whole content was a note
             saying to sign in. -->
        {#if session}
          <Tabs
            label={$t('Which sheets')}
            tabs={[
              { key: 'featured', label: 'Featured' },
              { key: 'favorites', label: 'Favorites' },
            ]}
            active={filterCollection}
            on:change={(e) => (filterCollection = e.detail.key as typeof filterCollection)}
          />
        {/if}
      </div>

      <!-- No loading state for the featured set: it is in the HTML. Favorites
           are the only thing this page still waits for. -->
      {#if filterCollection === 'favorites' && loadingFavorites}
        <p class="empty-state is-block">{$t('Opening the archive…')}</p>
      {:else if filterCollection === 'favorites' && displayedMaps.length === 0}
        <div class="empty-state is-block">
          <h3>{$t('No favorites yet.')}</h3>
          <p>{$t('Heart any map and it lands here, on every device you sign in from.')}</p>
        </div>
      {:else if displayedMaps.length > 0}
        <FeaturedSheet
          maps={displayedMaps}
          {thumbnails}
          {favoriteIds}
          showFavorite={!!session}
          on:toggleFavorite={(e) => toggleFavorite(e.detail)}
        />
      {:else}
        <div class="empty-state is-block">
          <h3>{$t('Nothing here yet.')}</h3>
          <p>{$t('No maps match this view — try another tab or the catalog.')}</p>
        </div>
      {/if}

      <div class="action-footer">
        <div class="footer-links-group">
          <a href="/catalog" class="text-link">{$t('Browse the catalog')}</a>
          <!-- "Inspect a scan" pointed at /scan, which stopped being a public
               address in Sept 2026: a sheet's own catalogue page carries the
               tiled scan now, so the catalogue link above is that door. -->
          <a href="/catalog/series" class="text-link">{$t('Map series')}</a>
        </div>
        <a href="/explore" class="btn is-lg is-primary">{$t('Open the map')}</a>
      </div>
    </section>

    <!-- ============ HOW THIS WORKS ============
         The animated hero, moved out of the header. Same map, same four beats;
         the difference is that a reader who never scrolls this far never pays
         for OpenLayers. -->
    <HeroDemo
      mapId={HERO_SHEET.id}
      slug={HERO_SHEET.slug}
      view={HERO_SHEET.view}
      video={HERO_CLIP}
      videoSmall={HERO_CLIP_SMALL}
      poster={HERO_CLIP_POSTER}
      posterSrcset={twoCuts(HERO_CLIP_POSTER, 1200)}
    />

    <!-- ============ THE BAND ============
         Tools, Contribute and the two standing notes were four bordered cards
         across two rows. They hold four short lists and two short paragraphs
         between them, which is one band's worth of content, so that is what
         they are now. -->
    <div class="home-band">
      <section class="band-col" id="tools">
        <h2 class="band-title">
          {$t('Tools')} <span class="fun-badge">Beta</span>
        </h2>
        <p class="band-desc">
          {$t(
            'Build something on top of the archive — a scrollytelling story across historical layers, or your own points, lines and shapes on a sheet.'
          )}
        </p>
        <div class="micro-links">
          <a href="/explore?mode=story" class="micro-link-card">
            <span class="mlc-body">
              <span class="mlc-title">{$t('Story Builder')}</span>
              <span class="mlc-desc">{$t('Walk readers through a place, one layer at a time')}</span
              >
            </span>
          </a>
          <a href="/explore?mode=studio" class="micro-link-card">
            <span class="mlc-body">
              <span class="mlc-title">Studio</span>
              <span class="mlc-desc">{$t('Draw on any map and save it as a set')}</span>
            </span>
          </a>
        </div>
      </section>

      <section class="band-col" id="contribute">
        <h2 class="band-title">{$t('Contribute')}</h2>
        <p class="band-desc">
          {$t(
            'The archive is built by volunteers, and there are not many of us yet. Your name stays on what you submit, and all of it is meant to be released openly.'
          )}
        </p>
        <div class="micro-links">
          <a href="/scan?mode=prepare" class="micro-link-card">
            <span class="mlc-body">
              <span class="mlc-title">{$t('Prepare a sheet')}</span>
              <span class="mlc-desc"
                >{$t('Crop a neatline, check the toponyms the pipeline pulled')}</span
              >
            </span>
          </a>
          <a href="/scan?mode=shapes" class="micro-link-card">
            <span class="mlc-body">
              <span class="mlc-title">{$t('Trace buildings')}</span>
              <span class="mlc-desc">{$t('Outline buildings, roads and waterways')}</span>
            </span>
          </a>
          <a href="/contribute/georef" class="micro-link-card">
            <span class="mlc-body">
              <span class="mlc-title">{$t('Georeference')}</span>
              <span class="mlc-desc"
                >{$t('Pin a scan to real coordinates in the Allmaps Editor')}</span
              >
            </span>
          </a>
        </div>
      </section>

      <section class="band-col">
        <h2 class="band-title">{$t('About the project')}</h2>
        <p class="band-desc">
          {$t(
            "Volunteers put those sheets on the ground they drew. Reading the names off them and tracing what they show is where the work goes next: the aim is to get the buildings and street names out of Vietnam's colonial-era maps and into open data, with a person checking the machine's work. The 1882 cadastral survey of Saigon is where it starts, and where most of the work so far sits. Everything published will be CC-BY / ODbL."
          )}
        </p>
        <a href="/about" class="info-link">{$t("What's actually done →")}</a>
      </section>

      <section class="band-col">
        <h2 class="band-title">{$t('Where things stand')}</h2>
        <p class="band-note">{STATS.snapshot}</p>
        <p class="band-desc">
          {$t(
            'Two surveys went on the map this week: the US Army 1:50,000 of Vietnam — {N} of its {T} sheets — and the Indochine 1:25,000 of Tonkin. The map draws {D} sheets now, against {B} a week ago.',
            {
              N: STATS.l7014Held,
              T: STATS.l7014Total,
              D: STATS.sheetsDrawn,
              B: STATS.sheetsDrawnBefore,
            }
          )}
        </p>
        <p class="band-desc">
          {$t(
            'The OCR pass has read {N} distinct place names off six sheets, {M} of which have been checked by a person — so that queue has barely started.',
            { N: STATS.labels, M: STATS.labelsChecked }
          )}
          {$t(
            '{N} building outlines have been traced on the 1882 cadastral survey, and none are approved yet.',
            { N: STATS.footprints }
          )}
        </p>
        <!-- Two links, so one wrapper takes the `margin-top: auto` that pins
             them to the foot of the column; on the anchors themselves it would
             push the pair apart instead. -->
        <div class="band-links">
          <a href="/blog/two-map-series-2026-09" class="info-link">{$t('Read the update →')}</a>
          <a href="/explore?series=l7014#@16.1,107.2,5.7z,0r" class="info-link"
            >{$t('Open L7014 on the map →')}</a
          >
        </div>
      </section>
    </div>

    <!-- ============ THE WAY OUT ============
         The reader who got this far is the likeliest to act, and until now the
         page handed them a footer. Same field as the hero, same one CTA. -->
    <section class="home-cta">
      <h2 class="home-cta-title">{$t('What will you find?')}</h2>
      <p class="home-cta-sub">
        {$t('Most people come for one street and stay for the city. {N} sheets, 1791 to 1984.', {
          N: mapCount,
        })}
      </p>
      <PaletteSearchField variant="home-cta-search" />
      <a href="/explore" class="btn is-lg home-cta-btn on-light-plate">{$t('Open the map')}</a>
    </section>
  </main>
</div>
