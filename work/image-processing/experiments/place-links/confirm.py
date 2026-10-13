#!/usr/bin/env python3
"""Confirm place links: the 1882 label, the machine's up-to-3 candidates, one verdict per item, timed.

  confirm.py                 serve http://127.0.0.1:8792 (needs build.py's items.json and the native scan)
  confirm.py --spot          write 10 example crops (5 shown, 5 blind) to place-links/spot/ and exit
  confirm.py --self-check    no network, no data files

Each page shows the label on the sheet as printed (text upright; north is to the right on this sheet, so
the north arrow is drawn from the georeference), the label box outlined, a close-up and a context view, and,
on the shown arm, the candidates as numbered markers with their outlines.

Keys   1 2 3  pick a candidate (again to unpick)        /  search the pool within 300 m (Enter picks the first hit)
       then the relation:  s same building · n same site, new building · m moved
                           g gone · x no modern equivalent · ?  unsure     (s n m need a pick)
       u undo the last verdict · t note (Enter or Esc leaves it)

Blind arm: a fixed random 20% of the items that have a candidate show none. Seeds, the arms and the order
are fixed in session.json the first time and never drift. Order is random, not by score.
Every verdict is one review_record line in verdicts.jsonl (task place-link, item_id = ocr_labels.id).
Undo appends {"undone": true} for the item; the last line for an item wins.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "work" / "review-kit"))
from review_record import bound as bound_hash, load, record  # noqa: E402

MAP = "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b"
OUT = ROOT / "work" / "image-processing" / "results" / "prior" / MAP / "place-links"
NATIVE = ROOT / "work" / "image-processing" / "results" / MAP / "native.png"
RELATIONS = {"s": "same_building", "n": "same_site_new_building", "m": "moved", "g": "gone", "x": "none", "?": "unsure"}
NEEDS_PICK = {"same_building", "same_site_new_building", "moved"}
VIEWS = {"close": (520, 800, 50), "context": (1800, 900, 200)}  # half-size in source px, output px, scale-bar metres
COLOURS = [(230, 30, 30), (20, 90, 230), (20, 160, 60)]


# --------------------------------------------------------------------------- arms and order

def assign_arms(with_cands: list[str], without: list[str], seed: int, frac: float) -> dict[str, str]:
    """blind: a fixed random frac of the items that have a candidate; shown: the rest of those; nocand: the others."""
    ids = sorted(with_cands)
    blind = set(random.Random(seed).sample(ids, round(frac * len(ids))))
    return {**{i: ("blind" if i in blind else "shown") for i in ids}, **{i: "nocand" for i in without}}


def make_order(ids: list[str], seed: int) -> list[str]:
    o = sorted(ids)
    random.Random(seed).shuffle(o)
    return o


def fold(s: str) -> str:
    import unicodedata
    import re

    s = unicodedata.normalize("NFD", s or "").replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn").lower()).strip()


# --------------------------------------------------------------------------- crops

def render(im, item: dict, view: str, show_cands: bool, mpp: float, north: tuple[float, float]):
    """The crop, as printed (no rotation). Blind arm: show_cands False draws nothing of the machine's."""
    from PIL import Image, ImageDraw, ImageFont

    half, out, bar_m = VIEWS[view]
    cx, cy = item["px"]
    x0, y0 = cx - half, cy - half
    z = out / (2 * half)
    c = im.crop((round(x0), round(y0), round(x0) + 2 * half, round(y0) + 2 * half)).resize((out, out), Image.LANCZOS)
    d = ImageDraw.Draw(c)
    big = ImageFont.load_default(size=22)
    to = lambda p: ((p[0] - round(x0)) * z, (p[1] - round(y0)) * z)
    if item.get("box"):
        bx, by, bw, bh = item["box"]
        (a, b), (e, f) = to((bx, by)), to((bx + bw, by + bh))
        d.rectangle([a, b, e, f], outline=(255, 210, 0), width=3)
    if item.get("pos_from") == "px":
        px, py = to(item["px"])
        d.ellipse([px - 7, py - 7, px + 7, py + 7], outline=(255, 210, 0), width=3)
    if show_cands:
        for k, cand in enumerate(item["cands"]):
            col = COLOURS[k % 3]
            if cand.get("outline_px"):
                pts = [to(p) for p in cand["outline_px"]]
                d.line(pts + [pts[0]] if len(pts) > 2 else pts, fill=col, width=2)
            mx, my = to(cand["px"])
            d.ellipse([mx - 13, my - 13, mx + 13, my + 13], fill=col, outline=(255, 255, 255), width=2)
            d.text((mx, my), str(k + 1), fill=(255, 255, 255), font=big, anchor="mm")
    # north arrow: from the georeference, not from the picture
    nx, ny = north
    ox, oy = out - 70, out - 70
    tail, head = (ox - nx * 36, oy - ny * 36), (ox + nx * 36, oy + ny * 36)
    d.ellipse([ox - 52, oy - 52, ox + 52, oy + 52], fill=(255, 255, 255))
    d.line([tail, head], fill=(0, 0, 0), width=5)
    px_, py_ = -ny, nx
    d.polygon([head, (head[0] - nx * 16 + px_ * 9, head[1] - ny * 16 + py_ * 9),
               (head[0] - nx * 16 - px_ * 9, head[1] - ny * 16 - py_ * 9)], fill=(0, 0, 0))
    d.text((head[0] + nx * 14, head[1] + ny * 14), "N", fill=(0, 0, 0), font=big, anchor="mm")
    # scale bar
    L = bar_m / mpp * z
    d.rectangle([12, out - 40, 12 + L + 12, out - 12], fill=(255, 255, 255))
    d.line([(18, out - 22), (18 + L, out - 22)], fill=(0, 0, 0), width=4)
    d.text((18, out - 36), f"{bar_m} m", fill=(0, 0, 0), font=ImageFont.load_default(size=14))
    return c


def png(img) -> bytes:
    b = BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


# --------------------------------------------------------------------------- the session

class Session:
    def __init__(self, doc: dict, out: Path, reviewer: str = "tue", seed_arm: int = 20261012, seed_order: int = 20261013,
                 frac: float = 0.2, new: bool = False):
        self.meta, self.out, self.reviewer = doc["meta"], Path(out), reviewer
        self.items = {i["id"]: i for i in doc["items"]}
        self.out.mkdir(parents=True, exist_ok=True)
        self.vf = self.out / "verdicts.jsonl"
        self.lock = threading.Lock()
        wc = [i for i, it in self.items.items() if it["cands"]]
        wo = [i for i, it in self.items.items() if not it["cands"]]
        h = hashlib.sha1(json.dumps([sorted(wc), sorted(wo)]).encode()).hexdigest()[:12]
        sf = self.out / "session.json"
        if sf.exists() and new:
            sf.rename(sf.with_name(f"session.{int(time.time())}.json"))
        if sf.exists():
            s = json.loads(sf.read_text())
            if s["ids_hash"] != h:
                raise SystemExit("items.json changed since session.json was written (different items or candidates); "
                                 "the arms must not drift: pass --new-session to start over")
        else:
            arms = assign_arms(wc, wo, seed_arm, frac)
            s = {"written": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "seed_arm": seed_arm, "seed_order": seed_order,
                 "blind_fraction": frac, "ids_hash": h, "n_items": len(self.items), "arms": arms,
                 "order": make_order(list(self.items), seed_order),
                 "note": "blind = fixed random share of items that have a candidate; nocand = none to hide"}
            sf.write_text(json.dumps(s, indent=1))
        self.arms, self.order = s["arms"], s["order"]

    # state ---------------------------------------------------------------
    def done(self) -> dict:
        return {k: v for k, v in load(self.vf).items() if not v["verdicts"].get("undone")}

    def nxt(self) -> dict:
        done = self.done()
        todo = [i for i in self.order if i not in done]
        if not todo:
            return {"id": None, "done": len(done), "total": len(self.items)}
        it = self.items[todo[0]]
        shown = self.arms[it["id"]] == "shown"
        return {"id": it["id"], "done": len(done), "total": len(self.items), "category": it["category"], "text": it["text"], "lon": it["lon"], "lat": it["lat"],
                "names": it["names"], "cands": [{"k": k + 1, "name": c["name"], "source": c["source"], "dist_m": c["dist_m"],
                                                 "wikidata": c["wikidata"], "osm": c["osm"]}
                                                for k, c in enumerate(it["cands"])] if shown else []}

    def search(self, iid: str, q: str, n: int = 8) -> list[dict]:
        it, q = self.items[iid], fold(q)
        hits = [p for p in it["pool300"] if not q or any(q in fold(x) for x in p["names"])]
        return [{"id": p["id"], "name": p["name"], "source": p["source"], "dist_m": p["dist_m"], "wikidata": p["wikidata"]}
                for p in sorted(hits, key=lambda p: p["dist_m"])[:n]]

    def target(self, c: dict) -> dict:
        return {"source": c["source"], "id": c["osm"] or ("tasco:%d" % c["tasco_ids"][0]), "name": c["name"],
                "lng": c["lon"], "lat": c["lat"], "wikidata": c.get("wikidata"), "osm_alts": c.get("osm_alts", []),
                "tasco_ids": c.get("tasco_ids", [])}

    def bound(self, it: dict) -> str:
        judged = {"label_id": it["id"], "label_px": it["px"], "radius_m": self.meta["radius_m"],
                  "cands": [{"id": c["id"], "name": c["name"], "lon": c["lon"], "lat": c["lat"]} for c in it["cands"]]}
        return bound_hash(judged, self.meta["method"])

    def submit(self, b: dict, now: float | None = None) -> dict:
        with self.lock:
            iid = b["id"]
            it, arm = self.items[iid], self.arms[iid]
            rel = RELATIONS.get(b["relation"], b["relation"])
            if rel not in RELATIONS.values():
                raise ValueError(f"unknown relation {b['relation']!r}")
            tgt, via, pick = None, None, None
            if b.get("search_id"):
                p = next((p for p in it["pool300"] if p["id"] == b["search_id"]), None)
                if p is None:
                    raise ValueError("not in this item's pool")
                tgt, via = self.target(p), "search"
            elif b.get("pick"):
                if arm != "shown":
                    raise ValueError("no candidates were shown on this item")
                pick = int(b["pick"])
                tgt, via = self.target(it["cands"][pick - 1]), "candidate"
            if rel == "none":
                tgt, via, pick = None, None, None
            if rel in NEEDS_PICK and tgt is None:
                raise ValueError("pick a place first (1 2 3 or / to search)")
            t1 = float(b.get("decided_at") or now or time.time())
            t0 = min(float(b.get("shown_at") or t1), t1)
            return record(self.vf, task="place-link", item_id=iid, bound=self.bound(it), reviewer=self.reviewer,
                          order_idx=len(self.done()), shown_at=t0, decided_at=t1,
                          proposal_shown=arm == "shown" and bool(it["cands"]),
                          verdicts={"arm": arm, "pick": pick, "pick_via": via, "relation": rel, "target": tgt},
                          note=(b.get("note") or "").strip())

    def undo(self, now: float | None = None) -> dict | None:
        with self.lock:
            if not self.vf.exists():
                return None
            lines = [json.loads(x) for x in self.vf.read_text(encoding="utf-8").splitlines() if x.strip()]
            cur = self.done()
            for r in reversed(lines):
                if r["verdicts"].get("undone") or cur.get(r["item_id"], {}).get("written_at") != r["written_at"]:
                    continue
                t = now or time.time()
                return record(self.vf, task="place-link", item_id=r["item_id"], bound=r["bound"], reviewer=self.reviewer,
                              order_idx=r["order_idx"], shown_at=t, decided_at=t, proposal_shown=r["proposal_shown"],
                              verdicts={"undone": True}, note="")
            return None


# --------------------------------------------------------------------------- web

PAGE = """<!doctype html><meta charset=utf-8><title>Place links</title>
<style>body{font:15px system-ui;margin:12px;background:#222;color:#eee}kbd{background:#444;padding:2px 6px;border-radius:3px}
#row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-start}img{border:1px solid #555}
.c{padding:4px 8px;margin:3px 0;border-left:6px solid;background:#2c2c2c;cursor:pointer}.c.sel{background:#444}
#res div{padding:3px 8px;cursor:pointer}#res div:hover{background:#444}#q,#note{width:340px;background:#111;color:#eee;border:1px solid #666;padding:4px}
#msg{color:#ffb347;min-height:1.3em}.dim{color:#999}</style>
<p id=s></p><div id=row><img id=a width=800 height=800><div style="max-width:920px"><img id=b width=900 height=900></div>
<div style="max-width:420px"><h3 id=t></h3><p>What is this 1882 place today? 1) pick a match, 2) say how it relates.</p><p id=lk></p><div id=cands></div><p><input id=q placeholder="/  search a place within 300 m"><div id=res></div></p>
<p>picked: <b id=pk>nothing</b></p><p><input id=note placeholder="t  note (optional)"></p><p id=msg></p>
<p class=dim><kbd>1</kbd><kbd>2</kbd><kbd>3</kbd> pick &nbsp; <kbd>/</kbd> search<br>
<kbd>s</kbd> same building &nbsp; <kbd>n</kbd> same site, new building &nbsp; <kbd>m</kbd> moved<br>
<kbd>g</kbd> gone &nbsp; <kbd>x</kbd> none &nbsp; <kbd>?</kbd> unsure &nbsp; <kbd>u</kbd> undo</p></div></div>
<script>
const MAP='0e02b9d9-9d40-4cca-8e41-8c8373d54d3b';const COL=['#e61e1e','#145ae6','#14a03c'];
let cur=null,item=null,pick=null,sid=null,sname='',shownAt=0,loaded=0;
const $=id=>document.getElementById(id);
function loadedOne(){if(++loaded===2)shownAt=Date.now()/1000}
a.onload=b.onload=loadedOne;
async function next(){item=await (await fetch('/next')).json();cur=item.id;pick=null;sid=null;
 $('s').textContent=cur?`${item.done} / ${item.total} done`:`all ${item.total} done - close the tab`;
 $('msg').textContent='';$('note').value='';$('q').value='';$('res').innerHTML='';render();
 if(cur){loaded=0;a.src=`/img/${cur}/close.png`;b.src=`/img/${cur}/context.png`}else{a.removeAttribute('src');b.removeAttribute('src')}}
function render(){ $('t').textContent=cur?`${item.text}`:'';
 $('lk').innerHTML=cur?`See today: <a target=_blank href="https://maparchive.vn/explore?map=${MAP}&at=${item.lon},${item.lat}">1882 over today (o)</a> &middot; <a target=_blank href="https://www.google.com/maps/@${item.lat},${item.lon},19z/data=!3m1!1e3">satellite (v)</a> &middot; <a target=_blank href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${item.lat},${item.lon}">street view (w)</a>`:'';
 $('cands').innerHTML=(item.cands||[]).length?'':'<p class=dim>No suggestions here. Press / and type a name you know, or g gone, x none, ? unsure.</p>';
 $('cands').innerHTML+=(item.cands||[]).map(c=>`<div class=c data-k=${c.k} style="border-color:${COL[c.k-1]}" onclick="doPick(${c.k})">
 <b>${c.k}</b> ${c.name}<br><span class=dim>${c.source} &middot; ${c.dist_m} m${c.wikidata?' &middot; '+c.wikidata:''}</span></div>`).join('');
 $('pk').textContent=sid?sname+' (search)':pick?item.cands[pick-1].name:'nothing';
 document.querySelectorAll('.c').forEach(e=>e.classList.toggle('sel',+e.dataset.k===pick))}
function doPick(k){if(!item.cands||!item.cands[k-1])return;sid=null;pick=pick===k?null:k;render()}
async function doSearch(){const r=await (await fetch(`/search?id=${cur}&q=${encodeURIComponent($('q').value)}`)).json();
 $('res').innerHTML=r.map((p,i)=>`<div data-i=${i}>${p.name}<br><span class=dim>${p.source} &middot; ${p.dist_m} m</span></div>`).join('');
 $('res').dataset.r=JSON.stringify(r);
 [...$('res').children].forEach((e,i)=>e.onclick=()=>choose(r[i]))}
function choose(p){sid=p.id;sname=p.name;pick=null;$('q').blur();$('res').innerHTML='';render()}
async function send(rel){ if(!cur)return;
 const body={id:cur,relation:rel,pick:pick,search_id:sid,note:$('note').value,shown_at:shownAt,decided_at:Date.now()/1000};
 const r=await fetch('/verdict',{method:'POST',body:JSON.stringify(body)});
 if(!r.ok){$('msg').textContent=(await r.json()).error;return}next()}
$('q').oninput=doSearch;
document.onkeydown=async e=>{
 if(e.target.id==='q'){if(e.key==='Enter'){const r=JSON.parse($('res').dataset.r||'[]');if(r[0])choose(r[0])}if(e.key==='Escape')$('q').blur();return}
 if(e.target.id==='note'){if(e.key==='Enter'||e.key==='Escape')$('note').blur();return}
 if(e.metaKey||e.ctrlKey||e.altKey)return;
 const k=e.key;
 if(k==='/'){e.preventDefault();$('q').focus();doSearch();return}
 if(k==='t'){e.preventDefault();$('note').focus();return}
 if(k==='u'){await fetch('/undo',{method:'POST'});return next()}
 const lk={o:0,v:1,w:2}[k];if(lk!==undefined){const l=$('lk').querySelectorAll('a')[lk];if(l)window.open(l.href,'_blank');return}
 if(k.length===1&&'123'.includes(k))return doPick(+k);
 const rel={s:'s',n:'n',m:'m',g:'g',x:'x','?':'?'}[k];if(rel)send(rel)};
next();
</script>"""


def make_handler(sess: Session, get_im):
    mpp, north = sess.meta["m_per_px"], tuple(sess.meta["north_px"])

    class H(BaseHTTPRequestHandler):
        def send(self, body, ctype="application/json", code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else body.encode())

        def do_GET(self):
            u = urlparse(self.path)
            try:
                if u.path == "/":
                    return self.send(PAGE, "text/html; charset=utf-8")
                if u.path == "/next":
                    return self.send(json.dumps(sess.nxt(), ensure_ascii=False))
                if u.path == "/search":
                    q = parse_qs(u.query)
                    return self.send(json.dumps(sess.search(q["id"][0], q.get("q", [""])[0]), ensure_ascii=False))
                if u.path.startswith("/img/"):
                    _, _, iid, name = u.path.split("/")
                    it = sess.items[iid]
                    img = render(get_im(), it, name.removesuffix(".png"), sess.arms[iid] == "shown", mpp, north)
                    return self.send(png(img), "image/png")
            except (KeyError, ValueError, IndexError) as e:
                return self.send(json.dumps({"error": str(e)}), code=404)
            self.send("{}", code=404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            try:
                if self.path == "/undo":
                    sess.undo()
                else:
                    sess.submit(body)
            except (KeyError, ValueError, IndexError) as e:
                return self.send(json.dumps({"error": str(e)}), code=400)
            self.send("{}")

        def log_message(self, *a):
            pass

    return H


def open_native(path: Path = NATIVE):
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(path).convert("RGB")
    im.load()
    return im


def spot(sess: Session, im, n: int = 5, seed: int = 7) -> list[Path]:
    from PIL import Image

    d = sess.out / "spot"
    d.mkdir(exist_ok=True)
    rng = random.Random(seed)
    paths = []
    for arm in ("shown", "blind"):
        ids = sorted(i for i, a in sess.arms.items() if a == arm)
        for k, iid in enumerate(rng.sample(ids, min(n, len(ids))), 1):
            it = sess.items[iid]
            a = render(im, it, "close", arm == "shown", sess.meta["m_per_px"], tuple(sess.meta["north_px"]))
            b = render(im, it, "context", arm == "shown", sess.meta["m_per_px"], tuple(sess.meta["north_px"])).resize((800, 800))
            c = Image.new("RGB", (1600, 800))
            c.paste(a, (0, 0))
            c.paste(b, (800, 0))
            p = d / f"{arm}-{k}-{iid[:8]}.png"
            c.save(p)
            paths.append(p)
    return paths


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8792)
    ap.add_argument("--reviewer", default="tue")
    ap.add_argument("--items", default=str(OUT / "items.json"))
    ap.add_argument("--out", default=str(OUT), help="where session.json, verdicts.jsonl and spot/ go")
    ap.add_argument("--seed-arm", type=int, default=20261012)
    ap.add_argument("--seed-order", type=int, default=20261013)
    ap.add_argument("--blind-frac", type=float, default=0.2)
    ap.add_argument("--new-session", action="store_true", help="move session.json aside and draw arms and order again")
    ap.add_argument("--spot", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    if not Path(a.items).exists():
        sys.exit(f"{a.items} missing: run build.py first")
    sess = Session(json.loads(Path(a.items).read_text()), Path(a.out), a.reviewer, a.seed_arm, a.seed_order, a.blind_frac, a.new_session)
    cache: list = []

    def get_im():
        if not cache:
            cache.append(open_native())
        return cache[0]

    if a.spot:
        for p in spot(sess, get_im()):
            print(p)
        return 0
    get_im()
    print(f"http://127.0.0.1:{a.port}  ({len(sess.items)} items, {sum(v == 'blind' for v in sess.arms.values())} blind)")
    ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(sess, get_im)).serve_forever()
    return 0


def self_check() -> int:
    import tempfile

    from PIL import Image

    ids = [f"id{i:02d}" for i in range(10)]
    arms = assign_arms(ids[:8], ids[8:], 1, 0.2)
    assert sorted(arms.values()).count("blind") == 2 and sorted(arms.values()).count("nocand") == 2
    assert arms == assign_arms(ids[:8], ids[8:], 1, 0.2), "arms are a function of the seed"
    assert {i for i, a in arms.items() if a == "blind"} <= set(ids[:8]), "only items with a candidate can be blind"
    assert make_order(ids, 3) == make_order(list(reversed(ids)), 3) and make_order(ids, 3) != sorted(ids)
    assert fold("Đại Chủng Viện") == "dai chung vien"

    def cand(k):
        return {"id": f"osm:way/{k}", "name": f"Place {k}", "names": [f"Place {k}"], "source": "osm", "osm": f"way/{k}",
                "osm_alts": [], "wikidata": None, "tasco_ids": [], "lon": 106.7, "lat": 10.78, "dist_m": 10.0 * k, "score": 1.0,
                "px": [300 + 50 * k, 300], "outline_px": [[280, 280], [400, 280], [400, 340], [280, 340]]}

    def item(i, ncand):
        return {"id": ids[i], "category": "institution", "text": f"LABEL {i}", "names": [f"LABEL {i}"], "px": [400.0, 300.0],
                "lon": 106.7, "lat": 10.78, "box": [330, 280, 150, 40], "pos_from": "box", "in_fit": False,
                "gcp_dist_m": 99, "cands": [cand(k) for k in range(1, ncand + 1)],
                "pool300": [{**cand(k), "dist_m": 10.0 * k} for k in range(1, 6)] + [{**cand(9), "name": "Hôtel Đặc Biệt", "names": ["Hôtel Đặc Biệt"], "id": "osm:way/99"}]}

    doc = {"meta": {"radius_m": 150, "method": "name_today@test+place-link-v1", "m_per_px": 0.341, "north_px": [1.0, 0.0]},
           "items": [item(i, 3 if i < 8 else 0) for i in range(10)]}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        s = Session(doc, td, "tester")
        again = Session(doc, td, "tester", seed_arm=999)  # the file wins, the seed passed is ignored
        assert again.arms == s.arms and again.order == s.order, "arms must not drift between sittings"
        # render: synthetic scan, blind crop draws nothing of the machine's
        im = Image.new("RGB", (900, 700), (200, 190, 170))
        it = doc["items"][0]
        for v in VIEWS:
            shown = render(im, it, v, True, 0.341, (1.0, 0.0))
            assert shown.size == (VIEWS[v][1],) * 2
        nocand = {**it, "cands": []}
        blind = render(im, it, "close", False, 0.341, (1.0, 0.0))
        assert blind.tobytes() == render(im, nocand, "close", True, 0.341, (1.0, 0.0)).tobytes(), "blind crop must not carry candidates"
        assert blind.tobytes() != render(im, it, "close", True, 0.341, (1.0, 0.0)).tobytes()
        assert png(blind)[:8] == b"\x89PNG\r\n\x1a\n"
        # north arrow follows the georeference: a different north changes the picture
        assert render(im, it, "close", False, 0.341, (0.0, -1.0)).tobytes() != blind.tobytes()
        # verdicts
        shown_id = next(i for i, a in s.arms.items() if a == "shown")
        blind_id = next(i for i, a in s.arms.items() if a == "blind")
        nc_id = next(i for i, a in s.arms.items() if a == "nocand")
        t = 1000.0
        r = s.submit({"id": shown_id, "pick": 2, "relation": "n", "shown_at": t, "decided_at": t + 9.5, "note": " ok "})
        assert r["task"] == "place-link" and r["item_id"] == shown_id and r["proposal_shown"] is True and r["note"] == "ok"
        assert r["verdicts"]["target"]["id"] == "way/2" and r["verdicts"]["pick"] == 2 and r["verdicts"]["relation"] == "same_site_new_building"
        assert r["decided_at"] - r["shown_at"] == 9.5 and r["order_idx"] == 0
        assert r["bound"] == s.bound(s.items[shown_id])
        for bad in ({"id": shown_id, "relation": "s"}, {"id": blind_id, "pick": 1, "relation": "s"},
                    {"id": shown_id, "pick": 1, "relation": "zz"}, {"id": blind_id, "search_id": "nope", "relation": "s"}):
            try:
                s.submit(bad)
                raise AssertionError(f"accepted {bad}")
            except ValueError:
                pass
        rb = s.submit({"id": blind_id, "search_id": "osm:way/99", "relation": "m", "shown_at": t + 10, "decided_at": t + 30})
        assert rb["proposal_shown"] is False and rb["verdicts"]["pick_via"] == "search" and rb["verdicts"]["arm"] == "blind"
        rn = s.submit({"id": nc_id, "relation": "x", "pick": None, "shown_at": t + 30, "decided_at": t + 35})
        assert rn["verdicts"]["target"] is None and rn["proposal_shown"] is False
        assert s.nxt()["done"] == 3 and s.nxt()["id"] not in (shown_id, blind_id, nc_id)
        assert Session(doc, td, "x").search(blind_id, "dac biet")[0]["id"] == "osm:way/99", "accent-free search finds the pool"
        assert [p["dist_m"] for p in s.search(blind_id, "")] == sorted(p["dist_m"] for p in s.search(blind_id, ""))
        # the blind item's page data never lists candidates
        s2 = Session(doc, td, "x")
        s2.order = [blind_id] + [i for i in s2.order if i != blind_id]
        s2.vf = td / "other.jsonl"
        assert s2.nxt()["id"] == blind_id and s2.nxt()["cands"] == []
        # undo: item returns to the queue, the log keeps every line
        u = s.undo(now=t + 40)
        assert u["item_id"] == nc_id and u["verdicts"] == {"undone": True}
        assert s.nxt()["done"] == 2 and nc_id not in s.done()
        assert len((td / "verdicts.jsonl").read_text().splitlines()) == 4
        # the page's own script is syntactically served and the spot writer works
        assert "doPick" in PAGE and "/verdict" in PAGE
        got = spot(s, im, n=2)
        assert len(got) == 4 and all(p.exists() for p in got)
    print("confirm self-check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
