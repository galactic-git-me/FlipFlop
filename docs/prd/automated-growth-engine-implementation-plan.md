# Automated Growth Engine implementation plan

**Basis:** owner-supplied Automated Growth Engine PRD v1.1, 26 November 2026, reconciled against the current source audit.
**Status:** proposed; application work is gated on owner approval under PRD §32.

## Decisions and reconciliation

1. Treat v1.1 as the proposed consolidated target, but do not silently supersede or archive [marketing-engine-prd.md](./marketing-engine-prd.md), [marketing-engine-codex-implementation-prompt.md](./marketing-engine-codex-implementation-prompt.md), or the repository's v1.0 [automated-growth-engine-prd.md](./automated-growth-engine-prd.md). Update the PRD register only after the owner approves the precedence and archival/reference changes.
2. Retain v1.1 Release 1 boundaries: no paid spend, newsletter sending, automated blog publishing, replies, or unapproved public publishing. Automatic mode, if implemented, executes only an approved exact revision.
3. Reuse the Growth models/API/service and scheduler where they meet the requirement. Do not create parallel build, listing, inventory, order, media, analytics, or approval sources of truth.
4. The present fixture publisher is not a live provider. Keep external publishing disabled until each provider's API/version, account type, scopes, media constraints, rate limits, revocation, error mapping, and reconciliation are verified from current authoritative documentation and an approved account.
5. Current campaign source includes factual commercial claims. Every claim and destination must be checked against current commerce data immediately before approval/execution; no hard-coded sample establishes current availability or price.
6. Financial targets, provider budget ceilings, retention/lawful-basis policy, render infrastructure, service targets, and approved campaign expiry policy remain owner decisions or require qualified review. Missing evidence blocks the affected action; it is not zero or approval.

## Proposed phases and acceptance gates

### Phase 0 — owner decisions and clean evidence baseline

- Approve this audit and plan; confirm v1.1 as governing and decide the document-register/archival treatment.
- Identify which existing dirty Growth changes are intended for the first implementation slice; inspect current listing/price/stock for any campaign draft before reuse.
- Confirm canonical build identity and authoritative hooks for listing published, public promotion, price/availability change, sold, expired, and blog published.
- Confirm existing authentication/authorization and approval authority for Growth endpoints; resolve single-user versus future role behavior.
- Decide privacy basis, consent event rules, retention, and acceptable GA4 connection/reporting model before storing or exposing additional event data.
- No application implementation starts until owner approval; no production writes are part of this phase.

### Phase 1 — Foundation release (fastest useful vertical slice)

**P1.1: Verified source snapshot and event idempotency.** Define versioned event envelope, unique event/idempotency keys, source snapshot, correlation IDs and failure reason codes. Consume only authoritative build/public-promotion events; reconcile missed events; group cross-listings by canonical build + launch revision. Eligibility blocks incomplete, hidden, sold, unavailable, private promotion, missing canonical URL, and stale claims. Replay creates one campaign/draft set.

**P1.2: Approval-safe campaign drafts.** Reuse current post/revision/approval structures where sufficient. Add any missing campaign identity and destination records with transactional uniqueness. Render channel variants from versioned templates using known source fields only; missing variables fail validation. Require exact revision, media, claims, destination/account, tracked URL and schedule scope. Edits/regeneration invalidate approval. All launch/promotion/rotation drafts require approval.

**P1.3: Dispatch controls and outcomes.** Before dispatch, revalidate current availability, price, promotion terms, account health, approval expiry and global/channel/workflow pause. Add configurable frequency limits. Keep fixture execution visibly sandboxed. Unknown provider results reconcile before retry; transient retries are bounded; partial channel outcomes remain separate. Use a durable queue/outbox only if existing infrastructure cannot provide durable delivery and locking.

**P1.4: Curated rotation.** Implement selected builds/order/selection policy, cadence/time window, active range, repeat interval, maximum promotion count, available-only filter, template, last-promotion and selection reason. Rotation creates approval drafts only and excludes launch conflicts.

**P1.5: Calendar and admin workflow.** Preserve existing route conventions and Advertising & Growth entry unless product approves splitting routes. Expose connected/configured/unsupported/failed states truthfully, approval queue, scheduled/draft/failure state, action-needed errors, pause status and empty states. Do not call fixture accounts live-connected. Calendar edits cannot publish directly and schedule changes outside approval scope require reapproval.

**P1.6: Analytics foundation.** Specify event names/payloads and consent rules, preserve UTM parameters, add GA4 configuration state and reporting access as separate capabilities. Show provider source/freshness and missingness. Keep synthetic fixture data out of observed metrics. No revenue/profit attribution until evidence and finance reconciliation are accepted.

**Phase 1 gate:** atomic A01–A09 and A12/A18 requirements passing in isolated fixtures; migrations reversible; no unapproved external side effect; provider capability/credential gate signed off; UI/runtime and accessibility verified. Production launch remains a separate explicit authorization.

### Phase 2 — Creative Studio

Inventory actual 3D assets and rights; map SKU/BOM to versioned GLBs and coordinate/transform metadata; validate assembly and collisions; preview manifests. Select a compatible deterministic renderer after measured infrastructure review. Add schema-constrained AI creative direction only through an authorized API and approved budget; retain model/prompt/cost provenance. Add cached async jobs with cancellation/retry/timeouts and deterministic output hashes. Missing critical assets block video or produce separately disclosed, approved still fallback. Verify exact channel exports, benchmarks, Pace, price, audio/media rights and claims before reapproval.

### Phase 3 — Editorial and distribution

Choose CMS interface; implement sourced brief, draft, preview, canonical slug, collision checks, approval, confirmed publication, rollback and sitemap/RSS. Publication produces social drafts. Add Search Console only after ownership/scopes/data availability are proven.

### Phase 4 — Paid acquisition

Verify Google Ads and Merchant Center access, provider policy, product feed diagnostics, exact account scopes, conversion definitions and economics. Implement spend envelopes, concurrent exposure caps, pause/reconciliation and immutable approvals before any launch endpoint. Establish finance fixtures that reconcile VAT, refunds, fees, fulfilment and contribution profit. No API campaign may launch until account, consent, price/stock, spend, approval and pause checks pass.

### Phase 5 — Owned audience and placements

Select an email provider and verify sender authentication, consent/suppression, unsubscribe/bounce/complaint handling, frequency, idempotency and delivery reconciliation. Add newsletter and website placements with exact preview/approval, expiry, tracking and rollback. No sends or public placement updates before approval.

### Phase 6 — Growth intelligence

Add evidence-backed opportunities, Playbook segments, non-comparable competitor caveats, funnel/lead lifecycle, consented remarketing, GEO/AEO observations, finance reconciliation, asset rights, social listening, review/affiliate controls and a ranked Growth Director queue. Agents emit typed proposals only; deterministic policy gates enforce action limits. Experiments require hypothesis, control/exposure design, metrics and stopping rules; never imply causality without valid evidence.

## Verification and release process

- Translate each tracker row into an executable acceptance test or documented human/provider verification. Keep source inspection, automated test, UI/runtime, provider confirmation, and production readiness as separate evidence types.
- Use isolated fixtures and safe dev adapters; no live posts, spend, newsletters, public blog content, database production mutations, or provider credentials in tests.
- Before schema changes: migration-up/down review, existing-data compatibility, constraints/index review, and isolated migration tests.
- Validate backend unit/API/integration paths, admin type/lint/build, browser workflow, accessibility, concurrency/replay/restart, pause/approval races, provider timeout/reconciliation, secret redaction, privacy/deletion and restore according to the platform test strategy.
- Reconcile every failure and pre-existing dirty change. Do not modify unrelated working-tree paths. Update implementation status only after corresponding behavior has evidence.
- Do not claim “complete” or production-ready until the required evidence is attached to every atomic criterion and source/runtime facts agree.

## Critical path and dependencies

Owner approval → document precedence and dirty-work scope → canonical commerce event/identity contracts → approval/auth/pause policy → idempotent campaign/draft persistence → fixture end-to-end path → rotation/calendar → GA4/event contract → provider feasibility and controlled live verification. Creative/video and paid acquisition depend on asset/claim/economic evidence; newsletter depends on consent/provider readiness. Those later streams do not block a useful, approval-gated organic draft foundation.

## Open decisions before implementation

- Approve the first slice: Foundation event-to-review drafts and its acceptance IDs.
- Confirm PRD source precedence and whether/when v0.1 implementation prompt and v1.0 local copy may be archived or marked superseded.
- Confirm provider selection, account ownership, scopes, API costs/limits, and whether the first phase remains fixture-only.
- Confirm lawful basis/consent and retention policy; select GA4 collection versus reporting credentials.
- Confirm financial policy, paid budget ceilings, commercial baseline/targets, render budget/infrastructure and SLO/RPO/RTO ownership.
- Confirm campaign approval expiry and role/separation-of-duties policy.
