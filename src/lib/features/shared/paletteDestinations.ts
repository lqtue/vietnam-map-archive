/**
 * paletteDestinations.ts — every page the command palette can send you to.
 *
 * The list is here rather than derived from the route tree because a route is
 * not a destination: `/archive/[id]` needs an id, `/trip/[id]` needs a story, and
 * `/screens` is only interesting to whoever is building the UI. Keywords carry
 * the words people actually type — "viewer" for /explore, "ocr" for digitalize.
 *
 * `role` gates a row the same way the page does. Anything a signed-out visitor
 * cannot use is hidden rather than shown and then refused.
 */

export type PaletteRole = 'anyone' | 'member' | 'mod' | 'admin';

export interface Destination {
  href: string;
  label: string;
  hint: string;
  role: PaletteRole;
  keywords: string;
}

export const DESTINATIONS: Destination[] = [
  // Browse
  {
    href: '/archive',
    label: 'Catalog',
    hint: 'Every map, faceted',
    role: 'anyone',
    keywords: 'browse archive collection list search maps',
  },
  {
    href: '/explore',
    label: 'Map viewer',
    hint: 'Overlay historical maps on the city',
    role: 'anyone',
    keywords: 'explore view overlay layers basemap story play',
  },
  {
    href: '/scan',
    label: 'Scan inspector',
    hint: 'Read one sheet at full resolution',
    role: 'anyone',
    keywords: 'iiif zoom scan image viewer',
  },

  // Make
  {
    href: '/explore?mode=story',
    label: 'Story Builder',
    hint: 'Author a guided walk',
    role: 'member',
    keywords: 'story trip tour author write make',
  },
  {
    href: '/explore?mode=annotate',
    label: 'Studio',
    hint: 'Annotate and animate',
    role: 'member',
    keywords: 'annotate draw timeline animation',
  },

  // Contribute
  {
    href: '/contribute',
    label: 'Contribute',
    hint: 'The three jobs, and which suits you',
    role: 'anyone',
    keywords: 'help volunteer join tasks',
  },
  {
    href: '/contribute#georef',
    label: 'Georeference a map',
    hint: 'Pin a scan to the world',
    role: 'member',
    keywords: 'allmaps control points warp align',
  },
  {
    href: '/scan?mode=triage',
    label: 'Digitalize a sheet',
    hint: 'Triage, then review the OCR',
    role: 'member',
    keywords: 'ocr triage neatline tiles labels text',
  },
  {
    href: '/scan?mode=trace',
    label: 'Trace footprints',
    hint: 'Draw buildings and roads',
    role: 'member',
    keywords: 'polygon shape outline building road',
  },
  {
    href: '/scan?mode=review',
    label: 'Review queue',
    hint: 'Approve stories and footprints',
    role: 'mod',
    keywords: 'moderate approve reject submissions queue',
  },

  // Read
  {
    href: '/about',
    label: 'About',
    hint: 'What the project is',
    role: 'anyone',
    keywords: 'project mission team who',
  },
  {
    href: '/blog',
    label: 'Blog',
    hint: 'Research and build notes',
    role: 'anyone',
    keywords: 'posts writing updates news journal',
  },

  // Account and staff
  {
    href: '/profile',
    label: 'Your profile',
    hint: 'Account, favourites, staff pages',
    role: 'member',
    keywords: 'account me settings favourites',
  },
  {
    href: '/admin?tab=status',
    label: 'System status',
    hint: 'What the archive holds, what is stuck',
    role: 'mod',
    keywords: 'admin health jobs failures counts queue',
  },
  {
    href: '/admin?tab=bulk',
    label: 'Bulk upload',
    hint: 'Add sheets in a batch',
    role: 'admin',
    keywords: 'admin import upload csv new maps',
  },
  {
    href: '/admin?tab=scout',
    label: 'Scout',
    hint: 'Candidate maps from other collections',
    role: 'admin',
    keywords: 'admin candidates harvest gallica sources',
  },
  {
    href: '/screens',
    label: 'Design system',
    hint: 'Every token and component',
    role: 'admin',
    keywords: 'screens ui components tokens styleguide',
  },
];

const RANK: Record<PaletteRole, number> = { anyone: 0, member: 1, mod: 2, admin: 3 };

/** Destinations this visitor can actually use. */
export function destinationsFor(role: string | null, signedIn: boolean): Destination[] {
  const held: PaletteRole =
    role === 'admin' ? 'admin' : role === 'mod' ? 'mod' : signedIn ? 'member' : 'anyone';
  return DESTINATIONS.filter((d) => RANK[d.role] <= RANK[held]);
}

/**
 * Rank destinations against what was typed. A prefix match on the label beats a
 * word inside it, which beats a keyword — so typing "map" offers "Map viewer"
 * before "Bulk upload", whose keywords merely mention maps.
 */
export function matchDestinations(list: Destination[], q: string, limit = 6): Destination[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return list.slice(0, limit);
  const scored: { d: Destination; score: number }[] = [];
  for (const d of list) {
    const label = d.label.toLowerCase();
    let score = -1;
    if (label.startsWith(needle)) score = 0;
    else if (label.includes(needle)) score = 1;
    else if (d.href.toLowerCase().includes(needle)) score = 2;
    else if (d.keywords.includes(needle)) score = 3;
    else if (d.hint.toLowerCase().includes(needle)) score = 4;
    if (score >= 0) scored.push({ d, score });
  }
  scored.sort((a, b) => a.score - b.score || a.d.label.localeCompare(b.d.label));
  return scored.slice(0, limit).map((s) => s.d);
}
