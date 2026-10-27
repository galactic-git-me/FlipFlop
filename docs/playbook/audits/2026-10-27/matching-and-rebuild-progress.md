# Matching repair and Playbook cost rebuild

DEV only. Whole-computer/component regression fixed in shared identity detection, ingestion cleanup and supplier selection. Genuine SSDs advertised for laptops, all-in-one CPU coolers and PC cases retain component eligibility.

Applied 733 obsolete complete-system identity removals with full backup; recalculated 240 affected price aggregates. One concurrently owned row was skipped, never overwritten. Source observations and sold evidence retained.

Fresh saved-capture reconciliation examined 55,379 listings and applied 440 identity changes; all saved keys verified, no concurrent skips, 165 price aggregates recalculated. In the exact-MPN cohort, products linked across sources rose 206 to 213; direct-retailer products rose 71 to 73. These are not counts of all products with title-based matches.

See [fixed-cohort coverage](bestseller-link-coverage.md) for the same 90 bestsellers, with actual Playbook same-product validation and separate exact-ASIN capture/CPK-join columns. Earlier raw-CPK-only figures were less strict and should not be treated as validated supplier counts.

All eight focused backend check files passed. The stored-only DEV cost rebuild completed and saved all 24 proposals across eight segments: 24 complete hardware BOMs and 24 priced drafts. It did not approve or publish, made zero provider requests, and deferred model compatibility work to the existing thread. Backups and the generated Playbook are under `rebuilt-playbook/`.

## Processing throughput sample

At 00:44:58 UTC: 4,061 completed pages, 364 waiting. At 00:46:37 UTC: 4,086 completed, 339 waiting. That is 25 pages in approximately 99 seconds, or 15.2 pages/minute, with four processing and zero failed. No net incoming pages in that interval. The early 23:57:45–00:03:10 sample was nine pages in approximately 325 seconds, or 1.66 pages/minute. This approximately ninefold difference is observational, not a controlled benchmark: page sizes, cache hits and concurrent workload differ.

## Completed rebuild

Galileo draft price: GBP 1,432.58. All 24 builds still have publication blockers: Windows licence-source review affects all 24; 13 report compatible-combination search-limit exhaustion; 12 need compatibility confirmation; five have a selected CPU explicitly unavailable; three have stale/missing RAM captures. These figures overlap and are not a count of distinct affected builds. No build was declared publishable. See [rebuilt Playbook](rebuilt-playbook/playbook.md).
