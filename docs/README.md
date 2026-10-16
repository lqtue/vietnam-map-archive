# Vietnam Map Archive documentation

Start here to find a guide, understand the system, or locate the evidence behind a result.
For a folder-by-folder map of the workspace, with what each holds and what to read first, use the [Atlas](ATLAS.md).
For scripts, datasets and local experiments, use the [work directory guide](../work/README.md).
Guides (`guides/`) say how the system works and how to work on it; plans (`plans/`) say where it is going.

[Page specs](guides/pages/README.md) — every web page in one template, with the bugs and house-rule gaps found on 2026-10-14.

The [directory layout](model-layout.md) follows the same layers as the knowledge system.
The [map-type audit](plans/catalog-map-type-audit.md) records the original-map review and pending classification questions.
The [workspace mapping](workspace-model.json) declares each area's primary responsibility;
[research records](research/README.md) now have a dedicated folder.

## What do you want to do?

| I want to…                               | Start here                                                                                |
| ---------------------------------------- | ----------------------------------------------------------------------------------------- |
| Explore maps or contribute               | [User guide](guides/user-guide.md)                                                               |
| Prepare and read a scanned sheet         | [Reading a sheet](guides/digitalize-guide.md)                                                    |
| Manage the catalog and review queues     | [Admin tooling](guides/admin-tooling.md)                                                         |
| Understand how the archive fits together | [System graph](guides/system-graph.md)                                                           |
| See what matters now, and why            | [Now](NOW.md) — the goal, three bets, the idea gate, who is on what                       |
| See what is being worked on              | [Roadmap](ROADMAP.md) — the single tracker for open work                                  |
| Change the app                           | [Architecture](guides/architecture.md), [conventions](guides/conventions.md), then the references below |
| Run OCR, segmentation or georeferencing  | [Pipelines](guides/pipelines.md) and [work directory guide](../work/README.md)                   |
| Build or deploy                          | [Deployment](guides/deploy.md)                                                                   |
| Find a research result                   | [Research records](#research-records) and [journal index](journals/README.md)             |
| Read the manuscript                      | [Paper guide](paper/README.md)                                                            |

## Engineering references

| Document                                  | Covers                                                                                          |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [Architecture](guides/architecture.md)           | Map runtime, shells, stores and page composition                                                |
| [Conventions](guides/conventions.md)             | Fonts, naming, types and component conventions                                                  |
| [Design system](guides/design-system.md)         | Visual language, tokens and styling                                                             |
| [System guidelines](guides/system-guidelines.md) | Layering, page structure and component patterns                                                 |
| [API](guides/api.md)                             | Server routes and their contracts                                                               |
| [Database guidelines](guides/db-guidelines.md)   | Schema decisions; also read [Supabase instructions](../supabase/CLAUDE.md) before database work |
| [Testing](guides/testing.md)                     | What the checks protect; read before changing tests                                             |
| [Pipelines](guides/pipelines.md)                 | Operator commands and pipeline design                                                           |
| [Lessons](guides/lessons.md)                     | Rules learned from failures; read before database writes, unattended runs or measurements       |
| [Ponytail debt](ponytail-debt.md)         | Deliberate shortcuts and when to revisit them                                                   |

## Product direction and plans

Plans describe intended behavior. Use the [roadmap](ROADMAP.md) to determine what is still open;
a proposed feature in a plan is not evidence that it is available in the app.

| Document                                     | Covers                                               |
| -------------------------------------------- | ---------------------------------------------------- |
| [Strategy](plans/strategy.md)                      | Product direction and funding narrative              |
| [Theory](plans/theory.md)                          | Intellectual framework                               |
| [Knowledge system](plans/knowledge-system-plan.md) | Object model, gaps and the roadmap index in §9       |
| [Data model target](plans/data-model-target.md)    | No rebuild: places, feature-to-place links and activities, the tables bets 1a and 2 need |
| [Model dedup](plans/model-dedup-plan.md)           | One fact, one writer: the duplicated series, edition and JSON columns, measured |
| [Digest pipeline](plans/digest-pipeline-plan.md)   | How a map goes from found to linked: machine proposes, person decides, every decision timed (bet 1a) |
| [Review page](plans/review-page-plan.md)           | The offline review pages moved into the app: one engine, one record, open to contributors later |
| [Search](plans/search-plan.md)                     | Finding labels, shapes and period sources            |
| [Usage measurement](plans/usage-measurement-plan.md) | Study, grant and support evidence; opt-in journeys and confirmed outcomes |
| [Usage evidence sheet](plans/usage-evidence-template.md) | Monthly template for an aggregate usage report |
| [Catalog](plans/catalog-plan.md)                   | The public list: columns, facets, speed, search       |
| [Walk](plans/walk-plan.md)                         | Proposed district walks; forks the separate HACW app |
| [Evidence chain](plans/evidence-chain-plan.md)     | Source-backed claims, review and reuse               |
| [Platform design](plans/platform-design.md)        | Proposed shared platform architecture                |

## Research records

These are dated findings and experiments. Read their dates, inputs and caveats before reusing a result.

| Document                                                       | Covers                                                          |
| -------------------------------------------------------------- | --------------------------------------------------------------- |
| [Image processing record](research/image-processing-record.md) | Methods and recorded measurements, with links to their evidence |
| [Field comparison](research/field-comparison.md)               | Comparison with published research and deployed systems         |
| [Worked example: 1882](research/worked-example-1882.md)        | One sheet taken through the pipeline                            |
| [1882 feature-layer plan](plans/image-processing-1882-plan.md) | Repo consolidation, frozen water and the block comparison |
| [River reconstruction](research/river-reconstruction.md)       | Exploratory 1882/1898 work; no river layer approved             |
| [Allmaps series note](research/allmaps-series-note.md)         | Dated technical note on georeferencing two map series           |
| [Journals](journals/README.md)                                 | Dated runs, audits and handoffs                                 |
| [Paper](paper/README.md)                                       | Manuscript, claim evidence, figures and review records          |
| [Analysis folders](../work/analysis/README.md)                 | Scripts, figures and review packs behind experiments            |

## Historical and private material

- [Archive](archive/README.md): frozen design and implementation records.
- [Roadmap record](roadmap-record.md): frozen on 2026-09-22; use it for past decisions and costs.
- `private/`: local, gitignored outreach and personal material. Never publish it or copy it into a public index.
- `guides/system-graph*.svg` and `.png`: illustrations used by [System graph](guides/system-graph.md).

## Keeping this directory useful

Link a new guide from this index and describe its audience and purpose in its opening paragraph.
Put dated investigations in `journals/`; keep frozen material in `archive/` and label it as historical.
Keep open tasks in `ROADMAP.md` and update the matching item in `plans/knowledge-system-plan.md` §9 together.
