<script lang="ts">
  import { t, locale, setLocale, splitHighlight } from '$lib/core/i18n';
  import { onMount } from 'svelte';
  import { getSupabaseContext } from '$lib/data/supabase/context';
  import { fetchUserRole } from '$lib/data/supabase/role';
  import PageHero from '$lib/ui/PageHero.svelte';
  import type { PageData } from './$types';
  import '$styles/pages/profile.css';

  $: heroTitle = splitHighlight($t('Your **profile.**'));

  export let data: PageData;
  const { supabase } = getSupabaseContext();

  // From this page's own load, which redirects when there is no session — so
  // this is the getUser()-validated user and it cannot be null.
  const user = data.user;
  const avatarUrl = user.user_metadata?.avatar_url;
  const displayName = user.user_metadata?.full_name || user.email;
  const initials = displayName
    ? displayName
        .split(' ')
        .map((n: string) => n[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : '?';

  let role = 'user';
  let stats = { pins: 0, traces: 0, reviews: 0 };
  let loading = true;
  // No reload: `t` is a derived store, so every string on screen re-renders
  // the moment the locale changes.
  function toggleLanguage() {
    setLocale($locale === 'vi' ? 'en' : 'vi');
  }

  onMount(async () => {
    try {
      // 1. Get role
      role = (await fetchUserRole(supabase, user.id)) ?? role;

      // 2. Get counts
      const [pinsRes, tracesRes] = await Promise.all([
        supabase
          .from('label_pins')
          .select('*', { count: 'exact', head: true })
          .eq('user_id', user.id),
        supabase
          .from('footprints')
          .select('*', { count: 'exact', head: true })
          .eq('user_id', user.id),
      ]);

      stats = {
        pins: pinsRes.count || 0,
        traces: tracesRes.count || 0,
        reviews: 0,
      };
    } catch (e) {
      console.error('Failed to load profile stats:', e);
    } finally {
      loading = false;
    }
  });

  async function handleSignOut() {
    await supabase.auth.signOut();
    window.location.href = '/';
  }
</script>

<svelte:head>
  <title>Your profile — Vietnam Map Archive</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<div class="page profile-page">
  <PageHero eyebrow="Account" sub="Your contributions, your settings, in one place.">
    <svelte:fragment slot="title">
      {heroTitle[0]}{#if heroTitle[1]}<br /><span class="text-highlight">{heroTitle[1]}</span
        >{/if}{heroTitle[2]}
    </svelte:fragment>
  </PageHero>

  <main class="editorial-main">
    <div class="section-card profile-card">
      <div class="profile-header">
        <div class="avatar-large">
          {#if avatarUrl}
            <img src={avatarUrl} alt={displayName} />
          {:else}
            <span>{initials}</span>
          {/if}
        </div>
        <div class="profile-info">
          <h2 class="profile-name">{displayName}</h2>
          <p class="profile-email">{user.email}</p>
          <span class="role-badge" class:admin={role === 'admin'} class:mod={role === 'mod'}>
            {role.toUpperCase()}
          </span>
        </div>
        <button class="btn" on:click={handleSignOut}>{$t('Sign out')}</button>
      </div>

      <div class="stats-section">
        <h3 class="section-title">{$t('Your contributions')}</h3>
        {#if loading}
          <div class="loading-pulse">{$t('Counting…')}</div>
        {:else}
          <div class="stats-grid">
            <div class="stat-tile">
              <span class="value">{stats.pins}</span>
              <span class="label">{$t('Pins placed')}</span>
            </div>
            <div class="stat-tile">
              <span class="value">{stats.traces}</span>
              <span class="label">{$t('Buildings traced')}</span>
            </div>
          </div>
        {/if}
      </div>

      {#if role === 'admin' || role === 'mod'}
        <div class="settings-section">
          <h3 class="section-title">{$t('Staff tools')}</h3>
          <p class="staff-blurb">
            {$t(
              'Pages only staff can open. Start at System status — it says what the archive holds and what is currently blocked.'
            )}
          </p>
          <div class="staff-links">
            <a class="btn" href="/admin?tab=status">System status</a>
            <a class="btn" href="/screens">{$t('Design system')}</a>
            <a class="btn" href="/scan?mode=shapes&amp;tab=validate">{$t('Review queue')}</a>
            <a class="btn" href="/admin?tab=scout">Scout review</a>
            <a class="btn" href="/admin?tab=bulk">Bulk upload</a>
          </div>
        </div>
      {/if}

      <div class="settings-section">
        <h3 class="section-title">{$t('Preferences')}</h3>
        <div class="settings-grid">
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-name">{$t('Language')}</span>
              <span class="setting-desc"
                >{$t('Switch between English and Tiếng Việt — translation is beta')}</span
              >
            </div>
            <button class="chip is-primary" on:click={toggleLanguage}>
              {$locale === 'vi' ? '🇬🇧 English' : '🇻🇳 Tiếng Việt'}
            </button>
          </div>
        </div>
      </div>
    </div>
  </main>
</div>
