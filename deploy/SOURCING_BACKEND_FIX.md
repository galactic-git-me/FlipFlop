# Sourcing backend repair

The 3 November 2026 production logs showed two independent failures:

- Sold-comps batches returned HTTP 500 when full eBay URLs exceeded the
  `source_url VARCHAR(1000)` column. Migration `20261104_0001` widens it to
  `TEXT`, retaining existing values and complete future evidence URLs.
- Canonical product extraction requested the unavailable
  `qwen2.5:7b-instruct`. The production Compose file now defaults both API and
  Gem Radar services to `qwen3:4b`, verified present on the production Ollama
  endpoint during diagnosis. `FLIPFLOP_OLLAMA_MODEL` overrides all four model
  settings together; select a model installed on that endpoint.

This fix is based on DEV and extends its `20261103_0002` migration head.
Production was at `20261101_0001` when inspected; the normal DEV-to-main
promotion must carry the intervening schema-alignment migrations too.
Production rollout requires approval. Before rollout, back up the
database, apply the migration chain, then deploy the model and Compose
changes together. Restarting services interrupts in-flight requests; use a
quiet scan window. Verify the selected model exists and responds, a sold
batch containing a URL longer than 1000 characters persists successfully,
and a complete scan no longer logs either failure.

Downgrading the column to `VARCHAR(1000)` fails if long URLs now exist;
PostgreSQL must not truncate evidence to permit rollback. The application
can be rolled back while leaving the widened column in place.

Offline regression checks (no database or provider calls):

```powershell
python flipflop-api/tests/test_sourcing_backend_contracts.py
```

These checks validate the ORM column, PostgreSQL migration SQL, Alembic
head and shared model default. They do not verify a PostgreSQL migration
or live scan.
