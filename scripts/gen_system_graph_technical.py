#!/usr/bin/env python3
"""Render docs/system-graph-technical.svg: one row per knowledge layer, columns for tools, research and
branches, and the open-item count per layer parsed from docs/knowledge-system-plan.md §9.

Fixed grid on purpose: an auto-layout (Mermaid, Graphviz) staggers the boxes and clips titles.
Which tool or doc sits in which layer is inferred from names and locations, not declared in the
repo; edit ROWS below when that changes. Run: python3 scripts/gen_system_graph_technical.py
"""
import re
from html import escape as e
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (key, label, holds, tools, research, branches). Top of the page first. Each cell is a list of
# (plain-language label, code name): the reader sees the label, the code name sits beneath it.
ROWS = [
    ("Surfaces", "Surfaces", "pages people use: search, Walk, blog",
     [("Explore map and catalog pages", "/explore · /catalog"), ("Walk-through routes and stories", "Walk · stories"), ("3D stack of six sheets (prototype)", "work/proto/fabric")],
     [("Blog and public changelog", "posts.ts · releases.ts"), ("Named work items, checked", "tests/work-items.spec.ts")],
     [("Search by prefix", "feat/explore-search-prefix"), ("Hide label hits from search", "fix/explore-hide-label-hits")]),
    ("5.", "L5 Assertions", "claims backed by evidence",
     [("Nothing yet: evidence chain is planned", "evidence-chain item in ROADMAP")],
     [("Research paper", "docs/paper"), ("One sheet, start to finish", "worked-example-1882"), ("Evidence-chain plan", "evidence-chain-plan")],
     [("Paper on survey 561", "docs/paper-series561")]),
    ("4.", "L4 Entities", "place and street names",
     [("Match legends across sheets", "legend_timeline"), ("Attach period press to legends", "legend_press"), ("Place-name gazetteer", "gazetteer table")],
     [("Old and new street-name pairs", "work/doling"), ("Period newspaper searches", "work/press"), ("Search plan", "search-plan")],
     []),
    ("3.", "L3 Readings", "text and shapes read off the scans",
     [("Read text from scans, clean it up", "enqueue_ocr_all · dedupe_ocr"), ("Find shapes on maps (MapSAM2)", "work/MapSAM2"), ("Read city blocks from ink colour", "colour_blocks")],
     [("How scans become searchable", "digitalize-guide"), ("Image-processing results", "image-processing-record"), ("Reading rivers off 1882 and 1898", "river-reconstruction")],
     []),
    ("2.", "L2 Placement", "where each sheet sits on the ground",
     [("Check sheets agree with each other", "sheet_align"), ("Find landmarks on each sheet", "gcp_inverse_lookup"), ("Keep georeference history", "backfill_georef_versions"), ("Check every map is where it claims", "geo_audit")],
     [("Anchor points, 1942 fix (District 4)", "work/analysis/district4"), ("How we compare to the field", "field-comparison")],
     [("Georeference history table", "feat/georef-versions"), ("Fix georef sources", "fix/georef-sources"), ("Fix Indochine 100k links", "fix-indochine100k-annotation-url")]),
    ("1.", "L1 Holdings", "the sheet record, its scan and tiles",
     [("Bulk-upload scans into tiles", "bulk_upload_local"), ("Repair thumbnails", "fix_thumbs_to_r2"), ("Queue map warping", "enqueue_warp_all")],
     [("Admin tooling guide", "admin-tooling"), ("Tile-serving worker", "worker/ (R2)")],
     []),
    ("0.", "L0 Sources", "who made and holds each survey",
     [("Does the survey index match the maps?", "check_series_index"), ("Audit CartoMundi scan rights", "cartomundi_rights_index"), ("Snapshot CartoMundi sheet records", "fetch_cartomundi_sheets")],
     [("Survey sheets (Tonkin, L7014, Indochine)", "work/tonkin · l7014 · indochine-100k"), ("Two series, no Editor (note)", "allmaps-series-note")],
     []),
    ("Outside", "Outside the model", "build, deploy, UI language",
     [("Build, deploy, bundle check", "deploy · check-bundle · CI")],
     [("Deployment guide", "deploy.md")],
     []),
]

# (version tag, what happened), from CHANGELOG.md and the release headlines; "after 7.4" is unreleased
HISTORY = {
    "Surfaces": [("1.0 · Apr 2025", "one page of scanned sheets"), ("4.0–5.2", "stories, /explore, /trip"), ("7.0 · Sep 2026", "16 pages, one Tools menu")],
    "5.": [("4.0 · Feb 2026", "stories: routes with text, the first claims"), ("After 7.4", "1882 sheet worked end to end; paper under way")],
    "4.": [("5.1–5.2", "full-text search, then one search engine"), ("6.0 · Aug 2026", "legend extraction, numbered legend points")],
    "3.": [("4.1 · Mar 2026", "first auto-tracing attempt, later replaced"), ("5.0 · Apr 2026", "first reader of printed names"), ("7.0–7.1", "reading scored against the sheet's own index")],
    "2.": [("3.3 · Dec 2025", "rotate a sheet square to the paper"), ("6.0 · Aug 2026", "rule: a published map must be georeferenceable"), ("After 7.4", "1942 fit fixed (112 m to 34 m); history table built")],
    "1.": [("4.0 · Feb 2026", "maps move from a file into a database"), ("5.0–6.0", "scans mirrored to own storage; publishing queues tiling"), ("7.3–7.4", "scan on each sheet's page; sheets addressed by name")],
    "0.": [("1.0 · Apr 2025", "scanned sheets of Saigon"), ("5.1 · May 2026", "batch upload; Scout looks in other libraries"), ("7.2 · Sep 2026", "whole surveys as one layer, with sheets we lack")],
    "Outside": [("4.0 · Feb 2026", "installable on a phone"), ("6.0 · Aug 2026", "layers enforced; workers hold no database password")],
}
VERSIONS = [("1.0", "Apr 2025", "one page"), ("3.0", "Oct 2025", "SvelteKit rewrite"), ("4.0", "Feb 2026", "database, accounts, stories"),
            ("5.0", "Apr 2026", "catalogue, tracing, first OCR"), ("6.0", "Aug 2026", "queue, worker, layers"),
            ("7.0", "Sep 2026", "one site"), ("7.4", "Sep 2026", "names as addresses (now)")]
EDGES = ["sheets exist", "scan + tiles", "ground truth", "labels + shapes", "names", "claims cite objects"]  # bottom to top

# open items per layer, from the §9 table: count the backticked names in each row's last column
plan = (ROOT / "docs/knowledge-system-plan.md").read_text()
counts = {}
for line in plan.split("## 9.")[1].split("\n"):
    m = re.match(r"\| \*\*(\d\.|Surfaces|Outside)", line)
    if m:
        counts[m.group(1)] = len(re.findall(r"`[a-z0-9-]+`", line.split("|")[3]))

X = dict(spine=24, tools=284, doc=628, br=972, items=1280, hist=1396)
W = dict(spine=236, tools=330, doc=330, br=294, items=96, hist=420)
WIDTH = 1840
H, GAP, TOP = 148, 40, 116
ENTRY = 35


def cell(x, y, w, kind, entries):
    if not entries:
        return f'<rect class="empty" x="{x}" y="{y}" width="{w}" height="{H}" rx="6"/>'
    out = [f'<rect class="{kind}" x="{x}" y="{y}" width="{w}" height="{H}" rx="6"/>']
    y0 = y + (H - ENTRY * len(entries)) / 2
    for i, (plain, code) in enumerate(entries):
        ty = y0 + i * ENTRY
        out.append(f'<text class="pl {kind}t" x="{x + 14}" y="{ty + 16:.0f}">{e(plain)}</text>')
        out.append(f'<text class="m cd {kind}t" x="{x + 14}" y="{ty + 31:.0f}">{e(code)}</text>')
    return "".join(out)


def hist_cell(x, y, w, items):
    out = [f'<rect class="spine" x="{x}" y="{y}" width="{w}" height="{H}" rx="6"/>']
    y0 = y + (H - ENTRY * len(items)) / 2
    for i, (tag, text) in enumerate(items):
        ty = y0 + i * ENTRY
        out.append(f'<text class="vt" x="{x + 14}" y="{ty + 16:.0f}">{e(tag)}</text>')
        out.append(f'<text class="vx" x="{x + 14}" y="{ty + 31:.0f}">{e(text)}</text>')
    return "".join(out)


o = [
    f'<text class="h1" x="{X["spine"]}" y="40">Knowledge layers, and what sits on them</text>',
    f'<text class="mut" x="{X["spine"]}" y="62">Tools, research strands and git branches by the layer they act on, with the open ROADMAP items per layer.</text>',
]
total_h = TOP + len(ROWS) * (H + GAP) + 150
for col, label in [("tools", "TOOLS (what runs)"), ("doc", "RESEARCH (what we learned)"), ("br", "GIT BRANCHES (work in flight)"), ("items", "OPEN WORK"), ("hist", "DEVELOPMENT HISTORY (version, then what)")]:
    o.append(f'<text class="hd" x="{X[col]}" y="{TOP - 16}">{label}</text>')
o.append(f'<text class="hd" x="{X["spine"]}" y="{TOP - 16}">LAYER (each rests on the one below)</text>')

ys = [TOP + i * (H + GAP) for i in range(len(ROWS))]
for i, (key, label, holds, tools, docs, brs) in enumerate(ROWS):
    y = ys[i]
    layer_row = key[0].isdigit() or key == "Surfaces"
    o.append(f'<rect class="spine" x="{X["spine"]}" y="{y}" width="{W["spine"]}" height="{H}" rx="6"/>')
    o.append(f'<text class="ttl" x="{X["spine"] + 16}" y="{y + 62}">{e(label)}</text>')
    o.append(f'<text class="mut" x="{X["spine"] + 16}" y="{y + 86}">{e(holds)}</text>')
    o.append(cell(X["tools"], y, W["tools"], "tool", tools))
    o.append(cell(X["doc"], y, W["doc"], "pub" if key == "Surfaces" else "doc", docs))
    o.append(cell(X["br"], y, W["br"], "br", brs))
    n = counts.get(key, 0)
    o.append(f'<rect class="empty" x="{X["items"]}" y="{y}" width="{W["items"]}" height="{H}" rx="6"/>')
    o.append(f'<text class="num" x="{X["items"] + 16}" y="{y + 72}">{n}</text>')
    o.append(hist_cell(X['hist'], y, W['hist'], HISTORY.get(key, [])))
    o.append(hist_cell(X['hist'], y, W['hist'], HISTORY.get(key, [])))
    o.append(f'<rect class="bar" x="{X["items"] + 16}" y="{y + 90}" width="{n * 3.6:.0f}" height="8" rx="2"/>')

# dependency arrows between stacked layers, in the spine column, label on a knockout
cx = X["spine"] + 22
for j, label in enumerate(EDGES):  # j=0 is L0->L1: rows 6 -> 5
    lower, upper = ys[6 - j], ys[5 - j]
    y1, y2 = lower - 4, upper + H + 4
    o.append(f'<line class="arr" x1="{cx}" y1="{y1}" x2="{cx}" y2="{y2 + 6}" marker-end="url(#a)"/>')
    o.append(f'<text class="mut" x="{cx + 12}" y="{(y1 + y2) / 2 + 4:.0f}">{e(label)}</text>')

# divider above "Outside the model"
dy = ys[-1] - GAP / 2
o.append(f'<line class="div" x1="{X["spine"]}" y1="{dy}" x2="{WIDTH - 24}" y2="{dy}"/>')

# version timeline: the same history seen across layers
vy = total_h - 124
o.append(f'<text class="hd" x="{X["spine"]}" y="{vy - 14}">VERSIONS (CHANGELOG.md; layers above show what each added)</text>')
o.append(f'<line class="div" x1="{X["spine"]}" y1="{vy + 6}" x2="{WIDTH - 24}" y2="{vy + 6}" style="stroke-dasharray:none"/>')
span = (WIDTH - 48 - 200) / (len(VERSIONS) - 1)
for k, (v, when, what) in enumerate(VERSIONS):
    vx = X["spine"] + k * span
    o.append(f'<circle class="dot" cx="{vx + 6}" cy="{vy + 6}" r="6"/>')
    o.append(f'<text class="vt" x="{vx}" y="{vy + 30}">{e(v)} · {e(when)}</text>')
    o.append(f'<text class="vx" x="{vx}" y="{vy + 47}">{e(what)}</text>')

# legend + provenance
ly = total_h - 44
for k, (cls, t) in enumerate([("tool", "tool: script, pipeline, route"), ("doc", "research: doc, journal, work/ dir"),
                              ("br", "git branch, by the layer it changes"), ("pub", "public page that can name ROADMAP items")]):
    lx = X["spine"] + k * 330
    o.append(f'<rect class="{cls}" x="{lx}" y="{ly}" width="22" height="14" rx="3"/><text class="mut" x="{lx + 30}" y="{ly + 12}">{t}</text>')
o.append(f'<text class="mut" x="{X["spine"]}" y="{ly + 36}">A plain label first, its code name beneath. Placement is inferred from names and locations. Item counts are parsed from knowledge-system-plan §9 (the declared link: ROADMAP → §9 → layer).</text>')

css = """
:root{--bg:#fbfaf7;--fg:#1c1b19;--mut:#6b675f;--line:#cfcabf;--spine:#efece4;--arr:#1c1b19;
--tool:#e3eee8;--toolf:#1d3a2e;--tools:#9dc0ae;--doc:#f3ead9;--docf:#3b2c0e;--docs:#d2bd8f;
--br:#e8e7f5;--brf:#25224f;--brs:#b3b0e0;--pub:#f6e2db;--pubf:#4a1d10;--pubs:#dba593;--bar:#3d6b57}
@media (prefers-color-scheme:dark){:root{--bg:#1b1a18;--fg:#ece9e1;--mut:#a39e92;--line:#3a3833;--spine:#26241f;--arr:#ece9e1;
--tool:#1f3329;--toolf:#cfe6d9;--tools:#3d6b57;--doc:#35291a;--docf:#f0dfbd;--docs:#7a5f2a;
--br:#26244a;--brf:#d8d6f7;--brs:#5b55a8;--pub:#43211a;--pubf:#f6d6cb;--pubs:#a4492e;--bar:#7fb89c}}
text{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;font-size:14px;fill:var(--fg)}
.pl{font-size:14px;font-weight:550}.cd{font-size:11.5px;opacity:.72}
.m{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-size:12.5px}
.vt{font-size:13px;font-weight:650;fill:var(--bar)}.vx{font-size:13px;fill:var(--fg)}circle.dot{fill:var(--bar)}
.hd{font-size:11px;letter-spacing:.09em;fill:var(--mut);font-weight:600}
.h1{font-size:24px;font-weight:700}.ttl{font-size:19px;font-weight:650}.mut{fill:var(--mut);font-size:12.5px}.c{text-anchor:middle}
.num{font-size:30px;font-weight:650}
rect.spine{fill:var(--spine);stroke:var(--line)}rect.empty{fill:none;stroke:var(--line);stroke-dasharray:3 4}
rect.tool{fill:var(--tool);stroke:var(--tools)}.toolt{fill:var(--toolf)}
rect.doc{fill:var(--doc);stroke:var(--docs)}.doct{fill:var(--docf)}
rect.br{fill:var(--br);stroke:var(--brs)}.brt{fill:var(--brf)}
rect.pub{fill:var(--pub);stroke:var(--pubs)}.pubt{fill:var(--pubf)}
rect.bar{fill:var(--bar)}
.arr{stroke:var(--arr);stroke-width:1.6}.div{stroke:var(--line);stroke-dasharray:6 5}
"""
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {total_h}" width="{WIDTH}" role="img" aria-label="Knowledge layers 0 to 5 and Surfaces, stacked bottom to top, with the tools, research strands, git branches and open ROADMAP item count at each layer">
<style>{css}</style>
<defs><marker id="a" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="var(--arr)"/></marker></defs>
<rect width="{WIDTH}" height="{total_h}" fill="var(--bg)"/>
{"".join(o)}
</svg>"""
(ROOT / "docs/system-graph-technical.svg").write_text(svg)
print("wrote docs/system-graph-technical.svg", counts)
