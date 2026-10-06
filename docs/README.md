# Vietnam Map Archive documentation

Start here to find a guide, understand the system, or locate the evidence behind a result.
For scripts, datasets and local experiments, use the [work directory guide](../work/README.md).

The [directory layout](model-layout.md) follows the same layers as the knowledge system.
The [map-type audit](catalog-map-type-audit.md) records the original-map review and pending classification questions.
The [workspace mapping](workspace-model.json) declares each area's primary responsibility;
[research records](research/README.md) now have a dedicated folder.

## What do you want to do?

| I want to…                               | Start here                                                                                |
| ---------------------------------------- | ----------------------------------------------------------------------------------------- |
| Explore maps or contribute               | [User guide](user-guide.md)                                                               |
| Prepare and read a scanned sheet         | [Reading a sheet](digitalize-guide.md)                                                    |
| Manage the catalog and review queues     | [Admin tooling](admin-tooling.md)                                                         |
| Understand how the archive fits together | [System graph](system-graph.md)                                                           |
| See what is being worked on              | [Roadmap](ROADMAP.md) — the single tracker for open work                                  |
| Change the app                           | [Architecture](architecture.md), [conventions](conventions.md), then the references below |
| Run OCR, segmentation or georeferencing  | [Pipelines](pipelines.md) and [work directory guide](../work/README.md)                   |
| Build or deploy                          | [Deployment](deploy.md)                                                                   |
| Find a research result                   | [Research records](#research-records) and [journal index](journals/README.md)             |
| Read the manuscript                      | [Paper guide](paper/README.md)                                                            |

## Engineering references

| Document                                  | Covers                                                                                          |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [Architecture](architecture.md)           | Map runtime, shells, stores and page composition                                                |
| [Conventions](conventions.md)             | Fonts, naming, types and component conventions                                                  |
| [Design system](design-system.md)         | Visual language, tokens and styling                                                             |
| [System guidelines](system-guidelines.md) | Layering, page structure and component patterns                                                 |
| [API](api.md)                             | Server routes and their contracts                                                               |
| [Database guidelines](db-guidelines.md)   | Schema decisions; also read [Supabase instructions](../supabase/CLAUDE.md) before database work |
| [Testing](testing.md)                     | What the checks protect; read before changing tests                                             |
| [Pipelines](pipelines.md)                 | Operator commands and pipeline design                                                           |
| [Lessons](lessons.md)                     | Rules learned from failures; read before database writes, unattended runs or measurements       |
| [Ponytail debt](ponytail-debt.md)         | Deliberate shortcuts and when to revisit them                                                   |

## Product direction and plans

Plans describe intended behavior. Use the [roadmap](ROADMAP.md) to determine what is still open;
a proposed feature in a plan is not evidence that it is available in the app.

| Document                                     | Covers                                               |
| -------------------------------------------- | ---------------------------------------------------- |
| [Strategy](strategy.md)                      | Product direction and funding narrative              |
| [Theory](theory.md)                          | Intellectual framework                               |
| [Knowledge system](knowledge-system-plan.md) | Object model, gaps and the roadmap index in §9       |
| [Search](search-plan.md)                     | Finding labels, shapes and period sources            |
| [Usage measurement](usage-measurement-plan.md) | Study, grant and support evidence; opt-in journeys and confirmed outcomes |
| [Catalog](catalog-plan.md)                   | The public list: columns, facets, speed, search       |
| [Walk](walk-plan.md)                         | Proposed district walks; forks the separate HACW app |
| [Evidence chain](evidence-chain-plan.md)     | Source-backed claims, review and reuse               |
| [Platform design](platform-design.md)        | Proposed shared platform architecture                |

## Research records

These are dated findings and experiments. Read their dates, inputs and caveats before reusing a result.

| Document                                                       | Covers                                                          |
| -------------------------------------------------------------- | --------------------------------------------------------------- |
| [Image processing record](research/image-processing-record.md) | Methods and recorded measurements, with links to their evidence |
| [Field comparison](research/field-comparison.md)               | Comparison with published research and deployed systems         |
| [Worked example: 1882](research/worked-example-1882.md)        | One sheet taken through the pipeline                            |
| [1882 feature-layer plan](image-processing-1882-plan.md) | Repo consolidation, frozen water and the block comparison |
| [River reconstruction](research/river-reconstruction.md)       | Exploratory 1882/1898 work; no river layer approved             |
| [Allmaps series note](research/allmaps-series-note.md)         | Dated technical note on georeferencing two map series           |
| [Journals](journals/README.md)                                 | Dated runs, audits and handoffs                                 |
| [Paper](paper/README.md)                                       | Manuscript, claim evidence, figures and review records          |
| [Analysis folders](../work/analysis/README.md)                 | Scripts, figures and review packs behind experiments            |

## Historical and private material

- [Archive](archive/README.md): frozen design and implementation records.
- [Roadmap record](roadmap-record.md): frozen on 2026-09-22; use it for past decisions and costs.
- `private/`: local, gitignored outreach and personal material. Never publish it or copy it into a public index.
- `system-graph*.svg` and `.png`: illustrations used by [System graph](system-graph.md).

## Keeping this directory useful

Link a new guide from this index and describe its audience and purpose in its opening paragraph.
Put dated investigations in `journals/`; keep frozen material in `archive/` and label it as historical.
Keep open tasks in `ROADMAP.md` and update the matching item in `knowledge-system-plan.md` §9 together.
