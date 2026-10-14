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

// --- Plain hygiene ---

// LoC hands back protocol-relative permalinks (`//hdl.loc.gov/...`), which are
// a dead href anywhere the review UI renders them.
export function fixSourceUrl(rec) {
  const url = rec.sourceUrl || rec.source_url || '';
  return url.startsWith('//') ? `https:${url}` : url || null;
}
