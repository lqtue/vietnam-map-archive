// Per-source URL derivation for scout candidates.
//
// Shared by `load_scout_to_db.mjs` (new runs) and
// `oneoff/fix_scout_iiif.mjs` (the rows already in the table), so a source's
// pattern is written down once. Every function is pure: row in, string or null out.

// --- IIIF Presentation manifests ---

// Omeka S serves a v2 manifest at /iiif/{item_id}/manifest. Two federated
// Gallica-SRU sources are Omeka S instances, so their rows arrive with no
// manifest — the BnF ark pattern does not apply to them.
export const OMEKA_HOSTS = {
  'humazur.univ-cotedazur.fr': 'https://humazur.univ-cotedazur.fr',
  '1886.u-bordeaux-montaigne.fr': 'https://1886.u-bordeaux-montaigne.fr',
};

export function host(url) {
  try {
    return new URL(url).host;
  } catch {
    return '';
  }
}

// The Omeka item id is the last path segment of the item URL.
export function omekaItemId(url) {
  const id = String(url || '')
    .replace(/\/+$/, '')
    .split('/')
    .pop();
  return /^\d+$/.test(id) ? id : null;
}

export function deriveManifestUrl(rec) {
  const src = rec.sourceUrl || rec.source_url || '';
  const base = OMEKA_HOSTS[host(src)];
  if (base) {
    const id = omekaItemId(src);
    if (id) return `${base}/iiif/${id}/manifest`;
  }
  return rec.manifestUrl || rec.manifest_url || null;
}

// --- IIIF Image API ---

// The Library of Congress publishes no Presentation manifest we can reach —
// item pages sit behind a Cloudflare challenge — but its thumbnails name the
// image service, and that mapping is deterministic:
//   tile.loc.gov/storage-services/service/gmd/gmd7/g7823/g7823g/ct003290.gif
//     → tile.loc.gov/image-services/iiif/service:gmd:gmd7:g7823:g7823g:ct003290
// Already-IIIF thumbnails only need the image request suffix trimmed.
export function deriveImageUrl(rec) {
  return deriveLocImage(rec) || deriveGallicaImage(rec);
}

function deriveLocImage(rec) {
  const thumb = rec.thumbnail || '';
  const iiif = thumb.match(
    /^(https:\/\/tile\.loc\.gov\/image-services\/iiif\/[^/]+)\/[^/]+\/[^/]+\/[^/]+\/[^/]+$/
  );
  if (iiif) return `${iiif[1]}/info.json`;
  const stored = thumb.match(
    /^https:\/\/tile\.loc\.gov\/storage-services\/service\/(.+)\/([^/.]+)\.\w+$/
  );
  if (stored) {
    const id = `service:${stored[1].split('/').join(':')}:${stored[2]}`;
    return `https://tile.loc.gov/image-services/iiif/${id}/info.json`;
  }
  return null;
}

// Gallica rows carry a manifest and a thumbnail but no full-size image endpoint,
// so ingest would make a map the layout/OCR worker cannot read ("Map has no
// iiif_image"). Gallica serves its own IIIF Image API, keyed by the ark, and a
// single-sheet document is page 1:
//   gallica.bnf.fr/ark:/12148/btv1b8458472s/f1.thumbnail
//     → gallica.bnf.fr/iiif/ark:/12148/btv1b8458472s/f1
// The value is the image BASE, no `/info.json`: that is what the 1942 maps and every
// other Gallica `map_images` row hold, and the worker (`get_image_info`) and SheetZoom
// both append `/info.json` themselves. The ark is read off the row's own gallica.bnf.fr
// URLs, in order of how little they have been rewritten. The two Omeka-backed
// "gallica" federated hosts never have a gallica.bnf.fr URL and fall through to null.
const GALLICA_ARK = /^https:\/\/gallica\.bnf\.fr\/(?:iiif\/)?ark:\/12148\/([a-z0-9]+)(?:[/.?#]|$)/;

export function deriveGallicaImage(rec) {
  const src = rec.sourceUrl || rec.source_url || '';
  if (OMEKA_HOSTS[host(src)]) return null;
  for (const url of [src, rec.manifestUrl || rec.manifest_url, rec.thumbnail]) {
    const m = String(url || '').match(GALLICA_ARK);
    if (m) return `https://gallica.bnf.fr/iiif/ark:/12148/${m[1]}/f1`;
  }
  return null;
}

// --- Plain hygiene ---

// LoC hands back protocol-relative permalinks (`//hdl.loc.gov/...`), which are
// a dead href anywhere the review UI renders them.
export function fixSourceUrl(rec) {
  const url = rec.sourceUrl || rec.source_url || '';
  return url.startsWith('//') ? `https:${url}` : url || null;
}
