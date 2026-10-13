#!/usr/bin/env python3
"""Read hash-bound then-now verdicts without treating them as reference polygons.

Outline judgement time is review time, not correction time. Only an explicit
correction_seconds reading can support a correction-effort comparison.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics


def outline_bound(properties):
    judged = {'a': properties['a_outline'], 'm': properties['m_outline']}
    canonical = json.dumps(judged, sort_keys=True, separators=(',', ':'), default=str) + '|' + properties['method']
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def summarize(records, features):
    items = {str(f['properties']['id']): f['properties'] for f in features}
    latest = {}
    for row in records:
        if row.get('task') == 'then-now-block': latest[str(row['item_id'])] = row
    usable, stale, idle, malformed = [], 0, 0, 0
    for item_id, row in latest.items():
        props = items.get(item_id)
        if not props or row.get('bound') != outline_bound(props): stale += 1; continue
        elapsed = row.get('decided_at', 0) - row.get('shown_at', 0)
        if not math.isfinite(elapsed) or elapsed < 0: malformed += 1; continue
        if elapsed > 300: idle += 1; continue
        if row.get('verdicts', {}).get('v1') not in ('y', 'n', 'p'): continue
        usable.append((row, elapsed))
    correction = [r.get('readings', {}).get('correction_seconds') for r, _ in usable]
    correction = [v for v in correction if isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0]
    arms = {}
    for arm in (True, False):
        samples = [seconds for row, seconds in usable if row.get('proposal_shown') is arm]
        arms['shown' if arm else 'blind'] = {'n': len(samples), 'median_review_seconds': statistics.median(samples) if samples else None}
    return {'n_current': len(usable), 'stale_or_missing_outline': stale, 'idle_dropped': idle,
            'malformed_time': malformed, 'arms': arms,
            'correction_samples': len(correction), 'median_correction_seconds': statistics.median(correction) if correction else None,
            'limitation': 'Joint 1882/modern outline judgements are review evidence, not exhaustive parcel truth or timed correction.'}


def self_check():
    props = {'id': 1, 'a_outline': {'type': 'Polygon', 'coordinates': []}, 'm_outline': None, 'method': 'fixture'}
    row = {'task': 'then-now-block', 'item_id': '1', 'bound': outline_bound(props), 'shown_at': 10,
           'decided_at': 20, 'proposal_shown': True, 'verdicts': {'v1': 'y'}}
    result = summarize([row], [{'properties': props}])
    assert result['n_current'] == 1 and result['median_correction_seconds'] is None
    assert summarize([{**row, 'bound': 'old'}], [{'properties': props}])['stale_or_missing_outline'] == 1
    print('hash-bound review timing self-check passed')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--records'); p.add_argument('--items'); p.add_argument('--out'); p.add_argument('--self-check', action='store_true')
    args = p.parse_args()
    if args.self_check: self_check()
    else:
        if not args.records or not args.items: p.error('--records and --items are required')
        rows = [json.loads(line) for line in Path(args.records).read_text().splitlines() if line.strip()]
        report = summarize(rows, json.loads(Path(args.items).read_text())['features'])
        if args.out: Path(args.out).write_text(json.dumps(report, indent=2))
        else: print(json.dumps(report, indent=2))
