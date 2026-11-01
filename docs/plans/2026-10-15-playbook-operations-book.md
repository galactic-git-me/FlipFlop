# Playbook operations book

The Playbook tab in Curated Builds is the central operational workspace. Every
page uses the same customer-type rows and budget columns. Page changes retain the
selected cell. Catalogue and listing-photo intake remain supporting tools.

Pages: recommended build; market and target pricing; costs, profit and three
delivery products; linked listings; upsell components; upsell commercials;
listing media; 3D assets; performance; live status; approvals; history;
distribution; compatibility; software; automation.

Use persisted exact-cell evidence. Distinguish pending proposals from approved
offers and source prices from complete-build comparisons. Missing sold prices,
walk-away thresholds, channel identity or audit events remain explicitly absent.
Do not derive commercial authority from the view. Existing revision, compatibility,
supplier, commercial and publication checks still own consequential actions.

Implementation: a read-only operational book projection, shared matrix and cell
detail, embedded existing review tools, and append-only operational events using
the existing snapshot store. No new publication or repricing automation.

Validation: focused backend projection/event tests, matrix switching and empty
evidence tests, existing source-review tests, TypeScript and lint, then desktop
and narrow-screen browser checks. Production publishing remains a separate gate.

## Implementation and validation

Implemented the 16-page book in the existing Curated Builds entry route with
compact/detailed matrix views, retained cell selection, shareable page/cell URLs,
embedded scoped commercial/engineering approvals, exact product media/asset
tools and preserved setup controls. Added a read-only operational projection and
same-transaction append-only change records using the existing snapshot table.

Verified: 19 focused admin tests, five pure backend projection/event tests,
PostgreSQL event persistence/immutable evidence/rollback in a newly created and
removed disposable database, TypeScript and targeted lint. Authenticated local
browser checks switched all 16 pages without losing the selected cell; desktop
and 390px mobile screenshots were inspected and the mobile document width stayed
at 390px. The current book endpoint returned 24 cells. An isolated production
admin build passed compilation, TypeScript and all 72 static pages.

Evidence gaps remain explicit: exact-build active-market observations, sold-market
evidence where absent, approved walk-away thresholds, historical drafts that were
overwritten before event recording, and external channel records lacking exact
cell identity. No supplier/product/price/publication approvals, channel changes or
production deployment were performed as part of this consolidation.

## Evidence continuation — 15 October 2026

Added explicit engine-derived proposed floors, net operating cost/revenue and VAT;
the approved floor requires matching revision, policy version, definition and BOM.
Added exact build-assignment channel joins, direct storefront product records and
manual eBay lifecycle records, with conflicts/unassigned records held for review.
The pricing page now exposes build-specific sold-evidence coverage without
promoting it into a cell market price. Corrected saved-facts rebuild to reuse its
already completed local catalogue sync rather than repeat the remote default.

Current DEV reads: 24 cells, four unassigned channel-presence records and 159 sold
observations across two builds. No cell commercial policies or reliable cell
market comparisons were found. These are evidence gaps, not zero-valued prices.
Verified 21 admin tests, nine backend tests, TypeScript, targeted lint and local
browser review sections. A fresh isolated production admin build passed.
The automatic source refresh was active during validation; no provider capture,
source approval, offer publication or channel mutation was initiated by this pass.
# Exact-cell market review implementation

Implemented source collection and approve/reject APIs under
`/api/commerce-intelligence/playbook-service/market/{playbook_id}/{cell_id}`,
selected-cell Pricing/Approvals controls, separate sold/current medians,
append-only collection/decision history, BOM-bound approval expiry, and feeding
approved sold evidence into the existing three-mode commercial quote engine.
Source prices are immutable review inputs; approvals require three distinct
sold complete-PC comparisons and operator verification of the full BOM.
Unknown delivery, condition and mismatched title anchors cannot be approved.
Recalculation is explicit and never publishes automatically.

Validation includes pure matching/approval guards, an isolated in-memory SQL
session persistence/replay test, UI approval prerequisites and error states,
and a real authenticated browser collection. The live collection returned no
sold comparisons and rejected unrelated component listings; no real evidence
or publication was approved. Production-provider evidence availability remains
an operational input, rather than an implemented price being invented.

Latest checks: 20 backend unittest cases (including SQLite session persistence),
8 focused book/market UI cases, TypeScript, targeted ESLint and isolated webpack
production build passed. Browser collection persisted batch 48 with 30 current
listing candidates and no sold results; mismatch/condition guards prevented
approval, and the 390px view had no document overflow. No real evidence was
approved. PostgreSQL concurrency and production deployment were not exercised.
The broader commercial page suite has two failures expecting the removed
workshop-capacity form; those unrelated expectations were left untouched.

