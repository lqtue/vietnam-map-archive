<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
  import ChunkyTabs from '$lib/ui/ChunkyTabs.svelte';
  import CatalogCard from '$lib/ui/CatalogCard.svelte';
  import MapCard from '$lib/ui/MapCard.svelte';
  import LibraryGrid from '$lib/ui/LibraryGrid.svelte';
  import FacetRail from '$lib/ui/FacetRail.svelte';
  import InlineRename from '$lib/ui/InlineRename.svelte';
  import NameDialog from '$lib/ui/NameDialog.svelte';
  import NavDropdown from '$lib/ui/NavDropdown.svelte';
  import LocationSearch from '$lib/ui/LocationSearch.svelte';
  import type { MapListItem } from '$lib/data/maps/types';
  import '$styles/pages/screens.css';
  // the Status tones section renders real .status-row markup
  import '$styles/pages/admin-status.css';

  /*
    /screens — every piece of the design system on one page.

    The point is to make reuse cheaper than reinvention: if you can see that a
    thing exists, you stop building a second one. Nothing here touches the
    database. Every component is rendered from a fixture below, so this page
    cannot break because of data, and it loads the same whether you are signed
    in or not.

    Add a component here whenever you add one to `src/lib/ui/`.
  */

  // ── fixtures ──────────────────────────────────────────────────────────────
  const demoMap: MapListItem = {
    id: '00000000-0000-4000-8000-000000000000',
    name: 'Plan Cadastral de la ville de Saigon',
    year: 1882,
    location: 'Saigon',
    collection: 'Demo fixture',
    status: 'public',
  };

  const demoItems = [
    { id: '1', title: 'Cholon waterways' },
    { id: '2', title: 'District 4, 1878–1968' },
  ];

  const demoFacets = {
    map_type: { cadastral: 12, topographic: 7, city_plan: 3 },
    collection: { EFEO: 9, Gallica: 6 },
  };

  // ── interactive demo state ────────────────────────────────────────────────
  let tab = 'tokens';
  let renameValue = 'Untitled story';
  let dialogOpen = false;
  let locQuery = '';

  // ── the system, as data ───────────────────────────────────────────────────
  /*
    The system, as data. Six role tokens, redefined once per surface — that is
    the whole colour system. A component reads roles and never names a colour,
    which is what lets the same button be correct on paper and in the darkroom.
  */
  const SURFACES = [
    ['--ground', '#eae7df', '#14181a', 'The sheet itself'],
    ['--ground-raised', '#f6f4ef', '#1d2325', 'Panels, cards, table heads'],
    ['--ink', '#191c1a', '#e6e4dc', 'Body text; the neatline'],
    ['--ink-soft', '#5c625c', '#8b9490', 'Captions, labels, secondary text'],
    ['--rule', '#c6c2b6', '#2e3739', 'Every hairline and border'],
    ['--accent', '#0e7c86', '#2aa5ae', 'Live, selected, primary — survey cyan'],
    ['--on-accent', '#f6f4ef', '#0b1113', 'Text on an accent fill'],
    ['--status-ok', '#2e7d57', '#4caf87', 'Done, approved, passing'],
    ['--status-warn', '#9a6b1f', '#d6a344', 'Queued, needs attention'],
    ['--status-bad', '#a33a2e', '#e0705e', 'Failed, rejected, destructive'],
  ];

  /* Tight at reading sizes, loose at display sizes. */
  const TYPE = [
    ['--t-3xl', '4rem', 'Hero'],
    ['--t-2xl', '2.75rem', 'Page title'],
    ['--t-xl', '1.875rem', 'Section head'],
    ['--t-lg', '1.375rem', 'Subhead, standfirst'],
    ['--t-md', '1.0625rem', 'Body'],
    ['--t-sm', '0.9375rem', 'UI labels, buttons'],
    ['--t-xs', '0.8125rem', 'Data, table cells'],
    ['--t-2xs', '0.6875rem', 'Mono captions, tick labels'],
  ];

  const FACES = [
    ['--font-display', 'Spectral', 'Engraved, high contrast. Used with restraint.'],
    ['--font-body', 'Be Vietnam Pro', 'Body. A Vietnamese face for a Vietnamese archive.'],
    ['--font-mono', 'IBM Plex Mono', 'Coordinates, years, scales, tile ids. Tabular.'],
  ];

  const SPACE = [
    ['--s-1', '0.25rem'],
    ['--s-2', '0.5rem'],
    ['--s-3', '0.75rem'],
    ['--s-4', '1.25rem'],
    ['--s-5', '2rem'],
    ['--s-6', '3.5rem'],
  ];

  /*
    Paper is square, instruments are eased. So the neatline and every rule sit
    at 0 radius, and only what you press or type into gets the 2px. Elevation
    on paper is tone plus a rule — there is one shadow, for things that
    genuinely float above the sheet.
  */
  const LINE = [
    ['--rule-hair', '1px', 'Borders, dividers, table rows'],
    ['--rule-thick', '2px', 'The neatline; table head underline'],
    ['--radius', '2px', 'Buttons, fields — nothing else'],
    ['--radius-pill', '999px', 'Chips and badges'],
    ['--shadow-overlay', '0 8px 32px rgb(0 0 0 / .18)', 'Modals and popovers only'],
  ];

  /*
    The card inventory. Twenty distinct card patterns, four of them reusable and
    sixteen locked to a single page. This table is the reason this page exists:
    the duplication is invisible when the definitions sit in sixteen files.
  */
  const CARDS_GLOBAL = [
    ['.section-card', 'components/editorial.css', 'Every editorial page'],
    ['.catalog-card', 'components/catalog.css', 'CatalogCard, /archive'],
    ['.panel', 'primitives.css', 'Anywhere — the one panel'],
    ['.sb-card', 'components/sidebar.css', 'Tool sidebars (needs --sb-* from a parent)'],
    [
      '.auth-gate-card',
      'components/auth-gate.css',
      'AuthGate, /explore?mode=annotate, /explore?mode=story',
    ],
  ];

  const CARDS_SCOPED = [
    ['.layer-card', 'pages/about.css', '.about-page'],
    ['.phase-card', 'pages/about.css', '.about-page'],
    ['.cta-card', 'pages/about.css', '.about-page'],
    ['.latest-card', 'pages/about.css', '.about-page'],
    ['.user-card', 'pages/about.css', '.about-page'],
    ['.card', 'pages/admin-scout.css', '.scout-page'],
    ['.sidebar-card', 'pages/blog-post.css', '.blog-post-page'],
    ['.post-card', 'pages/blog.css', '.blog-page'],
    ['.subscribe-card', 'pages/blog.css', '.blog-page'],
    ['.profile-card', 'pages/profile.css', '.profile-page'],
    ['.stat-card', 'pages/profile.css', '.profile-page'],
    ['.status-row', 'pages/admin-status.css', 'global — /admin?tab=status'],
  ];

  const TABS = [
    { value: 'tokens', label: 'Tokens' },
    { value: 'parts', label: 'Parts' },
    { value: 'components', label: 'Components' },
    { value: 'cards', label: 'Cards' },
  ];
</script>

<svelte:head>
  <title>Screens — VMA Design System</title>
  <meta name="description" content="Every token, part and component in one place." />
  <meta name="robots" content="noindex" />
</svelte:head>

<div class="page screens-page">
  <PageHero
    eyebrow="Design system"
    sub="Every token, part and component in one place, so you can see what exists before building a second one. No data — nothing here can break."
  >
    <svelte:fragment slot="title">
      Screens<br /><span class="text-highlight">one page, whole system.</span>
    </svelte:fragment>
  </PageHero>

  <main class="editorial-main">
    <div class="sc-nav">
      <ChunkyTabs tabs={TABS} active={tab} on:change={(e) => (tab = e.detail)} />
    </div>

    <!-- ─────────────────────────────────────────────── TOKENS ── -->
    {#if tab === 'tokens'}
      <section class="sc-section">
        <h2 class="sc-h2">Colour</h2>
        <p class="sc-blurb">
          Six roles, redefined once per surface. A component reads a role and never names a colour —
          that is what lets one button be correct on paper and in the darkroom. A hex literal in a
          component <code>&lt;style&gt;</code> block is a bug, and the lint script fails the build on
          one.
        </p>
        <table class="data-table">
          <thead>
            <tr>
              <th>Token</th>
              <th>Paper</th>
              <th>Darkroom</th>
              <th>Role</th>
            </tr>
          </thead>
          <tbody>
            {#each SURFACES as [name, paper, dark, role] (name)}
              <tr>
                <td><code class="sc-code">{name}</code></td>
                <td>
                  <span class="sc-dot" style="background: {paper}"></span>
                  <span class="num">{paper}</span>
                </td>
                <td>
                  <span class="sc-dot" style="background: {dark}"></span>
                  <span class="num">{dark}</span>
                </td>
                <td>{role}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>

      <section class="sc-section">
        <h2 class="sc-h2">Type</h2>
        <p class="sc-blurb">
          Three faces, self-hosted from <code>/fonts</code>, each shipped only in latin, latin-ext
          and vietnamese. The corpus is French, Vietnamese and English.
        </p>
        <table class="data-table">
          <tbody>
            {#each FACES as [name, family, role] (name)}
              <tr>
                <td><code class="sc-code">{name}</code></td>
                <td><span style="font-family: var({name})">{family}</span></td>
                <td>{role}</td>
              </tr>
            {/each}
          </tbody>
        </table>

        <div class="sc-typelist">
          {#each TYPE as [name, size, role] (name)}
            <div class="sc-typerow">
              <code class="sc-code">{name}</code>
              <span class="sc-hex">{size}</span>
              <span class="sc-sample" style="font-size: var({name})">
                Saigon · Chợ Lớn · 1882
              </span>
              <span class="sc-role">{role}</span>
            </div>
          {/each}
        </div>
      </section>

      <section class="sc-section">
        <h2 class="sc-h2">Line, radius, elevation</h2>
        <p class="sc-blurb">
          Paper is square and instruments are eased, so the neatline and every rule sit at 0 and
          only what you press or type into gets the 2px. Elevation is tone plus a rule; there is one
          shadow, for what genuinely floats above the sheet.
        </p>
        <table class="data-table">
          <tbody>
            {#each LINE as [name, value, role] (name)}
              <tr>
                <td><code class="sc-code">{name}</code></td>
                <td class="num">{value}</td>
                <td>{role}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>

      <section class="sc-section">
        <h2 class="sc-h2">Space</h2>
        <p class="sc-blurb">Six steps. Breakpoints are 600 / 900 / 1280. Three.</p>
        <div class="sc-spacelist">
          {#each SPACE as [name, value] (name)}
            <div class="sc-typerow">
              <code class="sc-code">{name}</code>
              <span class="sc-hex">{value}</span>
              <span class="sc-bar" style="width: var({name})"></span>
            </div>
          {/each}
        </div>
      </section>
    {/if}

    <!-- ──────────────────────────────────────────────── PARTS ── -->
    {#if tab === 'parts'}
      <section class="sc-section">
        <h2 class="sc-h2">Buttons</h2>
        <p class="sc-blurb">
          One class, from <code>primitives.css</code>. There used to be four parallel button
          vocabularies — <code>.btn</code>, <code>.sb-btn</code>, <code>.tool-btn</code>,
          <code>.pill-btn</code>, plus <code>.action-btn</code> / <code>.ctrl-btn</code> /
          <code>.primary-btn</code> / <code>.secondary-btn</code>. The old names are aliased onto
          this one, so they still render; write <code>.btn</code> in new markup. Rules darken on hover
          — nothing lifts, nothing casts a shadow.
        </p>
        <div class="sc-row">
          <button class="btn btn--primary">Primary action</button>
          <button class="btn">Default</button>
          <button class="btn btn--ghost">Ghost</button>
          <button class="btn btn--danger">Danger</button>
          <button class="btn" aria-pressed="true">Selected</button>
          <button class="btn btn--primary" disabled>Disabled</button>
        </div>
        <div class="sc-row">
          <button class="btn btn--sm">Small</button>
          <button class="btn btn--xs">Extra small</button>
          <button class="btn btn--sm btn--icon" aria-label="Close">×</button>
        </div>
        <h3 class="sc-h3">.chip — the pill button</h3>
        <div class="sc-row">
          <button class="chip">Default</button>
          <button class="chip primary">Primary</button>
          <button class="chip add">Add</button>
          <button class="chip danger">Danger</button>
          <button class="chip ghost">Ghost</button>
          <button class="chip active">Active</button>
          <button class="chip" disabled>Disabled</button>
        </div>
        <h3 class="sc-h3">.btn — the squarer sibling, for admin and dialogs</h3>
        <div class="sc-row">
          <button class="btn btn-primary">Primary</button>
          <button class="btn btn-outline">Outline</button>
          <button class="btn btn-success">Success</button>
          <button class="btn btn-danger">Danger</button>
          <button class="btn btn-ghost">Ghost</button>
          <button class="btn btn-outline btn-sm">Small</button>
          <button class="btn btn-outline btn-xs">Extra small</button>
          <button class="btn btn-primary" disabled>Disabled</button>
        </div>
      </section>

      <section class="sc-section">
        <h2 class="sc-h2">Loading and empty states</h2>
        <p class="sc-blurb">
          One spinner for the whole app, in <code>components/feedback.css</code>. Size and colour
          tune through <code>--spinner-size</code>, <code>--spinner-thickness</code>,
          <code>--spinner-track</code> and <code>--spinner-ink</code> — a variant is three
          declarations, never a second <code>@keyframes</code>.
        </p>
        <div class="sc-row">
          <span class="spinner"></span>
          <span class="spinner" style="--spinner-size: 14px; --spinner-thickness: 2.5px"></span>
          <span class="spinner" style="--spinner-size: 40px; --spinner-ink: var(--accent)"></span>
          <button class="btn btn-primary"><span class="spinner on-ink"></span>&nbsp;Running…</button
          >
        </div>
        <h3 class="sc-h3">.state-msg</h3>
        <div class="sc-stack">
          <p class="state-msg">Loading maps…</p>
          <p class="state-msg">No results.</p>
          <p class="state-msg error">Couldn't reach the archive.</p>
        </div>
      </section>

      <section class="sc-section">
        <h2 class="sc-h2">Chips and badges</h2>
        <p class="sc-blurb">
          Only <code>.chip-blue</code>, <code>.chip-green</code> and <code>.chip-yellow</code> exist —
          the orange, purple and red chip classes were removed.
        </p>
        <div class="sc-row">
          <span class="label-chip">Label chip</span>
          <span class="badge-chip chip-blue">Blue</span>
          <span class="badge-chip chip-green">Green</span>
          <span class="badge-chip chip-yellow">Yellow</span>
        </div>
        <h3 class="sc-h3">Icon blobs</h3>
        <div class="sc-row">
          <div class="icon-blob color-green">🗺</div>
          <div class="icon-blob color-blue">📊</div>
          <div class="icon-blob color-orange">👥</div>
          <div class="icon-blob color-yellow">⭐</div>
          <div class="icon-blob color-purple">🔮</div>
        </div>
      </section>

      <section class="sc-section">
        <h2 class="sc-h2">Text highlight</h2>
        <p class="sc-blurb">
          <code>.text-highlight</code> belongs on one or two words of a hero title — never in body text.
        </p>
        <p class="sc-hero-sample">
          Saigon <span class="text-highlight">across time.</span>
        </p>
      </section>
    {/if}

    <!-- ─────────────────────────────────────────── COMPONENTS ── -->
    {#if tab === 'components'}
      <section class="sc-section">
        <h2 class="sc-h2">Components</h2>
        <p class="sc-blurb">
          Everything in <code>src/lib/ui/</code>, rendered from fixtures. These import nothing from
          <code>features/</code>, <code>map/</code> or <code>data/</code>, so any page may use them.
        </p>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">PageHero</code>
            <span class="sc-role"
              >The hero on every editorial page. You are looking at one above.</span
            >
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">ChunkyTabs</code>
            <span class="sc-role">Tab strip. Use instead of buttons that toggle a variable.</span>
          </div>
          <div class="sc-stage">
            <ChunkyTabs
              tabs={[
                { value: 'a', label: 'First' },
                { value: 'b', label: 'Second' },
              ]}
              active="a"
            />
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">MapCard</code>
            <span class="sc-role">A map in a listing. Optional favourite and source badge.</span>
          </div>
          <div class="sc-stage sc-stage-narrow">
            <MapCard map={demoMap} href="#" showSourceBadge />
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">CatalogCard</code>
            <span class="sc-role"
              >Generic listing card with thumb, meta, description and action slots.</span
            >
          </div>
          <div class="sc-stage sc-stage-narrow">
            <CatalogCard title="Plan Cadastral, 1882" href="#">
              <svelte:fragment slot="meta">
                <span class="meta-tag">1882</span><span class="meta-tag">Cadastral</span>
              </svelte:fragment>
              <svelte:fragment slot="description">A fixture, not a real record.</svelte:fragment>
            </CatalogCard>
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">LibraryGrid</code>
            <span class="sc-role">Project and story libraries. Items need only id and title.</span>
          </div>
          <div class="sc-stage">
            <LibraryGrid items={demoItems} noun="Story" eyebrow="Demo" showCreate={false} />
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">FacetRail</code>
            <span class="sc-role">Faceted filter column with counts.</span>
          </div>
          <div class="sc-stage sc-stage-narrow">
            <FacetRail facets={demoFacets} selected={{}} />
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">InlineRename</code>
            <span class="sc-role">Click the title to edit it in place. This one is live.</span>
          </div>
          <div class="sc-stage">
            <InlineRename bind:value={renameValue} placeholder="Story title" />
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">NameDialog</code>
            <span class="sc-role">Naming flow. Live — the button really opens it.</span>
          </div>
          <div class="sc-stage">
            <button class="pill-btn" on:click={() => (dialogOpen = true)}>Open dialog</button>
            <NameDialog
              bind:open={dialogOpen}
              heading="Name this story"
              showDescription
              on:cancel={() => (dialogOpen = false)}
              on:submit={() => (dialogOpen = false)}
            />
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">NavDropdown</code>
            <span class="sc-role">Nav menu disclosure. Takes a default slot of links.</span>
          </div>
          <div class="sc-stage">
            <NavDropdown label="Menu">
              <a href="#top" class="dropdown-item">First link</a>
              <a href="#top" class="dropdown-item">Second link</a>
            </NavDropdown>
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">LocationSearch</code>
            <span class="sc-role">
              Nominatim place lookup. Live — typing here really queries OpenStreetMap.
            </span>
          </div>
          <div class="sc-stage sc-stage-narrow">
            <LocationSearch bind:query={locQuery} />
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">AuthGate</code>
            <span class="sc-role">
              Signed-out gate for /explore?mode=annotate and /explore?mode=story. Not rendered here
              — its button starts a real Google sign-in.
            </span>
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">SnapSheet</code>
            <span class="sc-role">
              Mobile bottom sheet. Not rendered here — it is fixed-position and would cover the
              page.
            </span>
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">NavBar · EditorialFooter</code>
            <span class="sc-role">
              Mounted once by the editorial layout. Top and bottom of this page.
            </span>
          </div>
        </div>
      </section>
    {/if}

    <!-- ───────────────────────────────────────────────── CARDS ── -->
    {#if tab === 'cards'}
      <section class="sc-section">
        <h2 class="sc-h2">Cards</h2>
        <p class="sc-blurb">
          Twenty distinct card patterns exist. Four are reusable; sixteen are locked to a single
          page and cannot be used anywhere else. Almost all of them are the same object — a white
          box with a thick border and a solid shadow. <strong
            >Check this list before writing a twenty-first.</strong
          >
        </p>

        <h3 class="sc-h3">Reusable — reach for these</h3>
        <div class="sc-stage">
          <div class="section-card" style="padding: 1.5rem">
            <h4 class="section-title-sm" style="margin:0 0 .5rem">.section-card</h4>
            <p class="section-desc" style="margin:0">
              The editorial default. Thick border, large radius, solid shadow.
            </p>
          </div>
        </div>
        <table class="sc-table">
          <thead><tr><th>Class</th><th>File</th><th>Used by</th></tr></thead>
          <tbody>
            {#each CARDS_GLOBAL as [cls, file, used] (cls)}
              <tr><td><code>{cls}</code></td><td><code>{file}</code></td><td>{used}</td></tr>
            {/each}
          </tbody>
        </table>

        <h3 class="sc-h3">Locked to one page — the duplication</h3>
        <table class="sc-table">
          <thead><tr><th>Class</th><th>File</th><th>Scoped under</th></tr></thead>
          <tbody>
            {#each CARDS_SCOPED as [cls, file, scope] (cls + file)}
              <tr
                ><td><code>{cls}</code></td><td><code>{file}</code></td><td><code>{scope}</code></td
                ></tr
              >
            {/each}
          </tbody>
        </table>
      </section>

      <section class="sc-section">
        <h2 class="sc-h2">Status tones</h2>
        <p class="sc-blurb">
          The <code>.status-row</code> variants from <code>/admin?tab=status</code>. Colour never
          carries meaning alone — the sentence on the card says the same thing.
        </p>
        <div class="sc-grid3">
          <article class="status-row tone-good">
            <div class="status-row-head">
              <h3 class="status-row-label">Good</h3>
              <div class="status-row-value">1,369</div>
            </div>
            <p class="status-row-detail">Working as intended.</p>
          </article>
          <article class="status-row tone-warn">
            <div class="status-row-head">
              <h3 class="status-row-label">Warning</h3>
              <div class="status-row-value">2 of 39</div>
            </div>
            <p class="status-row-detail">Partly done; needs attention but not blocked.</p>
          </article>
          <article class="status-row tone-bad">
            <div class="status-row-head">
              <h3 class="status-row-label">Blocked</h3>
              <div class="status-row-value">0 of 39</div>
            </div>
            <p class="status-row-detail">Nothing works here yet.</p>
            <p class="status-row-next"><span>Next</span> What would unblock it.</p>
          </article>
          <article class="status-row tone-idle">
            <div class="status-row-head">
              <h3 class="status-row-label">Neutral</h3>
              <div class="status-row-value">101</div>
            </div>
            <p class="status-row-detail">A count with no judgement attached.</p>
          </article>
        </div>
      </section>
    {/if}
  </main>
</div>
