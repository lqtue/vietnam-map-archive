# VMA 3D Pipeline — Technical Reference
_Morlighem Adaptation + Photogrammetry_
_March 2026_

---

## Overview

VMA produces 3D models of 1880–1930 Saigon through two complementary pipelines:

1. **Automated LoD2** — Morlighem (2021) pipeline adapted to VMA's IIIF georef output → CityJSON box
   models for all buildings
2. **Photogrammetry LoD3+** — SfM from archival photos → textured mesh for ~30 landmark buildings

These correspond to **L2 (volumetric 3D)** and **L3 (facade + road)** in the 6-layer data stack.

---

## Pipeline 1: Morlighem Adaptation (LoD2)

### Source

**Morlighem, C. (2021).** *Automatic reconstruction of 3D city models from historical maps.* MSc
thesis, TU Delft / Delft University of Technology. Supervisor: Hugo Ledoux (CityJSON creator, TU
Delft 3D Geoinformation Group).

Code: `github.com/CamilleMorlighem/histo3d` (CC-BY licence)

**Results (original paper):** >84% building plot detection, >89% building plot classification, >99%
valid CityJSON geometry. Tested on two cities: Delft (Dutch) and Brussels (Belgian).

**Critical condition:** These results apply only to maps that are *"properly scanned, with
sufficient spatial resolution and strict symbology rules."* Morlighem's abstract frames this as the
primary determinant of pipeline quality. Inconsistent scanning, low resolution, or variable
cartographic conventions degrade results significantly — this is VMA's main technical risk, not a
minor calibration question.

**Co-supervisors:** Hugo Ledoux and Anna Labetski (TU Delft 3D geoinformation group); co-reader
Francesca Noardo.

### Why This Fits VMA

| Morlighem prerequisite | VMA status |
|---|---|
| Georeferenced historical map rasters | Done — L7014 pipeline mature; colonial maps extension planned |
| Known cartographic colour scheme | Colonial French Indochina maps have consistent symbology (buildings=pink/red, streets=white/grey, water=blue) |
| Building footprints as OBIA input | Stage 4 of Morlighem; VMA community tracing pre-populates this |
| CityJSON output format | Hugo Ledoux (CityJSON creator) is Morlighem's supervisor — direct compatibility |

**The key complement:** VMA automates georeferencing (the prerequisite Morlighem left manual).
Morlighem automates 3D from georeferenced maps. Together they form a complete pipeline from scanned
map → validated 3D city model.

### Pipeline Steps

```
Stage 1: OBIA segmentation
  Input:  Georeferenced colonial map raster (GeoTIFF from VMA annotate pipeline)
  Tool:   GRASS GIS + SegSeg / OTB
  Output: Classified regions — buildings, streets, water, vegetation, text
  Config: Colour model calibrated for French colonial Indochina cartographic symbology
            buildings: pink/red hues (Munsell 5R-10R)
            streets:   white/light grey
            water:     blue
            vegetation: green
  Risk:   CENTRAL RISK (not a minor question): Morlighem explicitly states the
          84%/89% accuracy holds only under "strict symbology rules." French
          colonial Indochina maps have varying publishers, ink degradation, and
          mixed cartographic conventions. A calibration study on 5–10 maps is
          needed before claiming transferability. This is the pipeline's primary
          unknown — treat it as a prerequisite research question, not an
          implementation detail.

Stage 2: Text removal
  Tool:   Connected component analysis (Tesseract mask + morphological ops)
  Output: Clean segmentation with map labels removed

Stage 3: Vectorisation
  Tool:   GRASS GIS v.clean + v.generalize
  Output: 2D building plot polygons (GeoJSON)
  Note:   Complements community tracing — ML detects, community validates

Stage 4: 2D procedural modelling
  Tool:   Custom Python (Morlighem) + PostGIS
  Output: Individual building footprint polygons (not merged blocks)
  Step:   Separate merged building plots into individual lots using cadastral logic

Stage 5: Height inference (NO LiDAR needed)
  Method: Probabilistic roof type table × building typology
  Table:  Roof type probabilities by building category:
            residential/Chinese shophouse:  flat roof 80%, pitched 20%
            colonial admin buildings:       hipped roof 70%, gabled 20%, flat 10%
            warehouses/commercial:          flat roof 90%
            religious:                      tower + pitched (custom)
  Sources (in priority order):
    1. Painting-map pairs (two contemporaneous pairs available):
         a. 1881 B&W engraving (Colonies Françaises - Cochinchine, "Saigon") paired
            with 1882 cadastral map — monochrome oblique view of the full city;
            gives height classes and massing for the early colonial grid.
            Height anchor: documented landmarks (cathedral, government buildings).
         b. 1901 colored lithograph paired with 1898 cadastral map — full-color
            oblique view showing the city at peak first-wave development.
            ADDITIONAL VALUE over 1881 engraving:
              - Color confirms roof material: near-uniform terracotta tile
                across residential/commercial stock (validates NYPL classifier)
              - Color distinguishes white/cream institutional buildings from
                red-tile residential — directly maps to cadastral color classes
              - More buildings visible (city more complete by 1901)
              - Temporal pair (1882 vs 1898 maps + 1881 vs 1901 paintings)
                provides visual ground-truth for stable/new/demolished classification
            Caveat: oblique projection distorts absolute heights — use for height
            CLASS assignment (1/2/3 stories) not metric values; calibrate with
            known reference structures.
    2. EFEO/BnF/Manhhai photos — height ratios observable from street-level photos
    3. Cadastral records — floor counts for commercial buildings in land registers
    4. Building typology standards — French colonial construction norms for each type
  Output: Height estimate + uncertainty_m field in CityJSON
  Note:   Painting calibration reduces uncertainty from ±3m to ~±1.5m for
          buildings visible in 1881/1901 paintings; the two-period pair enables
          cross-validation — a building present and unchanged in both paintings
          gets higher height confidence than one visible in only one source.

Stage 6: 3D procedural modelling
  Tool:   Blender (BCGA — Building CGA grammar)
  Output: LoD2 CityJSON — box geometry with typed roof
  Export: CityJSON → glTF/GLB for web viewer (Three.js / Cesium.js)
```

### Output Schema

```json
{
  "type": "CityJSON",
  "version": "1.1",
  "CityObjects": {
    "building_uuid": {
      "type": "Building",
      "attributes": {
        "vma:entity_id": "kg_entity_uuid",
        "vma:valid_from": "1900",
        "vma:valid_to": "1954",
        "measuredHeight": 8.5,
        "vma:height_uncertainty_m": 2.0,
        "vma:roof_type": "hipped",
        "vma:roof_type_confidence": 0.7,
        "vma:source": "morlighem_auto_v1"
      }
    }
  }
}
```

### Validation

- **Geometric validation:** `cjio` (CityJSON CLI) — checks topology, manifold geometry
- **Attribution validation:** Every automated building is flagged `vma:source: morlighem_auto_v1` so
  users know it is approximate
- **Community review:** Architect tier contributors can flag incorrect height/roof assignments
- **Ground truth:** EFEO photos provide spot-checks for key buildings

---

## Pipeline 2: Photogrammetry (LoD3+)

### Goal

For ~30 landmark buildings (Notre Dame, City Hall, Opera House, Central Post Office, Ben Thanh
Market, key Cholon merchant buildings), produce textured 3D meshes with facade detail — linked to KG
entities, viewable in browser.

### Photo Sources

| Collection | Coverage | Notes |
|---|---|---|
| **1881 B&W engraving** (Colonies Françaises — Cochinchine, "Saigon") | Full city oblique view — height classes + massing for early colonial grid | Pairs with 1882 cadastral map; monochrome limits material info |
| **1901 colored lithograph** (city coat-of-arms, full color) | Full city oblique view — color confirms terracotta roof tile at city scale; shows expanded 1898-era city | Pairs with 1898 cadastral map; richer than 1881 for LoD2 roof type + material |
| EFEO (École française d'Extrême-Orient) | Best systematic collection — colonial buildings, street-level + elevated views | BnF Gallica (partially open) |
| BnF Gallica postcards | 1900–1930 Saigon postcard boom — natural multi-angle facade coverage | Open IIIF |
| Manhhai collection (Flickr) | Large private digitised collection, mixed dates | Open |
| Family archives | Diaspora uploads via community contribution | Via `/contribute/photo` |
| ANOM (Archives nationales d'outre-mer) | French colonial admin photos | On-site / digitisation project needed |

**Key insight on painting-map pairs:** VMA has two contemporaneous painting-map pairs — a rare
combination that most historical reconstruction projects lack:

- **Pair 1882:** The 1881 B&W engraving "Saigon" (Colonies Françaises — Cochinchine) pairs with the
  1882 cadastral map. The engraving shows the full city from an elevated oblique south-to-north
  perspective. Massing, story heights, and roof shapes are directly readable for all blocks visible
  in the scene.

- **Pair 1898:** The 1901 full-color lithograph pairs with the 1898 cadastral map. The painting
  shows the city at peak first-wave colonial development. The color is the critical additional
  value: near-uniform terracotta roof tiling across residential and commercial stock is visually
  confirmed at city scale — this directly calibrates the NYPL color classifier and the Morlighem
  probabilistic roof type table without requiring European priors. Institutional buildings
  (white/cream) and military/warehouse zones (grey/brown) are visually distinct and map precisely
  onto the cadastral color classes.

**Temporal pair methodology:** The two paintings together enable a visual cross-validation of the
automated temporal classification (stable / new / demolished) produced by the `match` command. A
block that appears built-up in both the 1881 and 1901 paintings is a visual confirmation of "stable"
status for that building cluster. A block sparse in 1881 but dense in 1901 visually confirms "new
construction" between the two map dates.

**Workflow:** Architecture historians annotate buildings visible in each painting → cross-reference
with the paired cadastral polygon → assign height class (1/2/3 stories) + roof type → calibrate
height estimates in probabilistic table → apply as priors in Morlighem height inference. Landmark
height anchors: Notre-Dame Cathedral spires (57 m, documented), Hôtel de Ville facade (approx. 18
m), Marché Central roof ridge (approx. 12 m).

**Key insight on postcards:** The Saigon postcard industry (1900–1930) produced a large volume of
images of the city's major buildings. [NOTE: the claim that this exceeds other colonial cities in
comparable volume needs a citation before it appears in a paper — it is currently unverified.]

### SfM Pipeline

```
Phase 1: Photo collection + curation
  - Community Photo Hunter tier tags photos to buildings (KG entity link)
  - Mission card shows which angles are covered / needed
  - Target: 15+ photos per building, covering front + sides + aerial if available

Phase 2: SfM processing
  Tool 1: COLMAP (open-source, GPU-accelerated) — recommended
  Tool 2: Meshroom (open-source, AliceVision framework) — alternative
  Tool 3: Metashape (commercial) — for high-priority landmarks with funding

  Steps:
    1. Feature extraction (SIFT/SuperPoint)
    2. Feature matching (exhaustive for <100 photos, sequential for more)
    3. Sparse reconstruction (SfM) → camera poses + sparse point cloud
    4. Dense reconstruction (MVS) → dense point cloud
    5. Mesh generation → surface mesh
    6. Texture mapping → textured mesh

Phase 3: Post-processing + export
  Tool:   Blender (mesh cleanup) + cjio (CityJSON wrapping)
  Output: GLB (textured, compressed) for web viewer
         CityJSON (semantic geometry for data layer)
  Upload: Supabase Storage → `photogrammetry_sessions.mesh_url`

Phase 4: Validation + publish
  - Architect tier: submit mesh
  - Admin review: geometry quality + texture quality
  - On approval: `photogrammetry_sessions.status = 'done'`
  - KG entity `/kg/[id]` shows 3D tab
  - All contributors get reveal notification + badge
```

### Limitations and Honest Notes

- **No interior data:** Historical photos are almost entirely exterior. Interior reconstructions are
  not feasible.
- **Photo dating uncertainty:** Many Manhhai/EFEO photos have approximate dates (1900–1910). SfM
  meshes inherit this uncertainty — buildings may show a composite of several decades.
- **Scale ambiguity:** SfM produces relative scale. Absolute scale requires at least one known
  dimension (building width from cadastral record, or person of known height in photo). Architecture
  historians provide this from KG data.
- **Older photos = lower quality:** Pre-1910 glass plate photographs are lower resolution. Some will
  not produce clean SfM meshes. Expectation: ~60% of landmark buildings produce usable meshes from
  available EFEO/Gallica material. [NOTE: this figure is an estimate without citation — needs
  empirical support or should be reframed as a hypothesis.]
- **Nostalgin (Kapoor et al. 2019) is NOT a SfM precedent.** That paper uses single-view neural
  reconstruction (MaskRCNN + inpainting) and explicitly assumes a Manhattan-world (orthogonal grid).
  Colonial Saigon's street network violates this assumption. Nostalgin is referenced in some VMA
  notes as a photogrammetry precedent — this is incorrect. VMA's COLMAP/Meshroom SfM approach has no
  direct published precedent for colonial Southeast Asian architecture and should be framed as
  original applied research.

---

## Two-Tier Output Summary

| | LoD2 (Morlighem automated) | LoD3+ (SfM photogrammetry) |
|---|---|---|
| Coverage | All buildings (~500–2,000 in 1900 core) | ~30 landmark buildings |
| Accuracy | Approximate (height ±2m, footprint from map) | Photo-realistic facade detail |
| Time to produce | Weeks (batch pipeline) | Weeks–months per building |
| Data format | CityJSON | GLB + CityJSON |
| Uncertainty | Explicit `height_uncertainty_m` field | Photo dating uncertainty noted |
| Web viewer | Cesium.js / Three.js city model | `<model-viewer>` or Three.js |
| Attribution | `vma:source: morlighem_auto_v1` | Per-contributor in KG |

---

## 4D Viewer Integration

The 3D city model is served through the `/timeline` route as temporal snapshots:

| Snapshot | Source maps | Expected coverage |
|---|---|---|
| 1890 | ANOM plan cadastral 1890 | City centre + Cholon |
| 1910 | BnF Gallica 1905 + EFEO 1908 | Full colonial city |
| 1930 | ANOM 1924 + EFEO 1930 | Full city + suburbs |

At each snapshot: footprints from community tracing → LoD2 model from Morlighem → LoD3+ overlaid for
landmarks.

Users can scrub between snapshots and watch buildings appear, change, or disappear.

---

## Academic Partnership

**TU Delft 3D Geoinformation Group** (Prof. Hugo Ledoux) is the natural partner:
- Hugo Ledoux created CityJSON — direct format compatibility
- He supervised Morlighem's thesis — direct pipeline expertise
- TU Delft has experience with historical city reconstruction across Dutch/Belgian cities
- VMA brings the first Southeast Asian colonial city application of this methodology

**Contact at TU Delft:** Hugo Ledoux + Anna Labetski (both supervised Morlighem). Francesca Noardo
(co-reader) is also a relevant contact — she specialises in 3D standards and cultural heritage.

**Proposed collaboration:**
- Joint paper: *Automated 3D reconstruction of a French colonial city from historical map rasters —
  extending the Morlighem pipeline to French Indochina cartographic symbology*
- Target venue: ISPRS Annals or International Journal of Digital Earth
- TU Delft co-applies to EU Horizon Digital Heritage calls with VMA as domain partner

---

## Open Source Commitment

- Pipeline adaptation code: published under MIT licence
- Calibrated colour model for French colonial Saigon symbology: published as GRASS GIS module
- Probabilistic roof type table: published as CC-BY dataset
- Model weights (if ML detection is added): published on Hugging Face
- All output CityJSON: published under ODbL (OpenStreetMap licence)
