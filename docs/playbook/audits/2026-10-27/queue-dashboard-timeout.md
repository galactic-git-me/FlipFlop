# Processing queue refresh timeout

The earlier Stats fix removed hidden listing-table polling but not queue-monitoring load. Live queue-status probes took 10.5 seconds, near the 15-second UI timeout. `get_live_items` claimed to return metadata but selected whole ORM submissions including every scraped listing JSON payload; queue-items and durable pipeline hydration requested up to 100 and 500 submissions respectively. Pipeline polling repeated every second.

Changed the shared query to select metadata and SQL JSON array length only. Both API consumers now use `listings_count`. Progress polling is every five seconds with its existing no-overlap guard. No data removed, queue concurrency unchanged, errors still reported.

Verified the generated SQL does not select raw payloads. Focused offline check and Python compilation passed; admin TypeScript passed. Runtime admin-proxy requests returned HTTP 200: queue-status 3.42s, queue-items 3.45s, pipeline-status 3.61s. Existing sourcing browser tab displayed no warning and showed four processing, 315 waiting, 4,110 completed. This verifies recovery in the observed load; it does not guarantee that unrelated future service failures cannot trigger a truthful warning.
