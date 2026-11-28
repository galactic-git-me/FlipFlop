# FlipFlop release process

FlipFlop has two runtime environments, not three:

- DEV runs on `prometheus-ts` with hot reload and isolated local data.
- PROD runs on `andromeda-ts` as Docker services.
- Both Gem Radar browser extensions remain on `prometheus-ts` because scanning requires an open browser.

## Workflow

1. Create a feature branch from the latest `origin/dev` and open a pull request
   into `dev`. GitHub requires pull requests and the `checks` status on both
   `dev` and `main`; force pushes and branch deletion are disabled. Keep the
   branch current with its base before merging.
2. Wait for pull-request checks to pass. GitHub auto-merges the change into
   `dev` after its required checks succeed.
3. The `Validate development` workflow runs its API checks and admin build. On
   success for a push to `dev`, the repository-scoped Windows runner deploys
   that exact commit to the DEV host using a reusable detached runtime
   worktree; the primary developer checkout is left untouched. It requires a
   clean/current storefront checkout, starts the DEV API/admin/storefront, then
   verifies the API and admin source SHA and storefront health. Manual workflow
   dispatch validates without deploying.
   Feature work still requires an isolated preview environment.
4. After DEV runtime verification, automation opens or updates a promotion PR
   from `dev` to `main` and queues auto-merge. The main PR's required `checks`
   job waits for the `DEV deployment` check on that exact head SHA, then verifies
   source parity and runs repository checks. This prevents a newer, not-yet-
   deployed DEV commit from being promoted by an older open PR.
5. When the promotion PR merges, automation tags that exact merge commit with
   the next `vMAJOR.MINOR.PATCH` version. The tag starts release checks and the
   LIVE deployment workflow. Release and deployment checks verify that the tag
   is on `main`, matches current `origin/dev`, and is associated with the
   merged, passing promotion PR.
6. LIVE deployment verifies the tagged source, reruns release checks, builds
   the admin bundle, deploys to Andromeda and verifies the running API source
   SHA and dependent service health. It labels the merged PR `deployed-live`.
   The GitHub `production` environment is the manual-approval point to enable
   when the app launches. Until required reviewers are configured, a verified
   release tag deploys automatically. Manual **Actions → Deploy production**
   remains available for recovery and still requires typing
   `DEPLOY-PRODUCTION`.

Production is never deployed merely because code was pushed to `main`; a tag
created from a DEV-verified promotion PR is required. The DEV runtime check
happens before promotion; CI build success alone is not evidence that the live
DEV journey was exercised. GitHub branch protection on
`main` requires pull requests and the `checks` status check, including for
administrators, so a direct production push cannot bypass this path.

## Secrets

GitHub Secrets contain deployment-only values such as the restricted Andromeda
SSH key. Application runtime secrets remain in environment-specific secret
files on the target machines and are never committed. Local `.env` files are
ignored; `.env.example` files document names without values.

Scanning uses production eBay API credentials in both environments. Listing
credentials remain sandbox-only in DEV and production-only in PROD. Stripe
test and live credentials are separate modes. Delivery-insurance and Post2Go
credentials remain marked as DEV credentials until production credentials are
created.

## Required GitHub configuration

The repository administrator must configure these Actions secrets:

- `ANDROMEDA_HOST`
- `ANDROMEDA_USER`
- `ANDROMEDA_PORT` (optional; defaults to `22`)
- `ANDROMEDA_SSH_KEY`
- `ANDROMEDA_HOST_KEY`
- `FLIPFLOP_EXTENSION_DISPATCH_TOKEN`

The `production` environment should be enabled even on plans where required
reviewers are unavailable. The explicit workflow confirmation remains the
final deployment gate.

The Andromeda checkout must contain `FlipFlop.shop` beside the main checkout
or at `$REPO_DIR/FlipFlop.shop`; the production compose build uses that sibling
repository as the storefront build context. Install the Caddy site blocks from
`deploy/andromeda.Caddyfile.example` before the first full-stack deployment.
