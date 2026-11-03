# Database schema release gate

DEV is the local `pcflipper` PostgreSQL database. PROD is the remote Andromeda
database. The API must not create or alter schema at production startup; schema
changes go through Alembic migrations.

## Validate in local DEV

After adding or changing a migration, run:

```powershell
python scripts/validate-dev-schema.py
```

The command is restricted to loopback `pcflipper`. It applies pending migrations
to local DEV, runs the isolated migration/startup schema tests against a
disposable local database, verifies the local schema, and writes
`docs/database/dev-schema-validation.json`. Commit that validation record with
the migration change and merge the change into `dev` before promoting it.

The record includes hashes of every Alembic migration. Any later migration edit
invalidates the record until validation is repeated.

## Production enforcement

Production PR checks and the production deployment workflow verify that:

- the attested source commit is in DEV history;
- the release's migration files exactly match those tested in local DEV;
- the attested migration head matches the release's single Alembic head; and
- local migration tests and schema checks passed.

The remote deployment script repeats the check immediately before invoking
`alembic upgrade head`. A missing or stale record blocks the deployment before
production migrations run. Production API startup skips schema DDL; deployments
apply schema only through this gated Alembic step.

No workflow deploys DEV remotely. FlipFlopXtension remains in its existing local
workflow.
