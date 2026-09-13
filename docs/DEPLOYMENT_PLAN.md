# FlipFlop deployment plan

> Database refresh update (12 September 2026):
> [PRODUCTION_TO_LOCAL_SYNC.md](PRODUCTION_TO_LOCAL_SYNC.md) supersedes the
> extension-routing and secret-exclusion statements below. The extension
> currently writes to production. The approved refresh is a complete one-way
> production-to-local copy, including OAuth tokens. Its first restore awaits
> local PostgreSQL administrator configuration; no local replacement has run.

This is the short, authoritative description of how FlipFlop is run.

## 1. Two separate environments

There are two complete copies of the application:

| Environment | Location | Purpose |
|---|---|---|
| Local/development | `C:\Users\mclar\CODING\FlipFlop` | Development, testing, and local admin work |
| Production | Andromeda, `/home/mac/CODING/FlipFlop-production` | Live website, live eBay operations, and production data |

The two checkouts and their databases are separate. Local work must never use the production database directly.

## 2. Local services

The established local layout is:

| Service | Local address |
|---|---:|
| Admin UI | `http://localhost:4312` |
| Main API | `http://localhost:4311` |
| GemRadar API | `http://localhost:18000` |
| Local PostgreSQL | local Docker/PostgreSQL database |
| Local Redis | local Docker/Redis instance |

The admin UI talks to the local main API on port `4311`. GemRadar is a separate service on `18000`.

The normal local launcher starts these local services by default. It does not connect to the production website, production API, production database, or the SSH database tunnel. Peer database synchronisation is an explicit opt-in operation only.

The older compose definitions that map the whole development API to `18000` are not the canonical local operator workflow and should not be used to infer the port layout.

## 2a. FlipFlop browser extension

`FlipFlopExtension` is a local-only operator tool. It seeds and refreshes listing data through a real browser, so it is not part of the production server deployment and must not be moved into the production Docker stack.

```text
Local browser + FlipFlopExtension
              |
              v
        Local main API (4311)
              |
              v
        Local development DB
```

The extension is used from the local machine because it requires an interactive browser session. Its normal responsibilities are:

1. Open the required marketplace pages in a real browser.
2. Collect and seed listing data through the local API.
3. Allow the local GemRadar and admin tools to process and inspect that data.
4. Leave the resulting approved/synchronised data available for the controlled database refresh to local development.

Production should receive data through an explicit, reviewed promotion step, not by attempting to launch a browser on the production API host. The extension must not write directly to the production database.

## 3. Production services

Production runs from the separate Andromeda checkout using Docker Compose:

| Service | Production address |
|---|---:|
| Public storefront | `https://www.theflipflop.shop` |
| Production admin UI | Andromeda, port `4312` |
| Production main API | Andromeda loopback, `127.0.0.1:4311` |
| Production GemRadar worker | Internal Docker service |
| Production PostgreSQL | Production-only Docker volume/database |
| Production Redis | Production-only Docker volume |

### Shared Ollama endpoint

Both environments use Ollama on the Prometheus host at `localhost:11434`.
The Andromeda host reaches that same daemon through the SSH tunnel that maps
Andromeda's `localhost:11434` to Prometheus' `127.0.0.1:11434`. The production
Compose services therefore use `http://host.docker.internal:11434`, which is
the Docker host gateway; using `localhost` inside a container would point back
to that container and silently send CPK/scoring requests to the wrong place.
The tunnel must be running before restarting `gemradar-worker`.

Port `4311` on Andromeda belongs to production. It is not a reason to start a production backend on the development machine.

## 4. Database separation and daily copy

There are two databases:

```text
Local database  <---- one-way daily copy ----  Production database
```

The daily copy direction is production to local. It is intended to give local development a current working dataset without allowing local changes to alter production.

The extension is a separate concern from that daily copy. It is a local browser-based source/ingestion process, whereas the daily database copy is a production-to-local refresh. Those flows must not be silently combined:

```text
Browser extension -> local API -> local DB
Production DB     -> (daily, one-way refresh) -> local DB
```

If extension-seeded data is required in production, that is a separate promotion workflow and must be explicitly designed and authorised. It must not be achieved by reversing the daily database copy. This is the key exception to resolve: the refresh is production-to-local, while extension data may need a controlled local-to-production promotion.

Rules:

1. Production is the source of truth for copied data.
2. Local is the destination and may be overwritten by the daily refresh.
3. The copy must never write from local back into production.
4. Secrets, tokens, API keys, OAuth credentials, and other production-only values are excluded.
5. Schema migrations are applied deliberately to both databases; data copying is not a substitute for migrations.
6. A backup/snapshot is taken before replacing or restoring the local database.
7. The copy must be logged with source, destination, timestamp, row counts, and outcome.

The existing `peer_sync` code is a row-level peer synchroniser and currently supports bidirectional/continuous operation. That is not the final deployment policy above; it must be configured or replaced with a scheduled production-to-local refresh before it is treated as the daily database-copy mechanism.

## 5. Code deployment

1. Development changes are made and tested in the local checkout.
2. Changes are committed and pushed to GitHub.
3. Production deployment fetches the selected branch in `/home/mac/CODING/FlipFlop-production`.
4. Production advances only fast-forward to the selected commit.
5. Production migrations run before the API is restarted.
6. The API health check and public eBay callback check must pass.
7. The production database is never replaced by a local database during deployment.

## 6. Non-negotiable boundaries

- Never point the local application at the production database.
- Never point production at the local database.
- Never run local auto-commit/push tooling against the production checkout.
- Never use the local database as the source for the daily refresh.
- Never create a branch as part of deployment; deployment follows the selected existing branch by fast-forward only.

## 7. Items to make explicit in implementation

- Make the local `4311/4312/18000` environment variables canonical and remove conflicting defaults from older compose paths.
- Implement the scheduled, one-way production-to-local database refresh.
- Keep the production database backup and local pre-refresh backup.
- Add a dry-run and a clear health/status report for the daily copy.
- Define the controlled promotion path for extension-seeded listing data from local into production without granting the extension production database access.
- Keep the default local launcher fully local; production URLs and peer sync must require an explicit opt-in.
