# CPK repair implementation checkpoint

26 October 2026. This is an implementation checkpoint, not a publication-readiness claim.

## Verified evidence

The read-only shadow report records its target: local `pcflipper`, schema `public`, search path `"$user", public`. The running DEV API uses the same local database configuration, with no DATABASE_URL or PGOPTIONS override in its process environment. No historical identities were reassigned by this audit.

Latest snapshot: 13,508 listings; 131 with a validated GTIN or recognised manufacturer part number; eight cross-vendor exact-identifier groups split between existing CPKs. 1,254 cached assignments were flagged by contradiction checks. These are review candidates, not 1,254 proven incorrect products: manufacturer versus board-partner metadata can also produce flags. These figures measure captured identifier coverage, not retailer stock coverage.

See `cpk-shadow-assignment-report.json` for source rows and proposed clusters. Do not redirect an old CPK wholesale: previously collided keys can contain different variants.

## Implemented

- Capture and retain GTIN, MPN, model and brand through the extension schema/converter and API contract. Scope JSON-LD Product identifiers to the exact captured product URL.
- Validate GTIN checksums and compare UPC/EAN through a padded internal key. Preserve meaningful manufacturer part-code suffixes.
- Identifier registry migration and resolver: immutable internal product CPK, namespaced aliases, provenance, transaction locks and explicit conflicting-identifier outcomes. Catalogue reconciliation consults this resolver before legacy lookup. The Playbook's legacy metadata writer is disabled when the registry is present.
- Revalidate cached assignments against the current title and explicit variant facts. Refuse family-only RAM/SSD aliases lacking evidence for the specified variant.
- Preserve raw captures even when an ASIN-tagged search result does not match the target; search tags are context, not proof of identity.
- Recompute the old and new market aggregates when a listing changes CPK; recompute the old aggregate when its contribution is quarantined.
- Fix the component search feed's stale CPK loop variable and prefer recognised exact manufacturer part codes over truncated marketing titles.
- Preserve captured retailer URLs during phase-two classification instead of replacing them with fallback search URLs.

## Validation performed

New offline checks only, with no provider calls or database writes:

- `tests_unit/test_cpk_identifier_resolution.py`: 9 passed.
- `tests_unit/test_cpk_registry_decisions.py`: 4 passed (fake SQL results).
- `tests_unit/test_cpk_price_reassignment.py`: 4 passed (fake SQL results).
- Extension `src/content/product-identifiers.test.ts`: 4 passed.
- Extension `npx tsc --noEmit`: passed.
- Python compilation of changed modules: passed.

The dotenv parser emits an existing line-one warning when checks run from the repository root. No secrets were printed. This warning remains unexplained and is not being hidden as a clean runtime result.

## Remaining before operational completion

1. Validate the registry migration and persistence SQL in the approved isolated database workflow. Offline decision tests do not verify PostgreSQL locking, constraints or migration execution.
2. Prepare and apply a per-listing historical backfill with saved old assignments and conflict review. The migration is not applied and the registry is not operational yet; legacy guarded fallback remains in use when the tables are absent.
3. Reconcile historical observation CPKs and all price sources, not just current listing contributions. Old sold/Amazon/Scan observation aggregates must not retain collided identity assignments.
4. Build/reload the DEV extension and verify real captured identifiers end to end. Current search cards may omit identifiers; targeted product-detail enrichment is still required to close that coverage gap.
5. Re-run the bestseller/build-to-offer audit, rebuild proposals and inspect publication blockers using repaired supplier identities and current active offers.

No production migration, historical mass reassignment, extension reload or build publication was performed in this checkpoint.


## Subsequent search-only policy implementation

The later agreed search-results-only policy is implemented and applied to DEV. Manufacturer plus exact MPN now works against the existing CPK schema without requiring the optional identifier registry migration. Capture incidental barcodes only; no detail-page enrichment was added. See `search-matching-before-after.md` for verified before/after counts, backups, concurrent-row exclusions, and the extension reload boundary. Earlier statements in this checkpoint that all MPN matching is inactive until registry migration are superseded by this implementation; the optional alias-table migration and broader historical sold-data cleanup remain separate work.
