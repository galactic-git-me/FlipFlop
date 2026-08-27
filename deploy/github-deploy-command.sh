#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_SCRIPT="/home/mac/CODING/FlipFlop-production/deploy/deploy-andromeda.sh"
original="${SSH_ORIGINAL_COMMAND:-}"

# The workflow sends exactly this command with a Git commit SHA. Reject every
# other command so the Actions key cannot be used as a general SSH shell.
if [[ "$original" =~ ^/home/mac/CODING/FlipFlop-production/deploy/deploy-andromeda\.sh[[:space:]]+\'?([0-9a-fA-F]{7,40})\'?$ ]]; then
  exec "$DEPLOY_SCRIPT" "${BASH_REMATCH[1]}"
fi

printf 'Rejected deployment command.\n' >&2
exit 126
