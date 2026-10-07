<!--
  FavoriteButton — save / unsave one sheet. Renders nothing when signed out,
  unless `signInLink` asks for a "Sign in to save" link. `icon` is the compact
  heart-only form for a table row; the default is a labelled Save / Saved chip.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { t } from '$lib/core/i18n';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { favoriteIds, loadFavoriteIds, toggleFavorite } from './favoritesStore';

  export let mapId: string;
  export let icon = false;
  export let signInLink = false;

  const { supabase, session } = getSupabaseContext();
  const userId = session?.user?.id;

  onMount(() => {
    if (userId) loadFavoriteIds(supabase, userId);
  });

  $: saved = $favoriteIds.has(mapId);
  $: label = saved ? 'Remove from favorites' : 'Add to favorites';
</script>

{#if userId}
  {#if icon}
    <button
      type="button"
      class="btn is-icon is-xs"
      aria-pressed={saved}
      aria-label={label}
      title={label}
      on:click|stopPropagation={() => toggleFavorite(supabase, userId, mapId)}
    >
      <span class="notranslate">{saved ? '❤️' : '🤍'}</span>
    </button>
  {:else}
    <button
      type="button"
      class="chip act"
      aria-pressed={saved}
      aria-label={label}
      on:click={() => toggleFavorite(supabase, userId, mapId)}
    >
      <span class="notranslate">{saved ? '❤️' : '🤍'}</span>
      {saved ? $t('Saved') : $t('Save')}
    </button>
  {/if}
{:else if signInLink}
  <a class="btn" href="/login">{$t('Sign in to save')}</a>
{/if}
