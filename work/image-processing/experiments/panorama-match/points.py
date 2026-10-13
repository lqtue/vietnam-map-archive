#!/usr/bin/env python3
"""Ground points for matching the 1881 Favre/Lepère view to the ground: street corners that existed
in 1881 and still exist, in lng/lat.

    python3 work/image-processing/experiments/panorama-match/points.py   # -> points.csv beside this file

Source: modern streets already warped into the 1882 sheet's pixels (modern_prior.py, affine from
gcps-1882.json). This undoes that affine exactly, so the lng/lat is the modern street line, not the
1882 sheet. Corner = closest approach of the two named streets; `gap_m` > ~5 says they do not meet.
"""
import csv, json
from pathlib import Path
import numpy as np, shapely, shapely.geometry
from shapely.ops import nearest_points

R = Path("work/image-processing/results/prior/0e02b9d9-9d40-4cca-8e41-8c8373d54d3b")
TDT = "Tôn Đức Thắng"
# (id, street a, street b, what to look for in the engraving)
PAIRS = [
    ("q-hamnghi", TDT, "Hàm Nghi", "quay at the mouth of the Grand Canal (filled 1887)"),
    ("q-nguyenhue", TDT, "Nguyễn Huệ", "quay at the mouth of the Charner canal (filled 1887)"),
    ("q-dongkhoi", TDT, "Đồng Khởi", "rue Catinat meets the quay"),
    ("q-leduan", TDT, "Lê Duẩn", "bd Norodom meets the quay at the arsenal; same corner as Đinh Tiên Hoàng"),
    ("dk-leloi", "Đồng Khởi", "Lê Lợi", "Catinat x bd Bonnard"),
    ("dk-lethanhton", "Đồng Khởi", "Lê Thánh Tôn", "Catinat x rue d'Espagne"),
    ("dk-lytutrong", "Đồng Khởi", "Lý Tự Trọng", "Catinat x rue Lagrandière"),
    ("ld-pasteur", "Lê Duẩn", "Pasteur", "bd Norodom, west of the cathedral"),
    ("ld-namky", "Lê Duẩn", "Nam Kỳ Khởi Nghĩa", "bd Norodom in front of the Governor's palace"),
    ("ld-haibatrung", "Lê Duẩn", "Hai Bà Trưng", "bd Norodom, east of the cathedral"),
    ("ld-macdinhchi", "Lê Duẩn", "Mạc Đĩnh Chi", "bd Norodom at the citadel's west side"),
    ("hbt-lethanhton", "Hai Bà Trưng", "Lê Thánh Tôn", "mid-town"),
    ("pasteur-leloi", "Pasteur", "Lê Lợi", "mid-town, left"),
    ("nk-leloi", "Nam Kỳ Khởi Nghĩa", "Lê Lợi", "left, towards the old market"),
    ("nmk-haibatrung", "Nguyễn Thị Minh Khai", "Hai Bà Trưng", "far edge, rue Chasseloup-Laubat"),
    ("nmk-namky", "Nguyễn Thị Minh Khai", "Nam Kỳ Khởi Nghĩa", "far edge, behind the palace"),
]


def px_to_lonlat():
    g = json.load(open(R / "gcps-1882.json"))["gcps"]
    px = np.array([p["px"] for p in g]); ll = np.array([p["lonlat"] for p in g])
    o = ll.mean(0)
    A, *_ = np.linalg.lstsq(np.column_stack([ll - o, np.ones(len(ll))]), px, rcond=None)  # = SheetFit.to_px
    M = np.vstack([A.T, [0, 0, 1]])  # [x,y,1] = M @ [dlng,dlat,1]
    Mi = np.linalg.inv(M)
    return lambda p: (Mi @ np.r_[p, 1])[:2] + o


def main():
    to_ll = px_to_lonlat()
    s = json.load(open(R / "streets.geojson"))["features"]
    lines = {}
    for f in s:
        n = f["properties"]["name"]
        if n:
            lines.setdefault(n, []).append(shapely.geometry.shape(f["geometry"]))
    m_per_deg = np.array([111_320 * np.cos(np.radians(10.78)), 111_133])
    rows = []
    for pid, a, b, look in PAIRS:
        if a not in lines or b not in lines:
            print("missing street", pid); continue
        pa, pb = nearest_points(shapely.union_all(lines[a]), shapely.union_all(lines[b]))
        mid = np.array([(pa.x + pb.x) / 2, (pa.y + pb.y) / 2])
        lng, lat = to_ll(mid)
        gap = np.linalg.norm((to_ll([pa.x, pa.y]) - to_ll([pb.x, pb.y])) * m_per_deg)
        rows.append(dict(id=pid, lng=round(lng, 6), lat=round(lat, 6), gap_m=round(gap, 1),
                         streets=f"{a} x {b}", look_for=look))
    # sanity: Notre-Dame footprint centroid must land on the cathedral
    nd = next(f for f in json.load(open(R / "landmarks.geojson"))["features"] if f["properties"]["key"] == "notre-dame")
    c = shapely.Polygon(nd["geometry"]["coordinates"][0]).centroid
    lng, lat = to_ll([c.x, c.y])
    print(f"check: Notre-Dame centroid {lng:.6f},{lat:.6f} (cathedral is ~106.6990,10.7798)")
    rows.append(dict(id="notre-dame", lng=round(lng, 6), lat=round(lat, 6), gap_m=0, streets="footprint centroid",
                     look_for="cathedral: centre of the nave at ground level, between the two towers' feet"))
    out = Path(__file__).with_name("points.csv")
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for r in rows: print(r["id"], r["lng"], r["lat"], r["gap_m"])
    print("->", out)


if __name__ == "__main__":
    main()
