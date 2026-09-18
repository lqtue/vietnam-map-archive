#!/usr/bin/env python3
"""Render a docs/*.md note to PDF, for attaching to an email.

ponytail: needs `markdown` + `weasyprint`, neither in the repo's deps because nothing
else here makes a PDF. Run it from a venv that has them:
    python3 -m venv .venv-pdf && .venv-pdf/bin/pip install markdown weasyprint
    .venv-pdf/bin/python scripts/md2pdf.py docs/allmaps-series-note.md

Usage: md2pdf.py <in.md> [out.pdf]
"""
import sys, pathlib, markdown, weasyprint

CSS = """
@page { size: A4; margin: 20mm 18mm; @bottom-center { content: counter(page);
  font: 8pt/1 Helvetica; color: #888; } }
body { font: 10pt/1.5 "Charter","Georgia",serif; color: #1a1a1a; hyphens: auto; }
h1 { font-size: 19pt; margin: 0 0 .2em; line-height: 1.2; }
h2 { font-size: 13pt; margin: 1.6em 0 .4em; border-bottom: 1px solid #ddd;
     padding-bottom: .2em; break-after: avoid; }
h3 { font-size: 11pt; margin: 1.3em 0 .3em; break-after: avoid; }
p, li { orphans: 2; widows: 2; }
table { border-collapse: collapse; width: 100%; margin: .8em 0; font-size: 8.5pt;
        break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 4px 7px; text-align: left; vertical-align: top; }
th { background: #f2f2f2; }
code, pre { font-family: "SF Mono","Menlo",monospace; font-size: 8.5pt; }
pre { background: #f6f6f6; padding: 8px 10px; border-left: 2px solid #bbb;
      white-space: pre-wrap; break-inside: avoid; }
blockquote { margin: .8em 0 .8em 1em; padding-left: .9em; border-left: 2px solid #ccc;
             color: #444; }
a { color: #24506b; }
hr { border: 0; border-top: 1px solid #ddd; margin: 1.6em 0; }
"""

src = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".pdf")
html = markdown.markdown(src.read_text(), extensions=["tables", "fenced_code", "toc"])
weasyprint.HTML(string=f"<meta charset='utf-8'>{html}").write_pdf(
    out, stylesheets=[weasyprint.CSS(string=CSS)])
print(f"{out}  ({out.stat().st_size // 1024} kB)")
