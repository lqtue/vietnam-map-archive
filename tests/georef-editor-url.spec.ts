import { test, expect } from '@playwright/test';
import {
  allmapsEditorSourceUrl,
  allmapsTileUrl,
  ohmEditorUrl,
} from '../src/lib/core/iiif/annotationUrl';

// The editor opens a IIIF resource, not an annotation. Getting the source wrong
// is silent: it starts a blank map instead of loading the points already placed.
test('editor source prefers the manifest, and suffixes info.json', () => {
  // maps.iiif_manifest was dropped (mig 095) — the manifest now lives per
  // source, on map_images (was map_iiif_sources), so it arrives via `sources`.
  expect(allmapsEditorSourceUrl({}, [{ iiif_manifest: 'https://x/manifest' }])).toBe(
    'https://x/manifest/info.json'
  );
  expect(allmapsEditorSourceUrl({}, [{ iiif_manifest: 'https://x/manifest.json' }])).toBe(
    'https://x/manifest.json'
  );
});

test('an R2 mirror is skipped — its URL derives a different allmaps_id', () => {
  const sources = [
    { iiif_image: 'https://iiif.maparchive.vn/a', source_type: 'r2' },
    { iiif_image: 'https://gallica.bnf.fr/iiif/b', source_type: 'gallica' },
  ];
  expect(allmapsEditorSourceUrl({}, sources)).toBe('https://gallica.bnf.fr/iiif/b/info.json');
  expect(allmapsEditorSourceUrl({}, [sources[0]])).toBe('');
});

test('the annotation fallback takes no info.json — that URL 404s', () => {
  expect(allmapsEditorSourceUrl({ allmaps_id: 'abc123' })).toBe(
    'https://annotations.allmaps.org/images/abc123'
  );
  // A self-hosted annotation is not something the editor can open at all.
  expect(allmapsEditorSourceUrl({ allmaps_id: 'abc123', annotation_url: 'https://x/a.json' })).toBe(
    ''
  );
});

// iD's own hash parser, verbatim in behaviour: a pair is kept only when it
// splits into exactly two parts on '='. A raw tile template carries `?url=`,
// so it yields three and the background is dropped in silence.
function idStringQs(hash: string): Record<string, string> {
  let i = 0;
  while (i < hash.length && (hash[i] === '?' || hash[i] === '#')) i++;
  return hash
    .slice(i)
    .split('&')
    .reduce<Record<string, string>>((obj, pair) => {
      const parts = pair.split('=');
      if (parts.length === 2) obj[parts[0]] = decodeURIComponent(parts[1].trim());
      return obj;
    }, {});
}

test('the OHM editor link survives iD’s hash parser and round-trips the template', () => {
  const tiles = allmapsTileUrl('https://x.supabase.co/storage/v1/object/public/annotations/a.json');
  const url = ohmEditorUrl(tiles, [106.6862515, 10.7696121, 106.7139283, 10.7924709]);
  const q = idStringQs(new URL(url).hash);

  expect(new URL(url).searchParams.get('editor')).toBe('id');
  expect(q.background).toBe(`custom:${tiles}`);
  expect(q.map).toBe('14/10.78104/106.70009');

  // The unencoded form is the bug: three parts, so iD keeps nothing.
  expect(idStringQs(`#background=custom:${tiles}`).background).toBeUndefined();
});

test('no bbox means no map param — the editor keeps wherever it was', () => {
  const url = ohmEditorUrl(allmapsTileUrl('abc123'));
  expect(url).not.toContain('map=');
  expect(idStringQs(new URL(url).hash).background).toBe(
    'custom:https://allmaps.xyz/{z}/{x}/{y}.png?url=https%3A%2F%2Fannotations.allmaps.org%2Fimages%2Fabc123'
  );
});
