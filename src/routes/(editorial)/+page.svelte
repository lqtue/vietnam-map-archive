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
  import HowItWorks from '$lib/features/explore/HowItWorks.svelte';
  import Tabs from '$lib/ui/Tabs.svelte';
  import PaletteSearchField from '$lib/ui/PaletteSearchField.svelte';
  import { openPaletteWith, pageOwnsSearch } from '$lib/core/utils/commandPalette';
  import { tweenValue } from '$lib/core/utils/tween';
  import '$styles/layouts/home.css';

  const { supabase, session } = getSupabaseContext();

  /** The surveys and the sheet count, server-rendered — see `+page.server.ts`. */
  export let data: PageData;

  let favoriteMaps: MapListItem[] = [];
  let favoriteIds: string[] = [];
  let thumbnails: Map<string, string> = new Map();
  /** Only the Favorites tab ever waits: the surveys are already in the HTML. */
  let loadingFavorites = false;
  let filterCollection: 'maps' | 'featured' | 'favorites' = 'maps';
  /** Which place the Maps tab shows. All four sets are in the HTML already. */
  let placeKey = 'saigon';
  $: place = data.places.find((p) => p.key === placeKey) ?? data.places[0];
  /** Display names; the keys come from `+page.server.ts`. */
  const placeLabel = (key: string) =>
    key === 'saigon'
      ? $t('Saigon')
      : key === 'hanoi'
        ? 'Hà Nội'
        : key === 'hue'
          ? 'Huế'
          : $t('Across Vietnam');
  /** /catalog filters on `?area=<province>`; the survey set has no URL filter, so it opens the catalog. */
  $: seeAllHref = place?.area ? `/catalog?area=${encodeURIComponent(place.area)}` : '/catalog';

  /**
   * The sheet the "how this works" section opens, and the header stills show.
   * Pinned alongside nothing else: the section is four screenshots now, so the
   * only thing the page needs from the sheet is where the outbound link goes.
   * `maps.slug` can be re-minted and `maps.id` cannot, but a stale slug 301s.
   */
  const HERO_SLUG = 'plan-cadastral-de-la-ville-de-saigon-cochinchine-francaise';

  /**
   * The header used to be the live map itself, which put OpenLayers,
   * ol-pmtiles and Allmaps in the front page's first chunk — 179 kB of
   * JavaScript with ~390 kB of basemap behind it — before the masthead had
   * painted. It is two stills now, cross-faded by the slider in the column,
   * The two come out of one shoot, which is why the ends of the slider line up
   * to the pixel.
   *
   * They are a **pinned close-up, kept on purpose**. `scripts/gen-hero-still.mjs`
   * shoots `HeroDemo`'s stage, which the front page no longer renders, so it
   * cannot be re-run as it stands; the committed pair is the header's only copy.
   */
  const HERO_NOW = '/images/hero-now.webp';
  const HERO_1882 = '/images/hero-1882.webp';

  /**
   * The header image is full-bleed, so a 390px phone was being handed the whole
   * 1600px frame — 331 kB for the pair, a third of the front page at rest, most
   * of it pixels the screen cannot draw. `gen-hero-still.mjs` writes an 800px
   * cut beside each one; this is the naming convention, in the one place that
   * needs to know it.
   */
  const twoCuts = (src: string) => `${src.replace('.webp', '-800.webp')} 800w, ${src} 1600w`;

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
   * The front page's hand-kept numbers, a dated snapshot on purpose — refresh
   * them when they embarrass us, which is the point of putting them on the
   * front page. `mapCount` beside them is a real query over `maps`.
   *
   * `names` is distinct validated names, not rows: the OCR pass has been
   * re-run on some sheets, so 1,228 validated rows are 1,178 actual names.
   * `footprints` is the approved ones (all on the 1882 sheet); the rest of the
   * traced outlines wait for review. `legendEntries` is what
   * `/api/maps/[id]/legend-points` returns, summed over the sheets that have a
   * placed legend (1878, 1923, both 1942 halves, 1959, 1968).
   */
  const STATS = {
    snapshot: 'October 2026',
    names: 1178,
    nameSheets: 12,
    footprints: 46,
    legendEntries: 846,
    legendSheets: 6,
    l7014Held: 512,
    l7014Total: 627,
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
    `A small volunteer archive of historical maps of Vietnam. ` +
    `${mapCount} sheets are georeferenced and readable in a browser; the names on them are searchable, ` +
    `and numbered legends are being placed on the ground, a sheet at a time.`;

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

  $: displayedMaps = favoriteMaps;

  /**
   * Two client-side jobs, and neither blocks the page: the reader's favorites,
   * and the thumbnails for maps whose `thumbnail` column is empty — those have
   * to be read out of an annotation one at a time.
   */
  async function loadReaderData() {
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

    // Keep the Favorites tab in step without a round trip. The record is on
    // the page already: from the Favorites tab itself or the Maps tab.
    if (wasFavorited) {
      favoriteMaps = favoriteMaps.filter((m) => m.id !== mapId);
      return;
    }
    const added = data.places.flatMap((p) => p.maps).find((m) => m.id === mapId);
    if (added) favoriteMaps = [...favoriteMaps, added];
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
        {$t('{N} sheets of Vietnam — 1791 to 2006 — laid back over the ground they drew.', {
          N: mapCount,
        })}
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
              'The surveys the archive holds part of, and where. Pick one to see which of its sheets are here, then open it on the map or read its sheet list.'
            )}
          </p>
        </div>
        <!-- Only a signed-in reader has favorites, and the tab used to be there
             for everyone else too — a second tab whose whole content was a note
             saying to sign in. -->
        <Tabs
          label={$t('Which sheets')}
          tabs={[
            { key: 'maps', label: 'Maps' },
            { key: 'featured', label: 'Surveys' },
            ...(session ? [{ key: 'favorites', label: 'Favorites' }] : []),
          ]}
          active={filterCollection}
          on:change={(e) => (filterCollection = e.detail.key as typeof filterCollection)}
        />
      </div>

      <!-- No loading state for the surveys: they are in the HTML. Favorites
           are the only thing this page still waits for. -->
      {#if filterCollection === 'favorites' && loadingFavorites}
        <p class="empty-state is-block">{$t('Opening the archive…')}</p>
      {:else if filterCollection === 'favorites' && displayedMaps.length === 0}
        <div class="empty-state is-block">
          <h3>{$t('No favorites yet.')}</h3>
          <p>{$t('Heart any map and it lands here, on every device you sign in from.')}</p>
        </div>
      {:else if filterCollection === 'featured' ? data.series.length > 0 : filterCollection === 'maps' ? place.maps.length > 0 || data.places.some((p) => p.maps.length) : displayedMaps.length > 0}
        {#if filterCollection === 'maps'}
          <div class="place-chips" role="group" aria-label={$t('Place')}>
            {#each data.places as p (p.key)}
              <button
                type="button"
                class="chip"
                class:is-on={p.key === placeKey}
                aria-pressed={p.key === placeKey}
                on:click={() => (placeKey = p.key)}
              >
                {placeLabel(p.key)}{p.total ? ` (${p.total})` : ''}
              </button>
            {/each}
          </div>
        {/if}
        <FeaturedSheet
          maps={filterCollection === 'featured'
            ? []
            : filterCollection === 'maps'
              ? place.maps
              : displayedMaps}
          axis={filterCollection === 'maps'}
          series={filterCollection === 'featured' ? data.series : []}
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

      {#if filterCollection === 'maps' && place?.total}
        <p class="see-all">
          <a href={seeAllHref} class="text-link"
            >{$t('See all {N} in the catalog', { N: place.total })}</a
          >
        </p>
      {/if}

      <div class="action-footer">
        <div class="footer-links-group">
          <a href="/catalog" class="text-link">{$t('Browse the catalog')}</a>
        </div>
        <a href="/explore" class="btn is-lg is-primary">{$t('Open the map')}</a>
      </div>
    </section>

    <!-- ============ HOW THIS WORKS ============
         Four screenshots with a paragraph each. It used to be a clip of the
         map, which was one composition for every screen. -->
    <HowItWorks
      slug={HERO_SLUG}
      footprints={STATS.footprints}
      names={STATS.names}
      nameSheets={STATS.nameSheets}
      legendEntries={STATS.legendEntries}
      legendSheets={STATS.legendSheets}
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
            "Volunteers put those sheets on the ground they drew. Now the work is reading what is printed on them: a model reads the names and a person checks them, numbered legends are placed on the map, and buildings are traced. The aim is to get the buildings and street names out of Vietnam's colonial-era maps and into open data. The 1882 cadastral survey of Saigon is where it started; the city plans of 1923, 1942, 1959 and 1968 are where the legends are. Everything published will be CC-BY / ODbL."
          )}
        </p>
        <a href="/about" class="info-link">{$t("What's actually done →")}</a>
      </section>

      <section class="band-col">
        <h2 class="band-title">{$t('Where things stand')}</h2>
        <p class="band-note">{STATS.snapshot}</p>
        <p class="band-desc">
          {$t(
            'Most of the {N} sheets come from a few surveys: the US Army 1:50,000 of Vietnam — {M} of its {T} sheets — two editions of the Indochine 1:100,000, and the Indochine 1:25,000 of Tonkin.',
            { N: mapCount, M: STATS.l7014Held, T: STATS.l7014Total }
          )}
        </p>
        <p class="band-desc">
          {$t(
            'A person has checked {N} names the OCR pass read off {M} sheets, and the numbered legends of {L} sheets are placed on the ground: {P} entries you can click.',
            {
              N: STATS.names,
              M: STATS.nameSheets,
              L: STATS.legendSheets,
              P: STATS.legendEntries,
            }
          )}
          {$t(
            '{N} building outlines on the 1882 cadastral survey are approved, and more are waiting for review.',
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
        {$t('Most people come for one street and stay for the city. {N} sheets, 1791 to 2006.', {
          N: mapCount,
        })}
      </p>
      <PaletteSearchField variant="home-cta-search" />
      <a href="/explore" class="btn is-lg home-cta-btn on-light-plate">{$t('Open the map')}</a>
    </section>
  </main>
</div>
