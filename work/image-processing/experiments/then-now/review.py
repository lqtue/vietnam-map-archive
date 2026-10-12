"""Gate page for the 1882 then-now block differences: the owner decides every difference, the page times it.

  python3 work/image-processing/experiments/then-now/review.py            serve http://127.0.0.1:8793
      [--port 8793] [--seed 1] [--n-unchanged 30] [--reviewer tue] [--skip-open-new]
  python3 work/image-processing/experiments/then-now/review.py --stats    time per item and shown-vs-blind, from verdicts.jsonl
  python3 work/image-processing/experiments/then-now/review.py --self-check   synthetic data, serves itself on a spare port

Items are the components of `then-now/classes.geojson` (made by scripts/then_now_blocks.py): every
component that is not `unchanged`, plus a seeded random --n-unchanged (20-50) `unchanged` ones, all in a
seeded random order. --skip-open-new drops the `new` blocks that sit on ground the 1882 sheet left open
(paddy, the far bank); they are real differences but a low-value half of the queue.

Each item shows the 1882 scan, twice, in sheet orientation (a north arrow is drawn, from the sheet's own
fit): left with the outlines, right clean, so the outline can be judged against the ink. Red solid = the
1882 block(s) as drawn on this scan; blue dashed = the 2023 block(s) placed through the displacement field.
An item with only one outline (`gone`, `new`) shows only that one.

Two verdicts per item:
  V1  are the outlines right?      y yes   n no   p partly         (press first)
  V2  is the class right?          y yes, or the right class by number: 1 unchanged 2 reshaped 3 split
                                   4 merged 5 complex 6 gone 7 new 8 unpartnered
On a seeded random 20% (the blind arm) V2 is asked with NO class shown, so `y` is not offered and the number
is the reviewer's own reading; the shown-vs-blind gap is how agreement with the machine is told apart from
accuracy. `u` goes back from V2 to V1, or, at V1, undoes the last finished item.

Records: one line per finished item in then-now/verdicts.jsonl via work/review-kit/review_record.py, task
`then-now-block`, item_id = the component id, bound = hash of both outlines + the method version (a new
method changes the bound, so an old verdict cannot approve new geometry), proposal_shown false on the blind
arm, verdicts {v1, v2}, readings {class_read, class_proposed, arm, in_fit}. The time is decided_at - shown_at,
from the server clock, idle gaps over 5 minutes dropped and counted by review_record.sittings. An undo
appends a line {"undone": true} (append-only; the last line for an item wins).
"""
import json
import math
import random
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "work" / "review-kit"))
import review_record as rr  # noqa: E402

MAP_ID = "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b"
RES = ROOT / "work" / "image-processing" / "results"
OUT = RES / "prior" / MAP_ID / "then-now"
TASK = "then-now-block"
CLASSES = ["unchanged", "reshaped", "split", "merged", "complex", "gone", "new", "unpartnered"]
BLIND_SHARE = 0.2


def build_items(feats, seed=1, n_unchanged=30, skip_open_new=False):
    """Seeded: the same arguments always give the same items, order and blind arm."""
    rng = random.Random(seed)
    props = [f["properties"] for f in feats]
    keep = [p for p in props if p["class"] != "unchanged" and not (skip_open_new and p.get("in_1882_open"))]
    unch = sorted((p for p in props if p["class"] == "unchanged"), key=lambda p: p["id"])
    keep += rng.sample(unch, min(n_unchanged, len(unch)))
    keep.sort(key=lambda p: p["id"])
    rng.shuffle(keep)
    blind = {p["id"] for p in random.Random(seed + 1).sample(keep, round(BLIND_SHARE * len(keep)))}
    return [{"id": p["id"], "idx": i, "arm": "blind" if p["id"] in blind else "shown", "p": p} for i, p in enumerate(keep)]


def _rings(o):
    if not o:
        return
    polys = [o["coordinates"]] if o["type"] == "Polygon" else o["coordinates"]
    for poly in polys:
        for r in poly:
            yield r


def render(im, p, view, north=(1.0, 0.0), max_side=820, minside=420):
    """PNG bytes: a crop of the scan around the item. view 'overlay' draws the outlines, 'clean' does not."""
    from PIL import ImageDraw

    xs = [x for o in (p["a_outline"], p["m_outline"]) for r in _rings(o) for x, _ in r]
    ys = [y for o in (p["a_outline"], p["m_outline"]) for r in _rings(o) for _, y in r]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    m = max(60, 0.3 * max(x1 - x0, y1 - y0))
    w, h = max(x1 - x0 + 2 * m, minside), max(y1 - y0 + 2 * m, minside)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bx0, by0 = int(cx - w / 2), int(cy - h / 2)
    bx1, by1 = int(cx + w / 2), int(cy + h / 2)
    c = im.crop((bx0, by0, bx1, by1)).convert("RGB")      # PIL pads out-of-image with black
    z = min(1.0, max_side / max(c.size)) if max(c.size) > max_side else min(2.0, max_side / max(c.size))
    c = c.resize((max(1, round(c.width * z)), max(1, round(c.height * z))))
    d = ImageDraw.Draw(c)
    pt = lambda r: [((x - bx0) * z, (y - by0) * z) for x, y in r]
    if view == "overlay":
        for r in _rings(p["a_outline"]):
            d.line(pt(r), fill=(255, 40, 40), width=3)
        for r in _rings(p["m_outline"]):
            q = pt(r)
            for (ax, ay), (bx, by) in zip(q, q[1:]):
                n = max(1, int(math.hypot(bx - ax, by - ay) // 14))
                for s in range(n):
                    d.line([(ax + (bx - ax) * s / n, ay + (by - ay) * s / n), (ax + (bx - ax) * (s + .5) / n, ay + (by - ay) * (s + .5) / n)],
                           fill=(40, 90, 255), width=3)
    # north arrow, bottom-right; the sheet is not drawn north-up, so say where north is
    nx, ny = north
    ox, oy = c.width - 50, c.height - 50
    d.ellipse([ox - 30, oy - 30, ox + 30, oy + 30], fill=(255, 255, 255), outline=(0, 0, 0))
    d.line([(ox - nx * 22, oy - ny * 22), (ox + nx * 22, oy + ny * 22)], fill=(0, 0, 0), width=3)
    ax, ay = ox + nx * 22, oy + ny * 22
    d.polygon([(ax, ay), (ax - nx * 10 - ny * 6, ay - ny * 10 + nx * 6), (ax - nx * 10 + ny * 6, ay - ny * 10 - nx * 6)], fill=(0, 0, 0))
    d.text((ox + nx * 26 - 3, oy + ny * 26 - 6), "N", fill=(200, 0, 0))
    buf = BytesIO()
    c.save(buf, "PNG")
    return buf.getvalue()


PAGE = """<!doctype html><meta charset=utf-8><title>Then-now blocks</title>
<style>body{font:15px system-ui;margin:14px;background:#222;color:#eee}img{border:1px solid #555;max-width:49%}
kbd{background:#444;padding:2px 6px;border-radius:3px}#c{font-size:18px;color:#ffd}.dim{color:#aaa}.r{color:#f55}.b{color:#69f}</style>
<p id=s></p><p id=c></p><div id=row><img id=a><img id=b></div>
<p id=q></p>
<p class=dim><span class=r>red solid</span> = the 1882 block(s) on this scan &nbsp; <span class=b>blue dashed</span> = the 2023 block(s) placed through the field &nbsp; (one outline only for gone / new). The white circle shows where north is.</p>
<script>
let cur=null, stage=1, v1=null, blind=false;
const CL=["unchanged","reshaped","split","merged","complex","gone","new","unpartnered"];
function ask(){
 document.getElementById('q').innerHTML = stage==1
  ? '<b>V1 outlines right?</b> <kbd>y</kbd> yes <kbd>n</kbd> no <kbd>p</kbd> partly &nbsp; <kbd>u</kbd> undo last item'
  : '<b>V2 class right?</b> '+(blind?'(no class shown: say what you see) ':'<kbd>y</kbd> yes, or ')+CL.map((c,i)=>'<kbd>'+(i+1)+'</kbd> '+c).join(' ')+' &nbsp; <kbd>u</kbd> back to V1'}
async function next(){const r=await (await fetch('/next')).json();cur=r.id;stage=1;v1=null;blind=r.arm==='blind';
 document.getElementById('s').textContent=r.id!==null?`${r.done} / ${r.total} done`:`all ${r.total} done, close the tab`;
 document.getElementById('c').textContent=r.id===null?'':(blind?'':'proposed class: '+r.cls+(r.iou!==null?'  (IoU '+r.iou+')':'')+(r.in_fit?'  [near a control point]':''));
 if(r.id!==null){const t=Date.now();a.src='/img/'+r.id+'/overlay?'+t;b.src='/img/'+r.id+'/clean?'+t;ask()}
 else{a.removeAttribute('src');b.removeAttribute('src');document.getElementById('q').textContent=''}}
async function send(v2){await fetch('/verdict',{method:'POST',body:JSON.stringify({id:cur,v1:v1,v2:v2})});next()}
document.onkeydown=async e=>{const k=e.key.toLowerCase(); if(cur===null&&k!=='u')return;
 if(k==='u'){if(stage==2){stage=1;v1=null;ask()}else{await fetch('/undo',{method:'POST'});next()}return}
 if(stage==1&&'ynp'.includes(k)&&k.length==1){v1=k;stage=2;ask();return}
 if(stage==2){if(k==='y'&&!blind){send('y');return}
  const n=parseInt(k);if(n>=1&&n<=8)send(CL[n-1])}};
next();
</script>"""


class State:
    def __init__(self, items, out_dir, im, north, reviewer, seed):
        self.items = {it["id"]: it for it in items}
        self.order = [it["id"] for it in items]
        self.path = Path(out_dir) / "verdicts.jsonl"
        self.im, self.north, self.reviewer = im, north, reviewer
        self.shown: dict[int, float] = {}
        self.lock = threading.Lock()

    def done_ids(self):
        rows = rr.load(self.path)
        return {int(i) for i, r in rows.items() if not r["verdicts"].get("undone") and int(i) in self.items}

    def next_item(self):
        done = self.done_ids()
        todo = [i for i in self.order if i not in done]
        if todo:
            self.shown[todo[0]] = time.time()
        return todo[0] if todo else None, len(done)

    def verdict(self, iid, v1, v2):
        it = self.items[iid]
        p = it["p"]
        if v1 not in ("y", "n", "p") or (v2 != "y" and v2 not in CLASSES) or (v2 == "y" and it["arm"] == "blind"):
            raise ValueError("bad verdict")
        now = time.time()
        eff = p["class"] if v2 == "y" else v2
        rr.record(self.path, task=TASK, item_id=iid, bound=rr.bound({"a": p["a_outline"], "m": p["m_outline"]}, p["method"]),
                  reviewer=self.reviewer, order_idx=it["idx"], shown_at=min(self.shown.get(iid, now), now), decided_at=now,
                  proposal_shown=it["arm"] == "shown", verdicts={"v1": v1, "v2": v2},
                  readings={"class_read": eff, "class_proposed": p["class"], "arm": it["arm"], "in_fit": bool(p.get("in_fit"))})

    def undo(self):
        rows = [r for r in rr.load(self.path).values() if not r["verdicts"].get("undone")]
        if not rows:
            return
        last = max(rows, key=lambda r: r["decided_at"])
        now = time.time()
        rr.record(self.path, task=TASK, item_id=last["item_id"], bound=last["bound"], reviewer=self.reviewer, order_idx=last["order_idx"],
                  shown_at=now, decided_at=now, proposal_shown=last["proposal_shown"], verdicts={"undone": True}, note="undo")


def make_handler(st):
    class H(BaseHTTPRequestHandler):
        def send(self, body, ctype="application/json", code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else body.encode())

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                return self.send(PAGE, "text/html; charset=utf-8")
            if path == "/next":
                with st.lock:
                    iid, done = st.next_item()
                if iid is None:
                    return self.send(json.dumps({"id": None, "done": done, "total": len(st.items)}))
                it = st.items[iid]
                p = it["p"]
                return self.send(json.dumps({"id": iid, "done": done, "total": len(st.items), "arm": it["arm"],
                                             "cls": None if it["arm"] == "blind" else p["class"], "iou": None if it["arm"] == "blind" else p["iou"],
                                             "in_fit": bool(p.get("in_fit")) and it["arm"] == "shown"}))
            if path == "/stats":
                return self.send(json.dumps(stats(st.path)))
            if path.startswith("/img/"):
                _, _, sid, view = path.split("/")
                it = st.items.get(int(sid))
                if it is None or view not in ("overlay", "clean"):
                    return self.send("{}", code=404)
                return self.send(render(st.im(), it["p"], view, st.north), "image/png")
            self.send("{}", code=404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            with st.lock:
                try:
                    if self.path == "/undo":
                        st.undo()
                    elif self.path == "/verdict":
                        st.verdict(int(body["id"]), body["v1"], body["v2"])
                    else:
                        return self.send("{}", code=404)
                except (ValueError, KeyError) as e:
                    return self.send(json.dumps({"error": str(e)}), code=400)
            self.send("{}")

        def log_message(self, *a):
            pass

    return H


def stats(path):
    rows = [r for r in rr.load(path).values() if not r["verdicts"].get("undone")]
    out = {"n": len(rows), "time_all": rr.sittings(rows)}
    for arm in ("shown", "blind"):
        rs = [r for r in rows if r["readings"]["arm"] == arm]
        agree = sum(r["readings"]["class_read"] == r["readings"]["class_proposed"] for r in rs)
        out[arm] = {"n": len(rs), "class_agrees_with_proposal": rr.wilson(agree, len(rs)), "time": rr.sittings(rs),
                    "v1": {k: sum(r["verdicts"]["v1"] == k for r in rs) for k in "ynp"}}
    return out


def load_state(args, im_factory, classes_path):
    doc = json.loads(Path(classes_path).read_text())
    items = build_items(doc["features"], args["seed"], args["n_unchanged"], args["skip_open_new"])
    north = tuple(doc.get("north_px", [1.0, 0.0]))
    return State(items, args["out"], im_factory, north, args["reviewer"], args["seed"]), items


def serve(args):
    from PIL import Image

    if not 20 <= args["n_unchanged"] <= 50:
        args["n_unchanged"] = min(50, max(20, args["n_unchanged"]))
        print(f"--n-unchanged clamped to {args['n_unchanged']} (the plan asks for 20-50)")

    Image.MAX_IMAGE_PIXELS = None
    cache = {}

    def im():
        if "im" not in cache:
            cache["im"] = Image.open(args["image"]).convert("RGB")
        return cache["im"]

    st, items = load_state(args, im, args["out"] / "classes.geojson")
    n_blind = sum(it["arm"] == "blind" for it in items)
    print(f"http://127.0.0.1:{args['port']}  ({len(items)} items, {n_blind} blind, seed {args['seed']}; verdicts -> {st.path})")
    ThreadingHTTPServer(("127.0.0.1", args["port"]), make_handler(st)).serve_forever()


def _self_check():
    import tempfile
    import urllib.request

    from PIL import Image

    def sq(x, y, s=100):
        return {"type": "Polygon", "coordinates": [[[x, y], [x + s, y], [x + s, y + s], [x, y + s], [x, y]]]}

    feats = [{"type": "Feature", "geometry": sq(i * 150, 50), "properties": {
        "id": i, "class": CLASSES[i % 8], "iou": 0.5, "in_fit": i == 3, "method": "t1", "in_1882_open": i == 6,
        "a_outline": None if CLASSES[i % 8] == "new" else sq(i * 150, 50), "m_outline": None if CLASSES[i % 8] == "gone" else sq(i * 150 + 8, 55)}}
        for i in range(80)]
    a = build_items(feats, seed=1, n_unchanged=5)
    b = build_items(feats, seed=1, n_unchanged=5)
    assert [x["id"] for x in a] == [x["id"] for x in b] and [x["arm"] for x in a] == [x["arm"] for x in b], "must be deterministic"
    assert [x["id"] for x in a] != sorted(x["id"] for x in a), "must be shuffled"
    non_unch = sum(f["properties"]["class"] != "unchanged" for f in feats)
    assert len(a) == non_unch + 5, (len(a), non_unch)
    assert sum(x["arm"] == "blind" for x in a) == round(BLIND_SHARE * len(a))
    assert len(build_items(feats, 1, 5, skip_open_new=True)) < len(a)
    assert [x["id"] for x in build_items(feats, seed=2, n_unchanged=5)] != [x["id"] for x in a], "a new seed must reorder"
    im_ = Image.new("RGB", (2000, 400), (200, 190, 170))
    for p in (feats[0]["properties"], feats[6]["properties"], feats[5]["properties"]):
        for v in ("overlay", "clean"):
            png = render(im_, p, v, (1.0, 0.0))
            assert png[:4] == b"\x89PNG"
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "classes.geojson").write_text(json.dumps({"features": feats, "north_px": [1.0, 0.0]}))
        args = {"seed": 1, "n_unchanged": 5, "skip_open_new": False, "reviewer": "t", "out": Path(d)}
        st, items = load_state(args, lambda: im_, Path(d) / "classes.geojson")
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(st))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        get = lambda u: urllib.request.urlopen(base + u).read()

        def post(u, o):
            return urllib.request.urlopen(urllib.request.Request(base + u, json.dumps(o).encode(), {"Content-Type": "application/json"})).read()

        assert b"V1" in get("/")
        n1 = json.loads(get("/next"))
        assert n1["id"] == items[0]["id"] and n1["done"] == 0
        assert get(f"/img/{n1['id']}/overlay")[:4] == b"\x89PNG" and get(f"/img/{n1['id']}/clean")[:4] == b"\x89PNG"
        time.sleep(0.05)
        # blind arm: no class in /next, and a bare 'y' for V2 is refused
        bl = next(it for it in items if it["arm"] == "blind")
        sh = next(it for it in items if it["arm"] == "shown")
        st.shown[bl["id"]] = time.time()
        assert bl["arm"] == "blind"
        try:
            post("/verdict", {"id": bl["id"], "v1": "y", "v2": "y"})
            raise AssertionError("blind V2 'y' must be refused")
        except urllib.error.HTTPError as e:
            assert e.code == 400
        post("/verdict", {"id": sh["id"], "v1": "p", "v2": "y"})
        post("/verdict", {"id": bl["id"], "v1": "n", "v2": "split"})
        rows = rr.load(Path(d) / "verdicts.jsonl")
        r_sh, r_bl = rows[str(sh["id"])], rows[str(bl["id"])]
        assert r_sh["task"] == TASK and r_sh["proposal_shown"] is True and r_bl["proposal_shown"] is False
        assert r_sh["readings"]["class_read"] == sh["p"]["class"] and r_bl["readings"]["class_read"] == "split"
        assert r_sh["bound"] != r_bl["bound"] and r_sh["decided_at"] >= r_sh["shown_at"]
        nb = json.loads(get("/next"))
        done_before = nb["done"]
        assert done_before == 2
        assert (nb["cls"] is None) == (nb["arm"] == "blind"), "no class may be sent on the blind arm"
        post("/undo", {})
        assert json.loads(get("/next"))["done"] == 1, "undo must reopen the last finished item"
        assert len(rr.load(Path(d) / "verdicts.jsonl")) == 2, "undo appends, never rewrites"
        s = json.loads(get("/stats"))
        assert s["n"] == 1
        srv.shutdown()
    print("then-now review self-check OK")


if __name__ == "__main__":
    a = sys.argv[1:]
    opt = lambda k, d, t=str: t(a[a.index(k) + 1]) if k in a else d
    if "--self-check" in a:
        _self_check()
    elif "--stats" in a:
        print(json.dumps(stats(OUT / "verdicts.jsonl"), indent=1))
    else:
        serve({"port": opt("--port", 8793, int), "seed": opt("--seed", 1, int), "n_unchanged": opt("--n-unchanged", 30, int),
               "reviewer": opt("--reviewer", "tue"), "skip_open_new": "--skip-open-new" in a, "out": OUT,
               "image": RES / MAP_ID / "native.png"})
