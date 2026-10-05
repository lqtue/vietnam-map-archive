"""Export existing 1882 results for QGIS; no downloads or database writes.

python3 work/image-processing/scripts/export_1882_qgis.py export
python3 work/image-processing/scripts/export_1882_qgis.py return-json EDITED.gpkg OUT_DIR

Uses system Python's geopandas, rasterio, shapely and Pillow, not the OCR venv.
Output folders must not already exist, so hand edits cannot be overwritten.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import geopandas as gpd
import numpy as np
from PIL import Image
import pyogrio
from rasterio.features import shapes, rasterize
from rasterio.transform import Affine
from shapely.affinity import scale
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[3]
MAP_ID = "0e02b9d9-9d40-4cca-8e41-8c8373d54d3b"
SOURCE = ROOT / "work/image-processing/results" / MAP_ID
CRS = 'LOCAL_CS["1882 source pixels",LOCAL_DATUM["Image origin",0],UNIT["pixel",1],AXIS["Column",EAST],AXIS["Negative row",NORTH]]'
TRANSFORM = Affine(1, 0, 0, 0, -1, 0)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def return_json(src, dest):
    """Flip QGIS y-up coordinates back to VMA's source-pixel y-down frame."""
    layers = pyogrio.list_layers(src)
    dest.mkdir(parents=True, exist_ok=False)
    for name, geometry_type in layers:
        if geometry_type is None:
            continue
        frame = gpd.read_file(src, layer=name)
        # Reprojection would destroy the source-pixel correspondence.
        if frame.crs is not None and not frame.crs.equals(gpd.GeoSeries([], crs=CRS).crs):
            raise ValueError(f"{name}: CRS changed; return the original pixel CRS without reprojection")
        features = []
        for feature in frame.iterfeatures(drop_id=True):
            geom = scale(shape(feature["geometry"]), xfact=1, yfact=-1, origin=(0, 0))
            if not geom.is_valid or geom.is_empty:
                raise ValueError(f"{name}: invalid/empty geometry; fix it in QGIS first")
            feature["geometry"] = mapping(geom)
            feature["properties"]["area_px"] = geom.area
            features.append(feature)
        write_json(dest / f"{name}.json", {
            "type": "FeatureCollection", "coordinate_system": "source-pixels-y-down",
            "map_id": MAP_ID, "features": features,
        })
        print(f"{name}: {len(features)} features returned to source pixels", flush=True)


def export(dest):
    dest.mkdir(parents=True, exist_ok=False)
    Image.MAX_IMAGE_PIXELS = 200_000_000  # known local full-resolution scan
    width, height = Image.open(SOURCE / "native.png").size
    manifest = {"map_id": MAP_ID, "created_utc": datetime.now(timezone.utc).isoformat(),
                "image_size": [width, height], "coordinate_system": "x=source column, y=-source row; units=pixels",
                "layers": {}, "inputs": {}}
    json_dir = dest / "source-pixel-json"
    json_dir.mkdir()

    def record(path):
        relative = str(path.relative_to(SOURCE))
        manifest["inputs"][relative] = {"sha256": digest(path)}
        return relative

    def layer(name, features, source, note):
        native_features = []
        for i, ft in enumerate(features):
            props = dict(ft["properties"])
            props.update(map_id=MAP_ID, export_id=f"{name}:{i}", source_file=source,
                         review_status="needs_review")
            native_features.append({"type": "Feature", "geometry": ft["geometry"], "properties": props})
        write_json(json_dir / f"{name}.json", {
            "type": "FeatureCollection", "coordinate_system": "source-pixels-y-down",
            "map_id": MAP_ID, "features": native_features,
        })
        frame = gpd.GeoDataFrame.from_features(native_features)
        frame.geometry = frame.geometry.map(lambda g: scale(g, xfact=1, yfact=-1, origin=(0, 0)))
        frame = frame.set_crs(CRS)
        if not frame.geometry.is_valid.all():
            raise ValueError(f"Invalid geometry in {name}; do not silently repair")
        frame.to_file(dest / "1882-edit.gpkg", layer=name, driver="GPKG", engine="pyogrio")
        loaded = gpd.read_file(dest / "1882-edit.gpkg", layer=name)
        assert len(loaded) == len(frame)
        assert all(a.equals_exact(b, 1e-8) for a, b in zip(frame.geometry, loaded.geometry))
        manifest["layers"][name] = {"count": len(frame), "source": source, "note": note}
        print(f"{name}: {len(frame)} valid polygons", flush=True)

    cleaned = SOURCE / "colour-20260919-normalized/blocks.regularized.geojson"
    features = json.loads(cleaned.read_text())["features"]
    source = record(cleaned)
    for kind, name in [("land_plot", "plots"), ("building", "buildings")]:
        layer(name, [f for f in features if f["properties"]["feature_type"] == kind], source,
              "Cleaned/regularized outlines; extents still need hand correction. Regularization removed original holes.")

    for name, filename, kind in [("water", "water-1006337f.png", "waterway"),
                                  ("roads_diagnostic", "road-a3b0458f.png", "road")]:
        path = SOURCE / "river" / filename
        source = record(path)
        mask = np.asarray(Image.open(path)) > 0
        assert mask.shape == (height, width)
        polygons = [shape(g) for g, _ in shapes(mask.astype("uint8"), mask=mask,
                                               transform=TRANSFORM, connectivity=4)]
        # Pixel-edge polygonization: retain all components and islands, no area filter.
        rebuilt = rasterize([(g, 1) for g in polygons], out_shape=mask.shape,
                            transform=TRANSFORM, dtype="uint8")
        assert np.array_equal(rebuilt, mask), f"{name}: polygonization changed mask pixels"
        fs = []
        for g in polygons:
            native = scale(g, xfact=1, yfact=-1, origin=(0, 0))
            fs.append({"type": "Feature", "geometry": mapping(native),
                       "properties": {"feature_type": kind, "area_px": native.area,
                                      "source_index": len(fs), "mask_version": filename,
                                      "classification_note": "waterway/water_body split needs hand review" if name == "water" else "unscored road proposal"}})
        layer(name, fs, source, "Frozen v3 proposal. Exact pixel edges, all holes and components preserved. "
              + ("Water type needs review." if name == "water" else "Diagnostic only; unscored."))

    latest = SOURCE / "colour-20261001/blocks.geojson"
    layer("colour_oct01_experimental", json.loads(latest.read_text())["features"], record(latest),
          "Newer 4096-render experiment; raw colour classes. Alternative to plots/buildings, not an additional set of objects.")
    record(SOURCE / "native.png")
    shutil.copy2(SOURCE / "native.png", dest / "1882-scan.png")
    # World-file pixel centre is (0.5, -0.5); vector boundaries are pixel corners.
    (dest / "1882-scan.pgw").write_text("1\n0\n0\n-1\n0.5\n-0.5\n")
    (dest / "1882-scan.prj").write_text(CRS + "\n")
    from xml.sax.saxutils import escape
    bands = "".join(f'<VRTRasterBand dataType="Byte" band="{b}"><ColorInterp>{colour}</ColorInterp>'
                    f'<SimpleSource><SourceFilename relativeToVRT="1">1882-scan.png</SourceFilename><SourceBand>{b}</SourceBand>'
                    f'<SrcRect xOff="0" yOff="0" xSize="{width}" ySize="{height}"/>'
                    f'<DstRect xOff="0" yOff="0" xSize="{width}" ySize="{height}"/></SimpleSource></VRTRasterBand>'
                    for b, colour in [(1, "Red"), (2, "Green"), (3, "Blue")])
    (dest / "1882-scan.vrt").write_text(f'<VRTDataset rasterXSize="{width}" rasterYSize="{height}"><SRS>{escape(CRS)}</SRS>'
                                       f'<GeoTransform>0,1,0,0,0,-1</GeoTransform>{bands}</VRTDataset>\n')
    write_json(dest / "manifest.json", manifest)
    (dest / "load_in_qgis.py").write_text('''# Run in the QGIS Python Console editor; opens and styles this package.
from pathlib import Path
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsFillSymbol
package = Path(__file__).resolve().parent
project = QgsProject.instance()
scan = QgsRasterLayer(str(package / "1882-scan.vrt"), "1882 original scan")
assert scan.isValid(), "Scan failed to load"
project.setCrs(scan.crs())
project.addMapLayer(scan)
for name, colour in [("colour_oct01_experimental", "#888888"), ("roads_diagnostic", "#e69024"),
                     ("water", "#218acf"), ("plots", "#c89730"), ("buildings", "#cc3648")]:
    layer = QgsVectorLayer(str(package / "1882-edit.gpkg") + "|layername=" + name, name, "ogr")
    assert layer.isValid(), name
    layer.renderer().setSymbol(QgsFillSymbol.createSimple({"color": "0,0,0,0", "outline_color": colour, "outline_width": "0.25"}))
    project.addMapLayer(layer)
    project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(name not in ("colour_oct01_experimental", "roads_diagnostic"))
iface.mapCanvas().setExtent(scan.extent())
iface.mapCanvas().refresh()
project.setFileName(str(package / "1882-tracing.qgz"))
project.write()
''')
    (dest / "README.md").write_text(f'''# 1882 QGIS editing package

Start: drag `1882-scan.vrt` and `1882-edit.gpkg` into a new QGIS project.
Select the local **1882 source pixels** CRS for the project (or use No CRS).
The VRT supplies the exact raster placement and local CRS. Keep the whole folder together.

For automatic styling and a saved project: open Plugins → Python Console, then run:

```python
exec(compile(open({str(dest / 'load_in_qgis.py')!r}).read(), {str(dest / 'load_in_qgis.py')!r}, 'exec'), {{'__file__': {str(dest / 'load_in_qgis.py')!r}}})
```

## Layers

- `plots`: cleaned/regularized parcel outlines (881).
- `buildings`: cleaned/regularized building outlines (550).
- `water`: frozen water v3, polygonized exactly; islands/holes retained.
- `roads_diagnostic`: frozen road v3, unscored; keep hidden until needed.
- `colour_oct01_experimental`: newer raw colour-run alternative; keep hidden to avoid duplicates.

All are proposals marked `needs_review`. Newer does not mean reviewed or better.
The regularized plot/building input already lost its original holes; add rings where needed.
Water is provisionally typed `waterway`; set isolated ponds to `water_body` by hand.
Original processing files remain untouched; the GeoPackage is your editable copy.

## Edit

Select a layer → Toggle Editing (pencil). Use Vertex Tool to move/add/delete vertices;
Add Polygon to trace missing objects; Add Ring for islands; Split Features to divide merged objects.
Use transparent fill with a coloured outline so the scan remains visible.
For neighbouring plots enable vertex/segment snapping and topological editing.
Save Layer Edits often, and save the project as `1882-tracing.qgz` in this folder.
New objects need `feature_type` and `review_status`; retain existing `export_id` and `source_index`.

QGIS editing reference: https://docs.qgis.org/3.44/en/docs/user_manual/working_with_vector/editing_geometry_attributes.html

## Coordinates and JSON

QGIS uses x=column, y=negative row, in pixels. Do not reproject or assign EPSG:4326.
This is for tracing the original scan; it does not overlay a modern basemap.
The scan is 12102 × 8982 px; (0,0) is its top-left corner, (12102,-8982) bottom-right.

`source-pixel-json/*.json` are FeatureCollections in VMA's original x=column, y=row-down frame.
Use the GeoPackage for QGIS editing, not those source-frame JSON files.
After saving edits, export back to JSON (new folder each time):

```sh
python3 work/image-processing/scripts/export_1882_qgis.py return-json \\
  '{dest / '1882-edit.gpkg'}' \\
  '{dest / 'edited-source-json'}'
```

The command flips y back and recomputes `area_px`; it preserves holes and attributes.
These are local JSON exports, not database uploads. The existing VMA footprint table only stores
outer rings; decide how to handle holes before importing them there.
For new features, fill attributes in QGIS; the return command does not mark anything approved.

`manifest.json` records exact input hashes, source files, layer counts and limitations.
No OCR text, modern OSM layers, or held-out evaluation windows are included.
''')
    print(f"Package: {dest}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    out = commands.add_parser("export")
    out.add_argument("--out", type=Path, default=SOURCE / "qgis-1882-20261003")
    back = commands.add_parser("return-json")
    back.add_argument("gpkg", type=Path)
    back.add_argument("out", type=Path)
    args = parser.parse_args()
    if args.command == "export":
        export(args.out.resolve())
    else:
        return_json(args.gpkg.resolve(), args.out.resolve())
