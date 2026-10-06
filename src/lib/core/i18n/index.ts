import { derived, get, writable } from 'svelte/store';
import { vi } from './vi';
import { CATALOG_AREAS } from '../catalogAreas';

export type Locale = 'en' | 'vi';

export const LOCALE_COOKIE = 'vma-lang';

const DICTS: Record<Locale, Record<string, string>> = { en: {}, vi };

/**
 * The chosen locale. Two states, not three — English is the source, Vietnamese
 * is the translation, and there is no "follow the browser": a reader who wants
 * Vietnamese picks it once and the cookie remembers.
 *
 * This is module state, which on the server is shared by every request in the
 * isolate. It is safe because `+layout.svelte` sets it synchronously at
 * component init and Svelte's SSR render is synchronous end to end — there is
 * no await between the set and the reads it feeds, so two concurrent requests
 * cannot interleave inside one render.
 */
export const locale = writable<Locale>('en');

/** A value still loading is blank, never the word "null". */
export type TVars = Record<string, string | number | null | undefined>;

function interpolate(s: string, vars?: TVars): string {
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (m, k) =>
    k in vars ? (vars[k] == null ? '' : String(vars[k])) : m
  );
}

function translate(l: Locale, en: string, vars?: TVars): string {
  return interpolate(DICTS[l][en] ?? en, vars);
}

/**
 * `{$t('Save')}` in a template, `$t('{N} stops', { N: 4 })` with values.
 *
 * The key IS the English string: there is no key vocabulary to invent, drift
 * from, or look up, and an untranslated string renders as itself rather than
 * as `home.hero.title`. The cost is that editing English copy orphans its
 * translation — `npm run i18n:check` lists those.
 */
export const t = derived(
  locale,
  ($l) =>
    (en: string, vars?: TVars): string =>
      translate($l, en, vars)
);

/** Non-reactive read, for the places a store subscription cannot reach. */
export function tr(en: string, vars?: TVars): string {
  return translate(get(locale), en, vars);
}

export function isLocale(v: unknown): v is Locale {
  return v === 'en' || v === 'vi';
}

/** Reads the cookie the server also reads, for the `ssr = false` tool routes. */
export function localeFromCookie(cookie: string): Locale {
  const m = /(?:^|;\s*)vma-lang=(en|vi)/.exec(cookie);
  return m ? (m[1] as Locale) : 'en';
}

/** Picks a locale and remembers it. One year, path `/`, no reload needed. */
export function setLocale(next: Locale): void {
  locale.set(next);
  if (typeof document !== 'undefined') {
    document.cookie = `${LOCALE_COOKIE}=${next};path=/;max-age=31536000;samesite=lax`;
    document.documentElement.lang = next;
  }
}

/**
 * A hero title is one sentence with its second half lit: `Old maps of
 * Vietnam,` then `put back in place.` in `.text-highlight`. Keying the two
 * halves separately would hand a translator "together." on its own, which is
 * not a translatable unit — so the key is the whole sentence and `**` marks
 * the run to light up. Vietnamese word order can put it anywhere.
 *
 * Returns `[before, highlight, after]`; with no marker the whole string is
 * `before`, which is what an untranslated or unmarked title renders as.
 */
export function splitHighlight(s: string): [string, string, string] {
  const m = /^([\s\S]*?)\*\*([\s\S]+?)\*\*([\s\S]*)$/.exec(s);
  return m ? [m[1], m[2], m[3]] : [s, '', ''];
}

/**
 * The paths that exist in both languages, and so the paths that get a `/vi`
 * twin, an `hreflang` pair and a sitemap entry each.
 *
 * Everything else — a map record, a place name, a blog post — is one document
 * written in one language with only the chrome around it translated. A `/vi`
 * twin of those would be the same page again, which is a duplicate to answer
 * for rather than a translation to rank.
 *
 * `sitemap.xml` enumerates exactly this list, which is why it lives here
 * rather than beside either caller.
 */
export const LOCALIZED_PATHS = [
  '/',
  '/catalog',
  '/about',
  '/blog',
  '/changelog',
  '/contribute',
  '/contribute/georef',
  '/directory',
];

/** Translated collections are enumerated separately: only populated areas enter the sitemap. */
export function isLocalizedPath(path: string): boolean {
  return (
    LOCALIZED_PATHS.includes(path) ||
    CATALOG_AREAS.some((area) => path === `/catalog/area/${area.slug}`)
  );
}

/** `/vi/about` → `/about`, `/vi` → `/`. Any other path is returned unchanged. */
export function stripLocale(pathname: string): string {
  if (pathname === '/vi') return '/';
  return pathname.startsWith('/vi/') ? pathname.slice(3) : pathname;
}

/** `/about` → `/vi/about`, `/` → `/vi`. Assumes the path carries no locale. */
export function withLocale(pathname: string): string {
  return pathname === '/' ? '/vi' : `/vi${pathname}`;
}

/**
 * The locale a URL pins, or null when it pins none.
 *
 * A cookie cannot be the only answer: a crawler sends none, so before this
 * existed every request from Google resolved to English and the Vietnamese
 * half of the site had no address to index.
 */
export function localeFromPath(pathname: string): Locale | null {
  return pathname === '/vi' || pathname.startsWith('/vi/') ? 'vi' : null;
}
