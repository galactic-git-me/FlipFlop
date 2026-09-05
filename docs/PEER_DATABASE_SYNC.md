# Two-way peer database sync

The two databases are equal peers with eventual consistency. Neither is a
fixed "master" — the synchroniser uses `updated_at` as the conflict clock
and copies the newer row to the other peer. Re-running a cycle is safe and
idempotent. It never performs a blind/unconditional delete.

Run it from `flipflop-api` after both databases have the same Alembic schema:

```bash
DATABASE_URL=postgresql://...local... \
PEER_DATABASE_URL=postgresql://...andromeda... \
PEER_SYNC_NODE=local \
python -m app.services.peer_sync --once
```

The command is a dry run unless `--write` is supplied (or `PEER_SYNC_WRITE=1`
is set). Start with `--once`, compare the `copied`/`skipped`/`conflicts`/
`deletes`/`errors` counters, then enable `--write` only after a database
backup and schema check. Run a second instance on Andromeda with the URLs
reversed and `PEER_SYNC_NODE=andromeda`.

## Tables

The default allowlist covers `customers`, `admin_users`, `orders`,
`order_checklists`, `order_photos`, `gem_radar_scan_runs`,
`gem_radar_listing_observations`, `gem_radar_sold_observations`,
`gem_radar_amazon_observations`, `submission_queue`, and
`inventory_units`/`inventory_events` — 12 tables. A table is only synced
once it validates: it must have a primary key and an `updated_at` column
on **both** peers, checked on every run. A table that fails validation is
skipped (with a reported error) and the rest of the sync continues — it
does not abort the whole cycle.

`gem_radar_scored_listings` is deliberately **excluded**. It has a
`UNIQUE (listing_id)` constraint separate from its `id` primary key, and
both peers have independently scanned and scored the same real eBay
listings for months before this sync existed, under completely different
autoincrement ids. A first-time PK-based merge collides on nearly every
row (measured: ~40k of ~41k rows) — the engine handles that safely (each
collision is caught per-row and recorded as a `unique_constraint_violation`
conflict rather than corrupting data or crashing the batch — see the
fast-path/slow-path split in `sync_once`), but redoing a ~40k-row
per-row-transaction reconciliation on every 30-second cycle is far too
slow, and repeatedly re-attempting the same known collision every cycle is
wasted work. This table needs a one-time reconciliation decision (e.g.
pick a canonical winner per `listing_id`, or dedupe one side) before it
can safely rejoin `PEER_SYNC_TABLES`.

## Secret handling

Secrets (Stripe keys, eBay/Google/GitHub OAuth client secrets, the app JWT
signing key, IMAP/SMTP credentials, encryption keys) live exclusively in
each node's own `.env` file (`flipflop-api/app/config.py`) and are never
database rows — the sync engine has nothing to do with them.

Within the synced tables, `peer_sync.py` additionally excludes any column
whose name matches `SECRET_COLUMN_PATTERN` (`token`, `api_key`, `secret`,
`encryption_key`, `client_secret`, `credential`) — defense in depth, since
no currently-synced table actually has one of these as a plain column.

`customers.password_hash` and `admin_users.password_hash` are **not**
excluded and sync as ordinary data. This is a deliberate decision: a
bcrypt hash is not the plaintext password, and both peers must agree on it
for a customer/admin to be able to log in on whichever node their request
lands on after a password change. `orders.stripe_payment_intent_id` is a
Stripe reference ID (not a secret) and also syncs normally.

## Deletes

No table in this schema has a `deleted_at` column, so deletion is handled
via an explicit tombstone mechanism rather than soft-delete propagation:

1. Every successful copy or up-to-date comparison records the row's key,
   `updated_at`, and a content checksum into `peer_sync_state` — on **both**
   peers, not just the one that received the write.
2. On the next cycle, before any inserts/updates run, the sync compares
   each peer's currently-known keys (from `peer_sync_state`) against what
   currently exists in its table. A key that was known before but is gone
   now is a candidate delete.
3. The candidate is only actually deleted on the other peer if that peer's
   current row checksum still matches the checksum recorded at the last
   sync — i.e. it's provably untouched since. In that case a real `DELETE`
   is issued and the bookkeeping is cleared.
4. If the other peer's row has since been edited independently, the delete
   is **not** applied. Instead a `peer_sync_conflicts` row with
   `winner = 'delete_skipped_local_edit'` is recorded and both rows are
   left as-is for manual reconciliation.

This ordering (tombstone check before the insert/update pass) matters: it
prevents a row deleted on peer A from being silently re-inserted from
peer B's still-present copy in the same cycle.

## Performance: the fingerprint short-circuit

At real production row counts (100k+ rows in some Gem Radar tables), doing
a full row-by-row comparison of every table on every 30-second cycle over
an SSH tunnel doesn't fit in the cycle interval. Before the real
comparison, each table is checked with one cheap query per peer —
`COUNT(*)` and `MAX(updated_at)` — and skipped entirely for that cycle if
both numbers match on both peers. This turns a steady-state cycle (nothing
changed) into two tiny aggregate queries per table instead of four full
table scans, which is what makes the 30-second interval workable at all.

Known, accepted limitation: if a row exists with byte-identical
`updated_at` and a different value on each peer, but the table's overall
row count and max `updated_at` are otherwise identical between peers (i.e.
literally nothing else about the table differs), the fingerprint check
will skip that table and the tie will not be detected until something else
changes the count or max. In practice this requires two independent
writers to land on the exact same primary key and the exact same
timestamp with no other table activity happening — a scenario ordinary
traffic essentially never produces, since any other insert/update on the
table changes the fingerprint and forces the real comparison. This is a
deliberate tradeoff in favor of the sync actually completing within its
interval at real data volumes.

## Conflicts

- `updated_at` differs → newer row wins, copied to the other side.
- `updated_at` is identical but content differs → recorded as
  `peer_sync_conflicts.winner = 'tie_kept_both'`; neither side is
  overwritten, and this needs manual review.
- A delete is skipped because the target was edited locally →
  `winner = 'delete_skipped_local_edit'` (see above).

`peer_sync_conflicts` is a plain audit table — nothing auto-resolves from
it. Query it periodically; a nonzero conflict count means a human decision
is needed.

## Run history and health

Every cycle writes a row to `peer_sync_runs` (node, started/finished,
status, `tables_synced`/`copied`/`skipped`/`conflicts`/`deletes`/
`errors_count`, `error_detail`) on the `local` engine, including failed
runs (e.g. the peer database/tunnel was unreachable). Check status without
starting a sync cycle:

```bash
python -m app.services.peer_sync --health
```

This prints the latest run per invocation plus a raw TCP reachability
check against both `DATABASE_URL` and `PEER_DATABASE_URL`. No HTTP
endpoint or frontend surface was added for this — it is a CLI/DB-only
concern by design, to avoid touching the admin UI.

## Retries

Batch reads/writes are retried up to 3 times (1s/2s/4s backoff) on
connection-class errors (`OperationalError`, `DBAPIError`,
`ConnectionError`, `TimeoutError`) before that table's error is recorded
and the sync moves on to the next table. A whole-cycle failure (e.g. the
peer is unreachable at startup) is caught, logged to `peer_sync_runs` as
`status = 'failed'`, and re-raised so the process supervisor (systemd /
the Windows runner loop) can retry the whole cycle on its own schedule.

## Networking: the reverse tunnel

Andromeda cannot reach the Windows machine directly (no inbound path), so
a single SSH connection from Windows carries both directions:

- `-L 15432:172.23.0.3:5432` — Windows reaches Andromeda's Postgres
  container on `127.0.0.1:15432`.
- `-R 15433:127.0.0.1:5432` — Andromeda reaches Windows' local Postgres on
  its own `127.0.0.1:15433`.

`scripts/start-peer-sync-tunnel.ps1` opens this tunnel, watches it (and the
sync runner process) every 30 seconds, and restarts either if it drops.

## Start / stop / check

**Windows** (one-time registration, then automatic at every boot and logon,
restarting itself up to 999 times at 1-minute intervals if it dies):

```powershell
scripts\install-peer-sync-task.ps1      # registers the FlipFlopPeerSync scheduled task
schtasks /run /tn FlipFlopPeerSync      # start it immediately without logging off/on
schtasks /query /tn FlipFlopPeerSync /v # check status
schtasks /end /tn FlipFlopPeerSync      # stop it
Get-Content logs\tunnel.log -Tail 50    # tunnel watchdog log
Get-Content logs\peer-sync.log -Tail 50 # sync runner crash/retry log
```

Explicitly **not** PM2 — this project does not use PM2 for background
processes; the scheduled task wraps the existing self-looping PowerShell
runner instead.

**Andromeda** (one-time deploy, then a restart-safe systemd --user service):

```bash
ssh andromeda 'bash -s' < scripts/deploy-peer-sync-andromeda.sh   # deploy + enable
ssh andromeda systemctl --user status peer-sync.service           # check
ssh andromeda systemctl --user restart peer-sync.service          # restart
ssh andromeda journalctl --user -u peer-sync.service -f            # tail logs
```

**Ad hoc / manual runs from either machine:**

```bash
python -m app.services.peer_sync --once            # dry run
python -m app.services.peer_sync --once --write    # apply once
python -m app.services.peer_sync --health           # status without syncing
```
