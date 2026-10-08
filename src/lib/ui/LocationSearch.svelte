<!--
  LocationSearch — headless place lookup for a search field.

  Driven by an external `query` prop; renders an inline result list. Emits
  `pickLocation` with { lat, lng, label, bbox? }.

  Two sources, in this order:

  1. **Coordinates**, parsed locally — decimal, degrees/minutes/seconds, and the
     military grid references the US Army sheets of Vietnam carry (`XS 8965
     4123`, `48Q XD 850 418`). Those are on the **Indian 1960 datum**, so the
     same reference is offered twice: the wartime reading first, the modern
     WGS84 one under it, ~480 m apart. Picking between them is the reader's
     call — the archive cannot know which map the reference came off.
     The maths is `$lib/core/geo/coordinates.ts`.
  2. **Place names**, from Nominatim.

  Both run: a grid reference can also be somebody's search for a place, and
  suppressing one to favour the other guesses wrong either way.

  Keyboard: the input lives in the parent, so the parent forwards its keydown
  to the exported `keydown` (`bind:this`) — ↑/↓ move the highlight over every
  row, Enter picks it (the first row when none is lit), Escape puts it out. It
  returns true when it used the key, and the parent then has nothing to do.
  `activeId` is the lit row's element id, for the input's aria-activedescendant.
-->
<script context="module" lang="ts">
  let instances = 0;
</script>

<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { t } from '$lib/core/i18n';
  import { debounce } from '$lib/core/utils/debounce';
  import {
    parseCoordinateQuery,
    type CoordHit,
    type CoordSystem,
    type CoordDatum,
  } from '$lib/core/geo/coordinates';

  export let query: string = '';
  /** Hide the list (parent controls visibility, e.g. when collapsed). */
  export let hidden: boolean = false;
  /** Offer coordinate and grid-reference readings. Off for name-only fields. */
  export let coordinates: boolean = true;
  /** `west,south,east,north`: rank places inside it first (not a hard limit). */
  export let viewbox: string | null = null;
  /** The highlighted row's element id (bind it to the input's `aria-activedescendant`). */
  export let activeId: string | null = null;

  const dispatch = createEventDispatcher<{
    pickLocation: {
      lat: number;
      lng: number;
      label: string;
      bbox?: [number, number, number, number];
      geojson?: import('geojson').Geometry;
      /** The OpenStreetMap object a place result is, for a caller that keeps the link. */
      osm?: { type: 'node' | 'way' | 'relation'; id: number };
    };
  }>();

  let results: any[] = [];
  let loading = false;
  let abortCtrl: AbortController | null = null;
  let lastQuery = '';
  /** Index over the coordinate rows, then the place rows; -1 is none. */
  let active = -1;
  const uid = `ls-${++instances}`;

  $: if (query !== lastQuery) {
    lastQuery = query;
    active = -1;
    scheduleSearch();
  }

  // Parsing is pure and microseconds long, so it runs on the keystroke rather
  // than behind the debounce the network call needs.
  $: coordHits = coordinates ? parseCoordinateQuery(query) : [];

  // Every key below is spelled out as a literal translator call on purpose:
  // `tests/i18n.spec.ts` finds call sites by reading the source, so a string
  // assembled out of a lookup table is one it reports as orphaned and nobody
  // ever translates. (It reads comments too — do not write an example here.)
  // UTM is the same word in both languages, so it is not a key at all.
  $: SYSTEM_LABEL = {
    mgrs: $t('Military grid'),
    utm: 'UTM',
    latlon: $t('Coordinates'),
  } satisfies Record<CoordSystem, string>;
  /** The datum's name — a proper noun, the same in both languages. */
  const DATUM_NAME: Record<CoordDatum, string> = {
    indian1960: 'Indian 1960',
    wgs84: 'WGS 84',
  };
  /** What that name means to a reader who has not met it before. */
  $: DATUM_GLOSS = {
    indian1960: $t('as printed on US Army sheets'),
    wgs84: $t('modern GPS datum'),
  } satisfies Record<CoordDatum, string>;

  /**
   * Two readings of one grid reference share a title, so the datum goes in it —
   * otherwise the list shows the same bold line twice and the reader picks by
   * coin toss. Both lines truncate to one line each (`.mo-result-*`), which is
   * why the position leads the sub-line: where it lands is the thing that
   * actually differs, and it has to survive the ellipsis.
   */
  $: coordRows = coordHits.map((hit) => {
    const parts = [
      `${hit.lat.toFixed(5)}, ${hit.lng.toFixed(5)}`,
      SYSTEM_LABEL[hit.system],
      DATUM_GLOSS[hit.datum],
    ];
    const side = hit.precisionM * 2;
    if (side >= 1000) parts.push($t('{N} km square', { N: side / 1000 }));
    else if (side >= 1) parts.push($t('{N} m square', { N: side }));
    return { hit, title: `${hit.ref} — ${DATUM_NAME[hit.datum]}`, sub: parts.join(' · ') };
  });

  const scheduleSearch = debounce(runSearch, 300);

  async function runSearch() {
    const q = query.trim();
    if (q.length < 2) {
      results = [];
      active = -1;
      return;
    }
    abortCtrl?.abort();
    abortCtrl = new AbortController();
    loading = true;
    try {
      const params = new URLSearchParams({
        format: 'jsonv2',
        q: q + ', Vietnam',
        addressdetails: '1',
        limit: '3',
        polygon_geojson: '1',
      });
      if (viewbox) params.set('viewbox', viewbox);
      const res = await fetch(`https://nominatim.openstreetmap.org/search?${params}`, {
        signal: abortCtrl.signal,
      });
      results = res.ok ? await res.json() : [];
      active = -1;
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        results = [];
        active = -1;
      }
    } finally {
      loading = false;
    }
  }

  function pick(r: any) {
    const lat = parseFloat(r.lat),
      lng = parseFloat(r.lon);
    let bbox: [number, number, number, number] | undefined;
    if (Array.isArray(r.boundingbox) && r.boundingbox.length === 4) {
      const [s, n, w, e] = r.boundingbox.map(parseFloat);
      bbox = [w, s, e, n];
    }
    const osm =
      ['node', 'way', 'relation'].includes(r.osm_type) && Number.isSafeInteger(r.osm_id)
        ? { type: r.osm_type, id: r.osm_id }
        : undefined;
    dispatch('pickLocation', { lat, lng, label: r.display_name, bbox, geojson: r.geojson, osm });
  }

  function pickCoord(hit: CoordHit, label: string) {
    dispatch('pickLocation', { lat: hit.lat, lng: hit.lng, label, bbox: hit.bbox });
  }

  $: rowCount = hidden ? 0 : coordRows.length + results.length;
  // Rows can shrink under a lit one (a new keystroke); then nothing is lit.
  $: current = active < rowCount ? active : -1;
  $: activeId =
    current < 0
      ? null
      : current < coordRows.length
        ? `${uid}-c${current}`
        : `${uid}-p${current - coordRows.length}`;

  function pickRow(i: number) {
    if (i < coordRows.length) pickCoord(coordRows[i].hit, coordRows[i].title);
    else pick(results[i - coordRows.length]);
  }

  /** Wired to the parent input's keydown; true when the key was used. */
  export function keydown(e: KeyboardEvent): boolean {
    if (rowCount === 0 || e.isComposing) return false;
    if (e.key === 'ArrowDown') active = (current + 1) % rowCount;
    else if (e.key === 'ArrowUp') active = current <= 0 ? rowCount - 1 : current - 1;
    else if (e.key === 'Enter') pickRow(Math.max(current, 0));
    else if (e.key === 'Escape' && current >= 0) active = -1;
    else return false;
    e.preventDefault();
    return true;
  }
</script>

{#if !hidden && (coordRows.length > 0 || results.length > 0)}
  <div class="ls" role="listbox" aria-label={$t('Places')}>
    {#if coordRows.length > 0}
      <div class="mo-results-label" aria-hidden="true">{$t('Coordinates')}</div>
      <ul class="mo-results" role="group" aria-label={$t('Coordinates')}>
        {#each coordRows as row, i (row.title)}
          <li role="presentation">
            <button
              type="button"
              class="mo-result"
              class:is-active={current === i}
              role="option"
              id="{uid}-c{i}"
              aria-selected={current === i}
              on:click={() => pickCoord(row.hit, row.title)}
            >
              <span class="mo-result-title">{row.title}</span>
              <span class="mo-result-sub">{row.sub}</span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}

    {#if results.length > 0}
      <div class="mo-results-label" aria-hidden="true">{$t('Places')}{loading ? ' …' : ''}</div>
      <ul class="mo-results" role="group" aria-label={$t('Places')}>
        {#each results as r, i (r.place_id)}
          <li role="presentation">
            <button
              type="button"
              class="mo-result"
              class:is-active={current === coordRows.length + i}
              role="option"
              id="{uid}-p{i}"
              aria-selected={current === coordRows.length + i}
              on:click={() => pick(r)}
            >
              <span class="mo-result-title">{r.display_name.split(',')[0]}</span>
              <span class="mo-result-sub">{r.display_name}</span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
{/if}

<style>
  .ls {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
</style>
