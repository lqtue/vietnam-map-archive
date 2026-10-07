/** Who holds what: the institution registry, small enough for any page to import. */

export interface Institution {
  slug: string;
  /** The `cell_printings.institution` code; null for a holder known only from `maps.holding_institution`. */
  code: string | null;
  name: string;
  /** A name short enough for a row of links; the full name where none is set. */
  short?: string;
  url: string | null;
  about: string | null;
  /** Every other `maps.holding_institution` spelling that means this institution. */
  aliases: string[];
}

export const KNOWN: Institution[] = [
  {
    slug: 'pcl',
    short: 'Perry-Castañeda Library',
    code: 'PCL',
    name: 'Perry-Castañeda Library Map Collection, University of Texas at Austin',
    url: 'https://maps.lib.utexas.edu/maps/vietnam.html',
    about: 'Scans of US Army Map Service sheets, published online as JPGs and GeoPDFs.',
    aliases: [],
  },
  {
    slug: 'ttu',
    short: 'Texas Tech Vietnam Archive',
    code: 'TTU',
    name: 'Vietnam Center and Sam Johnson Vietnam Archive, Texas Tech University',
    url: 'https://www.vietnam.ttu.edu/resources/maps/',
    about:
      'The Virtual Vietnam Archive map collection, often a different printing from the PCL copy.',
    aliases: ['Texas Tech'],
  },
  {
    slug: 'usgs',
    short: 'USGS Store',
    code: 'USGS',
    name: 'U.S. Geological Survey Store (NGA maps)',
    url: 'https://store.usgs.gov/',
    about:
      "Free PDFs of the National Geospatial-Intelligence Agency's Vietnam sheets, most of them GeoPDFs.",
    aliases: [],
  },
  {
    slug: 'anu',
    short: 'ANU',
    code: 'ANU',
    name: 'Australian National University',
    url: 'https://openresearch-repository.anu.edu.au/',
    about: null,
    aliases: ['ANU'],
  },
  {
    slug: 'ign',
    short: 'IGN',
    code: 'IGN',
    name: "IGN (Institut national de l'information géographique et forestière)",
    url: 'https://www.ign.fr/',
    about: null,
    aliases: [],
  },
  {
    slug: 'princeton',
    short: 'Princeton University Library',
    code: 'Princeton',
    name: 'Princeton University Library',
    url: 'https://maps.princeton.edu/',
    about: null,
    aliases: [],
  },
];

/** Platforms, not holders: credited in the index page's platform list instead. */
export const PLATFORM = /^(Cartomundi|Wikimedia Commons)/i;

export function institutionSlug(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/gi, 'd')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

/** The institution a code or a `holding_institution` string names; an unknown value is its own entry. */
export function institutionFor(value: string): Institution {
  const v = value.trim();
  return (
    KNOWN.find((i) => i.code === v || i.name === v || i.aliases.includes(v)) ?? {
      slug: institutionSlug(v),
      code: null,
      name: v,
      url: null,
      about: null,
      aliases: [],
    }
  );
}

/** The page for a holding-institution string or code, or null for a platform, which has none. */
export function institutionHref(value: string | null | undefined): string | null {
  if (!value?.trim() || PLATFORM.test(value)) return null;
  return `/catalog/institutions/${institutionFor(value).slug}`;
}
