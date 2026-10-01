"""Point labels: the cheap reference for the river and road passes (replaces polygon tracing).

  label.py points SHEET [--per 25] [--seed 1]   random points in the sheet's heldout windows,
                                                appended to points-<sheet>.json (stratum "uniform")
           [--edge MASK --edge-per 12 --band 30]  plus points near MASK's water edge (stratum "edge")
                                                A batch is a seed; score a new version on a batch it
                                                has not been scored on (score.py --seed).
  label.py serve SHEET [--port 8791]            labelling page at http://127.0.0.1:8791

The page shows each point as a crosshair on the native raster, close up and in context. It never
shows a proposal, the window or its case, so a label cannot lean on what a method said.
Keys: w water, r road, l land (block, plot, anything not water or road), s unsure, u undo.
Labels append to labels/<sheet>.jsonl, one line per point; the last line for a point wins.
Boundary rules are README's: a point on a printed edge line is `unsure`; a bridge is road.
"""
import json
import random
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
CLASSES = {"w": "water", "r": "road", "l": "land", "s": "unsure"}
CLOSE, CONTEXT = 120, 900   # source px either side shown; close-up at 4x, context at 1/2


def points(sheet, per, seed, edge=None, edge_per=0, band=30):
    """A batch is a seed. --edge MASK adds edge_per points per window within `band` px of that mask's
    water edge (either side), where wrong edges live; a window with no edge gets none."""
    path = HERE / f"points-{sheet}.json"
    pts = json.loads(path.read_text()) if path.exists() else []
    if any(p["seed"] == seed for p in pts):
        sys.exit(f"seed {seed} already used: a batch is a seed, pick a new one")
    rng = random.Random(seed)
    wins = [w for w in json.loads((HERE / "windows.json").read_text())["windows"]
            if w["sheet"] == sheet and w["split"] == "heldout"]
    if edge:
        import numpy as np
        from PIL import Image
        from scipy.ndimage import distance_transform_edt
        Image.MAX_IMAGE_PIXELS = None
        water = np.asarray(Image.open(edge)) == 255
    add = lambda w, x, y, stratum: pts.append({"id": f"{sheet}-{len(pts):04d}", "x": x, "y": y, "window": w["id"],
                                               "stratum": stratum, "seed": seed, **({"edge_of": str(edge)} if stratum == "edge" else {})})
    for w in wins:
        x, y, bw, bh = w["box"]
        for _ in range(per):
            add(w, x + rng.randrange(bw), y + rng.randrange(bh), "uniform")
        if edge and edge_per:
            m = water[y:y + bh, x:x + bw]
            ys = xs = ()
            if m.any() and not m.all():   # distance to the other side, inside water and out
                ys, xs = np.nonzero(np.where(m, distance_transform_edt(m), distance_transform_edt(~m)) <= band)
            for i in rng.sample(range(len(ys)), min(edge_per, len(ys))):
                add(w, x + int(xs[i]), y + int(ys[i]), "edge")
    path.write_text(json.dumps(pts, indent=0) + "\n")
    print(f"{len(pts)} points in {path.name}; seed {seed}: {sum(p['seed'] == seed for p in pts)} new")


def latest(sheet):
    f = HERE / "labels" / f"{sheet}.jsonl"
    rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []
    return {r["id"]: r["label"] for r in rows}, f


PAGE = """<!doctype html><meta charset=utf-8><title>Point labels</title>
<style>body{font:15px system-ui;margin:16px;background:#222;color:#eee}img{image-rendering:pixelated;border:1px solid #555}
#row{display:flex;gap:16px;flex-wrap:wrap}kbd{background:#444;padding:2px 6px;border-radius:3px}</style>
<p id=s></p><div id=row><img id=a width=960 height=960><img id=b width=900 height=900></div>
<p><kbd>w</kbd> water <kbd>r</kbd> road <kbd>l</kbd> land <kbd>s</kbd> unsure (on a line, can't tell) <kbd>u</kbd> undo</p>
<script>
let cur=null;
async function next(){const r=await (await fetch('/next')).json();cur=r.id;
 document.getElementById('s').textContent=r.id?`${r.done} / ${r.total} labelled`:`all ${r.total} labelled, close the tab`;
 if(r.id){a.src='/img/'+r.id+'/close';b.src='/img/'+r.id+'/context'}}
document.onkeydown=async e=>{const k=e.key.toLowerCase();
 if(k==='u'){await fetch('/undo',{method:'POST'});return next()}
 if(cur&&k.length===1&&'wrls'.includes(k)){await fetch('/label',{method:'POST',body:JSON.stringify({id:cur,key:k})});next()}};
next();
</script>"""


def serve(sheet, port):
    from PIL import Image, ImageDraw
    Image.MAX_IMAGE_PIXELS = None
    pin = json.loads((HERE / "native.json").read_text())[sheet]
    im = Image.open(ROOT / pin["path"]).convert("RGB")
    pts = {p["id"]: p for p in json.loads((HERE / f"points-{sheet}.json").read_text())}
    order = sorted(pts, key=lambda i: random.Random(i).random())   # stable, not grouped by window

    def crop(p, view):
        r, z = (CLOSE, 4) if view == "close" else (CONTEXT, 0.5)
        c = im.crop((p["x"] - r, p["y"] - r, p["x"] + r + 1, p["y"] + r + 1))
        c = c.resize((round(c.width * z), round(c.height * z)), Image.NEAREST if z > 1 else Image.LANCZOS)
        d, m = ImageDraw.Draw(c), c.width / 2
        g = 6 if view == "close" else 10     # gap at the centre so the labelled pixel stays visible
        for a0, a1 in ((m - 40, m - g), (m + g, m + 40)):
            d.line([(a0, m), (a1, m)], fill=(255, 0, 255), width=2)
            d.line([(m, a0), (m, a1)], fill=(255, 0, 255), width=2)
        buf = BytesIO()
        c.save(buf, "PNG") if view == "close" else c.save(buf, "JPEG", quality=85)
        return buf.getvalue()

    class H(BaseHTTPRequestHandler):
        def send(self, body, ctype="application/json"):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else body.encode())

        def do_GET(self):
            if self.path == "/":
                return self.send(PAGE, "text/html")
            if self.path == "/next":
                done, _ = latest(sheet)
                todo = [i for i in order if i not in done]
                return self.send(json.dumps({"id": todo[0] if todo else None, "done": len(done), "total": len(pts)}))
            _, _, pid, view = self.path.split("/")
            self.send(crop(pts[pid], view), "image/png" if view == "close" else "image/jpeg")

        def do_POST(self):
            done, f = latest(sheet)
            f.parent.mkdir(exist_ok=True)
            if self.path == "/undo":
                lines = f.read_text().splitlines() if f.exists() else []
                f.write_text("".join(l + "\n" for l in lines[:-1]))
            else:
                b = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if b["id"] in pts and b["key"] in CLASSES:
                    with f.open("a") as fh:
                        fh.write(json.dumps({"id": b["id"], "label": CLASSES[b["key"]]}) + "\n")
            self.send("{}")

        def log_message(self, *a):
            pass

    print(f"http://127.0.0.1:{port}  ({len(pts)} points)")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    a = sys.argv[1:]
    opt = lambda k, d: int(a[a.index(k) + 1]) if k in a else d
    if a[:1] == ["points"] and len(a) >= 2:
        points(a[1], opt("--per", 25), opt("--seed", 1), a[a.index("--edge") + 1] if "--edge" in a else None,
               opt("--edge-per", 0), opt("--band", 30))
    elif a[:1] == ["serve"] and len(a) >= 2:
        serve(a[1], opt("--port", 8791))
    else:
        sys.exit(__doc__)
