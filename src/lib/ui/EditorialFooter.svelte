<!--
  EditorialFooter.svelte — the colophon.

  Bottom of the field, not the margin: it is a block of text with links in it,
  and the margin is for one line of annotation. Ruled off above, set at the
  small end of the scale.
-->
<footer class="colophon is-wide">
  <nav class="colophon__links" aria-label="Footer">
    <a href="/">Home</a>
    <a href="/archive">Archive</a>
    <a href="/explore">Explore</a>
    <a href="/scan">Scan</a>
    <a href="/contribute">Contribute</a>
    <a href="/about">About</a>
    <a href="/blog">Blog</a>
    <a href="https://github.com/lqtue/svelte-beta" target="_blank" rel="noopener">GitHub</a>
  </nav>

  <p>
    Built openly with
    <a href="https://allmaps.org" target="_blank" rel="noopener">Allmaps</a>,
    <a href="https://openlayers.org" target="_blank" rel="noopener">OpenLayers</a>
    and
    <a href="https://svelte.dev" target="_blank" rel="noopener">SvelteKit</a>.
  </p>

  <p><a href="mailto:vietnamma.project@gmail.com">vietnamma.project@gmail.com</a></p>
</footer>

<style>
  .colophon {
    margin-top: var(--s-6);
    padding-top: var(--s-4);
    border-top: var(--rule-hair) solid var(--rule);

    font-family: var(--font-mono);
    font-size: var(--t-2xs);
    letter-spacing: 0.04em;
    color: var(--ink-soft);
  }

  .colophon__links {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-2) var(--s-4);
    margin-bottom: var(--s-3);
    text-transform: uppercase;
  }

  .colophon p {
    margin: 0 0 var(--s-1);
    max-width: none;
  }

  .colophon a:hover {
    color: var(--accent);
  }
</style>
