<!--
  ReviewGate.svelte — the review pages are staff only for now (plan §2.8; v2 opens them to signed-in
  users). The API is the real gate: it refuses anyone who is not admin or mod, with MFA. This only
  says why a page is empty instead of showing a broken one.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchUserRole } from '$lib/data/supabase/role';
  import AuthGate from '$lib/ui/AuthGate.svelte';

  const { session, supabase } = getSupabaseContext();

  let role: string | null = null;
  let checked = false;

  onMount(async () => {
    role = await fetchUserRole(supabase, session?.user?.id);
    checked = true;
  });

  $: staff = role === 'admin' || role === 'mod';
</script>

{#if !session?.user}
  <AuthGate
    {supabase}
    title="Sign in to review"
    body="The review pages are open to staff while the first test runs."
  />
{:else if !checked}
  <p class="note" aria-busy="true">Checking your access…</p>
{:else if !staff}
  <p class="note">The review pages are for staff while the first test runs.</p>
{:else}
  <slot />
{/if}

<style>
  .note {
    padding: var(--space-8);
  }
</style>
