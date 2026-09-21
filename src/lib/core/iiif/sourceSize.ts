/**
 * sourceSize.ts — does a IIIF endpoint serve the image an annotation was drawn on?
 *
 * A georeference annotation carries its control points and mask in the pixel grid
 * of one particular scan. Nothing in the JSON says which file that was beyond the
 * source URL and a width/height, so pointing the URL at a different scan of the
 * same sheet is a silent, whole-sheet georeference error.
 */

/** The pixel size the annotation says its `resourceCoords` and mask are in. */
export function declaredSourceSize(annotation: any): { width: number; height: number } | null {
  const items: any[] =
    annotation?.type === 'Annotation'
      ? [annotation]
      : (annotation?.items ?? annotation?.maps ?? []);
  for (const item of items) {
    const source = item?.target?.source;
    if (typeof source?.width === 'number' && typeof source?.height === 'number') {
      return { width: source.width, height: source.height };
    }
  }
  return null;
}

/**
 * `annotationMirror` rewrites an annotation's IIIF URL with a string replace: it
 * leaves `width`/`height`, every `resourceCoords` and the SvgSelector mask alone.
 * Point that at an R2 copy that is a *rescan* and the annotation claims one pixel
 * grid while the server serves another — a silent georeference error the size of
 * the scale ratio (2x on the 1942 sheet).
 *
 * We refuse rather than rescale. The rescan is not a pure scale of the original:
 * on 1942 the relation is affine with an offset, so scaling the mask is wrong by
 * up to 75 px. Re-georeferencing against the new scan is the only correct fix,
 * and that is a human decision.
 *
 * Returns a message when the two disagree, null when they agree or when there is
 * nothing to compare — an R2 base with no `info.json` yet is the *first* mirror,
 * whose tiles this very call tells the operator to build.
 */
export async function sourceSizeMismatch(
  annotation: any,
  iiifBase: string
): Promise<string | null> {
  const declared = declaredSourceSize(annotation);
  if (!declared) return null;

  let served: any;
  try {
    const res = await fetch(`${iiifBase}/info.json`, { headers: { Accept: 'application/json' } });
    if (!res.ok) return null;
    served = await res.json();
  } catch {
    return null;
  }
  if (typeof served?.width !== 'number' || typeof served?.height !== 'number') return null;
  if (served.width === declared.width && served.height === declared.height) return null;

  return (
    `Annotation is georeferenced against a ${declared.width}x${declared.height} image, ` +
    `but ${iiifBase} serves ${served.width}x${served.height}. Writing it would move every ` +
    `control point and the mask. Re-georeference this sheet against the scan R2 holds.`
  );
}

/**
 * Which R2 base a re-mirror should rewrite the annotation's source to.
 *
 * Not always `<R2_BASE>/<mapId>`. A sheet that has been rescanned lives under a
 * dated key — 1942 is `…-7651a1c48aba-20260911`, 14915x12602, while the bare map
 * id still serves the original 7479x6314 — and `maps.iiif_image` is what points
 * at it. Assuming the bare id silently demotes such a sheet back to the old scan
 * on every re-mirror: consistent, half the resolution, no error anywhere.
 *
 * Keeping the rescan is what makes `sourceSizeMismatch` matter — the upstream
 * annotation is still drawn on the original, so the rewrite now aims coordinates
 * at an image of a different size and is refused instead of written.
 */
export function r2MirrorBase(
  currentIiifImage: string | null | undefined,
  fallback: string
): string {
  return currentIiifImage?.includes('maparchive.vn') ? currentIiifImage : fallback;
}
