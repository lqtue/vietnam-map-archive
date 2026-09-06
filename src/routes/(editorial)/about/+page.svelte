<script lang="ts">
  import { onMount } from 'svelte';
  import PageHero from '$lib/ui/PageHero.svelte';
  import '$styles/pages/about.css';
  import { layers, phases, users } from './content';
  let mounted = false;

  onMount(() => {
    mounted = true;
  });

  let expanded: Record<string, boolean> = {};
  function toggleLayer(id: string) {
    expanded[id] = !expanded[id];
    expanded = expanded;
  }
</script>

<svelte:head>
  <title>About — Vietnam Map Archive</title>
  <meta
    name="description"
    content="Vietnam Map Archive is rebuilding Saigon's urban history as a time-layered, georeferenced digital city — starting with 1880–1930 French colonial Saigon."
  />
</svelte:head>

<div class="page about-page" class:mounted>
  <PageHero
    eyebrow="About the project"
    sub="We started in Saigon — the city we know, live in, and have the best archives for. The 1880–1930 French colonial period is the testbed: the most documented, most transformative, most underserved window in the city's history. Once the method works here, it travels. Vietnam next. Then any city with a map archive and a community that cares."
  >
    <svelte:fragment slot="title">
      The city disappears<br />into the past.<br />
      <span class="text-highlight">We bring it back.</span>
    </svelte:fragment>
    <div class="hero-badges">
      <span class="badge-chip chip-green">Featured in Saigoneer Jan 2026</span>
      <span class="badge-chip chip-blue">Open Source · CC-BY · ODbL</span>
      <span class="badge-chip chip-yellow">Forkable · Community-driven</span>
    </div>
  </PageHero>

  <main class="main">
    <!-- WHO IS THIS FOR -->
    <section class="users-section">
      <div class="section-card">
        <div class="section-card-header">
          <div class="icon-blob color-yellow">👥</div>
          <div>
            <h2 class="section-title-sm">Who is this for?</h2>
            <p class="section-desc">
              Anyone who cares about Saigon — as a place they live, a city they left, a history they
              study, or a dataset they need.
            </p>
          </div>
        </div>
        <div class="users-grid">
          {#each users as user}
            <div class="user-card">
              <div class="user-icon">{user.icon}</div>
              <h4 class="user-title">{user.title}</h4>
              <p class="user-desc">{user.desc}</p>
              <span class="user-uses">{user.uses}</span>
            </div>
          {/each}
        </div>
      </div>
    </section>

    <!-- 6-LAYER STACK PROGRESS -->
    <section class="stack-section">
      <div class="section-card">
        <div class="section-card-header">
          <div class="icon-blob color-blue">📊</div>
          <div>
            <h2 class="section-title-sm">What we're building</h2>
            <p class="section-desc">
              Six layers, each one resting on the one below — from maps pinned to real coordinates
              up to a walkable 3D city with family memories attached. Click any layer to see what's
              done and what's next.
            </p>
          </div>
        </div>
        <div class="stack-list">
          {#each [...layers].reverse() as layer}
            <div class="layer-card" class:open={expanded[layer.id]}>
              <!-- Header row — click to expand -->
              <button
                class="layer-header"
                on:click={() => toggleLayer(layer.id)}
                aria-expanded={!!expanded[layer.id]}
              >
                <span class="layer-id" style="background:{layer.color}">{layer.id}</span>
                <div class="layer-title-group">
                  <span class="layer-name">{layer.name}</span>
                  <span class="layer-desc">{layer.desc}</span>
                </div>
                <span
                  class="phase-tag"
                  style="border-color:{layer.phaseColor};color:{layer.phaseColor}"
                  >{layer.phase}</span
                >
                <span class="layer-pct">{layer.pct}%</span>
                <svg
                  class="chevron"
                  viewBox="0 0 20 20"
                  fill="none"
                  width="16"
                  height="16"
                  aria-hidden="true"
                >
                  <path
                    d="M5 7.5l5 5 5-5"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </button>
              <!-- Progress bar always visible -->
              <div class="progress-track">
                <div
                  class="progress-fill"
                  style="width:{layer.pct}%;background:{layer.color}"
                ></div>
              </div>
              <!-- Detail grid — collapsible -->
              {#if expanded[layer.id]}
                <div class="layer-detail">
                  <div class="detail-col">
                    <span class="detail-label built-label">Done</span>
                    <ul class="detail-list">
                      {#each layer.built as item}
                        <li class="detail-item built-item">{item}</li>
                      {/each}
                    </ul>
                  </div>
                  <div class="detail-col">
                    <span class="detail-label building-label">Building now</span>
                    <ul class="detail-list">
                      {#each layer.building as item}
                        <li class="detail-item building-item">{item}</li>
                      {/each}
                    </ul>
                    <div class="next-row">
                      <span class="detail-label next-label">What's next</span>
                      <span class="next-text">{layer.next}</span>
                    </div>
                  </div>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    </section>

    <!-- 3-PHASE ROADMAP -->
    <section class="roadmap-section">
      <h2 class="section-title">The roadmap, in three phases</h2>
      <div class="phases-grid">
        {#each phases as phase}
          <div class="phase-card" style="--phase-color: {phase.color}">
            <div class="phase-header">
              <span class="phase-num">Phase {phase.num}</span>
              <h3 class="phase-title">{phase.title}</h3>
              <p class="phase-subtitle">{phase.subtitle}</p>
              <div class="phase-timeline">{phase.timeline}</div>
            </div>
            <ul class="milestone-list">
              {#each phase.milestones as m}
                <li class="milestone" class:done={m.done}>
                  <span class="milestone-check">{m.done ? '✅' : '○'}</span>
                  <span class="milestone-id">{m.id}</span>
                  <span>{m.text}</span>
                </li>
              {/each}
            </ul>
          </div>
        {/each}
      </div>
    </section>

    <!-- HOW THIS IS FUNDABLE / SUPPORTED -->
    <section class="funding-section">
      <div class="section-card">
        <div class="section-card-header">
          <div class="icon-blob color-yellow">💡</div>
          <div>
            <h2 class="section-title-sm">How this stays alive</h2>
            <p class="section-desc">
              Not a startup. Not a closed archive. Public infrastructure for historical memory —
              open, honest, designed to still be useful in 50 years.
            </p>
          </div>
        </div>
        <div class="model-grid">
          <div class="model-item">
            <h4>Community-built, like OSM and Wikipedia</h4>
            <p>
              No central authority decides what's true. Anyone can add a fact, trace a building, or
              correct a mistake — with a citation. Disputes are resolved by evidence. The archive
              belongs to whoever uses it. This is the model that produced OpenStreetMap and
              Wikipedia; VMA applies it to historical city data.
            </p>
          </div>
          <div class="model-item">
            <h4>Decentralized, open, forkable</h4>
            <p>
              All data is openly licensed (CC-BY / ODbL). All code and methodology published. Any
              city with a map archive and a community can fork VMA and run the same pipeline locally
              — no permission required. Saigon is the testbed; the model is designed to replicate.
            </p>
          </div>
          <div class="model-item">
            <h4>Community trains the AI, AI helps the community</h4>
            <p>
              Contributors trace buildings; those traces train better AI detectors; better detectors
              reduce the work for the next contributor. The community and the AI improve each other
              in a loop — the same principle behind OSM's machine-assisted mapping tools.
            </p>
          </div>
          <div class="model-item">
            <h4>Grant-funded (Phase 1–2)</h4>
            <p>
              Confirmed fit targets: French Institute, EFEO partnership, Wikimedia Foundation, Asia
              Foundation, NEH (with US university partner). Not chasing every grant — building one
              strong application at a time.
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- GET INVOLVED -->
    <section class="cta-section">
      <div class="cta-card">
        <h2 class="cta-title">Get involved</h2>
        <p class="cta-desc">
          VMA runs on the OpenStreetMap and Wikipedia model — open data, community-verified,
          permanently attributed. No single organisation controls it. Every traced building, cited
          source, and added fact lands in a shared public record anyone can use, correct, or build
          on.
        </p>
        <div class="cta-grid">
          <div class="cta-role">
            <div class="role-icon">🗺️</div>
            <h4>Trace the city</h4>
            <p>
              Draw building outlines on historical maps — same skills as OSM tracing. Every shape
              goes into the open dataset.
            </p>
            <a href="/scan?mode=trace" class="role-btn">Start tracing →</a>
          </div>
          <div class="cta-role">
            <div class="role-icon">📖</div>
            <h4>Write the history</h4>
            <p>
              Once buildings are in the archive, each one gets a page — add what you know, cite a
              source, the same way you'd edit Wikipedia.
            </p>
            <a href="mailto:vietnamma.project@gmail.com" class="role-btn"
              >Join the historian group →</a
            >
          </div>
          <div class="cta-role">
            <div class="role-icon">🏛️</div>
            <h4>Adopt a building</h4>
            <p>
              Take a landmark building from flat footprint to detailed 3D model — collect archival
              photos, submit a mesh, get permanent credit.
            </p>
            <a href="mailto:vietnamma.project@gmail.com" class="role-btn">Get in touch →</a>
          </div>
          <div class="cta-role">
            <div class="role-icon">💼</div>
            <h4>Fund the work</h4>
            <p>
              No pitch deck needed. Read the roadmap. If you see a fit — university partnership,
              heritage grant, institutional collaboration — write us.
            </p>
            <a href="mailto:vietnamma.project@gmail.com" class="role-btn">Contact us →</a>
          </div>
        </div>
      </div>
    </section>

    <!-- LATEST UPDATE -->
    <section class="latest-section">
      <div class="latest-card">
        <div class="latest-header">
          <span class="latest-chip">Latest update</span>
          <a href="/blog" class="all-updates-link">All updates →</a>
        </div>
        <h3 class="latest-title">March 2026 — first buildings out of the 1882 map</h3>
        <p class="latest-excerpt">
          A zero-shot SAM pipeline on IIIF tiles pulled 91 city blocks out of the 1882 Saigon
          cadastral survey — no training data required. The 1881 and 1901 painting–map pairs are now
          confirmed as the height-calibration source for the 3D pipeline.
        </p>
        <a href="/blog/buildings-as-ground-control" class="action-btn primary-btn"
          >Read the update</a
        >
      </div>
    </section>
  </main>
</div>
