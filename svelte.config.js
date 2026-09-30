import adapter from '@sveltejs/adapter-cloudflare';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  // Consult https://svelte.dev/docs/kit/integrations
  // for more information about preprocessors
  preprocess: vitePreprocess(),

  kit: {
    // SvelteKit nonces its SSR scripts (including the bootstrap); a fixed
    // response header cannot safely describe them. Allmaps needs eval for its
    // runtime transformer and a blob worker for warped tiles.
    csp: {
      mode: 'auto',
      directives: {
        'default-src': ['self'],
        'script-src': ['self', 'unsafe-eval'],
        'style-src': ['self', 'unsafe-inline'],
        'img-src': ['self', 'data:', 'blob:', 'https:'],
        'connect-src': ['self', 'https:'],
        'font-src': ['self'],
        'worker-src': ['self', 'blob:'],
        'child-src': ['blob:'],
        'frame-ancestors': ['none'],
        'base-uri': ['self'],
        'object-src': ['none'],
      },
    },
    // adapter-auto only supports some environments, see https://svelte.dev/docs/kit/adapter-auto for a list.
    // If your environment is not supported, or you settled on a specific environment, switch out the adapter.
    // See https://svelte.dev/docs/kit/adapters for more information about adapters.
    adapter: adapter(),
    alias: {
      $styles: './src/styles',
    },
  },
};

export default config;
