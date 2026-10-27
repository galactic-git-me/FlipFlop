# Sourcing refresh warning: verified DEV correction

The Stats screen polled the full scored-listing endpoint every five seconds despite not displaying that table. During the active scrape, the exact request exceeded 35 seconds directly and the admin proxy returned HTTP 500 after 30.12 seconds. The queue endpoint remained responsive. A later repeat completed in 5.69 seconds, showing load-dependent latency rather than a permanent route failure.

Refresh now requests the listings table only on the Listings tab, at 15-second intervals. Queue refresh continues every five seconds on Stats. A failed visible request identifies Listings or Processing queue, retains previous data and retries; late results from another tab cannot restore its warning.

Verification: five focused refresh-policy checks passed; admin TypeScript checking passed; new helper/test ESLint passed. On the existing authenticated DEV browser tab, Stats displayed without the warning and Listings loaded 100 rows out of 2,415 matching CPU listings. Returned to Stats with the queue still processing. No backend restart, scraper restart, production change or database migration was needed. Screenshot: `output/sourcing/refresh-fixed.png`.

This removes unnecessary polling and the unrelated Stats warning. It does not establish that every listing query will always complete within its timeout under any load. Actual visible request failures remain reported.
