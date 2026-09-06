<script lang="ts">
  import { onMount } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchUserRole } from '$lib/data/supabase/role';
  import PageHero from '$lib/ui/PageHero.svelte';
  import GeorefQueue from '$lib/features/contribute/georef/GeorefQueue.svelte';

  const { session, supabase } = getSupabaseContext();

  let mounted = false;
  let role = 'user';

  onMount(async () => {
    mounted = true;
    role = (await fetchUserRole(supabase, session?.user?.id)) ?? 'user';
  });
</script>

<svelte:head>
  <title>Contribute — Vietnam Map Archive</title>
  <meta
    name="description"
    content="Trace buildings, georeference maps, and review AI output. Anyone with an account can contribute to the Vietnam Map Archive."
  />
</svelte:head>

<div class="page" class:mounted>
  <PageHero
    eyebrow="Open contribution"
    sub="Trace a building, anchor a scan, or check the AI's work. Anyone with an account can contribute — an admin reviews and publishes what's ready."
  >
    <svelte:fragment slot="title">
      Build the archive<br />
      <span class="text-highlight">together.</span>
    </svelte:fragment>
  </PageHero>

  <main class="editorial-main">
    <section class="contribute-grid">
      <a href="/scan?mode=triage" class="section-card card-link">
        <div class="section-card-header">
          <div class="icon-blob color-orange">✏️</div>
          <div>
            <h2 class="section-title-sm">OCR &amp; Triage</h2>
            <p class="section-desc">
              Crop a map's neatline, set tile priorities, and validate the toponyms our pipeline
              extracts. Feeds the SAM2 segmentation step.
            </p>
          </div>
        </div>
        <span class="card-cta">Start triaging →</span>
      </a>

      <a href="/scan?mode=trace" class="section-card card-link">
        <div class="section-card-header">
          <div class="icon-blob color-yellow">🖋️</div>
          <div>
            <h2 class="section-title-sm">Trace buildings</h2>
            <p class="section-desc">
              Outline buildings, roads, and waterways on a georeferenced map. Every shape goes into
              the open dataset.
            </p>
          </div>
        </div>
        <span class="card-cta">Open the tracer →</span>
      </a>

      <a href="/contribute#georef" class="section-card card-link">
        <div class="section-card-header">
          <div class="icon-blob color-blue">📍</div>
          <div>
            <h2 class="section-title-sm">Georeference a map</h2>
            <p class="section-desc">
              Place ground control points in the Allmaps Editor to anchor a historical map to
              real-world coordinates.
            </p>
          </div>
        </div>
        <span class="card-cta">Jump to the queue →</span>
      </a>

      {#if role === 'admin' || role === 'mod'}
        <a href="/scan?mode=review" class="section-card card-link mod-card">
          <div class="section-card-header">
            <div class="icon-blob color-green">✅</div>
            <div>
              <h2 class="section-title-sm">Review footprints</h2>
              <p class="section-desc">
                Approve or reject building traces from volunteers and the SAM2 pipeline. Mods and
                admins only.
              </p>
            </div>
          </div>
          <span class="card-cta">Open the review queue →</span>
        </a>

        <a href="/archive" class="section-card card-link catalog-card">
          <div class="section-card-header">
            <div class="icon-blob color-purple">📚</div>
            <div>
              <h2 class="section-title-sm">Catalog metadata</h2>
              <p class="section-desc">
                Complete bibliographic records: titles, shelfmarks, creators, dates, rights, and
                physical descriptions.
              </p>
            </div>
          </div>
          <span class="card-cta">Edit the catalog →</span>
        </a>
      {/if}
    </section>

    <section id="georef" class="georef-section">
      <GeorefQueue />
    </section>
  </main>
</div>

<style>
  :global(body) {
    margin: 0;
    background-color: var(--ground);
    color: var(--ink);
    font-family: var(--font-body);
  }

  .page {
    min-height: 100vh;
    opacity: 0;
    transition: opacity 0.4s ease;
  }
  .page.mounted {
    opacity: 1;
  }

  .contribute-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 1.5rem;
  }

  .card-link {
    text-decoration: none;
    color: var(--ink);
    display: flex;
    flex-direction: column;
    gap: 1rem;
    transition:
      transform 0.1s,
      box-shadow 0.1s;
  }

  .card-link:hover {
    transform: translate(-3px, -3px);
    box-shadow: var(--shadow-overlay);
  }

  .mod-card:hover {
    border-color: var(--status-ok);
  }
  .catalog-card:hover {
    border-color: color-mix(in srgb, var(--accent) 55%, var(--status-bad));
  }

  .georef-section {
    margin-top: var(--s-6);
    padding-top: var(--s-4);
    border-top: var(--rule-hair) solid var(--rule);
    scroll-margin-top: var(--s-5);
  }

  .card-cta {
    font-size: 0.875rem;
    font-weight: 700;
    color: var(--accent);
    margin-top: auto;
  }
</style>
