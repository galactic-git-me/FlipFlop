#!/usr/bin/env bash
set -euo pipefail

CODING_DIR="${CODING_DIR:-/coding}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-300}"
COMMIT_MSG_PREFIX="${COMMIT_MSG_PREFIX:-chore: automated codebase synchronization}"
PRIMARY_REPO="${PRIMARY_REPO:-FlipFlop}"
TZ="${TZ:-UTC}"
export TZ

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*"; }

if [[ ! -d "$CODING_DIR" ]]; then
  log "ERROR: CODING_DIR not found: $CODING_DIR"
  exit 1
fi

git config --global credential.helper "store --file /tmp/git-creds/.git-credentials" || true
git config --global --add safe.directory '*' || true

if [[ -n "${GIT_USER_NAME:-}" ]]; then git config --global user.name "$GIT_USER_NAME"; fi
if [[ -n "${GIT_USER_EMAIL:-}" ]]; then git config --global user.email "$GIT_USER_EMAIL"; fi

log "Started multi-repo autosync for root=$CODING_DIR interval=${INTERVAL_SECONDS}s"

sync_repo() {
  local repo="$1"
  local name
  name="$(basename "$repo")"

  if [[ ! -d "$repo/.git" ]]; then
    return 0
  fi

  cd "$repo"

  local branch
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo master)"
  if [[ -z "$branch" || "$branch" == "HEAD" ]]; then
    branch="master"
  fi

  local fetch_rc=0 commit_rc=0 push_rc=0 rebase_rc=0 ahead=0 behind=0
  git fetch origin "$branch" --quiet || fetch_rc=$?

  if git rev-parse --verify "origin/$branch" >/dev/null 2>&1; then
    behind="$(git rev-list --count "HEAD..origin/$branch" 2>/dev/null || echo 0)"
  fi

  # If remote has new commits, stash any uncommitted work, rebase on top, then restore.
  if [[ "$behind" -gt 0 ]]; then
    log "[$name] Remote is $behind commit(s) ahead — rebasing local work on top..."
    local stashed=0
    if ! git diff --quiet || ! git diff --cached --quiet 2>/dev/null; then
      git stash push -u -m "autosync-stash" >/dev/null 2>&1 && stashed=1
    fi
    git rebase "origin/$branch" || rebase_rc=$?
    if [[ $rebase_rc -ne 0 ]]; then
      git rebase --abort >/dev/null 2>&1 || true
      [[ "$stashed" -eq 1 ]] && git stash pop >/dev/null 2>&1 || true
      log "[$name] Rebase failed — skipping this cycle. Manual intervention required."
      return 0
    fi
    [[ "$stashed" -eq 1 ]] && git stash pop >/dev/null 2>&1 || true
  fi

  git add -A || true
  if ! git diff --cached --quiet 2>/dev/null; then
    local ts
    ts="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    git commit -m "$COMMIT_MSG_PREFIX ($ts)" || commit_rc=$?
  fi

  if git rev-parse --verify "origin/$branch" >/dev/null 2>&1; then
    ahead="$(git rev-list --count "origin/$branch..HEAD" 2>/dev/null || echo 0)"
    behind="$(git rev-list --count "HEAD..origin/$branch" 2>/dev/null || echo 0)"
  else
    ahead=1
    behind=0
  fi

  if [[ "$ahead" -gt 0 && "$behind" -eq 0 ]]; then
    git push origin "$branch" || push_rc=$?
  elif [[ "$behind" -gt 0 ]]; then
    log "[$name] Still behind after rebase — skipping push this cycle."
  fi

  if [[ $fetch_rc -ne 0 || $commit_rc -ne 0 || $push_rc -ne 0 ]]; then
    log "[$name] issues: fetch=$fetch_rc commit=$commit_rc push=$push_rc ahead=$ahead behind=$behind"
  fi
}

while true; do
  if [[ -d "$CODING_DIR/$PRIMARY_REPO" ]]; then
    sync_repo "$CODING_DIR/$PRIMARY_REPO"
  fi
  while IFS= read -r -d '' d; do
    if [[ "$d" == "$CODING_DIR/$PRIMARY_REPO" ]]; then
      continue
    fi
    sync_repo "$d"
  done < <(find "$CODING_DIR" -mindepth 1 -maxdepth 1 -type d -print0)

  sleep "$INTERVAL_SECONDS"
done
