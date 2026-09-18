# Field audit — the domain VMA operates in

_Stage 3 artifact. Plain-language map of the scholarly + open-source field around VMA, the
methods it borrows, the gaps it can fill, and the literature behind it. Feeds the `realm:"field"`
nodes in `graph.json`. Sources: `docs/field-knowledge-graph.md`, `docs/theory.md`, and the
167-PDF reading library at `~/Downloads/Urbanism/` (7 folders)._

Written so a non-specialist understands the landscape, but precise enough to seed graph nodes and
the seminar / Engaging-With-Vietnam decks and the PhD SOP.

---

## How to read this

VMA sits at the intersection of five worlds: (1) historical-map **georeferencing**,
(2) map **vectorization / OBIA**, (3) **historical GIS + digital humanities**,
(4) **citizen-science / HITL** crowdsourcing, and (5) **colonial + Vietnamese urban history /
planning**. For each we name who does it well, what the canonical tools/works are, and — crucially
— **where the gap is**, because the gaps are VMA's publishable research contributions.

Two kinds of "gap" appear below:
- **Research gaps** (`kind:"gap"`) — things nobody has published; VMA's contribution opportunities.
- **Library gaps** (`status:"gap"` on `kind:"work"`) — canonical books VMA *should* cite that are
  NOT in the 167-PDF library yet (Thongchai *Siam Mapped*, Anderson *Imagined Communities*, etc.).

---

## The library at a glance (`~/Downloads/Urbanism/`, 167 PDFs)

| Folder | Theme | Weight | What it anchors |
|---|---|---|---|
| `01-phd-priority` | Saigon/HCMC + colonial urbanism core (Wright, Harms, Huynh, Rabinow…) | 20 | The dissertation's empirical + theoretical spine |
| `02-hgis-methodology` | Historical GIS + spatial-history method (Knowles, Gregory, Harley, White…) | 24 | Cluster A method grounding |
| `03-vietnam-indochina` | Vietnam/Indochina specific (Annuaire, Whitmore, de Rugy, Huynh The Du…) | 27 | Area-studies + primary-source layer |
| `04-vma-pipeline` | Map CV/vectorization technical (Morlighem, Chen, Jiao, Xia MapSAM2…) | 35 | The technical pipeline literature (largest block) |
| `05-tod-transport` | TOD / transit-oriented development | 8 | Contemporary-planning arm (post-Doi Moi) |
| `06-phd-references` | Application materials (CVs, writing samples) | 3 | SOP / outreach support |
| `07-general-theory` | Urban theory canon (Lefebvre, Harvey, Jacobs, Scott, Foucault…) | 37 | The interpretive lens (largest block) |

The two heaviest folders — **technical pipeline (35)** and **urban theory (37)** — are exactly the
two halves of VMA's "body and soul" claim: the CV machinery and the interpretive frame. The middle
is thin on purpose: the original bridge (spatial methods *on* colonial Saigon) is the gap.

---

## Cluster 1 — Historical-map georeferencing

**The standard:** **Allmaps** (Bert Spaan, Jules Schoonman/TU Delft Library, Manuel Claeys
Bouuaert) — IIIF-native, client-side WebGL warping, all data as W3C Georeference Annotations.
Funded by the Pica Foundation. **VMA is built directly on it** (`@allmaps/openlayers`,
`@allmaps/maplibre`). Production exemplar: **Atlascope** (Ian Spangler, Leventhal/BPL — 145+ Boston
atlases). Older workhorse: **MapWarper** (Tim Waters). Series-georeferencing research: Martijn
Meijers (TU Delft).

**Automated frontier (none general-purpose yet):** OCR+geocoding (~316 m error); deep-learning
feature matching (RMSE <1% on 83% of 86 Jerusalem maps); object-detection for series (Sanborn, 14%
fully auto). VMA's L7014 **GCP-propagation over a uniform military grid + Helmert datum correction
(Indian 1960 → WGS84)** is *not* in this list — see Gap 2.

---

## Cluster 2 — Map vectorization / OBIA (the largest technical block)

**The reference pipeline:** **histo3d** (Camille Morlighem, TU Delft 2021) — raster → GRASS OBIA →
polygonize → height inference → Blender procedural → LoD2 CityJSON. >84% plot detection, >99% valid
geometry — **but only under strict, consistent symbology** (the central risk for any new map style).
Supervisors **Hugo Ledoux** (CityJSON author) + **Anna Labetski** = VMA's strongest technical-PhD
target (the VMA georef pipeline is the *input* histo3d needs).

**ETH IKG** (Lorenz Hurni, Sidi Wu, Yizi Chen, Konrad Schindler) — cross-attention spatio-temporal
transformers for segmentation *across map editions* (urban change detection, not single-map). Note:
two "Yizi Chen" (ETH vs LRDE/EPITA). **SODUCO** (Julien Perret/IGN; EHESS, BnF, EPITA/LRDE) — Paris
1789–1950, vectorization + 113 trade directories → urban-history KG. **VMA's closest methodological
peer** (same loop, different city). Its **benchmark paper** (Chen et al., PLoS ONE 2024) is the
field's first systematic method comparison. **NYPL Building Inspector + Map Vectorizer** (Mauricio
Giraldo Arteaga) — the canonical HITL precedent (170k polygons in 24h). The library also holds the
newest work VMA actually runs/cites: **Xia, MapSAM2 (2025)**, **Jiao road vectorization (2024)**,
Chen 2021/2023, Petitpierre 2023, Schlegel, Iosifescu, Uhl/Duan, Chiang.

---

## Cluster 3 — Historical GIS, digital humanities & 4D city models

**HGIS founders** (the vocabulary): **Anne Kelly Knowles** (Maine — defined HGIS in English),
**Ian Gregory** (Lancaster — coined "spatial humanities"; **closest method+career fit for VMA**, see
below), **Peter Bol** (Harvard — **CHGIS**, the infrastructure template + the *closest career
analogy* to VMA's founder: a humanist who learned spatial methods mid-career), **Humphrey Southall**
(GB Historical GIS — scalability engineering), **Ruth Mostern** (Pittsburgh — World Historical
Gazetteer → *The Yellow River*, Levenson Prize: the full infrastructure→prize arc), **Richard
White** (Stanford — "What is Spatial History?", spatial visualization as argument). Critical
cartography ground: **J.B. Harley**, "Deconstructing the Map" (1989) — maps as instruments of power.

**DH-at-scale:** **MapReader / Machines Reading Maps** (Katherine McDonough, Lancaster + Turing —
AHA Roy Rosenzweig Prize 2023; the clearest bridge-figure model). **Venice Time Machine** (Frédéric
Kaplan, EPFL) → **Time Machine Europe** (EU Horizon, 200+ institutions) → **UrbanHistory4D**
(Dresden). **EPFL DH Lab** (Isabella Di Lenardo bridges SODUCO + Venice; Rémi Petitpierre). **KG
peers:** **Leon van Wissen** (Amsterdam Time Machine / GLOBALISE — VMA's most direct KG peer),
**Vienna History Wiki**. Standards: **Pelagios / Linked Places**, **ORBIS** (Meeks + Scheidel).

---

## Cluster 4 — Citizen science / HITL at scale

NYPL Building Inspector (proof of concept) → **RapiD** (Meta AI — AI proposes, OSM volunteers
confirm) → **HOT Tasking Manager** (volunteer tile decomposition — the model for VMA's tracing
workflow) → **Zooniverse** (general platform). Data destination: **OpenHistoricalMap** (OSM with a
time dimension — VMA's vectorized footprints could flow here). VMA's HITL loop (theory.md) is
architecturally the RapiD/Building-Inspector model applied to colonial Saigon.

---

## Cluster 5 — Colonial + Vietnamese urban history / planning (the interpretive home)

**Colonial-urbanism canon:** **Gwendolyn Wright**, *Politics of Design in French Colonial Urbanism*
(1991, in library) — the founding text (colonies as planning laboratories). **Paul Rabinow**,
*French Modern* (in library). Eric Jennings (Dalat), Haydon Cherry (*Down and Out in Saigon*),
Nicola Cooper, Ambe Njoh (comparative colonial urbanism → *Planning Perspectives*), Brocheux &
Hémery (the synthesis).

**Vietnam/Saigon-specific (library-heavy):** **Erik Harms** (*Saigon's Edge* 2011; *Luxury and
Rubble* 2016) — ethnography of HCMC's edges. **Huỳnh Thế Du** (*Quy hoạch Sài Gòn–TPHCM 1858–2024*;
also a VMA letter writer). Labbé (peri-urban Hanoi), the JARDCS Saigon–Chợ Lớn morphology paper,
Ly The Dan, Pham, Tran+Kamalipour (informal/formal morphology over time). Primary source in
library: **Annuaire général de l'Indochine** — the trade-directory corpus for the geographical-text-
analysis → KG pipeline (SODUCO did exactly this for Paris).

**Urban morphology vocabulary:** Conzenian school (M.R.G. Conzen → J.W.R. Whitehand: plan units,
street/plot/building) and Italian/Muratorian school (Saverio Muratori → Gianfranco Caniggia:
procedural typology — conceptual base for Morlighem's procedural LoD2).

**Theory canon (07-general-theory):** Lefebvre (*Production of Space*; *Right to the City*), Harvey
(*Social Justice and the City*; *Right to the City*), James C. Scott (*Seeing Like a State* —
legibility), Jacobs, Lynch, Mumford, Foucault (heterotopias), Soja, Ananya Roy (subaltern
urbanism), AbdouMaliq Simone (people as infrastructure). These supply VMA's "soul" reading.

**Planning-school PhD targets (Part III):** Columbia GSAPP — **Felicity Scott** (Architecture PhD;
active Cambodia/Indochina colonial-archive project; "Documenting the Colonial Archive") and **Hiba
Bou Akar** + **Laura Kurgan** (Urban Planning PhD; decolonial planning + Center for Spatial
Research — *Close Up at a Distance* is in library). Also Weiping Wu (GSAPP, East Asia). MIT DUSP:
Bish Sanyal, Lawrence Vale. Harvard GSD: Davis (weaker fit), Mehrotra (monitor).

---

## The gaps (VMA's research contributions)

| # | Gap | What exists (adjacent) | What doesn't | Target venue |
|---|---|---|---|---|
| 1 | **OBIA calibration for French colonial Indochina symbology** | SODUCO (Paris), ETH IKG (Swiss topos), Morlighem (Dutch cadastral) | Any calibration for Indochina color/line/hatching conventions | *Imago Mundi* / IJGIS |
| 2 | **Automated georef of Indian 1960 datum military series** | DL feature-matching (Jerusalem), OCR+geocode (Sanborn), VLM preprints | GCP-propagation over uniform grid + Helmert Indian-1960 correction | ISPRS Annals / CHR |
| 3 | **Geotemporal KG for a SE-Asian colonial city** | Amsterdam TM, Vienna History Wiki, GLOBALISE (VOC) | Any street/building-level KG for a colonial Asian city | DSH / DH conf |
| 4 | **Spatial/GIS methods × colonial Saigon (urban history)** | Shanghai French Concession cadastral GIS (*Transactions in GIS* 2012) | The same for Saigon | *Planning Perspectives* / *Urban History* |

**Library gaps to acquire (cited, not yet in the 167 PDFs):** Thongchai Winichakul, *Siam Mapped*
(geo-body theory — essential for SE-Asian colonial cartography critique); Benedict Anderson,
*Imagined Communities* (census/map/museum as colonial techniques); also worth adding: Cherry *Down
and Out in Saigon*, Brocheux & Hémery *Indochina*, Mostern *The Yellow River* (career-model output).

---

## The career model (the through-line for the SOP)

Every successful bridge figure followed the same two-phase arc: **build the tool the field needs →
use it to make arguments no one could make before.** Peter Bol (CHGIS → Song-history scholarship),
Katherine McDonough (MapReader → AHA prize), Ruth Mostern (World Historical Gazetteer → Levenson
Prize). VMA's founder is in Phase 1 *because the tools for French colonial Indochina don't exist
yet*. The intellectual home is **urban planning & design** (theory.md, field-graph Part III); the
GIS/CV pipeline and the KG are instruments, not ends. Closest method+career fit: **Ian Gregory**
(geographical text analysis on colonial corpora → KG); closest career analogy: **Peter Bol**.
