#!/usr/bin/env bash
set -Eeuo pipefail
api=/home/mac/CODING/FlipFlop-production
shop=/home/mac/CODING/flipflop-shop
# Check the deployed checkouts, not the similarly named development folders.
for repo in "$api" "$shop"; do
  branch=$(git -C "$repo" branch --show-current)
  [[ -n "$branch" ]] || { echo "Detached checkout: $repo"; exit 1; }
  [[ -z "$(git -C "$repo" status --porcelain)" ]] || { echo "Uncommitted production files: $repo"; exit 1; }
  git -C "$repo" fetch --quiet origin "$branch"
  [[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse "origin/$branch")" ]] || {
    echo "Deployment required: $repo differs from origin/$branch. Startup does not deploy code."; exit 1;
  }
  echo "GitHub check passed: $repo ($branch)"
done
[[ "$(systemctl --user show flipflop-shop.service -p WorkingDirectory --value)" == "$shop" ]] || { echo 'Storefront service directory changed; inspect configuration'; exit 1; }
# Existing released images only: never build local/unreleased source here.
docker compose -f "$api/deploy/andromeda-api.compose.yml" up -d --no-build --wait --wait-timeout 120
systemctl --user start flipflop-shop.service
curl --fail --silent --show-error --retry 10 --retry-connrefused --retry-delay 2 http://127.0.0.1:4311/health >/dev/null
curl --fail --silent --show-error --retry 10 --retry-connrefused --retry-delay 2 http://127.0.0.1:3020/ >/dev/null
echo 'Production API, database, Redis, worker and storefront are running.'
