# Deployment branches

FlipFlop uses two branches with different responsibilities:

- `dev` is the development branch. Autosync is allowed to commit and push only
  to this branch. Feature pull requests target `dev`, where CI and the DEV
  runtime journey are completed before production promotion.
- `main` is the production branch. It is never updated by autosync and the
  production deploy workflow has no push trigger. Pull requests into `main`
  must match the current `dev` source tree, and GitHub branch protection
  requires the `checks` status check and pull-request flow for administrators
  too.

After the exact DEV commit has passed its runtime check, open a pull request
for `main` only when its tracked source tree matches `dev`. This permits a
promotion branch that preserves production-only generated artifacts while
ensuring application code and migrations are the tested DEV versions. Tag
that exact merge commit. Release and deployment checks require a passing
DEV-parity CI run for the associated production pull request.

The remote startup and deployment scripts verify that the production checkout
is on `main` and deploy only `origin/main`. If a production checkout is still
on `master`, startup stops with an actionable error instead of deploying the
wrong branch. Development startup uses the hot-reloading Next.js dev server;
production build output is generated during deployment and is not a source of
DEV code.
