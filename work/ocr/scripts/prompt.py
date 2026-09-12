"""Versioned prompt strings and JSON schema for the OCR pipeline.

CANONICAL COORDINATE CONTRACT
-----------------------------
Gemini `bbox_px` is 0–1000 normalized *per frame* (0,0 = top-left, 1000,1000 =
bottom-right of the tile it was read in). This is the ONE space every prompt
here must state and every model call assumes; `ocr.py:_to_global` converts it
to full-image source pixels by treating render_w/h as 1000. All prompt versions
(V1–V8) now say 0–1000 — earlier V1–V3 mistakenly said "pixels" and were
corrected. SCOUT uses the same 0–1000 space but at full-map scale (its own
inline scaling in ocr.py, not _to_global).

NOT this space: `local_vision.py` (detect_legend_boxes / spot_numerals) returns
raw source-image pixels — a separate, legitimate space for the local tools; the
`numerals` / `detect-layout` subcommands convert those directly, never via the
0–1000 path. Don't feed local_vision boxes through _to_global.
"""

import copy

# ── JSON schema ───────────────────────────────────────────────────────────────

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "extractions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "street",
                            "place",
                            "building",
                            "institution",
                            "hydrology",
                            "legend",
                            "title",
                            "other",
                        ],
                    },
                    "language": {
                        "type": "string",
                        "enum": ["fr", "vi", "zh", "mixed", "other"],
                    },
                    "bbox_px": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 4,
                        "maxItems": 4,
                        "description": "[x, y, width, height] in 0-1000 normalized coordinates (0,0 = top-left, 1000,1000 = bottom-right)",
                    },
                    "rotation_deg": {
                        "type": "number",
                        "description": "Baseline angle in degrees (0 = horizontal, positive = counter-clockwise)",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    "notes": {"type": "string"},
                },
                "required": [
                    "text",
                    "category",
                    "language",
                    "bbox_px",
                    "rotation_deg",
                    "confidence",
                ],
            },
        }
    },
    "required": ["extractions"],
}

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert in the cartography and toponymy of southern Vietnam, across both the \
French colonial period and the mid-twentieth-century Vietnamese one.

The images you receive are crops from one historical map sheet of Saigon / Ho Chi Minh City \
or another Vietnamese city. The sheet may be French-language (colonial cadastral plans and \
city plans, c. 1860-1954), Vietnamese-language (quốc ngữ, c. 1955 onward), or mixed. Do not \
assume a language or a period: read what is printed on this sheet.

Typical text you will encounter:
- French street names: "Rue de ...", "Boulevard ...", "Quai de ...", "Avenue ..."
- Vietnamese street names: "Đường ...", "Bến ...", "Đại lộ ...", "Công trường ..."
- Quarter / district / village names: "Quartier de l'Inspection", "Village Annamite de ...", \
"Quận ...", "Phường ...", "Xã ..."
- Institutional labels: "Abattoir", "Hôpital", "Pagode", "Caserne", "Cathédrale", "Palais", \
"Bệnh viện", "Chợ", "Trường", "Nhà thờ", "Chùa"
- Building labels: "Mairie", "Direction de l'Intérieur", "Résidence", "Dinh ...", "Toà ..."
- Hydrology: "Arroyo de ...", "Rach ...", "Rạch ...", "Kinh ...", "Sông ..."
- Parcel numbers: bare integers (classify as "other")
- Legend / cartouche text: colour key, scale bar labels, map title, date, cartographer credit

**Diacritics are part of the text, not decoration.** Transcribe French accents \
(é è ê ç î ô û) and Vietnamese vowel and tone marks (ă â đ ê ô ơ ư plus the five tones) \
exactly as printed, in upper case as well as lower: "CHÂTEAU" is not "CHATEAU", "ĐƯỜNG" is \
not "DUONG", "MARCHÉ" is not "MARCHE". Drop a mark only where the print carries none.

Labels may be rotated to follow street axes. Ink may be faded or slightly blurred.
"""

# ── User prompt V1 ────────────────────────────────────────────────────────────

PROMPT_V1 = """\
Examine the map tile image provided and extract every readable text label.

For each text region:
1. Transcribe the text exactly as it appears (preserve accents, capitalisation).
2. Assign the most appropriate category.
3. Note the language.
4. Provide bbox_px as [x, y, width, height] in 0–1000 normalized scale \
(0,0 = top-left, 1000,1000 = bottom-right of this tile).
5. Estimate rotation_deg: the angle of the text baseline from horizontal \
(0 = left-to-right horizontal; positive = counter-clockwise). Most street labels \
follow the road angle.
6. Set confidence between 0 and 1 (0 = completely unreadable, 1 = perfectly clear).
7. Add an optional notes field for observations like "faded", "partially cut off", \
"possibly misspelled", or historical context.

Return ONLY the JSON object matching the schema. Do not include commentary outside the JSON.
If no text is visible, return {"extractions": []}.
"""

# ── User prompt V2 — grouping fix ─────────────────────────────────────────────
# Key change: street names on diagonal roads appear word-by-word along the axis.
# V2 explicitly instructs the model to treat them as ONE extraction.

PROMPT_V2 = """\
Examine the map tile image provided and extract every readable text label.

**Grouping rule (critical):** Words that belong to the same label MUST be returned \
as a single extraction, even if they are spread apart along a road axis or wrapped \
across multiple lines. For example, "Boulevard" and "Charner" printed along a diagonal \
street are ONE extraction: {"text": "Boulevard Charner", "bbox_px": [x, y, w, h]} \
where the bbox is the tightest rectangle enclosing all the words together. \
Similarly "Rue", "de", "Genouilly" → one entry: "Rue de Genouilly". \
Only split into separate extractions if the words clearly belong to different labels \
(e.g. two different streets, or a street name and a building name in the same area).

For each text region:
1. Transcribe the complete label text in reading order (preserve accents, capitalisation).
2. Assign the most appropriate category.
3. Note the language.
4. Provide bbox_px as [x, y, width, height] in 0–1000 normalized scale \
(0,0 = top-left, 1000,1000 = bottom-right; enclosing ALL words of the label).
5. Estimate rotation_deg: the angle of the text baseline from horizontal \
(0 = left-to-right horizontal; positive = counter-clockwise). Most street labels \
follow the road angle.
6. Set confidence between 0 and 1.
7. Add an optional notes field for observations like "faded", "partially cut off at tile edge", \
"continues outside tile", or historical context.

If a label is partially cut off at the tile edge, still extract it and note "cut off at [edge] edge".
If no text is visible, return {"extractions": []}.
Return ONLY the JSON object. Do not include commentary outside the JSON.
"""

# ── User prompt V3 — diagonal axis scan ───────────────────────────────────────
# Key addition: explicit "scan along the road axis" instruction for diagonal names.

PROMPT_V3 = """\
Examine the map tile image provided and extract every readable text label.

**How street names work on this map (critical):**
Street names like "Rue de Genouilly" or "Boulevard Charner" are printed \
word-by-word along the road centreline, following the road's diagonal angle. \
The words are spread apart — separated by 50–300 pixels of blank space — \
but they form ONE label. Here is how to find them:

1. When you spot any word that looks like part of a street name — "Rue", "Boulevard", \
"Quai", "Passage", or any French proper noun — identify its angle (e.g. -45°).
2. Scan along that same angle in both directions within the tile, up to ~400 pixels, \
to find all other words/syllables belonging to the same label.
3. Group every fragment on that axis into a SINGLE extraction. The bbox must enclose \
ALL the fragments — it will be an elongated rectangle following the road axis.
4. The text field must contain the full assembled label in reading order.

**Grouping rules for all label types:**
- Words on the same road axis at the same angle = ONE extraction.
- A building/institution name printed in 2–3 lines inside a parcel = ONE extraction \
(bbox encloses all lines).
- Only create separate extractions for labels that genuinely belong to different roads \
or buildings — even if they are spatially close.
- Short connector words ("de", "du", "de la") must be included in the parent label, \
NOT extracted as standalone items.

**Edge handling:**
- If a label is cut off at the tile edge, include the visible words and add a note: \
"continues outside [left/right/top/bottom] edge".

**What to SKIP (do not extract):**
- Bare parcel numbers (lone integers like "18", "42", "N°7") — category "other" only if part of a larger label.
- Single letters or syllables that are clearly decoration or wear artifacts.
- Any text you are less than 0.5 confident about — omit it entirely rather than guessing.

**For each label:**
1. Full assembled text in reading order (preserve accents, capitalisation).
2. Category: street | place | building | institution | legend | title | other
3. Language: fr | vi | zh | other
4. bbox_px: [x, y, width, height] enclosing ALL words, 0–1000 normalized scale.
5. rotation_deg: baseline angle from horizontal (positive = counter-clockwise).
6. confidence: 0.5–1.0 (only include labels you are at least 50% confident about).
7. notes: optional observations.

Return ONLY the JSON object. If no text is visible, return {"extractions": []}.
"""

PROMPT_V4 = """\
Examine the map tile image provided and extract every readable text label.

**How street names work on this map (critical):**
Street names like "Rue de Genouilly" or "Boulevard Charner" are printed word-by-word \
along the road centreline, following the road's diagonal angle. Words are separated by \
50–400 pixels of blank space but form ONE label. Rules:

1. When you spot any word suggesting a street name — "Rue", "Boulevard", "Quai", \
"Passage", or any French proper noun — identify its angle (e.g. −45°).
2. Scan along that SAME angle in both directions across the ENTIRE tile — \
from one edge to the other — to collect all words/syllables on that road axis.
3. Group ALL fragments into a SINGLE extraction. The bbox MUST enclose every fragment: \
for a diagonal street it will be a large elongated rectangle.
4. If a street name begins or ends outside the tile edge, include the visible words \
and note "continues outside [edge] edge".

**Grouping rules for all label types:**
- Same road axis + same angle = ONE extraction, no matter how far apart the words are.
- A multi-line building/institution name inside one parcel = ONE extraction.
- Separate extractions only for labels that genuinely belong to different roads or buildings.
- Short connectors ("de", "du", "de la") belong to the parent label — never standalone.

**What to skip:**
- Bare integers (parcel numbers like "18", "N°7") — skip entirely.
- Single stray letters that are clearly wear artifacts.
- Fragments so faded you cannot read any letter — skip.

**For each label:**
1. Full assembled text in reading order (preserve accents, capitalisation).
2. Category: street | place | building | institution | legend | title | other
3. Language: fr | vi | zh | other
4. bbox_px: [x, y, width, height] enclosing ALL words of the label (0–1000 scale \
where 0,0 is top-left and 1000,1000 is bottom-right of this tile image).
5. rotation_deg: baseline angle from horizontal (positive = counter-clockwise).
6. confidence: 0.0–1.0. Include everything you can read — the pipeline will filter.
7. notes: "continues outside [edge] edge", "faded", "possibly misspelled", etc.

Return ONLY the JSON object. If no text is visible, return {"extractions": []}.
"""


# ── User prompt V5 — taxonomy and noise filtering ───────────────────────────
# Key changes from V4:
#   1. Added 'hydrology' category for canals (Rach), rivers, and arroyos.
#   2. Explicitly skip library/archival stamps (e.g. Bibliothèque Nationale).
#   3. Instruction to expand common abbreviations (Vge -> Village, R. -> Rue).
#   4. Improved instruction for diagonal rotation and elongated bboxes.

PROMPT_V5 = """\
Examine the map tile image provided and extract every readable text label.

**How street names work on this map (critical):**
Street names like "Rue de Genouilly" or "Boulevard Charner" are printed word-by-word \
along the road centreline, following the road's diagonal angle. Words are separated by \
50–400 pixels of blank space but form ONE label. Rules:

1. When you spot any word suggesting a street name — "Rue", "Boulevard", "Quai", \
"Passage", or any French proper noun — identify its angle (e.g. −45°).
2. Scan along that SAME angle in both directions across the ENTIRE tile — \
from one edge to the other — to collect all words/syllables on that road axis.
3. Group ALL fragments into a SINGLE extraction. The bbox MUST enclose every fragment: \
for a diagonal street it will be a large elongated rectangle.
4. If a street name begins or ends outside the tile edge, include the visible words \
and note "continues outside [edge] edge".

**Classification Rules:**
- **hydrology**: Names of canals (Rach), rivers (Rivière), and arroyos (e.g. "Arroyo de l'Avalanche").
- **street**: Names of roads, boulevards, quais, and passages.
- **institution**: Public or private institutions (e.g. "Abattoir", "Poste de Police", "Cathédrale").
- **building**: Individual building names (e.g. "Hôtel du Gouverneur").
- **place**: Village names (often "Vge de ..."), quarters, or districts.
- **legend / title**: Map boilerplate, scale bars, cartographer credits, or large titles.
- **other**: Anything else that is relevant text but doesn't fit the above.

**Important Normalization:**
- Expand common abbreviations: "Vge de" → "Village de", "R." → "Rue", "Pce" → "Place".
- Preserve French accents and proper capitalization (e.g. "Cochinchine Française").

**What to skip (Noise Filtering):**
1. **Library/Archival Stamps**: Ignore modern stamps from national libraries (e.g. "BIBLIOTHÈQUE NATLE", "SOCIÉTÉ DE GÉOGRAPHIE").
2. **Handwritten Annotations**: Ignore contemporary archival marks, inventory numbers (e.g. "A1005"), or signatures not part of the original map.
3. **Bare integers**: Skip parcel numbers (lone integers like "18", "42", "N°7").

**For each label:**
1. text: Full normalized text in reading order.
2. category: street | hydrology | place | building | institution | legend | title | other
3. language: fr | vi | zh | other
4. bbox_px: [x, y, width, height] (0–1000 scale where 0,0 is top-left and 1000,1000 is bottom-right).
5. rotation_deg: baseline angle from horizontal (positive = counter-clockwise).
6. confidence: 0.0–1.0. Include everything you can read.
7. notes: any relevant observations (e.g. "faded", "continues outside edge").

Return ONLY the JSON object. If no text is visible, return {"extractions": []}.
"""

# The layout vocabulary. `sheet` is the whole printed object and `main_map` the
# cartographic body inside it — they differ by exactly the furniture, which is
# the point: tiling the sheet reads the legend as if it were terrain.
LAYOUT_CATEGORIES = [
    "sheet", "main_map", "title", "legend", "name_list",
    "inset", "scale_bar", "north_arrow", "stamp",
]

SCOUT_SCHEMA = {
    "type": "object",
    "properties": {
        "map_content_bbox": {
            "type": "array",
            "items": {"type": "number"},
            "description": "The [x, y, width, height] of the actual map content area (neatline), excluding white margins and archival stamps. 0-1000 normalized scale."
        },
        "cartouche_bbox": {
            "type": "array",
            "items": {"type": "number"},
            "description": "The [x, y, width, height] of the cartouche / title block. 0-1000 normalized scale. Omit if not present."
        },
        "regions": {
            "type": "array",
            "description": (
                "Layout of the sheet: one entry per distinct area. A sheet is not one "
                "thing, and each of these areas wants a different pass — the main map is "
                "tiled and read at full resolution, a legend is one structured call, "
                "furniture is skipped entirely."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": LAYOUT_CATEGORIES},
                    "bbox": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "[x, y, width, height] on the 0-1000 normalized scale.",
                    },
                    "confidence": {"type": "number"},
                    "notes": {"type": "string", "description": "What identified it, if not obvious."},
                },
                "required": ["category", "bbox", "confidence"],
            },
        },
        "metadata": {
            "type": "object",
            "description": "Structured metadata extracted from the cartouche or title block.",
            "properties": {
                "title":     {"type": "string", "description": "Main map title (e.g. 'Plan de Saïgon')"},
                "subtitle":  {"type": "string", "description": "Subtitle or secondary title line"},
                "year":      {"type": "string", "description": "Survey or publication year (e.g. '1882', 'circa 1898')"},
                "scale":     {"type": "string", "description": "Map scale as printed (e.g. '1:5 000', 'Echelle de 1:5000')"},
                "author":    {"type": "string", "description": "Cartographer or surveying organisation"},
                "publisher": {"type": "string", "description": "Publisher or printing body, if distinct from author"},
                "series":    {"type": "string", "description": "Series or collection name, if stated"},
                "edition":   {"type": "string", "description": "Edition or revision number, if stated"},
                "notes":     {"type": "string", "description": "Any other relevant cartouche text not captured above"},
            },
        },
        "extractions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "category": {"type": "string", "enum": ["street", "place", "building", "institution", "legend", "title", "hydrology", "other"]},
                    "language": {"type": "string", "enum": ["fr", "vi", "zh", "mixed", "other"]},
                    "bbox_px": {"type": "array", "items": {"type": "number"}},
                    "rotation_deg": {"type": "number"},
                    "confidence": {"type": "number"},
                    "notes": {"type": "string"}
                },
                "required": ["text", "category", "language", "bbox_px", "rotation_deg", "confidence"]
            }
        }
    },
    "required": ["extractions"]
}

# ── User prompt SCOUT — Macro-scanning ───────────────────────────────────────
# Key focus: Map metadata (cartouche), map bounds, major spanning features.

PROMPT_SCOUT = """\
Examine the provided low-resolution full-map image.

**1. Detect Map Bounds (Neatline):**
Identify the `map_content_bbox` [x, y, width, height] of the actual map content area.
Exclude white/paper margins, archival stamps (e.g. "BIBLIOTHÈQUE NATIONALE"), \
and handwritten inventory notes outside the map border.

**2. Extract Map Metadata (Cartouche):**
Find the cartouche or title block — typically a decorative box containing the map's \
formal information. Return its location as `cartouche_bbox` and populate the `metadata` object:
- **title**: main map title (e.g. "Plan de Saïgon", "Ville de Saïgon")
- **subtitle**: secondary title line, if any
- **year**: survey or publication year (e.g. "1882", "Levé en 1898")
- **scale**: scale as printed (e.g. "1:5 000", "Echelle de 1/5000")
- **author**: cartographer or surveying organisation (e.g. "Service Géographique de l'Indo-Chine")
- **publisher**: publisher or printing body, if distinct from author
- **series**: series or collection name, if stated
- **edition**: edition or revision, if stated
- **notes**: any other relevant cartouche text not captured above

Omit `metadata` fields that are not present. If no cartouche is visible at this resolution, \
return an empty `metadata` object and omit `cartouche_bbox`.

**3. Map the Layout (`regions`):**
Return one entry per distinct area of the sheet, each with a `category`, a `bbox` \
on the 0-1000 scale, and a `confidence`. Categories:
- **sheet**: the whole printed object, edge to edge of the paper, excluding scanner \
  background. Exactly one.
- **main_map**: the cartographic body — the terrain itself, inside the neatline and \
  excluding every block of text or furniture laid over or beside it. Exactly one. \
  This is usually, but not always, most of `map_content_bbox`.
- **title**: the cartouche or title block. Same area as `cartouche_bbox`.
- **legend**: the key explaining symbols, hatching or colours. Often a ruled box, \
  often headed "Légende", "Nomenclature" or "Signes conventionnels".
- **name_list**: an index or table of street or place names printed on the sheet, \
  usually alphabetical and in columns. This is NOT the legend: a legend explains \
  symbols, a name list enumerates places. Return one entry per column block.
- **inset**: a smaller separate map drawn within the sheet, at its own scale.
- **scale_bar**, **north_arrow**: furniture. Return them so they can be skipped.
- **stamp**: archival stamps, accession numbers, handwritten inventory marks.

Return only what you can actually see. Omit a category entirely rather than \
guessing at it, and never return a zero-area or full-sheet box just to fill a slot. \
Regions may overlap; a title block printed over the terrain belongs to `title`, and \
`main_map` should exclude it.

**4. Extract Major Spanning Features:**
Extract ONLY the large features within the map content area:
- **Hydrology**: Major canals, rivers, arroyos spanning large areas
- **Major streets**: Boulevard / Quai / Rue labels defining the primary road skeleton

Group words belonging to the same spanning label into ONE extraction \
(e.g. "Boulevard" ... "Charner" → one entry).

**What to SKIP:**
- Small buildings, house names, parcel numbers
- Library/archival stamps or handwritten marks
- Scale bar tick-mark numbers

Return `map_content_bbox`, `cartouche_bbox` (if found), `regions`, `metadata`, and \
`extractions`. Use the 0-1000 normalized scale for all bounding boxes.
"""

# ── User prompt V6 — transcription-only + edge-zone + row-sequence aware ──────
# Key changes from V5:
#   1. TRANSCRIPTION RULE: model must only transcribe visible text, not assemble/infer.
#      Removes the "scan along axis" instruction that caused prefix hallucination.
#   2. FRAGMENT CONFIDENCE: fragments at tile edges get 0.5-0.7 + required notes.
#   3. EDGE ZONE RULE: labels fully in the outer 10% of the tile get ≤0.6 confidence.
#   4. Confidence floor restored to 0.5 (omit entirely below that).
#   5. Expanded skip list: scale bar numbers, compass labels, isolated single letters.

PROMPT_V6 = """\
Examine the map tile image provided and extract every readable text label.

**TRANSCRIPTION RULE (critical — read carefully):**
Transcribe ONLY text that is physically visible in this tile image.
Do NOT complete, infer, or reconstruct labels using prior knowledge of place names.
Examples:
- You see "Charner" but not "Boulevard" → return: text="Charner", notes="fragment"
- You see "Rue de" but not the street name → return: text="Rue de", notes="continues outside right edge"
- You see the complete "Boulevard Charner" → return the full text normally

**FRAGMENT CONFIDENCE:**
- Complete label fully visible: confidence 0.7–1.0
- Partial label cut at a tile edge: confidence 0.5–0.7, notes MUST state which edge it exits
- Suspected fragment (spacing looks odd but no clear edge-cut): confidence ≤ 0.5 → omit entirely

**EDGE ZONE RULE:**
If a label is FULLY contained in the outer 10% strip near any tile edge (the overlap zone shared with the adjacent tile), set confidence ≤ 0.6 and add notes "edge zone". Labels that span from the tile interior into the edge zone should be extracted normally. The adjacent tile will extract edge-zone-only labels with higher confidence from its interior.

**GROUPING RULE (multi-line buildings only):**
A building or institution name printed across 2–3 lines inside one parcel = ONE extraction. The bbox must enclose all lines. Do NOT apply this rule to street names — extract only the visible words.

**Classification:**
- **street**: Roads, boulevards, quais, passages — extract ONLY the words you see
- **hydrology**: Canals (Rach), rivers, arroyos
- **institution**: Public/private institutions (Abattoir, Poste de Police, Cathédrale)
- **building**: Individual named buildings (Hôtel du Gouverneur)
- **place**: Village names (often "Vge de ..."), quarters, districts
- **legend / title**: Map boilerplate, scale bars, cartouche text, large titles
- **other**: Relevant text not fitting the above

**Normalization:**
Expand abbreviations: "Vge de" → "Village de", "R." → "Rue", "Pce" → "Place".
Preserve French accents and proper capitalisation.

**What to skip (do NOT extract):**
- Library/archival stamps (BIBLIOTHÈQUE NATIONALE, handwritten inventory numbers)
- Scale bar numbers (0, 200, 500, etc.) and their unit labels
- North arrow or compass labels (standalone "N", "Nord", "S", "E", "O")
- Grid coordinate numbers in map margins
- Bare integers — parcel numbers like "18", "42", "N°7"
- Isolated single letters not forming an obvious abbreviation
- Hatching, stippling, or colour-fill patterns that resemble letterforms

**For each label:**
1. text: Visible text only, in reading order
2. category: street | hydrology | place | building | institution | legend | title | other
3. language: fr | vi | zh | other
4. bbox_px: [x, y, width, height] (0–1000 scale, 0,0 = top-left)
5. rotation_deg: baseline angle from horizontal (positive = counter-clockwise)
6. confidence: 0.5–1.0. Omit labels you cannot reach 0.5 confidence on.
7. notes: "fragment", "continues outside [edge] edge", "edge zone", "faded", etc.

Return ONLY the JSON object. If no text is visible, return {"extractions": []}.
"""


# ── User prompt V7 — numbered streets + confidence tiers ─────────────────────
# Key changes from V6:
#   1. N°29 / N° 7 / No. 12 are valid Saigon numbered-street designations — keep them.
#   2. Confidence floor lowered to 0.4; adds an "uncertain" tier (0.4–0.7).
#      The pipeline uses this tier for spatial anchoring rather than outright discard.
#   3. Uncertain tier note convention: notes MUST include "uncertain:" prefix.

PROMPT_V7 = """\
Examine the map tile image provided and extract every readable text label.

**TRANSCRIPTION RULE (critical — read carefully):**
Transcribe ONLY text that is physically visible in this tile image.
Do NOT complete, infer, or reconstruct labels using prior knowledge of place names.
Examples:
- You see "Charner" but not "Boulevard" → return: text="Charner", notes="fragment"
- You see "Rue de" but not the street name → return: text="Rue de", notes="continues outside right edge"
- You see the complete "Boulevard Charner" → return the full text normally

**CONFIDENCE TIERS:**
- **Confirmed** (confidence 0.7–1.0): Label is complete and clearly legible.
- **Uncertain** (confidence 0.4–0.7): Label is legible but partial, faded, or cut by a tile edge.
  → notes MUST begin with "uncertain:" and describe why (e.g. "uncertain: faded ink", "uncertain: fragment").
- Omit labels you cannot reach 0.4 confidence on.

**FRAGMENT CONFIDENCE:**
- Complete label fully visible: confidence 0.7–1.0
- Partial label cut at a tile edge: confidence 0.4–0.7, notes: "uncertain: continues outside [edge] edge"
- Suspected fragment (no clear edge-cut): confidence ≤ 0.5 — only include if ≥ 0.4 and add "uncertain: suspected fragment"

**EDGE ZONE RULE:**
If a label is FULLY contained in the outer 10% strip near any tile edge, set confidence ≤ 0.6 \
and notes "uncertain: edge zone". Labels spanning from the interior into the edge zone are extracted normally.

**GROUPING RULE (multi-line buildings only):**
A building or institution name printed across 2–3 lines inside one parcel = ONE extraction. \
The bbox must enclose all lines. Do NOT apply this rule to street names — extract only the visible words.

**NUMBERED STREETS (important):**
Saigon's 1882 map uses numbered street designations: "N°29", "N° 7", "No. 12", etc. \
These are valid street-name labels (category="street"), NOT parcel numbers. \
Extract them when clearly printed as a street label (typically placed along the road centreline). \
Do NOT extract bare integers ("18", "42") that are parcel fill numbers inside plot areas.

**Classification:**
- **street**: Roads, boulevards, quais, passages, and numbered streets (N°…) — extract ONLY visible words
- **hydrology**: Canals (Rach), rivers, arroyos
- **institution**: Public/private institutions (Abattoir, Poste de Police, Cathédrale)
- **building**: Individual named buildings (Hôtel du Gouverneur)
- **place**: Village names (often "Vge de ..."), quarters, districts
- **legend / title**: Map boilerplate, scale bars, cartouche text, large titles
- **other**: Relevant text not fitting the above

**Normalization:**
Expand abbreviations: "Vge de" → "Village de", "R." → "Rue", "Pce" → "Place".
Preserve French accents and proper capitalisation.

**What to skip (do NOT extract):**
- Library/archival stamps (BIBLIOTHÈQUE NATIONALE, handwritten inventory numbers)
- Scale bar numbers (0, 200, 500, etc.) and their unit labels
- North arrow or compass labels (standalone "N", "Nord", "S", "E", "O")
- Grid coordinate numbers in map margins
- Bare parcel integers — lone digits inside plot areas like "18", "42" (NOT "N°29" — see above)
- Isolated single letters not forming an obvious abbreviation with a period
- Hatching, stippling, or colour-fill patterns that resemble letterforms

**For each label:**
1. text: Visible text only, in reading order
2. category: street | hydrology | place | building | institution | legend | title | other
3. language: fr | vi | zh | mixed | other
   Use "mixed" for labels combining languages (e.g. "Village Annamite de Chợ Quán").
4. bbox_px: [x, y, width, height] (0–1000 scale, 0,0 = top-left)
5. rotation_deg: baseline angle from horizontal (positive = counter-clockwise)
6. confidence: 0.4–1.0. Omit labels below 0.4.
7. notes: use "uncertain: <reason>" for confidence < 0.7; "fragment", "continues outside [edge] edge", "edge zone", "faded", etc.

Return ONLY the JSON object. If no text is visible, return {"extractions": []}.
"""


# ── User prompt V8 — maximum recall (false-positive tolerant) ─────────────────
# Key changes from V7:
#   1. No confidence floor — the model reports EVERYTHING it can detect.
#      The review UI, not the model, decides what to keep.
#   2. Removed edge-zone penalty (was suppressing overlapping detections).
#   3. Kept TRANSCRIPTION RULE (no hallucination) and hydrology category from V6.
#   4. Kept numbered streets (N°29) from V7.
#   5. Simplified skip list to only hard non-text cases (stamps, pure scale numbers).
#   6. Explicit "err on the side of inclusion" instruction.

PROMPT_V8 = """\
Examine the map tile image provided and extract every readable text label.

**TRANSCRIPTION RULE (critical):**
Transcribe ONLY text that is physically visible in this tile image.
Do NOT complete, infer, or reconstruct labels using prior knowledge of place names.
- You see "Charner" but not "Boulevard" → text="Charner", notes="fragment"
- You see the complete "Boulevard Charner" → return the full text normally

**RECALL RULE (critical):**
Err on the side of INCLUSION. If you can detect any text — even faded, rotated, or partially \
cut off — return it. Set a low confidence score rather than omitting it. A human reviewer \
will reject false positives. A missed label can never be recovered.

**GROUPING RULE (multi-line buildings/institutions):**
A building or institution name printed across 2–3 lines inside one parcel = ONE extraction. \
The bbox must enclose all lines. Do NOT apply this rule to street names — extract only the visible words.

**NUMBERED STREETS:**
"N°29", "N° 7", "No. 12" etc. are valid street labels (category="street"), NOT parcel numbers. \
Extract them when placed along a road centreline. Do NOT extract bare integers inside plot areas.

**Classification:**
- **street**: Roads, boulevards, quais, passages, and numbered streets (N°…)
- **hydrology**: Canals (Rach), rivers, arroyos (e.g. "Arroyo de l'Avalanche")
- **institution**: Public/private institutions (Abattoir, Poste de Police, Cathédrale)
- **building**: Individual named buildings (Hôtel du Gouverneur)
- **place**: Village names ("Vge de ..."), quarters, districts
- **legend / title**: Map boilerplate, scale bars, cartouche text, large titles
- **other**: Any other relevant text that does not fit the above

**Normalization:**
Expand abbreviations: "Vge de" → "Village de", "R." → "Rue", "Pce" → "Place".
Preserve French accents and proper capitalisation.

**What to skip (hard non-text only):**
- Library/archival stamps added to the scan (BIBLIOTHÈQUE NATIONALE, handwritten inventory numbers like "A1005")
- Scale bar tick-mark numbers (0, 100, 200 m) — numeric only, no associated text
- North arrow compass letters (standalone "N", "S", "E", "O" next to an arrow symbol)
- Hatching, stippling, or colour-fill patterns that only superficially resemble letters

**For each label:**
1. text: Visible text only, in reading order
2. category: street | hydrology | place | building | institution | legend | title | other
3. language: fr | vi | zh | mixed | other
4. bbox_px: [x, y, width, height] (0–1000 scale, 0,0 = top-left)
5. rotation_deg: baseline angle from horizontal (positive = counter-clockwise)
6. confidence: 0.1–1.0. There is NO minimum threshold — include everything you detect.
   Use low confidence (0.1–0.4) for very faded or uncertain text rather than omitting it.
7. notes: "fragment", "continues outside [edge] edge", "faded", "uncertain: <reason>", etc.

Return ONLY the JSON object. If no text is visible, return {"extractions": []}.
"""


# ── Sequence prompts ──────────────────────────────────────────────────────────
# v8 is a per-tile prompt: it asks for fragments and relies on the offline join to
# rebuild labels. On the row-sequence path the model holds every frame, so the
# fragment rule is pure loss — measured 2026-09-08 as −0.14 recall and −2.7 pts
# char_acc against the old fallback. seq-v1 is v8 with whole-label assembly
# restored. (A seq-v1-style variant with style/ink fields was measured 2026-09-08
# — 38/43 vs 39/43, +5k output tokens — and cut; see EVAL-BASELINE.md.)

PROMPT_SEQ_V1 = """\
Examine the map crops provided and extract every readable text label.

**TRANSCRIPTION RULE (critical):**
Transcribe ONLY text that is physically printed on the sheet. Do NOT complete, infer, or \
reconstruct labels from prior knowledge of place names.

**WHOLE LABELS (critical):**
Return each label COMPLETE, as one extraction. Street names are printed word by word along \
the road ("Rue" … "de" … "Genouilly"), building names across two or three lines inside a \
parcel; all of those words are one label with one bbox enclosing every word. Only when a \
label genuinely runs off the outermost edge of what you are shown do you return the visible \
part, with notes "continues outside [edge] edge".

**RECALL RULE (critical):**
Err on the side of INCLUSION. If you can detect any text — even faded, rotated, or partially \
cut off — return it. Set a low confidence score rather than omitting it. A human reviewer \
will reject false positives. A missed label can never be recovered.


**NUMBERED STREETS:**
"N°29", "N° 7", "No. 12" etc. are valid street labels (category="street"), NOT parcel numbers. \
Extract them when placed along a road centreline. Do NOT extract bare integers inside plot areas.

**Classification:**
- **street**: Roads, boulevards, quais, passages, and numbered streets (N°…)
- **hydrology**: Canals (Rach), rivers, arroyos (e.g. "Arroyo de l'Avalanche")
- **institution**: Public/private institutions (Abattoir, Poste de Police, Cathédrale)
- **building**: Individual named buildings (Hôtel du Gouverneur)
- **place**: Village names ("Vge de ..."), quarters, districts
- **legend / title**: Map boilerplate, scale bars, cartouche text, large titles
- **other**: Any other relevant text that does not fit the above

**Normalization:**
Transcribe abbreviations AS PRINTED — "Vge de", "R.", "Pce", "Bd" stay as they are. Do not \
expand them: "R." is "Rue" before a French road name but "Rạch" (creek) before a Vietnamese \
name on the water, and the sheet, not prior knowledge, decides. Preserve accents, Vietnamese \
diacritics and the printed capitalisation.

**What to skip (hard non-text only):**
- Library/archival stamps added to the scan (BIBLIOTHÈQUE NATIONALE, handwritten inventory numbers like "A1005")
- Scale bar tick-mark numbers (0, 100, 200 m) — numeric only, no associated text
- North arrow compass letters (standalone "N", "S", "E", "O" next to an arrow symbol)
- Hatching, stippling, or colour-fill patterns that only superficially resemble letters

**For each label:**
1. text: Visible text only, in reading order
2. category: street | hydrology | place | building | institution | legend | title | other
3. language: fr | vi | zh | mixed | other
4. bbox_px: [x, y, width, height] (0–1000 scale, 0,0 = top-left)
5. rotation_deg: baseline angle from horizontal (positive = counter-clockwise)
6. confidence: 0.1–1.0. There is NO minimum threshold — include everything you detect.
   Use low confidence (0.1–0.4) for very faded or uncertain text rather than omitting it.
7. notes: "continues outside [edge] edge", "faded", "uncertain: <reason>", etc.

Return ONLY the JSON object. If no text is visible, return {"extractions": []}.
"""


# ── Index-key variant ────────────────────────────────────────────────────────
# seq-v1 suppresses bare integers ("Do NOT extract bare integers inside plot
# areas"), which is right on a cadastral sheet — the 1882 gate sheet is wall to
# wall parcel numbers — and wrong on a sheet whose numbers are keys into its own
# printed directory. The 1959 Đô thành Sài Gòn plan carries a numbered
# administrative index; seq-v1 returned 11 of its numbers across the whole
# sheet, as leakage against instruction, filed under `other` and `legend`
# because there was no class for them.
#
# A separate id on purpose: seq-v1 is the measured gate (EVAL-BASELINE.md) and
# its ground truth is the sheet that wants integers dropped. Opt in per sheet.
PROMPT_SEQ_V1_IDX = PROMPT_SEQ_V1.replace(
    """Extract them when placed along a road centreline. Do NOT extract bare integers inside plot areas.""",
    """Extract them when placed along a road centreline.

**INDEX KEYS (this sheet has a numbered index):**
Bare integers printed on the map are keys into the sheet's own printed directory, not noise. \
Extract every one as category="index_key", with the bbox on the digits themselves. Include the \
parentheses if printed ("(12)"). Do NOT extract the numbers along the border grid strips or the \
scale bar.""",
).replace(
    """- **other**: Any other relevant text that does not fit the above""",
    """- **index_key**: A bare integer keying into the sheet's printed directory
- **other**: Any other relevant text that does not fit the above""",
).replace(
    """2. category: street | hydrology | place | building | institution | legend | title | other""",
    """2. category: street | hydrology | place | building | institution | legend | title | index_key | other""",
)
assert "index_key" in PROMPT_SEQ_V1_IDX and "bare integers inside plot" not in PROMPT_SEQ_V1_IDX


# The schema that prompt needs. `index_key` has to be in the response schema's
# category enum or the model cannot answer with it: structured output is
# constrained to the enum, so every index number silently lands in `other`.
# That is exactly what happened — the 1942 rescan one-off carries the note "the
# prompt's own `index_key` never made it into a response" and reclassifies by
# hand afterwards, and the 1878 sheet repeated it on 2026-09-12 (28 numerals,
# all filed as `other`, scoring 0/29 against the sheet's own printed list).
#
# Kept SEPARATE from EXTRACTION_SCHEMA rather than adding the value there: the
# Gemini result cache keys on the schema (`schema_version`), and `ocr.py` pins
# it with `assert ... == SCHEMA_VERSION, "cache went cold"`. Widening the shared
# enum would cold-cache every run of every other prompt to fix one of them.
EXTRACTION_SCHEMA_IDX = copy.deepcopy(EXTRACTION_SCHEMA)
EXTRACTION_SCHEMA_IDX["properties"]["extractions"]["items"]["properties"]["category"]["enum"].append(
    "index_key"
)


def schema_for(prompt_key: str) -> dict:
    """The response schema a prompt version needs.

    Only `seq-v1-idx` asks for a category the default schema does not list.
    Every other version gets EXTRACTION_SCHEMA unchanged, so their cached tile
    results stay warm.
    """
    return EXTRACTION_SCHEMA_IDX if prompt_key == "seq-v1-idx" else EXTRACTION_SCHEMA


assert "index_key" in schema_for("seq-v1-idx")["properties"]["extractions"]["items"]["properties"]["category"]["enum"]
assert "index_key" not in schema_for("seq-v1")["properties"]["extractions"]["items"]["properties"]["category"]["enum"]


# ── Prompt registry (used by ocr.py --prompt flag) ───────────────────────────

PROMPTS: dict[str, str] = {
    "v1": PROMPT_V1,
    "v2": PROMPT_V2,
    "v3": PROMPT_V3,
    "v4": PROMPT_V4,
    "v5": PROMPT_V5,
    "v6": PROMPT_V6,
    "v7": PROMPT_V7,
    "v8": PROMPT_V8,
    "seq-v1": PROMPT_SEQ_V1,
    "seq-v1-idx": PROMPT_SEQ_V1_IDX,
    "scout": PROMPT_SCOUT,
}

# seq-v1 passed the gate on 2026-09-08 (39/43 vs the fallback's 33/43, char_acc
# 0.990 vs 0.979, diacritic recall 1.0) — see EVAL-BASELINE.md. It is written
# for the row-sequence path, which is the production default; a one-tile row
# gets the same prompt and loses nothing by being asked for whole labels.
DEFAULT_PROMPT = "seq-v1"


# ── Frame rules for the row-sequence call ──────────────────────────────

def sequence_frame_rules(n_frames: int) -> str:
    """Frame-addressing rules to append to the selected prompt for a sequence call.

    Deliberately not a `PROMPTS` entry: this is not a prompt version, it is the delta
    between "one tile" and "n adjacent tiles in one call", so it has to be appended to
    whichever version the run picked rather than replacing it.

    Until 2026-09-08 these rules lived in `gemini_client.extract_labels_sequence` as a
    hardcoded fallback that named an "1882 Saigon cadastral map", and `cmd_batch` passed
    no `user_prompt` — so the row-sequence path (the production default for any row of
    more than one tile) sent that fallback *instead of* the selected prompt. v8 never
    reached the model on the default path, while every tile's `_meta` recorded
    `"prompt": "v8"`. That is the most likely source of the 9%-100% per-run diacritic
    spread in `EVAL-BASELINE.md`: the prompt version was never actually a variable.
    """
    return f"""

**FRAME ADDRESSING (this call carries {n_frames} frames):**
You are given {n_frames} overlapping crops of ONE map sheet, in reading order along the \
tile row. Consecutive frames overlap, so the same label can fall inside more than one.

- Add a top-level "frame_idx" (integer, 0-based) to every extraction.
- bbox_px is always in the coordinate space of the frame named by that extraction's frame_idx.
- Return each label ONCE. When it is legible in several frames, pick the frame showing most of it.
- A label cut by a frame edge is not a fragment: the tile boundary is an artefact of how the \
sheet was cropped for this call, not of how it was printed. Join the pieces you can see across \
frames into the complete label — "Rue" at the right edge of frame 0 plus "de Genouilly" at the \
left edge of frame 1 is one extraction, "Rue de Genouilly" — and add notes "spans frames 0-1".
- Joining across frames is the ONLY exception to the transcription rule above. Join text you \
can SEE in another frame; never supply words from prior knowledge of the place. If a label runs \
off the outermost frame, transcribe what is printed and note "continues outside [edge] edge".
"""
