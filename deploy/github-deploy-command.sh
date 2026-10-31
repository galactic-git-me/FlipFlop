#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_SCRIPT="/home/mac/CODING/FlipFlop-production/deploy/deploy-andromeda.sh"
original="${SSH_ORIGINAL_COMMAND:-}"

# The workflow sends exactly this command with a Git commit SHA. Reject every
# other command so the Actions key cannot be used as a general SSH shell.
if [[ "$original" =~ ^/home/mac/CODING/FlipFlop-production/deploy/deploy-andromeda\.sh[[:space:]]+\'?([0-9a-fA-F]{7,40})\'?$ ]]; then
  exec bash "$DEPLOY_SCRIPT" "${BASH_REMATCH[1]}"
fi

provision_google_key() {
  local destination="/home/mac/.secrets/flipflop/google-merchant-service-account.json"
  local temporary="${destination}.tmp.$$"
  install -d -m 700 /home/mac/.secrets/flipflop
  umask 077
  trap 'rm -f "$temporary"' EXIT
  cat > "$temporary"
  python3 - "$temporary" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as key_file:
    key = json.load(key_file)
if (key.get("type") != "service_account"
        or key.get("project_id") != "flipflop-509210"
        or key.get("client_email") != "flipflop-merchant-api@flipflop-509210.iam.gserviceaccount.com"
        or not key.get("private_key")):
    raise SystemExit("The supplied Google key is not the configured FlipFlop Merchant service account.")
PY
  chmod 600 "$temporary"
  mv -f "$temporary" "$destination"
  trap - EXIT
  printf 'Google Merchant service-account key installed.\n'
}

provision_worker_key() {
  local destination="/home/mac/CODING/FlipFlop-production/runtime/browser-worker.env"
  local temporary="${destination}.tmp.$$"
  install -d -m 700 /home/mac/CODING/FlipFlop-production/runtime
  umask 077
  trap 'rm -f "$temporary"' EXIT
  cat > "$temporary"
  if [[ "$(wc -l < "$temporary")" -ne 1 ]] || ! grep -Eq '^CROSS_LISTING_WORKER_KEY=[A-Za-z0-9_-]{48,}$' "$temporary"; then
    printf 'Invalid browser worker key payload.\n' >&2
    return 1
  fi
  chmod 600 "$temporary"
  mv -f "$temporary" "$destination"
  trap - EXIT
  printf 'Browser worker key installed.\n'
}

if [[ "$original" == "provision-google-merchant-key" ]]; then
  provision_google_key
  exit
fi

if [[ "$original" == "provision-browser-worker-key" ]]; then
  provision_worker_key
  exit
fi

printf 'Rejected deployment command.\n' >&2
exit 126
