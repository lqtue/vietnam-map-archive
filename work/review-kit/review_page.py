"""The template for a VMA manual review page: one item at a time, keyboard verdicts, timed, blind arm.

Every page so far (place-links confirm.py, then-now review.py, paper_audit_100k.py serve) rebuilt the same
server, session and page, and each had to learn the same lessons. They live here once:
  - the page states its QUESTION above every item (a reviewer once could not tell what to do);
  - "See today" links (o v w: 1882-over-today on maparchive.vn, satellite, street view) when the item
    has lon/lat, built from the item's own position, never from the machine's proposal;
  - a click is stored in the IMAGE'S own pixels and its marker is drawn with the same measure, the
    content box of the <img> (a marker placed in % of the wrapper box once landed 15 px off);
  - a fixed blind arm: a share of the items that have a proposal show none, and the render is told so;
  - order, arms and seeds are fixed in session.json the first time and refuse to drift;
  - one review_record line per verdict, undo appends, resume at the first item without a verdict.

A new page is one small file:

    from review_page import serve
    TASK = {
        "name": "my-task",                       # review_record task
        "method": "my_script@<hash or version>", # goes into every bound: a new version stales old verdicts
        "question": "Is this road outline right?",
        "keys": {"y": ("yes", "right"), "n": ("no", "wrong"), "?": ("unsure", "can't tell")},
        "views": ["close", "context"],           # one <img> each, in this order
        "render": lambda item, view, shown: pil_image,   # shown=False on the blind arm: draw no proposal
        "judged": lambda item: item["geom"],     # exactly what the verdict approves (hashed into bound)
        "points": 0,                             # max clicks per item (0 = no clicking); see readings.points
        "point_label": False,                    # True: each click asks for typed text (a tick's label)
        "needs_points": {"no"},                  # verdict values refused until at least one click exists
    }
    serve(TASK, items, out_dir, port=87xx)       # items: [{"id", "title", "lon"?, "lat"?, "proposal"?: str}]

`proposal` is the machine's suggestion as text; the page shows it only on the shown arm, and an item
without one is never blind. Clicks land in readings {"points": [{"view", "x", "y", "label"}]} in the
rendered image's pixels; convert them in your scoring step (the render is fixed by `method`).

  python3 review_page.py --self-check    no network: serves a synthetic task, posts verdicts, undoes
  python3 review_page.py --demo          the synthetic task on http://127.0.0.1:8799, to try the keys
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_record import bound as bound_hash, load, record  # noqa: E402

MAP_1882 = "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b"  # ponytail: the "over today" link opens this sheet; pass item["map"] for another


class Session:
    def __init__(self, task: dict, items: list[dict], out, reviewer="tue", seed=20261013, blind_frac=0.2, new=False):
        self.t, self.reviewer = task, reviewer
        self.items = {str(i["id"]): i for i in items}
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.vf, self.lock = self.out / "verdicts.jsonl", threading.Lock()
        with_p = sorted(i for i, it in self.items.items() if it.get("proposal"))
        h = hashlib.sha1(json.dumps([sorted(self.items), with_p]).encode()).hexdigest()[:12]
        sf = self.out / "session.json"
        if sf.exists() and new:
            sf.rename(sf.with_name(f"session.{int(time.time())}.json"))
        if sf.exists():
            s = json.loads(sf.read_text())
            if s["ids_hash"] != h:
                raise SystemExit("items changed since session.json was written; the arms must not drift (new=True starts over)")
        else:
            blind = set(random.Random(seed).sample(with_p, round(blind_frac * len(with_p))))
            order = sorted(self.items)
            random.Random(seed + 1).shuffle(order)
            s = {"written": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "task": task["name"], "method": task["method"],
                 "seed": seed, "blind_fraction": blind_frac, "ids_hash": h, "order": order,
                 "arms": {i: ("blind" if i in blind else "shown" if i in with_p else "none") for i in order}}
            sf.write_text(json.dumps(s, indent=1))
        self.arms, self.order = s["arms"], s["order"]

    def done(self) -> dict:
        return {k: v for k, v in load(self.vf).items() if not v["verdicts"].get("undone")}

    def nxt(self) -> dict:
        done = self.done()
        todo = [i for i in self.order if i not in done]
        head = {"done": len(done), "total": len(self.items)}
        if not todo:
            return {"id": None, **head}
        it = self.items[todo[0]]
        return {"id": todo[0], **head, "title": it.get("title", todo[0]), "lon": it.get("lon"), "lat": it.get("lat"),
                "map": it.get("map", MAP_1882),
                "proposal": it.get("proposal") if self.arms[todo[0]] == "shown" else None}

    def image(self, iid: str, view: str) -> bytes:
        if view not in self.t["views"]:
            raise KeyError(view)
        img = self.t["render"](self.items[iid], view, self.arms[iid] == "shown")
        if isinstance(img, bytes):
            return img
        b = BytesIO()
        img.save(b, "PNG")
        return b.getvalue()

    def submit(self, b: dict) -> dict:
        with self.lock:
            iid = str(b["id"])
            it = self.items[iid]
            vals = {v for v, _ in self.t["keys"].values()}
            if b.get("value") not in vals:
                raise ValueError(f"unknown verdict {b.get('value')!r}")
            pts = [{"view": p["view"], "x": round(float(p["x"]), 1), "y": round(float(p["y"]), 1),
                    "label": str(p.get("label", "")).strip()} for p in b.get("points") or []]
            if len(pts) > self.t.get("points", 0) or any(p["view"] not in self.t["views"] for p in pts):
                raise ValueError("too many clicks, or a click outside the views")
            if self.t.get("point_label") and any(not p["label"] for p in pts):
                raise ValueError("type the label for every click, or remove the click (Esc)")
            if b["value"] in self.t.get("needs_points", ()) and not pts:
                raise ValueError("click on the image first")
            t1 = float(b.get("decided_at") or time.time())
            t0 = min(float(b.get("shown_at") or t1), t1)
            return record(self.vf, task=self.t["name"], item_id=iid,
                          bound=bound_hash(self.t["judged"](it), self.t["method"]), reviewer=self.reviewer,
                          order_idx=len(self.done()), shown_at=t0, decided_at=t1,
                          proposal_shown=self.arms[iid] == "shown",
                          verdicts={"arm": self.arms[iid], "value": b["value"]},
                          readings={"points": pts} if pts else {}, note=(b.get("note") or "").strip())

    def undo(self) -> dict | None:
        with self.lock:
            cur = self.done()
            if not cur:
                return None
            r = max(cur.values(), key=lambda r: r["written_at"])
            t = time.time()
            return record(self.vf, task=self.t["name"], item_id=r["item_id"], bound=r["bound"], reviewer=self.reviewer,
                          order_idx=r["order_idx"], shown_at=t, decided_at=t, proposal_shown=r["proposal_shown"],
                          verdicts={"undone": True})


PAGE = """<!doctype html><meta charset=utf-8><title>%(name)s</title>
<style>body{font:15px system-ui;margin:12px;background:#222;color:#eee}kbd{background:#444;padding:2px 6px;border-radius:3px}
a{color:#8cf}#row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-start}.v{position:relative}
.v img{display:block;max-width:min(900px,90vw);border:1px solid #555;cursor:%(cursor)s}
.m{position:absolute;box-sizing:border-box;width:16px;height:16px;margin:-8px 0 0 -8px;border:2px solid #f0f;border-radius:50%%;pointer-events:none}
.m span{position:absolute;left:14px;top:-4px;background:#000c;color:#fff;padding:0 4px;font-size:12px;white-space:nowrap}
input{width:340px;background:#111;color:#eee;border:1px solid #666;padding:4px}#msg{color:#ffb347;min-height:1.3em}
.dim{color:#999}#q{font-size:17px;margin:4px 0 8px}#prop{background:#2c2c2c;border-left:6px solid #e61e1e;padding:4px 8px}</style>
<p id=s></p><h3 id=t></h3><p id=q>%(question)s</p><p id=lk></p><p id=prop hidden></p>
<div id=row></div><p id=pt class=dim></p><p><input id=lab placeholder="type the label, Enter" hidden></p>
<p><input id=note placeholder="t  note (optional)"></p><p id=msg></p><p class=dim>%(legend)s</p>
<script>
const T=%(cfg)s;let item=null,pts=[],shownAt=0,loaded=0,pending=null;const $=id=>document.getElementById(id);
async function next(){item=await (await fetch('/next')).json();pts=[];pending=null;$('msg').textContent='';$('note').value='';
 $('s').textContent=item.id?`${item.done} / ${item.total} done`:`all ${item.total} done - close the tab`;$('t').textContent=item.title||'';
 const p=$('prop');p.hidden=!item.proposal;p.textContent=item.proposal?'Machine suggests: '+item.proposal:'';
 $('lk').innerHTML=item.id&&item.lon!=null?`See today: <a target=_blank href="https://maparchive.vn/explore?map=${item.map}&at=${item.lon},${item.lat}">old map over today (o)</a> &middot; <a target=_blank href="https://www.google.com/maps/@${item.lat},${item.lon},19z/data=!3m1!1e3">satellite (v)</a> &middot; <a target=_blank href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${item.lat},${item.lon}">street view (w)</a>`:'';
 loaded=0;$('row').innerHTML=item.id?T.views.map(v=>`<div class=v data-v=${v}><img src="/img/${item.id}/${v}.png"></div>`).join(''):'';
 document.querySelectorAll('.v img').forEach(img=>{img.onload=()=>{if(++loaded===T.views.length)shownAt=Date.now()/1000};
  img.onclick=e=>{if(!T.points)return;if(pts.length>=T.points){$('msg').textContent=`at most ${T.points} clicks; u-key undoes a verdict, Esc removes the last click`;return}
   // the image's own pixels: content box of the <img>, scaled to its natural size (border excluded)
   const r=img.getBoundingClientRect();pts.push({view:img.parentNode.dataset.v,x:(e.clientX-r.left-img.clientLeft)/img.clientWidth*img.naturalWidth,
    y:(e.clientY-r.top-img.clientTop)/img.clientHeight*img.naturalHeight,label:''});draw();if(T.point_label){pending=pts.length-1;$('lab').hidden=false;$('lab').value='';$('lab').focus()}}});draw()}
function draw(){document.querySelectorAll('.m').forEach(m=>m.remove());pts.forEach(p=>{const box=document.querySelector(`.v[data-v="${p.view}"]`),img=box.querySelector('img'),m=document.createElement('div');
 m.className='m';m.style.left=(img.offsetLeft+img.clientLeft+p.x/img.naturalWidth*img.clientWidth)+'px';m.style.top=(img.offsetTop+img.clientTop+p.y/img.naturalHeight*img.clientHeight)+'px';
 if(p.label)m.innerHTML=`<span>${p.label.replace(/</g,'&lt;')}</span>`;box.appendChild(m)});
 $('pt').textContent=T.points?`clicks: ${pts.length} / ${T.points}  (Esc removes the last)`:''}
async function send(value){if(!item.id)return;const r=await fetch('/verdict',{method:'POST',body:JSON.stringify({id:item.id,value,points:pts,note:$('note').value,shown_at:shownAt||Date.now()/1000,decided_at:Date.now()/1000})});
 if(!r.ok){$('msg').textContent=await r.text();return}next()}
$('lab').onkeydown=e=>{e.stopPropagation();if(e.key==='Enter'){pts[pending].label=$('lab').value;$('lab').hidden=true;$('lab').blur();pending=null;draw()}
 if(e.key==='Escape'){pts.splice(pending,1);$('lab').hidden=true;$('lab').blur();pending=null;draw()}};
$('note').onkeydown=e=>{e.stopPropagation();if(e.key==='Enter'||e.key==='Escape')$('note').blur()};
document.onkeydown=async e=>{if(e.metaKey||e.ctrlKey||e.altKey)return;const k=e.key;
 if(k==='t'){e.preventDefault();$('note').focus();return}
 if(k==='Escape'){pts.pop();draw();return}
 if(k==='u'){await fetch('/undo',{method:'POST'});return next()}
 const lk={o:0,v:1,w:2}[k];if(lk!==undefined&&!(k in T.keys)){const l=$('lk').querySelectorAll('a')[lk];if(l)window.open(l.href,'_blank');return}
 if(k in T.keys)send(T.keys[k])};
next();
</script>"""


def page(task: dict) -> str:
    legend = " &nbsp; ".join(f"<kbd>{k}</kbd> {lab}" for k, (_, lab) in task["keys"].items())
    legend += " &nbsp; <kbd>u</kbd> undo &nbsp; <kbd>t</kbd> note"
    cfg = {"views": task["views"], "points": task.get("points", 0), "point_label": bool(task.get("point_label")),
           "keys": {k: v for k, (v, _) in task["keys"].items()}}
    return PAGE % {"name": task["name"], "question": task["question"], "legend": legend,
                   "cursor": "crosshair" if task.get("points") else "default", "cfg": json.dumps(cfg)}


def make_server(sess: Session, port: int) -> ThreadingHTTPServer:
    html = page(sess.t).encode()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, body: bytes, ctype="application/json", code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path).path
            try:
                if u == "/":
                    return self.send(html, "text/html; charset=utf-8")
                if u == "/next":
                    return self.send(json.dumps(sess.nxt(), ensure_ascii=False).encode())
                if u.startswith("/img/") and u.endswith(".png"):
                    _, _, iid, view = u[:-4].split("/")
                    return self.send(sess.image(iid, view), "image/png")
            except KeyError:
                pass
            self.send(b"not found", "text/plain", 404)

        def do_POST(self):
            u = urlparse(self.path).path
            try:
                if u == "/verdict":
                    body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                    return self.send(json.dumps(sess.submit(body), ensure_ascii=False).encode())
                if u == "/undo":
                    return self.send(json.dumps(sess.undo()).encode())
            except (ValueError, KeyError) as e:
                return self.send(str(e).encode(), "text/plain", 400)
            self.send(b"not found", "text/plain", 404)

    return ThreadingHTTPServer(("127.0.0.1", port), H)


def serve(task: dict, items: list[dict], out, port: int, **session_kw):
    sess = Session(task, items, out, **session_kw)
    srv = make_server(sess, port)
    blind = sum(a == "blind" for a in sess.arms.values())
    print(f"http://127.0.0.1:{port}  ({len(sess.items)} items, {blind} blind, verdicts -> {sess.vf})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped; run again to resume")


# --------------------------------------------------------------------------- demo and self-check

def demo_task() -> tuple[dict, list[dict]]:
    from PIL import Image, ImageDraw

    def render(item, view, shown):
        im = Image.new("RGB", (400, 300) if view == "close" else (300, 300), (235, 225, 200))
        d = ImageDraw.Draw(im)
        d.rectangle([150, 100, 250, 200], outline=(0, 0, 0), width=3)
        if shown and item.get("proposal"):
            d.rectangle([140, 90, 260, 210], outline=(230, 30, 30), width=2)
        return im

    task = {"name": "demo", "method": "demo@1", "question": "Is the black square on the printed square? Click its NW corner.",
            "keys": {"y": ("yes", "yes"), "n": ("no", "no"), "?": ("unsure", "can't tell")}, "views": ["close", "context"],
            "render": render, "judged": lambda it: it["id"], "points": 2, "point_label": False, "needs_points": {"no"}}
    items = [{"id": f"i{k}", "title": f"Item {k}", "lon": 106.7049, "lat": 10.7847,
              **({"proposal": "the red outline"} if k < 5 else {})} for k in range(8)]
    return task, items


def self_check():
    import tempfile
    from urllib.request import Request, urlopen

    task, items = demo_task()
    with tempfile.TemporaryDirectory() as d:
        s = Session(task, items, d, blind_frac=0.4)
        assert sorted(s.arms.values()).count("blind") == 2 and sorted(s.arms.values()).count("none") == 3
        assert all(s.arms[i["id"]] == "none" for i in items if not i.get("proposal")), "no proposal, never blind"
        assert Session(task, items, d, blind_frac=0.4).order == s.order, "order must not drift on restart"
        try:
            Session(task, items[:-1], d)
            raise AssertionError("changed items must refuse")
        except SystemExit:
            pass
        b = next(i for i, a in s.arms.items() if a == "blind")
        sh = next(i for i, a in s.arms.items() if a == "shown")
        assert s.image(b, "close") != s.image(sh, "close"), "the blind render must not draw the proposal"
        srv = make_server(s, 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        get = lambda p: urlopen(base + p).read()
        post = lambda p, body: urlopen(Request(base + p, data=json.dumps(body).encode(), method="POST")).read()
        assert b"Is the black square" in get("/") and b"clientLeft" in get("/")
        n = json.loads(get("/next"))
        assert n["id"] == s.order[0] and (n["proposal"] is None) == (s.arms[n["id"]] != "shown")
        assert get(f"/img/{n['id']}/close.png")[:8] == b"\x89PNG\r\n\x1a\n"
        for bad in ({"id": n["id"], "value": "no"},  # needs a click
                    {"id": n["id"], "value": "maybe"},
                    {"id": n["id"], "value": "yes", "points": [{"view": "close", "x": 1, "y": 1}] * 3}):
            try:
                post("/verdict", bad)
                raise AssertionError(f"must refuse {bad}")
            except Exception as e:
                assert getattr(e, "code", None) == 400, e
        post("/verdict", {"id": n["id"], "value": "no", "points": [{"view": "close", "x": 150, "y": 100}],
                          "shown_at": 10, "decided_at": 14})
        r = load(Path(d) / "verdicts.jsonl")[n["id"]]
        assert r["readings"]["points"][0]["x"] == 150 and r["decided_at"] - r["shown_at"] == 4
        assert r["proposal_shown"] == (s.arms[n["id"]] == "shown") and r["task"] == "demo"
        assert json.loads(get("/next"))["id"] == s.order[1], "resume moves on"
        post("/undo", {})
        assert json.loads(get("/next"))["id"] == s.order[0], "undo brings the item back"
        srv.shutdown()
    print("review_page self-check OK")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        self_check()
    elif "--demo" in sys.argv:
        import tempfile

        t, its = demo_task()
        serve(t, its, Path(tempfile.mkdtemp()), 8799)
    else:
        print(__doc__)
