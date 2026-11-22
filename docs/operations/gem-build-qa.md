# GEM build compatibility QA

## Trigger and data flow

The GEM QA event is queued in the database transaction that clears the sweep signal, after the submission queue drains and Phase 2, catalogue publication, and listing lifecycle reconciliation succeed. The background worker reads eligible `SUPER_GEM` candidates, builds AM4 and AM5 snapshots, and runs the shared deterministic fit rules. It does not call an LLM, scrape provider, retailer, or marketplace.

A source-backed mismatch is reported as incompatible. Missing or unreviewed engineering facts remain unverified; neither state is labelled compatible. The sheet uses “Top SUPER_GEM candidate” rather than implying that the highest score is automatically compatible. The engine can therefore show blockers without silently endorsing a candidate. Full compatibility still depends on complete reviewed specs for every selected part.

The QA event contains the environment label and sweep completion timestamp as its run key. The existing extension completion payload does not include its own stable sweep ID, so retries while the singleton sweep signal is pending are deduplicated, but a delayed duplicate arriving after that signal has cleared cannot be proven to be the same extension run. For strict end-to-end per-run idempotency, the extension must generate and resend a stable sweep UUID; the extension source is not present in this isolated worktree.

## Google Sheets setup (DEV only)

The two workbook tabs are `AM4 GEM QA` and `AM5 GEM QA`. The API does not use the Companion's signed-in Google OAuth connection; that browser connection is not an application credential. Runtime publishing is disabled by default and additionally refuses to write when `FLIPFLOP_RUNTIME_ENV` is `LIVE`/`production` or the parsed `APP_ENV` is not a dev value.

To enable future dev writes:

1. Create a dedicated Google service account in the team's approved Google Cloud project, with Sheets API enabled.
2. Share only the `PC Deal Log (Black Friday UK)` workbook with that service-account email as Editor. Do not grant broad Drive access.
3. Store its JSON key in the deployment's secret manager and mount it read-only outside the repository; never add key JSON to Git, `.env` files, synced files, logs, or the workbook.
4. In the DEV API runtime only, set `GEM_BUILD_QA_GOOGLE_SERVICE_ACCOUNT_FILE` to the mounted file path, `GEM_BUILD_QA_SPREADSHEET_ID` to the existing workbook ID, and `GEM_BUILD_QA_SHEETS_ENABLED=true`.
5. Keep the setting absent/false in LIVE. Validate the service-account share and sheet permissions in DEV before enabling scheduled writes.

The publisher writes only the QA tabs and includes the run ID for duplicate suppression. Events and computed snapshots remain stored in the QA event table when the publisher is disabled or credentials are missing.
