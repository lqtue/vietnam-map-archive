# Vietnam Map Archive documentation

The one index. Every doc is one of four kinds, and the kind says how far to trust it:

| Kind | Folder | Trust it as |
| --- | --- | --- |
| **Guide** | `guides/` | How things work now. Wrong means a bug in the doc. |
| **Plan** | `plans/` | Where things are going. A plan is not proof a feature exists; [ROADMAP](ROADMAP.md) says what is open. |
| **Record** | `research/`, `journals/`, `paper/` | True on its date, for its inputs. Read both before reusing a number. |
| **Frozen** | `archive/`, `roadmap-record.md` | History. Never cite as current. |

Folder by folder, with the layer each belongs to: the [Atlas](ATLAS.md) (generated).
Scripts, datasets and local experiments: the [work directory guide](../work/README.md).

## What do you want to do?

| I want to… | Start here |
| --- | --- |
| Know what VMA is, and the words for it | [Concept](CONCEPT.md): the line, four verbs, the goal, the scope |
| See what matters now, and why | [Now](NOW.md): the bets, the idea gate, who is on what |
| See what is open | [Roadmap](ROADMAP.md): the one backlog |
| Explore maps or contribute | [User guide](guides/user-guide.md) |
| Prepare and read a scanned sheet | [Reading a sheet](guides/digitalize-guide.md) |
| Manage the catalog and review queues | [Admin tooling](guides/admin-tooling.md) |
| See how the archive fits together | [Ontology](ontology.md), [system graph](guides/system-graph.md), [knowledge system](plans/knowledge-system-plan.md) |
| Change the app | [Architecture](guides/architecture.md), then the guides below |
| Run OCR, segmentation or georeferencing | [Pipelines](guides/pipelines.md) and the [work directory guide](../work/README.md) |
| Build or deploy | [Deployment](guides/deploy.md) |
| Find a research result | [Research records](research/README.md) and the [journal index](journals/README.md) |
| Read the manuscript | [Paper guide](paper/README.md) |

## Guides

| Guide | Covers |
| --- | --- |
| [Ontology](ontology.md) | The terms for what VMA holds, by layer: built, and proposed |
| [Architecture](guides/architecture.md) | The app: layering, every route, the map runtime, data access, components and styling |
| [Design system](guides/design-system.md) | Visual language, tokens and styling |
| [Page specs](guides/pages/README.md) | Every web page in one template, with known bugs and house-rule gaps |
| [API](guides/api.md) | Server routes and their contracts |
| [Database](guides/db-guidelines.md) | Schema decisions; also read [Supabase instructions](../supabase/CLAUDE.md) |
| [Testing](guides/testing.md) | What each check protects; read before changing tests |
| [Pipelines](guides/pipelines.md) | Index: where each tool's commands and design now live |
| [Check register](guides/check-register.md) | Each check in the series pipeline: what it reads, whether it could have caught a known error, and what it has done |
| [Lessons](guides/lessons.md) | Rules learned from failures; read before database writes, unattended runs or measurements |
| [Ponytail debt](ponytail-debt.md) | Deliberate shortcuts and when to revisit them |

## Plans

| Plan | Covers |
| --- | --- |
| [Strategy](plans/strategy.md) | Product direction and funding |
| [Theory](plans/theory.md) | The intellectual framework |
| [Knowledge system](plans/knowledge-system-plan.md) | The object model, its gaps, and every ROADMAP item by layer (§9) |
| [Data model target](plans/data-model-target.md) | No rebuild: places, feature-to-place links and activities, the tables bets 1a and 2 need |
| [Model dedup](plans/model-dedup-plan.md) | One fact, one writer: the duplicated series, edition and JSON columns, measured |
| [Digest pipeline](plans/digest-pipeline-plan.md) | Found to linked: machine proposes, person decides, every decision timed (bet 1a) |
| [Review page](plans/review-page-plan.md) | The offline review pages moved into the app |
| [Series-led admin units](plans/series-admin-saigon-plan.md) | Admin units and Saigon's states traced through the map series; the pilot area, link types, phases (bet 1c) |
| [1882 feature layer](plans/image-processing-1882-plan.md) | Repo consolidation, frozen water and the block comparison (bet 1b) |
| [Corpus](plans/corpus-plan.md) | Every map of Vietnam we know of: one row per source, measured (bet 3) |
| [Search](plans/search-plan.md) | Finding labels, shapes and period sources |
| [Catalog](plans/catalog-plan.md) | The public list: columns, facets, speed, search |
| [Map-type audit](plans/catalog-map-type-audit.md) | The original-map review and open classification questions |
| [Evidence chain](plans/evidence-chain-plan.md) | Source-backed claims, review and reuse |
| [Platform design](plans/platform-design.md) | Proposed shared platform architecture |
| [Usage measurement](plans/usage-measurement-plan.md), [evidence sheet](plans/usage-evidence-template.md) | Study, grant and support evidence |
| [Walk](plans/walk-plan.md) | Proposed district walks (parked); forks the separate HACW app |

## Records

| Record | Covers |
| --- | --- |
| [Research records](research/README.md) | Methods, comparisons and worked examples, each dated |
| [Journals](journals/README.md) | Dated runs, audits and handoffs |
| [Paper](paper/README.md) | Manuscript, claim evidence, figures and review records |
| [Analysis folders](../work/analysis/README.md) | Scripts, figures and review packs behind experiments |

## Rules for this folder

- **A new doc** goes in the folder for its kind and gets a line in this index. Its first paragraph
  says who it is for.
- **A journal** is `journals/YYMMDD-slug.md` and opens with Question → Answer → So what.
- **ROADMAP** holds open items only. Close one by deleting it, and remove its name from
  [knowledge system §9](plans/knowledge-system-plan.md#9-open-work-by-layer) in the same commit;
  CI fails until the two match.
- **`CHANGELOG.md` and `/changelog`** (`releases.ts`) are separate texts for separate readers;
  add a release to both. The version moves on a structural change, not a build.
- **`private/` is gitignored.** Never publish it or link it from a public page.
