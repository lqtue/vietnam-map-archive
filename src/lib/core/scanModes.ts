/**
 * What `/scan?mode=` means — the one copy.
 *
 * Two readers need the same answer and must not drift: `hooks.server.ts`, which
 * redirects a request the shell no longer serves, and `(app)/scan/+page.svelte`,
 * which renders the one it does. A mode list that lived in the dispatcher alone
 * would make the redirect a second, silently diverging spelling of it.
 *
 * `inspect` is still here and is deliberately unlisted (Sept 2026). The public
 * read-only viewer is `/catalog/[id]` now — same tiles, plus the title, the
 * date, the places and a shareable URL — so nothing links to inspect any more.
 * It stays because a **draft** has no record page for anonymous readers and the
 * contribute modes all want a role; this is the plain look at an unpublished
 * scan that a signed-in volunteer can still reach by typing it.
 */

export const SCAN_MODES = ['inspect', 'prepare', 'text', 'shapes'] as const;
export type ScanMode = (typeof SCAN_MODES)[number];

/**
 * Old spellings, kept working rather than redirected: they are in bookmarks, in
 * the Tools menu people have memorised, and in the links /admin?tab=status
 * prints.
 */
const MODE_ALIASES: Record<string, ScanMode> = {
  triage: 'prepare',
  ocr: 'text',
  trace: 'shapes',
  review: 'shapes',
};

/**
 * `null` means "the shell has nothing for this" — a missing mode, or a spelling
 * that is neither a mode nor an alias. Both belong at /catalog now.
 *
 * Until Sept 2026 both fell through to inspect, which is public: a typo in the
 * mode name looked like it had worked and quietly showed the wrong surface.
 */
export function resolveScanMode(raw: string | null | undefined): ScanMode | null {
  if (!raw) return null;
  if ((SCAN_MODES as readonly string[]).includes(raw)) return raw as ScanMode;
  return MODE_ALIASES[raw] ?? null;
}
