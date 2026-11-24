# Engineering router

- `flipflop-api/app/` — primary Python API, routes, services, models, scrapers, workers, and Gem Radar.
- `flipflop-api/tests/` — backend integration, contract, and end-to-end checks; `flipflop-api/testing/unit/` and `flipflop-api/testing/manual/` — focused unit and standalone diagnostic checks.
- `flipflop-admin/testing/` — admin `unit/`, `e2e/`, and `manual/` checks.
- `services/ollama-priority-gateway/testing/` — gateway and launcher checks.
- `scripts/browser-listing/testing/` — browser-listing tests.
- `flipflop-admin/app/` — primary admin application routes and operational screens.
- `flipflop-admin/components/` — reusable admin UI components.
- `components/` — root-shared React components used by the main application surfaces.
- `../engineering/components/api-setup.md` and `../engineering/components/admin-setup.md` — component-specific setup notes.
- `docs/testing/platform-test-strategy.md` — approved scope, environments, journey matrix, safety boundaries, sequencing, and release gates for platform testing.
