/**
 * Editorial copy for /about — the six-layer stack, the three-phase roadmap and
 * the audience cards. Pure content: no logic, no imports. Lives here so the
 * page component is markup only.
 */

export interface Layer {
  id: string;
  name: string;
  desc: string;
  pct: number;
  color: string;
  phase: string;
  phaseColor: string;
  built: string[];
  building: string[];
  next: string;
}

export const layers: Layer[] = [
  {
    id: 'L1',
    name: 'Historical maps',
    desc: 'The foundation — old maps placed on real coordinates so every building on them has an address',
    pct: 40,
    color: 'var(--status-ok)',
    phase: 'Foundation',
    phaseColor: 'var(--status-ok)',
    built: [
      '45 historical maps in the archive spanning 1791 to today — Saigon, Hanoi, Huế, and broader Vietnam, sourced from archives in Paris, Hanoi, and private collections',
      'Every map works in a regular browser — no specialist software, just a link',
      'First AI extraction test: 91 city blocks pulled from the 1882 Saigon survey automatically — the AI found them without being shown a single example first',
    ],
    building: [
      'Running the full 1882 map — city blocks first, then individual building footprints inside each block',
      'Preparing the 1898 map — same process, so we can see exactly what changed in 16 years',
    ],
    next: 'Both maps fully extracted → an automatic map of change: every building that was built, demolished, or subdivided between 1882 and 1898',
  },
  {
    id: 'L2',
    name: 'Building heights',
    desc: 'How tall was the city? We read it from two rare paintings — no laser scanning needed',
    pct: 5,
    color: 'var(--ink-soft)',
    phase: 'Phase 3',
    phaseColor: 'var(--ink-soft)',
    built: [
      'Two painting-and-map pairs found from the same years as our maps — most reconstruction projects only have the map',
      "An 1881 bird's-eye engraving shows the whole city from above: you can count the floors, see the rooflines, compare block heights across the grid",
      'A 1901 full-color painting of the same city — even more detailed, and color shows what the roofs are actually made of',
      'Open-source 3D reconstruction tool (TU Delft, 2021) studied and adapted — proven on Dutch and Belgian cities, this would be the first Southeast Asian colonial application',
    ],
    building: [
      'Adapting the tool to recognise the specific colors and symbols used on French colonial Saigon maps',
    ],
    next: 'Simple 3D models for ~2,000 buildings in the 1900 city centre — each one with a height estimate and a confidence score',
  },
  {
    id: 'L3',
    name: 'Roof types',
    desc: 'Flat, pitched, or hipped — giving every building its correct roofline',
    pct: 5,
    color: 'var(--ink-soft)',
    phase: 'Phase 3',
    phaseColor: 'var(--ink-soft)',
    built: [
      'The 1901 painting is the key: look at it and the whole city is covered in red-tiled roofs — the same terracotta tiles still common in Vietnamese cities today',
      'This is more than a visual observation — it confirms that the color-coded map symbols really do map onto real, distinct building types. The AI classification is semantically correct.',
      'Rules designed for buildings with no surviving photo: shophouses → flat roof, colonial admin buildings → hipped roof, churches → towers. Checked against landmarks with known heights (Notre-Dame: 57 m)',
    ],
    building: ['Connecting roof type assignments to the height model'],
    next: 'Every building gets a typed roof — each with a confidence score based on how much evidence we have',
  },
  {
    id: 'L4',
    name: 'Detailed 3D models',
    desc: 'Photo-realistic facades for ~30 landmark buildings, built from archival photos',
    pct: 5,
    color: 'var(--ink-soft)',
    phase: 'Phase 3',
    phaseColor: 'var(--ink-soft)',
    built: [
      '3D-from-photos technique chosen — open-source, proven on architectural heritage projects worldwide',
      'Best photo sources mapped: French colonial survey albums, Paris national library postcards (1900–1930), the Manhhai community archive, family collections',
      '”Adopt a building” volunteer role designed — find the photos, the computer builds the model, you get permanent credit in the archive',
    ],
    building: [
      'Gathering archival photos for the first 5 buildings: Notre-Dame, City Hall, Opera House, Central Post Office, Ben Thanh Market',
    ],
    next: 'First landmark shown as a full textured 3D model — every detail visible, every photo contributor named',
  },
  {
    id: 'L5',
    name: 'Stories behind the buildings',
    desc: 'Names, owners, dates, and histories — linked to every building on the map',
    pct: 10,
    color: 'var(--accent)',
    phase: 'Phase 2',
    phaseColor: 'var(--accent)',
    built: [
      'Data structure complete: buildings, streets, people, institutions — each connected by named relationships (built by, owned by, known as, replaced by...)',
      'Dates handle uncertainty honestly — “around 1905” or “before 1910” are valid entries, not workarounds',
      'Every historical record links directly to the building geometry it describes',
    ],
    building: [
      'Search and browse interface: find a building, see its history; find a person, see what they owned',
      'Historian tool: add a fact, cite your source, attach it to a specific building',
    ],
    next: 'First 100 entries with citations: Cathedral, City Hall, Opera House, key colonial streets, Cholon market district',
  },
  {
    id: 'L6',
    name: 'Living memory',
    desc: 'A Wikipedia page for every building — anyone can add what they know, from a family photo to an archival document',
    pct: 20,
    color: 'var(--accent)',
    phase: 'Phase 1',
    phaseColor: 'var(--status-ok)',
    built: [
      'GPS walking stories: stand near a historic site and the app reveals what was there',
      'Drawing tool for marking and annotating historical maps',
      'Community map placement: anyone can help put an unplaced historical map on the correct location',
    ],
    building: [
      "Once the building dataset is published, a discussion page for each building — add what you know, attach a photo, correct a date, just like Wikipedia but for Saigon's streets",
    ],
    next: 'Every building in the archive gets its own page — and anyone who knows something about it can add their piece',
  },
];

export const phases = [
  {
    num: 1,
    title: 'Maps to Geometry',
    subtitle: '"Turn every building on colonial maps into a shape with an address"',
    timeline: '6–9 months from funding',
    color: 'var(--status-ok)',
    milestones: [
      {
        id: 'M1.1',
        text: '10 colonial Saigon maps placed and linked — spanning 1880 to 1930',
        done: false,
      },
      {
        id: 'M1.2',
        text: 'Community tracing tools live: tag photos and trace building outlines',
        done: false,
      },
      {
        id: 'M1.3',
        text: 'AI building detector improved on community-traced examples',
        done: false,
      },
      {
        id: 'M1.4',
        text: 'First open dataset: every building outline in 1900 Saigon',
        done: false,
      },
      { id: 'M1.5', text: 'Dataset covers 5 time periods from 1880 to 1930', done: false },
    ],
  },
  {
    num: 2,
    title: 'Geometry to Knowledge',
    subtitle: '"Give every building a story, every street a history"',
    timeline: '9–18 months from funding',
    color: 'var(--accent)',
    milestones: [
      {
        id: 'M2.1',
        text: 'History database live — find any building and see what we know about it',
        done: false,
      },
      {
        id: 'M2.2',
        text: '100 buildings documented with sources: who built them, who owned them, what happened to them',
        done: false,
      },
      {
        id: 'M2.3',
        text: 'Uncertain dates handled honestly — every fact shows how confident we are',
        done: false,
      },
      {
        id: 'M2.4',
        text: 'Research library: 50+ primary sources (maps, surveys, land records) linked to specific buildings',
        done: false,
      },
      {
        id: 'M2.5',
        text: 'All data publicly downloadable — open for researchers, students, journalists',
        done: false,
      },
    ],
  },
  {
    num: 3,
    title: 'Knowledge to Dimension',
    subtitle: '"Lift the city off the page"',
    timeline: '18–30 months from funding',
    color: 'var(--ink-soft)',
    milestones: [
      {
        id: 'M3.1',
        text: '3D reconstruction tool adapted to French colonial Saigon maps',
        done: false,
      },
      {
        id: 'M3.2',
        text: 'Color and symbol recognition validated across 3 different Saigon map editions',
        done: false,
      },
      {
        id: 'M3.3',
        text: '3D city model for the 1900 Saigon core — every building as a block with a roof',
        done: false,
      },
      {
        id: 'M3.5',
        text: '"Adopt a building" live — volunteers collect archival photos, earn permanent credit',
        done: false,
      },
      {
        id: 'M3.6',
        text: '10 landmark buildings rebuilt in full detail from historical photos',
        done: false,
      },
      {
        id: 'M3.7',
        text: 'Timeline viewer: scrub through the city at 1890, 1910, and 1930',
        done: false,
      },
    ],
  },
];

export const users = [
  {
    icon: '🏙️',
    title: 'People living in the city',
    desc: 'You walk past these buildings every day. Find out who built them, who owned them, what was torn down to put them there — and watch the street you know change across a century.',
    uses: 'Browse georeferenced maps · GPS walking stories · Overlay history on today',
  },
  {
    icon: '👨‍👩‍👧',
    title: 'Families with roots here',
    desc: "Your grandparents' neighborhood existed. The street where they lived had a name before it was renamed. Tag a family photo, find the address, connect a memory to a place that still exists — just changed.",
    uses: 'Tag archival photos · Contribute family knowledge · Find addresses on colonial maps',
  },
  {
    icon: '🔬',
    title: 'Researchers & historians',
    desc: 'Georeferenced maps, structured data, cited sources, open download. Colonial land tenure, urban morphology, merchant networks, French administrative records — searchable and linked.',
    uses: 'Download open datasets · Cite structured KG entries · Embed georeferenced maps',
  },
  {
    icon: '🗺️',
    title: 'OSM & GIS mappers',
    desc: 'Same skills you already use — polygon tracing on a georeferenced base, open data values, community validation. Historical Saigon needs the same attention OpenStreetMap gives to the modern city.',
    uses: 'Trace building footprints · Validate community submissions · Export GeoJSON',
  },
  {
    icon: '📚',
    title: 'Educators',
    desc: 'Interactive maps you can walk through, GPS stories you can assign, sourced historical data you can cite. Usable for teaching Vietnamese history, colonial urbanism, or heritage and memory.',
    uses: 'Embed maps in lessons · Assign GPS walks · Use structured timeline data',
  },
  {
    icon: '🏛️',
    title: 'Archives & institutions',
    desc: 'Your digitized maps used, linked to knowledge, and kept accessible — not downloaded and forgotten. BnF Gallica, EFEO, and David Rumsey collections are already in the archive.',
    uses: 'Ingest existing collections · Get attribution · Reach new audiences',
  },
];
