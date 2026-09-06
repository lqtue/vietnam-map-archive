<!--
  Sheet — the one layout primitive.

  A printed map sheet puts its content inside a NEATLINE and everything that
  describes that content — title cartouche, scale bar, legend — in the MARGIN
  around it. This component is that arrangement, and every page is one:
  an article is a field, a map is a field.

  Visual layer is $styles/sheet.css. This file only decides which slots exist.

    <Sheet title="Archive" meta="1859–1975">…</Sheet>
    <Sheet variant="tool" title="Explore"><MapShell/></Sheet>
-->
<script lang="ts">
  /** 'page' pads and scrolls the field. 'tool' hands the field to a map. */
  export let variant: 'page' | 'tool' = 'page';
  /** Faint coordinate grid behind the margin. Home page only. */
  export let graticule = false;
  /** Cartouche text, top-left of the margin. */
  export let title = '';
  /** Scale-bar slot, bottom-right of the margin. Years, counts, extents. */
  export let meta = '';
</script>

<div class="sheet" class:sheet--tool={variant === 'tool'} class:sheet--graticule={graticule}>
  <div class="sheet__margin">
    <div class="sheet__cartouche">
      {#if title}<span>{title}</span>{/if}
      <slot name="cartouche" />
    </div>
    <div class="sheet__scale">
      <slot name="margin-top-right" />
    </div>
  </div>

  <div class="sheet__field">
    {#if variant === 'page'}
      <div class="sheet__body"><slot /></div>
    {:else}
      <slot />
    {/if}
  </div>

  <div class="sheet__margin">
    <div class="sheet__cartouche">
      <slot name="margin-bottom-left" />
    </div>
    <div class="sheet__scale">
      {#if meta}<span>{meta}</span>{/if}
      <slot name="scale" />
    </div>
  </div>
</div>
