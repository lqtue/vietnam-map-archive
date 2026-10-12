import {
  deriveManifestUrl,
  deriveImageUrl,
  deriveGallicaImage,
  fixSourceUrl,
} from './scoutDerive.mjs';
import assert from 'node:assert';

// Omeka S item URL → v2 manifest
assert.equal(
  deriveManifestUrl({ source_url: 'https://1886.u-bordeaux-montaigne.fr/s/1886/item/494060' }),
  'https://1886.u-bordeaux-montaigne.fr/iiif/494060/manifest'
);
assert.equal(
  deriveManifestUrl({ source_url: 'https://humazur.univ-cotedazur.fr/s/x/item/77' }),
  'https://humazur.univ-cotedazur.fr/iiif/77/manifest'
);
// A manifest we already have survives untouched
assert.equal(
  deriveManifestUrl({ source_url: 'https://gallica.bnf.fr/ark:/12148/btv1b1', manifest_url: 'M' }),
  'M'
);
// Non-numeric trailing segment must not become a manifest URL
assert.equal(
  deriveManifestUrl({ source_url: 'https://1886.u-bordeaux-montaigne.fr/s/1886/page/about' }),
  null
);

// LoC storage thumbnail → image service info.json
assert.equal(
  deriveImageUrl({
    thumbnail: 'https://tile.loc.gov/storage-services/service/gmd/gmd7/g7823/g7823g/ct003290.gif',
  }),
  'https://tile.loc.gov/image-services/iiif/service:gmd:gmd7:g7823:g7823g:ct003290/info.json'
);
// Already-IIIF thumbnail → same id, suffix trimmed
assert.equal(
  deriveImageUrl({
    thumbnail:
      'https://tile.loc.gov/image-services/iiif/service:asian:lcnclscd:2008623187:1A001:00001a/full/pct:6.25/0/default.jpg',
  }),
  'https://tile.loc.gov/image-services/iiif/service:asian:lcnclscd:2008623187:1A001:00001a/info.json'
);
// No thumbnail, or another host, yields nothing rather than a guess
assert.equal(deriveImageUrl({ thumbnail: '' }), null);
assert.equal(deriveImageUrl({ thumbnail: 'https://example.org/ark:/12148/x/f1.thumbnail' }), null);

// Gallica: the ark comes from whichever of source_url / manifest_url / thumbnail names it;
// the result is the image base (no info.json), page 1.
const MYTHO = 'https://gallica.bnf.fr/iiif/ark:/12148/btv1b8458472s/f1';
assert.equal(
  deriveGallicaImage({ source_url: 'https://gallica.bnf.fr/ark:/12148/btv1b8458472s' }),
  MYTHO
);
assert.equal(
  deriveGallicaImage({
    manifest_url: 'https://gallica.bnf.fr/iiif/ark:/12148/btv1b8458472s/manifest.json',
  }),
  MYTHO
);
assert.equal(
  deriveGallicaImage({ thumbnail: 'https://gallica.bnf.fr/ark:/12148/btv1b8458472s/f1.thumbnail' }),
  MYTHO
);
assert.equal(
  deriveGallicaImage({ sourceUrl: 'https://gallica.bnf.fr/ark:/12148/btv1b8458472s.item' }),
  MYTHO
);
// deriveImageUrl reaches it, and LoC still wins on its own host
assert.equal(
  deriveImageUrl({
    source: 'gallica',
    source_url: 'https://gallica.bnf.fr/ark:/12148/btv1b530577107',
  }),
  'https://gallica.bnf.fr/iiif/ark:/12148/btv1b530577107/f1'
);
// Omeka-backed federated hosts, other hosts, and a bare "ark" on a lookalike host derive nothing
assert.equal(
  deriveGallicaImage({ source_url: 'https://humazur.univ-cotedazur.fr/api/items/4054' }),
  null
);
assert.equal(
  deriveGallicaImage({ source_url: 'https://1886.u-bordeaux-montaigne.fr/s/1886/item/494060' }),
  null
);
assert.equal(
  deriveGallicaImage({ source_url: 'https://evil.example/gallica.bnf.fr/ark:/12148/x' }),
  null
);
assert.equal(
  deriveGallicaImage({ source_url: 'https://gallica.bnf.fr/services/engine/search' }),
  null
);
assert.equal(deriveGallicaImage({}), null);

// Protocol-relative permalinks get a scheme
assert.equal(
  fixSourceUrl({ source_url: '//hdl.loc.gov/loc.gmd/eadgmd.gm016002' }),
  'https://hdl.loc.gov/loc.gmd/eadgmd.gm016002'
);
assert.equal(
  fixSourceUrl({ source_url: 'https://www.loc.gov/item/1/' }),
  'https://www.loc.gov/item/1/'
);

console.log('scoutDerive: all assertions pass');
