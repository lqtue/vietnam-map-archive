# contracts

Part of the **operations** layer — see [ATLAS](../docs/ATLAS.md).

The archive's public output shapes, written down once so more than one consumer
can rely on them. Design rationale in `docs/plans/platform-design.md` §3.

**The rule for adding a file here: name the second consumer.** A shape with one
consumer belongs in that consumer's own types, not in this directory. "Something
will need it later" is not a second consumer.

| Contract | Producer | Consumers today |
|---|---|---|
| `context.schema.json` | `GET /api/context` (`context_at`, migration 066) | /explore's here-across-time panel · the District 4 notebook · the event app's "what stood here" · any planner querying an area |
| `label-hit.schema.json` | `GET /api/search?include=labels` (`search_labels`, migration 065) | /catalog results · /explore browse pane · the press panel, which takes its query from a hit |
| `footprint-feature.schema.json` | `GET /api/export/footprints` (GeoJSON) | /explore's fabric layer · the District 4 notebook · QGIS |

These are **descriptive, not generated**: nothing compiles them into types, and
the app's own types still come from `supabase gen types`. What they buy is a
single written definition plus the write smoke in `tests/write.spec.ts`, which
validates the live responses against them — so a field cannot quietly change
shape under a consumer that is not in this repo.

`ponytail:` JSON Schema by hand, checked by a ~50-line subset walker in
`tests/schemaCheck.ts` rather than a validator library. The only installed
validator is a transitive eslint dependency on draft-07, which would vanish on
any lockfile change. Adopt `ajv` properly if these ever outgrow the subset:
`type` (including unions with `null`), `required`, `properties`,
`additionalProperties`, `items`, and `enum`.
