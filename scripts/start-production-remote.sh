#!/usr/bin/env bash
set -Eeuo pipefail
api=/home/mac/CODING/FlipFlop-production
shop=/home/mac/CODING/flipflop-shop
deploy_if_needed() {
  local repo="$1"
  local deploy_script="$2"
  branch=$(git -C "$repo" branch --show-current)
  [[ -n "$branch" ]] || { echo "Detached checkout: $repo"; exit 1; }
  [[ -z "$(git -C "$repo" status --porcelain)" ]] || { echo "Uncommitted production files: $repo"; exit 1; }
  git -C "$repo" fetch --quiet origin "$branch"
  local current_sha target_sha
  current_sha="$(git -C "$repo" rev-parse HEAD)"
  target_sha="$(git -C "$repo" rev-parse "origin/$branch")"
  if [[ "$current_sha" != "$target_sha" ]]; then
    echo "Deploying $repo from ${current_sha:0:9} to ${target_sha:0:9} before startup."
    "$deploy_script" "$target_sha"
  fi
  [[ "$(git -C "$repo" rev-parse HEAD)" == "$target_sha" ]] || {
    echo "Deployment did not reach origin/$branch: $repo"; exit 1;
  }
  echo "GitHub check passed: $repo ($branch)"
}
# Reconcile the deployed checkouts, not the similarly named development folders.
deploy_if_needed "$api" "$api/deploy/deploy-andromeda.sh"
deploy_if_needed "$shop" "$shop/scripts/deploy-production.sh"
[[ "$(systemctl --user show flipflop-shop.service -p WorkingDirectory --value)" == "$shop" ]] || { echo 'Storefront service directory changed; inspect configuration'; exit 1; }
# Existing released images only: never build local/unreleased source here.
docker compose -f "$api/deploy/andromeda-api.compose.yml" up -d --no-build --wait --wait-timeout 120
systemctl --user start flipflop-shop.service
curl --fail --silent --show-error --retry 10 --retry-connrefused --retry-delay 2 http://127.0.0.1:4311/health >/dev/null
curl --fail --silent --show-error --retry 10 --retry-connrefused --retry-delay 2 http://127.0.0.1:3020/ >/dev/null
echo 'Production API, database, Redis, worker and storefront are running.'
