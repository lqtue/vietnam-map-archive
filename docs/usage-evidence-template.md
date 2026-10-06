# Monthly usage evidence sheet

Copy this template for an aggregate report after live measurement begins. Keep
participant contacts and unapproved quotations in `docs/private/`, never in a
public report. Definitions and instrumentation coverage are in
[the measurement plan](usage-measurement-plan.md).

## Reporting basis

- Reporting period and timezone:
- Measurement first enabled:
- Instrumentation version / covered surfaces:
- Sources and retrieval dates:
- Staff, test and preview exclusions:
- Consent and browser-blocking limitations:
- Known outages, missing events or changed definitions:

Use “unavailable” for missing measurements; do not substitute zero. Never merge
Cloudflare estimated visits, GA4 browsers and registered accounts into one count.

## Reach and useful actions

| Measure | Count / denominator | Source | Limit |
| --- | --- | --- | --- |
| Estimated visits | | Cloudflare | Sampled; staff not necessarily excluded |
| Consented active browsers / returning browsers | | GA4 | Devices/cookies, not unique people; opt-in coverage |
| Settled search events / zero-result events | | GA4 | Only covered search surfaces; no raw search terms |
| Search result opens | | GA4 | Event counts, not linked completed tasks |
| Map opens by covered surface | | GA4 | Intent, not successful rendering |
| Source opens / completed exports | | GA4 | Does not prove citation or external reuse |

State whether every numerator is unique users, sessions, attempts or event counts.
Do not divide search-result click events by search events and call it a per-attempt
conversion rate without a method for matching attempts and repeated clicks.

## Contribution evidence

Report Studio and Shapes separately. Identify whether each value is a browser
observation or an authoritative stored outcome; browser-blocking means they may
not reconcile. Empty projects are not meaningful saved contributions.

| Workflow | Tool entries | Meaningful starts | Observed save successes | Stored submissions | Accepted outcomes |
| --- | --- | --- | --- | --- | --- |
| Shapes | | | | | |
| Studio | | | | | |

List uncovered workflows and available timestamps. Do not attribute backfills,
imports or staff-only OCR to public volunteers.

## Voluntary use evidence

- Reported research/teaching/local-history use:
- What the archive enabled, in the participant's own account:
- Evidence link, where voluntarily supplied:
- Permission to quote / publish and permitted attribution:
- Sampling limitations (self-selection, recruitment channel, small sample):

Do not infer motivation, institutional affiliation or scholarly impact from
browsing logs. Publication of participant details is opt-in and separate from
analytics consent.

## Study or support experiment

- One question and the predefined outcome:
- Recruitment/eligibility and exposure rule:
- Period and sample size:
- Completion/failure observations and reasons from participants:
- For support: invitation exposures, visits and provider-confirmed payments:
- No support flow yet: mark these measures unavailable.

Record any definition/product changes before comparing periods. Small counts
support descriptive findings, not causal claims or a confident growth forecast.

## Decision

State one finding, its evidence and limitation, then one proposed action. Specify
what the next reporting period will measure to assess that action.
