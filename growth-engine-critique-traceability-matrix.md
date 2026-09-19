# FlipFlop Growth Engine — Critique Traceability Matrix

**Related documents:** Master Mega-PRD v1.1 and phase PRDs 01–07  
**Purpose:** Provide an auditable response to the earlier implementation review

## Status meanings

- **Resolved:** The requirement is explicitly defined in the revised documents.
- **Partially resolved:** The governing rule exists, but a provider, baseline, owner or implementation detail remains to be confirmed.
- **Still open:** A decision is required before the affected phase can be approved.
- **Superseded:** The original concern is no longer applicable because the MVP boundary changed.

## Traceability matrix

| Earlier critique | Status | Resolution / evidence | Remaining action |
|---|---|---|---|
| No enforceable release boundary | Resolved | Master §1.2 and §32 define MVP, roadmap phases, exclusions, feature flags and phase gates. | Confirm the existing implementation brief’s exact MVP provider list. |
| Scope was too broad for the current implementation | Resolved | Marketing MVP PRD limits Release 1 to social publishing and website analytics. | None before MVP planning. |
| No glossary or domain boundaries | Resolved | Master §33 defines product, build, listing, content, campaign, offer, voucher, audience, conversion and attribution terms. | Reconcile names with the existing database during architecture audit. |
| Ownership/source of truth unresolved | Resolved | Master §33.2 defines authority for customers, consent, catalogue, inventory, orders, profit, loyalty, content, channels and attribution. | Assign named technical owners in project configuration. |
| Approval rules contradictory | Resolved | Master §34 establishes approval by default, smallest consequential unit, roles, reapproval triggers, expiry and emergency pause. | Configure policy values in the deployed environment. |
| Approval policy not executable | Resolved | Master §49 defines default expiry, authorities, single-user behaviour, low-risk actions and retention. | Owner must confirm defaults before production. |
| Financial formula imprecise | Resolved | Master §§35 and 51 define revenue, VAT, COGS, fulfilment, fees, incentives, funding responsibility, FX and rounding. | Implement and reconcile the profitability API with worked examples. |
| Voucher funding could be double-counted | Resolved | Master §51 separates customer discount from incentive funding cost and defines funding responsibility. | Confirm supplier/marketplace funding contracts when applicable. |
| Attribution claims exceeded evidence | Resolved | Master §36 distinguishes observed, attributed, assisted and incremental outcomes and requires windows and evidence labels. | Implement the attribution service and synthetic test dataset. |
| Identity resolution was undefined | Resolved | Master §36.1 defines approved identifiers and prohibits assumed cross-device joining. | Confirm consent-approved identifiers with the privacy owner. |
| Consent/privacy requirements were shallow | Resolved | Master §37 defines purposes, lawful basis, withdrawal propagation, retention, deletion, exports and profiling notices. | Complete the DPIA/privacy review before owned-audience release. |
| External connectors underspecified | Partially resolved | Master §38 and each phase define connector contract fields, capabilities, idempotency, reconciliation and failure states. | Add exact provider/API/scope details in provider-specific implementation briefs. |
| State machines incomplete | Resolved | Master §39 defines campaign, content, newsletter, offer and agent states plus transitions and concurrency rules. | Add provider-specific states only where required by an approved connector. |
| Numeric goals and baselines missing | Partially resolved | Master §44 adds initial launch thresholds for reliability, freshness, audit, availability, accessibility and redemption correctness. | Record current baselines and final business KPIs before launch. |
| Exact MVP channels unclear | Partially resolved | MVP PRD limits channels to the existing implementation configuration rather than inventing providers. | Copy the exact provider list and capability matrix from the existing Marketing brief. |
| Social moderation scope missing | Resolved | MVP and Master §40.3 limit initial support to monitoring/surfacing; replies, deletion and hiding require a later phase. | None for MVP. |
| Newsletter deliverability missing | Resolved | Owned Audience PRD and Master §40.4 define sender identity, authentication, bounces, complaints, suppression, rendering and outage behaviour. | Select the concrete email provider. |
| Blog CMS integration missing | Resolved | Editorial PRD and Master §40.1 define preview, sync, slugs, canonical URLs, sitemap/RSS, rollback and publication confirmation. | Confirm the storefront CMS interface. |
| Media licensing incomplete | Resolved | Editorial PRD and Master §§10, 40 require provenance, licence status, model/prompt records and review. | Complete asset-source register for production media. |
| Agent runtime limits missing | Resolved | Master §42 and Controlled Optimisation PRD define tool scopes, budgets, timeouts, retries, PII handling and escalation. | Select Hermes/local/hosted providers per environment. |
| Audience freshness missing | Resolved | Master §41.1 defines evaluation mode, staleness, entry/exit, consent, suppression and provider export status. | Configure freshness per audience type. |
| Loyalty source of truth unclear | Resolved | Master §33.2 and Offers/Loyalty PRD make Loyalty Service authoritative for balances and ledger transactions. | Confirm the existing/future Loyalty Service API. |
| Experiment design missing | Resolved | Master §41.2 and Analytics/Learning PRD require hypothesis, holdout, randomisation, sample size, stopping rules and contamination handling. | Choose the experiment storage and reporting implementation. |
| RBAC/separation of duties missing | Resolved | Master §§34 and 43 define roles, permissions and self-approval rules. | Seed roles in the authentication system. |
| Operational requirements missing | Resolved | Master §44 defines initial targets, SLAs/RPO/RTO requirements, observability and cost ceilings. | Confirm final production SLOs after MVP measurement. |
| API contracts too vague | Partially resolved | Master §23, §38 and §50 define endpoint groups, connector contracts and dependency interfaces. | Produce concrete OpenAPI contracts during implementation planning. |
| Accessibility standard missing | Resolved | Master §44 explicitly requires WCAG 2.2 AA. | Add automated and manual accessibility tests to CI/release gates. |
| Retention/storage controls missing | Resolved | Master §37 and §44 define retention classes, deletion/anonymisation and storage controls. | Confirm legal retention periods with the business/privacy owner. |
| Mega-PRD conflicted with social PRD | Resolved | Master §33 ownership and phase PRDs define Social Channel Service ownership; Growth orchestrates campaigns without duplicating social publishing ownership. | Reconcile exact route names with the existing social implementation. |
| Organic post promotion implied universal availability | Resolved | Paid Acquisition PRD requires capability discovery; promotion is shown only where the connector supports it. | None beyond connector implementation. |
| Asset resizing versus generated media approval unclear | Resolved | Controlled Optimisation permits resizing approved assets as low risk; newly generated/materially edited media requires review. | Encode asset mutation classification in Media Service. |
| Newsletter missed-send behaviour missing | Resolved | Owned Audience PRD defaults to skip and notify when there is no suitable content or the provider is unavailable. | Configure holiday calendar and notification destination. |
| Placeholder thresholds such as £X/Y% | Resolved | Offers/Loyalty PRD and Master §49 use named configuration fields. | Set production values after margin review. |
| Offer lifecycle did not cover no-code offers | Resolved | Offers/Loyalty PRD separates `offer` lifecycle from optional `voucher_code` and redemption records. | None. |
| Campaign parent versus provider campaign unclear | Resolved | Master glossary defines Growth Campaign as parent and provider-specific executions as children. | Implement foreign-key relationships and reconciliation IDs. |
| Provenance did not cover every channel | Resolved | Master §40.2 makes provenance mandatory for blog, social, newsletter and paid advertising. | Add provenance validation to every publication path. |
| End-to-end examples appeared to bypass approval | Resolved | All phase PRDs require approval before external side effects; examples now represent preparation plus approval. | Ensure workflow UI cannot skip the approval state. |
| Documents structurally malformed | Resolved in current source set | The revised local documents contain no blank bullets/headings or placeholder policy values; Master §52 adds mechanical integrity checks. | Run the same checks in CI and inspect rendered Markdown before approval. |

## Open decisions before implementation

1. Exact social providers and API versions for the MVP.
2. Concrete email and website analytics providers.
3. Named owners for Consent, Approval, Agent Runtime, Loyalty and Profitability services.
4. Current baseline metrics and final commercial launch KPIs.
5. Production retention periods where legal review has not yet confirmed the defaults.
6. Provider-specific OpenAPI contracts and fixture payloads.

These open items do not invalidate the phased product design, but they must be resolved before the affected phase receives an implementation-ready approval.

