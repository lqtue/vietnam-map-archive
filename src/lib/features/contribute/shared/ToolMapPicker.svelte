<!--
  ToolMapPicker.svelte — the map picker in the /scan left rail, rendered inline
  by `ScanLeftRail`.

  It is `ArchiveBrowser` — the very component /explore's Browse pane uses, moved
  to `features/shared` for the purpose. Search box, three facet dropdowns, the
  count, and rows with the year, the title and a type chip. It used to render
  `SearchMapsTab`, which looked nothing like it: every rule in
  `search-panel.css` is scoped under `.search-panel`, so outside that floating
  container the rows drew with no border, no hover and titles at the inherited
  display size.

  The rows come from the catalog engine; the *list* still comes from
  `fetchLabelMaps` (or a caller's own), because the catalog knows nothing about
  triage or OCR progress and the picker must hand back a `LabelMapInfo`. So the
  list supplies the badge text and the lookup, and the browser supplies the rows
  and the filtering.

  Dispatches:
    loaded { maps }        — after the list arrives
    select { map }         — the LabelMapInfo the user picked
    error  { message }     — the list could not be loaded
-->
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import ArchiveBrowser from '$lib/features/shared/ArchiveBrowser.svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { triageState } from '$lib/data/maps/triageTypes';
  import { fetchLabelMaps } from '$lib/data/supabase/footprints';
  import type { LabelMapInfo } from '$lib/data/supabase/footprints';

  /** Currently selected map id — the row that ticks. */
  export let selectedMapId: string | null = null;
  /** Caller-supplied list. When set the picker offers only these and skips the
   *  fetch — the review queue is "sheets with pending polygons", not every
   *  georeferenced sheet. */
  export let maps: LabelMapInfo[] | null = null;
  /** Only maps that can be laid on the world. False for /scan?mode=inspect. */
  export let requireGeoref = true;

  const dispatch = createEventDispatcher<{
    loaded: { maps: LabelMapInfo[] };
    select: { map: LabelMapInfo };
    error: { message: string };
  }>();

  const { supabase } = getSupabaseContext();

  let loaded: LabelMapInfo[] = [];
  $: list = maps ?? loaded;
  $: byId = new Map(list.map((m) => [m.id, m]));

  // Over a 39-sheet pass "which have I already done?" is the column that
  // decides what to open next. A proposal nobody has accepted is not triaged —
  // that is the whole point of `validated_at`, and `triageState` is the one
  // place the rule lives. One strong mark beats two weak ones, so OCR'd wins.
  $: badges = Object.fromEntries(
    list.flatMap((m) => {
      const text =
        m.badge ?? (m.hasOcr ? "OCR'd" : triageState(m.triage) === 'ready' ? 'Triaged' : '');
      return text ? [[m.id, text] as [string, string]] : [];
    })
  );

  // Oldest → newest, the way /explore's Browse pane sorts.
  const byYear = (a: any, b: any) => (a.year ?? 9999) - (b.year ?? 9999);

  function handlePick(e: CustomEvent<{ map: { id: string } }>) {
    const picked = byId.get(e.detail.map.id);
    if (picked) dispatch('select', { map: picked });
  }

  onMount(async () => {
    if (maps) return;
    try {
      loaded = await fetchLabelMaps(supabase);
      dispatch('loaded', { maps: loaded });
    } catch (err: any) {
      dispatch('error', { message: err?.message ?? 'Failed to load maps' });
    }
  });
</script>

<!-- `filterIds` keeps the browser to sheets the tool can actually open: the
     catalog engine reaches the whole corpus, `list` is this rail's slice of it.
     showLabels={false}: a label hit flies /explore to a spot, which an
     ImageShell tool has nowhere to go with. -->
<div class="tool-map-picker">
  <ArchiveBrowser
    sortRows={byYear}
    {requireGeoref}
    filterIds={list.map((m) => m.id)}
    activeIds={selectedMapId ? [selectedMapId] : []}
    {badges}
    showLabels={false}
    on:pick={handlePick}
  />
</div>

<style>
  /* The browser was written for a card body that scrolls; in the rail it is the
     part that flexes, so the rows scroll and the filters stay put. */
  .tool-map-picker {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 0.6rem 0.65rem;
    gap: 0.5rem;
  }
</style>
