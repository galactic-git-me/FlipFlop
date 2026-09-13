# Production-to-local database refresh

Production on Andromeda is the source. Local PostgreSQL at
`127.0.0.1:5432/pcflipper` is the destination. The browser extension submits
scraped listings to `https://www.theflipflop.shop`, so those observations
arrive in production first.

The refresh copies the entire database: all schemas, tables, rows, sequences,
and OAuth token columns. There are no table or token exclusions. This includes
the existing foreign-table definitions; pg_dump copies their definitions,
not the external data referenced by those foreign tables. Database server
roles and filesystem assets are outside a database dump.

## Operation

Run `scripts/run-production-to-local-sync.ps1`. The Python implementation:

1. Rejects any destination other than the local database and takes a local
   advisory lock to prevent simultaneous refreshes.
2. Downloads a consistent full production pg_dump archive over SSH.
3. Restores into a new staging database, counts every ordinary table, and
   verifies the copied eBay tokens can be decrypted.
4. Pauses local API workers, saves a local pg_dump backup and `.env.local`
   backup, then atomically renames the databases. The previous local database
   is retained as an additional rollback copy.
5. Installs the eBay application/encryption settings needed by the copied
   tokens, clears obsolete local static production eBay tokens, and restarts
   the services that were running. Other local environment settings remain local.

Local automatic workers use `WEB_ONLY=true` so production jobs copied into the
mirror do not execute a second time. Manual eBay operations continue to route
to production through the admin proxy.

Backups and a JSON report with timestamps, destination, per-table row counts,
and outcome are stored under `%LOCALAPPDATA%/FlipFlop/database-backups`.
These archives contain credentials and are outside the repository.

## Local prerequisites

PostgreSQL 18 client tools and the existing `andromeda` SSH alias are required.
Set `LOCAL_POSTGRES_ADMIN_USER` and `LOCAL_POSTGRES_ADMIN_PASSWORD` in the
untracked `flipflop-api/.env.local`. Administrator access is needed for the
staging database and the production `postgres_fdw` extension. These settings
are used only against the guarded local destination.

After the first successful refresh, run
`scripts/install-production-to-local-sync.ps1` to install the daily 04:00
Windows task. It runs in the user's signed-in session, with missed starts
enabled. The previous `FlipFlopPeerSync` task and Andromeda's user
`peer-sync.service` are disabled. Legacy local peer-sync entrypoints now call
the one-way refresh and never start a reverse tunnel or peer writer.

## Current rollout status

The first production snapshot has been downloaded. Initial restore stopped
before changing local data because the local `flipper` role is not an
administrator. Supply the local administrator configuration above, then run
and verify the first refresh before installing the daily task.
