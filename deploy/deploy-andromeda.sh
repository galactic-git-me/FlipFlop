#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="${FLIPFLOP_REPO_DIR:-/home/mac/CODING/FlipFlop}"
COMPOSE_FILE="$REPO_DIR/deploy/andromeda-api.compose.yml"
BRANCH="${FLIPFLOP_DEPLOY_BRANCH:-master}"
TARGET_SHA="${1:-}"
LOCK_FILE="${FLIPFLOP_DEPLOY_LOCK:-/tmp/flipflop-production-deploy.lock}"

log() {
  printf '[flipflop-deploy] %s\n' "$*"
}

exec 9>"$LOCK_FILE"
flock -n 9 || { log "Another production deployment is running."; exit 1; }

cd "$REPO_DIR"

if [[ -n "$(git status --porcelain)" ]]; then
  log "Refusing to deploy over uncommitted changes in $REPO_DIR."
  exit 1
fi

log "Fetching origin/$BRANCH"
git fetch --prune origin "$BRANCH"

if [[ -z "$TARGET_SHA" ]]; then
  TARGET_SHA="$(git rev-parse "origin/$BRANCH")"
fi

git cat-file -e "$TARGET_SHA^{commit}"
if ! git merge-base --is-ancestor "$TARGET_SHA" "origin/$BRANCH"; then
  log "Refusing SHA $TARGET_SHA because it is not on origin/$BRANCH."
  exit 1
fi

CURRENT_SHA="$(git rev-parse HEAD)"
if ! git merge-base --is-ancestor "$CURRENT_SHA" "$TARGET_SHA"; then
  log "Refusing a non-fast-forward deployment ($CURRENT_SHA -> $TARGET_SHA)."
  exit 1
fi

log "Fast-forwarding to $TARGET_SHA"
git merge --ff-only "$TARGET_SHA"

OLD_IMAGE="$(docker inspect flipflop-production-api --format '{{.Image}}' 2>/dev/null || true)"
if [[ -n "$OLD_IMAGE" ]]; then
  docker image tag "$OLD_IMAGE" flipflop-api:rollback
fi

log "Building production API"
docker compose -f "$COMPOSE_FILE" build api

log "Applying database migrations"
docker compose -f "$COMPOSE_FILE" run --rm api alembic upgrade head

log "Starting production API"
docker compose -f "$COMPOSE_FILE" up -d --no-deps api

healthy=0
for _ in $(seq 1 30); do
  if curl --fail --silent --show-error http://127.0.0.1:4311/health >/dev/null; then
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

callback_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
  https://www.theflipflop.shop/api/ebay/oauth/callback)"
if [[ "$callback_status" != "307" && "$callback_status" != "302" ]]; then
  log "Public eBay callback check failed with HTTP $callback_status."
  exit 1
fi

log "Deployment completed at $(git rev-parse --short HEAD)."
