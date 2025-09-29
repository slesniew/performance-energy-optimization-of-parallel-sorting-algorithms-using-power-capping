#!/usr/bin/env bash
set -euo pipefail

START=${START:-1}
END=${END:-16}
MAX_RETRIES=${MAX_RETRIES:-2}
CONNECT_TIMEOUT=${CONNECT_TIMEOUT:-10}
PARALLEL=${PARALLEL:-1}
JOBS=${JOBS:-8}

PROXY_USER=${PROXY_USER:-s184711}
PROXY_HOST=${PROXY_HOST:-kask.eti.pg.gda.pl}
REPO_URL=${REPO_URL:-https://github.com/slesniew/performance-energy-optimization-of-parallel-sorting-algorithms-using-power-capping.git}
REPO_DIR_PREFIX=${REPO_DIR_PREFIX:-des}

CLEAN_MODE=0
FORCE_MODE=0
for arg in "$@"; do
  case "$arg" in
    clean) CLEAN_MODE=1 ;;
    force) FORCE_MODE=1 ;;
  esac
done

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

JUMP_OPT="-J ${PROXY_USER}@${PROXY_HOST}"
if hostname 2>/dev/null | grep -qi '^kask'; then
  JUMP_OPT=""
fi

SSH_OPTS="-o ConnectTimeout=${CONNECT_TIMEOUT} -o ServerAliveInterval=5 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=accept-new -o BatchMode=no ${JUMP_OPT}"

pad() {
  printf "%02d" "$((10#$1))"
}

remote_sync() {
  cat <<'RS'
set -euo pipefail
REPO_URL="$1"
DIR_NAME="$2"
CLEAN_MODE="$3"
FORCE_MODE="${4:-0}"

update_submodules() {
  if [ -f "$DIR/.gitmodules" ]; then
    echo "[INFO] Submodules detected. Syncing..."
    git -C "$DIR" submodule sync --recursive || true
    # Use parallel jobs if supported (git 2.9+)
    if git -C "$DIR" submodule update --help 2>&1 | grep -q -- '--jobs'; then
      git -C "$DIR" submodule update --init --recursive --jobs ${SUBMODULE_JOBS:-4}
    else
      git -C "$DIR" submodule update --init --recursive
    fi
    echo "[INFO] Submodules updated."
  else
    echo "[INFO] No submodules."
  fi
}

DIR="$HOME/$DIR_NAME"
echo "[INFO] Target dir: $DIR"

if [ ! -d "$DIR/.git" ]; then
  echo "[INFO] Cloning $REPO_URL"
  git clone --quiet "$REPO_URL" "$DIR"
  cd "$DIR"
  BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo main)"
  update_submodules
else
  echo "[INFO] Updating repo"
  cd "$DIR"
  BRANCH="${BRANCH:-}"
  if [ -z "$BRANCH" ] || [ "$BRANCH" = "HEAD" ]; then
    # Try to detect default remote HEAD, fallback to current ref or main
    BRANCH=$(git remote show origin 2>/dev/null | awk '/HEAD branch/ {print $NF}') || true
    if [ -z "$BRANCH" ]; then
      BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo main)
    fi
  fi
  if [ "$FORCE_MODE" = "1" ]; then
    echo "[INFO] Force mode enabled. Hard resetting to origin/$BRANCH"
    git fetch --all --prune
    git reset --hard "origin/$BRANCH" || true
    git clean -fdx
  else
    if ! git pull --ff-only; then
      echo "[WARN] Fast-forward failed; hard reset (non-force fallback)."
      git fetch --all --prune
      git reset --hard "origin/$BRANCH" || true
      git clean -fdx
    fi
  fi
  update_submodules
fi

if [ "$CLEAN_MODE" = "1" ]; then
  echo "[INFO] Clean mode: removing logs directory if present"
  rm -rf logs || true
fi
RS
}

sync_one() {
  raw_idx="$1"
  idx_padded="$(pad "$raw_idx")"
  host="des${idx_padded}.kask"
  dir="${REPO_DIR_PREFIX}${idx_padded}"

  echo -e "\n${YELLOW}==> ${host} (${dir})${NC}"

  attempt=1
  while [ "$attempt" -le "$MAX_RETRIES" ]; do
    if [ "$attempt" -gt 1 ]; then
      echo -e "${YELLOW}Retry ${attempt}/${MAX_RETRIES} ${host}${NC}"
      sleep 2
    fi

  if remote_sync | ssh ${SSH_OPTS} "${host}" bash -s -- "${REPO_URL}" "${dir}" "${CLEAN_MODE}" "${FORCE_MODE}"; then
      echo -e "${GREEN}[OK] ${host}${NC}"
      return 0
    else
      rc=$?
      echo -e "${RED}[FAIL] Attempt ${attempt} rc=${rc} ${host}${NC}"
    fi
    attempt=$((attempt+1))
  done

  echo -e "${RED}[ERROR] Could not sync ${host}${NC}"
  return 1
}

if [ "$PARALLEL" -eq 1 ]; then
  echo -e "${YELLOW}Parallel mode (JOBS=${JOBS})${NC}"
  export REPO_URL CLEAN_MODE FORCE_MODE REPO_DIR_PREFIX MAX_RETRIES SSH_OPTS GREEN YELLOW RED NC
  export -f pad sync_one remote_sync
  seq "$START" "$END" | xargs -P "${JOBS}" -I{} bash -c 'sync_one "$@"' _ {}
else
  n="$START"
  while [ "$n" -le "$END" ]; do
    sync_one "$n" || true
    n=$((n+1))
  done
fi

echo -e "\n${GREEN}========== SYNC COMPLETE ==========${NC}"
if [ "$CLEAN_MODE" -eq 1 ]; then
  echo -e "${YELLOW}Clean mode applied (logs removed).${NC}"
fi