# Data router

- `flipflop-api/data/` — runtime and imported backend data.
- `flipflop-api/alembic/` and `flipflop-api/migrations/` — schema migration history.
- `flipflop-api/app/models/` and `flipflop-api/app/schemas/` — persistence and API data contracts.
- `flipflop.db` — root local database artifact; inspect schema before using it.
- `flipflop-*.csv` and `*.xlsx` — catalogue and component exports used for reconciliation and analysis.
- `extract_*.py` and `validate_*.py` — catalogue extraction and validation utilities.
