<!--
  Editorial pages: paper surface, page sheet.

  The layout owns the Sheet, so a page contributes content and nothing else —
  no header scaffold, no max-width, no footer. A page whose content must break
  the measure marks that block `.is-wide`.
-->
<script lang="ts">
  import { page } from '$app/stores';
  import Sheet from '$lib/ui/Sheet.svelte';
  import NavBar from '$lib/ui/NavBar.svelte';
  import EditorialFooter from '$lib/ui/EditorialFooter.svelte';
</script>

<div class="surface-paper">
  <Sheet meta="Saigon · Huế · Hà Nội">
    <svelte:fragment slot="cartouche">
      <NavBar session={$page.data.session} />
    </svelte:fragment>

    <slot />
    <EditorialFooter />
  </Sheet>
</div>
