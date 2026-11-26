# Automated Growth Engine progress tracker

**Source:** Automated Growth Engine PRD v1.1, 26 November 2026.
**Last reviewed:** 26 November 2026.
**Scope:** All v1.1 acceptance criteria A01–A37, represented as atomic rows below. Release 2–6 requirements remain applicable target requirements; release boundaries control when they may be implemented. No exclusions have been approved.

## Status definitions

- **COMPLETE** — verified acceptance evidence exists. Counted in verified percentage.
- **IMPLEMENTED–UNVERIFIED** — source suggests implementation; required behavior/runtime evidence is absent.
- **PARTIAL** — some required outcomes exist, with material gaps.
- **NEEDS ENHANCEMENT** — an equivalent exists but must be strengthened to satisfy the criterion.
- **MISSING** — no adequate implementation evidence found in the audited paths.
- **BLOCKED** — requires owner/provider/legal/operational decision or approval.
- **CONFLICT** — specification conflict requires reconciliation.

Status is about verified outcomes, not the presence of a page or schema. “No test run” means the row cannot be COMPLETE unless its acceptance is the audit/document deliverable itself.

## Atomic acceptance trace

| ID | PRD ref | Atomic requirement / acceptance evidence | Status | Evidence inspected / verification | Remaining work / dependency | Priority / effort |
|---|---|---|---|---|---|---|
| A01.1 | A01, §3 | Marketing entry is visible in admin navigation. | IMPLEMENTED–UNVERIFIED | Sidebar has `/advertising-growth`; no browser run. | Browser/accessibility verification. | P1 / S |
| A01.2 | A01, §3 | Social Media is the initial default experience. | PARTIAL | One combined Advertising & Growth page; no Social Media default tab verified. | Align route/tab with approved product decision. | P1 / S |
| A01.3 | A01, §9 | Profile connection state distinguishes connected, disconnected, not configured, unsupported, failed. | NEEDS ENHANCEMENT | Seed service labels fixture accounts connected; capability separately says fixture. | Correct semantics; test states and token-health transitions. | P1 / M |
| A01.4 | A01, §3 | Owner can view and enable/disable a provider profile with health details. | PARTIAL | Accounts list endpoint exists; inspected page does not provide profile management controls. | Account settings/API and permission tests. | P1 / M |
| A02.1 | A02, §4 | Only authoritative eligible build event creates a launch draft; incomplete/hidden/sold/unavailable/missing URL is blocked. | MISSING | Growth API accepts manual post creation; no lifecycle intake found. | Identify authoritative hooks and implement fail-closed eligibility. | P1 / L |
| A02.2 | A02, §§4–5 | One campaign uses canonical build + launch revision across cross-listings; replay does not duplicate it. | MISSING | No campaign entity/event idempotency found in Growth models/API. | Canonical identity contract, unique key and replay tests. | P1 / L |
| A02.3 | A02, §§5–6 | Draft uses approved, rights-cleared media and correct platform variant. | PARTIAL | Revision stores media IDs/variants; asset approval exists; no automatic build asset selection or channel validation verified. | Asset rights/provenance and variant tests. | P1 / M |
| A02.4 | A02, §13 | Draft URL is canonical and preserves existing query while adding content/campaign/build/template tracking. | PARTIAL | Tracked URL preserves destination query and adds four UTM fields; build/template/variant IDs are not all represented. | Extend contract and test encoding/query preservation. | P1 / M |
| A03.1 | A03, §4 | Public promotion creates drafts with exact eligibility, terms, dates and discount. | MISSING | No promotion event integration found. | Define promotion source and exact snapshot. | P1 / L |
| A03.2 | A03, §4 | Private promotion never creates public marketing. | MISSING | No promotion intake/visibility gate found. | Add explicit visibility/consent gate and negative tests. | P1 / M |
| A03.3 | A03, §4 | Price/availability changes invalidate stale drafts; sold/expired state cancels pending execution and flags live content. | MISSING | No invalidation/reconciliation hook found. | Add lifecycle events and pre-dispatch revalidation. | P1 / L |
| A04.1 | A04, §4.1 | Rotation supports selected builds, ordering/selection, cadence, active dates/windows and repeat limits. | MISSING | No rotation collection/config/service found in inspected Growth code. | Define schema/API/worker and deterministic tests. | P1 / L |
| A04.2 | A04, §4.1 | Rotation excludes unavailable/incomplete/sold builds and records reason/last promotion. | MISSING | No rotation implementation found. | Implement eligibility, selection evidence and tests. | P1 / M |
| A04.3 | A04, §§4.1,8 | Rotation creates drafts requiring approval and respects frequency/conflicts. | MISSING | Approval exists for manual posts; rotation/frequency guard absent. | Integrate scheduler with approval and limits. | P1 / M |
| A05.1 | A05, §5 | Versioned templates render supported variables; missing required source facts fail closed. | PARTIAL | Revision stores copy/variants; no template registry/render/required-variable validator found. | Add versioned templates and fixture coverage. | P1 / M |
| A05.2 | A05, §5 | Platform variants enforce character/media/accessibility requirements. | PARTIAL | Connector character limit and asset validation helpers exist; full channel media/alt rules unverified. | Provider-specific validation tests. | P1 / M |
| A06.1 | A06, §8 | Exact revision/assets/claims/destinations/links/schedule are approved; edits invalidate approval. | NEEDS ENHANCEMENT | Revision rows and invalidation on edit exist; approval request records revision ID but exact approval hash/scope not shown. | Persist approval scope/hash and race tests. | P1 / M |
| A06.2 | A06, §8 | No external publish occurs before approval; scheduled execution is approved-only. | IMPLEMENTED–UNVERIFIED | `schedule_or_publish` requires approved; scheduler selects due scheduled rows; fixtures only; tests not run. | Execute isolated API/scheduler tests; verify no bypass. | P1 / M |
| A06.3 | A06, §8 | Dispatch revalidates current price, stock, terms, consent, account health, pause and approval expiry. | MISSING | No complete dispatch revalidation found. | Implement policy checks before dispatch. | P1 / L |
| A07.1 | A07, §§3,8 | Global, channel and workflow pause prevents new dispatch and reports in-flight work. | MISSING | No pause state/check found in inspected Growth dispatch path. | Add persisted pause policy and race-safe tests. | P1 / M |
| A07.2 | A07, §§4,8 | Daily/weekly limits and minimum-repeat windows are enforced. | MISSING | No Growth frequency limiter found. | Define policy settings and atomic reservation. | P1 / M |
| A08.1 | A08, §8 | Each destination outcome is independent and partial success is visible. | PARTIAL | Per-platform publication rows exist; admin page primarily displays post-level status. | Expose destination outcomes and test mixed results. | P1 / M |
| A08.2 | A08, §8 | Unknown provider outcome is reconciled before retry; retries are bounded and idempotent. | PARTIAL | Idempotency key and timed-out guard exist; provider adapter is fixture; no reconciliation worker/backoff/dead-letter found. | Define provider reconciliation and durable retry policy. | P1 / L |
| A08.3 | A08, §§8,16 | Failures show actionable errors and auditable attempts/reason codes. | PARTIAL | Error/connector/audit models exist; durable attempt history and reason taxonomy not established. | Add attempt history, reason codes and UI evidence. | P1 / M |
| A09.1 | A09, §13 | GA4 configuration/reporting connection state is clear and distinguishes collection from reporting access. | MISSING | Internal event API only; no GA4 configuration/reporting integration found. | Select access model and connector contract. | P1 / M |
| A09.2 | A09, §13 | Date/channel/content filters report source and freshness without fabricated metrics. | MISSING | `analytics_summary` returns internal aggregate only; no filters/provider freshness model in admin path. | Add provider-backed reporting and empty states. | P1 / M |
| A09.3 | A09, §§13,29 | Event schema includes named events, consent and payload validation. | PARTIAL | Generic event ingestion exists; full schema/consent validation not found. | Define versioned event contract and consent tests. | P1 / M |
| A10.1 | A10, §6 | Every actual BOM SKU resolves to versioned licensed asset with transform/material metadata. | MISSING | Growth asset model is generic URL/provenance; no assembled scene manifest verified. | Inventory assets and rights; define SKU mapping. | P2 / L |
| A10.2 | A10, §6 | Assembly fit/orientation/collision/material validation blocks inaccurate renders. | MISSING | No Growth assembly/render validation found. | Select renderer; build representative scene validation. | P2 / XL |
| A11.1 | A11, §6.3 | Launch video includes verified specs/benchmark/value/Pace claims and approved CTA. | MISSING | Campaign assets exist in dirty user changes; no verified generated video template/claim provenance. | Create approved template and factual source checks. | P2 / L |
| A11.2 | A11, §6.3 | Exact channel exports are previewed; regeneration invalidates approval. | MISSING | No render job/export approval lifecycle found. | Implement export manifest and revision binding. | P2 / L |
| A12.1 | A12, §7 | Calendar covers all active types with day/week/month/list, filters and timezone rules. | PARTIAL | Admin page lists posts; no unified multi-type calendar/date views/filter contract found. | Implement calendar model/views and timezone tests. | P1 / L |
| A12.2 | A12, §7 | Schedule conflicts/limits/expiry are enforced; out-of-scope reschedule requires reapproval. | MISSING | No calendar reschedule/conflict checks found. | Add policy-aware schedule operations. | P1 / M |
| A13.1 | A13, §10 | Approved blog publishes to CMS with confirmed URL, rollback and social draft trigger. | MISSING | Blog publishing capability is roadmap-gated. | Select CMS/API and define publication confirmation. | P3 / XL |
| A14.1 | A14, §11 | Google Ads/Merchant Center account, capability, product feed diagnostics and approved campaign are implemented. | MISSING | Paid advertising is roadmap-gated; no account/feed connector found. | Verify provider access, account, scopes and feed. | P4 / XL |
| A14.2 | A14, §§8,11 | Unapproved spend is impossible; approved launch is idempotent. | MISSING | No ad spend execution implementation found. | Define spend envelope, approval hash and idempotent launch. | P4 / XL |
| A15.1 | A15, §§11,16 | Exposure caps and emergency pause reconcile with provider; organic/paid metrics remain separate. | MISSING | No paid execution/reconciliation or spend cap found. | Implement only after provider/economic gates. | P4 / XL |
| A16.1 | A16, §§10,12 | Newsletter consent/suppression is checked at send and sends reconcile. | MISSING | Newsletter is roadmap-gated; no email marketing send flow found. | Select provider and privacy policy. | P5 / XL |
| A16.2 | A16, §§10,12 | Owned placements are tracked separately and require approval/rollback. | MISSING | No owned placement workflow found. | Define placement inventory and approval API. | P5 / L |
| A17.1 | A17, §14 | Recommendation includes dated evidence/confidence/assumptions and supports no-action. | MISSING | Existing demand/Playbook code is adjacent; no Growth recommendation evidence bundle found. | Map reusable services and define evidence contract. | P6 / L |
| A17.2 | A17, §§8,14 | No autonomous public action or expenditure bypasses approval. | BLOCKED | Policy is normative; broad agent/action permissions and production boundary not verified. | Approve policy and test typed-action enforcement. | P6 / L |
| A18.1 | A18, §3 | Screens are keyboard accessible, responsive, high contrast and visibly focused. | PARTIAL | Source includes responsive classes/focus styling; no rendered/accessibility audit run. | Browser/manual WCAG 2.2 AA verification. | P1 / M |
| A18.2 | A18, §§8,16 | Audit history and secret redaction cover external actions. | PARTIAL | Audit model/events exist; secret redaction and complete external action coverage not verified. | Threat/test review and audit coverage. | P1 / M |
| A19.1 | A19, §20 | Approved strategy revision is stored and recommendations reference it; absent financial limits block paid launch. | MISSING | No Growth strategy/policy object found; paid is gated. | Define owner-approved strategy/financial policy. | P6 / L |
| A20.1 | A20, §21 | Director queue ranks actionable items, deduplicates and supports no-action. | MISSING | No Director queue found. | Define evidence/ranking/duplicate key. | P6 / L |
| A21.1 | A21, §22 | Opportunity includes dated evidence, margin and availability; stale/incomplete evidence blocks recommendation. | PARTIAL | Demand/Playbook services exist; Growth opportunity evidence contract not verified. | Map current sources and freshness/finance contract. | P6 / L |
| A22.1 | A22, §23 | Playbook variant preserves real specs and eligible Pace prices; unsupported audience claim fails validation. | PARTIAL | Playbook/commercial logic exists elsewhere; Growth creative validation not integrated. | Reuse authoritative Playbook/Pace source and add tests. | P6 / M |
| A23.1 | A23, §24 | Competitor comparison records provenance and flags incomparable configurations; no inferred sales as fact. | MISSING | No Growth competitor comparison surfaced. | Define source and comparability model. | P6 / L |
| A24.1 | A24, §25 | Funnel metrics define denominators/missingness; leads deduplicate and persist through status changes. | MISSING | Generic events exist; no lead lifecycle/funnel denominator model found. | Define event/lead ownership and privacy constraints. | P6 / L |
| A25.1 | A25, §26 | Remarketing approval, consent withdrawal, suppression and frequency are enforced at dispatch. | MISSING | No audience/remarketing execution found. | Legal/privacy decision and provider design. | P4 / XL |
| A26.1 | A26, §27 | Landing pages support preview, approval, publish, expiry, tracking and rollback. | MISSING | No Growth landing page model/workflow found. | Define CMS/hosting ownership. | P6 / L |
| A27.1 | A27, §27 | Structured data matches catalogue; AI discovery observations record query/provider/date without rank guarantees. | MISSING | Not established in inspected Growth implementation. | Define structured-data source and observation contract. | P6 / M |
| A28.1 | A28, §27 | Finance fixtures reconcile VAT/refunds/fees/fulfilment; CPA/ROAS examples match. | PARTIAL | Commerce finance sources exist but Growth attribution reconciliation and worked fixtures were not verified. | Map finance source and approve formulas. | P4 / L |
| A29.1 | A29, §27 | Concurrent paid campaigns cannot exceed exposure; pause/reconciliation/reporting lag are tested. | MISSING | No paid execution or exposure reservation found. | Atomic spend reservation and provider reconciliation. | P4 / XL |
| A30.1 | A30, §27 | Asset lineage/licence expiry/takedown/master reuse are traceable. | PARTIAL | Generic asset provenance exists; rights/expiry/lineage not verified. | Extend asset governance and takedown workflow. | P2 / L |
| A31.1 | A31, §27 | Model/render budget, cache, cancellation, timeout, fallback and cost controls are enforced. | MISSING | No render pipeline found. | Choose renderer/provider and budget policy. | P2 / XL |
| A32.1 | A32, §28 | Social inbox classifies/routes enquiries; replies/moderation cannot bypass approval. | MISSING | No inbox workflow found; automated replies are excluded from Release 1. | Later-phase provider/privacy design and approval tests. | P6 / L |
| A33.1 | A33, §28 | Review consent, affiliate disclosures, referral fraud and payout reconciliation are implemented. | MISSING | No integrated advocacy program found. | Define rights/disclosure/fraud/payout policy. | P6 / XL |
| A34.1 | A34, §29 | Consent, claim, price and promotion compliance gates fail closed on missing required evidence. | PARTIAL | Approval/asset checks exist; complete legal/consent/freshness gate not established. | Qualified policy review and dispatch tests. | P1 / L |
| A35.1 | A35, §29 | Agent permissions, prompt injection, secret redaction, restore and outage tests meet approved targets. | PARTIAL | General security/test infrastructure exists; Growth-specific evidence and approved operational targets absent. | Approve targets and add adversarial/restore tests. | P6 / XL |
| A36.1 | A36, §32 | Atomic IDs, evidence, status and verification date are recorded; counts reconcile. | COMPLETE | This tracker gives stable atomic IDs, evidence/status/date, and reconciled summary below. | Reconcile after each implementation/change. | P0 / S |
| A37.1 | A37, §32 | Audit and implementation plan precede application changes; completed capability is not rebuilt without evidence. | BLOCKED | Audit/plan delivered and no app code changed; owner approval remains pending. | Owner review/approval; preserve originals and dirty work. | P0 / S |

## Current totals

Atomic rows: **62**. Applicable requirements: **62**. Approved exclusions: **0**. COMPLETE: **1**; IMPLEMENTED–UNVERIFIED: **2**; PARTIAL: **19**; NEEDS ENHANCEMENT: **2**; MISSING: **36**; BLOCKED: **2**; CONFLICT: **0**. Verified percentage = **1 / 62 = 1.6%**. Only A06.2 (approval-required source path) and A01.1 (navigation source presence) are not complete because their runtime behavior has not been verified; they are currently reported as implemented-unverified. (Counts are reconciled against the rows; update them whenever a row changes.)

## Verification log

| Date | Activity | Result |
|---|---|---|
| 2026-11-26 | Read-only source and document audit | Completed for paths listed in the audit; no runtime/provider/test execution. |

## Decision and evidence log

| Date | Decision/evidence | Owner |
|---|---|---|
| 2026-11-26 | v1.1 is treated as proposed governing specification; archival/reference changes are deferred. | Pending owner approval |
| 2026-11-26 | Existing dirty user edits are preserved and not counted as verified deployment behavior. | Audit constraint |
