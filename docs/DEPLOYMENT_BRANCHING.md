# Deployment branches

FlipFlop uses two branches with different responsibilities:

- `dev` is the development branch. Autosync is allowed to commit and push only
  to this branch. A push to `dev` runs the development validation workflow.
- `main` is the production branch. It is never updated by autosync and the
  production workflow has no push trigger.

When `scripts/start-all-servers.ps1` is started in LIVE OPERATOR mode, it
fetches both branches and lists every commit in `dev` that is not already in
`main`. The operator selects the last commit to promote (or chooses `0` to
leave production unchanged). The script then fast-forwards `main` to that
selected commit and starts the remote production deployment. A normal
development startup never performs this promotion.

The remote startup and deployment scripts verify that the production checkout
is on `main` and deploy only `origin/main`. If a production checkout is still
on `master`, startup stops with an actionable error instead of deploying the
wrong branch.
