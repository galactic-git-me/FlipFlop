#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$#" -ne 2 ]]; then
  echo "Usage: $0 <dev-ref> <promotion-candidate-ref>" >&2
  exit 2
fi

dev_ref="$1"
candidate_ref="$2"
git cat-file -e "$dev_ref^{commit}"
git cat-file -e "$candidate_ref^{commit}"

# Production and DEV can have different generated bundles and local tooling
# snapshots. Application code, migrations, configuration, and tracked data
# must otherwise match before a production promotion is allowed.
excluded_paths=(
  ':(exclude,glob)**/.next*/**'
  ':(exclude,glob)**/.playwright-cli/**'
  ':(exclude,glob).playwright-cli/**'
  ':(exclude,glob).venv_bsc/**'
  ':(exclude,glob)**/__pycache__/**'
  ':(exclude,glob)**/skills/ui-ux-pro-max/**'
  ':(exclude,glob).github/prompts/ui-ux-pro-max/**'
  ':(exclude,glob).kiro/steering/ui-ux-pro-max/**'
  ':(exclude,glob).serena/project.local.yml'
)

if ! git diff --quiet "$dev_ref" "$candidate_ref" -- . "${excluded_paths[@]}"; then
  echo "Promotion candidate differs from DEV source outside generated/local artifacts." >&2
  git diff --stat "$dev_ref" "$candidate_ref" -- . "${excluded_paths[@]}" >&2
  exit 1
fi

echo "Promotion source matches DEV: $dev_ref -> $candidate_ref"
