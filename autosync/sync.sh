#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/repo}"
BRANCH="${BRANCH:-master}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-300}"
COMMIT_MSG_PREFIX="${COMMIT_MSG_PREFIX:-chore: automated codebase synchronization}"
TZ="${TZ:-UTC}"
export TZ

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*"; }

if [[ ! -d "$REPO_DIR/.git" ]]; then
  log "ERROR: $REPO_DIR is not a git repo"
  exit 1
fi

cd "$REPO_DIR"

git config --global --add safe.directory "$REPO_DIR" || true
git config --global credential.helper store || true
if [[ -n "${GIT_USER_NAME:-}" ]]; then git config user.name "$GIT_USER_NAME"; fi
if [[ -n "${GIT_USER_EMAIL:-}" ]]; then git config user.email "$GIT_USER_EMAIL"; fi

log "Started autosync for repo=$REPO_DIR branch=$BRANCH interval=${INTERVAL_SECONDS}s"

while true; do
  set +e
  # Keep remote refs fresh.
  git fetch origin "$BRANCH" --quiet
  FETCH_RC=$?

  BEHIND_CNT=0
  if git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
    BEHIND_CNT=$(git rev-list --count "HEAD..origin/$BRANCH" 2>/dev/null || echo 0)
  fi

  # If remote has new commits, stash any uncommitted work, rebase on top, then restore.
  REBASE_RC=0
  if [[ "$BEHIND_CNT" -gt 0 ]]; then
    log "Remote is $BEHIND_CNT commit(s) ahead — rebasing local work on top..."
    STASHED=0
    if ! git diff --quiet || ! git diff --cached --quiet 2>/dev/null; then
      git stash push -u -m "autosync-stash" >/dev/null 2>&1 && STASHED=1
    fi
    git rebase "origin/$BRANCH" || REBASE_RC=$?
    if [[ $REBASE_RC -ne 0 ]]; then
      git rebase --abort >/dev/null 2>&1 || true
      [[ "$STASHED" -eq 1 ]] && git stash pop >/dev/null 2>&1 || true
      log "Rebase failed — skipping this cycle. Manual intervention required."
      set -e
      sleep "$INTERVAL_SECONDS"
      continue
    fi
    [[ "$STASHED" -eq 1 ]] && git stash pop >/dev/null 2>&1 || true
  fi

  git add -A
  if ! git diff --cached --quiet; then
    TS="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    git commit -m "$COMMIT_MSG_PREFIX ($TS)"
    COMMIT_RC=$?
    # Re-touch any TS/TSX files in the commit so Next.js HMR fires correctly.
    # git commit doesn't update file mtimes, which silently breaks HMR.
    git diff-tree --no-commit-id -r --name-only HEAD 2>/dev/null \
      | grep -E '\.(ts|tsx|css|js|jsx)$' \
      | xargs -r touch --
  else
    COMMIT_RC=0
  fi

  # Push only when branch can fast-forward remote.
  if git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
    AHEAD_CNT=$(git rev-list --count "origin/$BRANCH..HEAD" 2>/dev/null || echo 0)
    BEHIND_CNT=$(git rev-list --count "HEAD..origin/$BRANCH" 2>/dev/null || echo 0)
  else
    AHEAD_CNT=1
    BEHIND_CNT=0
  fi

  if [[ "$AHEAD_CNT" -gt 0 && "$BEHIND_CNT" -eq 0 ]]; then
    git push origin "$BRANCH"
    PUSH_RC=$?
  else
    PUSH_RC=0
    if [[ "$BEHIND_CNT" -gt 0 ]]; then
      log "Still behind after rebase — skipping push this cycle."
    fi
  fi

  if [[ $FETCH_RC -ne 0 || $COMMIT_RC -ne 0 || $PUSH_RC -ne 0 ]]; then
    log "Cycle completed with issues: fetch=$FETCH_RC commit=$COMMIT_RC push=$PUSH_RC"
  else
    log "Cycle completed: fetch=$FETCH_RC commit=$COMMIT_RC push=$PUSH_RC ahead=$AHEAD_CNT behind=$BEHIND_CNT"
  fi
  set -e

  sleep "$INTERVAL_SECONDS"
done
