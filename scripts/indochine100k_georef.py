#!/usr/bin/env python3
"""Read series 561's own printed frame against its per-record CartoMundi extent.

Only `annotate --apply` writes to the database; calibration and placement keep
local JSON records. No command publishes a map.

Run with the OCR virtualenv (google-genai is installed there):

    work/ocr/.venv/bin/python scripts/indochine100k_georef.py calibrate --count 12
    work/ocr/.venv/bin/python scripts/indochine100k_georef.py place <map-id>
    work/ocr/.venv/bin/python scripts/indochine100k_georef.py check
    work/ocr/.venv/bin/python scripts/indochine100k_georef.py annotate

`annotate --apply` is draft-only and requires an accepted calibration and a
clean lattice check. The first series-wide calibration failed those gates; see
docs/journals/260923-indochine100k-georef.md.
"""
import argparse
import hashlib
import json
import math
import os
import pickle
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "work/ocr/scripts"))
import iiif_tiles as T  # noqa: E402

WORK = Path("work/indochine-100k")
SOURCE = WORK / "sources/serie-561.json"
OFFSET_FILE = WORK / "catalogue-offset.json"
OBS_FILE = WORK / "calibration-observations.json"
REPORT_FILE = WORK / "calibration-report.json"
FIT_FILE = WORK / "calibration-fit.json"
CAL_VERSION = 1
# Increment when detection changes so place() revisits saved local placements.
DETECT_VERSION = 39
COLLECTION = "Indochine 1:100,000 — 2nd édition SGI (1947–1959)"
OV, PATCHES, SPAN = 1800, 24, (0.12, 0.88)
ACROSS, MAXIN, MINGAP, LIM, TRIM = (190, 300), 250, 10, 34, 3.0
# The overview peak already locates the thick frame line closely. A wider search
# can lock onto a neighbouring graticule/rim line 20-30 px away, making a sound
# rim appear to have an anomalous offset (Gia Ray, Kratié, Hà Giang).
NEAR, RESIDUAL = 12, 15.0
GRADE, PARIS = 0.9, 2.337229166666667
BUCKET = "annotations"
CORNERS = ("NW", "NE", "SE", "SW")
# Tri Binh (W) ("1f025a9f-...") was held here after its 2026-09-23 two-tick
# Gemini read came out 741.5m off the accepted latitude fit -- removed
# 2026-09-30 after a three-tick-per-axis re-read (SOURCE_REVIEWED_CORRECTED_BOX)
# found the catalogue's own west/south fields wrong by ~510-540m and corrected
# them directly; see that registry's comment for the full reading.
CALIBRATION_HOLDS = {
    # Detects cleanly on every per-sheet gate; only check()'s cross-sheet series
    # median catches it. That check is stateful (it compares against whichever
    # sheets are currently placed), so a hold that lives only in check()'s
    # output does not survive a DETECT_VERSION bump -- place() just regenerates
    # a fresh, locally-clean JSON. Recorded here so it can't be silently wiped
    # again (2026-09-24: DETECT_VERSION 3->4 did exactly that).
    "7d1e6918-25a0-481b-b798-04b8df15aa57": "Pursat (E): rim offsets agree with each other but differ >15% from series median; different frame convention, unverified",
    "13b11b89-ced4-4eaf-907a-19d7806a3dca": "Kompong Sralao (W): footprint overlaps cell 154 W after guided rim recovery; placement unverified",
}

# Four mapped boundaries on each of these sheets were checked against marked
# source strips on 2026-09-27. The outer decorative frame is inconsistent, so
# its offset spread is not evidence against the mapped quad. Pin the reviewed
# rim positions: a later detector change must not inherit this review if it
# selects a different line. Values are L/R x and T/B y at the fitted anchor.
SOURCE_REVIEWED_RIMS = {
    "a387ff3f-05c4-4d46-8470-079323555c40": (344.60, 4759.52, 711.998, 6621.165),  # Lai Châu (E)
    "dcfb2452-b976-4092-bddb-8c9e04300db3": (323.414, 4743.445, 1040.030, 6950.208),  # Tu Lê (E)
    "d7561735-d521-4aa7-ba74-de5b3e992789": (313.3, 4720.7, 684.6, 6598.6),  # Bac-Kan (E)
    "8f06c5b2-807b-4501-9f5c-c2bedcde85c1": (301.7, 4686.3, 680.5, 6587.6),  # Bai-Thuong (W)
    "aa3c4bcb-9070-40dc-8ce0-9bd098429f28": (327.2, 4742.6, 623.8, 6502.0),  # Beng Lovéa (E)
    "557c1b72-ecbf-4113-8c29-4efb16cea25e": (291.9, 4703.2, 621.5, 6530.2),  # Bô Kham (E)
    "c4a6bf0a-278d-4125-9e2e-6e7a155b7e9e": (285.0, 4769.7, 582.1, 6495.4),  # Cam Pha ouest (W)
    "50689317-5dbf-46db-ba84-0fa4c0a67213": (347.7, 4763.8, 641.6, 6552.3),  # Dong-Hoi (W)
    "e19c409d-e2bb-469e-8c6c-ed7c8d3fcf3f": (332.9, 4746.3, 596.8, 6509.1),  # Dô-Son (W)
    "d1db5882-a158-43d8-8ae8-420b57f13919": (297.6, 4713.3, 574.4, 6495.4),  # Blao (W)
    "59b7ab12-6586-4aec-9e3a-55b5fb6624de": (321.4, 4735.2, 639.5, 6555.3),  # Hai Phong (E)
    "826a2182-bc32-4fa7-babe-59c784ec1440": (245.3, 4643.9, 628.6, 6558.6),  # Muong-Phine (E)
    "8714ef04-fd0b-44be-a324-1fefd2db9976": (359.2, 4754.5, 671.6, 6595.2),  # Trang Bang (W)
    "9038fcc1-e05b-4217-92a5-1942e2b0da80": (173.0, 4573.5, 600.6, 6515.4),  # Lovéa (E)
    "90b6dcd2-269e-4829-9d22-32e92c5d68ee": (340.5, 4732.2, 614.5, 6523.2),  # Pak-Seng (W)
    "dd3e54c5-a7af-46fe-8e51-9bd79be31b98": (172.9, 2791.5, 369.0, 3875.4),  # Phsar Oudong (E)
    "dd513b9b-d4de-439e-9a49-694827a647f6": (373.4, 4798.4, 872.8, 6782.2),  # Bao-Lac (W)
    "287d7a08-d14e-4186-a0e3-e31c1456a4e2": (295.9, 4721.1, 681.5, 6593.9),  # Bac-Kan (W)
    "84fd3f51-4dda-4e87-8b5f-925b47c7c4a3": (307.7, 4717.2, 582.4, 6489.1),  # Kompong Chhnang (E)
    "da274467-2985-43b4-a0ae-dc6f2b64ef4a": (265.1, 4681.7, 494.3, 6385.5),  # Qui Nhon (W)
    "e13bcdfc-b852-4349-8119-f988ff6e44ec": (374.4, 4765.9, 705.4, 6615.6),  # Phnom Deck (E)
    "d5139795-2c78-4159-a376-0ef11f1c0f46": (379.2, 4775.2, 656.9, 6566.8),  # Trapéang Chong (E): wider decorative band
    "3d8d139e-7609-4d57-94dc-733e35032ae6": (362.8, 4758.6, 662.1, 6555.8),  # Battambang (W)
    "452e84c2-e679-4075-b281-bbe4aea41154": (287.0, 4682.9, 616.8, 6515.8),  # Dak To (E)
    "5c06d0d8-65c8-453b-8313-c3dc88e0a2d4": (325.5, 4747.7, 579.1, 6481.3),  # Kralanh (W)
    "d7a35019-ec33-4418-8733-334ee1e4d313": (410.8, 4809.7, 707.0, 6604.3),  # Ninh Binh (E)
    "e43f0089-a1bf-4fc1-a8db-1defaeb24e9a": (271.9, 4669.6, 657.1, 6545.2),  # Mimot (E)
    "03e339a6-e196-41df-a7bc-5f77491634f1": (296.6, 4702.2, 615.6, 6530.7),  # Kompong Chhnang (W)
    "4981483e-68b0-485a-a7d5-d319b15b3147": (311.3, 4734.3, 585.3, 6502.0),  # Gia Ray (E)
    "583fa8fd-e5d5-4ca8-aa46-43ef3781fca7": (302.6, 4706.6, 648.0, 6556.0),  # Banteai Srei (W)
    "60a3de16-8bb6-4827-9b1b-d51a50320689": (319.3, 4732.7, 657.9, 6571.7),  # Lôc Ninh (E)
    "69c78109-7163-4434-bd24-1662e7b15a49": (318.0, 4735.1, 632.4, 6552.4),  # Tây Ninh (E)
    "6ef896bf-d4cf-4202-b402-7693d70154bc": (320.2, 4739.2, 623.9, 6523.1),  # Beng Lovéa (W)
    "7530d40e-cbb0-4521-b12a-c99acffec27d": (411.2, 4839.2, 619.0, 6515.0),  # Nam Dinh (W)
    "79ee184d-f9cc-435f-a5c9-23896d14930d": (358.5, 4773.2, 588.2, 6490.9),  # Banteai Srei (E)
    "7c7b90fa-a2ef-4978-8765-75127fc5b0a3": (329.7, 4727.7, 673.6, 6573.6),  # Battambang (E)
    "8fcd3ac5-7661-4284-9e43-d9dbcd5213fc": (310.3, 4703.5, 676.3, 6596.4),  # Bac-Ninh (W)
    "9839a452-f7f8-4a10-a865-4e900eaa0788": (307.9, 4729.6, 609.4, 6520.6),  # Saigon (W)
    "9a1808b9-be9c-4323-9574-9d56bec7b5ca": (300.8, 4714.0, 681.5, 6578.2),  # Prey Veng (E)
    "b2ced5b1-57e4-4406-93ff-9f2d44d25f9f": (358.8, 4770.3, 591.8, 6460.5),  # Mimot (W)
    "c8846603-1059-4d7f-be78-75708191e447": (318.7, 4744.2, 675.4, 6564.1),  # Tô Bông
    "dfe53d27-d8d1-4410-b107-941e5fa19061": (294.0, 4715.0, 650.2, 6552.2),  # Hai Phong (W)
    "e0555f42-2f14-4075-b0d5-b0e68ce81a1e": (337.2, 4760.0, 611.6, 6526.9),  # Saigon (E)
    "f4201ba5-30de-46e8-8ae6-b109b9dc6f41": (326.9, 4755.6, 692.2, 6616.6),  # Kompong Thom (W)
    "60b8180d-71de-4402-b994-d44b6e4a2c85": (405.4, 9225.5, 570.7, 6450.5),  # Poste du Lac full sheet
    # Second batch, reviewed 2026-09-29: same decorative-frame inconsistency.
    # Verified with a per-pixel profile localised to each anchor (paper
    # plateau ends within ~3px of the pin; contact-scale and fixed-window
    # crops missed a 52px interior-grid-line miss on two of these sheets
    # before this method caught it -- see the 2026-09-29 journal entry).
    "5e1ca3a9-4e94-4ec4-976a-86c13ad12b27": (305.7, 4717.5, 499.4, 6408.1),  # Kratié (E)
    "b12f0296-9d70-4ec2-83fd-90fb57fba38a": (306.8, 4718.4, 581.9, 6494.4),  # Krau Chmar (E)
    "488d9453-88ba-4c6d-ade4-b221e95d735e": (293.1, 4699.7, 661.2, 6574.5),  # Luc-An-Chau (E)
    "ab592683-7ea2-43e7-bf78-bbcbc8dc1045": (323.2, 4720.2, 618.1, 6529.8),  # Luc-An-Chau (W)
    "65559440-3d12-4cfe-9d52-9e872564f3bd": (247.2, 4676.2, 650.0, 6552.4),  # Muong Ou Tay (W)
    "09a93bb7-56f4-4e0a-99df-8bcc69a9a64a": (395.9, 4803.6, 747.0, 6661.9),  # Muong Phalane (E)
    "e6ee3683-83a9-4497-b95e-7b38a0dc5c12": (365.7, 4790.7, 719.3, 6626.3),  # Muong Phine (W)
    "e19e7743-f209-4947-a2d1-d40c3a11948d": (360.6, 4792.6, 736.6, 6639.8),  # Muong Song Khone (W)
    "96bb8a0d-67c0-4762-9eb6-85c9be8df23c": (363.8, 4797.1, 702.6, 6612.2),  # Muong-Song-Khone (E)
    "83501380-a456-4687-a6b7-76f798925a7e": (349.0, 4750.9, 660.4, 6563.0),  # Muong-Vène (W)
    "45e9e857-f40a-494e-904a-3b2ef0bc0d7d": (360.2, 4778.5, 726.9, 6650.8),  # Pa-Kha (E)
    "fbe9e63d-1b00-44b4-b88f-50f67a3c5871": (317.0, 4756.7, 683.5, 6605.0),  # Pa-Kha (W)
    "a8039626-c205-4a4d-a136-87acb33c2fc8": (324.7, 4726.5, 686.7, 6606.5),  # Than-Poun (E)
    # Marked crops show T/B's automatically-detected lines are already correct
    # (a "different candidate" a few px away is the same printed line, not a
    # second rule) -- the sheet's top/bottom margin is genuinely wider than
    # its left/right, tripping the spread gate on a real, not a wrong, rim.
    "1ce2d961-4147-44eb-964c-9a7f64ea48d4": (401.2, 4810.6, 780.7, 6694.7),  # Muong-Tè (E)
    "8289d9a6-6780-4f1e-8ead-7f9f137d6ada": (324.5, 4932.3, 607.5, 6514.5),  # Ha-Lang (W)
    "f9fc556b-8311-4e0a-8f72-fd5801b13ef1": (189.7, 4770.2, 730.4, 6642.4),  # Quan-Ba (E)
    # 2026-09-30: Phan Rang (E)'s B side sits ~25px outside the ~170-175px
    # family band on all other sides (199.2px). Per-pixel profile of the B
    # strip: uniformly blank paper (values 20-24) from the family-band offset
    # all the way out to where the one real line rises (index ~175-195,
    # peaking ~102) -- no second/competing line anywhere in between, so this
    # is the same "genuinely wider margin on this side" case as Muong-Tè (E)/
    # Ha-Lang (W)/Quan-Ba (E) above, not a double-frame pick.
    "c19c68a6-5ce8-4b74-86ec-9272f0c98a21": (331.52, 4739.89, 646.82, 6557.5),  # Phan Rang (E)
    # 2026-09-30: Sam-Neua (E) -- required so the SOURCE_REVIEWED_BOUNDARIES
    # manual fix below (both B and R corrected) can pass the "still reproduces
    # what was reviewed" gate. Anchor positions as `detect()` actually computes
    # them post-fix, not the raw target values.
    "85967c9c-9bb7-4acb-9688-2eaf3d93216b": (300.3, 4708.1, 616.3, 6723.9),  # Sam-Neua (E)
    # 2026-09-30 (superseded 2026-09-30, later): the B side was locked at 6787.56,
    # which is the caption text under the sheet, ~200px below the map's own bottom
    # line (the "1200K" grid line at y=6589, per-pixel profile on empty sea). Left
    # as a strip too tall by 3.4%, it showed as a wrong bottom edge on the map and
    # as the y scale (8.18 m/px) disagreeing with x (8.47) — which was then
    # explained away as "real printed-sheet distortion". Corrected to 6589.5.
    # The earlier note follows, and is wrong about which line is "the only real line":
    # Phu Diên Châu (E)'s B side sits ~23px outside the
    # ~166-171px family band on L/R/T (193.5px). Native crop of the strip
    # confirmed the tick label's own ink is what a naive full-width column
    # scan picks up as a weak secondary peak inside the family band -- no
    # competing frame/grid line actually sits there; the strong, wide peak at
    # the detected offset is the only real line. Same "genuinely wider
    # margin on this side" case as Phan Rang (E) above.
    "65366fa5-092a-4225-a576-69e83bf4c647": (374.83, 6003.26, 669.38, 6589.5),  # Phu Diên Châu (E)
    # 2026-09-30: Lang Son (E) -- required so the SOURCE_REVIEWED_BOUNDARIES
    # direct fix above (both R and B corrected) can pass the "still reproduces
    # what was reviewed" gate. Anchor positions as `detect()` actually computes
    # them post-fix, not the raw target values.
    "5300b1fc-7b90-4c8d-a800-5f369bea96ca": (401.72, 4958.92, 715.99, 6796.50),  # Lang Son (E)
}

# 2026-09-30: sheets whose catalogue UNIMARC corner is confirmed *wrong*, not
# merely unusual (that's SOURCE_REVIEWED_SPECIAL_SPANS, which only lets an
# already-correct declared span through the standard-span gate -- it has no
# way to substitute a different number). record_box() overlays these fields
# onto the fkey's own UNIMARC box before computing the span, keyed by map id
# and gated on the fkey still matching.
#
# Phan Rang (E)/(W) (fkey 60739/60742): catalogue declares both sheets
# abnormally tall (~0.608-0.609g lat, standard band is 0.48-0.53g) by nearly
# the same amount -- the sub-pattern flagged 2026-09-30 as distinct from the
# sibling-width cases (no standard sibling to borrow from, error too large
# for the special-span precedent). Read each sheet's own printed parallel
# grid (four to five 0.10g-spaced ticks along the left margin, native crops,
# `fetch_crop`, text-center pixel position via a darkness-threshold scan) and
# fit a line (y-pixel -> grade north) to extrapolate the north/south corner
# grades. North matches the catalogue within 0.001-0.002 deg on both sheets
# -- not touched. South is off by 5.8' (Phan Rang E) and 3.1' (Phan Rang W).
# Cross-checked against `detect()`'s independently-measured pixel aspect
# ratio (which never consults the catalogue): 2.7% and 2.1% residual once
# corrected, against 14-16% before. Full reading in
# docs/journals/260923-indochine100k-georef.md.
SOURCE_REVIEWED_CORRECTED_BOX = {
    "c19c68a6-5ce8-4b74-86ec-9272f0c98a21": ("60739", {"s": 11.20180}),  # Phan Rang (E)
    "3d0a6cca-5ca3-4ceb-9334-5374d4d2afb4": ("60742", {"s": 11.16400}),  # Phan Rang (W)
    # 2026-09-30: Tri Binh (W) -- the original 2026-09-23 calibration-sample
    # read (Gemini, two ticks per axis) found catalogue-minus-printed -460m
    # east / -492m north, an internally-plausible but 250m-gate-failing
    # outlier that got the sheet dropped from the calibration fit and held
    # under CALIBRATION_HOLDS rather than corrected. Redone here with three
    # ticks per axis (118.20/118.30/118.40g on the top margin, 17.40/17.30/
    # 17.00g on the left margin), read the same no-Gemini way as the coastal
    # family: both intervals on each axis agree with each other to <0.3%
    # (11740 vs 11768 px/g on latitude; 11375 vs 11340 px/g on longitude).
    # East and north both match the catalogue closely (-59m, +50m -- within
    # reading noise); west and south are the two that are actually wrong, by
    # +509m and +544m respectively (catalogue's box is very slightly too
    # wide and too tall). Corrected fields below now come from the sheet's
    # own printed grid, not the axis this session couldn't reproduce.
    "1f025a9f-ea9e-4816-ad35-edfba60bf518": ("60391", {"w": 108.636689, "s": 15.274067}),  # Tri Binh (W)
    # 2026-09-30: Quang Ngai -- the "third" unresolved abnormal-span sheet
    # from the coastal-family investigation (0.523g x 0.510g declared, 0.428g
    # implied by pixel-aspect matching against the catalogue's own,
    # presumably-correct, latitude span). Read the sheet's own four printed
    # longitude ticks (118.20/118.30/118.40/118.50g along the top margin,
    # spacing consistent to <0.6%): west matches the catalogue closely
    # (+256m, within reading noise) but east is off by ~9.2km -- corrected
    # east gives a printed span of 0.4281g, matching the independent
    # pixel-aspect estimate (0.4280g) almost exactly. Now inside the standard
    # 0.36-0.43g band on its own, no SOURCE_REVIEWED_SPECIAL_SPANS needed.
    "48584dae-d4e3-4821-82a1-bab588ec3dd2": ("60407", {"e": 109.011425}),  # Quang Ngai
    # 2026-09-30: the coastal ~0.49g family (retracted sibling rule, see the
    # 09-30 journal entries). Printed longitude ticks read on both W/E, not
    # just one side as with Phan Rang -- west residual against the catalogue
    # is small but not negligible (0.4-1.6%) on all four, east's is 3-4x
    # larger and consistent in sign; rather than trust catalogue west and
    # correct east alone, both fields use the sheet's own printed reading, an
    # internally self-consistent pair independently within ~1% of the
    # pixel-aspect-implied span on 3 of 4. Full reading:
    # docs/journals/260923-indochine100k-georef.md, "the coastal ~0.49g
    # family, redone at landing-grade precision".
    "65366fa5-092a-4225-a576-69e83bf4c647": ("60219", {"w": 105.493015, "e": 105.946408}),  # Phu Diên Châu (E)
    "ba3f38a6-78ed-49d6-a656-8390961cab3b": ("60498", {"w": 108.959793, "e": 109.400596}),  # Qui Nhon (E)
    "7bf1330c-2cf2-4974-9daa-dded9ed72d00": ("60546", {"w": 108.963964, "e": 109.408290}),  # Söng Cau (E)
    "e8b02c15-5e15-4bc5-bf99-b5d4e2c008e2": ("60651", {"w": 108.942315, "e": 109.380224}),  # Nha Trang (E)
}

# These nonstandard cuts have real catalogue spans. The full source overviews
# show the detected quadrangle on the printed mapped boundary, including blank
# terrain along the northern edge (where an ink-transition test is misleading).
# Store fkey, span in grades, source dimensions, and reviewed L/R/T/B anchors.
# Both catalogue identity and pixel geometry must still match on regeneration.
SOURCE_REVIEWED_SPECIAL_SPANS = {
    "1eda9df3-4ee3-4555-92a8-47c50b447fc3": ("60611", .77068, .51173, 9476, 7096, (294.5, 9134.3, 657.9, 6550.7)),  # Phnom Leach full sheet
    "261c851c-4c2c-4243-8155-9a2dc201dd25": ("60434", .39012, .60556, 5052, 8540, (318.7, 4734.1, 575.6, 7671.0)),  # Anlong Veng E
    "38305a6d-b86f-41af-8f5d-b4b8f7f6d9df": ("60437", .38920, .60494, 5130, 8540, (325.1, 4739.5, 569.3, 7668.1)),  # Cheom Ksan W
    "3a5be1b2-b181-47f7-85f2-179b72954f78": ("60436", .38827, .60432, 5134, 8586, (339.8, 4750.3, 635.0, 7730.2)),  # Cheom Ksan E
    "43cc3dd1-6e1a-4419-9602-8271d589b47a": ("60432", .39198, .60679, 5050, 8452, (300.3, 4720.7, 568.0, 7661.3)),  # Chong Kal E
    "60b8180d-71de-4402-b994-d44b6e4a2c85": ("60648", .77068, .51142, 9688, 7204, (405.4, 9225.5, 570.7, 6450.5)),  # Poste du Lac full sheet
    "61272041-c511-4384-91af-f4694954f79c": ("60288", .55154, .50340, 7148, 7288, (432.5, 6802.1, 619.6, 6697.4)),  # Ron E
    "c4963daf-5b8a-4448-a1d2-8fbebfafcbed": ("60066", .81481, .51142, 9502, 7342, (306.0, 9131.2, 635.7, 6527.1)),  # Luân Châu double format
    "f8c55f03-0aa0-47ef-8c68-badf98156649": ("60433", .39290, .60741, 5152, 8542, (374.4, 4790.6, 636.9, 7731.8)),  # Chong Kal W
    # 2026-09-29: five more of the 24 abnormal-span holds, confirmed the same
    # way as the batch above -- detect() (which does not consult the catalogue
    # span) found a clean four-sided fit (16-24/24 patches kept, 0.3-5.5px
    # residual, ~165-177px decorative-frame offset matching the family's usual
    # band) whose pixel aspect ratio matches this fkey's own declared ground
    # span within 5%. Thanh Hoa (E) and Vinh (E) are the same wide-lon,
    # standard-lat shape already seen on Ron (E) above.
    "edd8be90-fa2d-422f-aa46-cbc1f6c657ac": ("60778", .38642, .60741, 5162, 8376, (383.15, 4791.65, 589.40, 7459.04)),  # Phan Thiet E
    "04f35f4f-b19a-4992-bfc7-d1da75a9ddba": ("60780", .38580, .60679, 5166, 8448, (369.85, 4786.90, 603.64, 7477.13)),  # Phan Thiet W
    "283ae0d8-dca7-4a2d-a86e-1e56dc08527e": ("60202", .55679, .50216, 6612, 7566, (305.11, 6269.67, 625.19, 6544.97)),  # Thanh Hoa E
    "99adde4f-9d56-4a66-b186-6c8e81b63d39": ("60240", .55370, .50247, 6684, 7548, (290.23, 6234.86, 629.10, 6550.42)),  # Vinh E
    "edb34855-cc39-4b9b-83cd-113f5aafb505": ("60245", .40556, .70864, 5322, 9900, (457.37, 4869.98, 688.81, 8963.24)),  # Vientiane Ban Keun E
    # 2026-09-30: Phan Rang (W) after its SOURCE_REVIEWED_CORRECTED_BOX south
    # fix above still sits 0.02g over the standard lat_g cap (0.550 vs 0.53)
    # -- register the *corrected* span here so it passes. (Phan Rang (E)'s
    # correction lands inside the standard band on its own, no entry needed.)
    "3d0a6cca-5ca3-4ceb-9334-5374d4d2afb4": ("60742", .38796, .55019, 5040, 8136, (332.54, 4739.29, 742.1, 7192.22)),  # Phan Rang W
    # 2026-09-30: the coastal ~0.49g family, corrected box above still sits
    # outside the standard 0.36-0.43g longitude band (that's the whole point
    # -- these are a genuine third span family, not a transcription slip back
    # into standard range) -- register the corrected span so it passes.
    "65366fa5-092a-4225-a576-69e83bf4c647": ("60219", 0.503770000000006, 0.502160493827163, 6414, 7134, (374.83, 6003.26, 669.38, 6589.5)),  # Phu Diên Châu E
    "ba3f38a6-78ed-49d6-a656-8390961cab3b": ("60498", 0.48978111111109807, 0.5111111111111121, 6258, 7442, (309.79, 5900.22, 649.88, 6565.16)),  # Qui Nhon E
    "7bf1330c-2cf2-4974-9daa-dded9ed72d00": ("60546", 0.49369555555554395, 0.5111111111111101, 6236, 7032, (336.18, 5913.78, 588.43, 6490.32)),  # Söng Cau E
    "e8b02c15-5e15-4bc5-bf99-b5d4e2c008e2": ("60651", 0.48656555555556086, 0.5111111111111121, 6234, 7540, (300.82, 5893.72, 606.37, 6525.0)),  # Nha Trang E
}

# On these Bonne sheets the graticule slants across the rectangular map
# frame. Catalogue extrema mix opposite corners and create a false axis-scale
# failure. Two labelled ticks on each of T/B/L/R were read independently and
# inspected in source crops. Four corner grades are interpolated from those
# eight ticks; pin the detected L/R/T/B rims so a changed scan cannot silently
# reuse the review. Values are grades east of Paris and north, not WGS 84.
SOURCE_REVIEWED_PRINTED_QUADS = {
    "8a876d4c-7193-461b-b60d-851df9542a1f": {
        "rims": (368.91053128536817, 4783.497676520706, 690.5222459564903, 6607.742899492821),  # Diên Biên Phu (E)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (112.183156632, 24.002415802),
            "NE": (112.585579330, 24.006341894),
            "SE": (112.593203910, 23.504883670),
            "SW": (112.191696225, 23.500390317),
        },
    },
    "c7b7949d-de54-4341-8616-a256dddd5771": {
        "rims": (337.1051227890517, 4746.775480294141, 631.1795968560598, 6548.206775990109),  # Khang Khai (E)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (112.216952228, 21.994982550),
            "NE": (112.613861505, 21.999137187),
            "SE": (112.620601080, 21.498543611),
            "SW": (112.224582932, 21.493115199),
        },
    },
    "2b289c7e-b8fb-4f91-8718-7baa688f6db4": {
        "rims": (330.72484188647155, 4749.013179809603, 638.7116158104285, 6557.48435698031),  # Luang Prabang (E)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (110.613807072, 22.471750837),
            "NE": (111.012569492, 22.478610934),
            "SE": (111.023751294, 21.977444822),
            "SW": (110.626065640, 21.969876464),
        },
    },
    "3b61a7ea-09dc-41cf-9a0c-a29402dfadeb": {
        "rims": (354.91004974438283, 4775.784415039244, 608.8269746661283, 6521.856294380891),  # Luân Châu (W)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (111.771469979, 24.498741251),
            "NE": (112.175010319, 24.503032754),
            "SE": (112.182620159, 24.001655506),
            "SW": (111.780547906, 23.997222250),
        },
    },
    "03973ced-e945-4fa1-923b-b66a526eabf8": {
        "rims": (336.7746566734879, 4752.979922615636, 578.5161156180557, 6491.981391326406),  # Pak Seng (E)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (111.411308942, 22.485438249),
            "NE": (111.809881727, 22.490932230),
            "SE": (111.818595879, 21.989793239),
            "SW": (111.421278159, 21.984157654),
        },
    },
    "b90ff4e3-f256-43f0-9316-52163827f955": {
        "rims": (417.396709614656, 4836.593330196112, 655.4293657682131, 6569.107618083206),  # Luân Châu (E)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (112.178044810, 24.503108179),
            "NE": (112.581071824, 24.508386559),
            "SE": (112.586129267, 24.008075983),
            "SW": (112.183102254, 24.002091149),
        },
    },
    "db0171f6-564e-4d7c-94a6-cde0f8b4198f": {
        "rims": (293.43425881585443, 4705.947988131286, 647.3927784357215, 6562.703494952946),  # Ban-Calan (E)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (111.343940122, 25.496069767),
            "NE": (111.749874990, 25.502162879),
            "SE": (111.760847304, 24.999801230),
            "SW": (111.355471832, 24.993708117),
        },
    },
    "dd424aed-fd34-4882-a2b7-6953ec6d82d9": {
        "rims": (347.0423183452041, 4759.121108579781, 622.5813211671532, 6535.550387073513),  # Ban-Calan (W)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (110.937321518, 25.489359318),
            "NE": (111.343216268, 25.495901726),
            "SE": (111.355287618, 24.994165176),
            "SW": (110.951436274, 24.987409807),
        },
    },
    "ae3c2983-9710-416b-82e6-7448c1414c78": {
        "rims": (369.79916269692535, 4783.64062168136, 787.0309001496204, 6703.585485390793),  # Diên Biên Phu (W)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (111.780834240, 23.996702758),
            "NE": (112.182823061, 24.002274487),
            "SE": (112.191436263, 23.500233845),
            "SW": (111.790906566, 23.495087755),
        },
    },
    "10e6a00f-2aea-42d1-8c41-370fc0993099": {
        "rims": (337.63830258689967, 4735.842757883647, 656.1774455069896, 6552.079537359292),  # Muong-Tè (W)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (110.950989295, 24.986085668),
            "NE": (111.353939677, 24.996397203),
            "SE": (111.368191712, 24.493762873),
            "SW": (110.966895780, 24.486221260),
        },
    },
    "90b6dcd2-269e-4829-9d22-32e92c5d68ee": {
        "rims": (340.51427618609307, 4732.154539405785, 614.4754086850386, 6523.154121838206),  # Pak-Seng (W)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (111.012758026, 22.479491539),
            "NE": (111.410728259, 22.485155142),
            "SE": (111.420166089, 21.983041135),
            "SW": (111.022915838, 21.977164092),
        },
    },
    "753b93ac-e569-4a49-8018-e089354e2be2": {
        "rims": (252.79107858206498, 4662.971514921339, 696.8782773089131, 6609.36332535565),  # Phong-Saly (W)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (110.156076233, 24.470243908),
            "NE": (110.559569350, 24.478581031),
            "SE": (110.573932498, 23.976991709),
            "SW": (110.172276782, 23.968654585),
        },
    },
    "3b2b62bb-5557-477e-888f-bed1fa477fe2": {
        "rims": (374.3005117662249, 4784.465807986187, 708.9762586721122, 6627.861189434911),  # Than-Poun (W)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (116.614871180, 24.515891323),
            "NE": (117.018916255, 24.510752173),
            "SE": (117.011747354, 24.011058878),
            "SW": (116.609361224, 24.013440808),
        },
    },
    "38d8877f-64e9-42cf-bb98-8ac90c5d3c8f": {
        "rims": (297.27832310140224, 4705.935828056417, 715.0861551895207, 6630.868523806068),  # Khang Khai (W)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (111.818501789, 21.989653691),
            "NE": (112.216574443, 21.994967951),
            "SE": (112.224905613, 21.493205565),
            "SW": (111.827550530, 21.487465361),
        },
    },
    "e7cc411f-63a5-46c8-81da-719ec613014b": {
        "rims": (312.36552936273756, 4744.299319937893, 735.9862507703231, 6639.662987202191),  # Muong Ou Tay (E)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (110.545708030, 24.980328702),
            "NE": (110.950446034, 24.987730243),
            "SE": (110.964590303, 24.485936227),
            "SW": (110.560405977, 24.478960838),
        },
    },
    "c18b8494-09c5-43e6-bd9b-18f40696b32e": {
        "rims": (345.73998535389154, 4774.156403891573, 742.2560022103733, 6664.551583671473),  # Muong Soui (E)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (111.420949523, 21.983868869),
            "NE": (111.819545663, 21.989446051),
            "SE": (111.827611055, 21.487132412),
            "SW": (111.431155986, 21.481342115),
        },
    },
    "4e70153f-d765-4966-a794-e5d86c8fa6d8": {
        "rims": (377.9697113151658, 4803.539734361143, 689.3207157676811, 6607.580579533706),  # Muong Soui (W)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (111.022499788, 21.977094095),
            "NE": (111.421020276, 21.984176884),
            "SE": (111.431850232, 21.481351068),
            "SW": (111.034403441, 21.475759080),
        },
    },
    "fa43ed0f-d887-4564-a23e-9550cd87d25b": {
        "rims": (336.4291510795645, 4756.487467124529, 752.920315616815, 6662.68023053197),  # Phong Thô (W)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (111.749634858, 25.501873524),
            "NE": (112.156076830, 25.507100908),
            "SE": (112.165322229, 25.005423708),
            "SW": (111.760369737, 24.999129380),
        },
    },
    "7a5fc271-21ee-4053-9438-40a66873e691": {
        "rims": (301.0035724004223, 4710.477894991635, 735.390524588757, 6641.3015583906035),  # Phong-Saly (E)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (110.562675451, 24.478223255),
            "NE": (110.962262119, 24.485950702),
            "SE": (110.976625668, 23.985029281),
            "SW": (110.574304603, 23.977089309),
        },
    },
    "562fd87b-b04a-4d17-a06b-6f5f6b9e68d2": {
        "rims": (326.40310093663373, 4735.275947998809, 598.2961201465607, 6507.467799349829),  # Vang Vieng (E)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (111.431250819, 21.481665186),
            "NE": (111.827553653, 21.487649268),
            "SE": (111.835876986, 20.986128659),
            "SW": (111.440462723, 20.980357312),
        },
    },
    "97d155e5-ebb5-4402-8c4d-4fdb5fe8ccd6": {
        "rims": (326.09533330902246, 4744.798900767155, 566.4459073652305, 6484.319519276494),  # Ban Nam Bac (E)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (111.400482714, 22.987127321),
            "NE": (111.800363564, 22.993104357),
            "SE": (111.809667150, 22.491875113),
            "SW": (111.411048891, 22.485473187),
        },
    },
    "6eca3a2a-3c32-4a95-8fc6-21934716ac48": {
        "rims": (298.9562148559305, 4713.602844591042, 652.3550653910406, 6573.75560882742),  # M?ong Sai (E)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (110.587934759, 23.474708511),
            "NE": (110.989448743, 23.482304191),
            "SE": (111.000796300, 22.980915533),
            "SW": (110.600556385, 22.976693368),
        },
    },
    "3c0fb979-fbf6-4451-8352-abfd657a0059": {
        "rims": (317.50589368917196, 4728.568988969616, 656.3501886880146, 6572.926454053571),  # Muong Het (W)
        "reviewed_on": "2026-09-28",
        "grades": {
            "NW": (112.593303477, 23.505044150),
            "NE": (112.994125806, 23.508431512),
            "SE": (112.999326406, 23.005180164),
            "SW": (112.600136385, 23.003215622),
        },
    },
    "44176367-f159-472d-a9bd-6bd334a5737a": {
        "rims": (300.3, 4712.5, 579.5, 6491.0),  # Ban Nam Bac W
        "grades": {"NW": (111.001041117, 22.980897028),
                   "NE": (111.400156819, 22.987193129),
                   "SE": (111.410696783, 22.485585013),
                   "SW": (111.012481613, 22.479288912)},
    },
    "ab99db79-58e1-4535-928e-49fe6c7723e8": {
        "rims": (324.0, 4734.1, 715.2, 6624.8),  # Lai Châu W
        "grades": {"NW": (111.760797844, 25.000209428),
                   "NE": (112.163917286, 25.005830398),
                   "SE": (112.174521617, 24.503527331),
                   "SW": (111.770663862, 24.498545966)},
    },
    "0d026129-f521-48eb-8cd9-b86a1a256fa3": {
        "rims": (303.1, 4715.3, 631.3, 6543.8),  # Muong Hun Xieng Hung E
        "reviewed_on": "2026-09-28",
        "grades": {"NW": (111.367153059, 24.492389978), "NE": (111.771197896, 24.498326394),
                   "SE": (111.780994490, 23.996837952), "SW": (111.378791244, 23.991326526)},
    },
    "8a518936-b23a-4f7d-983e-a12288fd2ffa": {
        "rims": (390.7, 4812.9, 631.2, 6551.6),  # Muong Hùn Xiêng Hung W
        "reviewed_on": "2026-09-28",
        "grades": {"NW": (110.963773786, 24.486049058), "NE": (111.367624344, 24.492788376),
                   "SE": (111.379171789, 23.990845046), "SW": (110.976424648, 23.983892860)},
    },
    "bcf2da50-f093-41aa-b1bf-a3c9e53d8b4e": {
        "rims": (310.4, 4721.6, 778.1, 6694.6),  # Muong Khoua W
        "reviewed_on": "2026-09-28",
        "grades": {"NW": (110.988478464, 23.482627981), "NE": (111.390045477, 23.489115098),
                   "SE": (111.400039594, 22.987296786), "SW": (111.001015293, 22.981022394)},
    },
    "0576d9eb-38d0-4ca0-bae6-fa4a4bfb2fea": {
        "rims": (377.7, 4787.2, 664.3, 6583.3),  # Muong May W
        "reviewed_on": "2026-09-28",
        "grades": {"NW": (111.835547911, 20.986032593), "NE": (112.232084232, 20.991281452),
                   "SE": (112.238508469, 20.489031295), "SW": (111.844100249, 20.484420890)},
    },
    "5dfc24fb-b2c5-43fe-b74a-6d5abb564f62": {
        "rims": (302.1, 4715.9, 573.8, 6488.8),  # Muong Son W
        "reviewed_on": "2026-09-28",
        "grades": {"NW": (111.800468054, 22.993455392), "NE": (112.200264528, 22.998187756),
                   "SE": (112.208140257, 22.496702759), "SW": (111.809607248, 22.491757722)},
    },
    "70951e24-876e-4b5f-8a7b-1a440ec2fd37": {
        "rims": (306.7, 4721.1, 683.1, 6602.8),  # Sop Cop E
        "reviewed_on": "2026-09-28",
        "grades": {"NW": (112.191754773, 23.500467985), "NE": (112.592882316, 23.504335440),
                   "SE": (112.600031976, 23.003097075), "SW": (112.200176124, 22.998804842)},
    },
    "7ec6dcc4-ba07-4fb3-87ff-78ae548fcf17": {
        "rims": (409.6, 4820.5, 656.5, 6571.1),  # Sop Cop W
        "reviewed_on": "2026-09-28",
        "grades": {"NW": (111.791001134, 23.494785328), "NE": (112.192171861, 23.500048968),
                   "SE": (112.199958613, 22.998600166), "SW": (111.800423092, 22.993336526)},
    },
    "435e35c6-d44e-446e-8999-a165ed0cbfcb": {
        "rims": (327.7, 4734.9, 589.6, 6507.2),  # Xieng Khouang est E
        "reviewed_on": "2026-09-28",
        "grades": {"NW": (112.225004655, 21.492906878), "NE": (112.619211463, 21.497823871),
                   "SE": (112.626750384, 20.995913223), "SW": (112.232190661, 20.990996230)},
    },
}

def darkness(img):
    return 255.0 - np.asarray(img.convert("L"), dtype=float)


def fit(points):
    """Least squares with the outliers trimmed away -- the part that matters."""
    if len(points) < max(6, PATCHES // 3):
        return None
    a = np.array([p[0] for p in points], float)
    b = np.array([p[1] for p in points], float)
    keep = np.ones(len(a), bool)
    for _ in range(8):
        m, c = np.polyfit(a[keep], b[keep], 1)
        r = np.abs(b - (m * a + c))
        med = float(np.median(r[keep])) or 1.0
        new = r < max(1.5, TRIM * med)
        if new.sum() < 5 or (new == keep).all():
            keep = new
            break
        keep = new
    m, c = np.polyfit(a[keep], b[keep], 1)
    res = float(np.median(np.abs(b[keep] - (m * a[keep] + c))))
    return float(m), float(c), res, int(keep.sum()), len(a)


def rim_in(p, thick, which):
    """Where the rim pair sits in an averaged, de-tilted cross-profile.

    Reading inward from the thick outer line the profile goes: a thin companion
    line, blank paper, the graticule band, a wider run of blank paper, the rim
    pair, then map content that never falls back to paper level. The second blank
    run is the landmark, and it is the *innermost* one -- the band is what a walk
    in from the paper margin finds first, and it is 40 px out, which is 170 m on
    the ground.

    Of the pair it is the inner line that bounds the mapped quadrangle. That is
    not a reading of the print but a measurement: on Nhu Trac the inner line puts
    the two axes' ground scales within 0.03% of each other (4.2595 against 4.2582
    m/px) and the outer line within 0.23%. Eight times better, on a sheet whose
    corner coordinates are known independently.
    """
    # Paper level from inside the window, not from the whole strip. Some scans
    # carry the scanner's own white background past the edge of the sheet, and a
    # low percentile over the strip then returns 0 rather than the tone of the
    # paper -- which puts the threshold below the margin itself, finds no blank
    # run anywhere, and reports a sheet with no rim. (Cam Ly, 1907.)
    hi = min(len(p), thick + MAXIN)
    paper = float(np.percentile(p[thick:hi], 25))
    thr = paper + max(6.0, 0.06 * (float(p.max()) - paper))
    gap, run, start = None, 0, None
    for i in range(thick, hi):
        if p[i] < thr:
            start = i if run == 0 else start
            run += 1
        else:
            if run >= MINGAP:
                gap = start + run
            run = 0
    if gap is None:
        return None
    lo, hi2 = gap, min(len(p), gap + LIM)
    if hi2 - lo < 4:
        return None
    # Peaks are picked on the whole profile, not on the window, so that a line
    # sitting at the window's first sample still has blank paper on its outer side
    # to be measured against. Prominence, not height: map content just inside the
    # rim sits well above paper and drifts, but it does not rise and fall in ten
    # pixels.
    floor = max(8.0, 0.25 * (float(p[lo:hi2].max()) - paper))
    picked = []
    for j in range(max(1, lo), min(len(p) - 1, hi2)):
        if not (p[j] >= p[j - 1] and p[j] > p[j + 1]):
            continue
        u, v = max(0, j - 10), min(len(p), j + 11)
        if p[j] - max(p[u:j + 1].min(), p[j:v].min()) >= floor:
            picked.append(j)
    if not picked:
        return None
    j = picked[-1] if which == "inner" else picked[0]
    u = v = j
    while u > 0 and p[u - 1] > thr and p[u - 1] <= p[u]:
        u -= 1
    while v < len(p) - 1 and p[v + 1] > thr and p[v + 1] <= p[v]:
        v += 1
    w = p[u:v + 1] - thr
    if w.sum() <= 0:
        return None
    return u + float((np.arange(len(w)) * w).sum() / w.sum())


def quad(c):
    P = c["corners"]
    top, bot = math.dist(P["NW"], P["NE"]), math.dist(P["SW"], P["SE"])
    lft, rgt = math.dist(P["NW"], P["SW"]), math.dist(P["NE"], P["SE"])
    d1, d2 = math.dist(P["NW"], P["SE"]), math.dist(P["NE"], P["SW"])
    return {"w": (top + bot) / 2, "h": (lft + rgt) / 2,
            "opp_x": abs(top - bot) / max(top, bot),
            "opp_y": abs(lft - rgt) / max(lft, rgt),
            "diag": abs(d1 - d2) / max(d1, d2),
            "aspect": ((top + bot) / 2) / ((lft + rgt) / 2)}


WGS84_A = 6378137.0
WGS84_E2 = 1 - (6356752.314245 / WGS84_A) ** 2


def metres_per_degree(lat):
    """Parallel and meridian scale on the WGS 84 ellipsoid."""
    p = math.radians(lat)
    q = 1 - WGS84_E2 * math.sin(p) ** 2
    return (math.pi / 180 * WGS84_A * math.cos(p) / math.sqrt(q),
            math.pi / 180 * WGS84_A * (1 - WGS84_E2) / q ** 1.5)


def north_metres(lat0, lat1):
    """Meridian arc via Simpson integration; checked against Geod to <1 mm."""
    mid = (lat0 + lat1) / 2
    return abs(lat1 - lat0) * (metres_per_degree(lat0)[1] +
                              4 * metres_per_degree(mid)[1] +
                              metres_per_degree(lat1)[1]) / 6


def ground(lon0, lat0, lon1, lat1):
    north = abs(lon1 - lon0) * metres_per_degree(lat0)[0]
    south = abs(lon1 - lon0) * metres_per_degree(lat1)[0]
    return (north + south) / 2, north_metres(lat0, lat1)


def annotation(iiif, w, h, got):
    """One georeference annotation, in the shape the Allmaps renderer reads.

    Same shape `scripts/l7014_annotate.py` writes, and for the same two reasons.
    The transformation is a first-order polynomial, not a projective: four corners
    fit a projective *exactly*, so a pixel of detection error would be reproduced
    faithfully as perspective instead of averaged away, and these sheets were
    measured as having no perspective to recover -- the rigid-rotation fit makes
    opposite edges agree by construction. And the mask is the rim quad, which is
    what stops the paper margin, the title block and the legend being painted over
    the neighbouring sheets.
    """
    px = {c: [round(got["corners"][c][0]), round(got["corners"][c][1])] for c in CORNERS}
    poly = " ".join(f"{px[c][0]},{px[c][1]}" for c in CORNERS)
    return {
        "type": "AnnotationPage",
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "items": [{
            "id": f"{iiif}/annotation",
            "type": "Annotation",
            "@context": [
                "http://iiif.io/api/extension/georef/1/context.json",
                "http://iiif.io/api/presentation/3/context.json",
            ],
            "motivation": "georeferencing",
            "target": {
                "type": "SpecificResource",
                "source": {"id": iiif, "type": "ImageService3", "width": w, "height": h},
                "selector": {"type": "SvgSelector",
                             "value": f'<svg width="{w}" height="{h}">'
                                      f'<polygon points="{poly}" /></svg>'},
            },
            "body": {
                "type": "FeatureCollection",
                "transformation": {"type": "polynomial", "options": {"order": 1}},
                "features": [
                    {"type": "Feature",
                     "properties": {"resourceCoords": px[c]},
                     "geometry": {"type": "Point",
                                  "coordinates": [round(got["wgs84"][c][0], 7),
                                                  round(got["wgs84"][c][1], 7)]}}
                    for c in CORNERS
                ],
            },
        }],
    }



def cached_crop(base, x, y, w, h, size):
    """Keep expensive IIIF strips reusable across calibration attempts."""
    cache = WORK / ".fetch_cache"
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{base}|{x}|{y}|{w}|{h}|{size}".encode()).hexdigest()
    path = cache / f"{key}.pkl"
    if path.exists():
        with path.open("rb") as f:
            image, stats = pickle.load(f)
        if stats.get("coverage") == 1:
            return image
    stats = {}
    image = T.fetch_crop_level0(base, x, y, w, h, size, stats=stats, max_workers=4)
    if stats.get("coverage") != 1:
        raise RuntimeError(f"crop has incomplete tile coverage: {base} {stats}")
    with path.open("wb") as f:
        pickle.dump((image, stats), f)
    return image


def frame(base, W, H):
    # Only the central cross contributes to these profiles. Fetching a whole
    # overview assembled ~150 IIIF tiles per sheet, then discarded most of it.
    # Both bands use the same pyramid level and rendered scale as that overview.
    overview_h = round(OV * H / W)
    x0 = round(int(OV * .46) * W / OV)
    x1 = round(int(OV * .54) * W / OV)
    y0 = round(int(overview_h * .46) * H / overview_h)
    y1 = round(int(overview_h * .54) * H / overview_h)
    with ThreadPoolExecutor(max_workers=2) as pool:
        horizontal = pool.submit(cached_crop, base, 0, y0, W, y1 - y0, OV)
        vertical = pool.submit(cached_crop, base, x0, 0, x1 - x0, H,
                               round(OV * (x1 - x0) / W))
        cols = darkness(horizontal.result()).mean(axis=0)
        vertical_img = vertical.result()
    # The narrow crop's rounded width can resize to a slightly different
    # height than the old whole-image overview. Align it before finding peaks.
    vertical_img = vertical_img.resize((vertical_img.width, overview_h), Image.Resampling.LANCZOS)
    rows = darkness(vertical_img).mean(axis=1)

    def ambiguous(profile, side):
        third = len(profile) // 3
        seg = profile[:third] if side == "T" else profile[-third:]
        strongest = int(np.argmax(seg))
        others = seg.copy()
        others[max(0, strongest - 12):min(len(seg), strongest + 13)] = -1
        return (seg[strongest] - others.max()) / max(seg[strongest], 1) < .07

    # On some scans two dark horizontal rules are nearly tied. A narrow crop
    # can reverse their order by a few grey levels; use the original overview
    # for those sheets rather than risking a different frame line.
    if ambiguous(rows, "T") or ambiguous(rows, "B"):
        full = darkness(cached_crop(base, 0, 0, W, H, OV))
        fh, fw = full.shape
        cols = full[int(fh * .46):int(fh * .54)].mean(axis=0)
        rows = full[:, int(fw * .46):int(fw * .54)].mean(axis=1)
    def alt_peak(seg, from_edge):
        """The next-outermost rule nearly as dark as the strongest one, if any.

        Used only as a fallback when the strongest peak turns out not to be the
        neatline: a bolder inner rim line can outscore a thinner outer frame
        line (Russey Chrum (E), Kompong Chhnang (W)), leaving nothing further
        inward for rim_in to find. Never used as the primary pick -- a comparably
        dark feature nearer the paper edge is at least as often a scanner
        background/mount artefact (Attopeu (E), Vinh (W) and 70 others regressed
        when this ran unconditionally), and those already succeed under argmax.
        """
        order = seg if from_edge else seg[::-1]
        strongest = int(np.argmax(order))
        baseline = float(np.percentile(order, 25))
        near = baseline + 0.85 * max(1.0, float(order[strongest]) - baseline)
        for i in range(1, strongest - 5):
            if order[i] >= near and order[i] >= order[i - 1] and order[i] >= order[i + 1]:
                return i if from_edge else len(seg) - 1 - i
        return None

    out = {}
    for side, prof, n, scale in (("L", cols, len(cols), W / len(cols)),
                                 ("R", cols, len(cols), W / len(cols)),
                                 ("T", rows, len(rows), H / len(rows)),
                                 ("B", rows, len(rows), H / len(rows))):
        third = n // 3
        seg = prof[:third] if side in "LT" else prof[-third:]
        strongest = int(np.argmax(seg))
        alt = alt_peak(seg, side in "LT")
        out[side] = (strongest + (0 if side in "LT" else n - third)) * scale
        if alt is not None:
            out[side + "_alt"] = (alt + (0 if side in "LT" else n - third)) * scale
    return out


def frame_strip(base, side, rough, W, H, full_along=False):
    c = rough[side]
    if side in "LR":
        a0, a1 = (0, H) if full_along else (int(H * SPAN[0]), int(H * SPAN[1]))
        x0 = max(0, int(c - (ACROSS[0] if side == "L" else ACROSS[1])))
        x1 = min(W, int(c + (ACROSS[1] if side == "L" else ACROSS[0])))
        d = darkness(cached_crop(base, x0, a0, x1 - x0, a1 - a0, x1 - x0))
        origin, step = (x0, 1) if side == "L" else (x1 - 1, -1)
    else:
        a0, a1 = (0, W) if full_along else (int(W * SPAN[0]), int(W * SPAN[1]))
        y0 = max(0, int(c - (ACROSS[0] if side == "T" else ACROSS[1])))
        y1 = min(H, int(c + (ACROSS[1] if side == "T" else ACROSS[0])))
        d = darkness(cached_crop(base, a0, y0, a1 - a0, y1 - y0, a1 - a0)).T
        origin, step = (y0, 1) if side == "T" else (y1 - 1, -1)
    return (d if step > 0 else d[:, ::-1]), origin, step, a0


def rim_relaxed(p, thick):
    hi = min(len(p), thick + MAXIN)
    paper = float(np.percentile(p[thick:hi], 25))
    thr = paper + max(6.0, 0.06 * (float(p.max()) - paper))
    gap, run, start = None, 0, None
    for i in range(thick, hi):
        if p[i] < thr:
            start = i if run == 0 else start
            run += 1
        else:
            if run >= MINGAP:
                gap = start + run
            run = 0
    if gap is None:
        return None
    lo, hi2 = gap, min(len(p), gap + LIM)
    if hi2 - lo < 4:
        return None
    floor = max(5.0, 0.12 * (float(p[lo:hi2].max()) - paper))
    picked = []
    for j in range(max(1, lo), min(len(p) - 1, hi2)):
        if p[j] >= p[j - 1] and p[j] > p[j + 1]:
            u, v = max(0, j - 10), min(len(p), j + 11)
            if p[j] - max(p[u:j + 1].min(), p[j:v].min()) >= floor:
                picked.append(j)
    if not picked:
        return None
    j = picked[-1]
    u = v = j
    while u > 0 and p[u - 1] > thr and p[u - 1] <= p[u]:
        u -= 1
    while v < len(p) - 1 and p[v + 1] > thr and p[v + 1] <= p[v]:
        v += 1
    weights = p[u:v + 1] - thr
    return u + float((np.arange(len(weights)) * weights).sum() / weights.sum()) if weights.sum() > 0 else None


def guided_rim(p, thick, expected):
    """Retry a failed rim search at the offset measured by the other sides.

    Some maps have a second long paper-coloured run *inside* the true rim.
    rim_in() deliberately takes the last run, so those maps miss a plainly
    visible border. Search every run here, but only at an independently
    measured offset; a borderless crop must still fail.
    """
    hi = min(len(p), thick + MAXIN)
    paper = float(np.percentile(p[thick:hi], 25))
    thr = paper + max(6.0, 0.06 * (float(p.max()) - paper))
    gaps, run = [], 0
    for i in range(thick, hi):
        if p[i] < thr:
            run += 1
        else:
            if run >= MINGAP:
                gaps.append(i)
            run = 0
    candidates = []
    for gap in gaps:
        lo, end = gap, min(len(p), gap + LIM)
        if end - lo < 4:
            continue
        # This retry already has a 12px location prior from three independent
        # sides. A faint printed rim (Thât Khê E) can have 4–8 grey levels of
        # local prominence; the unguided floor of 8 rejects it outright.
        floor = max(4.0, 0.12 * (float(p[lo:end].max()) - paper))
        for j in range(max(1, lo), min(len(p) - 1, end)):
            if abs(j - thick - expected) > 12:
                continue
            if not (p[j] >= p[j - 1] and p[j] > p[j + 1]):
                continue
            u, v = max(0, j - 10), min(len(p), j + 11)
            if p[j] - max(p[u:j + 1].min(), p[j:v].min()) >= floor:
                candidates.append(j)
    if not candidates:
        return None
    j = min(candidates, key=lambda x: abs(x - thick - expected))
    u = v = j
    while u > 0 and p[u - 1] > thr and p[u - 1] <= p[u]:
        u -= 1
    while v < len(p) - 1 and p[v + 1] > thr and p[v + 1] <= p[v]:
        v += 1
    weights = p[u:v + 1] - thr
    if weights.sum() <= 0:
        return None
    rim = u + float((np.arange(len(weights)) * weights).sum() / weights.sum())
    return rim if abs(rim - thick - expected) <= 12 else None


def ranked_rim(p, aligned, thick, expected):
    """Pick an observed rim when two other sides provide an offset prior.

    Search every paper gap rather than only the last one. A peak must persist
    through most of the individually aligned patches; this distinguishes a
    printed rule from a local map feature that happened to survive averaging.
    The series spacing prior ranks supported peaks, never creates one.
    """
    hi = min(len(p), thick + MAXIN)
    paper = float(np.percentile(p[thick:hi], 25))
    thr = paper + max(6.0, 0.06 * (float(p.max()) - paper))
    gaps, run = [], 0
    for i in range(thick, hi):
        if p[i] < thr:
            run += 1
        else:
            if run >= MINGAP:
                gaps.append(i)
            run = 0
    candidates = []
    for gap in gaps:
        lo, end = gap, min(len(p), gap + LIM)
        if end - lo < 4:
            continue
        floor = max(4.0, 0.12 * (float(p[lo:end].max()) - paper))
        for j in range(max(1, lo), min(len(p) - 1, end)):
            if abs(j - thick - expected) > 12:
                continue
            if not (p[j] >= p[j - 1] and p[j] > p[j + 1]):
                continue
            u, v = max(0, j - 10), min(len(p), j + 11)
            prominence = p[j] - max(p[u:j + 1].min(), p[j:v].min())
            if prominence < floor:
                continue
            support = 0
            for patch in aligned:
                left = patch[max(0, j - 13):max(0, j - 6)]
                right = patch[min(len(patch), j + 7):min(len(patch), j + 14)]
                if not len(left) or not len(right):
                    continue
                peak = patch[max(0, j - 4):min(len(patch), j + 5)].max()
                if peak - max(left.min(), right.min()) >= 8:
                    support += 1
            if support < math.ceil(.75 * len(aligned)):
                continue
            a = b = j
            while a > 0 and p[a - 1] > thr and p[a - 1] <= p[a]:
                a -= 1
            while b < len(p) - 1 and p[b + 1] > thr and p[b + 1] <= p[b]:
                b += 1
            weights = p[a:b + 1] - thr
            if weights.sum() <= 0:
                continue
            rim = a + float((np.arange(len(weights)) * weights).sum() / weights.sum())
            if abs(rim - thick - expected) <= 12:
                candidates.append((support, float(prominence), -abs(rim - thick - expected), rim))
    return max(candidates)[-1] if candidates else None


def side_line(d, ref, expected_offset=None, rank_candidates=False, prefer_ranked=False,
              direct_frame=False):
    edges = np.linspace(0, d.shape[0], PATCHES + 1).round().astype(int)
    patches = [((lo + hi) / 2, d[lo:hi].mean(axis=0)) for lo, hi in zip(edges, edges[1:]) if hi - lo >= 8]
    if len(patches) < 6:
        return None, "too few patches"
    lo, hi = max(0, int(ref) - NEAR), min(d.shape[1], int(ref) + NEAR)
    if hi <= lo:
        return None, "rough frame outside strip"
    consensus = lo + int(np.argmax(np.mean([p for _, p in patches], axis=0)[lo:hi]))
    def pick(prof, centre, width):
        a, b = max(0, int(centre - width)), min(len(prof), int(centre + width) + 1)
        return a + int(np.argmax(prof[a:b]))
    fitted = fit([(mid, float(pick(p, consensus, 12))) for mid, p in patches])
    if fitted is None:
        return None, "thick line would not fit"
    m, c, *_ = fitted
    fitted = fit([(mid, float(pick(p, m * mid + c, 8))) for mid, p in patches])
    if fitted is None:
        return None, "thick line would not refine"
    m, c, residual, kept, found = fitted
    if residual > RESIDUAL:
        return None, f"thick line residual {residual:.1f}px"
    anchor = float(np.mean([mid for mid, _ in patches]))
    ref2 = m * anchor + c
    grid = np.arange(d.shape[1], dtype=float)
    aligned = [np.interp(grid, grid + (ref2 - (m * mid + c)), p) for mid, p in patches]
    avg = np.mean(aligned, axis=0)
    rim = rim_in(avg, int(round(ref2)), "inner")
    relaxed = rim is None
    if relaxed:
        rim = rim_relaxed(avg, int(round(ref2)))
    guided = False
    if expected_offset is not None and (rim is None or prefer_ranked):
        candidate = (ranked_rim(avg, aligned, int(round(ref2)), expected_offset)
                     if rank_candidates else guided_rim(avg, int(round(ref2)), expected_offset))
        if candidate is not None:
            rim, guided = candidate, True
    direct = False
    if rim is None and direct_frame:
        # Some split-sheet seam edges have only one printed boundary: the map
        # begins immediately after the fitted frame. Require blank paper on
        # the outside and substantially more ink inside; a missing rim alone
        # is not evidence for this convention.
        centre = int(round(ref2))
        outside = d[:, max(0, centre - 145):max(0, centre - 20)]
        inside = d[:, centre + 20:min(d.shape[1], centre + 145)]
        if outside.shape[1] >= 100 and inside.shape[1] >= 100:
            ink = float(np.percentile(outside, 40)) + 50
            out_ink = float(np.mean(outside > ink))
            in_ink = float(np.mean(inside > ink))
            if out_ink < .02 and in_ink > .05 and in_ink > 5 * out_ink:
                rim, direct = ref2, True
    if rim is None:
        return None, "no rim found inside the thick line"
    result = {"m": m, "c": c + rim - ref2, "res": residual, "kept": kept,
              "found": found, "offset": rim - ref2, "relaxed": relaxed and not guided and not direct,
              "guided": guided}
    if guided and rank_candidates:
        result["ranked"] = True
    if direct:
        result["direct"] = True
    return result, None


# Frame-to-rim distance as a fraction of image height, pooled over every side
# NOT reached via the alt retry below (636 sides, 170 sheets that independently
# cleared every gate). min 0.0213, max 0.0262, median 0.0230, std 0.0006 -- a
# real printed-margin constant across the series, not a per-sheet fit. A side
# that lands outside this band picked the wrong line, not a differently-scaled
# rim (see its use in detect()).
RETRY_BAND = (0.019, 0.028)


# Source overviews and detailed strips reviewed on 2026-09-28. These are
# approximate seeds for observed outer rules, not substituted map boundaries.
# Normal patch fitting still measures every rim; SOURCE_REVIEWED_RIMS pins
# the result so stale manual guidance fails closed after a detector change.
SOURCE_REVIEWED_FRAMES = {
    "d7561735-d521-4aa7-ba74-de5b3e992789": (5032, 7098, {'L': 148, 'B': 6773}),  # Bac-Kan (E)
    "8f06c5b2-807b-4501-9f5c-c2bedcde85c1": (5010, 7118, {'B': 6762}),  # Bai-Thuong (W)
    "aa3c4bcb-9070-40dc-8ce0-9bd098429f28": (5040, 7026, {'B': 6676}),  # Beng Lovéa (E)
    "557c1b72-ecbf-4113-8c29-4efb16cea25e": (5068, 7402, {'R': 4877}),  # Bô Kham (E)
    "c4a6bf0a-278d-4125-9e2e-6e7a155b7e9e": (5032, 7058, {'R': 4944, 'B': 6669}),  # Cam Pha ouest (W)
    "50689317-5dbf-46db-ba84-0fa4c0a67213": (5112, 7142, {'B': 6755}),  # Dong-Hoi (W)
    "e19c409d-e2bb-469e-8c6c-ed7c8d3fcf3f": (5114, 7092, {'B': 6683}),  # Dô-Son (W)
    "d1db5882-a158-43d8-8ae8-420b57f13919": (5046, 7390, {'B': 6669}),  # Blao (W)
    "826a2182-bc32-4fa7-babe-59c784ec1440": (4902, 7006, {'B': 6726}),  # Muong-Phine (E)
    "90b6dcd2-269e-4829-9d22-32e92c5d68ee": (5044, 7120, {'B': 6700}),  # Pak-Seng (W)
    "dd3e54c5-a7af-46fe-8e51-9bd79be31b98": (2968, 4179, {'T': 270}),  # Phsar Oudong (E)
    "dd513b9b-d4de-439e-9a49-694827a647f6": (5204, 7318, {'L': 214, 'B': 6948}),  # Bao-Lac (W)
    "287d7a08-d14e-4186-a0e3-e31c1456a4e2": (5068, 7116, {'B': 6761}),  # Bac-Kan (W)
    "84fd3f51-4dda-4e87-8b5f-925b47c7c4a3": (5008, 7034, {'B': 6653}),  # Kompong Chhnang (E)
    "da274467-2985-43b4-a0ae-dc6f2b64ef4a": (4994, 7162, {'L': 128, 'R': 4819, 'T': 358, 'B': 6524}),  # Qui Nhon (W)
    "e13bcdfc-b852-4349-8119-f988ff6e44ec": (5228, 7878, {'R': 5019, 'B': 6867}),  # Phnom Deck (E)
    # Second batch, reviewed 2026-09-29 by per-pixel profile at each anchor
    # (see the SOURCE_REVIEWED_RIMS comment above and the 2026-09-29 journal
    # entry -- contact-scale review alone missed a 52px interior-line pick).
    "5e1ca3a9-4e94-4ec4-976a-86c13ad12b27": (5060, 7220, {'L': 132, 'B': 6582}),  # Kratié (E)
    "b12f0296-9d70-4ec2-83fd-90fb57fba38a": (5026, 7052, {'B': 6668}),  # Krau Chmar (E)
    "488d9453-88ba-4c6d-ade4-b221e95d735e": (5050, 7196, {'T': 487}),  # Luc-An-Chau (E)
    "ab592683-7ea2-43e7-bf78-bbcbc8dc1045": (5024, 7102, {'B': 6704}),  # Luc-An-Chau (W)
    "65559440-3d12-4cfe-9d52-9e872564f3bd": (4994, 7098, {'B': 6726}),  # Muong Ou Tay (W)
    "09a93bb7-56f4-4e0a-99df-8bcc69a9a64a": (5192, 7314, {'B': 6836}),  # Muong Phalane (E)
    "e6ee3683-83a9-4497-b95e-7b38a0dc5c12": (5250, 7498, {'B': 6800}),  # Muong Phine (W)
    "e19e7743-f209-4947-a2d1-d40c3a11948d": (5168, 7188, {'B': 6814}),  # Muong Song Khone (W)
    "96bb8a0d-67c0-4762-9eb6-85c9be8df23c": (5220, 7140, {'B': 6786}),  # Muong-Song-Khone (E)
    "83501380-a456-4687-a6b7-76f798925a7e": (5154, 7664, {'B': 6737}),  # Muong-Vène (W)
    "45e9e857-f40a-494e-904a-3b2ef0bc0d7d": (5174, 7202, {'B': 6825}),  # Pa-Kha (E)
    "fbe9e63d-1b00-44b4-b88f-50f67a3c5871": (5074, 7228, {'R': 4931, 'B': 6779}),  # Pa-Kha (W)
}


# Faint or interrupted rims checked against detailed source strips on
# 2026-09-28. Each seed is near an observed boundary; all 24 patches are still
# fitted, and the resulting four anchors must match SOURCE_REVIEWED_RIMS.
SOURCE_REVIEWED_BOUNDARIES = {
    "d7561735-d521-4aa7-ba74-de5b3e992789": (5032, 7098, {'L': 314, 'B': 6597, 'T': 685}, ()),  # Bac-Kan (E)
    "8f06c5b2-807b-4501-9f5c-c2bedcde85c1": (5010, 7118, {'B': 6584}, ()),  # Bai-Thuong (W)
    "aa3c4bcb-9070-40dc-8ce0-9bd098429f28": (5040, 7026, {'B': 6507}, ()),  # Beng Lovéa (E)
    "557c1b72-ecbf-4113-8c29-4efb16cea25e": (5068, 7402, {'R': 4699}, ()),  # Bô Kham (E)
    "c4a6bf0a-278d-4125-9e2e-6e7a155b7e9e": (5032, 7058, {'R': 4771, 'B': 6495}, ()),  # Cam Pha ouest (W)
    "50689317-5dbf-46db-ba84-0fa4c0a67213": (5112, 7142, {'B': 6552}, ()),  # Dong-Hoi (W)
    "e19c409d-e2bb-469e-8c6c-ed7c8d3fcf3f": (5114, 7092, {'B': 6509}, ()),  # Dô-Son (W)
    "59b7ab12-6586-4aec-9e3a-55b5fb6624de": (5040, 7130, {'T': 631}, ()),  # Hai Phong (E)
    "8714ef04-fd0b-44be-a324-1fefd2db9976": (5184, 7418, {'R': 4758}, ()),  # Trang Bang (W)
    "9038fcc1-e05b-4217-92a5-1942e2b0da80": (4948, 7336, {'L': 170, 'T': 600}, ('L',)),  # Lovéa (E)
    "dd3e54c5-a7af-46fe-8e51-9bd79be31b98": (2968, 4179, {'T': 370, 'B': 3868, 'R': 2790}, ()),  # Phsar Oudong (E)
    "dd513b9b-d4de-439e-9a49-694827a647f6": (5204, 7318, {'L': 355}, ()),  # Bao-Lac (W)
    # Second batch, reviewed 2026-09-29 by per-pixel profile at each anchor.
    # Lang Son (E) was pulled from this table (and from FRAMES/RIMS) after
    # the profile found its B and R sides off by 10px and ambiguous between
    # two rules respectively; it reverted to its version-28 held verdict.
    "5e1ca3a9-4e94-4ec4-976a-86c13ad12b27": (5060, 7220, {'L': 305, 'B': 6403}, ()),  # Kratié (E)
    "b12f0296-9d70-4ec2-83fd-90fb57fba38a": (5026, 7052, {'B': 6492}, ()),  # Krau Chmar (E)
    "488d9453-88ba-4c6d-ade4-b221e95d735e": (5050, 7196, {'T': 661}, ()),  # Luc-An-Chau (E)
    "ab592683-7ea2-43e7-bf78-bbcbc8dc1045": (5024, 7102, {'B': 6526}, ()),  # Luc-An-Chau (W)
    "65559440-3d12-4cfe-9d52-9e872564f3bd": (4994, 7098, {'B': 6552}, ()),  # Muong Ou Tay (W)
    "09a93bb7-56f4-4e0a-99df-8bcc69a9a64a": (5192, 7314, {'B': 6663}, ()),  # Muong Phalane (E)
    "e6ee3683-83a9-4497-b95e-7b38a0dc5c12": (5250, 7498, {'B': 6626}, ()),  # Muong Phine (W)
    "e19e7743-f209-4947-a2d1-d40c3a11948d": (5168, 7188, {'B': 6638}, ()),  # Muong Song Khone (W)
    "96bb8a0d-67c0-4762-9eb6-85c9be8df23c": (5220, 7140, {'B': 6612}, ()),  # Muong-Song-Khone (E)
    "83501380-a456-4687-a6b7-76f798925a7e": (5154, 7664, {'B': 6563}, ()),  # Muong-Vène (W)
    "45e9e857-f40a-494e-904a-3b2ef0bc0d7d": (5174, 7202, {'B': 6648}, ()),  # Pa-Kha (E)
    "fbe9e63d-1b00-44b4-b88f-50f67a3c5871": (5074, 7228, {'R': 4757, 'B': 6605}, ()),  # Pa-Kha (W)
    # 2026-09-29/30: double-frame mixed-holds, source-reviewed against marked
    # crops after the family-offset heuristic first picked wrong (Than-Poun's
    # bottom margin is unusually deep: title/scale-bar/adjoining-sheet-index
    # block sits *between* the automatic pick and the true neatline).
    "a8039626-c205-4a4d-a136-87acb33c2fc8": (5060, 7154, {'L': 316, 'B': 6606}, ('B',)),  # Than-Poun (E)
    "8289d9a6-6780-4f1e-8ead-7f9f137d6ada": (5078, 7050, {'R': 4924}, ('R',)),  # Ha-Lang (W)
    "f9fc556b-8311-4e0a-8f72-fd5801b13ef1": (5130, 7206, {'L': 191}, ('L',)),  # Quan-Ba (E)
    # 2026-09-30: Sam-Neua (E)'s automatic B and R pins are both genuinely
    # wrong -- deep in a flat, feature-free/textured run with no printed line
    # nearby, not a double-frame pick. True edges read by the "last dark
    # feature before the blank-paper plateau" signature: B at y=6723.9
    # (residual 0.31px, 20/24 patches), R at x=4709 (mean of 4708-4711,
    # residual 0.55px, 22/24 patches). Both direct: the rough overview guess
    # for R sits in the same textured zone and does not fit a straight line
    # at all, which is exactly the case the outer-rule skip above exists for.
    "85967c9c-9bb7-4acb-9688-2eaf3d93216b": (5356, 7064, {'R': 4709, 'B': 6724}, ('R', 'B')),  # Sam-Neua (E)
    # 2026-09-30: Lang Son (E) reverted to held on 2026-09-29 pending a
    # side-by-side visual check ("two comparable rules... low-value gap
    # between them" on R; B similarly ambiguous). Both direct, not merely a
    # double-frame pick: native darkness scans on both sides show the
    # automatic pick landing in a genuinely quiet gap between two real
    # printed lines (R: 4796-4818 and 4872-4949, gap at the picked 4809;
    # B: 6800-6810 and 6827-6830, gap at the picked 6823) -- what `frame()`'s
    # coarse guess found (R 4966, B 7038) and treated as "outer decorative
    # frame, search inward" is itself the true neatline on this sheet, not a
    # decorative outer rule with a separate rim further in. Refit directly on
    # each: R residual 3.28px (24/24), B residual 3.32px (24/24) -- as clean
    # as any auto-detected side in the corpus. `rim offsets spread` drops
    # from 38% to 11.6% (12% gate), `shape off`/`axes disagree` from 4.6%/
    # 4.4% to 0.7%/0.7% -- clears outright, no catalogue correction or
    # axes-disagree exception needed.
    "5300b1fc-7b90-4c8d-a800-5f369bea96ca": (5152, 7210, {'R': 4970, 'B': 6805}, ('R', 'B')),  # Lang Son (E)
    # 2026-09-30: Tu Lê (E) -- same class of failure as Than-Poun (E): the
    # automatic B pick (offset 250.5px, far larger than the other three sides'
    # 170-195px) landed on an interior label-box rule deep inside the bottom
    # margin, between the sheet's two printed kilometric-index stripes and its
    # "113°20'" corner-grade label -- confirmed by a wide crop showing the true
    # neatline as the single thin line right at the top of that block, well
    # short of the label furniture. Direct refit at that line: residual
    # 0.35px, 24/24 patches -- far cleaner than the wrong pick's 3.4px.
    "dcfb2452-b976-4092-bddb-8c9e04300db3": (5178, 7550, {'B': 6950}, ('B',)),  # Tu Lê (E)
}

# Sheets whose neatline is source-confirmed correct (via SOURCE_REVIEWED_RIMS,
# SOURCE_REVIEWED_BOUNDARIES or SOURCE_REVIEWED_SPECIAL_SPANS matching, or a
# direct crop check) where the only remaining verdict problem is the printed
# sheet's own axis-scale distortion -- real, not a detection error, and
# absorbed by the georeference transform (Allmaps polynomial on 4 corner
# GCPs), never a wrong rim. Confirmed 2026-09-30, applied to sheets under a
# GATE["axes_disagree_reviewed"] cap; does NOT relax the gate for anyone not
# listed here. Ban Khana (W) is deliberately excluded: its axes-disagree is a
# known 0.4g catalogue longitude offset, not confirmed source distortion.
SOURCE_REVIEWED_AXES_DISAGREE = {
    "edd8be90-fa2d-422f-aa46-cbc1f6c657ac",  # Phan Thiet (E) -- special-span reviewed
    "04f35f4f-b19a-4992-bfc7-d1da75a9ddba",  # Phan Thiet (W) -- special-span reviewed
    "283ae0d8-dca7-4a2d-a86e-1e56dc08527e",  # Thanh Hoa (E) -- special-span reviewed
    "99adde4f-9d56-4a66-b186-6c8e81b63d39",  # Vinh (E) -- special-span reviewed
    "edb34855-cc39-4b9b-83cd-113f5aafb505",  # Vientiane Ban Keun (E) -- special-span reviewed
    "a8039626-c205-4a4d-a136-87acb33c2fc8",  # Than-Poun (E) -- boundary-reviewed
    "8289d9a6-6780-4f1e-8ead-7f9f137d6ada",  # Ha-Lang (W) -- boundary-reviewed
    "f9fc556b-8311-4e0a-8f72-fd5801b13ef1",  # Quan-Ba (E) -- boundary-reviewed
    "1ce2d961-4147-44eb-964c-9a7f64ea48d4",  # Muong-Tè (E) -- rim-reviewed
    "6bdd9ab8-22dd-460d-b511-0a29d5dd843f",  # Bun-Tai (E) -- confirmed correct rim, real residual scan distortion
    "559ba082-a861-45a8-bbff-e0285f727bd9",  # Mon-Cay (E) -- confirmed correct rim, real residual scan distortion
    "65559440-3d12-4cfe-9d52-9e872564f3bd",  # Muong Ou Tay (W) -- confirmed correct rim, real residual scan distortion
    "3d0a6cca-5ca3-4ceb-9334-5374d4d2afb4",  # Phan Rang (W) -- rim independently confirmed by printed corner-grade ticks (SOURCE_REVIEWED_CORRECTED_BOX), not just the family-offset heuristic
    "c19c68a6-5ce8-4b74-86ec-9272f0c98a21",  # Phan Rang (E) -- rim independently confirmed by printed corner-grade ticks (SOURCE_REVIEWED_CORRECTED_BOX) plus per-pixel profile on the wide B side (SOURCE_REVIEWED_RIMS)
    "65366fa5-092a-4225-a576-69e83bf4c647",  # Phu Diên Châu (E) -- rim independently confirmed by printed longitude ticks (SOURCE_REVIEWED_CORRECTED_BOX) plus per-pixel profile on the wide B side (SOURCE_REVIEWED_RIMS)
    "a387ff3f-05c4-4d46-8470-079323555c40",  # Lai Châu (E) -- rim-reviewed, all 4 sides confirmed isolated printed lines via per-pixel darkness profile, no competing feature nearby
}
AXES_DISAGREE_REVIEWED_CAP = .05


def reviewed_boundary_fit(d, ref):
    """Fit an observed rule near a manually reviewed source position."""
    edges = np.linspace(0, d.shape[0], PATCHES + 1).round().astype(int)
    patches = [((lo + hi) / 2, d[lo:hi].mean(axis=0))
               for lo, hi in zip(edges, edges[1:]) if hi - lo >= 8]
    if len(patches) < 18 or not 13 <= ref < d.shape[1] - 13:
        return None
    def peak(profile, centre, width):
        lo = max(1, round(centre) - width)
        hi = min(len(profile) - 1, round(centre) + width + 1)
        return lo + int(np.argmax(profile[lo:hi]))
    profile = np.mean([p for _, p in patches], axis=0)
    centre = peak(profile, ref, 12)
    fitted = fit([(mid, float(peak(p, centre, 12))) for mid, p in patches])
    if fitted is None:
        return None
    m, c, *_ = fitted
    fitted = fit([(mid, float(peak(p, m * mid + c, 6))) for mid, p in patches])
    if fitted is None:
        return None
    m, c, residual, kept, found = fitted
    if residual > RESIDUAL or kept < 18:
        return None
    return {"m": m, "c": c, "res": residual, "kept": kept, "found": found,
            "offset": 0, "relaxed": False, "guided": False, "reviewed_boundary": True}


def detect(base, W, H, verbose=False):
    rough = frame(base, W, H)
    reviewed_frame = SOURCE_REVIEWED_FRAMES.get(base.rstrip("/").rsplit("/", 1)[-1])
    if reviewed_frame:
        rw, rh, seeds = reviewed_frame
        if (W, H) != (rw, rh):
            return None, "source-reviewed frame dimensions changed"
        rough.update(seeds)
    lines = {}
    failed = {}
    # Edge strips are independent IIIF tile sets; fetch them concurrently.
    with ThreadPoolExecutor(max_workers=4) as pool:
        strips = dict(zip("LRTB", pool.map(lambda side: frame_strip(base, side, rough, W, H), "LRTB")))
    for side in "LRTB":
        d, origin, step, a0 = strips[side]
        ref = (rough[side] - origin) * step
        got, err = side_line(d, ref)
        # Retried whenever the primary pick is suspect: it failed outright, its
        # offset falls outside RETRY_BAND (frame() locked onto the rim itself,
        # as on Russey Chrum (E)), or the rim search only found something via
        # rim_relaxed. A side that is already a clean, in-band, non-relaxed hit
        # never reaches this branch, so it cannot regress a sheet that already
        # places correctly.
        suspect = err is not None or got["relaxed"] or not (RETRY_BAND[0] <= got["offset"] / H <= RETRY_BAND[1])
        if suspect and f"{side}_alt" in rough:
            alt_val = rough[f"{side}_alt"]
            alt_ref = (alt_val - origin) * step
            if 0 <= alt_ref < d.shape[1]:
                alt_d, alt_origin, alt_step, alt_a0 = d, origin, step, a0
            else:
                # The alt peak can sit outside the strip already fetched for the
                # primary guess (Hon Quan (E), Kompong Chhnang (W)); fetch a strip
                # centred on it instead of silently skipping the retry.
                alt_d, alt_origin, alt_step, alt_a0 = frame_strip(
                    base, side, {**rough, side: alt_val}, W, H)
                alt_ref = (alt_val - alt_origin) * alt_step
            alt_got, alt_err = side_line(alt_d, alt_ref)
            if (alt_err is None and not alt_got["relaxed"]
                    and RETRY_BAND[0] <= alt_got["offset"] / H <= RETRY_BAND[1]):
                got, err, d, origin, step, a0 = alt_got, None, alt_d, alt_origin, alt_step, alt_a0
                got["alt"] = True
        if err:
            failed[side] = (d, origin, step, a0, ref, err)
            continue
        got.setdefault("alt", False)
        m = got["m"] * step
        c = origin + step * (got["c"] - got["m"] * a0)
        mid = (H if side in "LR" else W) * sum(SPAN) / 2
        lines[side] = {**got, "m": m, "c": c, "anchor": [mid, m * mid + c]}
        if verbose:
            print(f"  {side}: offset {got['offset']:.1f}px, residual {got['res']:.1f}px, {got['kept']}/{got['found']}"
                  f" patches{' (alt)' if got['alt'] else ''}")
    # A central scale bar can outscore the actual bottom frame in the overview
    # (Bao-Lac E, Vang Vieng E, Muong Ou Tay E). It lies *outside* the true
    # frame, so the resulting offset is much larger than the independently
    # agreeing sides. Look farther inward only in that specific case. Two
    # agreeing ordinary sides suffice when a third side has failed or needed
    # relaxed detection; this lets the missing side use all three after the
    # frame is repaired (Cam Pha E, Thanh-Ba E).
    # The full strip
    # already contains the real frame on these sheets, but a new strip is needed
    # to see the rim another ~170px inward of it.
    outliers = []
    for side in lines:
        others = [lines[s] for s in lines if s != side]
        ordinary = [v["offset"] for v in others if not v["relaxed"]
                    and RETRY_BAND[0] <= v["offset"] / H <= RETRY_BAND[1]]
        if len(ordinary) < 2:
            continue
        median = float(np.median(ordinary))
        if (all(v["relaxed"] or RETRY_BAND[0] <= v["offset"] / H <= RETRY_BAND[1]
                for v in others)
                and (max(ordinary) - min(ordinary)) / median <= .08
                and lines[side]["offset"] > median * 1.2
                and lines[side]["offset"] / H > RETRY_BAND[1]):
            outliers.append((side, median))
    if len(outliers) == 1:
        side, expected = outliers[0]
        d, origin, step, a0 = strips[side]
        ref = (rough[side] - origin) * step
        profile = d.mean(axis=0)
        start = max(1, round(ref) + 60)
        peaks = [i for i in range(start, len(profile) - 12)
                 if profile[i] >= profile[i - 1] and profile[i] > profile[i + 1]]
        peaks.sort(key=lambda i: profile[i], reverse=True)
        tried = []
        for i in peaks:
            if any(abs(i - prior) < 12 for prior in tried):
                continue
            if profile[i] < float(np.percentile(profile, 25)) + 25:
                break
            tried.append(i)
            if len(tried) > 3:
                break
            shifted = origin + step * i
            alt_d, alt_origin, alt_step, alt_a0 = frame_strip(
                base, side, {**rough, side: shifted}, W, H)
            alt_ref = (shifted - alt_origin) * alt_step
            alt_got, alt_err = side_line(alt_d, alt_ref)
            if (alt_err or alt_got["relaxed"]
                    or abs(alt_got["offset"] - expected) > 12
                    or not (RETRY_BAND[0] <= alt_got["offset"] / H <= RETRY_BAND[1])):
                continue
            alt_got["inner_alt"] = True
            m = alt_got["m"] * alt_step
            c = alt_origin + alt_step * (alt_got["c"] - alt_got["m"] * alt_a0)
            mid = (H if side in "LR" else W) * sum(SPAN) / 2
            lines[side] = {**alt_got, "m": m, "c": c, "anchor": [mid, m * mid + c],
                           "alt": False}
            if verbose:
                print(f"  {side}: replaced scale-bar frame with inward line; "
                      f"offset {alt_got['offset']:.1f}px")
            break
    manual = SOURCE_REVIEWED_BOUNDARIES.get(base.rstrip("/").rsplit("/", 1)[-1])
    if manual:
        if (W, H) != manual[:2]:
            return None, "source-reviewed boundary dimensions changed"
        for side, target in manual[2].items():
            d, origin, step, a0 = frame_strip(base, side, {**rough, side: target}, W, H)
            boundary = reviewed_boundary_fit(d, (target - origin) * step)
            if boundary is None:
                return None, f"{side}: source-reviewed boundary would not fit"
            direct = side in manual[3]
            mid = (H if side in "LR" else W) / 2
            m = boundary["m"] * step
            c = origin + step * (boundary["c"] - boundary["m"] * a0)
            # A direct side's offset is discarded (set to 0 below), so the outer
            # decorative rule is never consulted for it -- don't require it to
            # fit either. It can be genuinely unfittable (Sam-Neua (E) R: the
            # rough guess sits in a textured zone with no straight line at all)
            # without blocking a direct correction that doesn't need it.
            if not direct:
                bd, bo, bs, ba = frame_strip(base, side, rough, W, H)
                outer = reviewed_boundary_fit(bd, (rough[side] - bo) * bs)
                if outer is None:
                    return None, f"{side}: source-reviewed outer rule would not fit"
                outer_position = bo + bs * (outer["m"] * (mid - ba) + outer["c"])
            boundary["offset"] = 0 if direct else (m * mid + c - outer_position) * step
            if not direct and not 10 <= boundary["offset"] <= MAXIN + 12:
                return None, f"{side}: reviewed boundary outside the printed margin"
            lines[side] = {**boundary, "m": m, "c": c,
                           "anchor": [mid, m * mid + c], "alt": False}
            if direct:
                lines[side]["direct"] = True
            failed.pop(side, None)
    # A direct boundary is established from this side's source pixels. It
    # does not depend on equal offsets on the other three decorative rules.
    # Try it before the spacing prior; all quad and lattice gates remain active.
    if len(failed) == 1:
        side, (d, origin, step, a0, ref, err) = next(iter(failed.items()))
        direct, direct_err = side_line(d, ref, direct_frame=True)
        if direct_err is None and direct.get("direct"):
            m = direct["m"] * step
            c = origin + step * (direct["c"] - direct["m"] * a0)
            mid = (H if side in "LR" else W) * sum(SPAN) / 2
            lines[side] = {**direct, "m": m, "c": c,
                           "anchor": [mid, m * mid + c], "alt": False}
            failed.clear()
    if failed:
        ordinary = [v["offset"] for v in lines.values() if not v["relaxed"]]
        if len(failed) != 1:
            side = next(iter(failed))
            return None, f"{side}: {failed[side][-1]}"
        three_agree = (len(ordinary) == 3
                       and all(not v["relaxed"] and RETRY_BAND[0] <= v["offset"] / H <= RETRY_BAND[1]
                               for v in lines.values())
                       and (max(ordinary) - min(ordinary)) / np.median(ordinary) <= .08)
        # If the three-side prior fails, accept a *unique* agreeing pair only
        # for a candidate supported across the missing side's patches. This
        # covers Takeo E's skipped right rule while rejecting sheets where two
        # incompatible pairs could both explain the offset.
        pair_prior = None
        if not three_agree:
            trusted = [(s, v["offset"]) for s, v in lines.items()
                       if not v["relaxed"] and RETRY_BAND[0] <= v["offset"] / H <= RETRY_BAND[1]]
            pairs = []
            for i, (sa, a) in enumerate(trusted):
                for sb, b in trusted[i + 1:]:
                    median = (a + b) / 2
                    if (abs(a - b) / median <= .08
                            and all(s in (sa, sb) or v["relaxed"]
                                    or abs(v["offset"] - median) / median > .08
                                    for s, v in lines.items())):
                        pairs.append(median)
            if len(pairs) == 1:
                pair_prior = pairs[0]
        if not three_agree and pair_prior is None:
            side = next(iter(failed))
            return None, f"{side}: {failed[side][-1]}"
        side, (d, origin, step, a0, ref, err) = next(iter(failed.items()))
        got, err = side_line(d, ref, expected_offset=(float(np.median(ordinary)) if three_agree else pair_prior),
                             rank_candidates=not three_agree)
        if err:
            got, err = side_line(d, ref, direct_frame=True)
        if err:
            return None, f"{side}: {err}"
        got["alt"] = False
        m = got["m"] * step
        c = origin + step * (got["c"] - got["m"] * a0)
        mid = (H if side in "LR" else W) * sum(SPAN) / 2
        lines[side] = {**got, "m": m, "c": c, "anchor": [mid, m * mid + c]}
        if verbose:
            print(f"  {side}: offset {got['offset']:.1f}px, residual {got['res']:.1f}px, "
                  f"{got['kept']}/{got['found']} patches "
                  f"({'direct boundary' if got.get('direct') else 'guided'})")
    # A relaxed peak can be the wrong member of a printed line pair. Search
    # earlier blank runs only when all three ordinary sides already agree.
    for side, v in list(lines.items()):
        others = [lines[s]["offset"] for s in lines if s != side and not lines[s]["relaxed"]
                  and RETRY_BAND[0] <= lines[s]["offset"] / H <= RETRY_BAND[1]]
        if (not v["relaxed"] or len(others) != 3
                or (max(others) - min(others)) / np.median(others) > .08
                or abs(v["offset"] - float(np.median(others))) <= max(5.0, 0.0011 * H)):
            continue
        d, origin, step, a0 = strips[side]
        ref = (rough[side] - origin) * step
        candidate, err = side_line(d, ref, expected_offset=float(np.median(others)),
                                   rank_candidates=True, prefer_ranked=True)
        if err or candidate["relaxed"] or not candidate.get("ranked"):
            continue
        m = candidate["m"] * step
        c = origin + step * (candidate["c"] - candidate["m"] * a0)
        mid = (H if side in "LR" else W) * sum(SPAN) / 2
        lines[side] = {**candidate, "m": m, "c": c, "anchor": [mid, m * mid + c], "alt": False}
        if verbose:
            print(f"  {side}: ranked rim offset {candidate['offset']:.1f}px")
    # An ordinary pick can sit on an interior printed rule. Retry a spread
    # failure only with one outlier against three agreeing sides, and require
    # source pixels to change from nearly blank paper to mapped content at the
    # replacement. Offset agreement and a supported peak alone can select a
    # graticule line outside the true border (Bac-Ninh W).
    offsets = [v["offset"] for v in lines.values() if not v.get("direct")]
    if (len(offsets) == 4 and all(not v["relaxed"] for v in lines.values())
            and (max(offsets) - min(offsets)) / np.mean(offsets) > GATE["rim_spread"]):
        alternatives = []
        for side, v in lines.items():
            if v.get("reviewed_boundary"):
                continue
            others = [line["offset"] for key, line in lines.items() if key != side]
            prior = float(np.median(others))
            if ((max(others) - min(others)) / prior > .08
                    or abs(v["offset"] - prior) / prior <= .12
                    or not all(RETRY_BAND[0] <= off / H <= RETRY_BAND[1] for off in others)):
                continue
            d, origin, step, a0 = strips[side]
            ref = (rough[side] - origin) * step
            candidate, err = side_line(d, ref, expected_offset=prior,
                                       rank_candidates=True, prefer_ranked=True)
            if (err or not candidate.get("ranked") or candidate["relaxed"]
                    or abs(candidate["offset"] - prior) >= abs(v["offset"] - prior)):
                continue
            centre = round(candidate["c"] + candidate["m"] * (d.shape[0] - 1) / 2)
            outside = d[:, centre - 35:centre - 10]
            inside = d[:, centre + 8:centre + 30]
            if outside.shape[1] != 25 or inside.shape[1] != 22:
                continue
            outer_ink = float(np.mean(outside > 40))
            inner_ink = float(np.mean(inside > 40))
            if outer_ink >= .03 or inner_ink <= .04 or inner_ink <= 4 * outer_ink:
                continue
            alternatives.append((side, candidate, origin, step, a0))
        if len(alternatives) == 1:
            side, candidate, origin, step, a0 = alternatives[0]
            m = candidate["m"] * step
            c = origin + step * (candidate["c"] - candidate["m"] * a0)
            mid = (H if side in "LR" else W) * sum(SPAN) / 2
            lines[side] = {**candidate, "m": m, "c": c, "anchor": [mid, m * mid + c],
                           "alt": False, "spread_retry": True}
            if verbose:
                print(f"  {side}: spread retry offset {candidate['offset']:.1f}px")
    # On several held scans the overview chose the weaker member of the two
    # horizontal outer rules. Refit the stronger observed rule only when the
    # inner map boundary stays fixed. This repairs an offset measurement, not
    # the geographic placement; the normal geometry gates still run below.
    offsets = [v["offset"] for v in lines.values() if not v.get("direct")]
    if (len(offsets) == 4 and all(not v["relaxed"] for v in lines.values())
            and (max(offsets) - min(offsets)) / np.mean(offsets) > GATE["rim_spread"]):
        target = .023 * H  # independently measured series frame-to-rim band
        for side in "TB":
            old = lines[side]
            if abs(old["offset"] - target) < 12:
                continue
            d, origin, step, a0 = strips[side]
            old_rim = (old["anchor"][1] - origin) * step
            old_frame = round(old_rim - old["offset"])
            profile = d.mean(axis=0)
            if not 0 <= old_frame < len(profile):
                continue
            wanted = round(old_rim - target)
            lo, hi = max(1, wanted - 16), min(len(profile) - 1, wanted + 17)
            peaks = [i for i in range(lo, hi)
                     if profile[i] >= profile[i - 1] and profile[i] > profile[i + 1]
                     and profile[i] > max(100, profile[old_frame] + 20)]
            peaks.sort(key=lambda i: profile[i], reverse=True)
            for peak in peaks[:4]:
                candidate, err = side_line(d, peak)
                if err or candidate["relaxed"]:
                    continue
                new_rim = candidate["c"] + candidate["m"] * (d.shape[0] - 1) / 2
                if (abs(new_rim - old_rim) > 1.5
                        or not 15 <= abs(candidate["offset"] - old["offset"]) <= 35
                        or abs(candidate["offset"] - target) > 12):
                    continue
                m = candidate["m"] * step
                c = origin + step * (candidate["c"] - candidate["m"] * a0)
                mid = W * sum(SPAN) / 2
                lines[side] = {**candidate, "m": m, "c": c, "anchor": [mid, m * mid + c],
                               "alt": False, "frame_retry": True}
                if verbose:
                    print(f"  {side}: stronger frame, offset {old['offset']:.1f} → {candidate['offset']:.1f}px")
                break
    ordinary = [v["offset"] for v in lines.values() if not v["relaxed"]]
    # The relaxed detector follows a low-contrast rim. On a 7,500px scan the
    # same printed-line width spans ~8px (Cam Ranh E, Ninh Binh W); a fixed 5px
    # disagreement limit rejects visibly correct borders there. Keep the 5px
    # floor on smaller scans and scale only this agreement check with height.
    reviewed_rims = SOURCE_REVIEWED_RIMS.get(base.rstrip("/").rsplit("/", 1)[-1])
    rims_reviewed = bool(reviewed_rims and all(
        abs(lines[side]["anchor"][1] - position) <= 2
        for side, position in zip("LRTB", reviewed_rims)))
    if (reviewed_frame or manual) and not rims_reviewed:
        return None, "source-reviewed frame no longer reproduces reviewed rims"
    for side, v in lines.items():
        if (v["relaxed"] and ordinary and not rims_reviewed
                and abs(v["offset"] - float(np.median(ordinary))) > max(5.0, 0.0011 * H)):
            return None, f"{side}: relaxed rim disagrees with ordinary sides"
    # The decorative outer frame has several continuous rules. Its chosen
    # member can vary by 20-30px even when all four mapped boundaries are
    # correctly measured. Require direct source evidence on every side before
    # treating an offset-spread failure as this frame-convention ambiguity.
    boundary_verified = False
    offsets = [v["offset"] for v in lines.values() if not v.get("direct")]
    if (len(offsets) == 4
            and (max(offsets) - min(offsets)) / np.mean(offsets) > GATE["rim_spread"]):
        boundary_verified = True
        for side in "LRTB":
            d, origin, step, a0 = strips[side]
            rim = round((lines[side]["anchor"][1] - origin) * step)
            outside = d[:, rim - 35:rim - 10]
            inside = d[:, rim + 8:rim + 30]
            if outside.shape[1] != 25 or inside.shape[1] != 22:
                boundary_verified = False
                break
            outer_ink = float(np.mean(outside > 40))
            inner_ink = float(np.mean(inside > 40))
            if outer_ink >= .03 or inner_ink <= .04 or inner_ink <= 4 * outer_ink:
                boundary_verified = False
                break
    tan = float(np.mean([lines["T"]["m"], lines["B"]["m"], -lines["L"]["m"], -lines["R"]["m"]]))
    for side in "LRTB":
        m = -tan if side in "LR" else tan
        ax, ay = lines[side]["anchor"]
        lines[side]["m"], lines[side]["c"] = m, ay - m * ax
    def cross(v, hz):
        V, Z = lines[v], lines[hz]
        y = (Z["m"] * V["c"] + Z["c"]) / (1 - Z["m"] * V["m"])
        return [V["m"] * y + V["c"], y]
    corners = {k: cross(*sides) for k, sides in (("NW", ("L", "T")), ("NE", ("R", "T")),
                                                   ("SE", ("R", "B")), ("SW", ("L", "B")))}
    return {"corners": corners, "lines": lines, "rotation": tan,
            "boundary_verified": boundary_verified}, None

def unimarc(value):
    m = re.fullmatch(r"([nsew])(\d{3})(\d{2})(\d{2})", str(value or "").strip(), re.I)
    if not m:
        return None
    deg = int(m[2]) + int(m[3]) / 60 + int(m[4]) / 3600
    return -deg if m[1].lower() in "sw" else deg


def catalogue():
    by_fkey = {}
    for records in json.loads(SOURCE.read_text())["cells"].values():
        for rec in records:
            key = str(rec["fkey"])
            if key in by_fkey:
                raise ValueError(f"duplicate CartoMundi fkey {key}")
            by_fkey[key] = rec
    return by_fkey


def record_box(row, records):
    """Use this maps row's fkey, never the unioned series_sheets bbox."""
    meta = row.get("extra_metadata") or {}
    keys = meta.get("cartomundi_fkeys") or []
    if len(keys) != 1:
        return None, "expected exactly one CartoMundi fkey"
    rec = records.get(str(keys[0]))
    if rec is None:
        return None, f"fkey {keys[0]} absent from serie 561"
    u = rec.get("unimarc") or {}
    vals = {side: unimarc(u.get(side)) for side in "wens"}
    if any(v is None for v in vals.values()):
        return None, f"fkey {keys[0]} has incomplete UNIMARC corners"
    corrected = SOURCE_REVIEWED_CORRECTED_BOX.get(row.get("id"))
    if corrected and str(keys[0]) == corrected[0]:
        vals = {**vals, **corrected[1]}
    box = {"west": vals["w"], "east": vals["e"], "north": vals["n"], "south": vals["s"], "fkey": keys[0]}
    if not (box["west"] < box["east"] and box["south"] < box["north"]):
        return None, f"fkey {keys[0]} has inverted bbox"
    lat_g = (box["north"] - box["south"]) / GRADE
    lon_g = (box["east"] - box["west"]) / GRADE
    standard_span = .48 <= lat_g <= .53 and .36 <= lon_g <= .43
    reviewed = SOURCE_REVIEWED_SPECIAL_SPANS.get(row.get("id"))
    special_span = (reviewed is not None and str(keys[0]) == reviewed[0]
                    and abs(lon_g - reviewed[1]) < .00001
                    and abs(lat_g - reviewed[2]) < .00001)
    if not standard_span and not special_span:
        return None, f"fkey {keys[0]} abnormal span {lon_g:.3f}g × {lat_g:.3f}g"
    if special_span:
        box["special_span"] = True
    return box, None


def rows():
    import requests
    load_dotenv(Path(".env"))
    url, key = os.environ["PUBLIC_SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_SERVICE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    out = []
    offset = 0
    while True:
        response = requests.get(f"{url}/rest/v1/maps", headers=headers, timeout=30,
                                params={"select": "id,name,status,is_georeferenced,extra_metadata,iiif_image",
                                        "collection": f"eq.{COLLECTION}", "order": "id",
                                        "limit": 500, "offset": offset})
        response.raise_for_status()
        page = response.json()
        out.extend(page)
        if len(page) < 500:
            return out
        offset += 500


def sample_rows(all_rows, records, count=12):
    """Evenly spaced latitude ranks, excluding abnormal per-record extents."""
    candidates = []
    for row in all_rows:
        box, err = record_box(row, records)
        if not err and row["status"] == "draft":
            candidates.append(((box["north"] + box["south"]) / 2, row))
    candidates.sort(key=lambda x: (x[0], x[1]["id"]))
    if not candidates:
        return []
    indices = sorted({round(i * (len(candidates) - 1) / (min(count, len(candidates)) - 1))
                      for i in range(min(count, len(candidates)))}) if len(candidates) > 1 else [0]
    return [candidates[i][1] for i in indices]


def grades(value):
    if not value:
        return None
    m = re.search(r"(\d{1,3})\s*(?:[gGᵍ°º]|\^g)\s*(\d{1,4})", str(value))
    if m:
        return float(f"{m[1]}.{m[2]}")
    m = re.search(r"(\d{1,3})\s*\D{0,4}?\s*[,.]\s*(\d{1,4})", str(value))
    if m:
        return float(f"{m[1]}.{m[2]}")
    m = re.fullmatch(r"\s*(\d{1,3})\s*", str(value))
    return float(m[1]) if m else None


def locate_tick(d, approx_along, rim_across):
    """Find the short ink stroke extending outward from the measured neatline."""
    lo, hi = max(0, round(approx_along) - 180), min(d.shape[0], round(approx_along) + 181)
    if hi - lo < 20:
        return None
    cross_lo = max(0, round(rim_across) - 22)
    cross_hi = min(d.shape[1], round(rim_across) - 5)
    if cross_hi - cross_lo < 8:
        return None
    scores = d[lo:hi, cross_lo:cross_hi].mean(axis=1)
    peak = int(np.argmax(scores))
    if scores[peak] < 45:
        return None
    return lo + peak


def tick_label(d, along, rim, axis, side):
    """Read the grade figure beside a detected tick from the cached edge strip."""
    import gemini_client as G
    if axis == "longitude":
        patch = d[max(0, along - 135):along + 135, max(0, round(rim) - 170):round(rim) + 30].T
        if side == "B":
            patch = patch[::-1]
    else:
        patch = d[max(0, along - 125):along + 125, max(0, round(rim) - 210):round(rim) + 30]
        if side == "R":
            patch = patch[:, ::-1]
    if min(patch.shape) < 40:
        return None
    image = Image.fromarray(np.clip(255 - patch, 0, 255).astype(np.uint8)).convert("RGB")
    image = image.resize((image.width * 2, image.height * 2))
    reply = G.extract_labels(
        image,
        system_prompt="Read only the printed grade coordinate beside the graticule tick in this crop.",
        user_prompt=(f"Read the {axis} grade value printed next to the short black tick. "
                     "It may appear as 112g00 or 11g90, where g is a superscript and the "
                     "digits after it are decimal grade digits. Return the entire value "
                     "without inference; return an empty string if absent or unclear."),
        schema={"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]},
        model=G.DEFAULT_MODEL, cache_dir=WORK / "gemini_cache")
    print(f"    {side} {axis} tick OCR: {reply.get('value')!r}", flush=True)
    return grades(reply.get("value"))


def read_printed(base, W, H, measured, box, reverse_sides=False):
    """Two ticks per axis determine both printed frame edges independently."""
    rough = frame(base, W, H)
    corners, lines = measured["corners"], measured["lines"]
    west_g, east_g = [(box[k] - PARIS) / GRADE for k in ("west", "east")]
    north_g, south_g = [box[k] / GRADE for k in ("north", "south")]
    def interior_ticks(low, high, step, inset):
        values = [round(i * step, 3)
                  for i in range(math.ceil(low / step), math.floor(high / step) + 1)
                  if inset <= (i * step - low) / (high - low) <= 1 - inset]
        return [values[0], values[-1]] if len(values) >= 2 else []
    targets = {
        "longitude": [interior_ticks(west_g, east_g, .1, .20),
                      interior_ticks(west_g, east_g, .2, .01)],
        "latitude": [list(reversed(interior_ticks(south_g, north_g, .1, .20))),
                     list(reversed(interior_ticks(south_g, north_g, .2, .01)))],
    }
    observations = {}
    used = {}
    for axis, sides in (("longitude", "BT" if reverse_sides else "TB"),
                        ("latitude", "RL" if reverse_sides else "LR")):
        errors = []
        strips = {}
        for target_pair in targets[axis]:
            if len(target_pair) != 2:
                continue
            for side in sides:
                if side not in strips:
                    strips[side] = frame_strip(base, side, rough, W, H, full_along=True)
                d, origin, step, a0 = strips[side]
                pair = []
                start, end = (("NW", "NE") if side == "T" else ("SW", "SE") if side == "B"
                              else ("NW", "SW") if side == "L" else ("NE", "SE"))
                for target in target_pair:
                    fraction = ((target - west_g) / (east_g - west_g) if axis == "longitude"
                                else (north_g - target) / (north_g - south_g))
                    coordinate = 0 if axis == "longitude" else 1
                    approx = corners[start][coordinate] + fraction * (corners[end][coordinate] - corners[start][coordinate])
                    rim = lines[side]["m"] * approx + lines[side]["c"]
                    tick = locate_tick(d, approx - a0, (rim - origin) * step)
                    if tick is None:
                        errors.append(f"{side}: no tick near {target}g")
                        break
                    position = a0 + tick
                    rim_at_tick = lines[side]["m"] * position + lines[side]["c"]
                    value = tick_label(d, tick, (rim_at_tick - origin) * step, axis, side)
                    if value is None or abs(value - target) > .015:
                        errors.append(f"{side}: read {value}g at expected {target}g tick")
                        break
                    pair.append((position, value))
                if len(pair) == 2:
                    observations[axis] = pair
                    used[axis] = (side, start, end)
                    break
            if axis in observations:
                break
        if axis not in observations:
            return None, "; ".join(errors)
    (x1, lon1), (x2, lon2) = observations["longitude"]
    (y1, lat1), (y2, lat2) = observations["latitude"]
    if x2 - x1 < 500 or y2 - y1 < 500:
        return None, f"tick spacing too small: {observations}"
    lon_per_px = (lon2 - lon1) / (x2 - x1)
    lat_per_px = (lat2 - lat1) / (y2 - y1)
    lon_start, lon_end = used["longitude"][1:]
    lat_start, lat_end = used["latitude"][1:]
    p = {"west": lon1 + (corners[lon_start][0] - x1) * lon_per_px,
         "east": lon1 + (corners[lon_end][0] - x1) * lon_per_px,
         "north": lat1 + (corners[lat_start][1] - y1) * lat_per_px,
         "south": lat1 + (corners[lat_end][1] - y1) * lat_per_px}
    if not (p["west"] < p["east"] and p["south"] < p["north"]):
        return None, f"printed ticks imply inverted rectangle: {p}"
    return {"grades": p, "read": observations, "read_sides": used}, None


def calibration_observation(box, printed, row):
    p = printed["grades"]
    pw, pe = p["west"] * GRADE + PARIS, p["east"] * GRADE + PARIS
    ps, pn = p["south"] * GRADE, p["north"] * GRADE
    # A different-sized polygon is an anomaly, not an offset measurement.
    if abs((box["east"] - box["west"]) - (pe - pw)) > .006 or abs((box["north"] - box["south"]) - (pn - ps)) > .006:
        return None, "catalogue and printed spans disagree"
    lat = (pn + ps) / 2
    dx = (box["west"] - pw) * metres_per_degree(lat)[0]
    dy = (1 if box["south"] > ps else -1) * north_metres(ps, box["south"])
    return {"id": row["id"], "name": row["name"], "fkey": box["fkey"],
            "lat": lat, "dx": dx, "dy": dy, "printed_grades": p,
            "read": printed["read"], "read_sides": printed["read_sides"]}, None


def fit_calibration(observations):
    if len(observations) < 6 or max(o["lat"] for o in observations) - min(o["lat"] for o in observations) < 8:
        raise ValueError("need at least six valid printed sheets over an 8° latitude span")
    lat = np.array([o["lat"] for o in observations])
    dx = np.array([o["dx"] for o in observations])
    dy = np.array([o["dy"] for o in observations])
    # The geographic span is broad; allow both axes a latitude slope and report
    # each observation's residual instead of assuming Tonkin's coefficients.
    ex, ei = np.polyfit(lat, dx, 1)
    ny, ni = np.polyfit(lat, dy, 1)
    residuals = np.hypot(dx - (ei + ex * lat), dy - (ni + ny * lat))
    return {"n": len(observations), "lat_min": float(lat.min()), "lat_max": float(lat.max()),
            "east_intercept_m": float(ei), "east_slope_m_per_deg": float(ex),
            "north_intercept_m": float(ni), "north_slope_m_per_deg": float(ny),
            "residual_mean_m": float(residuals.mean()), "residual_max_m": float(residuals.max()),
            "observations": [{**o, "residual_m": float(r)} for o, r in zip(observations, residuals)],
            "note": "catalogue minus printed; negate to place catalogue on printed frame"}


def calibration_ready(cal):
    return (cal.get("n", 0) >= 6 and cal.get("lat_max", 0) - cal.get("lat_min", 0) >= 8
            and cal.get("residual_max_m", float("inf")) <= 250)


def calibrate(count=12, extras=()):
    records = catalogue()
    all_rows = rows()
    chosen = sample_rows(all_rows, records, count)
    by_row = {r["id"]: r for r in all_rows}
    for mid in extras:
        if mid not in by_row:
            raise ValueError(f"extra map {mid} is not in series 561")
        if mid not in {r["id"] for r in chosen}:
            chosen.append(by_row[mid])
    print(f"calibrating on {len(chosen)} latitude-stratified sheets", flush=True)
    saved = json.loads(OBS_FILE.read_text()) if OBS_FILE.exists() else []
    by_id = {o["id"]: o for o in saved}
    previous = json.loads(REPORT_FILE.read_text()) if REPORT_FILE.exists() else {}
    held = previous.get("held", {}) if previous.get("version") == CAL_VERSION else {}
    held = {mid: reason for mid, reason in held.items()
            if "incomplete tile coverage" not in reason and "ConnectionError" not in reason}
    for i, row in enumerate(chosen, 1):
        if row["id"] in by_id:
            print(f"{i}/{len(chosen)} {row['name']}: cached observation", flush=True)
            continue
        if row["id"] in held:
            print(f"{i}/{len(chosen)} {row['name']}: cached HOLD {held[row['id']]}", flush=True)
            continue
        box, err = record_box(row, records)
        if err:
            held[row["id"]] = err
            continue
        base = row["iiif_image"] or f"https://iiif.maparchive.vn/iiif/{row['id']}"
        print(f"{i}/{len(chosen)} {row['name']} {row['id']} lat {(box['north']+box['south'])/2:.2f}", flush=True)
        try:
            info = T.get_image_info(base)
            measured, err = detect(base, info["width"], info["height"])
            if not err:
                printed, err = read_printed(base, info["width"], info["height"], measured, box)
            if not err:
                obs, err = calibration_observation(box, printed, row)
            if err:
                held[row["id"]] = err
                print(f"  HOLD {err}", flush=True)
            else:
                by_id[row["id"]] = obs
                OBS_FILE.write_text(json.dumps(list(by_id.values()), indent=1))
                print(f"  catalogue − print: {obs['dx']:+.1f}m east, {obs['dy']:+.1f}m north", flush=True)
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
            # Tile and API transport failures are transient; keep their report,
            # but allow the next invocation to retry the sheet.
            if "incomplete tile coverage" not in failure and "ConnectionError" not in failure:
                held[row["id"]] = failure
            print(f"  FAIL {failure}", flush=True)
        REPORT_FILE.write_text(json.dumps({"version": CAL_VERSION,
                                           "selected": [r["id"] for r in chosen],
                                           "held": held}, indent=1))
    observations = [by_id[r["id"]] for r in chosen if r["id"] in by_id]
    lat_span = (max(o["lat"] for o in observations) - min(o["lat"] for o in observations)) if observations else 0
    if len(observations) < 6 or lat_span < 8:
        print(f"calibration rejected: {len(observations)} valid sheets over {lat_span:.2f}° latitude; need six over 8°")
        return None
    cal = fit_calibration(observations)
    print(f"residual mean {cal['residual_mean_m']:.1f}m, max {cal['residual_max_m']:.1f}m")
    print(f"latitude {cal['lat_min']:.2f}–{cal['lat_max']:.2f}°N")
    FIT_FILE.write_text(json.dumps(cal, indent=1))
    if calibration_ready(cal):
        OFFSET_FILE.write_text(json.dumps(cal, indent=1))
        print(f"accepted offset saved to {OFFSET_FILE}")
        return cal
    print(f"calibration rejected: maximum residual exceeds 250 m; exploratory fit saved to {FIT_FILE}")
    return None

def corrected_edges(box, cal):
    lat = (box["north"] + box["south"]) / 2
    east_m = -(cal["east_intercept_m"] + cal["east_slope_m_per_deg"] * lat)
    north_m = -(cal["north_intercept_m"] + cal["north_slope_m_per_deg"] * lat)
    west = box["west"] + east_m / metres_per_degree(lat)[0]
    east = box["east"] + east_m / metres_per_degree(lat)[0]
    south = box["south"] + north_m / metres_per_degree(box["south"])[1]
    north = box["north"] + north_m / metres_per_degree(box["north"])[1]
    return {"west": (west - PARIS) / GRADE, "east": (east - PARIS) / GRADE,
            "south": south / GRADE, "north": north / GRADE}


GATE = {"residual": RESIDUAL, "rim_spread": .12, "aspect": .03, "scale_gap": .015}


def verdict(got):
    bad = []
    if got["aspect_err"] > GATE["aspect"]:
        bad.append(f"shape off by {got['aspect_err']*100:.1f}%")
    worst = max(v["res"] for v in got["lines"].values())
    if worst > GATE["residual"]:
        bad.append(f"edge fit {worst:.1f}px")
    if got["rim_spread"] > GATE["rim_spread"] and not got.get("boundary_verified"):
        bad.append(f"rim offsets spread {got['rim_spread']*100:.0f}%")
    if got["scale_gap"] > GATE["scale_gap"]:
        bad.append(f"axes disagree {got['scale_gap']*100:.1f}%")
    g = got["grades"]
    lon_span = g["SE"][0] - g["NW"][0]
    lat_span = g["NW"][1] - g["SE"][1]
    if not got.get("special_span") and not (.36 <= lon_span <= .43 and .48 <= lat_span <= .53):
        bad.append(f"corner figures span {lon_span:.3f}g × {lat_span:.3f}g")
    return bad


def finish(base, W, H, got, given):
    q = quad(got)
    west, east = given["west"] * GRADE + PARIS, given["east"] * GRADE + PARIS
    north, south = given["north"] * GRADE, given["south"] * GRADE
    gx, gy = ground(west, north, east, south)
    aspect_err = abs(gx / gy - q["aspect"]) / q["aspect"]
    mx, my = gx / q["w"], gy / q["h"]
    # A direct boundary has no frame-to-rim band to compare with the other
    # sides. Its position is still tested by aspect and axis-scale gates.
    offs = [v["offset"] for v in got["lines"].values() if not v.get("direct")]
    mean_off = sum(offs) / len(offs)
    got.update({"rim_spread": (max(offs) - min(offs)) / mean_off if mean_off else 0,
                "read": {}, "disagree": [], "aspect_err": aspect_err,
                "grades": {"NW": [given["west"], given["north"]],
                           "SE": [given["east"], given["south"]]},
                "wgs84": {"NW": [west, north], "NE": [east, north],
                          "SE": [east, south], "SW": [west, south]},
                "quad": q, "m_per_px": [mx, my],
                "scale_gap": abs(mx - my) / max(mx, my)})
    got["verdict"] = verdict(got)
    return got


def finish_printed_quad(got, printed, catalogue_grades):
    """Use independently labelled ticks on all four sides of a skewed frame."""
    grades = printed["grades"]
    extrema = {"west": min(p[0] for p in grades.values()),
               "east": max(p[0] for p in grades.values()),
               "south": min(p[1] for p in grades.values()),
               "north": max(p[1] for p in grades.values())}
    if any(abs(extrema[side] - catalogue_grades[side]) > .003 for side in extrema):
        return None, "printed quad extrema disagree with calibrated catalogue"
    world = {corner: [lon * GRADE + PARIS, lat * GRADE]
             for corner, (lon, lat) in grades.items()}
    def distance(a, b):
        p, q = world[a], world[b]
        east_m, north_m = metres_per_degree((p[1] + q[1]) / 2)
        return math.hypot((q[0] - p[0]) * east_m, (q[1] - p[1]) * north_m)
    gx = (distance("NW", "NE") + distance("SW", "SE")) / 2
    gy = (distance("NW", "SW") + distance("NE", "SE")) / 2
    q = got["quad"]
    mx, my = gx / q["w"], gy / q["h"]
    got["catalogue_scale_gap"] = got["scale_gap"]
    got.update({"grades": {k: list(v) for k, v in grades.items()}, "wgs84": world,
                "m_per_px": [mx, my], "aspect_err": abs(gx / gy - q["aspect"]) / q["aspect"],
                "scale_gap": abs(mx - my) / max(mx, my),
                "printed_quad_review": "eight printed ticks on four source edges checked "
                                       + printed.get("reviewed_on", "2026-09-27")})
    got["verdict"] = verdict(got)
    return got, None


def placement(row, records, cal):
    box, err = record_box(row, records)
    if err:
        return None, err
    base = row["iiif_image"] or f"https://iiif.maparchive.vn/iiif/{row['id']}"
    info = T.get_image_info(base)
    got, err = detect(base, info["width"], info["height"])
    if err:
        return None, err
    if box.get("special_span"):
        reviewed = SOURCE_REVIEWED_SPECIAL_SPANS[row["id"]]
        if ((info["width"], info["height"]) != reviewed[3:5]
                or any(abs(got["lines"][side]["anchor"][1] - position) > 2
                       for side, position in zip("LRTB", reviewed[5]))):
            return None, "special-span source review no longer matches detected boundary"
        got["special_span"] = True
        got["source_review"] = "special cut and four mapped boundaries checked against source overview on 2026-09-27"
    catalogue_grades = corrected_edges(box, cal)
    got = finish(base, info["width"], info["height"], got, catalogue_grades)
    reviewed = SOURCE_REVIEWED_RIMS.get(row["id"])
    reviewed_rims_match = (reviewed and all(
        abs(got["lines"][side]["anchor"][1] - position) <= 2
        for side, position in zip("LRTB", reviewed)))
    printed = SOURCE_REVIEWED_PRINTED_QUADS.get(row["id"])
    if printed and all(problem.startswith("axes disagree")
                       or (reviewed_rims_match and problem.startswith("rim offsets spread"))
                       for problem in got["verdict"]):
        if any(abs(got["lines"][side]["anchor"][1] - position) > 2
               for side, position in zip("LRTB", printed["rims"])):
            return None, "printed-quad source review no longer matches detected boundary"
        got, err = finish_printed_quad(got, printed, catalogue_grades)
        if err:
            return None, err
    got.update({"id": row["id"], "name": row["name"], "fkey": box["fkey"],
                "detector_version": DETECT_VERSION,
                "placed_from": ("four-edge printed ticks" if got.get("printed_quad_review")
                                else "per-record CartoMundi UNIMARC, calibrated against printed corners")})
    if reviewed_rims_match:
        got["source_review"] = "four mapped boundaries checked against source strips on 2026-09-27/28"
        got["verdict"] = [problem for problem in got["verdict"]
                          if not problem.startswith("rim offsets spread")]
    if (row["id"] in SOURCE_REVIEWED_AXES_DISAGREE
            and got["scale_gap"] <= AXES_DISAGREE_REVIEWED_CAP
            and got["aspect_err"] <= AXES_DISAGREE_REVIEWED_CAP
            and all(problem.startswith("axes disagree") or problem.startswith("shape off by")
                    for problem in got["verdict"])):
        # aspect_err and scale_gap are the same printed-sheet distortion read two
        # ways (gx/gy vs. pixel aspect, vs. mx vs. my) -- they move together, so a
        # sheet over the 3% shape gate almost always also fails axes-disagree, and
        # "shape off by" must be allowed through the guard too, not just "axes
        # disagree" (2026-09-30, caught reviewing the first cut of this rule).
        got["axes_disagree_review"] = ("source-confirmed real printed-sheet distortion, "
                                        "absorbed by the georeference transform, 2026-09-30")
        got["verdict"] = []
    if row["id"] in CALIBRATION_HOLDS:
        got["verdict"].append(CALIBRATION_HOLDS[row["id"]])
    return got, None


def place(map_id=None):
    if not OFFSET_FILE.exists():
        raise SystemExit("run calibrate and inspect its residuals before placement")
    cal = json.loads(OFFSET_FILE.read_text())
    if not calibration_ready(cal):
        raise SystemExit("calibration does not clear the six-sheet, 8° latitude, 250 m residual gate")
    records = catalogue()
    selected = [r for r in rows() if r["status"] == "draft" and not r["is_georeferenced"]
                and (map_id is None or r["id"] == map_id)]
    if map_id and not selected:
        raise SystemExit(f"no pending draft sheet {map_id}")
    WORK.mkdir(parents=True, exist_ok=True)
    for i, row in enumerate(selected, 1):
        path = WORK / f"{row['id']}.json"
        previous = json.loads(path.read_text()) if path.exists() else {}
        if (previous.get("detector_version") == DETECT_VERSION
                and not previous.get("placement_error")):
            print(f"{i}/{len(selected)} {row['name']}: cached")
            continue
        try:
            got, err = placement(row, records, cal)
        except Exception as exc:
            got, err = None, f"{type(exc).__name__}: {exc}"
        if err:
            previous.update({"id": row["id"], "name": row["name"],
                             "verdict": [err], "placement_error": err,
                             "placement_attempt_version": DETECT_VERSION})
            path.write_text(json.dumps(previous, indent=1))
            print(f"{i}/{len(selected)} {row['name']}: HOLD {err}", flush=True)
            continue
        path.write_text(json.dumps(got, indent=1))
        print(f"{i}/{len(selected)} {row['name']}: {'HOLD ' + '; '.join(got['verdict']) if got['verdict'] else 'clear'}", flush=True)


def check():
    """Self-consistency of placements; return failure on conflicting records."""
    records = catalogue()
    dbrows = {r["id"]: r for r in rows()}
    cells, problems, offsets, footprints = {}, [], [], []
    for file in sorted(WORK.glob("*.json")):
        if not re.fullmatch(r"[0-9a-f-]{36}", file.stem):
            continue
        got = json.loads(file.read_text())
        if got.get("verdict"):
            continue
        row = dbrows.get(got["id"])
        if not row:
            problems.append(f"{got['id']}: missing DB row")
            continue
        box, err = record_box(row, records)
        if err or str(box["fkey"]) != str(got.get("fkey")):
            problems.append(f"{got['id']}: fkey or span no longer matches row")
            continue
        w = got["wgs84"]
        key = (round(w["NW"][0], 3), round(w["NW"][1], 3),
               round(w["SE"][0], 3), round(w["SE"][1], 3))
        cell = (row["extra_metadata"].get("sheet_number"), row["extra_metadata"].get("sheet_half"))
        cells.setdefault(cell, []).append((key, got["id"]))
        footprints.append((cell, got["id"],
                           (min(p[0] for p in w.values()), min(p[1] for p in w.values()),
                            max(p[0] for p in w.values()), max(p[1] for p in w.values()))))
        # Decorative-frame distances on the source-reviewed special cuts are
        # not comparable with standard half sheets: they retain a ~170px band
        # on a taller mapped quadrangle. Kompong Chhnang W has a separately
        # reviewed 73px bottom band. Every footprint still enters lattice checks.
        if (not got.get("source_review")
                or (not got.get("special_span")
                    and got["id"] not in SOURCE_REVIEWED_RIMS)):
            offsets.append((np.mean([v["offset"] for v in got["lines"].values() if not v.get("direct")])
                            / got["quad"]["h"], got["id"]))
    for cell, vals in cells.items():
        if len({key for key, _ in vals}) > 1:
            problems.append(f"cell {cell} reprints disagree: {vals}")
    # A full sheet and its W/E cuts are alternative printings of one numbered
    # cell. Their geographic coverage intentionally overlaps, provided the
    # half is contained in the full sheet and shares its northern/southern edge.
    # Keep the ordinary cross-cell overlap gate for unrelated sheet numbers.
    for i, (cell_a, id_a, a) in enumerate(footprints):
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        for cell_b, id_b, b in footprints[i + 1:]:
            if cell_a == cell_b:
                continue
            overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
            area_b = (b[2] - b[0]) * (b[3] - b[1])
            full_a = cell_a[1] in (None, "", "whole")
            full_b = cell_b[1] in (None, "", "whole")
            if cell_a[0] == cell_b[0] and (full_a or full_b):
                full, half = (a, b) if full_a else (b, a)
                if (full[0] - .005 <= half[0] < half[2] <= full[2] + .005
                        and abs(full[1] - half[1]) <= .005
                        and abs(full[3] - half[3]) <= .005):
                    continue
            if overlap > .4 * min(area_a, area_b):
                problems.append(f"different cells overlap: {cell_a} {id_a} / {cell_b} {id_b}")
    if offsets:
        median = float(np.median([o for o, _ in offsets]))
        for offset, mid in offsets:
            if abs(offset / median - 1) > .15:
                problems.append(f"{mid}: rim offset differs >15% from series median")
    print(f"checked {sum(map(len, cells.values()))} placements in {len(cells)} sheet slots")
    for problem in problems:
        print("  HOLD " + problem)
    return not problems


def regress(tolerance=2.0):
    """Re-run detect() from cache against every saved clear placement's corners.

    The one thing any change to frame()/side_line()/rim_in() must not do is move
    a sheet that already places correctly -- this is what proved the alt-retry
    (added 2026-09-24) regression-free before it landed. Reads only cached IIIF
    crops; run place() first if a sheet's strips were never fetched.
    """
    bad = []
    n = 0
    for file in sorted(WORK.glob("*.json")):
        if not re.fullmatch(r"[0-9a-f-]{36}", file.stem):
            continue
        saved = json.loads(file.read_text())
        if saved.get("verdict") or "lines" not in saved or "quad" not in saved:
            continue
        base = f"https://iiif.maparchive.vn/iiif/{saved['id']}"
        info = T.get_image_info(base)
        got, err = detect(base, info["width"], info["height"])
        n += 1
        if err:
            bad.append(f"{saved['name']}: now fails: {err}")
            continue
        for c in CORNERS:
            dx = got["corners"][c][0] - saved["corners"][c][0]
            dy = got["corners"][c][1] - saved["corners"][c][1]
            if math.hypot(dx, dy) > tolerance:
                bad.append(f"{saved['name']}: {c} moved {dx:.2f},{dy:.2f}px")
    print(f"checked {n} clear placements, {len(bad)} regressions")
    for msg in bad:
        print("  " + msg)
    return not bad


def annotate(write=False, only_new=True, only_ids=None):
    """Prepare Allmaps annotations; --apply writes draft rows only."""
    import requests
    if not OFFSET_FILE.exists() or not calibration_ready(json.loads(OFFSET_FILE.read_text())):
        raise SystemExit("calibration has not cleared the residual and latitude gates")
    if not check():
        raise SystemExit("lattice check failed; no annotations prepared")
    load_dotenv(Path(".env"))
    url, key = os.environ["PUBLIC_SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_SERVICE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    dbrows = {r["id"]: r for r in rows()}
    outdir = WORK / "annotations"
    outdir.mkdir(parents=True, exist_ok=True)
    done = held = 0
    for file in sorted(WORK.glob("*.json")):
        if not re.fullmatch(r"[0-9a-f-]{36}", file.stem):
            continue
        got = json.loads(file.read_text())
        row = dbrows.get(got.get("id"))
        if (got.get("verdict") or not row or got.get("id") in CALIBRATION_HOLDS or
                row["status"] != "draft" or (only_new and row["is_georeferenced"]) or
                (only_ids is not None and got.get("id") not in only_ids)):
            held += 1
            continue
        mid = got["id"]
        iiif = row["iiif_image"] or f"https://iiif.maparchive.vn/iiif/{mid}"
        info = T.get_image_info(iiif)
        ann = annotation(iiif, info["width"], info["height"], got)
        (outdir / f"{mid}.json").write_text(json.dumps(ann, indent=1))
        w = got["wgs84"]
        bbox = [w["SW"][0], w["SW"][1], w["NE"][0], w["NE"][1]]
        if not write:
            print(f"{got['name']}: ready {bbox}")
            done += 1
            continue
        body = (outdir / f"{mid}.json").read_bytes()
        obj = f"{url}/storage/v1/object/{BUCKET}/{mid}.json"
        response = requests.post(obj, headers={**headers, "Content-Type": "application/json",
                                               "x-upsert": "true"}, data=body, timeout=60)
        if response.status_code == 400:
            response = requests.put(obj, headers={**headers, "Content-Type": "application/json",
                                                  "x-upsert": "true"}, data=body, timeout=60)
        response.raise_for_status()
        # Not a raw storage URL: the "annotations" bucket has no working public
        # path (confirmed 2026-09-30 -- it 400s "Bucket not found" for every
        # sheet written this way). Every sheet published before this one uses
        # the app's own route, which serves the same bucket through the
        # service-role client regardless of the bucket's own public flag.
        public = f"https://maparchive.vn/api/maps/{mid}/annotation"
        response = requests.patch(f"{url}/rest/v1/maps?id=eq.{mid}&status=eq.draft&is_georeferenced=is.false",
                                  headers=headers, timeout=30,
                                  json={"annotation_url": public, "is_georeferenced": True, "bbox": bbox})
        response.raise_for_status()
        print(f"{got['name']}: written")
        done += 1
    print(f"{done} {'written' if write else 'ready'}, {held} held")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["calibrate", "candidates", "detect", "place", "check", "annotate", "regress"])
    parser.add_argument("map_id", nargs="?")
    parser.add_argument("--count", type=int, default=12, help="latitude-stratified calibration sample size")
    parser.add_argument("--extra", action="append", default=[], help="additional series-561 map id for calibration")
    parser.add_argument("--lat-min", type=float, default=19, help="candidates: minimum catalogue latitude")
    parser.add_argument("--lat-max", type=float, default=23.5, help="candidates: maximum catalogue latitude")
    parser.add_argument("--apply", action="store_true", help="annotate: write draft-only annotation and flag")
    parser.add_argument("--ids", help="annotate: comma-separated map ids to restrict to")
    args = parser.parse_args()
    if args.phase == "calibrate":
        if calibrate(args.count, args.extra) is None:
            raise SystemExit(1)
    elif args.phase == "candidates":
        records = catalogue()
        for row in rows():
            box, err = record_box(row, records)
            if not err and args.lat_min <= (box["north"] + box["south"]) / 2 <= args.lat_max:
                print(f"{(box['north'] + box['south']) / 2:5.2f} {row['id']} {row['name']}")
    elif args.phase == "place":
        place(args.map_id)
    elif args.phase == "check":
        if not check():
            raise SystemExit(1)
    elif args.phase == "annotate":
        annotate(args.apply, only_ids=set(args.ids.split(",")) if args.ids else None)
    elif args.phase == "regress":
        if not regress():
            raise SystemExit(1)
    else:
        if not args.map_id:
            parser.error("detect requires map_id")
        base = f"https://iiif.maparchive.vn/iiif/{args.map_id}"
        info = T.get_image_info(base)
        got, err = detect(base, info["width"], info["height"], verbose=True)
        if err:
            raise SystemExit(err)
        print(json.dumps(got["corners"], indent=1))


if __name__ == "__main__":
    main()
