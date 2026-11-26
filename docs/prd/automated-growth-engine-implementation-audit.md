# Automated Growth Engine implementation audit

**PRD:** `automated-growth-engine-prd-v1.1.md`, supplied from `C:\Users\mclar\Downloads\automated-growth-engine-prd-v1.1.md` (v1.1, 26 November 2026).
**Audit date:** 2026-11-26
**Branch:** `codex/prometheus-growth-storefront-20261126`
**Scope:** Repository evidence review followed by an approved Release 1 implementation slice. No live database, external account, provider, or production state was changed.

## Executive result

The repository contains a Growth Engine MVP foundation: an admin Advertising & Growth screen, API and persistence for social drafts/revisions, approval requests, tracking links, first-party analytics events, audit events, a scheduled due-post worker, and fixture-oriented tests. This is not a live social or GA4 integration. Fixture outcomes are now explicitly simulated, seeded accounts report not configured, and the admin requires a registered adapter before resuming dispatch.

The initial approved Release 1 slice now connects successful Ready-to-Ship listing to idempotent Facebook/Instagram review drafts, with tracked product URLs and an explicit social-image approval step. A default-paused dispatch control is enforced by the worker. The fixture path cannot create a live publication or fabricated metrics. Rotation, full current-data revalidation, real social adapters, and GA4 reporting/configuration remain outstanding.

The source PRD §32 required this audit, plan, and tracker before implementation. The owner approved proceeding on 2026-11-26. The first implementation slice now adds authenticated Growth API boundaries, a default-paused dispatch control, fail-safe fixture behavior, listing-triggered review drafts, and an explicit admin action to approve reused storefront imagery for social use; later acceptance work remains in progress. Targeted static checks passed. The API integration tests were authored but not run because `FLIPFLOP_TEST_ADMIN_DATABASE_URL` is unset. The superseded marketing PRD and implementation prompt are retained unchanged.

## Repository and change safety

- Current branch: `codex/prometheus-growth-storefront-20261126` (observed with `git status --short --branch`).
- Pre-existing worktree change: `flipflop-api/data/component-manual-discovery.json` modified. It was not read or edited as part of this task.
- Growth Engine route registration: `flipflop-api/app/main.py` includes `growth.router` under `/api`.
- Admin navigation: `flipflop-admin/components/sidebar.tsx` links to `/advertising-growth` under “Listings & Growth”. This is not the PRD’s `/marketing/social` and `/marketing/analytics` route structure, though the PRD permits repository-convention adaptation.
- Admin screen: `flipflop-admin/app/advertising-growth/page.tsx` shows social draft/review workflow, fixture/assisted provider warning, and paid-ads gate. Its displayed campaign is hard-coded Prometheus/Black Friday example material and is not an event-driven general campaign workflow.
- API: `flipflop-api/app/api/growth.py` exposes release, command centre, accounts, assets, social posts/revisions, submit/approval/execute, approvals, audit, website event ingestion, analytics summary, and tracking redirect endpoints.
- Persistence: `flipflop-api/app/models/growth.py`; initial schema migration `flipflop-api/alembic/versions/20260921_0001_growth_engine_mvp.py` plus subsequent merge migration (see migration history). Entities include release config, accounts, assets, posts/revisions/publications, tracking links, analytics events, snapshots, approvals, connector executions and audit events.
- Scheduling: `flipflop-api/app/workers/scheduler.py` registers `growth_social_publisher`; `run_growth_social_publisher` delegates to `publish_due_posts`.
- Tests: `flipflop-api/tests/test_growth_engine.py` covers deterministic simulation, pause enforcement, approval workflow, listing draft replay/media approval, tracked-link preservation, and first-party event ingestion. The new tests have not run because the isolated Postgres admin URL is unavailable. These tests do not establish live provider behavior.
- Analytics route: `flipflop-api/app/api/analytics.py` covers vendor/catalogue analytics and is not a GA4 connector. Marketing first-party analytics live under `/api/growth/analytics`.
- Build/product lifecycle candidates for future verified integration: `flipflop-api/app/models/manual_build.py`, `flipflop-api/app/models/product.py`, `flipflop-api/app/api/manual_builds.py`, `flipflop-api/app/api/public_products.py`, and lifecycle/event code referenced by those modules. Exact canonical event hooks and public URL/media resolution must be traced during the implementation phase before selecting an integration point.

## Evidence boundaries and findings

| Area | Evidence observed | Audit conclusion |
|---|---|---|
| Admin entry | Sidebar item and `/advertising-growth` page exist; Growth routes now require authenticated admin access | Existing, but navigation and screen need Release 1 UX completion and route decision |
| Social account state | `SocialAccount`, API account listing, admin disable/verified-enable endpoint, fixture status, and profile cards | Fixture accounts are reported not configured; live OAuth setup and provider health check are not implemented |
| Drafts and approval | `SocialPost`, immutable revision rows, approval requests, edit invalidation and tests; Growth admin operations require admin authentication | Useful foundation; exact revision approval exists in the local workflow, but authentication/authorization and production policy need end-to-end verification |
| Publishing | Fixture outcomes are explicitly simulated; `LIVE_PUBLISHER_PLATFORMS` is empty and the UI requires an available adapter | No live publication capability verified; external publishing remains disabled |
| Scheduling | Due-post worker publishes `scheduled` rows after approval | Local scheduler path exists; durable queue guarantees, locking/race behavior and live provider reconciliation are not demonstrated by reviewed evidence |
| Events | `/growth/analytics/events` stores website analytics events; successful first-time storefront listing calls `create_build_launch_drafts` in the listing transaction | Listing hook creates factual, tracked, revision-keyed and replay-idempotent drafts; no general outbox, restart reconciliation, marketplace-wide event intake, or promotion event hook |
| Tracking | Tracking link table, slug endpoint, UTM redirect preserving existing query parameters | Core UTM redirect exists; build/template/creative opaque IDs and policy validation are not shown in its current fields/API |
| Analytics | First-party event counts; fixture synthetic snapshots were removed from dispatch | GA4 reporting/configuration remains absent; fixture metrics must not be interpreted as observed provider metrics |
| Rotation | No rotation/collection model or scheduler found in targeted Growth Engine files | Missing from reviewed Growth Engine implementation |
| Release gates | `GrowthReleaseConfiguration`, enabled capability list and roadmap; migration seeds `GrowthDispatchControl` paused and the worker checks it | Global pause is implemented; per-channel/per-workflow pause, frequency controls, current-data dispatch gates and concurrency acceptance evidence remain |
| Later releases | Models explicitly defer paid ads, blog, newsletter and related capabilities | PRD1.1 correctly keeps them non-operational in Release 1 |
| Production | No provider credentials/account calls, deployed runtime, or external delivery checks performed | Production readiness and connected status are unknown; no live claims made |

## Provider feasibility and unresolved integration facts

No live provider feasibility was asserted in this repository-only audit. Facebook Pages/Instagram Business require a selected Meta app/account ownership model, approved scopes, token lifecycle and review/app-mode verification. The repository currently contains no verified authorization or publishing adapter for these accounts. Exact Graph API capabilities, review status, limits and account eligibility remain to be checked against current official provider documentation and the actual account during the approved implementation phase.

GA4 collection configuration and GA4 Data API reporting are separate concerns. The API dependency set includes `google-auth`, but dependency presence is not a connection. No GA4 property, Measurement ID, service-account/OAuth configuration, reporting scope, secret storage, consent contract, or Data API result was verified. The owner must choose reporting credentials/access and confirm whether configuration state alone or fetched reports are required for the initial launch.

No OpenAI/ChatGPT API access or renderer choice is inferred from a subscription. Release 2 model, renderer, asset rights, API costs, hardware assets and scene provenance remain later-phase decisions.

## Conflicts and specification reconciliation

1. The prior v0.1 PRD and implementation prompt ask for implementation of an MVP vertical slice. v1.1 §32 explicitly supersedes that instruction with an audit-first approval gate. This audit follows v1.1.
2. v1.1 says Release 1 may prepare image-based announcements while video is unavailable, while §6.3 defines video as the target build-launch workflow. Plan: implement image fallback only as a visibly disclosed and separately approved path; do not call it completion of the video requirement.
3. The PRD asks to retain `/marketing/social` and `/marketing/analytics`, adapted to repository conventions. Existing navigation uses `/advertising-growth`; preserving that route and offering clear Social/Analytics views avoids a breaking link, subject to owner confirmation.
4. The model contains `content_calendar` and the screen presents a post list as a calendar. This does not demonstrate the PRD’s multi-content, timezone-aware, conflict-aware calendar; treat it as partial foundation.
5. A legacy Release 1 description names Facebook Pages and Instagram Business as first adapters, while existing fixture setup also includes X. Do not allow X or any other channel to imply provider support until explicitly configured and verified.

## Status methodology and counts

The progress tracker decomposes acceptance criteria A01–A37 into 108 stable atomic rows. Statuses use the mutually exclusive PRD vocabulary. **COMPLETE means verified against the PRD by current evidence**; an implementation with unrun tests is IMPLEMENTED–UNVERIFIED or PARTIAL. A fixture test does not prove a real integration. Owner approval was received on 2026-11-26; the approved first implementation slice is complete at source level, and acceptance validation remains in progress.

- Applicable atomic acceptance requirements: 108
- COMPLETE (verified): 6 (tracker uniqueness/count audit and approval-gate criteria)
- IMPLEMENTED–UNVERIFIED: 4
- PARTIAL: 19
- NEEDS ENHANCEMENT: 0
- MISSING: 79
- BLOCKED: 0
- CONFLICT: 0 (specification conflicts are recorded above and resolved as plan constraints)
- Verified percentage: **6 / 108 = 5.6%**
- Approved exclusions: none recorded

This percentage describes the explicit acceptance matrix’s verified completion, not the amount of code already present. Evidence gaps and existing partial foundations are identified above and item-by-item in the tracker.

## Decisions carried forward

Owner approval for this plan was received on 2026-11-26. Conservative defaults for this slice retain /advertising-growth, require approval for every draft, and keep external publishing and GA4 reporting disabled. Before live scheduling or provider work, resolve:

1. Should the existing `/advertising-growth` page remain the stable route with Social/Analytics tabs, or should compatibility routes `/marketing/social` and `/marketing/analytics` be added?
2. Which Meta business portfolio, Facebook Page and Instagram Business account are the Release 1 targets, and who will supply/configure least-privilege app credentials and complete any required provider review?
3. Which GA4 property and reporting access method should be used, and what event-consent and data-retention rules are approved?
4. Confirm Release 1 image fallback is allowed only after explicit per-draft approval while the video pipeline is unavailable.
5. Confirm initial posting windows/frequency limits and approval expiry policy, or authorize conservative disabled-by-default settings pending configuration.

Owner approval has been received. The first-party and fixture-safe slice described above is implemented. Continue with the remaining approved plan; real provider publishing and GA4 reporting remain disabled until account credentials and provider feasibility are verified.


