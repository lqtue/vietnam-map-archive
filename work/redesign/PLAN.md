# Sheet — redesign, done

Direction: neatline / margin / field, paper + darkroom surfaces, survey cyan,
Spectral / Be Vietnam Pro / IBM Plex Mono. Fifteen route surfaces became six.

| # | Phase | State |
|---|-------|-------|
| P1 | tokens / base / sheet / primitives | done |
| P2 | self-host fonts, unblock app.html | done |
| P3 | Sheet.svelte + NavBar + layouts + hero | done |
| P4 | token sweep, 19 -> 3 breakpoints | done |
| P5 | routes 15 -> 6 + redirects | done |
| P6 | delete shim + dead CSS, docs, verify | done |

Verified: `check` 0/0 · `lint` 0 errors · `build` ok · `test` 87 passed.

Left standing on purpose:
- `.sb-btn` / `.tool-btn` / `.pill-btn` / `.sb-card` / `.tool-section` / `.sb-input`
  are aliased onto the primitives with `:is()`, not renamed across sixty files.
- `driver.js` stays: the tour is a spotlight cutout with store-driven
  auto-advance, not three native popovers.
- ~6,600 lines of page-scoped CSS under components/ layouts/ pages/. All of it
  reads role tokens now; none of it was deleted. That is a second project.
