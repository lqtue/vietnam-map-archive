/**
 * Query-state vocabulary for the two route dispatchers that do not have a
 * separate page per screen. Keeping it here lets the server repair a pasted
 * URL and lets the client render the same safe fallback during app navigation.
 */

export const EXPLORE_MODES = ['browse', 'studio', 'story'] as const;
export type ExploreMode = (typeof EXPLORE_MODES)[number];

const EXPLORE_MODE_ALIASES: Record<string, ExploreMode> = { annotate: 'studio' };

/** `null` means a misspelling, not Browse. */
export function resolveExploreMode(raw: string | null | undefined): ExploreMode | null {
  if (!raw) return raw === null || raw === undefined ? 'browse' : null;
  if ((EXPLORE_MODES as readonly string[]).includes(raw)) return raw as ExploreMode;
  return EXPLORE_MODE_ALIASES[raw] ?? null;
}

export const ADMIN_TABS = ['bulk', 'scout', 'status', 'stories'] as const;
export type AdminTab = (typeof ADMIN_TABS)[number];

/** Status is the safe landing screen: it is read-only and available to mods. */
export const DEFAULT_ADMIN_TAB: AdminTab = 'status';

export function resolveAdminTab(raw: string | null | undefined): AdminTab {
  return (ADMIN_TABS as readonly string[]).includes(raw ?? '')
    ? (raw as AdminTab)
    : DEFAULT_ADMIN_TAB;
}
