# Four simultaneous DEV extraction requests

Implemented and activated on 27 October 2026.

- Gateway concurrency and Ollama parallelism are both four. Launchers and startup health checks retain this setting.
- Ollama 0.32.6 forces Qwen3.5 to one slot. Explicitly approved DEV-only canonical product extraction now uses Qwen3:4b through `DEV_CPK_OLLAMA_MODEL` in the ignored backend `.env.local`.
- Shared default and production model configuration remain Qwen3.5:4b. The shared local gateway concurrency changed as authorized.
- DEV extraction uses 2,048 context tokens, a 128-token prompt batch and reasoning disabled. Its override has no cloud fallback. Deterministic MPN/source-identity resolution still precedes LLM extraction.
- The gateway retains production-first queue ordering and GPU-only enforcement. Each streamed response is bound to its own upstream response so overlapping requests cannot cross streams.

## Verified

Five offline model-routing/request checks passed. A separate offline stream check verified four simultaneous streams, a fifth waiting, production queue priority and correct response isolation. PowerShell syntax checks and Python compilation passed.

The actual runner logged `n_seq_max = 4` and `n_slots = 4, n_ctx_slot = 2048`. GPU residency was checked through `/api/ps`. The authorized model canary passed all four fixtures: AMD Ryzen 5 5600, Intel i5-12400F, Corsair Vengeance LPX DDR4 RAM and Samsung 970 EVO Plus SSD. It made no database writes. Its 69.58-second elapsed time included model loading/queue contention and is not a steady-state throughput benchmark.

The API reloaded into DEV and the persisted scrape queue resumed. This confirms functioning parallel extraction, not a fourfold end-to-end scrape speedup or a comprehensive model accuracy evaluation. Other scraping, database, classification and shared-model workloads can still limit overall throughput.

Runtime evidence: [JSON](four-way-dev-extraction.json).
