# Finish the current FlipFlop work

**Status:** Active baseline and completion plan  
**Date:** 11 October 2026  
**Source baseline:** `8286096df` (`chore: establish current implementation baseline`)  
**Scope:** Current uncommitted API, admin, data-model, migration, product-documentation and validation work in this repository.

## Baseline

The current development branch contains a broad set of implementation changes across checkout and pricing, customer/order portals, support and warranty, shipment booking/tracking, Getting Ready, catalogue/3D assets, Playbooks and admin workflows. Product and engineering documentation has also been reorganized around canonical product, lifecycle, policy, PRD and test-plan documents.

This is a source baseline, not a release. The implementation register and individual work notes identify many changes as source-reviewed only. No production deployment or external provider action is part of this plan.

## Finish sequence

### 1. Capture a clean source baseline

- Review the staged file list and diff by subsystem; keep runtime state, credentials/tokens, generated data and temporary review artifacts out of Git.
- Run whitespace and repository hygiene checks; resolve reported issues.
- Commit the reviewed implementation and its matching documentation as one clearly named baseline on `dev`.
- Preserve any excluded local runtime state in the working tree; do not overwrite it during cleanup.

### 2. Validate the baseline locally

- Follow `docs/testing/platform-test-strategy.md` v4.29, approved 9 October 2026, for deterministic local validation. First repair the test harness so every database-backed test uses a dedicated disposable PostgreSQL database. Existing fixtures in `test_autonomous_notifications.py`, `test_demand_playbook_evolution.py`, and other worker suites issue broad table deletes through the configured application engine; those tests must not run against a developer or production database.
- Do not rerun database-backed tests until the isolated database target is explicit, verified, and has a `_test` database name. Keep any required migrations and service startup inside that isolated environment.
- Run the approved API regression suite, then admin type/lint/build checks and relevant storefront checks in their own repositories where applicable.
- Validate Alembic history and apply migrations only to a disposable/local validation database; verify schema and startup separately.
- Exercise the priority customer journeys in the strategy and record exact commands, outcomes and failures in the verification register.
- Keep live provider calls, paid actions, production data changes and deployment behind their separately documented gates.

### 3. Close current implementation gaps

- Reconcile the implementation register with source and validation evidence. Mark each capability implemented, partial, planned or gated; remove stale statements that testing is unapproved.
- Reconcile `docs/API_DOCUMENTATION.md` against registered API routes and schemas, including customer support, portal, shipment, warranty and Getting Ready contracts.
- Close the customer-facing portal, checkout, dispatch and aftercare journeys that remain partial in the implementation register. Track missing storefront/cross-repository work explicitly instead of treating API work as end-to-end completion.
- Complete the sole-trader launch checklist: legal identity/contact values, WEEE route, product-conformity assessment, ICO fee assessment and Northern Ireland/international sales scope.

### 4. Finish vNext commerce intelligence

Follow `docs/plans/vnext-implementation.md` in order:

1. Deliver and validate supplier offer evidence and immutable quote assessment snapshots.
2. Deliver and validate workshop capacity evidence and short internal quote holds.
3. Add trusted supplier and sold-market evidence, the delivery-priority queue, payment-safe-to-procure and refund integration, upgrade assessment integration, and customer tracking integration.
4. Keep recommendations non-purchasable until procurement, market, margin, fulfilment and payment gates are complete and verified.

### 5. Release only after evidence is complete

- Run the relevant customer and operator journeys in the intended development/staging environment.
- Confirm migration state, configuration, provider sandbox outcomes, rollback/reconciliation behavior and customer-safe copy.
- Update the implementation register and release checklist with evidence. Production release remains a separate explicitly approved action.

## Completion record

For each phase, record the commit, checks run, environment, result, known failures and external gates here or in the linked verification register. Do not describe source implementation as verified runtime behavior.

### 11 October 2026 baseline validation

- API command: `.venv\\Scripts\\python.exe -m pytest tests -q` from `flipflop-api`.
- Result: **998 passed, 145 failed, 21 skipped, 21 errors**. This is a failed baseline; the failure output was not retained as a report, so capture a concise rerun report only after the database harness is isolated.
- Safety finding: the test process connected to local PostgreSQL `127.0.0.1:5432/pcflipper`. Existing test fixtures performed table-wide cleanup through the application engine. Read-only inspection afterward showed `flips=0` and `flip_intelligence=0`; no pre-run counts exist, so prior contents and the full effect cannot be determined. No restoration was attempted because the available dump is not known to match the pre-run state.
- Immediate action: preserve the current database, do not run more DB tests or attempt restoration, and review the test harness and any fresh backup with the owner before cleanup or recovery.
- Admin checks: `npx tsc --noEmit` failed with six errors in `app/dispatch-zone/page.tsx` and `app/pc-builder/page.tsx` (missing API method, invalid JSX value, missing evidence handlers, and a missing `builds` prop). Source-only `npx eslint app components lib` failed on a Rules of Hooks violation for `useResearchSuggestion` in `app/dispatch-zone/page.tsx`. The package-wide `npm run lint` also traversed `.next-prod` generated output and reported 34 errors there; use the source-only command for the next baseline.
- Repository hygiene finding: automatic sync commits `122a31703` and `c94e5e395` included the eBay browser state and sandbox token cache; `origin/dev` pointed to `c94e5e395` at inspection. Commit `53ac803d2` removes both from current tracking and ignores the local runtime files, which remain on disk. Historical copies remain in shared Git history; rotate/revoke the eBay session and sandbox credentials, then handle history cleanup only with explicit approval. Do not push the corrective commit until that credential response is complete.

### 19 October 2026 readiness continuation

- Fixed the source lint error in `flipflop-admin/app/dispatch-zone/page.tsx`: `useResearchSuggestion` was an event-handler helper, not a React hook, so it is now named `applyResearchSuggestion`.
- Admin validation: `npx tsc --noEmit` passes; `npx eslint app components lib` passes with no warnings after moving the attention status into the Playbook buttons' accessible names; `npm run build` succeeds.
- Storefront validation: installed the existing locked dependencies with `npm ci --no-audit --no-fund`; `npm run build` succeeds. Set `outputFileTracingRoot` in `FlipFlop.shop.new/next.config.ts` to the storefront directory after the first build exposed an incorrect parent workspace-root inference; the subsequent build completed without that warning. The lockfile was not changed.
- API static checks: `python -m compileall -q app` and `python -m alembic history` succeed; Alembic reports head `20261015_0004`.
- `git diff --check` succeeds. Git reports line-ending normalization warnings for existing modified files; no whitespace errors remain.
- API database tests remain unverified. The test maintenance URL is present in the workspace-root `.env.local`; the local `postgres` maintenance connection was verified with `CREATEDB` permission, and the isolated runner created `flipflop_test_4f848baf5892438c834f8faf_test`. Migration upgrade failed at the root revision because it alters the legacy `listings` table before any revision creates it. No pytest cases ran; the runner retained its uniquely named test database and no application database was touched.
- The root `.env.local` `FLIPFLOP_TEST_ADMIN_DATABASE_URL` was parsed and used by the isolated runner; local PostgreSQL created only uniquely named `_test` databases. The runner still stops during Alembic upgrade before pytest starts because the root revision assumes a pre-existing legacy `listings` table. No application database was touched and no pytest cases ran.
- A disposable-only `create_all` plus `-x reconcile_existing=true` probe is not a safe fresh-install shortcut. It first exposed an incompatible historical `model_versions.artifact_path` type. After checking the wider migration chain, it exposed a deeper collision: current ORM `orders` is a workshop workflow table (enum status and customer/build fields), while revision `20260622_0008` creates a checkout/payment table with a different required field set and string payment status. Reconciliation correctly rejects this mismatch. Resolve the orders ownership/schema contract and add a real legacy baseline/forward migration before retrying isolated tests; do not weaken reconciliation to make the upgrade appear green.
- This remains a dirty working tree with 266 changed/untracked paths at assessment time. No files were staged or committed. Do not deploy or label this a release candidate until the API isolated suite, storefront/admin journeys, current catalogue readiness, provider sandbox flows, legal/operational gates and staging release rehearsal are complete.

### 19 October 2026 order-schema continuation

- Selected schema contract: one order record with separate fulfilment and payment statuses. `orders.status` remains the fulfilment state for compatibility; `fulfilment_status` is an ORM/API alias, and `payment_status` records payment/refund lifecycle independently.
- Added forward migration `20261019_0001_separate_order_payment_status.py` to backfill payment states, customer snapshots and capacity fields. Checkout/webhook paths persist paid state and buyer snapshots; cancellation/refund paths expose refund-pending/refunded states. Customer/admin order response schemas expose both states.
- Aligned the clean-install ORM baseline with historical migration definitions for model artifact path, PC build stage storage, manual-build policy ID length, warranty indexes, shipment provider-event uniqueness and checkout snapshot uniqueness. Added missing `Favourite` model registration.
- Updated migration reconciliation to adopt existing named constraints only when reflected definitions match, and made conflicting historical revisions safe when the current canonical schema already contains the corresponding object. Incompatible schema definitions continue to fail closed.
- Isolated migration probe advanced past the prior missing-`listings`, conflicting-orders, warranty-index, shipment-uniqueness and duplicate customer-problem-constraint failures. Latest probe proceeded through the migration chain to pytest; test execution then failed because outbound network access is disabled by the test harness (`Outbound network is disabled in tests`, localhost addresses). This does not establish a passing test suite. Exact failing case names were not retained in the filtered output.
- Focused payment/order tests have not yet been independently verified. API compile/history checks and final diff hygiene are pending after this continuation. No application database, staging environment, production system or provider was modified.
- Deployment readiness remains **not ready**: database-backed regression tests and end-to-end journeys remain unverified; provider sandbox, commercial data, legal/operational checklist and staging rehearsal gates remain open. The broader working tree is still dirty and has unrelated changes; no files were staged or committed.
