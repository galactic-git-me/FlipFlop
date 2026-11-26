# Automated Growth Engine implementation audit

**Specification:** Owner-supplied `C:\Users\mclar\Downloads\automated-growth-engine-prd-v1.1.md` (26 November 2026)
**Audit date:** 26 November 2026
**Scope:** Repository evidence for the Growth Engine, related requirements, migrations, scheduler, admin/API flow, provider adapters, and existing focused tests.
**Status:** Initial source audit complete; runtime/provider claims remain unverified. This audit is not approval to implement the application roadmap.

## Executive summary

The repository already contains a Marketing MVP slice: an Advertising & Growth admin page, a Growth API, SQLAlchemy entities and an Alembic migration, social post revision/approval flows, tracked links, first-party analytics event storage, fixture/assisted channel adapters, a due-post scheduler, and a small backend test file. This is meaningful reusable work, but it does not establish a working live social or GA4 integration. The current code shown by inspection does not implement authoritative build/promotion event intake, campaign upsert/deduplication, curated build rotation, GA4 reporting/configuration, a global/channel/workflow pause, or durable queue/outbox reconciliation. No runtime or external provider was exercised during this audit.

The supplied v1.1 specification is broader than the repository's v1.0 copy at [automated-growth-engine-prd.md](./automated-growth-engine-prd.md), the bounded v0.1 marketing PRD, and the former implementation prompt. v1.1 explicitly makes audit, tracker, and plan delivery the first gate and requires owner approval before application or architectural changes. It retains the earlier MVP requirements while adding substantial future releases. The PRD register still labels the v0.1 Marketing Engine as current and classifies the Growth Engine documents separately; that source-of-truth mapping needs owner approval before archival or register edits.

## Evidence examined

- Supplied v1.1 PRD and repository v1.0 copy; the v0.1 marketing PRD and its implementation prompt.
- Product and engineering routers, product documentation map, PRD register, Marketing MVP PRD, and critique/traceability matrix.
- `flipflop-admin/app/advertising-growth/page.tsx`, sidebar route, approval-count integration, and relevant API helper references.
- `flipflop-api/app/api/growth.py`, `app/models/growth.py`, `app/services/growth_social.py`, `growth_connectors.py`, `growth_release.py`, `app/main.py`, and scheduler registration/wrapper.
- Growth Alembic migration, dev schema-alignment migration, and `flipflop-api/tests/test_growth_engine.py` source.
- Current branch/history and `git status`; inspected diffs for the Growth Engine-related dirty files.

The source audit was read-only. Tests, type checks, builds, database migrations, browser flows, external APIs, production services, 3D assembly/rendering, and provider account capabilities were not run or verified. Code presence is recorded as implemented-unverified or partial; it is never counted as complete solely from source inspection.

## Working-tree protection and audit limitations

At audit start, branch `dev` was at `2a5a19b4e` and the checkout contained unrelated dirty changes. Growth-related dirty paths include [advertising-growth/page.tsx](../../flipflop-admin/app/advertising-growth/page.tsx), [growth_social.py](../../flipflop-api/app/services/growth_social.py), and [implementation-status.md](../product/implementation-status.md). The page/service diff adds a Prometheus Black Friday campaign draft flow and approved creative seeds; the status document records that runtime and persistence are unverified. Other dirty paths concern live-build withdrawal, component discovery data, and API helpers. None were changed by this audit. Dirty code is not assumed to be committed, deployed, or production behavior.

This audit has strong source-level coverage of the central MVP vertical slice, but not a line-by-line audit of every commerce source, every 3D asset, every provider's live documentation, production credentials, privacy/legal obligations, or production data. Those remain explicit evidence gaps, not inferred failures or passes.

## Architecture and current implementation evidence

| Area | Evidence and observed behavior | Audit result |
|---|---|---|
| Admin/navigation | Sidebar links to `/advertising-growth`; page lists campaign drafts, manual drafts, review/approve/publish actions, basic observed metrics, and a content calendar-like post list. No distinct Social Media/Analytics routes, full account management, global pause, or GA4 connection screen was found in inspected paths. | Partial; visual/runtime behavior unverified |
| API | `/api/growth` exposes release, command centre, accounts, assets, social posts, approvals, audit, event ingestion, analytics summary, and tracking redirect endpoints. No authoritative commerce-event intake or campaign/rotation API surfaced in this router. | MVP API partial |
| Persistence | Growth entities cover release config, social accounts/assets/posts/revisions/publications, tracking links, analytics events/snapshots, approvals, connector executions, and audit events. Migration exists. A campaign, durable business-event inbox/outbox, rotation collection, template registry, render job, GA4 credentials/reporting state, and provider-specific event reconciliation were not found in these Growth models. | Foundation present; remaining domain model missing |
| Approval/lifecycle | Revisions are versioned; submission validates copy/media and creates an expiring approval; editing an approved/review post resets it to draft; publication requires approved status and uses per-platform idempotency keys. | Implemented in source; tests/runtime not run; exact approval scope/revision hash, revalidation and conflict safety need enhancement |
| Provider execution | Current adapter module is explicitly fixture/assisted. Seeded accounts are marked `connected` while capabilities identify fixture/assisted; deterministic fixture results produce provider-like IDs and synthetic-looking organic metric snapshots. No live OAuth connector was found. | Live integration absent; connection semantics and metric provenance need review |
| Scheduled jobs | APScheduler registers a one-minute due-post publisher and a 90-day analytics retention task. The wrapper calls `publish_due_posts`; no durable queue/outbox, persisted attempt history/dead letter, reconciliation worker, or rotation worker was found in inspected code. | Scheduled MVP slice present; reliability requirements unmet/unverified |
| Tracking/analytics | Tracked URLs preserve the destination query and add four UTM parameters; API can ingest first-party event records and summarize sessions/UTM presence. No GA4 connection/reporting API, date/channel filters, consent contract, full named event schema, or attributed revenue implementation was found in the inspected growth API. | First-party foundation partial; GA4/reporting missing |
| Build/promotion lifecycle | The inspected Growth service accepts manually created social posts and campaign source references; it does not subscribe to authoritative listing, promotion, sold, availability, or blog events. No curated-build rotation implementation was found in the inspected Growth service/models. | Release 1 event orchestration and rotation missing |
| Future releases | Existing release capabilities gate paid advertising, blog publishing, newsletters, automated replies, vouchers, loyalty, abandoned cart, revenue attribution, and optimisation as roadmap capabilities. No inspected end-to-end implementation establishes those capabilities. | Correctly gated; future scope remains unimplemented/unverified |

## Risk and decision findings

1. **No live publishing proof.** Fixture publication can create a locally confirmed state and metric snapshots. This is not evidence that Facebook, Instagram, or X received a post. Seed account `connected` labels must not be interpreted as OAuth connection proof.
2. **Approval boundary is narrower than v1.1.** The source implements an approval step, but audit did not establish approval hashes covering channel/account, exact assets/claims/link/schedule, fresh price/availability/consent checks at dispatch, or safe concurrent approval/execution behavior.
3. **Pause and frequency controls are absent in inspected Growth flow.** The scheduler publishes due approved posts without visible global/channel/workflow pause or frequency-limit checks in `publish_due_posts`.
4. **Event-driven eligibility is absent.** Build readiness, canonical URL, cross-listing grouping, promotion privacy/terms, stale draft invalidation, and sold/expired cancellation are not wired through the inspected API/service.
5. **Analytics are not GA4.** Internal event counts and UTM presence are not GA4 connection state or provider-reported sessions/conversions. Avoid presenting synthetic fixture metrics as observed provider results without clear labeling.
6. **User-supplied Prometheus campaign changes need commercial revalidation.** The dirty admin diff contains hard-coded prices, stock, delivery claims, and destination URLs, with a reminder to verify them before approval. Source presence does not validate current listing truth or campaign eligibility.
7. **Governance mismatch.** The PRD asks to preserve the v0.1 prompt/docs until the owner approves archival; the docs register does not yet identify v1.1 as governing. Resolve document precedence and preserve both originals pending that decision.

## Requirement status summary

The detailed trace is in [the progress tracker](./automated-growth-engine-progress-tracker.md). The implementation plan is [here](./automated-growth-engine-implementation-plan.md). Counts are based on the tracker's atomic rows; only COMPLETE counts toward verified percentage. Source inspection alone cannot earn COMPLETE for application behavior. The only COMPLETE row is the traceability/documentation outcome supported by this audit package; it does not imply a shipped product capability. No exclusions have been approved.

## Audit conclusion

There is a reusable, test-backed-in-source Marketing MVP foundation, not a verified release-ready growth system. The shortest safe path is to first reconcile product documents and dirty campaign claims, then verify/fix the approval and pause boundary, then implement one authoritative event-to-draft vertical slice with deduplication and availability revalidation, while keeping real provider publication disabled until exact provider capability and credentials are proven. Release 1 completion should remain separate from the much larger creative, editorial, paid, audience, and intelligence roadmap.

**Gate:** stop here pending explicit owner approval of the audit/plan and a named implementation slice. No application change, provider mutation, spend, live publishing, or archival was performed.
