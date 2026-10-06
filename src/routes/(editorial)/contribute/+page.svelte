<script lang="ts">
  import { t, splitHighlight } from '$lib/core/i18n';
  import { onMount } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchUserRole } from '$lib/data/supabase/role';
  import PageHero from '$lib/ui/PageHero.svelte';

  $: heroTitle = splitHighlight($t('Build the archive **together.**'));

  const { session, supabase } = getSupabaseContext();

  let role = 'user';

  onMount(async () => {
    role = (await fetchUserRole(supabase, session?.user?.id)) ?? 'user';
  });
</script>

<svelte:head>
  <title>Contribute — Vietnam Map Archive</title>
  <meta
    name="description"
    content="Trace buildings, georeference maps, and check the OCR's reading. Anyone with an account can contribute to the Vietnam Map Archive — the queues are short and the work is real."
  />
</svelte:head>

<div class="page">
  <PageHero
    eyebrow="Open contribution"
    sub="Trace a building, anchor a scan, or check what the OCR read. Anyone with an account can contribute; an admin reviews before anything is published. There are only a handful of us, so a single afternoon's work is a visible share of the whole."
  >
    <svelte:fragment slot="title">
      {heroTitle[0]}{#if heroTitle[1]}<br /><span class="text-highlight">{heroTitle[1]}</span
        >{/if}{heroTitle[2]}
    </svelte:fragment>
  </PageHero>

  <main class="editorial-main">
    <section class="contribute-grid">
      <a href="/scan?mode=prepare" class="section-card card-link">
        <div class="section-card-header">
          <div>
            <h2 class="section-title-sm">{$t('Prepare a sheet')}</h2>
            <p class="section-desc">
              {$t(
                "Crop a map's neatline, set tile priorities, and check the place names the OCR pass read off the sheet. Around 950 distinct names are waiting; 43 have been checked."
              )}
            </p>
          </div>
        </div>
        <span class="card-cta">{$t('Start preparing')}</span>
      </a>

      <a href="/scan?mode=shapes" class="section-card card-link">
        <div class="section-card-header">
          <div>
            <h2 class="section-title-sm">{$t('Trace buildings')}</h2>
            <p class="section-desc">
              {$t(
                'Outline buildings, roads, and waterways on a georeferenced map. 46 shapes have been traced so far, all on the 1882 cadastral survey.'
              )}
            </p>
          </div>
        </div>
        <span class="card-cta">{$t('Open the tracer')}</span>
      </a>

      <a href="/contribute/georef" class="section-card card-link">
        <div class="section-card-header">
          <div>
            <h2 class="section-title-sm">{$t('Georeference a map')}</h2>
            <p class="section-desc">
              {$t(
                'Place ground control points in the Allmaps Editor to anchor a historical map to real-world coordinates.'
              )}
            </p>
          </div>
        </div>
        <span class="card-cta">{$t('See what needs georef')}</span>
      </a>

      {#if role === 'admin' || role === 'mod'}
        <a href="/scan?mode=legend" class="section-card card-link">
          <div class="section-card-header">
            <div>
              <h2 class="section-title-sm">{$t('Place the legend')}</h2>
              <p class="section-desc">
                {$t(
                  'Place numbered legend entries on the scan and link them to the features they name.'
                )}
              </p>
            </div>
          </div>
          <span class="card-cta">{$t('Open legend tool')}</span>
        </a>

        <a href="/scan?mode=shapes&amp;tab=validate" class="section-card card-link mod-card">
          <div class="section-card-header">
            <div>
              <h2 class="section-title-sm">{$t('Review footprints')}</h2>
              <p class="section-desc">
                {$t(
                  'Approve or reject building traces from volunteers and the SAM2 pipeline. Nothing is approved yet. Mods and admins only.'
                )}
              </p>
            </div>
          </div>
          <span class="card-cta">{$t('Open the review queue')}</span>
        </a>

        <a href="/catalog" class="section-card card-link catalog-card">
          <div class="section-card-header">
            <div>
              <h2 class="section-title-sm">{$t('Catalog metadata')}</h2>
              <p class="section-desc">
                {$t(
                  'Complete bibliographic records: titles, shelfmarks, creators, dates, rights, and physical descriptions.'
                )}
              </p>
            </div>
          </div>
          <span class="card-cta">{$t('Edit the catalog')}</span>
        </a>
      {/if}
    </section>
  </main>
</div>

<style>
  :global(body) {
    margin: 0;
    background-color: var(--color-bg);
    color: var(--color-text);
    font-family: var(--font-family-base);
  }

  .contribute-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 1.5rem;
  }

  .card-link {
    text-decoration: none;
    color: var(--color-text);
    display: flex;
    flex-direction: column;
    gap: 1rem;
    transition:
      transform 0.1s,
      box-shadow 0.1s;
  }

  .card-link:hover {
    transform: translate(-3px, -3px);
    box-shadow: var(--shadow-solid-hover);
  }

  .mod-card:hover {
    border-color: var(--color-green);
  }
  .catalog-card:hover {
    border-color: var(--color-purple);
  }

  .card-cta {
    font-size: 0.875rem;
    font-weight: 700;
    color: var(--color-primary);
    margin-top: auto;
  }
</style>
