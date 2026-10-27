#!/usr/bin/env python3
"""Landmark buildings on the 1882 Plan Cadastral that still stand, warped into its pixel grid.

    python work/image-processing/scripts/landmarks_1882.py                 # reads the cached Overpass/Wikidata files
    python work/image-processing/scripts/landmarks_1882.py --fetch-osm      # two Overpass queries (box, then relations by id)
    python work/image-processing/scripts/landmarks_1882.py --refresh-wikidata
    python work/image-processing/scripts/landmarks_1882.py --crops DIR      # overlay PNG per row, for the hand check
    python work/image-processing/scripts/landmarks_1882.py --self-check     # no network, no data files

Why: `modern_prior.py --survivors` says which 2023 footprints are big and low,
406 of them, and cannot say which are *the same building* as one on the 1882
sheet. A handful of landmarks are (Notre-Dame was finished in April 1880). Their
exact footprints are worth far more than 406 guesses: building corners as
control points, building-level ground truth for segmentation, and clean
OCR-label <-> modern-name <-> Wikidata links. So **precision beats recall**.

How a row gets to `kept`:

  1. candidates   survivors (modern_prior's own filter) U footprints inside an
                  OSM element tagged wikidata / historic / heritage / a religious,
                  civic or educational building U footprints under a TASCO
                  `label_congtrinhs` point or `region_trusos` polygon. The survivor
                  filter is NOT the gate: a tall landmark can fail its 25 m cap, so
                  the tagged and named sets are scanned for h > 25 m separately.
  2. identity     `LANDMARKS` below — a hand-written table, one row per building,
                  naming the OSM element that outlines it. Nothing is inferred
                  from a name match alone.
  3. date         every row carries the year(s) AND the URL AND a quote the year
                  was read from. Wikidata P571 is fetched and shown next to it, but
                  it is an *institution's* founding year as often as a building's,
                  so it never decides a status by itself. No date -> `undated`,
                  blank year, confidence low. Nothing is written from memory.
  4. status       built_end <= 1882 -> kept, later -> post-1882, demolished ->
                  gone (name + source only, no geometry).
  5. OCR          the nearest non-rejected `ocr_labels` row whose text matches the
                  row's 1882 name. `ocr_label_dist_px` is pixels from the warped
                  footprint to the label's CENTRE (the box is the envelope of slanted
                  ink and overlaps almost anything; its gap is `ocr_box_gap_px`).
                  Nothing within 300 px is recorded as blank, not forced.

**Read the fit before trusting a distance.** The sheet's georeference is an
affine over 8 GCPs at 33.6 px RMS (11.5 m, worst 48 px), so a warped footprint can
sit 15 m from the building it describes, which is the size of a small landmark.
The footprint is the *modern* outline; later wings are in it. Both are why every
row is meant to be looked at (`--crops`) before it is used as a control point.

Outputs (gitignored under results/; the HCMC building licence is unresolved so
the geometry stays on this machine):

  landmarks.geojson   kept rows, source pixels y-down — the same contract as
                      survivors.geojson
  landmarks.csv       every row, kept + post-1882 + gone + undated, `status` column
  landmarks_overpass.json / landmarks_wikidata.json   the cached raw responses

Writes nothing to Supabase and nothing outside the results directory. Self-check
at the bottom needs no network and no data files.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import numpy as np
import shapely

sys.path.insert(0, str(Path(__file__).resolve().parent))
import modern_prior as mp  # noqa: E402  (also puts work/ocr/scripts on sys.path)
from modern_prior import SURVIVOR_MAX_HEIGHT_M, SURVIVOR_MIN_AREA_M2  # noqa: E402

MAP_ID = "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b"
SHEET_W, SHEET_H = 12102, 8982
OUT_DIR = Path(__file__).resolve().parents[1] / "results" / "prior" / MAP_ID

# The sheet is a survey of 1881-82. A building has to be finished by the end of
# the year the sheet is dated for the sheet to show it as standing.
SHEET_YEAR = 1882

# A footprint belongs to an OSM outline when at least this share of the
# footprint's own area lies inside it. Not the other way round: a campus
# polygon holds many buildings and none of them covers it.
FOOTPRINT_IN_OUTLINE = 0.5
# Parts smaller than this are sheds and annexes, not the landmark.
MIN_PART_M2 = 100.0
# More footprints than this, or more ground, and the polygon is a compound
# (a campus, a hospital, a convent), not one building. It is still the right
# place; it is the wrong shape to use as a building corner.
SITE_PARTS = 3
SITE_AREA_M2 = 6000.0
# Candidate scan floors: a tagged or named footprint under this is a shophouse.
CANDIDATE_MIN_M2 = 300.0

# "Near" for an OCR label, in sheet pixels (0.34 m/px -> ~34 m). Under the
# sheet's 33.6 px fit RMS a label cannot be trusted much closer than this, and
# a label is routinely printed beside a block rather than on it.
OCR_NEAR_PX = 100.0
OCR_MAX_PX = 300.0
# Labels in these categories are names of things; street/hydrology/legend/title
# labels are not, and `Rue Chasseloup-Laubat` must not stand in for the college.
OCR_CATEGORIES = ("institution", "building", "place", "other")

BUILDINGS_PARQUET = mp.HCMC_DIR / "hcmc_buildings_3d.parquet"
VECTOR_PARQUET = mp.HCMC_DIR / "hcmc_vector.parquet"
TOPO_LAYERS = ("label_congtrinhs", "region_trusos")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "vma-landmarks-1882/1.0 (+https://maparchive.vn)"
OVERPASS_QL = """[out:json][timeout:180];
(
  nwr["wikidata"]({bbox});
  nwr["historic"]({bbox});
  nwr["heritage"]({bbox});
  nwr["building"~"^(cathedral|church|temple|palace|government|public|civic|hospital|school|university|college|pagoda|shrine|barracks|train_station|transportation|kindergarten|chapel|monastery|museum)$"]({bbox});
  nwr["amenity"~"^(place_of_worship|townhall|courthouse|hospital|university|college|school|marketplace|police|prison|theatre|post_office|library)$"]({bbox});
  nwr["tourism"~"^(museum|attraction|zoo|gallery)$"]({bbox});
  nwr["office"="government"]({bbox});
);
out tags geom;
"""

STATUSES = ("kept", "post-1882", "gone", "undated")


def wp_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='(),:')}"


def wd_url(qid: str) -> str:
    return f"https://www.wikidata.org/wiki/{qid}"


@dataclass(frozen=True)
class Landmark:
    """One building, by hand. Every field that is a claim carries its source."""

    key: str
    status: str  # 'kept' | 'post-1882' | 'gone' | 'undated' — checked against `built` in evaluate()
    name_modern: str
    osm: str | None  # 'way/123' | 'relation/123' — the outline the footprints are read from
    wikidata: str | None  # only ids taken from a Wikipedia sitelink or the OSM tag
    ocr: tuple[str, ...]  # regexes over the accent-stripped upper-case label text
    built: tuple[int, int] | None  # (start, end) year; None = unknown
    sources: tuple[tuple[str, str], ...]  # (url, what it says) — the date's provenance
    precise: bool = True  # False when the source gives a decade or a century
    cap: str = "high"  # ceiling on confidence for reasons the numbers cannot see
    note: str = ""


# ponytail: hand-written on purpose. A name match against the TASCO layer found
# 1,369 named points in this extent and a school every 200 m; the identity step
# is the only place a human reads a source, so it stays a table, not an inference.
LANDMARKS: tuple[Landmark, ...] = (
    # ---- stood in 1882, stands today -------------------------------------
    Landmark(
        "notre-dame", "kept", "Nhà thờ Chính tòa Đức Bà Sài Gòn (Notre-Dame Cathedral Basilica of Saigon)",
        "way/801950766", "Q428129", (r"CATHEDRALE",), (1877, 1880),
        ((wp_url("en", "Notre-Dame Cathedral Basilica of Saigon"),
          "constructed between 1877 and 1880; first stone 7 Oct 1877; completion ceremony 11 April 1880"),
         (wp_url("vi", "Nhà thờ chính tòa Đức Bà Sài Gòn"), "khánh thành 11 tháng 4 năm 1880"),
         (wd_url("Q428129"), "P571 inception 1880")),
        note="The only OCR label is PLACE DE LA CATHEDRALE — the square, not the building. "
             "The two 57 m bell towers were added in 1895 (same en/vi pages), so the 1882 roofline was lower; the footprint is unaffected. "
             "Overlay checked: the cathedral is drawn on the sheet (apse to the NE) and the warped footprint lies on it, shifted ~15 px (5 m).",
    ),
    Landmark(
        "lycee-le-quy-don", "kept", "Trường THPT Lê Quý Đôn (Collège Chasseloup-Laubat), 110 Nguyễn Thị Minh Khai",
        "way/469843391", "Q4559616", (r"^COLLEGE CHASSELOUP",), (1874, 1877),
        ((wp_url("vi", "Trường Trung học phổ thông Lê Quý Đôn, Thành phố Hồ Chí Minh"),
          "khởi công xây dựng ngay vào năm 1874 và hoàn tất vào năm 1877"),
         (wp_url("fr", "Lycée Lê Quý Đôn"), "fondé à Saïgon en 1874 ... collège Chasseloup-Laubat 1877"),
         (wd_url("Q4559616"), "P571 inception 1874 (the school, not the building)")),
        cap="medium",
        note="Site outline: the footprint is whatever 2023 buildings stand inside the school grounds and may include later wings. "
             "Overlay checked: the sheet draws a courtyard plan with two long wings and small pavilions; the 2023 outline follows the same two wings "
             "(shifted ~15 px) but also spans a later block on the NW side.",
    ),
    Landmark(
        "dinh-thuong-tho", "kept", "Dinh Thượng Thơ, 59-61 Lý Tự Trọng (Direction de l'Intérieur / Secrétariat du Gouvernement)",
        "way/258866011", "Q32174203", (r"DIRECTION DE L.INTERIEUR",), (1875, 1875),
        ((wp_url("vi", "Dinh Thượng thơ"),
          "Tiền thân ... Direction de l'Intérieur xây dựng xong vào năm 1864. Đến năm 1875, Dinh Thượng thơ được xây mới theo bản vẽ của Alfred Foulhoux và kiến trúc này tồn tại cho đến nay"),),
        precise=False,
        note="Rebuilt 1875 on the 1864 block; the source gives the year the rebuild was done, not a completion date. "
             "Overlay checked: the 2023 L-shaped footprint lies on the block labelled DIRECTION DE L'INTERIEUR but is not a corner-for-corner match "
             "(the sheet draws a long range along the street plus wings).",
    ),
    Landmark(
        "nha-rong", "kept", "Bến Nhà Rồng (Hôtel des Messageries Impériales / Maritimes)",
        "way/808022726", "Q10743440", (r"MESSAGERIES",), (1863, 1864),
        ((wp_url("vi", "Bến Nhà Rồng"),
          "khởi công xây dựng ngày 4 tháng 3 năm 1863 và hoàn thành trong 1 năm"),
         (wp_url("en", "Dragon House (Ho Chi Minh City)"), "construction began in 1862 ... completed in 1863")),
        note="en and vi disagree by one year on the start. No MESSAGERIES label lies within 300 px of the footprint: the two on the sheet are ~470 and ~580 px away. "
             "Overlay checked: a large square building is drawn at the river bend; the warped footprint sits ~60 px NE of it, so this is a position-and-size match "
             "(915 m2 vs ~1,400 m2 drawn), not a corner match. Hand-check before using as a control point.",
    ),
    Landmark(
        "hopital-maritime", "kept", "Bệnh viện Nhi đồng 2, 14 Lý Tự Trọng (French military hospital)",
        "way/187895176", "Q30293454", (r"HOPITAL MARITIME",), (1870, 1879),
        ((wp_url("vi", "Bệnh viện Nhi đồng 2"),
          "vốn là một bệnh viện Quân y được người Pháp cho xây dựng vào thập niên 1870"),),
        precise=False, cap="low",
        note="Date is a decade. The HOPITAL MARITIME <-> Nhi đồng 2 link is by position (label inside the footprint union), not by any source. "
             "Overlay checked: the sheet draws a dense pavilion hospital; the footprint is a union of ~60 2023 buildings (30,900 m2), a site mask and not a building.",
    ),
    Landmark(
        "continental", "kept", "Khách sạn Continental Sài Gòn (Hôtel Continental)",
        "relation/2204742", "Q5911405", (r"CONTINENTAL",), (1878, 1880),
        ((wp_url("en", "Hotel Continental Saigon"),
          "built in 1878 and opened in 1880 ... refurbished in 1892"),
         (wp_url("vi", "Khách sạn Continental"), "xây vào năm 1878 ... khánh thành năm 1880")),
        cap="low",
        note="No OCR label names it. Refurbished 1892 and altered since, so the footprint is the 2023 hotel, not necessarily the 1880 plan. "
             "Overlay checked and NOT confirmed: the warped footprint covers a private (pink) lot on rue Catinat where no drawn building can be singled out as the hotel.",
    ),
    Landmark(
        "carmel", "kept", "Đan viện Cát Minh Sài Gòn (Carmel of Saigon)",
        "way/804926030", "Q10840076", (r"CARMELITES",), (1867, 1876),
        ((wp_url("vi", "Đan viện Cát Minh Sài Gòn"),
          "đặt viên đá đầu tiên ngày 8 tháng 10 năm 1867 ... 9 tháng 12 năm 1876 đan viện mới được khánh thành và cung hiến"),),
        cap="low",
        note="Overlay checked and NOT confirmed: the sheet draws only small structures at the street corner of the convent lot, so the 1876 monastery "
             "is not identifiable among the 2023 courtyard buildings (7 parts).",
    ),
    Landmark(
        "saint-paul-convent", "kept", "Tu viện dòng Thánh Phaolô, 4 Tôn Đức Thắng",
        "way/493251146", "Q10829978", (r"SAINTE ENFANCE",), (1864, 1864),
        ((wp_url("vi", "Tu viện dòng Thánh Phaolô (Sài Gòn)"),
          "do Nguyễn Trường Tộ thiết kế ... hoàn thành ngày 10 tháng 8 năm 1864"),),
        cap="medium",
        note="SAINTE ENFANCE <-> this convent is by position only; no source ties the label to the Sisters of St Paul. "
             "Overlay checked: a semicircular apse in the 2023 outline coincides (within ~20 px) with a drawn apse, so the chapel is the same building; "
             "the other 13 parts are later or unmatched. Use the apse, not the union.",
    ),
    Landmark(
        "grand-seminaire", "kept", "Đại chủng viện Thánh Giuse Sài Gòn (Grand Séminaire)",
        "way/198123915", "Q10841200", (r"GRAND SEMINAIRE",), (1863, 1866),
        ((wp_url("vi", "Đại chủng viện Thánh Giuse Sài Gòn"),
          "đặt viên đá đầu tiên ... năm 1863; Giám mục Miche khánh thành ... năm 1866; nhà nguyện 1871"),),
        cap="medium",
        note="Campus outline (21 parts): which of today's buildings are the 1863-66 ones is not in the source. "
             "Overlay checked: a semicircular apse in the 2023 outline coincides with a drawn apse (chapel, 1867-71 per the same article); "
             "the rest of the union is later or unmatched. Treat as a site, not a building.",
    ),
    # ---- built after the sheet: kept out, recorded for later sheets ---------
    Landmark(
        "post-office", "post-1882", "Bưu điện Trung tâm Sài Gòn",
        "way/39514793", "Q2227270", (), (1886, 1891),
        ((wp_url("en", "Saigon Central Post Office"), "constructed between 1886 and 1891"),
         (wd_url("Q2227270"), "P571 inception 1891")),
    ),
    Landmark(
        "gia-long-palace", "post-1882", "Bảo tàng Thành phố Hồ Chí Minh (Gia Long Palace)",
        "way/802105071", None, (r"ANCIEN PALAIS DE JUSTICE",), (1885, 1890),
        ((wp_url("en", "Museum of Ho Chi Minh City"), "Construction of the palace began in 1885 and completed in 1890"),
         (wp_url("vi", "Bảo tàng Thành phố Hồ Chí Minh"), "khởi công xây dựng vào năm 1885 và hoàn thành năm 1890")),
        note="The sheet labels this spot 'Ancien Palais de Justice' — some earlier building stood here in 1882; the 2023 footprint is the 1885-90 palace.",
    ),
    Landmark(
        "city-hall", "post-1882", "Trụ sở UBND Thành phố Hồ Chí Minh (Hôtel de Ville)",
        "way/341504305", "Q2227195", (), (1898, 1909),
        ((wp_url("en", "Ho Chi Minh City Hall"), "broke ground 1898 ... opened in 1909"),
         (wd_url("Q2227195"), "P571 inception 1908")),
    ),
    Landmark(
        "opera-house", "post-1882", "Nhà hát Thành phố (Opéra de Saïgon)",
        "way/801710792", "Q1949129", (), (1898, 1900),
        ((wp_url("en", "Ho Chi Minh City Opera House"), "construction of the new theatre commenced in 1898 ... completed by 1 January 1900"),),
    ),
    Landmark(
        "ben-thanh-market", "post-1882", "Chợ Bến Thành (current building)",
        "way/39514795", "Q3232879", (), (1912, 1914),
        ((wp_url("vi", "Chợ Bến Thành"), "khởi công xây dựng từ năm 1912 đến cuối tháng 3 năm 1914 thì hoàn tất"),),
        note="The 1882 'MARCHE CENTRAL' stood on another site and is listed under gone.",
    ),
    Landmark(
        "tan-dinh-church", "post-1882", "Nhà thờ Tân Định (present fabric)",
        "way/60118189", "Q7682043", (), (1896, 1898),
        ((wp_url("vi", "Nhà thờ Tân Định"),
          "khởi công 1870, khánh thành 16/12/1876 ... Phần lớn diện tích của Nhà thờ Tân Định hiện nay có từ năm 1896-1898"),),
        note="A first church (1870-76) stood in 1882; the vi article dates most of today's building to the 1896-98 rebuild.",
    ),
    Landmark(
        "museum-of-history", "post-1882", "Bảo tàng Lịch sử TP.HCM",
        "relation/17758150", "Q6941045", (), (1929, 1929),
        ((wd_url("Q6941045"), "P571 inception 1929"),),
        precise=False, note="Wikidata only; the museum's own building year was not read from a prose source.",
    ),
    Landmark(
        "majestic-hotel", "post-1882", "Khách sạn Majestic Saigon",
        "way/193142038", "Q3063149", (), (1925, 1925),
        ((wd_url("Q3063149"), "P571 inception 1925"),),
        precise=False, note="Wikidata only.",
    ),
    Landmark(
        "taberd", "post-1882", "Trường THPT chuyên Trần Đại Nghĩa (La San Taberd), 20 Lý Tự Trọng",
        "way/801710776", None, (r"TABERD",), (1875, 1887),
        ((wp_url("vi", "Trường Trung học phổ thông chuyên Trần Đại Nghĩa"),
          "bắt đầu khởi công vào năm 1875 ... sau 12 năm kéo dài, vào năm 1887, nhà trường chính thức đã hoàn thành việc xây dựng"),),
        note="Completed 1887, but the sheet prints PRESBYTERE INSTITUTION TABERD, so part of it stood in 1882. Excluded because the source dates completion, not the 1882 state.",
    ),
    # ---- identity known, date not in a source we could read: do not guess ---
    Landmark(
        "mariamman-temple", "undated", "Đền Sri Mariamman (Bà Ấn)",
        "way/187949849", "Q4448947", (), None,
        ((wp_url("en", "Mariamman Temple, Ho Chi Minh City"), "built in the late 19th century (no year)"),),
        precise=False, note="OSM start_date says 1885 with no source; Wikipedia says only 'late 19th century'.",
    ),
    Landmark(
        "palais-de-justice", "undated", "Tòa án Nhân dân TP.HCM, 131 Nam Kỳ Khởi Nghĩa",
        "relation/2531662", None, (r"NOUVEAU PALAIS DE JUSTICE",), None,
        ((wp_url("vi", "Tòa án nhân dân Thành phố Hồ Chí Minh"), "article gives no construction year"),),
        precise=False, note="The 1882 label NOUVEAU PALAIS DE JUSTICE sits on the footprint, but no source for the building's date was found.",
    ),
    Landmark(
        "ba-son", "undated", "Xưởng đóng tàu Ba Son (Arsenal de la Marine)",
        "way/1125567704", None, (r"ARSENAL DE LA MARINE",), None,
        ((wp_url("en", "Ba Son Shipyard"), "Naval Arsenal and Shipyard from 1864; no standing building dated"),),
        precise=False, note="A shipyard from 1864, but which of today's buildings are original is unsourced.",
    ),
    # ---- gone: name + source only, no geometry ------------------------------
    Landmark(
        "norodom-palace", "gone", "Dinh Độc Lập (Independence Palace), built 1962-66 on the site of Dinh Norodom / Palais du Gouverneur",
        None, "Q55652939", (r"PALAIS DU GOUVERNEUR",), (1868, 1873),
        ((wp_url("fr", "Palais de l'Indépendance"), "construit entre 1868 et 1873 ... bombardé le 27 février 1962 ... démolir"),
         (wp_url("vi", "Dinh Norodom"), "xây dựng xong 1873 ... bị đập bỏ và thay thế bằng tòa nhà Dinh Độc Lập ngày nay")),
        note="The 2023 Reunification Hall (1962-66, 3,693 m2) stands on the site; it is not the 1882 building.",
    ),
    Landmark(
        "old-marche-central", "gone", "Chợ Bến Thành, the successor market (1912-14, on a new site); the 1870-71 Marché Central stood where the Treasury is now",
        None, None, (r"MARCHE CENTRAL",), (1870, 1871),
        ((wp_url("fr", "Marché Bến Thành"),
          "l'ancien marché ... reconstruit à partir du 30 novembre 1870 ... sur un terrain occupé aujourd'hui par le Trésor"),),
        note="en Wikipedia says the old hall was kept as a wholesale market; no source says it stands today.",
    ),
    Landmark(
        "kham-lon", "gone", "Thư viện Khoa học Tổng hợp Thành phố Hồ Chí Minh, built from 1968 on the site of Khám Lớn Sài Gòn (Grand Prison)",
        None, None, (r"^PRISONS",), None,
        ((wp_url("vi", "Thư viện Khoa học Tổng hợp Thành phố Hồ Chí Minh"),
          "khởi công 28/12/1968 tại số 69 Gia Long, tức vị trí Khám Lớn Sài Gòn cũ"),),
        precise=False, note="Identity of the PRISONS label with the Khám Lớn is by position (label ~100 px from the library).",
    ),
)

KEY_TO_LANDMARK = {m.key: m for m in LANDMARKS}


# ---------------------------------------------------------------------------
# small pure helpers
# ---------------------------------------------------------------------------

def strip_accents(s: str) -> str:
    """Upper-case, accent-free — the form every OCR regex is written against."""
    s = unicodedata.normalize("NFD", s.replace("Đ", "D").replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper()


def year_of(wikidata_time: str) -> int | None:
    """'+1880-00-00T00:00:00Z' -> 1880. BCE and malformed -> None."""
    m = re.match(r"^\+(\d{1,4})-", wikidata_time or "")
    return int(m.group(1)) if m else None


def status_for(built: tuple[int, int] | None, declared: str) -> str:
    """The declared status must agree with the dates; a disagreement is a bug in the table.

    `gone` is not derivable from a date, so it passes through. Everything else is
    decided by the year the building was *finished*."""
    if declared == "gone":
        return "gone"
    if built is None:
        return "undated"
    return "kept" if built[1] <= SHEET_YEAR else "post-1882"


def built_text(built: tuple[int, int] | None) -> str:
    if built is None:
        return ""
    return str(built[0]) if built[0] == built[1] else f"{built[0]}-{built[1]}"


def label_box(label):
    x, y = label["global_x"], label["global_y"]
    return shapely.box(x, y, x + (label["global_w"] or 0.0), y + (label["global_h"] or 0.0))


def box_distance(poly, label) -> float:
    """Pixels from a (warped) footprint to a label's box; 0 when they overlap."""
    return float(shapely.distance(poly, label_box(label)))


def centre_distance(poly, label) -> float:
    """Pixels from a footprint to the centre of a label's box.

    The box is the axis-aligned envelope of the text, so a label printed along a
    diagonal street has a box several times the size of the ink and "0 px from the
    box" is nearly free. The centre is the stricter number and the one the
    confidence tiers and `ocr_label_dist_px` use; the box gap is kept beside it."""
    return float(shapely.distance(poly, label_box(label).centroid))


def match_ocr(poly, labels: list[dict], patterns: tuple[str, ...]):
    """(label, centre_dist_px, box_gap_px) of the nearest accepted matching label, else (None, None, None).

    Rejected rows are duplicate or wrong readings from the other OCR runs; the
    effective text is the human correction when there is one."""
    best = None
    for lab in labels:
        if lab.get("review_status") == "rejected" or lab.get("category") not in OCR_CATEGORIES:
            continue
        if lab.get("global_x") is None:
            continue
        text = strip_accents(lab.get("text_corrected") or lab.get("text") or "")
        if not any(re.search(p, text) for p in patterns):
            continue
        d = centre_distance(poly, lab)
        if best is None or d < best[1]:
            best = (lab, d, box_distance(poly, lab))
    if best is None or best[1] > OCR_MAX_PX:
        return None, None, None
    return best


def confidence(lm: Landmark, *, cover_ok: bool, ocr_dist: float | None) -> tuple[str, str]:
    """high needs a precise date, a footprint that fills its outline AND a label close by.

    Each tier is a stated reason, so a reader can see what is missing. `cap` is
    the hand-set ceiling for what the numbers cannot see (a campus polygon, a
    decade for a date)."""
    if lm.built is None:
        return "low", "no date from any source"
    near = ocr_dist is not None and ocr_dist <= OCR_NEAR_PX
    if lm.precise and cover_ok and near:
        tier, why = "high", f"dated {built_text(lm.built)}; footprint fills outline; label {ocr_dist:.0f} px away"
    elif lm.precise and (cover_ok or near):
        tier, why = "medium", "dated; " + ("footprint fills outline; no label within %d px" % OCR_NEAR_PX if cover_ok else "label near but footprint covers little of the outline")
    elif near and cover_ok:
        tier, why = "medium", "date imprecise (decade or secondary source) but footprint and label agree"
    else:
        tier, why = "low", "date imprecise and footprint/label evidence thin"
    order = ("low", "medium", "high")
    if order.index(lm.cap) < order.index(tier):
        tier, why = lm.cap, why + f"; capped at {lm.cap} by hand"
    return tier, why


# ---------------------------------------------------------------------------
# OSM
# ---------------------------------------------------------------------------

def parse_osm(doc: dict) -> dict[str, dict]:
    """{'way/123': {'tags': {...}, 'geom': shapely geometry in lng/lat | None}}.

    A closed way with >= 4 points is a polygon; a relation is polygonized from
    its member ways' lines. Nodes become points. Anything that will not close is
    kept with geom=None — it still carries tags for the candidate scan."""
    out: dict[str, dict] = {}
    for el in doc.get("elements", []):
        key = f"{el['type']}/{el['id']}"
        geom = None
        if el["type"] == "node":
            geom = shapely.Point(el["lon"], el["lat"])
        elif el["type"] == "way" and el.get("geometry"):
            pts = [(p["lon"], p["lat"]) for p in el["geometry"]]
            if len(pts) >= 4 and pts[0] == pts[-1]:
                geom = shapely.Polygon(pts)
        elif el["type"] == "relation":
            lines = [
                shapely.LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                for m in el.get("members", [])
                if m.get("type") == "way" and m.get("geometry") and len(m["geometry"]) >= 2
                and m.get("role") in ("outer", "")
            ]
            if lines:
                polys = shapely.get_parts(shapely.polygonize(lines))
                if len(polys):
                    geom = shapely.union_all(polys)
        if geom is not None and not geom.is_valid:
            geom = shapely.make_valid(geom)
        out[key] = {"tags": el.get("tags", {}), "geom": geom}
    return out


def osm_is_candidate(tags: dict) -> bool:
    """Tagged as something a landmark would be — before any identity is decided."""
    if tags.get("highway"):
        return False
    return bool(
        tags.get("wikidata") or tags.get("historic") or tags.get("heritage")
        or tags.get("building") in {"cathedral", "church", "temple", "palace", "government", "pagoda",
                                    "shrine", "barracks", "chapel", "monastery", "museum", "civic", "public"}
        or tags.get("amenity") in {"place_of_worship", "townhall", "courthouse", "theatre", "post_office"}
        or tags.get("tourism") in {"museum", "attraction"}
    )


# ---------------------------------------------------------------------------
# network (explicit flags only)
# ---------------------------------------------------------------------------

def _overpass(ql: str) -> dict:
    import requests

    r = requests.post(OVERPASS_URL, data={"data": ql}, headers={"User-Agent": USER_AGENT}, timeout=240)
    r.raise_for_status()
    return r.json()


def fetch_overpass(bbox) -> dict:
    """ONE query for the sheet's box. 504s are common under load; the caller sees the status."""
    b = "%.5f,%.5f,%.5f,%.5f" % (bbox[1], bbox[0], bbox[3], bbox[2])  # south,west,north,east
    return _overpass(OVERPASS_QL.format(bbox=b))


def fetch_relations(ids: list[int]) -> dict:
    """`out tags geom` returns a relation's bounds only, never its members, so the
    relations the table names are fetched by id with `out geom` — one small query."""
    body = "".join(f"relation({i});" for i in ids)
    return _overpass(f"[out:json][timeout:60];({body});out geom;")


def fetch_wikidata(qids: list[str]) -> dict[str, dict]:
    """{qid: {label, P571, P1619, P580, P576, sitelinks}} for each id, 50 per request."""
    import requests

    out: dict[str, dict] = {}
    for i in range(0, len(qids), 50):
        r = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]),
                    "props": "labels|claims|sitelinks", "languages": "en|vi|fr", "format": "json"},
            headers={"User-Agent": USER_AGENT}, timeout=60,
        )
        r.raise_for_status()
        for qid, e in r.json().get("entities", {}).items():
            claims = e.get("claims", {})
            facts = {}
            for p in ("P571", "P1619", "P580", "P576"):
                vals = [c["mainsnak"].get("datavalue", {}).get("value", {}).get("time") for c in claims.get(p, [])]
                facts[p] = [y for y in (year_of(v) for v in vals if v) if y is not None]
            labels = e.get("labels", {})
            out[qid] = {
                "label": (labels.get("en") or labels.get("vi") or labels.get("fr") or {}).get("value"),
                **facts,
                "sitelinks": {k: v["title"] for k, v in e.get("sitelinks", {}).items() if k in ("enwiki", "viwiki", "frwiki")},
            }
    return out


def fetch_ocr_labels(map_id: str) -> list[dict]:
    """Read-only: every ocr_labels row of the sheet, all runs, rejected included (the caller filters)."""
    import requests

    from supabase_client import _headers, _load_config

    url, key = _load_config()
    rows, start = [], 0
    while True:
        r = requests.get(
            f"{url}/rest/v1/ocr_labels",
            params={"select": "text,text_corrected,category,category_corrected,review_status,run_id,"
                              "global_x,global_y,global_w,global_h",
                    "map_id": f"eq.{map_id}"},
            headers={**_headers(key), "Range": f"{start}-{start + 999}"}, timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        start += 1000


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------

def load_buildings_all(bbox):
    """(geoms lng/lat, area_m2 as shipped, height) — modern_prior's reader, all sizes."""
    g, c = mp.load_buildings(bbox)
    return g, np.asarray(c["area_m2"], float), np.asarray(c["height"], float)


def load_topo(bbox):
    """label_congtrinhs points and region_trusos polygons inside the box: (layer, name, geom)."""
    import pyarrow.parquet as pq

    t = pq.read_table(VECTOR_PARQUET, columns=["layer", "name", "geometry"],
                      filters=[("layer", "in", list(TOPO_LAYERS))])
    layer, name = t.column("layer").to_pylist(), t.column("name").to_pylist()
    geom = shapely.from_wkb(t.column("geometry").to_pylist())
    keep = shapely.intersects(geom, shapely.box(*bbox))
    return [(l, (n or "").strip(), g) for l, n, g, k in zip(layer, name, geom, keep) if k]


def utm_area(geom_ll) -> float:
    from pyproj import Transformer

    t = Transformer.from_crs(4326, 32648, always_xy=True)
    g = shapely.transform(geom_ll, lambda xy: np.column_stack(t.transform(xy[:, 0], xy[:, 1])))
    return float(g.area)


def footprints_in(outline, geoms, tree) -> list[int]:
    """Indices of buildings with >= FOOTPRINT_IN_OUTLINE of their area inside `outline` (lng/lat)."""
    hits = tree.query(outline, predicate="intersects")
    keep = []
    for i in hits:
        a = geoms[i].area
        if a > 0 and shapely.intersection(geoms[i], outline).area / a >= FOOTPRINT_IN_OUTLINE:
            keep.append(int(i))
    return keep


# ---------------------------------------------------------------------------
# evaluate one landmark
# ---------------------------------------------------------------------------

@dataclass
class Row:
    lm: Landmark
    status: str
    geom_px: Any = None
    area_m2: float | None = None
    height_m: float | None = None
    n_parts: int = 0
    cover: float | None = None
    in_survivors: bool | None = None
    ocr_text: str = ""
    ocr_dist: float | None = None
    ocr_gap: float | None = None
    ocr_xy: str = ""
    kind: str = ""
    confidence: str = "low"
    why: str = ""
    wikidata_years: list = field(default_factory=list)
    osm_name: str = ""
    topo_names: str = ""
    warnings: list = field(default_factory=list)


def evaluate(lm: Landmark, osm: dict, geoms, areas_raw, heights, tree, fit, labels, topo, wd) -> Row:
    status = status_for(lm.built, lm.status)
    if status != lm.status:
        raise ValueError(f"{lm.key}: declared {lm.status!r} but dates say {status!r}")
    row = Row(lm=lm, status=status)
    qid = lm.wikidata
    facts = (wd or {}).get(qid or "", {})
    row.wikidata_years = sorted(set(facts.get("P571", []) + facts.get("P1619", [])))
    if status == "kept" and any(y > SHEET_YEAR for y in row.wikidata_years):
        row.warnings.append(f"Wikidata inception {row.wikidata_years} is after {SHEET_YEAR}")
    # OCR first: a gone row has no geometry but its label still has a position.
    if lm.osm is None:
        lab = None
        for cand in labels:
            if cand.get("review_status") != "rejected" and cand.get("category") in OCR_CATEGORIES:
                if any(re.search(p, strip_accents(cand.get("text_corrected") or cand.get("text") or "")) for p in lm.ocr):
                    lab = cand
                    break
        if lab:
            row.ocr_text = (lab.get("text_corrected") or lab.get("text") or "").strip()
            row.ocr_xy = "%d,%d" % (lab["global_x"] + (lab["global_w"] or 0) / 2, lab["global_y"] + (lab["global_h"] or 0) / 2)
        row.confidence, row.why = ("medium" if lab and lm.precise else "low"), "no geometry by design"
        return row

    el = osm.get(lm.osm)
    if el is None or el["geom"] is None or el["geom"].geom_type not in ("Polygon", "MultiPolygon"):
        row.warnings.append(f"{lm.osm} has no polygon in the Overpass cache")
        row.confidence, row.why = "low", "no outline"
        return row
    row.osm_name = el["tags"].get("name", "")
    idx = footprints_in(el["geom"], geoms, tree)
    parts = [i for i in idx if utm_area(geoms[i]) >= MIN_PART_M2]
    if not parts:
        row.warnings.append("no 2023 footprint inside the outline")
        row.confidence, row.why = "low", "no footprint"
        return row
    union = shapely.union_all([geoms[i] for i in parts])
    row.geom_px = mp.warp(np.array([union], dtype=object), fit)[0]
    row.area_m2 = round(utm_area(union), 1)
    row.height_m = float(max(heights[i] for i in parts))
    row.n_parts = len(parts)
    outline_m2 = utm_area(el["geom"])
    row.cover = row.area_m2 / outline_m2 if outline_m2 else None
    row.in_survivors = any(areas_raw[i] >= SURVIVOR_MIN_AREA_M2 and heights[i] <= SURVIVOR_MAX_HEIGHT_M for i in parts)
    row.kind = "building" if row.n_parts <= SITE_PARTS and row.area_m2 <= SITE_AREA_M2 else "site"
    lab, dist, gap = match_ocr(row.geom_px, labels, lm.ocr) if lm.ocr else (None, None, None)
    if lab is not None:
        row.ocr_text = (lab.get("text_corrected") or lab.get("text") or "").strip()
        row.ocr_dist, row.ocr_gap = round(dist, 1), round(gap, 1)
    names = []
    for layer, name, g in topo:
        if name and layer == "label_congtrinhs" and el["geom"].buffer(0.00005).intersects(g):
            names.append(name.replace("\r", "").replace("\n", " ").strip())
    row.topo_names = " | ".join(dict.fromkeys(names))
    cover_ok = row.cover is not None and row.cover >= 0.15 and row.n_parts <= 4
    row.confidence, row.why = confidence(lm, cover_ok=cover_ok, ocr_dist=row.ocr_dist)
    return row


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

CSV_COLUMNS = ["status", "key", "name_modern", "name_1882", "wikidata", "osm_id", "built", "built_source", "built_evidence",
               "kind", "area_m2", "height_m", "ocr_label_dist_px", "ocr_box_gap_px", "ocr_label_xy", "confidence", "confidence_why", "in_survivors",
               "n_parts", "osm_cover", "wikidata_inception", "topo_names", "note"]


def props_of(r: Row) -> dict:
    lm = r.lm
    return {
        "key": lm.key,
        "name_modern": lm.name_modern,
        "name_1882": r.ocr_text or None,
        "wikidata": lm.wikidata,
        "osm_id": lm.osm,
        "built": built_text(lm.built) or None,
        "built_source": " ; ".join(u for u, _ in lm.sources),
        "built_evidence": " | ".join(q for _, q in lm.sources),
        "kind": r.kind or None,
        "area_m2": r.area_m2,
        "height_m": r.height_m,
        "ocr_label_dist_px": r.ocr_dist,
        "ocr_box_gap_px": r.ocr_gap,
        "ocr_label_xy": r.ocr_xy or None,
        "confidence": r.confidence,
        "note": " ".join(filter(None, [lm.note, *(f"[!] {w}" for w in r.warnings)])),
    }


def csv_row(r: Row) -> dict:
    p = props_of(r)
    return {
        **{c: ("" if p.get(c) is None else p[c]) for c in CSV_COLUMNS if c in p},
        "status": r.status,
        "confidence_why": r.why,
        "in_survivors": "" if r.in_survivors is None else str(r.in_survivors).lower(),
        "n_parts": r.n_parts or "",
        "osm_cover": "" if r.cover is None else round(r.cover, 2),
        "wikidata_inception": ";".join(map(str, r.wikidata_years)),
        "topo_names": r.topo_names,
    }


def write_outputs(rows: list[Row], out: Path) -> None:
    kept = [r for r in rows if r.status == "kept" and r.geom_px is not None]
    mp._write(out / "landmarks.geojson", [mp._feature(r.geom_px, props_of(r)) for r in kept],
              {"source": "landmarks_1882.py", "note": "2023 footprints warped through the sheet's own affine fit "
               "(rms 33.6 px); hand-check before use as control points"})
    path = out / "landmarks.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        order = {s: i for i, s in enumerate(STATUSES)}
        for r in sorted(rows, key=lambda r: (order[r.status], r.lm.key)):
            w.writerow(csv_row(r))
    print(f"  → {path}  ({len(rows)} rows)")


def write_crops(rows: list[Row], labels, out: Path, base: str, pad: int = 260) -> None:
    from PIL import Image, ImageDraw  # noqa: F401  (ImageDraw used below)

    from iiif_tiles import fetch_crop

    out.mkdir(parents=True, exist_ok=True)
    for r in rows:
        if r.geom_px is None:
            continue
        x0, y0, x1, y1 = r.geom_px.bounds
        x0, y0 = max(0, int(x0) - pad), max(0, int(y0) - pad)
        x1, y1 = min(SHEET_W, int(x1) + pad), min(SHEET_H, int(y1) + pad)
        w, h = x1 - x0, y1 - y0
        scale = 1100 / w
        img = fetch_crop(base, x0, y0, w, h, size=1100)
        d = ImageDraw.Draw(img)
        for poly in shapely.get_parts(r.geom_px):
            d.line([((x - x0) * scale, (y - y0) * scale) for x, y in poly.exterior.coords], fill=(255, 0, 0), width=3)
        for lab in labels:
            if lab.get("review_status") == "rejected" or lab.get("global_x") is None:
                continue
            gx, gy, gw, gh = lab["global_x"], lab["global_y"], lab["global_w"] or 0, lab["global_h"] or 0
            if gx + gw >= x0 and gx <= x1 and gy + gh >= y0 and gy <= y1:
                d.rectangle([(gx - x0) * scale, (gy - y0) * scale, (gx + gw - x0) * scale, (gy + gh - y0) * scale],
                            outline=(0, 90, 255), width=2)
        img.save(out / f"{r.status}-{r.lm.key}.png")
    print(f"  → {out}  (overlay per row: red = warped 2023 footprint, blue = accepted OCR boxes)")


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> int:
    from scale import annotation_for_map

    out = Path(args.out) if args.out else OUT_DIR
    fit = mp.fit_sheet(annotation_for_map(args.map_id))
    if fit is None:
        print("too few ground control points to fit", file=sys.stderr)
        return 1
    bbox = fit.bbox_lonlat(SHEET_W, SHEET_H)
    print(f"sheet {SHEET_W} x {SHEET_H} px   georef {fit}")

    ov_path = out / "landmarks_overpass.json"
    rel_path = out / "landmarks_overpass_relations.json"
    if args.fetch_osm:
        out.mkdir(parents=True, exist_ok=True)
        doc = fetch_overpass(bbox)
        ov_path.write_text(json.dumps(doc), encoding="utf-8")
        print(f"  → {ov_path}  ({len(doc.get('elements', []))} elements)")
        rels = [int(m.osm.split("/")[1]) for m in LANDMARKS if m.osm and m.osm.startswith("relation/")]
        rel_path.write_text(json.dumps(fetch_relations(rels)), encoding="utf-8")
        print(f"  → {rel_path}  ({len(rels)} relations by id)")
    if not ov_path.exists() or not rel_path.exists():
        print(f"no {ov_path.name} / {rel_path.name}; run once with --fetch-osm (two Overpass queries)", file=sys.stderr)
        return 1
    elements = json.loads(ov_path.read_text(encoding="utf-8"))["elements"]
    by_rel = {e["id"]: e for e in json.loads(rel_path.read_text(encoding="utf-8"))["elements"]}
    # the by-id copy carries the members; the box copy carries nothing for a relation but its tags
    osm = parse_osm({"elements": [by_rel.get(e["id"], e) if e["type"] == "relation" else e for e in elements]})

    wd_path = out / "landmarks_wikidata.json"
    qids = sorted({m.wikidata for m in LANDMARKS if m.wikidata}
                  | {t["wikidata"] for t in (e["tags"] for e in osm.values()) if t.get("wikidata", "").startswith("Q")})
    if args.refresh_wikidata or not wd_path.exists():
        wd = fetch_wikidata(qids)
        wd_path.write_text(json.dumps(wd, ensure_ascii=False), encoding="utf-8")
        print(f"  → {wd_path}  ({len(wd)} items)")
    wd = json.loads(wd_path.read_text(encoding="utf-8"))

    geoms, areas_raw, heights = load_buildings_all(bbox)
    tree = shapely.STRtree(geoms)
    topo = load_topo(bbox)
    labels = fetch_ocr_labels(args.map_id)
    page = shapely.box(0, 0, SHEET_W, SHEET_H)
    print(f"buildings {len(geoms)} in box   topo names {len(topo)}   ocr rows {len(labels)} "
          f"({sum(1 for l in labels if l.get('review_status') != 'rejected')} not rejected)")

    # -- 1. candidates -------------------------------------------------------
    px = mp.warp(geoms, fit)
    on_page = shapely.intersects(shapely.centroid(px), page)
    big = areas_raw >= CANDIDATE_MIN_M2
    surv = on_page & (areas_raw >= SURVIVOR_MIN_AREA_M2) & (heights <= SURVIVOR_MAX_HEIGHT_M)
    tagged: dict[int, str] = {}
    for key, el in osm.items():
        if el["geom"] is None or el["geom"].geom_type not in ("Polygon", "MultiPolygon") or not osm_is_candidate(el["tags"]):
            continue
        for i in footprints_in(el["geom"], geoms, tree):
            if on_page[i] and big[i]:
                tagged.setdefault(i, key)
    named: dict[int, str] = {}
    for layer, name, g in topo:
        if not name:
            continue
        if g.geom_type == "Point":
            hits = tree.query(g.buffer(0.00008), predicate="intersects")
        else:
            hits = [i for i in tree.query(g, predicate="intersects") if shapely.intersection(geoms[i], g).area / geoms[i].area >= 0.5]
        for i in hits:
            if on_page[i] and big[i]:
                named.setdefault(int(i), name)
    cand = set(np.flatnonzero(surv).tolist()) | set(tagged) | set(named)
    overlap = {"survivors": int(surv.sum()), "OSM-tagged": len(tagged), "topo-named": len(named)}
    print(f"\ncandidates {len(cand)} footprints (>= {CANDIDATE_MIN_M2:.0f} m2, on the page) = "
          + " U ".join(f"{k} {v}" for k, v in overlap.items()))
    # The survivor filter caps height at 25 m. Which tagged or named footprints did it drop for that alone?
    tall_tagged = sorted(i for i in tagged if heights[i] > SURVIVOR_MAX_HEIGHT_M and areas_raw[i] >= SURVIVOR_MIN_AREA_M2)
    tall_named = sorted(i for i in named if heights[i] > SURVIVOR_MAX_HEIGHT_M and areas_raw[i] >= SURVIVOR_MIN_AREA_M2)
    print(f"  dropped by the {SURVIVOR_MAX_HEIGHT_M:.0f} m cap alone: {len(tall_tagged)} OSM-tagged, {len(tall_named)} topo-named")
    for i in tall_tagged:
        t = osm[tagged[i]]["tags"]
        print(f"    {tagged[i]:<18} {t.get('name', '-')[:44]:<44} {areas_raw[i]:6.0f} m2 h{heights[i]:<4.0f} "
              f"{t.get('wikidata', '')} {t.get('start_date', '')}")

    # -- 2-5. identity, date, status, OCR -----------------------------------
    rows = [evaluate(m, osm, geoms, areas_raw, heights, tree, fit, labels, topo, wd) for m in LANDMARKS]
    counts = {s: sum(1 for r in rows if r.status == s) for s in STATUSES}
    print("rows      " + "  ".join(f"{s} {n}" for s, n in counts.items()))
    for r in rows:
        extra = f"  [!] {'; '.join(r.warnings)}" if r.warnings else ""
        print(f"  {r.status:<9} {r.confidence:<6} {r.lm.key:<20} "
              f"{'' if r.area_m2 is None else f'{r.area_m2:7.0f} m2 h{r.height_m:<3.0f}'} "
              f"{r.kind:<8} ocr {r.ocr_text[:28]!r} {'' if r.ocr_dist is None else f'{r.ocr_dist:.0f}px'}{extra}")
    missed = [r.lm.key for r in rows if r.status == "kept" and r.in_survivors is False]
    print(f"kept rows outside modern_prior's survivor filter: {missed or 'none'}")

    write_outputs(rows, out)
    if args.crops:
        from iiif_tiles import get_iiif_base_from_supabase

        write_crops([r for r in rows if r.geom_px is not None], labels, Path(args.crops),
                    get_iiif_base_from_supabase(args.map_id))
    return 0


# ---------------------------------------------------------------------------
# self-check
# ---------------------------------------------------------------------------

def _self_check() -> None:
    """No network, no data files."""
    # The table itself: keys unique, regexes compile, every claim has a source,
    # and every declared status agrees with its dates.
    assert len(KEY_TO_LANDMARK) == len(LANDMARKS), "duplicate key"
    for m in LANDMARKS:
        assert m.status in STATUSES, m.key
        assert m.cap in ("low", "medium", "high"), m.key
        for p in m.ocr:
            re.compile(p)
            assert p == p.upper() or "\\" in p, f"{m.key}: OCR regex must be written against upper-case text: {p!r}"
        assert m.sources, f"{m.key}: a row without a source is a guess"
        assert all(u.startswith("https://") and q for u, q in m.sources), m.key
        assert status_for(m.built, m.status) == m.status, f"{m.key}: status disagrees with its dates"
        assert (m.osm is None) == (m.status == "gone"), f"{m.key}: gone rows carry no outline, every other row does"
        if m.status == "undated":
            assert m.built is None, m.key
        if m.built:
            assert m.built[0] <= m.built[1], m.key
    assert {m.status for m in LANDMARKS} == set(STATUSES)

    # Dates -> status. A building finished the year the sheet is dated is kept.
    assert status_for((1877, 1880), "kept") == "kept"
    assert status_for((1882, 1882), "kept") == "kept"
    assert status_for((1883, 1883), "post-1882") == "post-1882"
    assert status_for((1875, 1887), "post-1882") == "post-1882"  # started before, finished after
    assert status_for(None, "undated") == "undated"
    assert status_for((1868, 1873), "gone") == "gone"
    assert built_text((1880, 1880)) == "1880" and built_text((1877, 1880)) == "1877-1880" and built_text(None) == ""

    # Wikidata time strings.
    assert year_of("+1880-00-00T00:00:00Z") == 1880
    assert year_of("+0867-01-01T00:00:00Z") == 867
    assert year_of("-0044-03-15T00:00:00Z") is None and year_of("") is None and year_of(None) is None

    # OCR text is compared accent-free and upper-case, so a regex works on either spelling.
    assert strip_accents("COLLÈGE CHASSELOUP LAUBAT") == "COLLEGE CHASSELOUP LAUBAT"
    assert strip_accents("Hôpital Maritime") == "HOPITAL MARITIME"
    assert strip_accents("Mairie Đồng Khởi") == "MAIRIE DONG KHOI"

    # Label matching: rejected rows and street labels never count, the corrected text beats
    # the raw OCR text, and the distance that decides is to the label's CENTRE (the box is
    # the envelope of slanted ink, so a box gap of 0 is cheap).
    poly = shapely.box(100, 100, 200, 200)
    def lab(text, x, y, **kw):
        return {"text": text, "text_corrected": None, "category": "institution", "review_status": "validated",
                "global_x": x, "global_y": y, "global_w": 40.0, "global_h": 10.0, **kw}
    assert box_distance(poly, lab("A", 150, 150)) == 0.0                 # overlaps
    assert abs(box_distance(poly, lab("A", 300, 100)) - 100.0) < 1e-9    # 100 px to the right
    assert abs(centre_distance(poly, lab("A", 300, 100)) - 120.0) < 1e-9  # box centre is 20 px further
    big = lab("A", 0, 0, global_w=1000.0, global_h=1000.0)               # envelope swallows the footprint
    assert box_distance(poly, big) == 0.0 and abs(centre_distance(poly, big) - 300.0 * 2 ** 0.5) < 1e-9
    cands = [lab("COLLÈGE CHASSELOUP LAUBAT", 400, 100),
             lab("COLLÈGE CHASSELOUP LAUBAT", 250, 100, review_status="rejected"),
             lab("Rue Chasseloup-Laubat", 150, 150, category="street"),
             lab("garbage", 220, 100, text_corrected="Collège Chasseloup Laubat")]
    got, d, gap = match_ocr(poly, cands, (r"^COLLEGE CHASSELOUP",))
    assert got is cands[3] and abs(d - 40.0) < 1e-9 and abs(gap - 20.0) < 1e-9, (got, d, gap)
    none = (None, None, None)
    assert match_ocr(poly, [lab("COLLÈGE CHASSELOUP", 900, 100)], (r"CHASSELOUP",)) == none  # past OCR_MAX_PX
    assert match_ocr(poly, [lab("x", 150, 150, category="street")], (r"X",)) == none
    assert match_ocr(poly, [lab("CATHEDRALE", None, None)], (r"CATHEDRALE",)) == none

    # Confidence: each tier needs what it says it needs, and the hand cap wins.
    base = dict(key="t", status="kept", name_modern="t", osm="way/1", wikidata=None, ocr=(), built=(1880, 1880),
                sources=(("https://x", "y"),))
    hi = Landmark(**base)
    assert confidence(hi, cover_ok=True, ocr_dist=60.0)[0] == "high"
    assert confidence(hi, cover_ok=True, ocr_dist=None)[0] == "medium"
    assert confidence(hi, cover_ok=False, ocr_dist=60.0)[0] == "medium"
    assert confidence(hi, cover_ok=False, ocr_dist=OCR_NEAR_PX + 1)[0] == "low"
    assert confidence(Landmark(**base, cap="medium"), cover_ok=True, ocr_dist=0.0)[0] == "medium"
    assert confidence(Landmark(**base, precise=False), cover_ok=True, ocr_dist=0.0)[0] == "medium"
    assert confidence(Landmark(**base, precise=False), cover_ok=True, ocr_dist=None)[0] == "low"
    assert confidence(Landmark(**{**base, "built": None, "status": "undated"}), cover_ok=True, ocr_dist=0.0)[0] == "low"

    # OSM parsing: a closed way is a polygon, a relation is polygonized from its outer ways,
    # an open way and a way without geometry carry tags but no outline.
    sq = [{"lon": 0.0, "lat": 0.0}, {"lon": 1.0, "lat": 0.0}, {"lon": 1.0, "lat": 1.0}, {"lon": 0.0, "lat": 1.0}]
    doc = {"elements": [
        {"type": "way", "id": 1, "tags": {"name": "closed"}, "geometry": sq + [sq[0]]},
        {"type": "way", "id": 2, "tags": {}, "geometry": sq},
        {"type": "way", "id": 3, "tags": {}},
        {"type": "node", "id": 4, "tags": {"historic": "memorial"}, "lat": 1.0, "lon": 2.0},
        {"type": "relation", "id": 5, "tags": {"wikidata": "Q1"}, "members": [
            {"type": "way", "role": "outer", "geometry": sq[:3]},
            {"type": "way", "role": "outer", "geometry": [sq[2], sq[3], sq[0]]},
            {"type": "way", "role": "inner", "geometry": [{"lon": .4, "lat": .4}, {"lon": .6, "lat": .6}]}]},
    ]}
    o = parse_osm(doc)
    assert o["way/1"]["geom"].geom_type == "Polygon" and abs(o["way/1"]["geom"].area - 1.0) < 1e-9
    assert o["way/2"]["geom"] is None and o["way/3"]["geom"] is None
    assert o["node/4"]["geom"].geom_type == "Point"
    assert o["relation/5"]["geom"] is not None and abs(o["relation/5"]["geom"].area - 1.0) < 1e-9
    assert osm_is_candidate({"wikidata": "Q1"}) and osm_is_candidate({"building": "cathedral"})
    assert osm_is_candidate({"amenity": "place_of_worship"}) and not osm_is_candidate({"building": "yes"})
    assert not osm_is_candidate({"wikidata": "Q1", "highway": "primary"})

    # A footprint belongs to an outline by its OWN area, not the outline's.
    outline = shapely.box(0, 0, 10, 10)
    inside, straddle, outside = shapely.box(1, 1, 3, 3), shapely.box(8, 8, 12, 12), shapely.box(20, 20, 22, 22)
    geoms = np.array([inside, straddle, outside], dtype=object)
    assert footprints_in(outline, geoms, shapely.STRtree(geoms)) == [0]   # straddle is 25% in, under the 50% bar

    # Row -> output: gone rows have no geometry and stay out of the geojson; the CSV carries every status.
    kept_row = Row(lm=hi, status="kept", geom_px=shapely.box(0, 0, 10, 10), area_m2=1000.0, height_m=15.0,
                   ocr_text="X", ocr_dist=12.3, confidence="high", why="w")
    gone_row = Row(lm=Landmark(**{**base, "status": "gone", "osm": None, "built": (1868, 1873)}), status="gone")
    c = csv_row(kept_row)
    assert set(c) == set(CSV_COLUMNS) and c["status"] == "kept" and c["ocr_label_dist_px"] == 12.3
    assert csv_row(gone_row)["area_m2"] == "" and csv_row(gone_row)["status"] == "gone"
    assert props_of(kept_row)["built"] == "1880" and props_of(gone_row)["name_1882"] is None

    print("landmarks_1882 self-check OK")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--map-id", default=MAP_ID, help="maps.id (default: the 1882 Plan Cadastral)")
    p.add_argument("--out", help="output directory (default work/image-processing/results/prior/<map-id>)")
    p.add_argument("--fetch-osm", action="store_true", help="make the two Overpass queries and cache them")
    p.add_argument("--refresh-wikidata", action="store_true", help="re-fetch Wikidata facts into the cache")
    p.add_argument("--crops", metavar="DIR", help="write an overlay PNG per geometry row, for the hand check")
    p.add_argument("--self-check", action="store_true")
    args = p.parse_args()
    if args.self_check:
        _self_check()
        return 0
    if args.map_id != MAP_ID:
        p.error("the LANDMARKS table is written for the 1882 Plan Cadastral only")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
