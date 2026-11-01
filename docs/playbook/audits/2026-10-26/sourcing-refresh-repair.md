# Sourcing refresh repair

The dashboard repeatedly reported partial refresh failures. Admin logs identify the listings request timing out at 15 seconds. Backend logs also show asyncpg rejecting more than 32,767 query arguments.

Cause: the endpoint fetched all recently active listing IDs into Python and expanded them back into an IN clause. It also scanned unrelated product observations for market links and review enrichment on every page poll.

Changed: retain active IDs in a database subquery; scope market-link/review/bestseller enrichment to page product identities. Preserve current-row and filter semantics. Give only the listings fetch 30 seconds of headroom while retaining the existing in-flight guard and stale-value/error behaviour. Queue polling keeps its 15-second timeout.

Verification: a new offline check against the actual endpoint query construction failed before the fix with 40,001 parameters and passes afterwards. Python compilation and sourcing TSX syntax validation passed. Through the running DEV admin proxy, CPU/GPU/RAM each returned HTTP 200 and 100 rows in 4.55/7.58/4.63 seconds. Queue status returned HTTP 200 in 0.17 seconds. Earlier concurrent requests still exceeded 15 seconds under load, which motivated retaining timeout headroom rather than claiming latency is guaranteed.

No database migration or data mutation was required. Browser rendering and a full frontend build were not verified in this repair.
