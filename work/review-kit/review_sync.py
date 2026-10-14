"""Move review tasks, items and verdicts between the offline pipeline and the app's database.

The review page in the app (docs/plans/review-page-plan.md) keeps a task, its items and one event per
verdict in Postgres (migration 122). Python still makes the machine's proposals; this is how they get
there, and how the verdicts come back as the same `review_record` lines the offline pages write, so
`load()`, `sittings()`, `wilson()` and each task's scoring run on them unchanged.

    python3 review_sync.py push task.json items.json     send a task and its items (idempotent)
    python3 review_sync.py pull place-link out/verdicts.jsonl   write the task's events as review_record lines
    python3 review_sync.py --self-check                  no network: round-trips synthetic events

Needs VMA_API_URL and VMA_WORKER_KEY (in the environment or the repo's .env), the same two variables
the worker uses; the key must be unscoped or include the `review` kind. `requests` is imported only
when a command talks to the network, so the self-check and the formatter need the standard library.

task.json   {"key", "title", "question", "question_vi"?, "method", "seed", "blind_frac"?,
             "audience"?, "status"?}                           (see review_tasks in migration 122)
items.json  [{"item_id", "bound", "payload", "proposal"?, "gold"?, "active"?}, ...]  or {"items": [...]}
            `bound` is review_record.bound() of exactly what is judged plus the method version;
            `payload` is what both arms see; `proposal` only the shown arm. Place links:
            work/image-processing/experiments/place-links/review_items.py makes both files.

A big task goes in several calls (each carries the task row). Once a task has events, its seed,
blind_frac and method are frozen: the server answers 409 rather than let the arms drift.

pull writes one line per event in arrival order, keys and rounding exactly as `review_record.record()`:
`shown_at` / `decided_at` are epoch seconds rounded to 3 places, `written_at` is the server's
`received_at`, and an undo is a line whose verdicts are {"undone": true}. `reviewer` is a handle:

    the profile's display_name, lower-cased, runs of anything but letters and digits made one "-"
    (so "Le Quang Tue" -> "le-quang-tue"); "u-" + the first 8 characters of the uuid when the name is
    blank; "deleted-user" when the account has been deleted. When two reviewers in the export would
    share a handle, each gets "-" + the first 8 characters of their uuid, so two people are never
    merged into one sitting. `--as UUID=handle` (repeatable) overrides any of it, e.g. to give the
    owner's web sittings the handle ("tue") the offline files use.
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "work" / "core"))

PAGE = 1000          # events per request; the endpoint's maximum
MAX_ITEMS = 100      # items per push call (the endpoint takes 200)
MAX_BYTES = 2_000_000  # JSON bytes per push call (the endpoint takes 8 MB)
ITEM_KEYS = {"item_id", "bound", "payload", "proposal", "gold", "active"}

_TS = re.compile(r"^(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d)(?:\.(\d{1,6}))?(Z|[+-]\d\d(?::?\d\d)?)$")


# --------------------------------------------------------------------------- the export formatter

def epoch(ts: str) -> float:
    """Postgres timestamptz text (any fraction length, any offset) -> epoch seconds, rounded to 3."""
    m = _TS.match(ts)
    if not m:
        raise ValueError(f"not a timestamp: {ts!r}")
    y, mo, d, h, mi, s, frac, tz = m.groups()
    secs = calendar.timegm((int(y), int(mo), int(d), int(h), int(mi), int(s)))
    off = 0
    if tz != "Z":
        digits = tz[1:].replace(":", "")
        off = (int(digits[:2]) * 3600 + int(digits[2:] or 0) * 60) * (-1 if tz[0] == "-" else 1)
    micro = int((frac or "0").ljust(6, "0"))
    return round(secs - off + micro / 1e6, 3)


def _slug(name: str) -> str:
    return re.sub(r"[\W_]+", "-", name.strip().lower()).strip("-")


def handles(reviewers: dict[str, str | None], override: dict[str, str] | None = None) -> dict[str, str]:
    """uuid -> the handle written to `reviewer` (rule in the module docstring)."""
    out = {u: _slug(n or "") or f"u-{u[:8]}" for u, n in reviewers.items()}
    seen: dict[str, list[str]] = {}
    for u, h in out.items():
        seen.setdefault(h, []).append(u)
    for h, us in seen.items():
        if len(us) > 1:
            for u in us:
                out[u] = f"{h}-{u[:8]}"
    out.update(override or {})
    return out


def to_line(ev: dict, handle: dict[str, str]) -> dict:
    """One database event as the dict `review_record.record()` would have written (same key order)."""
    who = handle.get(ev["reviewer"], f"u-{ev['reviewer'][:8]}") if ev.get("reviewer") else "deleted-user"
    return {"task": ev["task"], "item_id": str(ev["item_id"]), "bound": ev["bound"], "reviewer": who,
            "order_idx": ev["order_idx"], "shown_at": epoch(ev["shown_at"]), "decided_at": epoch(ev["decided_at"]),
            "proposal_shown": bool(ev["proposal_shown"]), "verdicts": ev["verdicts"],
            "readings": ev["readings"] or {}, "note": ev["note"] or "", "written_at": epoch(ev["received_at"])}


def format_lines(events: list[dict], reviewers: dict[str, str | None], override: dict[str, str] | None = None) -> list[str]:
    h = handles(reviewers, override)
    return [json.dumps(to_line(e, h), ensure_ascii=False) for e in events]


def fetch_events(task: str, get, limit: int = PAGE) -> tuple[list[dict], dict[str, str | None]]:
    """Every event of a task in id order, paging until `next_after` is null. `get(params) -> dict`."""
    events: list[dict] = []
    reviewers: dict[str, str | None] = {}
    after = 0
    while True:
        page = get({"task": task, "after": after, "limit": limit})
        events += page["events"]
        reviewers.update(page["reviewers"])
        if page["next_after"] is None:
            return events, reviewers
        after = page["next_after"]


# --------------------------------------------------------------------------- push

def chunks(items: list[dict], max_items: int = MAX_ITEMS, max_bytes: int = MAX_BYTES):
    """Split items so no call exceeds either bound; an item over max_bytes alone still goes (the server decides)."""
    cur: list[dict] = []
    size = 0
    for it in items:
        n = len(json.dumps(it, ensure_ascii=False))
        if cur and (len(cur) >= max_items or size + n > max_bytes):
            yield cur
            cur, size = [], 0
        cur.append(it)
        size += n
    if cur:
        yield cur


def read_push_files(task_path, items_path) -> tuple[dict, list[dict]]:
    task = json.loads(Path(task_path).read_text(encoding="utf-8"))
    raw = json.loads(Path(items_path).read_text(encoding="utf-8"))
    items = raw["items"] if isinstance(raw, dict) else raw
    if not isinstance(task, dict) or not isinstance(items, list) or not items:
        sys.exit("task.json must be an object and items.json a non-empty list")
    for i, it in enumerate(items):
        if not isinstance(it, dict) or set(it) - ITEM_KEYS or not {"item_id", "bound", "payload"} <= set(it):
            sys.exit(f"items[{i}]: needs item_id, bound, payload; allowed keys {sorted(ITEM_KEYS)}")
    return task, items


# --------------------------------------------------------------------------- transport

def _call(method: str, path: str, *, params=None, body=None) -> dict:
    from vma_core.db import _api_config  # the worker's own transport settings; imports requests
    import requests

    cfg = _api_config()
    if not cfg:
        sys.exit("Set VMA_API_URL and VMA_WORKER_KEY (environment or .env at the repo root)")
    url, key = cfg
    resp = requests.request(method, f"{url}{path}", params=params, timeout=120,
                            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                            data=None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8"))
    if not resp.ok:
        sys.exit(f"{method} {path}: {resp.status_code} {resp.text[:400]}")
    return resp.json()


def push(task_path, items_path) -> int:
    task, items = read_push_files(task_path, items_path)
    sent = 0
    for part in chunks(items):
        sent += _call("POST", "/api/pipeline/review-items", body={"task": task, "items": part})["items"]
    print(f"pushed task {task.get('key')}: {sent} items")
    return sent


def pull(task: str, out) -> int:
    events, reviewers = fetch_events(task, lambda params: _call("GET", "/api/pipeline/review-events", params=params))
    lines = format_lines(events, reviewers, PULL_OVERRIDE)
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    os.replace(tmp, p)  # a snapshot of the table, replaced whole; never a half-written file
    who = sorted({json.loads(x)["reviewer"] for x in lines})
    print(f"pulled {len(lines)} events of {task} -> {p}  reviewers: {', '.join(who) or 'none'}")
    return len(lines)


PULL_OVERRIDE: dict[str, str] = {}


# --------------------------------------------------------------------------- self-check

def self_check() -> int:
    import tempfile
    from datetime import datetime, timezone

    from review_record import load, record, sittings, wilson

    def pg(x: float) -> str:  # how PostgREST prints a timestamptz: no trailing zeros, +00:00
        s = datetime.fromtimestamp(x, timezone.utc).isoformat(timespec="microseconds")
        head, tail = s.split("+")
        d, f = head.split(".")
        return d + (("." + f.rstrip("0")) if f.rstrip("0") else "") + "+" + tail

    assert pg(1760428800.0) == "2025-10-14T08:00:00+00:00" and pg(1760428800.5).endswith(".5+00:00")
    for ts, want in (("2025-10-14T08:00:00Z", 1760428800.0), ("2025-10-14T08:00:00.123456+00:00", 1760428800.123),
                     ("2025-10-14T15:00:00.5+07:00", 1760428800.5), ("2025-10-14 03:30:00-04:30", 1760428800.0)):
        assert epoch(ts) == want, (ts, epoch(ts), want)
    try:
        epoch("yesterday")
        raise AssertionError("must refuse a non-timestamp")
    except ValueError:
        pass

    # the originals: what the offline pages write
    ids = {"tue": "11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "ann": "22222222-bbbb-4bbb-8bbb-bbbbbbbbbbbb"}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        orig = td / "orig.jsonl"
        t0 = 1760428800.1234
        kw = dict(task="place-link", bound="b0")
        record(orig, item_id="x1", order_idx=0, shown_at=t0, decided_at=t0 + 9.5, reviewer="tue", proposal_shown=True,
               verdicts={"arm": "shown", "pick": 2, "relation": "moved", "target": {"id": "way/2", "name": "Chợ Bến Thành"}},
               readings={"hidden_ms": 1200}, note="ok", **kw)
        record(orig, item_id="x2", order_idx=1, shown_at=t0 + 10, decided_at=t0 + 31.0004, reviewer="tue", proposal_shown=False,
               verdicts={"arm": "blind", "relation": "gone", "target": None}, **kw)
        record(orig, item_id="x2", order_idx=1, shown_at=t0 + 40, decided_at=t0 + 40, reviewer="tue", proposal_shown=False,
               verdicts={"undone": True}, **kw)
        record(orig, item_id="x2", order_idx=2, shown_at=t0 + 41, decided_at=t0 + 47.25, reviewer="tue", proposal_shown=False,
               verdicts={"arm": "blind", "relation": "unsure", "target": None}, note="Đại Chủng Viện?", **kw)
        record(orig, item_id="x3", order_idx=3, shown_at=t0 + 50, decided_at=t0 + 4000, reviewer="ann", proposal_shown=True,
               verdicts={"arm": "shown", "relation": "none"}, **kw)  # idle: dropped by sittings()
        record(orig, item_id="x4", order_idx=4, shown_at=t0 + 60, decided_at=t0 + 71, reviewer="ann", proposal_shown=True,
               verdicts={"arm": "shown", "pick": 1, "relation": "same_building"}, **kw)
        want = orig.read_text(encoding="utf-8").splitlines()

        # the same lines as the database would hold them
        events = []
        for i, line in enumerate(want, 1):
            r = json.loads(line)
            events.append({"id": 100 + i, "task": r["task"], "item_id": r["item_id"], "bound": r["bound"],
                           "reviewer": ids[r["reviewer"]], "order_idx": r["order_idx"], "shown_at": pg(r["shown_at"]),
                           "decided_at": pg(r["decided_at"]), "received_at": pg(r["written_at"]),
                           "proposal_shown": r["proposal_shown"], "verdicts": r["verdicts"], "readings": r["readings"],
                           "note": r["note"], "client_id": f"c{i}"})
        # paged exactly as the endpoint pages: next_after is null on a short page
        calls = []

        def get(params):
            calls.append(params)
            rest = [e for e in events if e["id"] > params["after"]][:2]
            full = len(rest) == 2
            return {"events": rest, "next_after": rest[-1]["id"] if full else None,
                    "reviewers": {e["reviewer"]: {ids["tue"]: "Tue", ids["ann"]: "Ann"}[e["reviewer"]] for e in rest}}

        got_events, who = fetch_events("place-link", get, limit=2)
        assert got_events == events and len(calls) == 4 and calls[0]["after"] == 0 and calls[1]["after"] == 102, calls
        got = format_lines(got_events, who)
        assert got == want, "pull must write byte-identical review_record lines"

        out = td / "pulled.jsonl"
        out.write_text("".join(x + "\n" for x in got), encoding="utf-8")
        a, b = load(orig), load(out)
        assert a == b and b["x2"]["verdicts"]["relation"] == "unsure", "last line for an item wins"
        rows = lambda d: sorted(d.values(), key=lambda r: r["item_id"])
        assert sittings(rows(a)) == sittings(rows(b)) and sittings(rows(b))["idle_dropped"] == 1
        every = lambda p: [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
        assert sittings(every(orig)) == sittings(every(out))
        ok = lambda p: sum(1 for r in every(p) if r["verdicts"].get("relation") == "same_building")
        assert wilson(ok(orig), len(every(orig))) == wilson(ok(out), len(every(out)))

    # handles: the rule in the docstring
    u1, u2, u3, u4 = "aaaaaaaa-0000-4000-8000-000000000001", "bbbbbbbb-0000-4000-8000-000000000002", \
        "cccccccc-0000-4000-8000-000000000003", "dddddddd-0000-4000-8000-000000000004"
    h = handles({u1: "Le Quang Tue", u2: "Ann", u3: "  ", u4: None})
    assert h == {u1: "le-quang-tue", u2: "ann", u3: "u-cccccccc", u4: "u-dddddddd"}, h
    h = handles({u1: "Tue", u2: "tue!", u3: "Nguyễn Văn A"})
    assert h[u1] == "tue-aaaaaaaa" and h[u2] == "tue-bbbbbbbb" and h[u3] == "nguyễn-văn-a", h
    assert handles({u1: "Tue"}, {u1: "tue"}) == {u1: "tue"} and handles({u1: "Tue"}, {u1: "owner"})[u1] == "owner"
    base = {"task": "t", "item_id": "i", "bound": "b", "order_idx": 0, "shown_at": "2025-10-14T08:00:00Z",
            "decided_at": "2025-10-14T08:00:01Z", "received_at": "2025-10-14T08:00:02Z", "proposal_shown": True,
            "verdicts": {}, "readings": None, "note": None}
    assert to_line({**base, "reviewer": None}, {})["reviewer"] == "deleted-user"
    assert to_line({**base, "reviewer": u1}, {})["reviewer"] == "u-aaaaaaaa"
    assert to_line({**base, "reviewer": None}, {})["readings"] == {} and to_line({**base, "reviewer": None}, {})["note"] == ""

    # push: chunking honours both bounds, loses nothing, never yields an empty call
    many = [{"item_id": str(i), "bound": "b", "payload": {"t": "x" * 40}} for i in range(25)]
    parts = list(chunks(many, max_items=10, max_bytes=10_000))
    assert [len(p) for p in parts] == [10, 10, 5] and sum(parts, []) == many
    parts = list(chunks(many, max_items=100, max_bytes=300))
    assert all(p for p in parts) and sum(parts, []) == many and all(len(json.dumps(p)) < 400 for p in parts)
    assert [len(p) for p in chunks([many[0]], max_bytes=1)] == [1], "an oversize item still goes alone"
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "t.json").write_text(json.dumps({"key": "k"}))
        (Path(td) / "i.json").write_text(json.dumps({"items": many[:2]}))
        assert read_push_files(Path(td) / "t.json", Path(td) / "i.json")[1] == many[:2]
        (Path(td) / "i.json").write_text(json.dumps([{"item_id": "a", "bound": "b", "payload": {}, "typo": 1}]))
        try:
            read_push_files(Path(td) / "t.json", Path(td) / "i.json")
            raise AssertionError("an unknown item key must be refused before anything is sent")
        except SystemExit:
            pass
    print("review_sync self-check OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-check", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("push", help="send a task and its items")
    p.add_argument("task_json")
    p.add_argument("items_json")
    q = sub.add_parser("pull", help="write a task's events as review_record lines")
    q.add_argument("task")
    q.add_argument("out")
    q.add_argument("--as", dest="as_", action="append", default=[], metavar="UUID=HANDLE",
                   help="use HANDLE as the reviewer for this uuid (repeatable)")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    if a.cmd == "push":
        push(a.task_json, a.items_json)
    elif a.cmd == "pull":
        PULL_OVERRIDE.update(x.split("=", 1) for x in a.as_)
        pull(a.task, a.out)
    else:
        ap.print_help()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
