import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ocr" / "scripts"))
from modern_prior import fit_sheet
from scale import annotation_for_map
for name, mid, w, h in [("1882","0e02b9d9-9d40-4cca-8e41-8c8373d54d3b",12102,8982),("1898","20ec4f9a-16bd-4895-a593-40c6ed9c9555",16267,14859)]:
    ann = annotation_for_map(mid); f = fit_sheet(ann)
    print(name, f, "m/px", f.metres_per_px if f else None); print("  bbox", f.bbox_lonlat(w,h) if f else None)
