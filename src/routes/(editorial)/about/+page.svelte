<script lang="ts">
  import { t, splitHighlight } from '$lib/core/i18n';
  import PageHero from '$lib/ui/PageHero.svelte';
  import '$styles/pages/about.css';
  import type { PageData } from './$types';

  $: heroTitle = splitHighlight($t('Old maps of Vietnam, **put back in place.**'));

  export let data: PageData;
  $: s = data.stats;

  /** `maps.location` holds the catalog key; the page says the short name. */
  const CITY_NAMES: Record<string, string> = { 'Saigon-HCMC': 'Saigon' };
  /**
   * The four biggest places, then a count. It printed every place, which was
   * fine at three and became a thirteen-item line the moment the L7014 city
   * sheets landed — a long tail of ones, in which the reader has to notice
   * that "Saigon 22" and "Saigon 1" are the same city under two `location`
   * spellings. Capping does not fix the spellings; it stops the page leading
   * with them.
   */
  const CITIES_SHOWN = 4;
  $: cityLine = [
    ...s.cities.slice(0, CITIES_SHOWN).map(([key, n]) => `${CITY_NAMES[key] ?? key} ${n}`),
    ...(s.cities.length > CITIES_SHOWN
      ? [$t('and {N} other places', { N: s.cities.length - CITIES_SHOWN })]
      : []),
  ].join(', ');
</script>

<svelte:head>
  <title>About — Vietnam Map Archive</title>
  <meta
    name="description"
    content="A small volunteer project putting historical maps of Vietnam on real coordinates and reading the names printed on them. {s.published} sheets are placed so far; this page says what is done and what is not."
  />
</svelte:head>

<div class="page about-page">
  <PageHero
    eyebrow="About"
    sub="A small volunteer project. We take scans of historical maps, pin them to real coordinates so they line up with the city as it is now, and read the names and shapes printed on them. Saigon in the French colonial period is where the work goes deepest — it is the city we live in and the one with the best archives."
  >
    <svelte:fragment slot="title">
      {heroTitle[0]}{#if heroTitle[1]}<br /><span class="text-highlight">{heroTitle[1]}</span
        >{/if}{heroTitle[2]}
    </svelte:fragment>
  </PageHero>

  <main class="editorial-main">
    <!-- WHERE THIS STANDS — counted on render, not typed in -->
    <section class="section-card">
      <h2 class="section-title-sm">{$t('Where this stands')}</h2>
      <p class="section-desc">{$t('Counted from the database when this page loaded.')}</p>
      <dl class="stats">
        <div class="stat">
          <dt>{s.published}</dt>
          <dd>
            {$t('sheets placed on the map — {city}, {from} to {to}', {
              city: cityLine,
              from: s.yearFrom,
              to: s.yearTo,
            })}
          </dd>
        </div>
        <div class="stat">
          <dt>{s.drafts}</dt>
          <dd>
            {$t(
              'more georeferenced but not published, so nobody outside the project sees them yet'
            )}
          </dd>
        </div>
        <!-- Not addable to the number above, and the copy has to say so: a
             sheet with a catalogue record is counted in both, and 452 mosaic
             cells are counted only here. -->
        {#if s.surveys > 0}
          <div class="stat">
            <dt>{s.surveySheetsHeld}</dt>
            <dd>
              {$t(
                'of {T} sheets in {N} complete surveys, each on the map as a single layer — most are cells of a pre-tiled mosaic and have no catalogue record of their own, which is why the count above is smaller',
                { T: s.surveySheets, N: s.surveys }
              )}
            </dd>
          </div>
        {/if}
        <div class="stat">
          <dt>{s.labels}</dt>
          <dd>
            {$t('place names read off the sheets by the OCR pass — {M} checked by a person', {
              M: s.labelsChecked,
            })}
          </dd>
        </div>
        <div class="stat">
          <dt>{s.shapes}</dt>
          <dd>
            {$t(
              'building and street shapes traced by hand — {M} approved, so there is no dataset to download yet',
              { M: s.shapesApproved }
            )}
          </dd>
        </div>
      </dl>
    </section>

    <!-- WHAT WORKS -->
    <section class="section-card">
      <h2 class="section-title-sm">{$t('What you can do today')}</h2>
      <p class="section-desc">
        {$t(
          'Five things work, and they work in an ordinary browser. No account is needed for the first two.'
        )}
      </p>
      <ul class="plain-list">
        <li>
          <a href="/catalog">Browse the sheets</a> and lay any of them over the modern city in
          <a href="/explore">the viewer</a>.
        </li>
        <li>
          Put a whole survey on the map in one tap — the
          <a href="/explore?series=l7014#@16.1,107.2,5.7z,0r">US Army 1:50,000 of Vietnam</a>
          or the
          <a href="/explore?series=indochine-1-25-000-tonkin-thanh-hoa#@20.65,106.10,8.2z,0r"
            >Indochine 1:25,000 of Tonkin</a
          >, and see
          <a href="/catalog/series/series-l7014-vietnam-1-50-000">which sheets are missing</a>.
        </li>
        <li>
          <a href="/scan?mode=shapes">Trace a building</a> — the same skill as tracing on OpenStreetMap.
        </li>
        <li><a href="/scan?mode=text">Check what the OCR read</a>, one label at a time.</li>
        <li>
          <a href="/contribute/georef">Place a sheet</a> that has no coordinates yet, in Allmaps Editor.
        </li>
      </ul>
    </section>

    <!-- WHAT IS NOT BUILT -->
    <section class="section-card">
      <h2 class="section-title-sm">{$t('What is not built')}</h2>
      <p class="section-desc">
        {$t(
          'The plan is larger than the archive. Written out so nobody has to guess which parts exist.'
        )}
      </p>
      <ul class="plain-list">
        <li>
          <strong>{$t('No published dataset.')}</strong>{$t(
            'Nothing traced has been reviewed and released. That is the next thing, and it needs people rather than code.'
          )}
        </li>
        <li>
          <strong>{$t('No building histories.')}</strong>{$t(
            'Who built a place, who owned it, what replaced it — there is no database for any of that, only a design.'
          )}
        </li>
        <li>
          <strong>{$t('No 3D.')}</strong>{$t(
            'Heights and roof shapes would come from two rare painted views of the city and a published reconstruction method. Nothing has been run.'
          )}
        </li>
        <li>
          <strong>{$t('Barely any contributors.')}</strong>{$t(
            'Single figures, and the review queues are nearly empty because almost nobody has filled them.'
          )}
        </li>
        <li>
          <strong>{$t('No funding.')}</strong>
          {$t('No institution behind it, no grant won. The work is unpaid.')}
        </li>
      </ul>
    </section>

    <!-- HOW IT IS KEPT -->
    <section class="section-card">
      <h2 class="section-title-sm">{$t('How it is kept')}</h2>
      <p class="section-desc">
        {$t(
          "Data is openly licensed (CC-BY / ODbL) and the code is public. Every sheet credits the institution holding the scan — the Bibliothèque nationale de France, Université Côte d'Azur, UT Austin, the Library of Congress and others — and links back to their record. None of that is a formal partnership. Any city with a map archive can fork the whole thing and run it locally; that is the point of building it this way."
        )}
      </p>
    </section>

    <!-- CONTACT -->
    <section class="section-card">
      <h2 class="section-title-sm">{$t('Get in touch')}</h2>
      <p class="section-desc">
        Tracing, checking labels, reading French or older Vietnamese romanization, or a grant that
        might fit — all welcome, and a slow reply is likelier than a fast one. Saigoneer wrote about
        the project in January 2026. The <a href="/blog">blog</a> has the working notes, including the
        posts that turned out to be wrong.
      </p>
      <a href="mailto:vietnamma.project@gmail.com" class="btn is-lg">vietnamma.project@gmail.com</a>
    </section>
  </main>
</div>
