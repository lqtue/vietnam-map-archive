# Historical city reconstruction — plan

This plan sets out how Vietnam Map Archive could show Saigon through time, using historical
maps and bird's-eye views to build simple city models and detailed landmarks. It records the
library options, evidence rules and delivery stages discussed on 2026-10-12.

**Status: planned; implementation has not started.** After checking the engraving, the first
deliverable is a short test of simple building volumes from the existing 1882 footprint cluster.
Choose the viewer after that test, then add supported heights and one landmark. The
[1882 feature-layer plan](image-processing-1882-plan.md) remains the current delivery priority.
1898 reconstruction follows that delivery. This file describes the approach; the
[roadmap](ROADMAP.md) remains the tracker when this work is scheduled.

## Viewer choice follows the small test

The earlier plan chose CesiumJS before testing VMA data and required too many tools for a small
pilot. The follow-up session summary changes that order. Neither Cesium nor Three.js is currently
in `package.json`; there is no implemented 3D path to preserve.

Use a local JSON file of reviewed footprints and their evidence links for the first scene.
Try the least costly route that answers the question: can we draw these volumes in the right
places, show their assumptions and open the right source when clicked? A small Three.js scene is
the first candidate. Choose Cesium if geography, map alignment or loading work makes that route
costlier. Do not build several viewers before finding a concrete limit in the first one.

Exercise year switching in this test too. A clearly labelled synthetic second state can test the
control before 1898 is reviewed; keep it outside historical exports and claims. A scene that draws
one year but cannot switch states has not tested the core requirement.

Record the result and the reason for choosing the engine. Citywide streaming, detailed modelling,
research exports and database changes follow a working pilot.

## Tools to consider after the test

| Role | Choice | Reason |
| --- | --- | --- |
| City viewer | Three.js or CesiumJS, decided by the test | Small-scene control versus built-in geographic and time support. |
| Ordinary buildings | S3DB → OSM2World, when roof generation is needed | Generates buildings from reviewed footprints, heights and roof descriptions. |
| Detailed landmarks | Blender → GLB, after the simple scene works | Gives us control over complex roofs and façades; GLB carries the model into the browser. |
| Historical records | Local JSON for the test; VMA's Supabase database later | Establish the dated-state and evidence records before adding tables. |
| Research exports | CityJSON, when a research use requires it | Preserves generated geometry and attributes for inspection and exchange. |
| Model hosting | Local files first; Cloudflare R2 for cleared public assets | Avoids publishing source data whose reuse terms are unresolved. |
| Large-area delivery | 3D Tiles, later | Loads visible parts of the city at the detail needed for the camera view. |

CesiumJS remains a strong option for the larger city-through-time view. We still need to test
alignment, interaction and phone performance with VMA assets. Its time support does not choose historical building states for us:
VMA must decide which model or city snapshot applies at each date.

Giro3D is the alternative if the Cesium prototype exposes a concrete problem. It supports
OpenLayers sources and Three.js models, but that does not establish support for VMA's custom
Allmaps renderer. Start with a historical map image already placed in ground coordinates.

MapLibre with Three.js remains an option for a smaller map-focused scene. It would require more
work on historical state selection and model loading. Unreal is a later option for an exhibition
or immersive application, with its own build and delivery workflow.

Keep the first test local and separate from the app. If it passes, add a separate 3D view.
Use the existing scan tools to review map observations.
Load the 3D library when the reader opens that view. Cesium ion may later supply managed tiling
and hosting if it saves enough work; CesiumJS can also read models from our own hosting.

## What each format does

- **S3DB** describes how to build ordinary volumes from footprints, parts, heights and roofs.
- **CityJSON** records generated 3D geometry, object relationships and attributes.
- **GLB** carries a display model, including landmark geometry and textures.
- **3D Tiles** packages display geometry for loading and drawing large areas in parts.

Keep one editable VMA record. Generate exports from it and record the generator version and
settings. Independently edited OSM and CityJSON copies would create competing versions.
Converting an arbitrary GLB to CityJSON does not restore building or surface meanings; any
research export must preserve or assign those meanings explicitly.

## Sources and dates

The follow-up session reports 46 approved 1882 footprints, including 17 tagged as buildings,
clustered around 106.700° E, 10.776° N near the Palais du Gouverneur. This is the proposed pilot
area. It is not District 4, which has no footprints in the reported audit. These are database
counts, not a complete inventory of historical buildings; confirm the feature types and exact
cluster boundary before modelling.

Check that this area is visible and readable in the Favre/Lepère engraving before fixing its
boundary or choosing a landmark. If it is not, choose another small area rather than inventing
the missing architectural evidence.

| Source | Role | Date and limit |
| --- | --- | --- |
| 1882 cadastral map, `0e02b9d9-9d40-4cca-8e41-8c8373d54d3b` | Footprints, street layout and water | Map observations for 1882; dimensions and placement depend on the pinned scan and georeference. |
| Favre/Lepère, *Saïgon d'après nature* | Visible roofs, storeys and relative massing | Published in 1881; check each proposed match to the 1882 map. |
| 1898 cadastral map, `20ec4f9a-16bd-4895-a593-40c6ed9c9555` | Second map state | Further reconstruction waits for the 1882 delivery and its own footprint review. |
| Pusch/Claude, *Ville de Saigon. 1902.*, David Rumsey List No. 16413.000 | Colour and architectural observations | The catalogue dates this copy 1902. Geographicus describes a view as circa 1898, undated. Compare the images before treating them as the same edition. |

The [panorama sourcing note](journals/260921-panorama-sourcing.md#addendum-2026-10-12--the-1898-pair-cited-to-david-rumsey)
now records the Rumsey catalogue and the limits of its machine-written summary. The printed date
still needs an image check. A 1902 depiction does not by itself establish a building's form in 1898.

Colour in the panorama supports a depicted appearance; it does not establish roof material by
itself. Cadastral property colours describe property categories, not architectural materials.

## Building records and evidence

Build on the [evidence-chain plan](evidence-chain-plan.md). A reconstruction record should link to
its map observations and, where established, the identity of the historical building. A footprint
row is an observation; matching two rows across dates is a separate claim.

Each dated building state needs:

- Footprint and part geometry, with courtyard rings where supported.
- Storeys, total height, roof form and roof dimensions; ranges or alternatives where uncertain.
- Evidence for each attribute: source image, crop or document locator, date and interpretation.
- Review decisions and any values supplied only to make the model drawable.
- Source-image identity, georeference version, generation settings and export identity.

Keep observation dates separate from construction and demolition dates. Preserve previous
published states when evidence changes. Keep uncertainty about position, identity, date, height
and roof form separate. Unknown evidence remains unknown; a renderer default is an assumption.

The existing `footprints` table has no height or roof fields. Do not treat a proposed record as
an existing database feature. For the first test, keep parameters in local JSON linked to the
footprint ID; use the result to design later storage.

### How assumed values look

- Draw a volume whose height is assumed with a wireframe or hatched surface. Its panel says
  `Height assumed` and gives the value and its basis.
- When no height estimate is supported, use a common schematic display height and label it
  `Display height only`. Exclude it from height measurements and panorama calibration.
- Draw supported attributes normally, but let the reader inspect their source and uncertainty.
  A supported footprint does not make its assumed height supported.
- Preserve these cues in both simple buildings and detailed landmarks. Use words and patterns
  as well as colour, and provide a view showing the unresolved parts.

Use fixed source years first. Do not animate gradual building changes between two observations
without evidence for when or how those changes happened.

## Landmark detail

Choose the historical state first, then the rendering detail:

| Decision | Example |
| --- | --- |
| Historical state | The supported form of a landmark in 1882 or 1898. |
| Evidence-supported detail | Simple massing, roof geometry or documented façade features. |
| Rendering detail | A simplified mesh from far away and a richer mesh nearby. |

The landmark model replaces its corresponding background building. Record explicit replacement
IDs. A hide box can help with overlapping proposals, but it is a display aid: preview which
objects it hides and never delete observations through it. Keep the landmark's identity and evidence
links through each model version. Prepare simplified assets for distant views; the viewer cannot
recover detail that was never modelled. High geometric detail does not imply high historical
confidence.

Preserve courtyards and water islands before generating geometry. VMA's current footprint storage
keeps outer rings only, while the local QGIS exports can preserve holes. Resolve that gap for the
pilot rather than filling courtyards or islands silently.

## Modern HCMC data and terrain

The follow-up session reports modern data at `~/Work/Projects/hcmc-buildings`: about 2.1 million
LiDAR-measured building footprints plus topographic layers. In an approximately 1.3 km box around
the pilot cluster, it reports 2,673 buildings and 1,208 spot heights ranging from 1.3 to 12.4 m.
These figures come from that session summary; this plan update did not repeat the data audit.

The reported range rules out treating the present ground as uniformly flat. Confirm the height
datum, units, point types and locations before using the values. Modern relief does not establish
1882 relief: filling, grading and riverbank work may have changed it.

Use the modern data locally to find possible survivor buildings and control points, examine
present relief and prepare a separate 2023 comparison. A survivor is a candidate until its
identity and dated form are checked. Never draw modern buildings as the 1882 city.

Reuse terms remain unresolved. Keep these data and derived model assets out of git and R2.
A flat plane may still serve the first schematic test, labelled as such; it is not a measured
historical terrain model. A later local relief comparison must label modern terrain separately.

## Lessons from the two reviewed sites

These notes record the user's follow-up session summary, not a new code audit.

- [cuulong3d](https://github.com/lysyan911/cuulong3d): borrow the explicit landmark replacements,
  a reusable kit of building models, historical-map ground and a phone quality tier. Its guessed
  building types are visual suggestions, not historical evidence. Review code and asset reuse
  terms before copying either.
- [Hanoi Maps](https://github.com/hanoimaps/hanoimaps.github.io): borrow quick year switching and
  dated street-name histories. Keep names linked to evidence and dates in VMA's model.

The previous claim that a sheet-to-tiles script already exists was wrong. `sheet_pmtiles.py` is
proposed work. `@allmaps/maplibre` beta.44 is a candidate; its pitch support and behaviour on this
sheet have not been checked. Choose and test a map-display path rather than assuming one exists.

## Delivery stages

| Stage | Work | Completion check |
| --- | --- | --- |
| 1. Check the engraving | Fetch the Favre/Lepère image and inspect the proposed footprint cluster. | The pilot area is visible and readable; matched landmarks and gaps are recorded. |
| 2. Prepare the small input | Confirm the existing building traces and their source links. Resolve holes only where the test needs them. | One local JSON file has the selected footprints, evidence links and stated assumptions. |
| 3. Test simple volumes; choose the engine | Draw the selected footprints with clearly marked display heights, a source panel and a phone quality tier. Try the cheapest workable route first. | Positions and IDs survive the display path, assumptions are visible, and loading and navigation are measured on a phone. Record the engine decision. |
| 4. Add supported heights | Read storeys and relative heights from the engraving, with independent dated anchors where available. | Each architectural value has evidence, a range or an explicit assumption. |
| 5. Add one landmark | Build its supported historical form with replacement IDs and simpler distance versions. | No duplicate buildings appear; its dated form and uncertain parts are inspectable. |
| 6. Add 1898 after 1882 delivery | Review the same area on the 1898 map and check which colour-view observations apply. | Changing the year loads the correct buildings, map and evidence; date gaps stay visible. |

Only then consider further districts, CityJSON research exports and 3D Tiles for large-area loading.
The small local test does not require finishing the entire sheet; the existing 1882 delivery
plan still governs full-sheet review, publication and the order of later extraction work.

Fix the pilot boundary after checking visibility in the engraving. Include ordinary housing,
a courtyard building and one identifiable landmark. Keep modelling work outside untouched
segmentation evaluation windows, following the active 1882 plan's blind-window rules.

Record loading time, frame time, memory use and model size on named desktop and phone devices.
Check source IDs after export so picking opens the right record. Compare the model with the map
and panorama, but use independent dated evidence where available to assess architectural claims.
Schema and geometry checks establish valid files, not historical correctness.

## References

Library capabilities checked on 2026-10-12; no VMA viewer benchmark has been run.

- [CesiumJS](https://cesium.com/platform/cesiumjs/) — models, imagery, 3D Tiles and time-dependent display.
- [Cesium entity availability](https://cesium.com/learn/cesiumjs/ref-doc/Entity.html) — time intervals for objects.
- [Cesium tileset controls](https://cesium.com/learn/cesiumjs/ref-doc/Cesium3DTileset.html) — loading and detail refinement.
- [Giro3D](https://giro3d.org/giro3d.html) — OpenLayers sources, Three.js objects and model formats.
- [Simple 3D Buildings](https://wiki.openstreetmap.org/wiki/Simple_3D_Buildings) — footprints, building parts and architectural tags.
- [OSM2World](https://osm2world.org/) — scene generation and GLB export.
- [CityJSON specification](https://www.cityjson.org/specs/2.0.2/) — geometry, attributes and object relationships.
- [CityJSON validation](https://www.cityjson.org/tutorials/validation/) — separate structure and geometry checks.
- [Cloudflare R2 hosting](https://developers.cloudflare.com/r2/buckets/public-buckets/) — serving assets through a custom domain.
