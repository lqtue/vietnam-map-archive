# Purposeful usage measurement

Updated 6 October 2026. This plan replaces the proposed custom telemetry collector
and Usage dashboard with GA4 journey measurement, existing database outcomes and
voluntary qualitative evidence. Implementation is tracked as `usage-measurement`
in [ROADMAP](ROADMAP.md). The goal is evidence for product decisions, a bounded
user study, grant applications and eventual support invitations.

## Questions and evidence

| Purpose | Question | Evidence and limits |
| --- | --- | --- |
| Product and study | Can visitors find a map for a place and period and use it? | Search → result → map → source/export; zero-result searches and voluntary task sessions. A result opening is not proof of task success. |
| Grants | What public benefit does VMA provide? | Collection use, repeat browsing, confirmed contributions, permissioned research/teaching examples. Traffic alone does not establish scholarly impact. |
| Donations | When is a support invitation useful and acceptable? | Eligible invitation exposures → support visits → provider-confirmed payments. Clicks are not donations. No payment integration is introduced in this implementation. |

The baseline is private at `docs/private/usage-2026-10-06.md`. Cloudflare visits are
sampled browser-traffic estimates, auth sign-ins are not active-user counts, and
map-open counters are not unique people. Do not subtract registered users from
traffic estimates to infer anonymous visitors.

## Architecture and initial scope

- Cloudflare remains the source for overall traffic and performance.
- GA4 records consented journeys and repeat browser use. It is not a census and
  does not identify unique people or independently verified signed-in readers.
- Existing Supabase records establish stored contributions and review outcomes.
  Client `save_success` is an observed successful persistence response; authoritative
  totals come from database records. No new analytics database or admin dashboard.
- Search Console supplies acquisition queries and landing pages, separately from
  internal searches.
- Optional purpose responses, reuse stories and study recruitment are a later,
  explicitly designed step. They are not silently collected by the initial code.

Core holds the pure allowlisted event contract; data holds a best-effort browser
adapter; existing feature/controller hooks record meaningful actions. Root layout
owns identity classification and navigation. Leaf UI primitives have no analytics
dependency. No new map runtime, backend collector, or database migration.

## Events and denominators

| Event | Trigger | Interpretation |
| --- | --- | --- |
| `page_view` | Real canonical page/mode entry | Map selection, camera motion and arbitrary query/hash changes are not new pages. |
| `map_open` | Existing intentional map-open seam | Opening intent, not proof that tiles rendered. Existing map-open history stays separate. |
| `search_completed` | Latest nonempty search settles | Result count only; zero results are meaningful, failed requests are not zero-result searches. |
| `search_result_open` | A displayed result is selected | Useful next step, not research success. |
| `contribution_open` | A public workflow is entered | Opening a tool is not a contribution. |
| `draft_started` | First meaningful edit in an attempt | Empty project creation, titles and merely selecting a map do not qualify. |
| `save_success` | Successful persistence of nonempty work | Workflow-specific, distinct from submission/reviewer acceptance; retries must not fabricate completion. |
| `source_open` | Existing source link is followed | Source access intent; external use remains unknown. |
| `export_completed` | An existing export actually completes | Output produced, not proof of downstream reuse. |
| Future support events | Invitation shown and support link selected | Reserved contract only until a support flow exists. |
| Future confirmed donation | Verified payment-provider receipt | Browser tracker rejects donation-completion events. No fabricated payment outcome. |

Implement hooks only where these triggers can be identified reliably. Maintain a
coverage table below rather than imply that every surface is instrumented. Do not
log every keystroke, map pan, vertex, autosave, edited text or drawn geometry.
Studio and Shapes are separate workflows. Staff-only OCR does not belong in the
public contribution funnel. External Allmaps completion is unknown unless a
result is independently confirmed.

## Identity, consent and boundaries

Tracking is disabled until a production GA4 property is configured and the visitor
explicitly opts in. No Google script is loaded before opt-in. A compact choice
allows declining and later changing/withdrawing the choice. Honor Do Not Track and
Global Privacy Control; blocked storage or tracking must not break the product.

Only `maparchive.vn` contributes. Local development, preview hosts, unknown roles
and staff are excluded. Block signed-in activity until role resolution and on
identity transitions. Account state is `guest` or `reader`, without sending an
account UUID, email or GA User-ID. Client role classification is a best-effort
reporting filter, not a server-enforced security boundary. Role failures produce
missing coverage rather than labeling staff as readers.

No raw search terms, arbitrary URLs, names, coordinates, user geometry, OCR edits,
free-text survey answers or custom IP/user-agent logging. Use bounded enum fields,
public map UUIDs and result counts. Canonical page paths must not disclose private
project identifiers or free-text place queries. GA has its own network/browser
collection; application code does not promise IP-free collection by Google.

Cookie/device-based repeat use is approximate. Opt-outs, browser restrictions,
ad blockers and staff exclusion create coverage gaps. Record the measurement
start, consent rules and exclusions with every published report.

## GA4 setup and verification

1. Open [Google Analytics](https://analytics.google.com/), create the account/property
   named Vietnam Map Archive, choose Vietnam time (UTC+7) and VND, then create a
   Web stream for `https://maparchive.vn`. Copy its public `G-…` Measurement ID.
   See [Google’s setup guide](https://support.google.com/analytics/answer/14183469). Configure
   `PUBLIC_GA_MEASUREMENT_ID=G-…` in the appropriate Cloudflare build environment.
   The public ID is configuration, not a secret. Keep it unset until setup is ready.
2. Disable Enhanced Measurement for this stream, including automatic history
   pageviews, search, forms and outbound-link tracking. `send_page_view: false`
   alone does not disable history pageviews. See
   [Google's manual pageview guidance](https://developers.google.com/analytics/devguides/collection/ga4/views).
3. Leave Google Signals, advertising personalization and User-ID off. Register
   only needed low-cardinality event dimensions (surface, workflow, actor/action);
   avoid high-cardinality map IDs as custom dimensions unless needed for a bounded
   analysis. Choose and document the property retention period, initially two months
   for the 6–8 week pilot; retain aggregated monthly evidence separately.
4. No duplicate Google tag, Tag Manager container, or analytics plugin. Set clean
   page location, route title and empty referrer explicitly. Document the resulting
   limitation on referral attribution; use Cloudflare/Search Console for acquisition.
5. Verify no requests before consent, after withdrawal, under DNT/GPC, on previews
   or for staff. Inspect network payloads for raw URL/query leakage. Check actual
   initial/navigation pageviews and same-page map/camera changes separately.
6. Verify settled search, result selection, map opening and meaningful save hooks.
   A failed script/collector must never block map access or saving. Use mocks or
   local fixtures for write journeys; do not alter production drafts for tests.

The application cannot change a GA4 property's Enhanced Measurement settings.
Property access and the public ID are activation dependencies, not reasons to
leave implementation incomplete. Production enablement and live verification
remain separate from local implementation.

## Study and monthly evidence protocol

Collect a 6–8 week baseline after live verification. Start with one study question:
“Can visitors find a historical map of their chosen place and period?” Record the
task, entry surface, completion criterion, time, obstacles and participant's own
account of success. Recruit voluntarily; keep contact details separate from event
logs, and obtain explicit permission before publishing quotations or identifiable
reuse stories. A research publication may require a separate ethics protocol;
routine analytics consent is not consent to a recruited study.

Optional purpose choices could be research, teaching, local history, family
history and browsing. A separate reuse question can invite a project/class example.
Do not infer these motivations from a map opening. No survey/recruitment endpoint
or personal-response database is added in the initial implementation.

Use the [monthly evidence template](usage-evidence-template.md). Each sheet records:

- Period, sources, consent/coverage limitations and measurement start.
- Consented reach and returning browser activity, separately from Cloudflare.
- Search attempts, zero-result share and result-opening share with denominators.
- Collection use and source/export actions, without claiming downstream impact.
- Studio/Shapes starts and saves separately; authoritative stored/reviewed totals.
- Permissioned research/teaching examples and unresolved usability obstacles.

Inspect counts before percentages where samples are small. Do not claim causality
or established conversion improvement from a few attempts. Identify one product
change from the evidence, then compare the same events, definitions and windows.

## Delivery status and exit criteria

GA4 Measurement ID supplied by the owner: `G-LXBJSXMSTB` (public configuration).
Configured locally; Cloudflare production configuration and live verification remain pending.

Initial implementation: event contract/adapter, opt-in UI, role/navigation
integration, reliable hooks, regression tests and setup instructions. No deployed
tracking, paid support flow, surveys or custom analytics database are implied.

Exit for the complete workstream: configured and verified live tracking, a 6–8
week observation window, one evidence sheet and one justified product/study/support
recommendation. Keep `usage-measurement` open until those steps are completed.

### Instrumentation coverage

Implemented locally and reviewed:

| Surface | Covered triggers | Limits |
| --- | --- | --- |
| Root navigation | Canonical route/mode views, opt-in/withdrawal and guest/reader classification | Staff and unresolved roles excluded; client classification is not a security boundary. Unsupported/private paths pause collection. |
| Explore | Explicit map selection, label-hit map selection and year-step map replacement | No direct/deep-link initial opens; keep legacy map-open counters separate. |
| Command palette | Settled successful requests/cache results and map/place selection | No raw queries. Selection of page/label rows is not yet covered. |
| Full catalog | Settled query/facet map results and filtered row selection | Failed map reads suppressed. Result counts cover listed map records, not OCR label hits. Compact pickers and Explore sidebar searches are not covered. |
| Catalog drawer | Source link opening | Full sheet record source links and downstream external reuse are not yet covered. |
| Shapes | Selected-map entry, each valid drawn-shape attempt and acknowledged create | Draw persists immediately; this is not a long draft funnel. Modifications/deletions/review decisions are not GA events. |
| Studio | Project entry, first feature change since baseline, acknowledged changed nonempty save and nonempty GeoJSON export | Restoring projects and selecting maps do not start drafts. Local-only saves, failed/zero-row writes and empty saves do not count as save successes. |

Georeferencing, staff text/OCR, story-authoring, other export paths, support prompts,
payments, purpose surveys and recruited study collection are not instrumented in
this release. Their event vocabulary or proposed protocol does not imply coverage.

Verification: the consent browser check uses a routed production hostname and a
mock Google loader; it verifies no pre-consent request, one initial catalog view,
withdrawal disabling and no browser exceptions. This is not proof of receipt in
the real GA4 property. The pure suite covers consent/roles, route/parameter
sanitization, adapter failures and Studio draft/save distinctions. A mocked
PostgREST check ensures a zero-row Studio update cannot acknowledge a save.

