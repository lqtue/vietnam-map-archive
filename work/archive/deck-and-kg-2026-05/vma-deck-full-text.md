# VMA Talk Deck — Full Text for NotebookLM Slide Generator

**Working title:** Deconstructing the World, Reconstructing the Past — A Method for Historical Maps
**Speaker:** Lê Quang Tuệ — VnExpress, Fulbright MPP, the Vietnam Map Archive project
**Snapshot date:** 2026-05-23 (live database figures pulled this morning)
**Format note:** Sections are H1, slides are H2. Each slide has 3–6 short bullets and one narrative paragraph. Appendices A–E are modular — keep only the ones that match your venue before pasting into NotebookLM.

---

# Section 0 — Open

## [Slide 0.1] Title slide

**Eyebrow:** The Vietnam Map Archive · 2026

- Deconstructing the world
- Reconstructing the past
- A method for historical maps
- Lê Quang Tuệ — VnExpress · Fulbright MPP

**Narrative:** Good morning. My name is Lê Quang Tuệ. I work as a data journalist at VnExpress, and over the past two years I have been building a research infrastructure called the Vietnam Map Archive. Today I want to share a method we have developed for taking historical maps — the densest spatial record we have of past worlds — and turning them into living, queryable, crowdsourceable data.

## [Slide 0.2] Open the archive

**Eyebrow:** Try it now

- PC stable build — vietnammaparchive.github.io/v3-beta/
- Mobile experimental — vmabeta.pages.dev
- Free and open
- No login required to browse

**Narrative:** Before we start, please take out your phones. There are two QR codes here. The one on the left is our stable desktop archive — it works best on a laptop. The one on the right is the experimental mobile build. Anything I show today is live in your hand right now, and I encourage you to interrupt and ask questions about anything you see.

## [Slide 0.3] Who I am

**Eyebrow:** Speaker

- Data journalist · VnExpress
- ~30M monthly readers
- Fulbright MPP graduate
- Ten years of editorial mapping

**Narrative:** I came to this work through journalism, not academia. For ten years I have been making maps for VnExpress, Vietnam's largest daily, reaching about thirty million readers a month. That meant building flood visualisations, population maps, urban-planning explainers. VMA started as a side project — a way to make sense of historical maps the way we make sense of modern data. It has now become research infrastructure for a longer arc.

---

# Section 1 — Premise · The World as Data

## [Slide 1.1] The world has become data

**Eyebrow:** I · Premise

- Continuous deconstruction
- Any place, any moment, queryable
- Satellites · sensors · OSM · IoT
- A six-layer stack

**Narrative:** The first half of the talk is a premise. Without anyone in this room asking for it, the modern world has been continuously deconstructed into data. Satellites pass overhead every few hours. Phones in our pockets emit GPS pings. OSM volunteers trace every new sidewalk. Foundation models compress entire cities into latent vectors. The result is that any place, at any moment, can be queried.

## [Slide 1.2] Any place, any moment, can be queried

**Eyebrow:** I · Premise

- Sensing · satellites, LiDAR, IoT
- Mapping · OSM, Street View, cadastres
- Modelling · foundation models, latent space
- Six layers — from orbit to human story

**Narrative:** When we say the world has become data, we mean a stack of six layers. From above — satellite and LiDAR. Then road networks and building footprints. Then 3D facades and textured meshes. Then points of interest and economic activity. And, at the bottom, the human stories that give those structures meaning. Each layer can be queried independently or composed.

## [Slide 1.3] Even daily journalism runs on this

**Eyebrow:** I · Premise · Evidence from my desk

- VnExpress population density map · 2025
- Cầu river basin flood viz · 2025
- Election turnout, urban heat, road safety
- All built from queryable layers

**Narrative:** This is not abstract. The work I do every week at VnExpress depends on this. When the Cầu river flooded Thái Nguyên last autumn, I built a basin-by-basin visualisation in two days because the elevation model, the rainfall feed, the population grid and the road network were all already there. The world as data is the operating environment of contemporary journalism.

---

# Section 2 — Problem · The Past is Not

## [Slide 2.1] But the past is not

**Eyebrow:** II · Problem

- Pre-satellite era is dark
- Past worlds survive as paper
- Maps are the densest record we have
- Sputnik · 4 October 1957

**Narrative:** Here is where the problem begins. The world has become data, but the past has not. Everything before Sputnik in October 1957, and most places long after, exists only as paper. If we want to understand how Saigon became Ho Chi Minh City — or how any city encoded its inequalities into the built form — we have to deal with the fact that the densest spatial record is a physical map in an archive somewhere in Paris.

## [Slide 2.2] Maps are what we have

**Eyebrow:** II · Problem

- Pre-satellite — paper is all there is
- Sputnik · 7:28 PM, 4 October 1957
- Post-Sputnik — coverage still uneven
- Saigon 1859–1957 — entirely on paper

**Narrative:** The window of historical maps is bounded on one side by what survives in archives and on the other by the launch of Sputnik on 4 October 1957 at 7:28 PM. Even after Sputnik, coverage of places like Saigon stayed thin for decades. The first century of French colonial Saigon — from 1859 to about 1955 — survives almost exclusively on paper. That is our primary corpus.

## [Slide 2.3] History on the head of a pin

**Eyebrow:** II · Problem

- "Historians focus on time"
- "Geographers focus on space"
- History written without place
- White, 2010

**Narrative:** There is a well-known critique from geographers — historians write history as if it happened on the head of a pin. The disciplinary instinct of history is to follow chronology. The disciplinary instinct of geography is to follow place. Most historical writing privileges time over space, partly because the spatial record was, until recently, too expensive to consult. Our project tries to remove that cost.

## [Slide 2.4] Yet historical maps are…

**Eyebrow:** II · Problem · The latent gap

- Not queryable
- Not readable
- Not analysable
- Not enrichable
- Digitized ≠ Digitalized

**Narrative:** Even when historical maps have been scanned and put online, they remain useless to a modern workflow. You cannot search them. You cannot ask them where a school stood in 1893. You cannot stack a second layer of evidence on top. Most digital archives stop at digitisation — pixels on a server. What we need is digitalisation — pixels turned into knowledge.

---

# Section 3 — Question

## [Slide 3.1] The research question

**Eyebrow:** III · Question

- Can we deconstruct the past?
- The way we deconstruct the present?
- Open
- Crowdsourceable

**Narrative:** This brings us to one research question that organises the whole project. Can we retroactively deconstruct the past the way we routinely deconstruct the present, and can we make the result open and crowdsourceable? Every architectural and methodological choice that follows is an answer to this single question.

---

# Section 4 — Lit Review · Who Has Tried

## [Slide 4.1] Adjacent projects

**Eyebrow:** IV · Lit Review

- Allmaps — georef standard + viewer
- SODUCO — Paris OCR + KG
- NYPL Building Inspector — crowd footprints
- histo3d — LoD2 from maps
- ETH IKG — synthetic data + ontology
- CHGIS — long-term GIS for China
- MapSAM2 — segmentation foundation model

**Narrative:** We are not the first to try this. Allmaps, run by Bert Spaan and collaborators, is the global standard for georeferencing historical maps. SODUCO at the French ANR mined directories of Paris 1789–1950. The New York Public Library crowdsourced building footprints from 1850s NYC. Camille Morlighem at TU Delft generates LoD2 city models from historical Dutch maps with extraordinary precision. The ETH cartography group is producing synthetic training data. CHGIS at Harvard, under Peter Bol, built the long-term historical GIS of China. And MapSAM2 is the new foundation model for map segmentation.

## [Slide 4.2] What is still missing

**Eyebrow:** IV · Lit Review · The gaps

- No end-to-end open pipeline
- No Indochina symbology calibration
- No crowdsourcing as method
- No spatial-history infrastructure for SE Asia

**Narrative:** Three gaps remain. First — every project listed solves one stage. None runs a complete open pipeline from raw scan to enriched, queryable corpus. Second — the cartographic tradition that produced Saigon's densest record, French colonial Indochina, has no published symbology calibration. The OBIA colour rules that work for Swiss topographic maps do not transfer. Third — human-in-the-loop review is almost always treated as private quality control, never as a public participation layer that doubles as a community archive.

---

# Section 5 — Method · Four Stages

## [Slide 5.0] Four stages

**Eyebrow:** V · Method

- Input
- Vectorize
- Georectify
- Enrich
- Built on Allmaps · MapSAM2 · IIIF

**Narrative:** Our answer to the research question is a four-stage method. Stage one — Input — open framework plus crowdsourced materials. Stage two — Vectorize — pixels become polygons. Stage three — Georectify — each map placed in modern coordinates. Stage four — Enrich — knowledge graph entries stack onto the geometric base. We did not invent the underlying tools. We composed Allmaps, MapSAM2 and IIIF into a single pipeline.

## [Slide 5.1] Stage one — Input

**Eyebrow:** V · Method · Stage one

- IIIF — open delivery protocol
- Crowdsourced source institutions
- manhhai · Stanford · BnF Gallica · Internet Archive
- David Rumsey · VVA Texas Tech · UT Austin

**Narrative:** Stage one is acquiring the maps. We rely on the IIIF protocol — the international standard that lets museums and libraries serve high-resolution images. Above that, we depend on a network of source institutions, both formal and informal. The BnF Gallica and David Rumsey collections give us the bulk of nineteenth-century material. Stanford and the Vietnam Virtual Archive at Texas Tech contribute mid-century military maps. The Vietnamese collector manhhai has been digitising material that no institution holds.

## [Slide 5.2] Stage one · deep-dive — Self-hosted IIIF

**Eyebrow:** V · Method · Stage one · deep-dive

- iiif.maparchive.vn — our own endpoint
- Cloudflare R2 storage + Worker
- On-the-fly info.json patching
- 62 Service Géographique de l'Indochine cadastres

**Narrative:** When the holding institution does not run a IIIF endpoint, we run our own. We built iiif.maparchive.vn on Cloudflare R2 storage with a Worker that patches info.json metadata on the fly. This let us ingest sixty-two large-format Service Géographique de l'Indochine cadastres from Cartomundi at Aix-Marseille — a partnership made possible because we could host the tiles ourselves at zero marginal cost.

## [Slide 5.3] Stage two — Vectorize

**Eyebrow:** V · Method · Stage two

- Pixels become polygons
- Building footprints, road centrelines, place names
- Foundation model fine-tuned on colonial style
- Human review on every output

**Narrative:** Stage two converts pixels into geometry. A foundation segmentation model identifies building footprints, road centrelines, water bodies and place-name regions. We fine-tune the model on French colonial cartographic style, because the symbology of an 1898 Saigon cadastre is nothing like a modern topographic map. Every machine prediction goes to human review before it enters the corpus.

## [Slide 5.4] Stage two · deep-dive — MapSAM2 with HITL

**Eyebrow:** V · Method · Stage two · deep-dive

- LoRA fine-tune on M1 Mac
- OCR-seeded prompting
- Watershed post-processing
- Review at /contribute/review

**Narrative:** Technically, we use MapSAM2 — Segment Anything Model 2, adapted for maps. We attach a LoRA adapter trained on annotated Indochina sheets, and we seed the prompts with OCR-extracted label positions, which dramatically improves recall. A watershed post-processing step turns probability maps into clean polygons. The output queue surfaces in a dedicated review tool at /contribute/review where any volunteer can approve, reject, or flag a footprint.

## [Slide 5.5] Stage three — Georectify

**Eyebrow:** V · Method · Stage three

- Place each map in modern coordinates
- Allmaps editor for manual GCPs
- Sheet-grid propagation for uniform series
- Output — W3C Georeference Annotation JSON

**Narrative:** Stage three is georeferencing — telling the computer that this corner of an 1893 cadastre corresponds to that point on the WGS84 globe. For one-off maps, contributors place ground control points in the Allmaps editor. For uniform military series like AMS L7014, we propagate from one seed sheet to its neighbours automatically. The output is a W3C standard annotation that any Allmaps-compatible viewer can render.

## [Slide 5.6] Stage three · deep-dive — L7014 propagation

**Eyebrow:** V · Method · Stage three · deep-dive

- Affine fit on seed map GCPs
- Extrapolate using sheet Δlon / Δlat
- No image feature matching
- Vector-to-vector for irregular sheets

**Narrative:** Here is one piece of original method. The US Army's L7014 series covers Vietnam in five hundred regular 1:50,000 sheets. We georeference one sheet manually, fit an affine model to its ground control points, then use the known sheet spacing in degrees of longitude and latitude to predict the corners of every neighbour. No image feature matching is needed — we exploit the regular grid geometry of the military series. For irregular cadastres we fall back to vector-to-vector alignment against modern OSM.

## [Slide 5.7] Stage four — Enrich

**Eyebrow:** V · Method · Stage four

- Stack materials onto the geometric base
- Knowledge graph entries
- Period photographs
- Oral histories, administrative records

**Narrative:** Stage four is where the map becomes more than a map. Once the geometry is locked, we stack semantic materials on top. Each building can be linked to its owner across census years, to a photograph from the 1880s, to an oral history recording from a descendant in California. The georeferenced base is the spine; everything else hangs off it through the knowledge graph.

## [Slide 5.8] Stage four · deep-dive — Provenance-aware KG

**Eyebrow:** V · Method · Stage four · deep-dive

- Every entity, relation, date — cites its source
- ISO 8601 partials — 1905, 1905-03
- Named periods — pre-colonial to reunification
- Nine eras, one schema

**Narrative:** The knowledge graph is built with provenance at the centre. Every entity, every relation, every date carries a citation to the source that supports it. Temporal values are encoded as ISO 8601 partials so we can express "this building was demolished sometime in 1905" without false precision. We have named nine periods of Saigon's history, from pre-colonial through reunification, and every fact is tagged to a period as well as an absolute date.

---

# Section 6 — Demonstration · Chợ Cũ

## [Slide 6.1] One place, four stages

**Eyebrow:** VI · Demonstration

- Chợ Cũ — the old market district
- Walk one place through all four stages
- 1893 cadastre to 2026 satellite
- Method made concrete

**Narrative:** Abstract pipelines are easy to describe and hard to believe. So let me walk one place — Chợ Cũ, the old market district of Saigon — through all four stages of the method. By the end of this section I want you to be able to see exactly what the pipeline produces.

## [Slide 6.2] Plan Cadastral de la Ville de Saigon · 1893

**Eyebrow:** VI · Demonstration · Stage one

- Source — Bibliothèque nationale de France
- IIIF tile pyramid
- 1893 cadastre, full sheet
- The raw input

**Narrative:** This is the input — the 1893 cadastral plan of Saigon, held at the BnF Gallica. We pull it through IIIF tiles at full resolution. At this scale you can see the regular Cartesian grid of the colonial planning regime and the curvilinear remnants of older Vietnamese street patterns at the edges. Everything we do downstream starts from this image.

## [Slide 6.3] Marché Central — cadastre meets aerial view

**Eyebrow:** VI · Demonstration · Stages two and three

- Cadastre · zoomed to Marché Central
- Aerial perspective · c. 1898
- Same place, two registers
- Georef makes them composable

**Narrative:** Now we zoom in to the Marché Central — the old central market. On the left, the cadastre at building-level resolution. On the right, a bird's-eye-view lithograph from about 1898 showing the same block in pictorial perspective. Each is informative alone. Together, once georeferenced, they triangulate building heights, roof types and street widths that neither view records explicitly.

## [Slide 6.4] Materials embedded

**Eyebrow:** VI · Demonstration · Stage four

- Period photograph · Chợ Cũ · 1880s
- Vương Hồng Sển quote
- Knowledge graph tag — "fish porridge corner"
- Each material cites its source

**Narrative:** On top of the geometry we stack materials. A photograph of the market from the 1880s. A line from the chronicler Vương Hồng Sển — "I started to taste fish porridge at Chợ Cũ, hủ tíu noodles at Chợ Mới." Every quotation and image is anchored to a building footprint and carries a citation. The map stops being a flat image and starts being a portal into the lived experience of one block.

## [Slide 6.5] Then and now

**Eyebrow:** VI · Demonstration · Composite

- Hôtel de Ville · 1908
- HCMC People's Committee · 2026
- Same footprint, different regime
- The slider is the pedagogy

**Narrative:** And here is what the public ultimately sees — a then-and-now slider. The Hôtel de Ville of 1908 fades into the People's Committee building of 2026. Same footprint, same plot, two political regimes. The slider is its own pedagogy. Visitors arrive looking for one thing and leave understanding continuity and rupture at a glance.

---

# Section 7 — Crowdsourcing as Method

## [Slide 7.1] Three contributor roles

**Eyebrow:** VII · Community

- Cartographer — trace footprints, target OSM mappers
- Architect — photogrammetry, target architecture students
- Historian — knowledge graph, target diaspora and journalists
- Each role, one tool, one badge

**Narrative:** Volunteers come into VMA through one of three doors. The Cartographer traces building outlines on georeferenced maps; we recruit from the OpenStreetMap community. The Architect adopts a building, runs structure-from-motion photogrammetry, and contributes a 3D mesh; we recruit from architecture schools. The Historian adds entities, citations, family histories and oral records; we recruit from the diaspora, from journalists, from families with attics full of letters.

## [Slide 7.2] Live contribute tools

**Eyebrow:** VII · Community

- /contribute/georef — Allmaps editor
- /contribute/digitalize — triage and OCR review
- /contribute/trace — polygons and lines
- /contribute/review — SAM2 footprint approval

**Narrative:** Each role has a dedicated tool on the site. /contribute/georef runs the Allmaps editor for ground control points. /contribute/digitalize handles triage of new scans and review of OCR extractions. /contribute/trace lets a Cartographer draw polygons and lines on top of any georeferenced map. /contribute/review is where the SAM2 footprint queue gets approved or rejected. All four are open right now — feel free to log in after the talk.

---

# Section 8 — Results · State of the Archive

## [Slide 8.1] The corpus

**Eyebrow:** VIII · Results

- 100 maps ingested
- BnF Gallica · David Rumsey · Internet Archive
- Stanford · UT Austin · Wikimedia Commons
- 62 SGI cadastres self-hosted

**Narrative:** Two years in, the archive holds one hundred maps. They come from the BnF Gallica in Paris, the David Rumsey collection at Stanford, the Internet Archive, the Perry-Castañeda Library at UT Austin, Wikimedia Commons, the IRD's Virtual Saigon project, and our own self-hosted copies of the Service Géographique de l'Indochine cadastres from Cartomundi.

## [Slide 8.2] By the numbers — as of 2026-05-23

**Eyebrow:** VIII · Results · Live snapshot

- 100 maps ingested
- 38 georeferenced
- 62 SGI cadastres self-hosted
- 1,028 OCR extractions
- 46 SAM2 footprints under review
- 11 active volunteers
- 3,373 candidate maps queued

**Narrative:** Here is where the archive stands this morning. One hundred maps ingested. Thirty-eight fully georeferenced. Sixty-two cadastres on our own IIIF endpoint. One thousand and twenty-eight OCR text extractions, with forty-three already human-validated. Forty-six MapSAM2 footprints in the review queue. Eleven active volunteers contributing this month. And a discovery queue — our scout pipeline — of three thousand three hundred and seventy-three candidate maps waiting to be ingested.

## [Slide 8.3] Try it on your phone

**Eyebrow:** VIII · Results

- PC build — vietnammaparchive.github.io/v3-beta/
- Mobile build — vmabeta.pages.dev
- Stop me if anything breaks
- This is live software

**Narrative:** A reminder, mid-deck — everything I have shown so far is live in your hand right now. The PC build runs the full editor. The mobile build is experimental and we are actively breaking and fixing it. Please open one or both. If you find a bug while I am talking, please shout it out — that is exactly the kind of feedback we need.

---

# Section 9 — Reconstruction · The Four Stages at City Scale

## [Slide 9.1] The four stages, at city scale

**Eyebrow:** IX · Reconstruction

- Same four stages
- Scaled across four layers of representation
- From one georeferenced sheet to a 4D past
- Not new vocabulary — same method, more layers

**Narrative:** Looking forward — the same four stages that handle one map can be scaled up to reconstruct an entire city through time. We deliberately reuse the same vocabulary so the audience does not have to learn a new mental model. What changes is the layer of representation, not the method.

## [Slide 9.2] From one map to a 4D past

**Eyebrow:** IX · Reconstruction

- Phase I — Geometric Foundation — the map
- Phase II — Semantic Core — the knowledge graph
- Phase III — Visual Validation — the photographs
- Phase IV — Neural Reconstruction — the 3D world

**Narrative:** Phase one is the geometric foundation — the georeferenced map. Phase two is the semantic core — the knowledge graph that names every entity in that geometry. Phase three is visual validation — period photographs re-projected onto the geometry using a method called SemPinPnP. Phase four is neural reconstruction — generating the 3D scenes that fill in what no single source records. End to end, the output is a four-dimensional digital twin of a past city.

## [Slide 9.3] The method generalises

**Eyebrow:** IX · Reconstruction · Portability

- Saigon today
- Hanoi tomorrow
- Angkor next
- Any place with a paper trail

**Narrative:** Nothing in this method is specific to Saigon. The four stages apply to any city for which we have a paper trail — Hanoi, Phnom Penh, Vientiane, Angkor, Yangon. Each new tradition needs a symbology calibration in stage two, but the architecture transfers. The long-term ambition is a method that any historical-mapping community in Southeast Asia can adopt.

---

# Section 10 — Discussion

## [Slide 10.1] What this work leaves behind

**Eyebrow:** X · Discussion · Contributions

- Technical — open end-to-end pipeline
- Technical — first calibration for Indochina symbology
- Technical — crowdsourcing as native layer
- Epistemological — "ground truth" is negotiated
- Epistemological — every reconstruction inherits a view of space

**Narrative:** The contributions split in two. Technically — we contribute the first open end-to-end pipeline from scan to enriched corpus, the first published calibration for French colonial Indochina symbology, and a crowdsourcing model where public participation is a first-class architectural element. Epistemologically — we contribute the observation that "ground truth" in historical reconstruction is never given. It is negotiated, and every reconstructed past inherits a particular perception of space.

## [Slide 10.2] Whose space?

**Eyebrow:** X · Discussion

- Colonial cadastre — absolute, Cartesian, metric
- Sinitic landscape — relative, narrative, embodied
- Two ontologies of space
- The reconstruction inherits whichever we choose

**Narrative:** Here is the open question we want to leave you with. Colonial cadastres encode absolute space — Cartesian, metric, owned. Vietnamese and Sinitic landscape maps encode relative space — relational, narrative, embodied. When we build a digital twin of past Saigon, we are forced to pick a coordinate system. We have, so far, picked the colonial one, because it is the one our modern tools speak. We do not yet know what it would take to reconstruct a past in relative space, but we think the question matters.

---

# Section 11 — Close

## [Slide 11.1] Thank you

**Eyebrow:** XI · Close

- Thank you
- Questions?
- Open the archive — try it
- vietnammaparchive.github.io/v3-beta/

**Narrative:** Thank you for your time. I am here for the rest of the day and very happy to talk about any piece of this — the technical pipeline, the OBIA calibration, the knowledge graph schema, the PhD arc this is leading toward, or just where to find good cháo cá in Chợ Cũ today. Please come find me.

## [Slide 11.2] Contact

**Eyebrow:** Contact

- Lê Quang Tuệ
- VnExpress · the Vietnam Map Archive
- facebook.com/deartue
- lqtue.vn@gmail.com
- vietnammaparchive.github.io/v3-beta/

**Narrative:** All my contact details are on this slide. The fastest way to reach me is Facebook Messenger; email is also fine. If you would like to volunteer, the contribute pages link directly from the home page. If you are at an institution that would like to deposit a collection through our self-hosted IIIF endpoint, please get in touch and we will set it up.

---

# Appendix A — For Funders and Partners

> Use this appendix when speaking to grant agencies, foundations, IIIF-Consortium prospects, or institutional partners considering a deposit.

## [Slide A.1] Why funding matters now

**Eyebrow:** A · Funders

- Pipeline is working — 100 maps, 38 georeferenced
- Bottleneck is human-in-the-loop review, not technology
- Next 24 months — scale from 100 to 1,000 maps
- Need annotation labour and compute, not engineering

**Narrative:** The technical pipeline works. The bottleneck right now is human time. Forty-six SAM2 footprints sit in review queues because we have eleven volunteers and three thousand maps waiting to come in. The funding ask is not for more engineering — it is for the human labour to keep the pipeline moving and for the compute to fine-tune models on each new cartographic tradition.

## [Slide A.2] 24-month budget envelope

**Eyebrow:** A · Funders

- $42K — annotation lead, part-time
- $18K — GPU credits for MapSAM2 retraining
- $9K — Cloudflare R2 and Worker compute
- $15K — community programs and OSM partnership
- $12K — fellowships for student contributors
- $96K total over 24 months

**Narrative:** We have scoped a twenty-four-month budget at ninety-six thousand US dollars. The largest line is a part-time annotation lead at forty-two thousand. Eighteen thousand for GPU credits to fine-tune MapSAM2 on each new cartographic tradition we ingest. Nine thousand for hosting. Fifteen thousand for community programmes — workshops, OSM partnership, the photogrammetry events. Twelve thousand in fellowships for student Cartographers and Historians.

## [Slide A.3] Comparables in funding context

**Eyebrow:** A · Funders

- SODUCO — €1.2M ANR grant, 2020–2024
- NYPL Building Inspector — Knight Foundation seed
- histo3d — TU Delft internal + EU Horizon
- VMA target — $96K matches Knight-tier seed

**Narrative:** For context — SODUCO ran on a 1.2 million euro ANR grant. The NYPL Building Inspector started on a Knight Foundation seed. Morlighem's histo3d was funded internally by TU Delft and an EU Horizon grant. Our ninety-six-thousand-dollar ask is the size of a Knight or Mellon seed grant, which is appropriate for a project that has already shipped a working pipeline.

## [Slide A.4] The four asks

**Eyebrow:** A · Funders

- GPU credits — AWS / GCP research credits, 50K hours
- Annotation lead — part-time, 18 months
- R2 storage — Cloudflare partnership, 5TB
- OSM partnership — joint mapping events in Saigon

**Narrative:** Four specific asks. First — fifty thousand GPU hours of research credits from AWS, GCP, or a similar programme. Second — funding for a part-time annotation lead for eighteen months. Third — a Cloudflare R2 storage partnership for five terabytes. Fourth — a memorandum with HOT-OSM or the local Saigon OSM community for joint mapping events on top of our georeferenced corpus.

## [Slide A.5] Partnership ladder

**Eyebrow:** A · Funders

- Depositor — give us a collection to host
- Sponsor — fund a contributor cohort
- Co-author — joint paper or exhibition
- Co-PI — multi-year research grant

**Narrative:** Four rungs on the partnership ladder, from light to heavy. Depositor — institutions that have scans we can ingest. Sponsor — funders of one volunteer cohort. Co-author — partners on a paper or exhibition that uses VMA data. Co-PI — institutional partners on a multi-year research grant. Each rung is a real conversation we are open to having today.

---

# Appendix B — For the Allmaps and IIIF Community

> Use this appendix when speaking to the Allmaps team, IIIF Consortium members, or other historical-mapping toolmakers.

## [Slide B.1] Where VMA extends Allmaps

**Eyebrow:** B · Allmaps / IIIF

- Self-hosted IIIF at production scale
- Bulk ingest pipeline
- Multiple IIIF sources per map record
- Lookup by Allmaps image ID
- Dublin Core metadata layer

**Narrative:** VMA is built on Allmaps. We want to share back five concrete extensions we have made. First — a production-grade self-hosted IIIF endpoint on Cloudflare R2. Second — a bulk ingest pipeline that takes a list of source URLs and walks them through IIIF derivation, info.json patching and Allmaps annotation. Third — a database schema that supports multiple IIIF sources per logical map record. Fourth — fast lookup by Allmaps image ID. Fifth — a Dublin Core metadata layer on top of the geographic data.

## [Slide B.2] Self-hosted IIIF — what we learned

**Eyebrow:** B · Allmaps / IIIF

- vips dzsave needs info.json patching
- Workers can patch on the fly
- R2 + Worker cheaper than dedicated IIIF servers
- One annotation server can mirror to R2

**Narrative:** The single biggest practical lesson — vips dzsave produces tile pyramids that almost work as IIIF but need an info.json shim. We built a Cloudflare Worker that patches the info.json on every request, which costs us pennies per month per collection. For any small archive that wants to be IIIF-compliant without running a dedicated server, this pattern works.

## [Slide B.3] Multi-source per map

**Eyebrow:** B · Allmaps / IIIF

- map_iiif_sources table
- one primary, many alternates
- supports mirror-to-R2 workflow
- preserves provenance back to original

**Narrative:** Often a map exists in three places — the holding institution's IIIF endpoint, the Allmaps mirror, and our own R2 copy. We model this with a map_iiif_sources table — one logical map, many IIIF source URLs, exactly one flagged as primary. This lets us mirror to R2 for performance without ever losing the link back to the original holder.

## [Slide B.4] Where we would love to collaborate

**Eyebrow:** B · Allmaps / IIIF

- Annotation review API standard
- Batch georef interchange format
- Footprint trace interchange
- Shared symbology dictionary

**Narrative:** Four things we would love to develop with the Allmaps community. A standardised review API so HITL queues can be portable. A batch georef interchange format for uniform map series like L7014. A footprint trace interchange so what NYPL Building Inspector produces can flow into Allmaps and vice versa. And a shared, versioned symbology dictionary keyed by cartographic tradition.

## [Slide B.5] Concrete CTAs

**Eyebrow:** B · Allmaps / IIIF

- Adopt our R2 + Worker IIIF pattern — code is open
- Join us on review API draft
- Pull our SGI cadastre annotations into Allmaps
- Co-author a paper on bulk georef at scale

**Narrative:** Four concrete things you can do today. Adopt our R2-plus-Worker IIIF pattern — the code is on GitHub. Join us in drafting an annotation review API. Pull the sixty-two SGI cadastre annotations we have produced into the main Allmaps index. And — speaking from the journalist hat — co-author a paper with us on bulk georef at scale, because no one has published clean numbers on this yet.

---

# Appendix C — For PhD and Academic Audiences

> Use this appendix at GSAPP, EFEO, ICOMOS, or any PhD admissions / academic audience.

## [Slide C.1] VMA as research apparatus

**Eyebrow:** C · PhD framing

- VMA is the apparatus, not the dissertation
- Dissertation — spatial history of Saigon urban planning
- Apparatus enables empirical claims about colonial spatial inequality
- Modelled on CHGIS / SODUCO

**Narrative:** I want to be precise about one thing. VMA is not the PhD. VMA is the research apparatus that the PhD depends on. The dissertation itself is a spatial history of Saigon urban planning from 1859 to the present, and its empirical claims about colonial spatial inequality are only credible because the apparatus underneath produces georeferenced, source-cited evidence at scale. The model here is Peter Bol's CHGIS at Harvard and SODUCO at the French ANR.

## [Slide C.2] The long arc — 1859 to present

**Eyebrow:** C · PhD framing

- 1859–1954 — French colonial regime
- 1955–1975 — Republican period, US-supported
- 1975–1986 — central planning under reunification
- 1986–present — Đổi Mới and market reform
- Four regimes, one city, traceable inequalities

**Narrative:** The dissertation argues that Saigon's contemporary spatial inequalities are legible in the built form as a stack of four planning regimes — French colonial, Republican, central-planning, and Đổi Mới. Each regime encoded a particular logic of inequality into the urban fabric, and each subsequent regime inherited and renegotiated those choices. The georeferenced corpus is what makes this argument concrete instead of allegorical.

## [Slide C.3] Climate adaptation as the binding question

**Eyebrow:** C · PhD framing

- HCMC is sinking — 2-5cm / year in parts
- 2050 projections — major flooding under low-warming scenarios
- Climate-adaptive planning requires historical baselines
- Where was a canal in 1893? Why was it filled in 1965?

**Narrative:** The binding contemporary question is climate. Parts of Ho Chi Minh City are subsiding two to five centimetres a year. Without historical baselines — where the canals were, why they were filled, who lived in the floodplain in each regime — climate-adaptive planning will repeat the failures of every prior regime. The dissertation is, ultimately, a tool for asking what a just climate-adaptive urbanism would look like for this city.

## [Slide C.4] Field positioning

**Eyebrow:** C · PhD framing

- Peter Bol / CHGIS — long-term HGIS, China
- SODUCO / Paris — directories and OCR
- Felicity Scott, GSAPP — Cambodia/Indochina colonial archives
- Hiba Bou Akar, GSAPP — post-conflict cities
- Ian Gregory, Lancaster — geographical text analysis

**Narrative:** The dissertation sits at the intersection of five conversations. Peter Bol's CHGIS provides the methodological model for long-term historical GIS. SODUCO offers the closest analogue to our pipeline. Felicity Scott at GSAPP has been working with Cambodia and Indochina colonial archives. Hiba Bou Akar, also at GSAPP, theorises post-conflict urbanism. Ian Gregory at Lancaster pioneered geographical text analysis, which is how we plan to mine the Annuaires de l'Indochine for the knowledge graph.

## [Slide C.5] Why now

**Eyebrow:** C · PhD framing

- Allmaps, MapSAM2 mature in last 24 months
- IIIF adoption near-universal in major archives
- LLMs make OCR of nineteenth-century French viable
- All preconditions in place for the first time

**Narrative:** A version of this PhD could not have been written even three years ago. Allmaps stabilised. MapSAM2 emerged. IIIF adoption became near-universal in the major archives we depend on. And large language models made OCR of nineteenth-century French print finally viable. Every precondition is in place, and the window to do this work cleanly is now.

## [Slide C.6] Letter writer slate

**Eyebrow:** C · PhD framing

- Bert Spaan — Allmaps lead, technical sponsor
- Camille Morlighem — TU Delft, methodological peer
- Hugo Ledoux — TU Delft, 3D geoinformation
- Felicity Scott / Hiba Bou Akar — GSAPP, regional and theoretical
- Senior Vietnamese historian — to be confirmed

**Narrative:** The letter-writer slate, for the academic audience — we are in conversation with Bert Spaan of Allmaps for the technical letter, Camille Morlighem and Hugo Ledoux at TU Delft on the methodological side, Felicity Scott or Hiba Bou Akar at GSAPP for the regional-theoretical letter, and a senior Vietnamese historian whom we will confirm before the application window closes.

---

# Appendix D — For OpenStreetMap and Crowdsourcing Audiences

> Use this appendix at OSM meetups, HOT events, or community-mapping conferences.

## [Slide D.1] The Cartographer track

**Eyebrow:** D · OSM

- One role — trace building outlines
- Tool — /contribute/trace
- Input — georeferenced colonial cadastres
- Output — polygons that can be exported to OSM

**Narrative:** For the OSM community specifically, there is one role and one tool. The role is Cartographer. The tool is /contribute/trace. You see a georeferenced colonial cadastre overlaid on a modern basemap; you trace the building footprints that match the historical layer. The output is clean polygon geometry that can be exported in OSM-compatible formats.

## [Slide D.2] Onboarding flow

**Eyebrow:** D · OSM

- Sign in with GitHub or email
- Pick a map from the queue
- Trace 5 buildings to qualify
- Reviewed footprints become public

**Narrative:** The onboarding takes about ten minutes. Sign in with GitHub or email. Pick a map from the assignment queue — we prioritise sheets that are partly done so you finish in one sitting. Trace your first five buildings; the system surfaces them for senior-volunteer review, and once you have five approved, you graduate to direct publishing.

## [Slide D.3] Recognition and provenance

**Eyebrow:** D · OSM

- Every traced footprint cites the tracer
- Public leaderboard
- Contributions exportable as a portfolio
- License — CC-BY for trace data

**Narrative:** Two principles. Recognition — every traced footprint carries the username of the tracer in its metadata, and the public leaderboard surfaces individual contributions. Provenance — your trace history is exportable as a portfolio you can show on a CV. Licensing — all trace data ships CC-BY, compatible with OSM's ODbL after the standard relicensing path.

## [Slide D.4] Call to action

**Eyebrow:** D · OSM · CTA

- /contribute/trace — open right now
- Saigon 1893 cadastre — first target
- OSM Saigon meetup — monthly, please join
- contact lqtue.vn@gmail.com for partnership

**Narrative:** Open /contribute/trace tonight. Our first target is the 1893 Saigon cadastre — about four thousand buildings on a regular grid, perfect for first-time tracers. Saigon's OSM chapter meets monthly and would welcome more participants. If you would like to organise a mapathon in your city around colonial cadastres we host, please email and we will set up a dedicated queue.

---

# Appendix E — The Six-Layer Data Stack

> Use this appendix at museum, theory, or design-school audiences who need conceptual scaffolding.

## [Slide E.1] The world model has six layers

**Eyebrow:** E · 6-layer stack

- Modern world is a stack of six layers
- We reconstruct each layer backwards in time
- Lower layers depend on higher layers
- VMA is climbing the stack

**Narrative:** A useful conceptual frame — the modern data-driven world is built as a stack of six layers, from satellite imagery at the top down to human stories at the bottom. Our project, taken at its full ambition, rebuilds each of those layers backwards in time. Each lower layer depends on the geometry of the one above, so we have to climb the stack in order.

## [Slide E.2] Layer one and two — geometry from above

**Eyebrow:** E · 6-layer stack

- L1 — macro signal · historical maps as our "satellite"
- L2 — LiDAR equivalent · LoD1 city mass from period photos
- L1 status — 35% complete
- L2 status — 5%, mostly pilot work

**Narrative:** Layer one is the macro signal — what satellites give us today, historical maps give us for the pre-satellite era. We are about thirty-five percent of the way through. Layer two is LiDAR — the building-height envelope. For history, we infer LoD1 city mass from period photographs and panoramas, particularly the 1882 and 1898 panoramas of Saigon. That layer is around five percent.

## [Slide E.3] Layers three and four — facade and form

**Eyebrow:** E · 6-layer stack

- L3 — road network and facade rhythm
- L4 — building-by-building LoD3 mesh
- Source — archival photographs
- Method — Morlighem 2021 pipeline adapted

**Narrative:** Layer three is the road network and the facade rhythm — what Street View captures today, archival photos capture for past decades. Layer four is the building-by-building LoD3 mesh — what photogrammetry produces today, structure-from-motion on archival photographs can produce for the past. We follow Camille Morlighem's 2021 pipeline as the template here.

## [Slide E.4] Layers five and six — semantic and human

**Eyebrow:** E · 6-layer stack

- L5 — points of interest and economic activity
- L6 — human interaction, oral history, community memory
- KG is the spine of L5–L6
- L5 — 10%, L6 — 20% with story-mode contributors

**Narrative:** Layer five is the semantic layer — names, owners, economic activity. The knowledge graph is the data spine here. Layer six is the human layer — oral histories, community memory, lived experience. This is where our story-mode contributors come in. We are about ten percent on layer five and around twenty percent on layer six, because the story tools shipped before the deep technical layers were ready.

## [Slide E.5] Why the stack matters

**Eyebrow:** E · 6-layer stack

- Each layer requires the one above it
- L1 (georef) is the precondition for everything
- The stack tells you what to build next
- It also tells the audience what is missing

**Narrative:** The reason to teach the stack is that it tells you what to build next, and it tells the audience what is missing. We cannot do photogrammetry without footprints. We cannot do footprints without georeferencing. The stack gives the project a roadmap and gives the audience a way to see why we make the priorities we do.

---

**End of full deck.** Total slide count — approximately 57 slides (32 core + 25 across the five modular appendices).

Before pasting into NotebookLM, decide which appendices to include. For a general-public conference talk, keep only the core (Sections 0–11). For a funder meeting, add Appendix A. For an Allmaps / IIIF community talk, add Appendix B. For a PhD admissions presentation, add Appendix C. For an OSM event, add Appendix D. For a theory or museum audience, add Appendix E. Live numbers in Slide 8.2 are accurate as of 2026-05-23; re-pull from Supabase before each talk.
