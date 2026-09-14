<script lang="ts">
  import { t } from '$lib/core/i18n';
</script>

<!--
  EditorialFooter.svelte — Single source of truth footer for all editorial pages.
  Uses .editorial-footer styles from editorial.css (loaded via global.css).
-->
<footer class="editorial-footer">
  <div class="footer-inner">
    <div class="footer-links">
      <a href="/">{$t('Home')}</a>
      <a href="/catalog">{$t('Catalog')}</a>
      <a href="/explore">{$t('Map viewer')}</a>
      <a href="/contribute">{$t('Contribute')}</a>
      <a href="/about">{$t('About')}</a>
      <a href="/blog">{$t('Blog')}</a>
      <a href="/changelog">{$t('Version history')}</a>
      <a href="/directory">{$t('All pages')}</a>
      <a href="https://github.com/lqtue/vietnam-map-archive" target="_blank" rel="noopener"
        >GitHub</a
      >
    </div>
    <p>
      {$t('Built openly with')}
      <a href="https://allmaps.org" target="_blank" rel="noopener">Allmaps</a>,
      <a href="https://openlayers.org" target="_blank" rel="noopener">OpenLayers</a>, &amp;
      <a href="https://svelte.dev" target="_blank" rel="noopener">SvelteKit</a>.
    </p>
    <p><a href="mailto:vietnamma.project@gmail.com">vietnamma.project@gmail.com</a></p>
  </div>
</footer>
