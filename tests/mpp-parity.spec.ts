/**
 * Ground metres per source pixel exists twice in this repo, and the two copies
 * were 2.8x apart on paper without ever having been fed the same input.
 *
 *   `work/ocr/scripts/scale.py`   `metres_per_pixel()` — least-squares affine
 *      over a sheet's whole set of GCPs, then the magnitude of each column of
 *      the fit. One number for the whole sheet, per image axis, in metres per
 *      *source* pixel. Reports 0.999 m/px for the 1959 Đô thành Sài Gòn sheet.
 *
 *   `scripts/collection_aoi.mjs`   `aoiInPixels()` — the study area's true
 *      ground area divided by the pixel area it maps onto through the Allmaps
 *      transform, square-rooted. Rotation- and skew-invariant, and *local* to
 *      that rectangle rather than global to the sheet. Feeds the D4 table that
 *      reports 2.80 m/px for the same 1959 sheet, which is the figure
 *      `docs/guides/pipelines.md` § Full resolution derives "6.5 m/px delivered" and
 *      "cannot resolve a street name" from.
 *
 * Same pattern as `tests/density-parity.spec.ts`: one committed fixture of real
 * bytes, both implementations run against it, and a tolerance chosen to catch a
 * 3x disagreement rather than a 3% one. A gap here does not look like a bug —
 * it looks like a sheet whose tile grid was sized for the wrong amount of
 * ground and came back thin.
 *
 * WHICH SHEET, AND WHY NOT THE 1959 ONE. The disputed sheet's GCPs are not
 * obtainable offline: nothing in the tree caches an annotation, and both
 * implementations fetch theirs (`annotations.allmaps.org`, or the mirrored
 * `annotation_url`) at run time. The only real georeference annotations
 * available without the network are five L7014 sheets removed from the tree in
 * 27f8e79f. Sheet 6330-4 is used here because it is the one whose graticule
 * (106.5–106.75 E, 10.75–11.0 N) contains the repo's own District 4 polygon —
 * so the *AOI* is real too, `work/analysis/district4/district4.geojson`
 * unchanged, and not a rectangle invented to make the test pass. Nothing here
 * is synthetic. What this cannot do is reproduce the 1959 number; what it does
 * instead is settle whether the two *methods* can differ by 2.8x at all.
 *
 * Neither implementation is touched by this file, deliberately. The area-ratio
 * side is reached through `tests/fixtures/mppAoiHarness.mjs`, which stands in
 * for the network and the database so the shipped script can run as written —
 * see that file's header for why an import is not possible, which is also why
 * these two had never met.
 */
import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const repo = fileURLToPath(new URL('..', import.meta.url));
const fixturePath = `${repo}tests/fixtures/mpp-parity-l7014-6330-4.json`;

type Fixture = {
  sheet: string;
  iiif_info: { width: number; height: number };
  gcp_bbox: [number, number, number, number];
  python_scale_fit: {
    mx: number;
    my: number;
    mean: number;
    anisotropy: number;
    n_gcps: number;
    transformation: string;
  };
  annotation: unknown;
};

const fx: Fixture = JSON.parse(readFileSync(fixturePath, 'utf8'));

/** The shipped area-ratio estimator, on the fixture's bytes and the real AOI. */
const areaRatio: { mpp: number; cov: number; rect: number[]; w: number; h: number } = JSON.parse(
  execFileSync('node', [`${repo}tests/fixtures/mppAoiHarness.mjs`, fixturePath], {
    cwd: repo,
    encoding: 'utf8',
  })
);

const affine = fx.python_scale_fit;

test('the fixture is one sheet, seen the same way by both sides', () => {
  // The harness serves the same annotation `python_scale_fit` was computed from,
  // and serves the sheet's own pixel dimensions as its info.json. If either
  // drifted, every number below would be comparing two different sheets.
  expect(areaRatio.w).toBe(fx.iiif_info.width);
  expect(areaRatio.h).toBe(fx.iiif_info.height);
  expect(affine.n_gcps).toBe(4);
  expect(affine.transformation).toBe('polynomial');
  // The AOI has to be *inside* the sheet or the area ratio is measuring an
  // extrapolation of the georeference rather than the georeference.
  expect(areaRatio.cov).toBe(1);
  const [x, y, w, h] = areaRatio.rect;
  expect(x).toBeGreaterThan(0);
  expect(y).toBeGreaterThan(0);
  expect(x + w).toBeLessThan(fx.iiif_info.width);
  expect(y + h).toBeLessThan(fx.iiif_info.height);
});

test('the affine fit and the area ratio agree — this is the 3x check', () => {
  // 3% is the contract. Two different estimators are being compared, so the
  // last decimal is not on offer: they use different degrees-to-metres
  // constants, the affine reports the arithmetic mean of two axis scales while
  // the area ratio is effectively their geometric mean, and the area ratio is
  // measured over one rectangle rather than the whole sheet. All three are
  // sub-percent effects on a first-order fit. 3% swallows them and still fails
  // loudly on the kind of gap this fixture was built for: 2.80 against 0.999 is
  // 180% out.
  const gap = Math.abs(areaRatio.mpp - affine.mean) / affine.mean;
  expect(
    gap,
    `area ratio ${areaRatio.mpp.toFixed(4)} m/px vs affine fit ${affine.mean.toFixed(4)} m/px ` +
      `= ${(gap * 100).toFixed(2)}% apart`
  ).toBeLessThan(0.03);
});

test('and the residual gap is the degrees-to-metres constants, not the method', () => {
  // Worth pinning tighter than the contract, because it says *why* they agree.
  // scale.py converts at the sheet's own latitude (111132.95 m/deg lat,
  // 111320·cos(lat) m/deg lon); collection_aoi.mjs uses two fixed constants for
  // 10.76 N (110574, 109368). On this sheet that alone predicts
  // sqrt((111132.95·109322)/(110574·109368)) - 1 = 0.23%, which is the whole
  // observed difference. If this loosens, something in the arithmetic moved —
  // a constant, an axis convention, a transform — and the 3% test above will
  // not notice until it is twelve times worse.
  const gap = Math.abs(areaRatio.mpp - affine.mean) / affine.mean;
  expect(gap, `observed ${(gap * 100).toFixed(3)}%, expected ~0.23%`).toBeLessThan(0.005);
});

test('scale.py still returns the fit stored in the fixture', () => {
  // Follows the density-parity precedent — Python's answer is committed beside
  // the input, so the comparison runs anywhere. When the OCR venv is present,
  // re-run it, so a change to the fit is caught rather than compared against
  // its own stale output.
  const python = `${repo}work/ocr/.venv/bin/python`;
  test.skip(!existsSync(python), 'work/ocr/.venv not present; using the committed fit');
  const out = execFileSync(
    python,
    [
      '-c',
      [
        'import json,sys',
        `sys.path.insert(0, ${JSON.stringify(`${repo}work/ocr/scripts`)})`,
        'from scale import metres_per_pixel',
        `fx=json.load(open(${JSON.stringify(fixturePath)}))`,
        'f=metres_per_pixel(fx["annotation"])',
        'print(json.dumps({"mx":f.mx,"my":f.my,"mean":f.mean,"anisotropy":f.anisotropy}))',
      ].join('\n'),
    ],
    { encoding: 'utf8' }
  );
  const live = JSON.parse(out);
  expect(live.mean).toBeCloseTo(affine.mean, 5);
  expect(live.mx).toBeCloseTo(affine.mx, 5);
  expect(live.my).toBeCloseTo(affine.my, 5);
  // Under ANISOTROPY_LIMIT, so `trustworthy` holds and one number is a fair
  // summary of the sheet — which is the premise the area ratio is compared to.
  expect(live.anisotropy).toBeLessThan(0.05);
});
