#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="${FLIPFLOP_REPO_DIR:-/home/mac/CODING/FlipFlop-production}"
COMPOSE_FILE="$REPO_DIR/deploy/andromeda-api.compose.yml"
ADMIN_AUTH_ENV="$REPO_DIR/runtime/admin-auth.env"
# Production is deliberately pinned to the promotion branch. A deployment
# may never follow the development branch implicitly.
BRANCH="${FLIPFLOP_DEPLOY_BRANCH:-main}"
TARGET_SHA="${1:-}"
LOCK_FILE="${FLIPFLOP_DEPLOY_LOCK:-/tmp/flipflop-production-deploy.lock}"

log() {
  printf '[flipflop-deploy] %s\n' "$*"
}

exec 9>"$LOCK_FILE"
flock -n 9 || { log "Another production deployment is running."; exit 1; }

cd "$REPO_DIR"

if [[ ! -s "$ADMIN_AUTH_ENV" ]] || ! grep -Eq '^ADMIN_JWT_SECRET=.{32,}$' "$ADMIN_AUTH_ENV"; then
  log "Missing runtime/admin-auth.env with a stable ADMIN_JWT_SECRET of at least 32 characters."
  exit 1
fi

log "Fetching origin/$BRANCH"
# A previous interrupted fetch can leave the remote-tracking ref undeletable.
# Remove only this branch's local tracking ref, then recreate it from origin.
git update-ref -d "refs/remotes/origin/$BRANCH" 2>/dev/null || true
git fetch --prune origin "$BRANCH:refs/remotes/origin/$BRANCH"

if [[ -z "$TARGET_SHA" ]]; then
  TARGET_SHA="$(git rev-parse "origin/$BRANCH")"
fi

git cat-file -e "$TARGET_SHA^{commit}"
if ! git merge-base --is-ancestor "$TARGET_SHA" "origin/$BRANCH"; then
  log "Refusing SHA $TARGET_SHA because it is not on origin/$BRANCH."
  exit 1
fi

CURRENT_SHA="$(git rev-parse HEAD)"
MERGE_BASE="$(git merge-base "$CURRENT_SHA" "$TARGET_SHA" || true)"
if [[ -z "$MERGE_BASE" ]]; then
  log "Refusing release $TARGET_SHA because it has no history in common with production HEAD $CURRENT_SHA."
  exit 1
fi

# A bootstrap deployment may already have installed these reviewed release
# scripts directly. Accept only bytes that exactly match the tagged commit.
for deploy_path in deploy/github-deploy-command.sh deploy/deploy-andromeda.sh; do
  target_blob="$(git rev-parse "$TARGET_SHA:$deploy_path")"
  worktree_blob="$(git hash-object "$deploy_path")"
  index_blob="$(git rev-parse ":$deploy_path")"
  head_blob="$(git rev-parse "HEAD:$deploy_path")"
  git update-index --no-skip-worktree -- "$deploy_path" 2>/dev/null || true
  if [[ "$worktree_blob" != "$index_blob" || "$index_blob" != "$head_blob" ]]; then
    if [[ "$worktree_blob" != "$target_blob" ]]; then
      log "Refusing an uncommitted deployment script that differs from release $TARGET_SHA ($deploy_path)."
      exit 1
    fi
    # Bootstrap copies are safe only when their bytes match the exact release.
    git add -- "$deploy_path"
  fi
done

# Git merge refuses to overwrite staged bootstrap copies even when their
# content is identical to the incoming commit. Record only those exact tagged
# scripts as a local preparation commit, then merge the tagged release.
if ! git diff --cached --quiet -- deploy/github-deploy-command.sh deploy/deploy-andromeda.sh; then
  git -c core.hooksPath=/dev/null \
      -c user.name="FlipFlop Production Deploy" \
      -c user.email="deploy@theflipflop.shop" \
      commit -m "chore: prepare verified deployment scripts ${TARGET_SHA:0:12}"
fi

CURRENT_SHA="$(git rev-parse HEAD)"
MERGE_BASE="$(git merge-base "$CURRENT_SHA" "$TARGET_SHA" || true)"
if [[ -z "$MERGE_BASE" ]]; then
  log "Refusing release $TARGET_SHA because it has no history in common with production HEAD $CURRENT_SHA."
  exit 1
fi

if ! git merge-base --is-ancestor "$CURRENT_SHA" "$TARGET_SHA"; then
  local_history_changes="$(git diff --name-only "$MERGE_BASE" "$CURRENT_SHA" | awk '
    $0 !~ /^runtime\// && $0 != "deploy/deploy-andromeda.sh" && $0 != "deploy/github-deploy-command.sh" { print }
  ')"
  if [[ -n "$local_history_changes" ]]; then
    log "Refusing divergent production history that includes changes outside runtime data and deployment scripts."
    exit 1
  fi
fi

# Production writes mutable data under runtime/ while source updates arrive on
# the promotion branch. Keep every tracked runtime file in the worktree across
# release merges, including seller-pack media and stable authentication data.
while IFS= read -r -d '' runtime_path; do
  git update-index --skip-worktree -- "$runtime_path"
done < <(git ls-files -z -- runtime)

unexpected_changes="$(git status --porcelain --untracked-files=all | awk '
  {
    path = substr($0, 4)
    if (path !~ /^runtime\//) print
  }
')"
if [[ -n "$unexpected_changes" ]]; then
  log "Refusing to deploy over uncommitted changes outside production runtime state in $REPO_DIR."
  exit 1
fi

if git merge-base --is-ancestor "$CURRENT_SHA" "$TARGET_SHA"; then
  log "Fast-forwarding to $TARGET_SHA"
  git merge --ff-only "$TARGET_SHA"
else
  log "Merging release $TARGET_SHA while preserving production runtime history"
  git merge --no-ff --no-commit -X ours "$TARGET_SHA"
  git checkout "$TARGET_SHA" -- deploy/github-deploy-command.sh deploy/deploy-andromeda.sh
  git add -- deploy/github-deploy-command.sh deploy/deploy-andromeda.sh
  git -c core.hooksPath=/dev/null \
      -c user.name="FlipFlop Production Deploy" \
      -c user.email="deploy@theflipflop.shop" \
      commit -m "chore: merge tagged production release ${TARGET_SHA:0:12}"
fi

git update-index --no-skip-worktree -- deploy/github-deploy-command.sh deploy/deploy-andromeda.sh

OLD_IMAGE="$(docker inspect flipflop-production-api --format '{{.Image}}' 2>/dev/null || true)"
if [[ -n "$OLD_IMAGE" ]]; then
  docker image tag "$OLD_IMAGE" flipflop-api:rollback
fi

log "Building production API, Gem Radar, and admin"
# The customer site is deployed from its own repository by flipflop-shop.service.
# Starting the legacy compose storefront would contend for its live port 3020.
docker compose -f "$COMPOSE_FILE" build api gemradar-worker admin

log "Applying database migrations"
docker compose -f "$COMPOSE_FILE" run --rm api alembic -x reconcile_existing=true upgrade head

log "Starting production stack"
docker compose -f "$COMPOSE_FILE" up -d api gemradar-worker admin

healthy=0
for _ in $(seq 1 30); do
  if curl --fail --silent --show-error http://127.0.0.1:4311/health >/dev/null \
    && curl --fail --silent --show-error http://127.0.0.1:3020/ >/dev/null \
    && curl --fail --silent --show-error http://127.0.0.1:3021/health >/dev/null; then
    healthy=1
    break
  fi
  sleep 2
done

if [[ "$healthy" -ne 1 ]]; then
  log "Health check failed. Restoring the previous API image."
  if docker image inspect flipflop-api:rollback >/dev/null 2>&1; then
    docker image tag flipflop-api:rollback deploy-api:latest
    docker compose -f "$COMPOSE_FILE" up -d --no-deps --force-recreate api
  fi
  exit 1
fi

log "Verifying browser worker authentication and live Merchant API writes"
docker compose -f "$COMPOSE_FILE" exec -T api python -c 'import asyncio, os; from app.services.google_merchant_api import GoogleMerchantAPI; assert len(os.getenv("CROSS_LISTING_WORKER_KEY", "")) >= 48, "Chrome worker key is not configured"; status = asyncio.run(GoogleMerchantAPI().verify_connection()); assert status.get("connected") and status.get("writes_enabled"), "Merchant API is not connected with writes enabled"; print("Browser worker and Merchant API write configuration verified")'

callback_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
  https://www.theflipflop.shop/api/ebay/oauth/callback)"
if [[ "$callback_status" != "307" && "$callback_status" != "302" ]]; then
  log "Public eBay callback check failed with HTTP $callback_status."
  exit 1
fi

for public_url in https://www.theflipflop.shop/ https://admin.theflipflop.shop/; do
  public_status="$(curl --silent --output /dev/null --write-out '%{http_code}' "$public_url")"
  if [[ "$public_status" -lt 200 || "$public_status" -ge 500 ]]; then
    log "Public endpoint check failed for $public_url with HTTP $public_status."
    exit 1
  fi
done

google_merchant_status="$(docker compose -f "$COMPOSE_FILE" exec -T api python -c 'import asyncio; from app.services.google_merchant_api import GoogleMerchantAPI; print(asyncio.run(GoogleMerchantAPI().verify_connection()))')"
log "Google Merchant connection: $google_merchant_status"
python3 -c 'import json,sys; result=json.loads(sys.argv[1]); sys.exit(0 if result.get("connected") and result.get("writes_enabled") else 1)' "$google_merchant_status" || {
  log "Google Merchant connection or live-write verification failed."
  exit 1
}

log "Deployment completed at $(git rev-parse --short HEAD)."
