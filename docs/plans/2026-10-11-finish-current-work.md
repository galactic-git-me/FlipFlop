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
