# Deployment branches

FlipFlop uses two branches with different responsibilities:

- `dev` is the development branch. Autosync is allowed to commit and push only
  to this branch. Feature pull requests target `dev`, where CI and the DEV
  runtime journey are completed before production promotion.
- `main` is the production branch. It is never updated by autosync and the
  production deploy workflow has no push trigger. Pull requests into `main`
  must match the current `dev` source tree, and GitHub branch protection
  requires a pull request and the `checks` status check. Branches must be
  current with their base. Force pushes and branch deletion are disabled.
  These rules include administrators; reviews are not required for this
  single-maintainer repository.

All intended changes must arrive through a pull request targeting `dev`; raw
branches are never merged automatically. GitHub auto-merge is enabled for
non-draft pull requests from branches in this repository that target `dev`.
The workflow queues the PR and GitHub merges it only after the required
`checks` status succeeds and branch protection is satisfied. Fork PRs and
drafts are not auto-queued. Conflicts and stale branches remain blocked until
they are resolved and the PR is updated. PRs targeting `main` are not
auto-queued. Keep unrelated or unfinished work in its own branch/PR rather
than combining every dirty worktree into one release.

DEV auto-merge uses the repository secret `FLIPFLOP_DEV_MERGE_TOKEN` so the
merge still triggers the normal post-merge DEV validation and worktree cleanup
workflows. Set it to a fine-grained token with read/write access to Contents and
Pull requests for this repository. Without this secret the automation safely
skips and leaves PRs available for manual merge.

Local `dev` is a separate copy from GitHub's `origin/dev`. Before starting
services, `scripts/start-all-servers.ps1` fast-forwards a clean local `dev`
from `origin/dev`. It preserves dirty work and starts other branches without
blocking; it prints the branch, commit, and dirty-worktree state. The API
`/health` response and admin `/build-info` route refresh source details from
Git during local DEV hot reloads. The admin header compares both services and
flags a mismatch.

After the exact DEV commit has passed its runtime check, open a pull request
for `main` only when its tracked source tree matches `dev`. This permits a
promotion branch that preserves production-only generated artifacts while
ensuring application code and migrations are the tested DEV versions. Tag
that exact merge commit. Release and deployment checks require a passing
DEV-parity CI run for the associated production pull request.

Production deployment stamps the tagged commit into the API and admin builds.
Deployment succeeds only when the production API health response reports that
exact commit; a mismatch triggers the existing rollback path.

The remote startup and deployment scripts verify that the production checkout
is on `main` and deploy only `origin/main`. If a production checkout is still
on `master`, startup stops with an actionable error instead of deploying the
wrong branch. Development startup uses the hot-reloading Next.js dev server;
production build output is generated during deployment and is not a source of
DEV code.
