#!/usr/bin/env python3
"""Render docs/system-graph.svg: the plain-language picture, for readers who are not engineers.

Seven steps a map goes through, each with why it matters, what is done, and what is open now. No
code names. The engineer view (tools, branches, files) is gen_system_graph_technical.py.
Open-task counts are parsed from docs/knowledge-system-plan.md §9; the prose is written here from
CHANGELOG.md, the /changelog headlines and docs/knowledge-system-plan.md. Run:
python3 scripts/gen_system_graph.py
"""
import re
import textwrap
from html import escape as e
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (plan key, title, why it matters, technical name, done [(when, text)], doing [plain tasks])
STEPS = [
    ("0.", "Find the maps", "We first need to know which maps exist, who made them, who holds them and whether we may show them.",
     "Layer 0 · Sources",
     [("Apr 2025", "The first scanned sheets of Saigon went online."),
      ("May 2026", "Volunteers can upload sheets in batches, and a search tool looks for more in other libraries."),
      ("Sep 2026", "Whole map series appear as one layer, including sheets we do not hold yet.")],
     ["Record every printing of a sheet", "Settle the licence for the Indochine 1:100,000 series"]),
    ("1.", "Keep them safe and online", "A scan on someone else's website can disappear. We keep our own copy and give each map a lasting web address.",
     "Layer 1 · Holdings",
     [("Feb 2026", "The list of maps moved from a file into a proper database."),
      ("Apr–Aug 2026", "Scans are copied to our own storage, and publishing a map now starts its processing by itself."),
      ("Sep 2026", "Every sheet has an address made from its name, and old links still work.")],
     ["Prove that old sheet links never break", "Fill in missing titles from the sheet itself"]),
    ("2.", "Pin each map to the real ground", "An old map only becomes a measuring tool once it lies exactly over today's city.",
     "Layer 2 · Placement",
     [("Dec 2025", "Sheets can be turned square to the page."),
      ("Aug 2026", "A map cannot be published until it can be placed."),
      ("Sep 2026", "The 1942 Saigon–Cholon sheet went from 112 m off to 34 m off.")],
     ["Keep a history of every placement, so a mistake can be undone", "Re-place the 1:50,000 US Army survey after a 470 m offset was found"]),
    ("3.", "Read what is printed on them", "Street names, numbers and legends are the history. A program reads them and people check its work.",
     "Layer 3 · Readings",
     [("Apr 2026", "The first program that reads printed names off a sheet; shapes traced by hand."),
      ("Sep 2026", "Reading quality can be scored against a sheet's own printed street index."),
      ("Now", "22 maps have been read, and 118 of their labels checked by a person.")],
     ["Read the whole placed archive", "Find city blocks and rivers from the ink colours"]),
    ("4.", "Make names comparable across years", "A street changes name; a place is spelled several ways. We link them so one search finds all.",
     "Layer 4 · Entities",
     [("May 2026", "Search across the whole catalogue, later merged into one search engine."),
      ("Aug 2026", "Printed legends are read and shown as numbered points on the map.")],
     ["Build a place-name dictionary that spans the years", "Pair old and new street names"]),
    ("5.", "Make claims we can prove", "A statement such as \"this street was here in 1882\" should lead to the exact spot on the exact sheet.",
     "Layer 5 · Assertions",
     [("Feb 2026", "Stories: routes across the map with text and stops."),
      ("Sep 2026", "One sheet (1882) taken all the way from scan to traced shapes; a research paper is under way.")],
     ["Link each statement to its trail of evidence", "Compare what different sheets say about the same place"]),
    ("Surfaces", "Show it to people", "All of the above matters only if a visitor can explore it.",
     "Surfaces",
     [("Jun 2026", "A map page you can search, and a trip page that a printed QR code opens."),
      ("Sep 2026", "The site went from 23 pages to 16, with a dark theme and one Tools menu.")],
     ["A walking tour of District 4", "A year slider to move through time", "A 3D stack of six District 4 maps, with how each was made (prototype, not published)"]),
    ("Outside", "Keep it running", "Building, publishing and testing the site, and the language of its screens.",
     "Outside the model",
     [("Aug 2026", "Dead code removed; the machines that read sheets hold no database password."),
      ("Now", "374 automated checks run before a change is accepted.")],
     ["Add a second key for the AI reading service", "Keep preview sites configured"]),
]
GROWTH = [("Apr 2025", "one web page of scans"), ("Oct 2025", "rebuilt as a real application"), ("Feb 2026", "accounts, database, stories"),
          ("Apr 2026", "catalogue, tracing, first text reading"), ("Aug 2026", "automatic processing queue"), ("Sep 2026", "one site, names as addresses")]

plan = (ROOT / "docs/knowledge-system-plan.md").read_text()
counts = {}
for line in plan.split("## 9.")[1].split("\n"):
    m = re.match(r"\| \*\*(\d\.|Surfaces|Outside)", line)
    if m:
        counts[m.group(1)] = len(re.findall(r"`[a-z0-9-]+`", line.split("|")[3]))

WIDTH, M = 1240, 28
XS, WS = M, 340          # step card
XD, WD = 392, 520        # what is done
XN, WN = 940, 272        # what is happening now
LH = 20                  # body line height
tag_w = 122              # slot for the date chip in "done"


def wrap(t, n):
    return textwrap.wrap(t, n, break_long_words=False)


o, y = [], 128
o.append(f'<text class="h1" x="{M}" y="44">How the archive is built, in seven steps</text>')
o.append(f'<text class="mut" x="{M}" y="70">Each step depends on the one before it, so a mistake early on carries into everything after.</text>')
o.append(f'<text class="mut" x="{M}" y="90">We fix the earliest broken step first. Read from the top down.</text>')
for x, t in [(XS, "THE STEP"), (XD, "WHAT IS DONE"), (XN, "WHAT IS OPEN NOW")]:
    o.append(f'<text class="hd" x="{x}" y="{y - 12}">{t}</text>')

n_step = 0
for i, (key, title, why, tech, done, doing) in enumerate(STEPS):
    if key == "Outside":
        o.append(f'<line class="div" x1="{M}" y1="{y - 16}" x2="{WIDTH - M}" y2="{y - 16}"/>')
        y += 14
    left_t, left_w = wrap(title, 25), wrap(why, 40)
    d_lines = [wrap(t, 52) for _, t in done]
    d_h = sum(len(l) * LH for l in d_lines) + 8 * (len(done) - 1)
    n_lines = [wrap(t, 31) for t in doing]
    n_h = 56 + sum(len(l) * LH for l in n_lines) + 6 * (len(doing) - 1)
    l_h = 42 + len(left_t) * 24 + 14 + len(left_w) * 18 + 40
    H = int(max(l_h, d_h + 36, n_h + 24, 120))

    o.append(f'<rect class="card" x="{XS}" y="{y}" width="{WS}" height="{H}" rx="8"/>')
    cx = XS + 32
    if key != "Outside":
        n_step += 1
        o.append(f'<circle class="dot" cx="{cx}" cy="{y + 36}" r="17"/><text class="bn c" x="{cx}" y="{y + 42}">{n_step}</text>')
    ty = y + 42
    for ln in left_t:
        o.append(f'<text class="ttl" x="{XS + (62 if key != "Outside" else 20)}" y="{ty}">{e(ln)}</text>')
        ty += 24
    ty += 6
    for ln in left_w:
        o.append(f'<text class="why" x="{XS + 20}" y="{ty + 8}">{e(ln)}</text>')
        ty += 18
    o.append(f'<text class="tech" x="{XS + 20}" y="{y + H - 12}">Technical name: {e(tech)}</text>')

    o.append(f'<rect class="card2" x="{XD}" y="{y}" width="{WD}" height="{H}" rx="8"/>')
    dy = y + 30
    for (when, _), lines in zip(done, d_lines):
        o.append(f'<text class="when" x="{XD + 18}" y="{dy}">{e(when)}</text>')
        for ln in lines:
            o.append(f'<text class="body" x="{XD + 18 + tag_w}" y="{dy}">{e(ln)}</text>')
            dy += LH
        dy += 8

    o.append(f'<rect class="card3" x="{XN}" y="{y}" width="{WN}" height="{H}" rx="8"/>')
    c = counts.get(key, 0)
    o.append(f'<text class="num" x="{XN + 18}" y="{y + 44}">{c}</text><text class="mut" x="{XN + 18 + 14 + len(str(c)) * 18}" y="{y + 44}">open tasks</text>')
    ny = y + 70
    for lines in n_lines:
        for j, ln in enumerate(lines):
            o.append(f'<text class="body" x="{XN + 18}" y="{ny}">{"· " if j == 0 else "  "}{e(ln)}</text>')
            ny += LH
        ny += 6

    if key not in ("Outside",) and i < len(STEPS) - 2:
        o.append(f'<line class="arr" x1="{XS + 32}" y1="{y + H + 2}" x2="{XS + 32}" y2="{y + H + 20}" marker-end="url(#a)"/>')
    y += H + 24

# how the site itself grew
y += 8
o.append(f'<text class="hd" x="{M}" y="{y}">HOW THE SITE ITSELF GREW (each version number is in CHANGELOG.md)</text>')
span = (WIDTH - 2 * M - 180) / (len(GROWTH) - 1)
o.append(f'<line class="div2" x1="{M}" y1="{y + 22}" x2="{WIDTH - M}" y2="{y + 22}"/>')
for k, (when, what) in enumerate(GROWTH):
    gx = M + k * span
    o.append(f'<circle class="dot" cx="{gx + 6}" cy="{y + 22}" r="6"/>')
    o.append(f'<text class="when" x="{gx}" y="{y + 48}">{e(when)}</text>')
    for j, ln in enumerate(wrap(what, 24)):
        o.append(f'<text class="body" x="{gx}" y="{y + 68 + j * 18}">{e(ln)}</text>')
y += 120
o.append(f'<text class="mut" x="{M}" y="{y}">Open-task counts come from the project roadmap, as of the last time this picture was drawn. The engineer view of the same picture is system-graph-technical.svg.</text>')
H_TOTAL = y + 28

css = """
:root{--bg:#fbfaf7;--fg:#1c1b19;--mut:#6b675f;--line:#cfcabf;--card:#efece4;--card2:#f6f3ec;--card3:#e3eee8;--acc:#2f6b52;--accf:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#1b1a18;--fg:#ece9e1;--mut:#a39e92;--line:#3a3833;--card:#26241f;--card2:#201f1b;--card3:#1f3329;--acc:#7fb89c;--accf:#12201a}}
text{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;font-size:15px;fill:var(--fg)}
.h1{font-size:28px;font-weight:700}.mut{fill:var(--mut);font-size:14px}.hd{font-size:12px;letter-spacing:.09em;fill:var(--mut);font-weight:650}
.ttl{font-size:20px;font-weight:650}.why{font-size:14px;fill:var(--mut)}.tech{font-size:12px;fill:var(--mut);opacity:.85}
.when{font-size:14px;font-weight:650;fill:var(--acc)}.body{font-size:15px}
.num{font-size:34px;font-weight:700;fill:var(--acc)}.bn{font-size:17px;font-weight:700;fill:var(--accf)}.c{text-anchor:middle}
rect.card{fill:var(--card);stroke:var(--line)}rect.card2{fill:var(--card2);stroke:var(--line)}rect.card3{fill:var(--card3);stroke:var(--line)}
circle.dot{fill:var(--acc)}.arr{stroke:var(--fg);stroke-width:1.6}.div{stroke:var(--line);stroke-dasharray:6 5}.div2{stroke:var(--line);stroke-width:2}
"""
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {H_TOTAL}" width="{WIDTH}" role="img" aria-label="Seven steps a map goes through in the Vietnam Map Archive, from finding the maps to showing them to people, with what is done and what is open at each step">
<style>{css}</style>
<defs><marker id="a" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="var(--fg)"/></marker></defs>
<rect width="{WIDTH}" height="{H_TOTAL}" fill="var(--bg)"/>
{"".join(o)}
</svg>"""
(ROOT / "docs/system-graph.svg").write_text(svg)
print("wrote docs/system-graph.svg", counts)
