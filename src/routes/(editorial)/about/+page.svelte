<script lang="ts">
  import { t, splitHighlight } from '$lib/core/i18n';
  import PageHero from '$lib/ui/PageHero.svelte';
  import '$styles/pages/about.css';
  import type { PageData } from './$types';

  $: heroTitle = splitHighlight($t('Old maps of Vietnam, **put back in place.**'));

  export let data: PageData;
  $: s = data.stats;
  const num = (n: number) => n.toLocaleString('en-US');

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
    content="A small volunteer project putting old maps of Vietnam back in place, reading what is printed on them and linking them to the city today. {s.published} sheets are placed so far; this page says what is done and what is not."
  />
</svelte:head>

<div class="page about-page">
  <PageHero
    eyebrow="About"
    sub="A small volunteer project. We put old maps of Vietnam back on the ground they drew, read what is printed on them, and link each one to other maps, to its sources and to the city today. A machine proposes each link and a person decides; we record who checked it and how often they were right. Saigon is where the work goes deepest: it is the city we live in and the one with the best archives."
  >
    <svelte:fragment slot="title">
      {heroTitle[0]}{#if heroTitle[1]}<br /><span class="text-highlight">{heroTitle[1]}</span
        >{/if}{heroTitle[2]}
    </svelte:fragment>
  </PageHero>

  <main class="editorial-main">
    <!-- WHY — docs/CONCEPT.md §Why -->
    <section class="section-card">
      <h2 class="section-title-sm">Why we do it</h2>
      <p class="section-desc">Three things make old Vietnamese sources hard to use.</p>
      <ul class="plain-list">
        <li>
          <strong>They are scattered.</strong> Maps sit in archives in France, the United States and Vietnam;
          the documents and photos about the same streets sit somewhere else.
        </li>
        <li>
          <strong>They never agree.</strong> Every map is a claim by someone, for a purpose. Agreement
          is also cheap now: a map redrawn from another, or a summary of a catalogue, agrees with its
          source for free.
        </li>
        <li>
          <strong>The places are going.</strong> The 2025 merge put old names on new ground, and a building
          that comes down leaves only what recorded it.
        </li>
      </ul>
      <p class="section-desc flow-lead">
        So we do not try to make the sources agree. We tie each one to a place and a time, say how
        the two relate, and keep who checked every link. A machine can propose thousands; only a
        person can decide. The aim is a record anyone can search, cite and download, and honest
        numbers on how often it is right.
      </p>
    </section>

    <!-- HOW IT WORKS, AND WHERE IT STANDS — the diagram carries the live counts; the marks and the
         "Status as of" line are true on the date written, so update them when the review page or the
         status page change. The numbers are counted on render, not typed in. -->
    <section class="section-card">
      <h2 class="section-title-sm">How it works, and where it stands</h2>
      <p class="section-desc">
        Four steps make a link: place, read, link, check. Each needs the one before. The figures are
        counted from the database when this page loaded.
      </p>

      <figure class="flow-fig">
        <ol class="flow">
          <li class="step span is-built">
            <h3>
              <span class="mark" aria-hidden="true"></span>Sources<span class="state">Built</span>
            </h3>
            <p>
              Maps from archives in France, the United States and Vietnam. Later, documents and
              photos.
            </p>
          </li>

          <li class="lane machine down">
            <h3 class="lane-title">A machine proposes</h3>
            <ol class="steps">
              <li class="step is-built">
                <h3>
                  <span class="mark" aria-hidden="true"></span>1. Place<span class="state"
                    >Built</span
                  >
                </h3>
                <p class="figure">
                  <b>{num(s.published)}</b> sheets on the map, {s.yearFrom} to {s.yearTo}
                </p>
                <p>
                  Pin a scan to real coordinates. A machine first finds the title, legend, map and
                  border.
                </p>
              </li>
              <li class="step down is-part">
                <h3>
                  <span class="mark" aria-hidden="true"></span>2. Read<span class="state"
                    >Partly</span
                  >
                </h3>
                <p class="figure">
                  <b>{num(s.labels)}</b> place names read, {num(s.labelsChecked)} checked
                </p>
                <p class="figure">
                  <b>{num(s.shapes)}</b> shapes traced by hand, {num(s.shapesApproved)} approved
                </p>
                <p>Names are read by a machine. Shapes are not yet.</p>
              </li>
              <li class="step down is-part">
                <h3>
                  <span class="mark" aria-hidden="true"></span>3. Link<span class="state"
                    >Offline only</span
                  >
                </h3>
                <p class="figure"><b>None</b> published yet</p>
                <p>
                  Which place today a name on an old sheet may mean, and how the two relate. Tested
                  on the 1882 survey of Saigon.
                </p>
              </li>
            </ol>
          </li>

          <li class="step person across is-part">
            <h3>
              <span class="mark" aria-hidden="true"></span>4. Check<span class="state"
                >Offline only</span
              >
            </h3>
            <p class="figure"><b>No</b> measured accuracy yet</p>
            <p>
              A person decides: same building, same site with a new building, moved, gone, none or
              unsure. Today every proposal goes to a person; sorting the sure from the unsure is not
              built.
            </p>
            <div class="odds-row">
              <span
                class="odds"
                role="img"
                aria-label="Five items: four show the machine’s suggestion, one hides it"
              >
                <i></i><i></i><i></i><i></i><i class="hidden"></i>
              </span>
              <span>About one item in five hides the machine’s suggestion first.</span>
            </div>
            <p>A web page for more reviewers is being built.</p>
          </li>

          <li class="step span down record is-built">
            <h3>
              <span class="mark" aria-hidden="true"></span>The record<span class="state">Built</span
              >
            </h3>
            <p>
              Who decided, when, what the machine had suggested, and whether they saw it. Added to,
              never edited.
            </p>
          </li>

          <li class="step down is-part measure">
            <h3>
              <span class="mark" aria-hidden="true"></span>Measure<span class="state"
                >Offline only</span
              >
            </h3>
            <p>
              How often a link is right, seconds per check, and which checks were independent of
              what they checked.
            </p>
          </li>

          <li class="step across is-planned back">
            <h3>
              <span class="mark" aria-hidden="true"></span>Back to the machines<span class="state"
                >Not yet</span
              >
            </h3>
            <p>
              Decisions train the proposals, with whole sheets held out so the test stays honest.
            </p>
          </li>
        </ol>
        <figcaption class="flow-key">
          <span><span class="mark is-built" aria-hidden="true"></span>Built: works now</span>
          <span
            ><span class="mark is-part" aria-hidden="true"></span>Partly or offline only: on one
            person’s machine, or for some maps</span
          >
          <span><span class="mark is-planned" aria-hidden="true"></span>Not yet: a design</span>
          <span>Status as of October 2026.</span>
        </figcaption>
      </figure>

      <h3 class="subhead">About the numbers</h3>
      <ul class="plain-list">
        <li>
          The sheets on the map are {cityLine}. A further {num(s.drafts)} are placed but not published,
          so nobody outside the project sees them yet.
        </li>
        <li>
          {num(s.surveySheetsHeld)} of {num(s.surveySheets)} sheets in {s.surveys} complete surveys are
          each on the map as a single layer. Most are cells of a pre-tiled mosaic with no catalogue record
          of their own, which is why the first figure is smaller.
        </li>
        <li>
          {num(s.shapesApproved)} approved shapes is too few to release, so there is no dataset to download
          yet.
        </li>
      </ul>
    </section>

    <!-- THE RULE -->
    <section class="section-card">
      <h2 class="section-title-sm">A check counts only if it could have failed</h2>
      <p class="section-desc">
        Three things look like a check and are not. We try not to count them, and we say so when we
        cannot tell.
      </p>
      <ul class="plain-list">
        <li>
          <strong>A test that shares the error it tests for.</strong> If the same mistake is in both,
          the test cannot find it.
        </li>
        <li>
          <strong>A person who only agrees with the machine.</strong> People tend to accept what a machine
          suggests, which is why some suggestions are hidden.
        </li>
        <li>
          <strong>A second source copied from the first.</strong> Two maps redrawn from one survey agree
          for free, and so does a summary of the catalogue it was written from.
        </li>
      </ul>
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
          <strong>{$t('No published dataset.')}</strong>
          {$t(
            'Nothing traced has been reviewed and released. That is the next thing, and it needs people rather than code.'
          )}
        </li>

        <li>
          <strong>{$t('No building histories.')}</strong>
          {$t(
            'Who built a place, who owned it, what replaced it — there is no database for any of that, only a design.'
          )}
        </li>
        <li>
          <strong>{$t('No 3D.')}</strong>
          {$t(
            'Heights and roof shapes would come from two rare painted views of the city and a published reconstruction method. Nothing has been run.'
          )}
        </li>
        <li>
          <strong>{$t('Barely any contributors.')}</strong>
          {$t(
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
