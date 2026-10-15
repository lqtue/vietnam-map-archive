<script lang="ts">
  import { t } from '$lib/core/i18n';
  import type { PageData } from './$types';
  import { CATEGORY_LABELS, CATEGORY_COLORS, posts } from '../posts';
  import '$styles/pages/blog-post.css';

  export let data: PageData;
  $: post = data.post;

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  }

  // Other posts for the sidebar (excluding current)
  $: otherPosts = posts
    .filter((p) => p.slug !== post.slug)
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    .slice(0, 3);
</script>

<svelte:head>
  <title>{post.title} — Vietnam Map Archive</title>
  <meta name="description" content={post.excerpt} />
</svelte:head>

<div class="page blog-post-page">
  <div class="layout">
    <!-- ARTICLE -->
    <article class="article">
      <header class="article-header">
        <a href="/blog" class="back-link">{$t('← All posts')}</a>
        <div class="article-meta">
          <span class="cat-chip" style="background: {CATEGORY_COLORS[post.category]}">
            {CATEGORY_LABELS[post.category]}
          </span>
          <time class="post-date">{formatDate(post.date)}</time>
        </div>
        <h1 class="article-title">{post.title}</h1>
        <p class="article-excerpt">{post.excerpt}</p>
        <div class="article-divider"></div>
      </header>

      {#if post.note}
        <aside class="article-note">
          <span class="note-label">{$t('Since this was written')}</span>
          <!-- Same trust boundary as post.content below: a committed module. -->
          <!-- eslint-disable-next-line svelte/no-at-html-tags -->
          <p>{@html post.note}</p>
        </aside>
      {/if}

      <div class="article-body">
        <!-- post.content comes from src/routes/(editorial)/blog/posts.ts, a
          committed module. No user input reaches this, so there is nothing to
          sanitise; if posts ever come from the database, this must change. -->
        <!-- eslint-disable-next-line svelte/no-at-html-tags -->
        {@html post.content}
      </div>

      <footer class="article-footer">
        <div class="footer-cta">
          <h3>{$t('Want to help?')}</h3>
          <p>
            {$t(
              'Every traced building, tagged photo, and cited source is permanently attributed in the archive.'
            )}
          </p>
          <div class="footer-cta-links">
            <a href="/contribute" class="btn is-lg is-primary">{$t('Start contributing')}</a>
            <a href="/about" class="btn is-lg">{$t('Read the project overview')}</a>
          </div>
        </div>
      </footer>
    </article>

    <!-- SIDEBAR -->
    <aside class="sidebar">
      <div class="section-card is-sm sidebar-card">
        <h3 class="sidebar-title">{$t('About the project')}</h3>
        <p class="sidebar-text">
          {$t(
            'Vietnam Map Archive puts old maps of Vietnam back in place, reads what is printed on them, and links each one to other maps and to the city today. Saigon is where the work goes deepest.'
          )}
        </p>
        <a href="/about" class="sidebar-link">{$t('Project overview')}</a>
      </div>

      {#if otherPosts.length > 0}
        <div class="section-card is-sm sidebar-card">
          <h3 class="sidebar-title">{$t('More posts')}</h3>
          <div class="other-posts">
            {#each otherPosts as p (p.slug)}
              <a href="/blog/{p.slug}" class="other-post">
                <span class="other-cat" style="background: {CATEGORY_COLORS[p.category]}"></span>
                <div class="other-post-info">
                  <span class="other-post-title">{p.title}</span>
                  <span class="other-post-date">{formatDate(p.date)}</span>
                </div>
              </a>
            {/each}
          </div>
        </div>
      {/if}

      <div class="section-card is-sm sidebar-card sidebar-contact">
        <h3 class="sidebar-title">{$t('Get in touch')}</h3>
        <p class="sidebar-text">{$t('Funder, researcher, volunteer, or just curious?')}</p>
        <a href="mailto:vietnamma.project@gmail.com" class="sidebar-link">
          vietnamma.project@gmail.com
        </a>
      </div>
    </aside>
  </div>
</div>
