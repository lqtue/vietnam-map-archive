<script lang="ts">
  import { onMount } from 'svelte';
  import PageHero from '$lib/ui/PageHero.svelte';
  import Tabs from '$lib/ui/Tabs.svelte';
  import CatalogCard from '$lib/ui/CatalogCard.svelte';
  import CatalogGrid from '$lib/ui/CatalogGrid.svelte';
  import PaletteSearchField from '$lib/ui/PaletteSearchField.svelte';
  import SortHeader from '$lib/ui/SortHeader.svelte';
  import DataTable from '$lib/ui/DataTable.svelte';
  import MapCard from '$lib/ui/MapCard.svelte';
  import LibraryGrid from '$lib/ui/LibraryGrid.svelte';
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

  // ── interactive demo state ────────────────────────────────────────────────
  let tab = 'tokens';
  let renameValue = 'Untitled story';
  let dialogOpen = false;
  let locQuery = '';

  // ── the system, as data ───────────────────────────────────────────────────
  /*
    Roles only. The hex column used to be written out here beside each token,
    which meant the reference page kept its own copy of the palette and went
    stale the moment tokens.css changed — it was still advertising the old
    palette after this one landed. It reads the live computed value now, so it
    cannot disagree with the stylesheet.
  */
  const COLORS: [string, string][] = [
    ['--color-bg', 'Page background'],
    ['--color-white', 'Card and element backgrounds'],
    ['--color-text', 'Primary text; also the footer background'],
    ['--color-border', 'Every border'],
    ['--rule', 'Hairlines and printed rules'],
    ['--shadow-ink', 'Every offset shadow'],
    ['--color-primary', 'CTAs, links, active states, errors'],
    ['--color-yellow', 'Hero backgrounds, highlights, hover fills'],
    ['--color-blue', 'Info, in progress, research'],
    ['--color-green', 'Done / complete'],
    ['--color-orange', 'Community / building now'],
    ['--color-purple', 'Future / announcement'],
  ];

  /** The value the browser actually resolved, so the table cannot drift. */
  let resolved: Record<string, string> = {};
  onMount(() => {
    const cs = getComputedStyle(document.documentElement);
    resolved = Object.fromEntries(COLORS.map(([name]) => [name, cs.getPropertyValue(name).trim()]));
  });

  const TYPE = [
    ['--text-3xl', '2rem'],
    ['--text-2xl', '1.5rem'],
    ['--text-xl', '1.25rem'],
    ['--text-lg', '1.125rem'],
    ['--text-base', '1rem'],
    ['--text-sm', '0.875rem'],
    ['--text-xs', '0.75rem'],
  ];

  const SHADOWS = [
    ['--shadow-solid-xs', '2px 2px 0', 'Chips, dense controls'],
    ['--shadow-solid-sm', '4px 4px 0', 'Smaller cards, badges, secondary buttons'],
    ['--shadow-solid', '6px 6px 0', 'Feature cards, primary CTAs'],
    ['--shadow-solid-hover', '8px 8px 0', 'Hover lift only — never static'],
  ];

  const RADII = [
    ['--radius-sm', '8px', 'Tags'],
    ['--radius-md', '16px', 'Cards, inputs'],
    ['--radius-lg', '24px', 'Feature cards'],
    ['--radius-pill', '999px', 'Buttons, chips'],
  ];

  /*
    The card inventory: seven reusable, seven locked to a single page. This
    table is the reason this page exists — the duplication is invisible when
    the definitions sit in fourteen files.

    It is hand-maintained and it does go stale: before the Sept 2026 pass it
    still advertised seven cards (`.feature-card`, `.mega-card`, `.info-card`,
    `.layer-card`, `.phase-card`, `.latest-card`, `.user-card`, `.cta-card`)
    that earlier cleanups had already deleted, which is the exact failure this
    page is supposed to prevent. Grep before you add a row.
  */
  const CARDS_GLOBAL = [
    ['.section-card', 'components/editorial.css', 'The card. `--card-pad` sets its padding'],
    [
      '.section-card.is-sm',
      'components/editorial.css',
      'The column size — blog grid, post sidebar',
    ],
    [
      '.section-card.is-link',
      'components/editorial.css',
      'When the whole card is a link; it lifts',
    ],
    [
      '.stat-tile',
      'components/editorial.css',
      'One number and its caption; .is-sm packs three across',
    ],
    ['.catalog-card', 'components/catalog.css', 'CatalogCard, /catalog'],
    ['.card', 'components/catalog.css', 'CatalogGrid item'],
    ['.sb-card', 'components/sidebar.css', 'Tool sidebars (needs --sb-* from a parent)'],
    ['.auth-gate-card', 'components/auth-gate.css', 'AuthGate, /explore?mode=annotate|story'],
    ['.data-table.is-card', 'components/table.css', 'A table that reads as a card'],
  ];

  /*
    Four names left this list in Sept 2026 — `.post-card`, `.subscribe-card`,
    `.sidebar-card` and `.profile-card` — because all four were `.section-card`
    re-typed in a different file with a different padding. They are that card
    now, and what stayed behind is only what is genuinely theirs: a gap, a
    dashed edge, a tighter `--card-pad`.
  */
  const CARDS_SCOPED = [
    ['.micro-link-card', 'layouts/home.css', '.home-page'],
    ['.card', 'pages/admin-scout.css', '.scout-page'],
    ['.status-row', 'pages/admin-status.css', 'global — /admin?tab=status'],
  ];

  const TABS = [
    { key: 'tokens', label: 'Tokens' },
    { key: 'parts', label: 'Parts' },
    { key: 'components', label: 'Components' },
    { key: 'cards', label: 'Cards' },
  ];

  /** Demo state for the two `Tabs` tones in the gallery. */
  let demoTone: 'page' | 'rail' = 'page';
  let demoPageTab = 'one';
  let demoRailTab = 'one';
  const DEMO_TABS = [
    { key: 'one', label: 'One' },
    { key: 'two', label: 'Two' },
    { key: 'three', label: 'Three' },
  ];
  let demoSort = { key: 'year', asc: true };
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
      <Tabs
        label="Design system sections"
        tabs={TABS}
        active={tab}
        on:change={(e) => (tab = e.detail.key)}
      />
    </div>

    <!-- ─────────────────────────────────────────────── TOKENS ── -->
    {#if tab === 'tokens'}
      <section class="sc-section">
        <h2 class="sc-h2">Colour</h2>
        <p class="sc-blurb">
          Never hardcode one. A hex literal in a component <code>&lt;style&gt;</code> block is a bug.
        </p>
        <div class="sc-swatches">
          {#each COLORS as [name, role] (name)}
            <div class="sc-swatch">
              <div class="sc-swatch-chip" style="background: var({name})"></div>
              <code class="sc-code">{name}</code>
              <span class="sc-hex">{resolved[name] ?? '…'}</span>
              <span class="sc-role">{role}</span>
            </div>
          {/each}
        </div>
      </section>

      <section class="sc-section">
        <h2 class="sc-h2">Type</h2>
        <p class="sc-blurb">
          <strong>Google Sans</strong> where the reader's machine has it, otherwise
          <strong>Be Vietnam Pro</strong> for headings, nav, badges, labels and buttons and
          <strong>Inter</strong> for body text. Hero titles use
          <code>clamp(2.5rem, 6vw, 4rem)</code> — always fluid.
        </p>
        <div class="sc-typelist">
          {#each TYPE as [name, size] (name)}
            <div class="sc-typerow">
              <code class="sc-code">{name}</code>
              <span class="sc-hex">{size}</span>
              <span class="sc-sample" style="font-size: var({name})">
                Saigon · Chợ Lớn · 1882
              </span>
            </div>
          {/each}
        </div>
      </section>

      <section class="sc-section">
        <h2 class="sc-h2">Page shell</h2>
        <p class="sc-blurb">
          Every <code>(editorial)</code> route roots at
          <code>&lt;div class="page x-page"&gt;</code>, then <code>PageHero</code>, then
          <code>&lt;main class="editorial-main"&gt;</code>. <code>.page</code> carries the mount
          fade as a CSS animation with <code>both</code> fill and a
          <code>prefers-reduced-motion</code> guard — it used to be a <code>mounted</code> boolean
          flipped in <code>onMount</code> and read as <code>class:mounted</code>, which is a round
          trip through JS for something the first frame already does, on a page that server-renders.
          Six routes carried that boolean and four carried an identical copy of the CSS.
        </p>
        <p class="sc-blurb">
          <code>.editorial-main</code> caps the measure at 1100px.
          <code>.editorial-main.is-wide</code> opens it to 1400 for a dense table —
          <code>/admin?tab=scout</code> is the only caller, and prose never takes it.
        </p>

        <h2 class="sc-h2">Surface</h2>
        <p class="sc-blurb">
          Borders, shadows and radii. The shadow is always solid, never blurred.
        </p>
        <div class="sc-grid3">
          {#each SHADOWS as [name, value, role] (name)}
            <div class="sc-demo">
              <div class="sc-box" style="box-shadow: var({name})"></div>
              <code class="sc-code">{name}</code>
              <span class="sc-hex">{value}</span>
              <span class="sc-role">{role}</span>
            </div>
          {/each}
          {#each RADII as [name, value, role] (name)}
            <div class="sc-demo">
              <div class="sc-box" style="border-radius: var({name})"></div>
              <code class="sc-code">{name}</code>
              <span class="sc-hex">{value}</span>
              <span class="sc-role">{role}</span>
            </div>
          {/each}
          <div class="sc-demo">
            <div class="sc-box" style="border: var(--border-thin)"></div>
            <code class="sc-code">--border-thin</code>
            <span class="sc-hex">2px</span>
            <span class="sc-role">Inline labels, dividers</span>
          </div>
          <div class="sc-demo">
            <div class="sc-box" style="border: var(--border-thick)"></div>
            <code class="sc-code">--border-thick</code>
            <span class="sc-hex">3px</span>
            <span class="sc-role">Cards, nav, structural</span>
          </div>
        </div>
      </section>
    {/if}

    <!-- ──────────────────────────────────────────────── PARTS ── -->
    {#if tab === 'parts'}
      <section class="sc-section">
        <h2 class="sc-h2">Buttons</h2>
        <p class="sc-blurb">
          <strong>Two names, because there are two things</strong>, and one modifier vocabulary —
          the same words <code>.sb-btn</code> and <code>.sb-pill</code> use in the sidebar scope, so
          there is one set to learn. In September 2026 this was
          <strong>twenty-seven selectors across nine families</strong>, with four tones spelled
          three different ways; it is eleven now. Everything else was a context, not a design.
        </p>

        <h3 class="sc-h3">.btn — an action</h3>
        <div class="sc-row">
          <button class="btn">Default</button>
          <button class="btn is-primary">.is-primary</button>
          <button class="btn is-success">.is-success</button>
          <button class="btn is-danger">.is-danger</button>
          <button class="btn is-ghost">.is-ghost</button>
          <button class="btn is-primary" disabled>disabled</button>
        </div>
        <div class="sc-row">
          <button class="btn is-lg is-primary">.is-lg — a page CTA</button>
          <button class="btn">default</button>
          <button class="btn is-sm">.is-sm</button>
          <button class="btn is-xs">.is-xs</button>
        </div>

        <h3 class="sc-h3">.chip — a choice</h3>
        <p class="sc-blurb">
          A tab, a facet, a filter. It fills yellow under the cursor because it is a thing you are
          about to pick rather than a thing you are about to do, and
          <code>.is-on</code> is the one that is picked — the same word as
          <code>.sb-pill.is-on</code>.
        </p>
        <div class="sc-row">
          <button class="chip">Default</button>
          <button class="chip is-on">.is-on</button>
          <button class="chip is-primary">.is-primary</button>
          <button class="chip is-ghost">.is-ghost</button>
          <button class="chip is-sm">.is-sm</button>
          <button class="chip" disabled>disabled</button>
        </div>

        <h3 class="sc-h3">.is-icon — round, three sizes</h3>
        <p class="sc-blurb">
          48px is the floating map control, 28px a card's action corner, 22px a row toggle in a
          table. They were <code>.ctrl-btn</code>, <code>.btn-icon-edit</code> /
          <code>.btn-icon-delete</code> and <code>.cmp-btn</code>, three private families for one
          shape at three sizes.
        </p>
        <div class="sc-row">
          <button class="btn is-icon" aria-label="Zoom in">+</button>
          <button class="btn is-icon is-sm" aria-label="Edit">✎</button>
          <button class="btn is-icon is-xs" aria-label="Add to comparison">+</button>
          <button class="btn is-icon is-xs is-on" aria-label="Remove from comparison">✓</button>
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
          <span class="spinner" style="--spinner-size: 40px; --spinner-ink: var(--color-primary)"
          ></span>
          <button class="btn is-primary"><span class="spinner on-ink"></span>&nbsp;Running…</button>
        </div>
        <h3 class="sc-h3">.empty-state</h3>
        <p class="sc-blurb">
          One class, two faces. Inline by default — it sits under a list inside a card.
          <code>.is-block</code> is the standalone face, for when it stands in the space the list
          would have filled; <code>.error</code> is the failed one. It was three classes (<code
            >.state-msg</code
          >, a second <code>.empty-state</code> in
          <code>layouts/tool-page.css</code>, and a third inside <code>OcrSidebar</code>) until Sept
          2026.
        </p>
        <div class="sc-stack">
          <p class="empty-state">No results.</p>
          <p class="empty-state is-block">Nothing here yet — try another tab or the catalog.</p>
          <p class="empty-state is-block error">Couldn't reach the archive.</p>
        </div>
      </section>

      <section class="sc-section">
        <h2 class="sc-h2">Chips and badges</h2>
        <p class="sc-blurb">
          <code>.badge-chip</code> plus one tone. Six tones exist; there is no purple.
          <code>.chip-yellow</code> is a filled yellow and keeps dark ink in both themes —
          <code>.chip-white</code> is the paper face it used to paint, which is why four components carried
          a private yellow tint until Sept 2026.
        </p>
        <div class="sc-row">
          <span class="label-chip">Label chip</span>
          <span class="badge-chip chip-blue">Blue</span>
          <span class="badge-chip chip-green">Green</span>
          <span class="badge-chip chip-yellow">Yellow</span>
          <span class="badge-chip chip-orange">Orange</span>
          <span class="badge-chip chip-red">Red</span>
          <span class="badge-chip chip-gray">Gray</span>
          <span class="badge-chip chip-white">White</span>
        </div>
        <h3 class="sc-h3">.badge-chip.is-sm — inside a table row</h3>
        <p class="sc-blurb">
          The dense face: base font, no offset shadow. A display-size chip in a table row reaches
          into the row below. Four components had a private copy of this.
        </p>
        <div class="sc-row">
          <span class="badge-chip is-sm chip-green">1882</span>
          <span class="badge-chip is-sm chip-orange">Gallica</span>
          <span class="badge-chip is-sm chip-gray">Cadastral</span>
        </div>
        <h3 class="sc-h3">.stat-tile</h3>
        <div class="sc-row">
          <span class="stat-tile"
            ><span class="value">412</span><span class="label">Maps</span></span
          >
          <span class="stat-tile is-sm"
            ><span class="value">3.2 km</span><span class="label">Distance</span></span
          >
          <span class="stat-tile is-sm"
            ><span class="value">7</span><span class="label">Stops</span></span
          >
        </div>
      </section>

      <section class="sc-section">
        <h2 class="sc-h2">Text highlight</h2>
        <p class="sc-blurb">
          <code>.text-highlight</code> belongs on one or two words of a hero title — never in body text.
        </p>
        <p class="sc-hero-sample">
          Vietnam <span class="text-highlight">across time.</span>
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
            <code class="sc-code">Tabs</code>
            <span class="sc-role">
              The one tab strip. Two tones because there are two design systems, not because there
              are two components: <code>page</code> is the editorial <code>.chip</code>,
              <code>rail</code> the sidebar <code>.sb-pill</code>. Pass a row an
              <code>href</code> and the whole strip becomes links with
              <code>aria-current</code>; without one it is a real
              <code>role="tablist"</code>. There were five of these in September 2026.
            </span>
          </div>
          <div class="sc-stage sc-stage-col">
            <Tabs
              label="Tone demo"
              tabs={DEMO_TABS}
              active={demoPageTab}
              on:change={(e) => (demoPageTab = e.detail.key)}
            />
            <div class="sc-rail-box">
              <Tabs
                tone="rail"
                label="Tone demo, rail"
                tabs={DEMO_TABS}
                active={demoRailTab}
                on:change={(e) => (demoRailTab = e.detail.key)}
              />
            </div>
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">.sb-search</code>
            <span class="sc-role">
              Not a component — the one search field, in
              <code>components/sidebar.css</code>. Both /explore rails, both /scan rails, the two
              table toolbars and /catalog wear it. Two sizes past the default:
              <code>.is-compact</code> is the toolbar, where the field shares a row with a status
              select, and <code>.is-page</code> the full width of an editorial page. It was four designs
              — two of them a quarter-rem apart — until September 2026.
            </span>
          </div>
          <div class="sc-stage sc-stage-col">
            <div class="sc-rail-box">
              <div class="sb-search">
                <svg
                  width="13"
                  height="13"
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  ><circle cx="7" cy="7" r="5" /><path d="M15 15l-3.5-3.5" /></svg
                >
                <input class="sb-search-input" placeholder="Search a place…" />
              </div>
            </div>
            <div class="sc-rail-box">
              <div class="sb-search is-compact">
                <svg
                  width="13"
                  height="13"
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  ><circle cx="7" cy="7" r="5" /><path d="M15 15l-3.5-3.5" /></svg
                >
                <input class="sb-search-input" placeholder="Filter text…" />
              </div>
            </div>
            <div class="sb-search is-page">
              <svg
                width="18"
                height="18"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                ><circle cx="7" cy="7" r="5" /><path d="M15 15l-3.5-3.5" /></svg
              >
              <input class="sb-search-input" placeholder="Search by title, creator, year…" />
            </div>
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">SortHeader</code>
            <span class="sc-role">
              A sortable column header for any <code>.data-table</code>. A real
              <code>&lt;button&gt;</code> in the <code>&lt;th&gt;</code> with
              <code>aria-sort</code> on the cell, so it is reachable from the keyboard — the four
              hand-rolled versions it replaced were not. Both carets always draw, one lit, so the
              header keeps its width when the direction flips. Sort state is
              <code>$lib/core/utils/tableSort.ts</code>.
            </span>
          </div>
          <div class="sc-stage">
            <table class="data-table is-dense">
              <thead>
                <tr>
                  <SortHeader
                    label="Title"
                    key="name"
                    sort={demoSort}
                    on:sort={(e) => (demoSort = { key: e.detail.key, asc: !demoSort.asc })}
                  />
                  <SortHeader
                    label="Year"
                    key="year"
                    klass="num"
                    sort={demoSort}
                    on:sort={(e) => (demoSort = { key: e.detail.key, asc: !demoSort.asc })}
                  />
                </tr>
              </thead>
              <tbody>
                <tr><td>Plan Cadastral</td><td class="num">1882</td></tr>
                <tr><td>Plan de Saigon</td><td class="num">1799</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">DataTable</code>
            <span class="sc-role">
              The scaffolding the four tables repeated: the scroll container, the
              <code>&lt;table&gt;</code> and its density, the header built from a column list, and
              the <code>&lt;tbody&gt;</code>. Rows are the caller's — they arrive through the
              default slot, because the rows are the only part that ever differed. A blank column (a
              dot, a thumbnail, an actions cell) is a column with
              <code>sortable: false</code> and an <code>srLabel</code>, so a table's header is one
              list in one place. Anything under the table — an empty state, a paging button — is the
              <code>after</code> slot.
            </span>
          </div>
          <div class="sc-stage">
            <DataTable
              columns={[
                { key: 'dot', label: '', srLabel: 'Status', sortable: false },
                { key: 'name', label: 'Title' },
                { key: 'year', label: 'Year', klass: 'num' },
              ]}
              klass="is-dense"
              bind:sort={demoSort}
            >
              <tr><td>●</td><td>Plan Cadastral</td><td class="num">1882</td></tr>
              <tr><td>●</td><td>Plan de Saigon</td><td class="num">1799</td></tr>
            </DataTable>
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">PaletteSearchField</code>
            <span class="sc-role">
              The search box that opens the command palette. One field, three places — the home
              hero, the nav and the palette itself — so the thing a reader types into is the same
              object everywhere.
            </span>
          </div>
          <div class="sc-stage">
            <PaletteSearchField kbd="⌘K" />
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">CatalogGrid</code>
            <span class="sc-role">
              The responsive grid <code>CatalogCard</code> and <code>MapCard</code> sit in. A wrapper
              with a slot and nothing else — it exists so the column rule is written once.
            </span>
          </div>
          <div class="sc-stage">
            <CatalogGrid>
              <CatalogCard title="Plan Cadastral, 1882" href="#" />
              <CatalogCard title="Plan de Cholon, 1893" href="#" />
            </CatalogGrid>
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
              <!-- The `.meta` wrapper is the caller's job: CatalogCard drops this slot
                   straight into `.card-body`, which is a column flex, so bare spans
                   render full-width one per line. LibraryGrid wraps it the same way. -->
              <svelte:fragment slot="meta">
                <div class="meta">
                  <span class="badge-chip is-sm chip-gray">1882</span>
                  <span class="badge-chip is-sm chip-gray">Cadastral</span>
                </div>
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
            <button class="btn" on:click={() => (dialogOpen = true)}>Open dialog</button>
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
              Place lookup, plus coordinates parsed locally — decimal, DMS, and the military grid
              the US Army sheets carry (<code>XS 8965 4123</code>), which resolves on both the
              wartime Indian 1960 datum and WGS 84. Live — a place name really queries
              OpenStreetMap.
            </span>
          </div>
          <div class="sc-stage sc-stage-narrow">
            <label class="sb-search">
              <input
                class="sb-search-input"
                type="search"
                placeholder="Ben Thanh · 48Q XD 850 418 · 10.7769, 106.7009"
                aria-label="Location search demo"
                bind:value={locQuery}
              />
            </label>
            <LocationSearch bind:query={locQuery} />
          </div>
        </div>

        <div class="sc-item">
          <div class="sc-item-head">
            <code class="sc-code">AuthGate</code>
            <span class="sc-role">
              Signed-out gate for the annotate and story modes. Not rendered here — its button
              starts a real Google sign-in.
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
            <code class="sc-code">NavBar</code> ·
            <code class="sc-code">EditorialFooter</code>
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
        <!-- Counted off the two tables rather than written out: the prose said
             "twenty … four … sixteen" against a list of seven and seven, which is
             the same drift the tables themselves are here to prevent. -->
        <p class="sc-blurb">
          {CARDS_GLOBAL.length + CARDS_SCOPED.length} distinct card patterns exist.
          {CARDS_GLOBAL.length} are reusable; {CARDS_SCOPED.length} are locked to a single page and cannot
          be used anywhere else. Almost all of them are the same object — a white box with a thick border
          and a solid shadow.
          <strong>Check this list before writing another.</strong>
        </p>

        <h3 class="sc-h3">Reusable — reach for these</h3>
        <div class="sc-stage sc-stage-col">
          <div class="section-card">
            <h4 class="section-title-sm">.section-card</h4>
            <p class="section-desc">
              The editorial default. Thick border, large radius, solid shadow. Padding is
              <code>--card-pad</code>, so a caller that wants a tighter one sets a property rather
              than declaring a fifth card.
            </p>
          </div>
          <div class="section-card is-sm">
            <h4 class="section-title-sm">.section-card.is-sm</h4>
            <p class="section-desc">
              The column size: smaller radius, lighter shadow. The blog grid, a post's sidebar and
              the subscribe nudge were three separate cards that were each this one.
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
