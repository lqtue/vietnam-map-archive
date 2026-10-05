<script lang="ts">
  import { t } from '$lib/core/i18n';
  import { createEventDispatcher } from 'svelte';
  import { layerDrag } from '$lib/map/shell/layerDrag';
  import { randomId } from '$lib/core/utils/id';
  export let name = 'layer';
  export let removable = false;
  export let drag: {
    id: string;
    onDrag: (id: string | null) => void;
    onMove: (id: string, targetId: string) => void;
  } | null = null;
  const dispatch = createEventDispatcher<{
    zoom: void;
    info: void;
    legend: void;
    remove: void;
    reorder: { direction: -1 | 1 };
  }>();
  function reorder(direction: -1 | 1) {
    menu.hidePopover();
    dispatch('reorder', { direction });
  }
  function keyboard(event: KeyboardEvent) {
    if (!drag || (event.key !== 'ArrowUp' && event.key !== 'ArrowDown')) return;
    event.preventDefault();
    dispatch('reorder', { direction: event.key === 'ArrowUp' ? -1 : 1 });
  }
  const menuId = randomId('layer-menu');
  let menu: HTMLElement;

  function positionPopover(node: HTMLElement) {
    menu = node;
    const trigger = node.previousElementSibling as HTMLButtonElement;
    let frame = 0;
    function position() {
      if (!node.matches(':popover-open')) return;
      const rect = trigger.getBoundingClientRect();
      const gap = parseFloat(getComputedStyle(node).fontSize) / 2;
      const viewport = window.visualViewport;
      const left = viewport?.offsetLeft ?? 0;
      const top = viewport?.offsetTop ?? 0;
      const width = viewport?.width ?? window.innerWidth;
      const height = viewport?.height ?? window.innerHeight;
      node.style.setProperty('--menu-max-width', `${Math.max(0, width - gap * 2)}px`);
      node.style.setProperty('--menu-max-height', `${Math.max(0, height - gap * 2)}px`);
      const menuRect = node.getBoundingClientRect();
      const below = top + height - rect.bottom - gap * 2;
      const above = rect.top - top - gap * 2;
      const opensAbove = menuRect.height > below && above > below;
      const available = Math.max(0, opensAbove ? above : below);
      node.style.setProperty('--menu-max-height', `${available}px`);
      const menuHeight = Math.min(menuRect.height, available);
      const x = Math.max(
        left + gap,
        Math.min(rect.right - menuRect.width, left + width - menuRect.width - gap)
      );
      const y = opensAbove ? rect.top - gap - menuHeight : rect.bottom + gap;
      node.style.setProperty('--menu-left', `${x}px`);
      node.style.setProperty('--menu-top', `${Math.max(top + gap, y)}px`);
      node.style.visibility = 'visible';
    }
    function beforeToggle(event: Event) {
      cancelAnimationFrame(frame);
      if ((event as ToggleEvent).newState === 'open') {
        node.style.visibility = 'hidden';
        frame = requestAnimationFrame(position);
      }
    }
    function toggle() {
      position();
    }
    function scroll(event: Event) {
      if (!node.contains(event.target as Node) && node.matches(':popover-open')) node.hidePopover();
    }
    node.addEventListener('beforetoggle', beforeToggle);
    node.addEventListener('toggle', toggle);
    document.addEventListener('scroll', scroll, true);
    window.addEventListener('resize', position);
    window.visualViewport?.addEventListener('resize', position);
    window.visualViewport?.addEventListener('scroll', position);
    return {
      destroy() {
        cancelAnimationFrame(frame);
        node.removeEventListener('beforetoggle', beforeToggle);
        node.removeEventListener('toggle', toggle);
        document.removeEventListener('scroll', scroll, true);
        window.removeEventListener('resize', position);
        window.visualViewport?.removeEventListener('resize', position);
        window.visualViewport?.removeEventListener('scroll', position);
      },
    };
  }
  function choose(action: 'zoom' | 'info' | 'legend' | 'remove') {
    menu.hidePopover();
    dispatch(action);
  }
</script>

<div class="layer-menu">
  <button
    type="button"
    class="sb-btn is-icon"
    use:layerDrag={drag}
    on:keydown={keyboard}
    class:can-drag={!!drag}
    popovertarget={menuId}
    aria-label="Actions for {name}"
    title="Layer actions">⋯</button
  >
  <div id={menuId} popover="auto" class="layer-options" use:positionPopover>
    <button type="button" class="sb-btn is-ghost" on:click={() => choose('zoom')}>Zoom to</button>
    <button type="button" class="sb-btn is-ghost" on:click={() => choose('info')}
      >Display info</button
    >
    <button type="button" class="sb-btn is-ghost" on:click={() => choose('legend')}
      >Display legend</button
    >
    {#if drag}
      <section class="reorder-section" aria-label="Reorder layer">
        <p>Hold and drag the three dots to reorder.</p>
        <button type="button" class="sb-btn is-ghost" on:click={() => reorder(-1)}
          >{$t('Move up')}</button
        >
        <button type="button" class="sb-btn is-ghost" on:click={() => reorder(1)}
          >{$t('Move down')}</button
        >
      </section>
    {/if}
    {#if removable}<button type="button" class="sb-btn is-ghost" on:click={() => choose('remove')}
        >Remove layer</button
      >{/if}
  </div>
</div>

<style>
  .can-drag {
    touch-action: none;
  }
  .reorder-section {
    border-top: 1px solid var(--rule);
    display: flex;
    flex-direction: column;
  }
  .reorder-section p {
    margin: 0.35rem 0.5rem;
    font-size: 0.7rem;
    max-width: 25ch;
  }

  .layer-menu {
    flex-shrink: 0;
  }
  .layer-options {
    position: fixed;
    inset: auto;
    left: var(--menu-left, 0);
    top: var(--menu-top, 0);
    margin: 0;
    width: max-content;
    max-width: var(--menu-max-width, none);
    max-height: var(--menu-max-height, none);
    box-sizing: border-box;
    overflow: auto;
    flex-direction: column;
    padding: 0.25rem;
    background: var(--sb-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-sm);
  }
  .layer-options:popover-open {
    display: flex;
  }
  .layer-options button {
    justify-content: flex-start;
  }
</style>
