<!--
  ReviewViews.svelte — the plain crops of one item, each with the task's overlay drawn over it.

  The clock starts when the last `<img>` has loaded (`session.viewLoaded`); a crop that fails to
  load stops the item with Retry instead of letting a timer run on a blank view. The views are
  fixed in size by the method and scaled down together only when the window is narrower than both,
  which is why they are plain `<img>`s with a width and no pan or zoom (plan §2: zoom changes the
  measured condition; "Open sheet" is the way out).
-->
<script lang="ts">
  import type { ComponentType, SvelteComponent } from 'svelte';
  import type { ReviewSession } from './reviewSession';
  import type { OverlayProps, ReviewItem } from './types';

  export let session: ReviewSession;
  export let item: ReviewItem;
  export let picked: number | null = null;
  /** The task's overlay component, drawn in each view's own pixel units. */
  export let overlay: ComponentType<SvelteComponent<OverlayProps>>;

  /** The ground the view covers, to the nearest 10 m. */
  const across = (side: number, mPerPx: number) => Math.round((side * mPerPx) / 10) * 10;

  const VIEWS = [
    { key: 'close', label: 'Close' },
    { key: 'context', label: 'Context' },
  ] as const;
</script>

<div class="views">
  {#each VIEWS as v (`${item.item_id}:${v.key}`)}
    {@const view = item.payload.views[v.key]}
    <figure style:--out={view.out}>
      <figcaption>
        {v.label} · about {across(view.side, item.payload.sheet.m_per_px)} m across
      </figcaption>
      <div class="frame">
        <img
          src={view.url}
          width={view.out}
          height={view.out}
          alt="{v.label} view of the label “{item.payload.text}” on the 1882 sheet"
          on:load={() => session.viewLoaded(VIEWS.length)}
          on:error={() => session.viewFailed()}
        />
        <svelte:component
          this={overlay}
          {view}
          payload={item.payload}
          candidates={item.proposal}
          {picked}
        />
      </div>
    </figure>
  {/each}
</div>

<style>
  .views {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    align-items: flex-start;
  }
  figure {
    margin: 0;
    max-width: 100%;
  }
  figcaption {
    font-size: var(--text-xs);
    color: var(--color-gray-500);
    margin-bottom: var(--space-1);
  }
  .frame {
    position: relative;
    width: calc(var(--out) * 1px);
    max-width: 100%;
    border: var(--border-thin) solid var(--color-border);
  }
  img {
    display: block;
    width: 100%;
    height: auto;
  }
</style>
