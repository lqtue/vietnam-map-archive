import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, type Plugin } from 'vite';
import { createReadStream, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Serve a locally built PMTiles archive in dev, with byte ranges.
 *
 * The mosaic is ~4.7 GB, so it cannot go in `static/` — that directory is copied
 * wholesale into the Pages bundle. Vite's own `/@fs/` route 403s it. And a
 * plain `python3 -m http.server` is no good either: it ignores `Range` and
 * answers 200 with the whole file, and PMTiles is nothing but range reads.
 *
 * Drop a build at `work/l7014/build/<name>.pmtiles` and it is readable at
 * `/local-pmtiles/<name>.pmtiles` while `npm run dev` is running. Dev only —
 * `apply: 'serve'` keeps it out of every build.
 */
function localPmtiles(): Plugin {
  const dir = fileURLToPath(new URL('./work/l7014/build', import.meta.url));
  return {
    name: 'vma-local-pmtiles',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/local-pmtiles', (req, res, next) => {
        const name = decodeURIComponent((req.url ?? '').split('?')[0]).replace(/^\//, '');
        // No traversal out of the build directory, and no serving anything but
        // an archive.
        if (!/^[\w.-]+\.pmtiles$/.test(name)) return next();
        const file = join(dir, name);
        let size: number;
        try {
          size = statSync(file).size;
        } catch {
          return next();
        }
        const m = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? '');
        const head = {
          'Content-Type': 'application/octet-stream',
          'Accept-Ranges': 'bytes',
          'Access-Control-Allow-Origin': '*',
        };
        if (!m) {
          res.writeHead(200, { ...head, 'Content-Length': String(size) });
          return createReadStream(file).pipe(res);
        }
        const start = m[1] ? Number(m[1]) : Math.max(0, size - Number(m[2]));
        const end = m[1] && m[2] ? Math.min(Number(m[2]), size - 1) : size - 1;
        if (start >= size || start > end) {
          res.writeHead(416, { ...head, 'Content-Range': `bytes */${size}` });
          return res.end();
        }
        res.writeHead(206, {
          ...head,
          'Content-Range': `bytes ${start}-${end}/${size}`,
          'Content-Length': String(end - start + 1),
        });
        createReadStream(file, { start, end }).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [sveltekit(), localPmtiles()],
  resolve: {
    alias: {
      // The app has no realtime subscriptions, but SupabaseClient's constructor
      // builds a RealtimeClient regardless, and the root layout creates that
      // client on every page. See the stub for the terms of the trade.
      '@supabase/realtime-js': fileURLToPath(
        new URL('./src/lib/data/supabase/realtimeStub.ts', import.meta.url)
      ),
    },
  },
  build: {
    // Optimize for production with esbuild (faster than terser)
    minify: 'esbuild',
    // Asset size limits
    chunkSizeWarningLimit: 1000,
    // Source maps for debugging (smaller inline maps)
    sourcemap: false,
    // CSS code splitting
    cssCodeSplit: true,
    // Asset inlining threshold
    assetsInlineLimit: 4096,
  },
  optimizeDeps: {
    // Pre-bundle dependencies
    include: ['ol', '@allmaps/openlayers'],
  },
});
