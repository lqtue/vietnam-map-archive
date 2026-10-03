# Research direction: historical urban change in Ho Chi Minh City

**2026-10-02.** Session record of the research focus discussed alongside organization of
`work/` and `docs/`, and higher education planning. Personal education and application
details are recorded separately in `docs/private/session-notes/261002-research-and-higher-education.md`
(gitignored). This note records discussion and proposed directions, not completed experiments.

## Focus

The proposed central question is **how successive phases of development shaped Ho Chi Minh
City's present urban fabric**, using historical maps, building data and remote sensing.
The contributing fields are historical GIS and cartography, urban morphology and housing,
geospatial data engineering, image processing, and urban environmental research.

VMA's current segmentation work centres on the 1882 and 1898 maps. The session identified
a complementary District 4 study spanning 1942, 1959, 1968 and the present.

## Observations to investigate

- The user sees notable change between 1942 and 1959 in District 4, including yellow areas
  interpreted as `nhà lá` (lightweight or temporary housing).
- The 1968 map appears to show some `cư xá` estates being built.
- Present-day contrasts include tightly packed fabric around Tôn Đản, housing estates
  across District 4, and high-rise development on formerly industrial land.
- Available HCMC building footprint and height data could support comparison with
  present urban form. Existing work on historical expansion, tree cover and land surface
  temperature offers an environmental extension.

These are user observations and research leads. Map legends, dates, coverage and independent
evidence still need checking before treating them as historical findings.

## Two possible outputs

1. **Development chronology:** estimate when sites or areas first appear developed in the
   available maps, with evidence and uncertainty attached to each interval.
2. **Urban morphology and taxonomy:** compare dense street fabric, estates, industrial
   sites and redevelopment, connecting historical trajectories to current footprints and heights.

The suggested first study is three or four contrasting small areas in District 4, using
1942, 1959, 1968 and current data. This is a proposed scope, not a new approved ROADMAP item.

## Interpretation rules

- First mapped development of a site does not establish the construction date of today's building.
- A change in mapped colour or symbols may reflect survey or legend conventions as well as physical change.
- Keep historical development, current morphology and land use distinguishable in the data.
- Land surface temperature and ambient heat exposure are different quantities.

## Organization and next steps

The session began with requests to consolidate image-processing folders, make OCR runs and
results easier to identify, and organize `work/` and `docs/` consistently with the system model.
This record does not certify that those cleanup tasks were completed.

The research discussion points toward an evidence chain connecting map observations,
derived objects, cross-date comparisons and research claims. Next research preparation:
write a one-page proposal, choose the small-area comparisons, inspect the map legends,
and inventory which dates and datasets actually support each proposed claim.
