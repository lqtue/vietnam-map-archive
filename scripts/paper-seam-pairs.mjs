// Reanalyse existing seam CSVs; no raster processing, network access, or writes.
// Usage: node scripts/paper-seam-pairs.mjs [faulty.csv corrected.csv]
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

const paths = process.argv.slice(2);
if (paths.length !== 0 && paths.length !== 2) {
  throw new Error('Supply both faulty and corrected CSV paths, or neither.');
}
const [faultyPath, correctedPath] = paths.length
  ? paths
  : ['work/l7014/regen/seams-faulty.csv', 'work/l7014/regen/seams-fixed.csv'];

function readCensus(path) {
  const bytes = readFileSync(path);
  const lines = bytes.toString('utf8').trim().split(/\r?\n/);
  const header = 'sheet_a,kind_a,sheet_b,kind_b,edge,median_m,max_m,samples';
  if (lines.shift() !== header) throw new Error(`Unexpected CSV schema: ${path}`);
  const rows = new Map();
  for (const line of lines) {
    const fields = line.split(',');
    if (fields.length !== 8 || line.includes('"')) throw new Error(`Malformed row: ${line}`);
    const [a, kindA, b, kindB, edge, medianText, maxText, samplesText] = fields;
    const median = Number(medianText),
      maximum = Number(maxText),
      samples = Number(samplesText);
    if (
      !a ||
      !b ||
      a === b ||
      !['N', 'E', 'S', 'W'].includes(edge) ||
      !medianText ||
      !maxText ||
      !samplesText ||
      !Number.isFinite(median) ||
      median < 0 ||
      !Number.isFinite(maximum) ||
      maximum < median ||
      !Number.isInteger(samples) ||
      samples !== 25
    ) {
      throw new Error(`Invalid measurement: ${line}`);
    }
    if (kindA !== 'pdf' || kindB !== 'pdf') throw new Error(`Non-PDF seam: ${line}`);
    const key = [a, b].sort().join('|');
    if (rows.has(key)) throw new Error(`Duplicate sheet pair: ${key}`);
    rows.set(key, { median_m: median, max_m: maximum, axis: 'NS'.includes(edge) ? 'NS' : 'EW' });
  }
  if (!rows.size) throw new Error(`Empty census: ${path}`);
  return { rows, path, sha256: createHash('sha256').update(bytes).digest('hex') };
}

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b),
    m = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[m] : (sorted[m - 1] + sorted[m]) / 2;
}

function summarize(rows) {
  const values = rows.map((row) => row.median_m);
  return {
    count: values.length,
    median_m: median(values),
    max_seam_median_m: values.length ? Math.max(...values) : null,
    over_100_m: values.filter((v) => v > 100).length,
    over_300_m: values.filter((v) => v > 300).length,
  };
}

const faulty = readCensus(faultyPath),
  corrected = readCensus(correctedPath);
const keys = [...faulty.rows.keys()].filter((key) => corrected.rows.has(key)).sort();
if (!keys.length) throw new Error('No shared sheet pairs.');
for (const key of keys) {
  if (faulty.rows.get(key).axis !== corrected.rows.get(key).axis) {
    throw new Error(`Changed edge orientation: ${key}`);
  }
}
const excluded = (left, right) =>
  [...left.rows.entries()]
    .filter(([key]) => !right.rows.has(key))
    .map(([pair, row]) => ({ pair, ...row }));
const pairedFaulty = keys.map((key) => faulty.rows.get(key));
const pairedCorrected = keys.map((key) => corrected.rows.get(key));
console.log(
  JSON.stringify(
    {
      inputs: [faulty, corrected].map(({ path, sha256 }) => ({ path, sha256 })),
      measurement:
        'Per-edge median of 25 sampled outline distances; counts use strict > thresholds.',
      full: {
        faulty: summarize([...faulty.rows.values()]),
        corrected: summarize([...corrected.rows.values()]),
      },
      paired: {
        faulty: summarize(pairedFaulty),
        corrected: summarize(pairedCorrected),
        median_change_m: median(
          keys.map((key) => corrected.rows.get(key).median_m - faulty.rows.get(key).median_m)
        ),
        over_100_to_at_most_100: keys.filter(
          (key) => faulty.rows.get(key).median_m > 100 && corrected.rows.get(key).median_m <= 100
        ).length,
        at_most_100_to_over_100: keys.filter(
          (key) => faulty.rows.get(key).median_m <= 100 && corrected.rows.get(key).median_m > 100
        ).length,
      },
      faulty_only: excluded(faulty, corrected),
      corrected_only: excluded(corrected, faulty),
      interpretation:
        'Descriptive matched-edge analysis of saved builds, not independent observations or absolute-accuracy validation.',
    },
    null,
    2
  )
);
