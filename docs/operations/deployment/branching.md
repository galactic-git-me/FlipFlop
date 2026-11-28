# Deployment branches

FlipFlop uses two branches with different responsibilities:

- `dev` is the development branch. Autosync is allowed to commit and push only
  to this branch. Feature pull requests target `dev`, where CI and the DEV
  runtime journey are completed before production promotion. Successful
  post-merge validation deploys that exact commit to the DEV host and verifies
  the API/admin source SHA plus storefront health.
- `main` is the production branch. It is never updated by autosync and the
  production deploy workflow runs only for verified release tags or an
  explicitly confirmed manual dispatch. Pull requests into `main`
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
they are resolved and the PR is updated. After the exact merged commit passes
DEV runtime deployment, automation opens or updates a `dev`-to-`main` promotion
PR and queues auto-merge. Its required `checks` job waits for a successful
`DEV deployment` check on the exact PR head SHA, then runs the normal
DEV-parity/repository checks. Other PRs targeting `main` are not automatically
queued. Keep unrelated or unfinished work in its own branch/PR rather than
combining every dirty worktree into one release.

DEV auto-merge uses the repository secret `FLIPFLOP_DEV_MERGE_TOKEN` so the
merge still triggers the normal post-merge DEV validation and worktree cleanup
workflows. Set it to a fine-grained token with read/write access to Contents and
Pull requests for this repository. Without this secret the automation safely
skips and leaves PRs available for manual merge.

Local DEV runs from the reusable detached `FlipFlop-dev-runtime` worktree beside
the primary checkout. The reserved DEV ports may be started only from the
runtime worktree whose HEAD exactly matches freshly fetched `origin/dev`, with
no local code changes. The API may append runtime cache entries to
`flipflop-api/data/component-manual-discovery.json`; deployment preserves this
specific file only while the target commit retains the same tracked blob. All
other dirty paths, or a source change to that file, block deployment.
`scripts/deploy-development.ps1` enforces that worktree-state rule before it
updates source or starts services. `scripts/start-all-servers.ps1` verifies the
branch, fetched source identity, and expected commit before touching ports, the
Ollama gateway, or service processes. The primary developer checkout is not
advanced or required to be clean by automated DEV deployment.
When the storefront is included, it must also be a clean checkout exactly
matching its remote default branch. Feature work must use an isolated preview
environment; it must never claim the shared DEV ports. The API
`/health` response and admin `/build-info` route refresh source details from
Git during local DEV hot reloads. The admin header compares both services and
flags a mismatch.

The post-merge `Validate development` workflow runs API checks and the admin
build on GitHub-hosted CI. After a successful push to `dev`, it uses the
repository-scoped Windows runner labelled `flipflop-coding-cleanup` to run
`scripts/deploy-development.ps1`. The script preserves the primary checkout,
updates only its fixed detached runtime worktree to the exact validated
`origin/dev` commit, requires the sibling storefront checkout to be clean and
current, starts the DEV services, and verifies the API and admin report that
SHA while the storefront responds. Manual workflow dispatch validates only and
does not deploy. A missing/offline runner, runtime edits, or source mismatch
leaves the deployment job pending or failed; it never overwrites local changes.

After the exact DEV commit has passed its runtime check, open a pull request
for `main` only when its tracked source tree matches `dev`. This PR and its
auto-merge are created only after the exact SHA passes the DEV deployment job.
When it merges, automation creates the next `vMAJOR.MINOR.PATCH` tag on the
merge commit; the tag starts release checks and LIVE deployment. The release
check and production deployment independently compare the tagged source tree
with freshly fetched `origin/dev`; a stale or divergent release is blocked.
Release and deployment checks also require a passing DEV-parity CI run for the
associated production pull request. The production GitHub environment is the
future manual-approval point: add required reviewers there when the app
launches; until then the verified tag deploys automatically.

Production deployment stamps the tagged commit into the API and admin builds.
Deployment succeeds only when the production API health response reports that
exact commit; a mismatch triggers the existing rollback path.

The remote startup and deployment scripts verify that the production checkout
is on `main` and deploy only `origin/main`. If a production checkout is still
on `master`, startup stops with an actionable error instead of deploying the
wrong branch. Development startup uses the hot-reloading Next.js dev server;
production build output is generated during deployment and is not a source of
DEV code.
