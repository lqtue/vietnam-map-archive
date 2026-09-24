<!--
  This sheet is a join someone else made; here are the originals it was made from.

  62 sheets of the Indochine 1:25,000 entered the archive as whole cells, and
  they are not scans of whole cells. A third party cut IGN's two half-sheets
  together and downscaled them in the joining, and we downloaded that. It was
  established from the paper rather than the pixels: cell 36 carries the same
  blue pencil "36" as IGN's west half and cell 72 the same library stamp and
  handwritten annotation, in the same positions. A dimension test cannot see a
  derivative — two files differing in size are not the same file, which says
  nothing about whether one was made from the other.

  So the page says so, and points at the originals. It is not a deprecation
  notice: the join is still the only way to see the cell whole, because IGN
  never digitised its own assembled edition, and this row keeps its address so
  no published link dies.

  Renders nothing when there are no mirrored originals, which is every sheet in
  the archive but these — and, until the originals are published, every sheet
  for an anonymous reader, because RLS is what decides whether the loader sees
  them at all.
-->
<script lang="ts">
  import { t } from '$lib/core/i18n';

  /** IGN's own sheets, as the loader read them off `mirrors_original_for`. */
  export let originals: Array<{
    id: string;
    slug: string | null;
    name: string;
    year: number | null;
    sheet_half: string | null;
  }> = [];

  const PART_LABEL: Record<string, string> = {
    W: 'west half',
    E: 'east half',
  };

  /** The half a row covers, for a reader who cannot be expected to read a uuid. */
  function half(row: { sheet_half: string | null }): string {
    return row.sheet_half ?? '';
  }

  const part = (row: { sheet_half: string | null }) => PART_LABEL[half(row)] ?? half(row);

  // West before east, so the two links read in the order the paper does. The
  // loader already orders by `sheet_half`, which happens to agree; sorting here
  // as well means a change there cannot silently reverse them on the page.
  $: ordered = [...originals].sort((a, b) => half(a).localeCompare(half(b)));

  /** A sheet is only reachable at its name; a row without one is not linked. */
  const href = (row: { slug: string | null }) => (row.slug ? `/catalog/${row.slug}` : null);
</script>

{#if ordered.length}
  <section class="superseded">
    <h2>{$t('This scan is an assemblage')}</h2>
    <p>
      {$t(
        'The sheet was printed as two halves and never as one. This scan is a third party’s join of them, reduced in the joining. The archive now holds the original half-sheets from IGN, at full resolution and unaltered.'
      )}
    </p>
    <ul>
      {#each ordered as row (row.id)}
        <li>
          {#if href(row)}
            <a href={href(row)}>
              {row.name}{#if row.year}<span class="superseded-year">{row.year}</span>{/if}
            </a>
          {:else}
            <span class="superseded-unlinked">{row.name}</span>
          {/if}
          {#if part(row)}<span class="superseded-part">{$t(part(row))}</span>{/if}
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  .superseded {
    margin: 0;
    padding: var(--space-3);
    border: var(--border-thin);
    border-radius: var(--radius-md);
    background: var(--color-gray-50);
    text-align: left;
  }
  .superseded h2 {
    margin: 0 0 var(--space-2);
    font-size: var(--text-base);
  }
  .superseded p {
    margin: 0 0 var(--space-2);
    font-size: var(--text-sm);
    color: var(--color-gray-500);
  }
  .superseded ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-2);
  }
  .superseded li {
    display: flex;
    align-items: baseline;
    gap: var(--space-1);
  }
  .superseded a {
    display: inline-block;
    padding: 2px var(--space-2);
    border: var(--border-thin);
    border-radius: var(--radius-pill);
    background: var(--color-white);
    color: inherit;
    font-size: var(--text-sm);
    text-decoration: none;
  }
  .superseded a:hover {
    background: var(--color-gray-50);
  }
  .superseded-year {
    margin-left: var(--space-1);
    color: var(--color-gray-500);
  }
  .superseded-part,
  .superseded-unlinked {
    font-size: var(--text-xs);
    color: var(--color-gray-500);
  }
</style>
