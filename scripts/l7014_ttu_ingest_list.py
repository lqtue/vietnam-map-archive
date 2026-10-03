#!/usr/bin/env python3
"""Build the `bulk_upload_local.sh` list for TTU's L7014 scans (Vietnam Archive at Texas Tech).

Input is the transcription of each sheet's title band (cell, title, edition_line, ...), read off the
scan by hand/agent because OCR cannot read these collars. Output rows follow the PCL rule
(`l7014_ingest_list.py`): slug <place>-l7014-<sheet>, plus `-ed-<n>` when the edition is printed
and `-ttu` when it is not, so a second printing of a cell never collides with the first.

    python3 scripts/l7014_ttu_ingest_list.py OUT.txt READ.json [READ.json ...]   # writes the list, touches nothing
"""
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

NATIVE = Path("/Users/airm1/Work/Maps/l7014/ttu/native")
ALREADY = {"6329-1", "6329-4", "6330-1", "6330-2", "6330-3", "6330-4"}  # ingested 2026-09-13 as drafts


def env():
    out = dict(l.split("=", 1) for l in Path(".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
    return out["PUBLIC_SUPABASE_URL"].strip('"'), out["SUPABASE_SERVICE_KEY"].strip('"')


def slugify(s):
    s = s.replace("Đ", "D").replace("đ", "d")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def titlecase(t):
    return " ".join(w.capitalize() if w.isupper() or w.islower() else w for w in re.split(r"\s+", t.strip()))


def main(out, *reads):
    url, key = env()
    r = urllib.request.Request(f"{url}/rest/v1/maps?select=slug,name,extra_metadata&slug=like.*l7014*&limit=5000",
                               headers={"apikey": key, "Authorization": f"Bearer {key}"})
    rows = json.load(urllib.request.urlopen(r))
    slugs = {x["slug"] for x in rows}
    pcl_ed = {(x["extra_metadata"] or {}).get("sheet_number"): (x["extra_metadata"] or {}).get("edition") for x in rows
              if (x["extra_metadata"] or {}).get("source_archive") == "PCL"}
    pcl_name = {(x["extra_metadata"] or {}).get("sheet_number"): x["name"] for x in rows
                if (x["extra_metadata"] or {}).get("source_archive") == "PCL"}
    items = sorted((i for f in reads for i in json.load(open(f))), key=lambda i: i["cell"])
    lines, notes = [], []
    for i in items:
        c = i["cell"]
        if c in ALREADY:
            continue
        jpg = NATIVE / f"{c}-000.jpg"
        assert jpg.exists(), jpg
        title = i.get("title")
        if not title:
            title = pcl_name.get(c)
            notes.append(f"{c}: no printed title read; using {'PCL name ' + repr(title) if title else 'placeholder'}")
            title = title or f"Sheet {c}"
        name = titlecase(title)
        eline = (i.get("edition_line") or "").strip()
        m = re.search(r"(\d)\s*[-–]?\s*(AMS|TPC|DMA)", eline, re.I) or re.search(r"(?:thứ|ed\.?|edition)\s*(\d)", eline, re.I)
        ed = m.group(1) if m else None
        if ed and pcl_ed.get(c) == ed and "AMS" in eline.upper():
            notes.append(f"{c}: TTU edition {ed} is PCL's edition {pcl_ed[c]} -- same printing, skipped")
            continue
        slug = f"{slugify(name)}-l7014-{c}-" + (f"ed-{ed}" if ed else "ttu")
        n = 2
        base = slug
        while slug in slugs:
            slug = f"{base}-{n}"; n += 1
        slugs.add(slug)
        extra = {"series": "L7014", "sheet_number": c, "source_archive": "TTU"}
        if ed:
            extra["edition"] = ed
        if eline:
            extra["edition_line"] = eline
        if i.get("confidence") in ("medium", "low"):
            extra["title_read"] = i["confidence"]
        lines.append("\t".join([str(jpg), name, "-", json.dumps(extra, ensure_ascii=False), slug]))
    Path(out).write_text("\n".join(lines) + "\n")
    print(f"{len(lines)} rows -> {out}")
    print("\n".join(notes))


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
