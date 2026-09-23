// Shared by scripts/gcp_inverse_lookup.mjs and scripts/sheet_align.mjs.
// Pulled out because this got the editor link wrong once already (memory:
// `src/lib/core/iiif/annotationUrl.ts` still skips R2 sources on the
// assumption R2 is always a redundant mirror — false for at least six
// sheets) and duplicating the fix invites the same bug to drift back in.
//
// The rule: trust the annotation's OWN `target.source.id` over any
// source_type heuristic. That id is the scan the GCPs were actually placed
// on; guessing from source_type is what broke the in-app Editor link.

const EDITOR_BASE = 'https://editor.allmaps.org/#/collection?url=';
const withInfoJson = (u) => (/\.json($|\?)/.test(u) ? u : `${u.replace(/\/$/, '')}/info.json`);

/** Best-effort link when the annotation hasn't been fetched yet, or has no usable target. */
export function editorUrlFallback(row) {
  if (row.iiif_manifest) return EDITOR_BASE + encodeURIComponent(withInfoJson(row.iiif_manifest));
  const original = row.map_iiif_sources?.find((s) => s.source_type !== 'r2' && s.iiif_image)?.iiif_image;
  if (original) return EDITOR_BASE + encodeURIComponent(withInfoJson(original));
  if (!row.annotation_url && row.allmaps_id)
    return EDITOR_BASE + encodeURIComponent(`https://annotations.allmaps.org/images/${row.allmaps_id}`);
  return null;
}

/** The verified link: whichever source's iiif_image the annotation is ACTUALLY fit to. */
export function editorUrlFromAnnotation(row, sourceId) {
  if (!sourceId) return null;
  const stripInfoJson = (u) => u.replace(/\/info\.json$/, '');
  const match = row.map_iiif_sources?.find(
    (s) => s.iiif_image && stripInfoJson(sourceId) === stripInfoJson(s.iiif_image)
  );
  return match ? EDITOR_BASE + encodeURIComponent(withInfoJson(match.iiif_image)) : null;
}

/** Verified link if possible, fallback otherwise, plus whether it was verified. */
export function editorLinkFor(row, sourceId) {
  const verified = editorUrlFromAnnotation(row, sourceId);
  if (verified) return { url: verified, verified: true };
  return { url: editorUrlFallback(row), verified: false };
}
