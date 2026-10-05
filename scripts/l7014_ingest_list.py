#!/usr/bin/env python3
"""Build the file list `bulk_upload_local.sh` takes for the PCL L7014 GeoPDFs.

The naming rule, so the 510 rows read as one series:

    name            the place, PCL's ASCII spelling, nothing else (no sheet, year, series)
    slug            <place-slug>-l7014-<sheet>      e.g. ha-dong-l7014-6150-1
    sheet_number    NNNN-N, never roman; the printed "6150 I" is the same thing
    edition         PCL's number without leading zeros ("003" -> "3")
    year            PCL's when it is four digits (a few say "Jan "), else null
    source_archive  PCL

A sheet that already has an L7014 row is skipped and listed, not duplicated.

    python3 scripts/l7014_ingest_list.py OUT.txt JPG_DIR  # dry run: writes the list, touches nothing
"""
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

SHEETS = Path("/Users/airm1/Work/Maps/l7014/sheets.json")
PDFS = Path("/Users/airm1/Work/Maps/l7014/pdfs")


def env():
    out = dict(l.split("=", 1) for l in Path(".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
    return out["PUBLIC_SUPABASE_URL"].strip('"'), out["SUPABASE_SERVICE_KEY"].strip('"')


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def existing():
    url, key = env()
    r = urllib.request.Request(
        f"{url}/rest/v1/maps?select=slug,sheet_number&slug=like.*l7014*&limit=5000",
        headers={"apikey": key, "Authorization": f"Bearer {key}"})
    rows = json.load(urllib.request.urlopen(r))
    return {x["sheet_number"] for x in rows}, {x["slug"] for x in rows}


def main(out, jpgs):
    have, slugs = existing()
    lines, skipped = [], []
    for x in sorted((x for x in json.load(open(SHEETS)) if x["kind"] == "pdf"), key=lambda x: x["sheet"]):
        if x["sheet"] in have:
            skipped.append(x["sheet"])
            continue
        stem = re.sub(r"\s+", "", Path(x["file"]).stem)  # one entry says "xom_ruong-6331-4 .pdf"
        assert (PDFS / f"{stem}.pdf").exists(), stem
        slug = f"{slugify(x['name'])}-l7014-{x['sheet']}"
        assert slug not in slugs, slug
        extra = {"series": "L7014", "sheet_number": x["sheet"], "source_archive": "PCL"}
        if x.get("edition"):
            extra["edition"] = x["edition"].lstrip("0") or "0"
        lines.append("\t".join([f"{Path(jpgs) / (stem + '.jpg')}", x["name"], (x.get("year") or "").strip() if re.fullmatch(r"\d{4}", (x.get("year") or "").strip()) else "-", json.dumps(extra), slug]))
    assert len({l.split("\t")[4] for l in lines}) == len(lines), "slug collision"
    Path(out).write_text("\n".join(lines) + "\n")
    print(f"{len(lines)} to ingest, {len(skipped)} skipped (already have a row): {skipped}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
