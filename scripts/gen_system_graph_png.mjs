// Rasterise the system-graph SVGs in docs/ to PNGs (light theme, 2x) with the Playwright Chromium
// the test suite already uses. Run after scripts/gen_system_graph.py and gen_system_graph_technical.py.
import { chromium } from '@playwright/test';
import { readFileSync } from 'node:fs';

const browser = await chromium.launch();
for (const name of ['system-graph', 'system-graph-technical']) {
  const svg = readFileSync(`docs/${name}.svg`, 'utf8');
  const width = Number(/viewBox="0 0 (\d+)/.exec(svg)[1]);
  const page = await browser.newPage({
    colorScheme: 'light',
    deviceScaleFactor: 2,
    viewport: { width, height: 1200 },
  });
  await page.setContent(`<body style="margin:0">${svg}</body>`);
  await page.locator('svg').screenshot({ path: `docs/${name}.png` });
}
await browser.close();
