/** Source-pixel outline preview. No domain/OL imports; never changes the input. */
export type RingPoint = [number, number];
export type SimplifyTrial = {
  polygon: RingPoint[];
  beforeVertices: number;
  afterVertices: number;
  areaChangePercent: number;
  boundaryMovement: number;
  valid: boolean;
  reason: string;
};

const EPS = 1e-8;
const same = (a: RingPoint, b: RingPoint) => a[0] === b[0] && a[1] === b[1];
export const ringSignature = (ring: RingPoint[]) => JSON.stringify(ring);
function open(ring: RingPoint[]): RingPoint[] {
  const points = ring.map(([x, y]): RingPoint => [x, y]);
  if (points.length > 1 && same(points[0], points[points.length - 1])) points.pop();
  return points.filter((p, i) => !i || !same(p, points[i - 1]));
}
export function ringArea(ring: RingPoint[]): number {
  const points = open(ring);
  return (
    Math.abs(
      points.reduce((sum, a, i) => {
        const b = points[(i + 1) % points.length];
        return sum + a[0] * b[1] - b[0] * a[1];
      }, 0)
    ) / 2
  );
}
function cross(a: RingPoint, b: RingPoint, c: RingPoint): number {
  return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
}
function onSegment(p: RingPoint, a: RingPoint, b: RingPoint): boolean {
  return (
    Math.abs(cross(a, b, p)) < EPS &&
    p[0] >= Math.min(a[0], b[0]) - EPS &&
    p[0] <= Math.max(a[0], b[0]) + EPS &&
    p[1] >= Math.min(a[1], b[1]) - EPS &&
    p[1] <= Math.max(a[1], b[1]) + EPS
  );
}
function intersects(
  a: RingPoint,
  b: RingPoint,
  c: RingPoint,
  d: RingPoint,
  touching = true
): boolean {
  const abC = cross(a, b, c),
    abD = cross(a, b, d),
    cdA = cross(c, d, a),
    cdB = cross(c, d, b);
  if (
    ((abC > EPS && abD < -EPS) || (abC < -EPS && abD > EPS)) &&
    ((cdA > EPS && cdB < -EPS) || (cdA < -EPS && cdB > EPS))
  )
    return true;
  return (
    touching &&
    (onSegment(c, a, b) || onSegment(d, a, b) || onSegment(a, c, d) || onSegment(b, c, d))
  );
}
export function validRing(ring: RingPoint[]): boolean {
  const p = open(ring);
  if (p.length < 3 || p.some((v) => !v.every(Number.isFinite)) || ringArea(p) < EPS) return false;
  for (let i = 0; i < p.length; i++) {
    for (let j = i + 1; j < p.length; j++) {
      if (j === i + 1 || (i === 0 && j === p.length - 1)) continue;
      if (intersects(p[i], p[(i + 1) % p.length], p[j], p[(j + 1) % p.length])) return false;
    }
  }
  return true;
}
function segmentDistance(p: RingPoint, a: RingPoint, b: RingPoint): number {
  const dx = b[0] - a[0],
    dy = b[1] - a[1],
    length = dx * dx + dy * dy;
  const t = length
    ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length))
    : 0;
  return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
}
function dp(points: RingPoint[], tolerance: number): RingPoint[] {
  if (points.length < 3) return points;
  const keep = new Set([0, points.length - 1]);
  const pending: [number, number][] = [[0, points.length - 1]];
  while (pending.length) {
    const [lo, hi] = pending.pop()!;
    let farthest = tolerance,
      at = -1;
    for (let i = lo + 1; i < hi; i++) {
      const distance = segmentDistance(points[i], points[lo], points[hi]);
      if (distance > farthest) {
        farthest = distance;
        at = i;
      }
    }
    if (at >= 0) {
      keep.add(at);
      pending.push([lo, at], [at, hi]);
    }
  }
  return points.filter((_, i) => keep.has(i));
}
function inside(point: RingPoint, polygon: RingPoint[]): boolean {
  let contained = false;
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i],
      b = polygon[(i + 1) % polygon.length];
    if (onSegment(point, a, b)) return false; // touching edges are not an area overlap
    if (
      a[1] > point[1] !== b[1] > point[1] &&
      point[0] < ((b[0] - a[0]) * (point[1] - a[1])) / (b[1] - a[1]) + a[0]
    )
      contained = !contained;
  }
  return contained;
}
/** Interior overlap, including coincident edges, but excluding shared boundary alone. */
export function ringsOverlap(first: RingPoint[], second: RingPoint[]): boolean {
  const a = open(first),
    b = open(second);
  if (!a.length || !b.length) return false;
  if (
    Math.max(...a.map((p) => p[0])) <= Math.min(...b.map((p) => p[0])) ||
    Math.max(...b.map((p) => p[0])) <= Math.min(...a.map((p) => p[0])) ||
    Math.max(...a.map((p) => p[1])) <= Math.min(...b.map((p) => p[1])) ||
    Math.max(...b.map((p) => p[1])) <= Math.min(...a.map((p) => p[1]))
  )
    return false;
  if (!validRing(a) || !validRing(b)) return false;
  for (let i = 0; i < a.length; i++) {
    for (let j = 0; j < b.length; j++) {
      if (intersects(a[i], a[(i + 1) % a.length], b[j], b[(j + 1) % b.length], false)) return true;
    }
  }
  if (a.some((p) => inside(p, b)) || b.some((p) => inside(p, a))) return true;
  // A small inward step detects identical/partially coincident shapes without
  // relying on the centroid, which can lie outside an L-shaped polygon.
  for (const [p, q] of [
    [a, b],
    [b, a],
  ]) {
    for (let i = 0; i < p.length; i++) {
      const v = p[i],
        w = p[(i + 1) % p.length];
      const length = Math.hypot(w[0] - v[0], w[1] - v[1]);
      if (!length) continue;
      const offset = Math.min(length * 1e-5, 1e-4);
      for (const direction of [-1, 1]) {
        const candidate: RingPoint = [
          (v[0] + w[0]) / 2 - ((direction * (w[1] - v[1])) / length) * offset,
          (v[1] + w[1]) / 2 + ((direction * (w[0] - v[0])) / length) * offset,
        ];
        if (inside(candidate, p) && inside(candidate, q)) return true;
      }
    }
  }
  return false;
}
export function simplifyRing(ring: RingPoint[], tolerance: number): SimplifyTrial {
  const points = open(ring);
  const before = ringArea(points);
  const inputValid = validRing(points) && Number.isFinite(tolerance) && tolerance >= 0;
  let result = points;
  if (inputValid && points.length > 3 && tolerance > 0) {
    let split = 1;
    for (let i = 2; i < points.length; i++) {
      if (
        Math.hypot(points[i][0] - points[0][0], points[i][1] - points[0][1]) >
        Math.hypot(points[split][0] - points[0][0], points[split][1] - points[0][1])
      )
        split = i;
    }
    result = [
      ...dp(points.slice(0, split + 1), tolerance).slice(0, -1),
      ...dp([...points.slice(split), points[0]], tolerance).slice(0, -1),
    ];
  }
  const valid = inputValid && validRing(result);
  // Each simplified edge replaces a known original chain. Its maximum
  // displacement is attained at an original vertex; this also bounds the
  // reverse direction by continuity of projection along the replacement edge.
  let movement = 0;
  if (valid)
    for (let i = 0; i < result.length; i++) {
      const a = result[i],
        b = result[(i + 1) % result.length];
      let index = points.findIndex((p) => same(p, a));
      const end = points.findIndex((p) => same(p, b));
      do {
        movement = Math.max(movement, segmentDistance(points[index], a, b));
        index = (index + 1) % points.length;
      } while (index !== end);
    }
  return {
    polygon: result.length ? [...result, [...result[0]] as RingPoint] : [],
    beforeVertices: points.length,
    afterVertices: result.length,
    areaChangePercent: before ? ((ringArea(result) - before) / before) * 100 : 0,
    boundaryMovement: movement,
    valid,
    reason: valid
      ? ''
      : inputValid
        ? 'This tolerance would make an invalid outline.'
        : 'The current outline is invalid.',
  };
}
