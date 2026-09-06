/**
 * markerPalette.ts — colours + label font for the numbered story markers.
 *
 * OpenLayers styles are built in JS, so they can't use CSS variables directly.
 * We read the tokens off :root once per call and fall back to the literals the
 * markers used before the two marker layers were merged.
 */
export interface MarkerPalette {
  pending: string;
  current: string;
  done: string;
  border: string;
  label: string;
  font: string;
}

// Last-resort literals, used only during SSR / before the stylesheet lands.
// They mirror --sb-accent, --sb-accent-warm, --rule and --ground-raised;
// `done` green has no token of its own (see --marker-done above).
const FALLBACK: MarkerPalette = {
  pending: '#2563eb',
  current: '#f59e0b',
  done: '#16a34a',
  border: '#111111',
  label: '#ffffff',
  font: "'Space Grotesk', system-ui, sans-serif",
};

function cssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined' || typeof document === 'undefined') return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

export function markerPalette(): MarkerPalette {
  return {
    // `--marker-*` lets a theme override the markers on their own; without one
    // they track the sidebar accents, which is where the literals came from.
    pending: cssVar('--marker-pending', cssVar('--sb-accent', FALLBACK.pending)),
    current: cssVar('--marker-current', cssVar('--sb-accent-warm', FALLBACK.current)),
    done: cssVar('--marker-done', FALLBACK.done),
    border: cssVar('--rule', FALLBACK.border),
    label: cssVar('--ground-raised', FALLBACK.label),
    font: cssVar('--font-display', FALLBACK.font),
  };
}
