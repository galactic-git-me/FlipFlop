# FlipFlop Growth Engine — Critique Traceability Matrix

**Related documents:** Master Mega-PRD v1.2 and phase PRDs 01–07  
**Purpose:** Auditable response to the implementation review

**Version alignment:** Each phase PRD explicitly declares `flipflop-growth-engine-mega-prd.md` v1.2 as its parent specification: 01 Marketing MVP, 02 Editorial Expansion, 03 Owned Audience, 04 Offers & Loyalty, 05 Paid Acquisition, 06 Analytics & Learning and 07 Controlled Optimisation.

## Status and evidence definitions

| Status | Meaning |
|---|---|
| Resolved | The requirement is explicitly defined and internally consistent in the source document. |
| Resolved with implementation gate | The normative rule is defined, but implementation evidence or configuration approval is still required. |
| Partially resolved | The architecture or rule exists, but a provider, owner, baseline or concrete contract remains open. |
| Still open | The source documents require repair or a decision before the finding can be considered resolved. |
| Superseded | The concern is no longer applicable because the MVP boundary changed. |

| Evidence quality | Meaning |
|---|---|
| Normative requirement | A governing rule in the Master Mega-PRD. |
| Phase requirement | A scope, workflow or acceptance requirement in a phase PRD. |
| Configuration default | A named policy value that must be confirmed before production. |
| Implementation dependency | A provider, service or API contract that must be supplied. |
| Acceptance evidence | A test result, fixture, baseline or operational measurement; not merely a written requirement. |

## Traceability

| Review finding | Status | Evidence quality | Correct evidence and resolution | Remaining action |
|---|---|---|---|---|
| No enforceable release boundary | Resolved | Normative requirement + phase requirement | Master §§1.2 and 32 define MVP, roadmap phases, exclusions, feature flags and gates; MVP PRD defines the first release. | Confirm exact MVP providers from the existing implementation brief. |
| Scope too broad for current implementation | Resolved | Phase requirement | Marketing MVP PRD explicitly limits Release 1 to social publishing and website analytics. | None for scope; implementation must honour the exclusions. |
| No glossary or domain boundaries | Resolved | Normative requirement | Master §33 defines product, build, listing, content, campaign, offer, voucher, audience, conversion and attribution. | Reconcile names with the existing database. |
| Source-of-truth ownership unresolved | Resolved with implementation gate | Normative requirement + implementation dependency | Master §33.2 assigns authority to Customer, Consent, Catalogue, Inventory, Order, Profitability, Loyalty, Content, Channel and Attribution services. | Assign named technical owners and interfaces. |
| Approval rules contradictory/incomplete | Resolved with implementation gate | Normative requirement + configuration default | Master §§34 and 49 define default approval, scope, roles, expiry, reapproval, emergency pause and low-risk actions. | Owner must confirm policy defaults and seed roles. |
| Approval policy not executable | Resolved with implementation gate | Configuration default | Master §49 specifies 24-hour approval validity, single-user behaviour, emergency authorities, automatic-action authorisation and audit retention. | Implement policy storage and approval tests. |
| Financial formula imprecise | Resolved with implementation gate | Normative requirement + acceptance evidence | Master §§35 and 51 define VAT, revenue, COGS, fulfilment, fees, discount value, incentive funding, FX and rounding. | Implement profitability API and reconcile worked examples. |
| Voucher funding may be double-counted | Resolved with implementation gate | Normative requirement | Master §51 states that customer discount reduces revenue and funding cost is separately recorded according to funding responsibility. | Confirm supplier/marketplace funding contracts. |
| Attribution claims exceed evidence | Resolved with implementation gate | Normative requirement + acceptance evidence | Master §36 and Analytics/Learning PRD distinguish observed, attributed, assisted and incremental outcomes. | Run synthetic attribution and refund tests. |
| Identity resolution undefined | Resolved with implementation gate | Normative requirement | Master §36.1 defines approved identifiers and prohibits assumed cross-device joining. | Confirm lawful identifiers with privacy owner. |
| Consent/privacy requirements shallow | Resolved with implementation gate | Normative requirement + implementation dependency | Master §37 defines purposes, withdrawal, propagation, retention, deletion, exports and profiling notices. | Complete DPIA/privacy review before Owned Audience. |
| External integrations underspecified | Partially resolved | Implementation dependency | Master §38 and each phase connector section define contract fields, capabilities, idempotency and reconciliation. | Add exact providers, APIs, scopes and fixture payloads. |
| State machines incomplete | Resolved with implementation gate | Normative requirement + phase requirement | Master §39 and phase PRDs define campaign, content, newsletter, offer and agent states, transitions and concurrency rules. | Add provider-specific states only when required. |
| Numeric goals and baselines missing | Partially resolved | Normative requirement + configuration target | Master §44 defines initial operational thresholds; these are written targets, not test results or measured baselines. | Record current baselines and final commercial KPIs. |
| Exact MVP channels unclear | Partially resolved | Implementation dependency | MVP PRD delegates provider selection to the existing implementation configuration. | Copy the exact provider/capability list into configuration. |
| Social moderation scope missing | Resolved | Phase requirement | MVP PRD and Master §40.3 limit MVP to monitoring/surfacing; replies, deletion and hiding are later scope. | None for MVP. |
| Newsletter deliverability missing | Resolved with implementation gate | Phase requirement + implementation dependency | Owned Audience PRD §5 and Master §40.4 define sender identity, authentication, bounces, complaints, suppression, rendering and outage behaviour. | Select the concrete email provider and test fixtures. |
| Blog CMS integration missing | Resolved with implementation gate | Phase requirement + implementation dependency | Editorial PRD §5 and Master §40.1 define preview, sync, slug collision, canonical URL, sitemap/RSS, rollback and deletion. | Confirm storefront CMS interface. |
| Media licensing incomplete | Resolved with implementation gate | Normative requirement + phase requirement | Editorial PRD §§4–6 and Master §§9 and 40 define provenance, licence status, model/prompt records and review. | Complete production asset-source register. |
| Agent runtime limits missing | Resolved with implementation gate | Normative requirement + phase requirement | Master §42 and Controlled Optimisation PRD §4 define tool scopes, budgets, timeouts, retries, PII handling and escalation. | Select Hermes/local/hosted provider routing. |
| Audience freshness missing | Resolved with implementation gate | Normative requirement | Master §41.1 defines evaluation mode, maximum staleness, entry/exit, consent and suppression. | Configure freshness per audience. |
| Loyalty source of truth unclear | Resolved with implementation gate | Normative requirement + implementation dependency | Master §33.2 and Offers/Loyalty PRD §§2 and 4 make Loyalty Service authoritative for balances and ledger transactions. | Confirm Loyalty Service API. |
| Experiment design missing | Resolved with implementation gate | Normative requirement + phase requirement | Master §41.2 and Analytics/Learning PRD §5 require hypothesis, holdout, randomisation, sample size, stopping and contamination rules. | Choose experiment storage/reporting implementation. |
| RBAC/separation of duties missing | Resolved with implementation gate | Normative requirement | Master §§34 and 43 define roles, permissions and self-approval behaviour. | Seed roles and test author/approver separation. |
| Operational requirements missing | Resolved with implementation gate | Normative requirement + configuration target | Master §44 defines initial targets, RPO/RTO, observability, browser and cost requirements; acceptance evidence must be generated during implementation. | Confirm production SLOs after MVP measurement. |
| API contracts too vague | Partially resolved | Implementation dependency | Master §§23, 38 and 50 define endpoint groups, dependency interfaces and connector contract fields. | Produce concrete versioned OpenAPI contracts. |
| Accessibility standard missing | Resolved with implementation gate | Normative requirement + acceptance evidence | Master §44 requires WCAG 2.2 AA. | Add automated and manual accessibility test evidence. |
| Retention/storage controls missing | Partially resolved | Normative requirement + implementation dependency | Master §§37, 44 and 49 define retention classes and defaults. | Obtain legal approval for final retention periods. |
| Mega-PRD conflicted with social PRD | Resolved | Normative requirement + phase requirement | Master §33.2 and MVP PRD assign publishing ownership to Social Channel Service; Growth orchestrates without duplicating it. | Reconcile exact routes with existing implementation. |
| Organic post promotion implied universal availability | Resolved | Phase requirement | Paid Acquisition PRD §2 requires capability discovery; promotion is available only where the connector supports it. | None beyond connector implementation. |
| Asset resizing versus generated-media approval unclear | Resolved | Normative requirement | Controlled Optimisation PRD §3 permits resizing approved assets as low risk; new/materially edited media requires review. | Encode mutation classification in Media Service. |
| Newsletter missed-send behaviour missing | Resolved | Phase requirement | Owned Audience PRD §3 defaults to skip and notify when content is unsuitable or provider unavailable. | Configure holiday calendar and notification destination. |
| Placeholder discount thresholds | Resolved | Configuration default | Offers/Loyalty PRD §5 and Master §49 use named fields such as `maximum_offer_exposure_gbp` and `maximum_discount_percent`. | Set production values after margin review. |
| Offer lifecycle did not cover no-code offers | Resolved | Phase requirement | Offers/Loyalty PRD §§2 and 6 separate offer lifecycle, optional voucher code and redemption event. | None. |
| Campaign parent versus provider campaign unclear | Resolved | Normative requirement | Master §33 defines Growth Campaign as parent and channel/provider executions as children. | Implement foreign-key and reconciliation IDs. |
| Provenance did not cover every channel | Resolved | Normative requirement | Master §40.2 requires provenance for blog, social, newsletter and paid adverts. | Add validation to each publication path. |
| End-to-end examples appeared to bypass approval | Resolved | Phase requirement | All phase PRDs require approval before external side effects; Controlled Optimisation limits automation by policy. | Test that UI cannot skip approval. |
| Documents structurally malformed | Resolved implementation gate | Acceptance evidence | Master §52 defines integrity checks. Rendered validation completed for all nine documents; source checks and table checks passed. This does not imply implementation or test evidence. | Retain the validation checks in CI and re-run them after future document edits. |

## Current source audit

The local source audit for this matrix checked:

- blank bullets;
- blank headings;
- placeholder policy values in PRDs;
- table row delimiter consistency;
- presence of phase headings and launch gates.

A clean document proves only that the source is structurally coherent. It does not prove that connectors, tests, policies or production services exist.

## Open decisions before implementation approval

1. Exact social providers and API versions for the MVP.
2. Concrete email and website analytics providers.
3. Named owners for Consent, Approval, Agent Runtime, Loyalty and Profitability services.
4. Current baselines and final commercial KPIs.
5. Legally approved retention periods.
6. Versioned OpenAPI contracts and provider fixtures.
