"""One line per human verdict: the record every VMA review page writes (contract of 2026-10-12).

    from review_record import record, load, sittings, wilson, bound

    record(path, task="place-link", item_id=label_id, bound=bound(geom_or_corners, "name_today@23b04a70"),
           reviewer="tue", order_idx=7, shown_at=t0, decided_at=t1,
           proposal_shown=True, verdicts={"relation": "same_building", "pick": 1}, readings={}, note="")

Why each field exists:
  bound           hash of exactly what was judged (geometry, corners, candidate list) plus the method
                  version that produced it. A later version changes the hash, so an old verdict can
                  never approve new geometry (paper §9, B0152).
  shown_at /      wall clock when the item appeared and when the verdict was given, so human time is a
  decided_at      measurement rather than a guess (docs/journals/261012-manual-baseline.md §4).
  proposal_shown  false on the blind arm (~20% of items): the reviewer saw no machine suggestion. The
                  shown-vs-blind gap is how agreement with the machine is told apart from accuracy.
  order_idx       position in the sitting, for the learning curve.

Lines are appended, never rewritten; the last line for an item wins. Seconds spent on an item are
decided_at - shown_at, dropped (and counted) when longer than IDLE_S: the reviewer walked away.
Stdlib only, so any page can import it. Self-check: python3 work/review-kit/review_record.py
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

IDLE_S = 300  # ponytail: one fixed idle cut; per-task cuts if a task's real items run longer


def bound(judged, method_version: str) -> str:
    """Stable hash of the judged thing (any JSON-able value) and the method version."""
    blob = json.dumps(judged, sort_keys=True, separators=(",", ":"), default=str) + "|" + method_version
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def record(path, *, task, item_id, bound, reviewer, order_idx, shown_at, decided_at,
           proposal_shown, verdicts, readings=None, note="") -> dict:
    if decided_at < shown_at:
        raise ValueError("decided_at before shown_at")
    row = {"task": task, "item_id": str(item_id), "bound": bound, "reviewer": reviewer,
           "order_idx": order_idx, "shown_at": round(shown_at, 3), "decided_at": round(decided_at, 3),
           "proposal_shown": bool(proposal_shown), "verdicts": verdicts, "readings": readings or {},
           "note": note, "written_at": round(time.time(), 3)}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def load(path) -> dict[str, dict]:
    """item_id -> its latest line."""
    out: dict[str, dict] = {}
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["item_id"]] = r
    return out


def sittings(rows, idle_s: float = IDLE_S) -> dict:
    """Seconds per item (median, IQR, n) with idle items excluded and counted."""
    secs = sorted(r["decided_at"] - r["shown_at"] for r in rows)
    kept = [s for s in secs if s <= idle_s]

    def q(p):
        if not kept:
            return None
        i = (len(kept) - 1) * p
        lo, hi = math.floor(i), math.ceil(i)
        return round(kept[lo] + (kept[hi] - kept[lo]) * (i - lo), 1)

    return {"n": len(kept), "idle_dropped": len(secs) - len(kept), "median_s": q(0.5),
            "iqr_s": [q(0.25), q(0.75)], "total_min": round(sum(kept) / 60, 1)}


def wilson(k: int, n: int, z: float = 1.96) -> str:
    """Same as river-reference/score.py, stdlib only."""
    if not n:
        return "n/a"
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return f"{100 * p:.1f}% [{max(0, 100 * (c - h)):.0f}-{min(100, 100 * (c + h)):.0f}] ({k}/{n})"


if __name__ == "__main__":
    import tempfile

    assert wilson(9, 10).startswith("90.0% [60-98]"), wilson(9, 10)  # matches score.py
    assert bound({"a": 1, "b": [1, 2]}, "v1") == bound({"b": [1, 2], "a": 1}, "v1")
    assert bound({"a": 1}, "v1") != bound({"a": 1}, "v2"), "a new method version must change the bound"
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "r.jsonl"
        kw = dict(task="t", bound="x", reviewer="r", proposal_shown=True, verdicts={"ok": True})
        record(p, item_id=1, order_idx=0, shown_at=0, decided_at=10, **kw)
        record(p, item_id=2, order_idx=1, shown_at=10, decided_at=30, **kw)
        record(p, item_id=1, order_idx=2, shown_at=30, decided_at=34, **{**kw, "verdicts": {"ok": False}})
        record(p, item_id=3, order_idx=3, shown_at=40, decided_at=4000, **kw)
        rows = load(p)
        assert len(rows) == 3 and rows["1"]["verdicts"] == {"ok": False}, "last line for an item wins"
        s = sittings(rows.values())
        assert s["idle_dropped"] == 1 and s["n"] == 2 and s["median_s"] == 12.0, s
        try:
            record(p, item_id=9, order_idx=9, shown_at=5, decided_at=1, **kw)
            raise AssertionError("must refuse decided_at < shown_at")
        except ValueError:
            pass
    print("review_record self-check OK")
