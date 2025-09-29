#!/usr/bin/env bash

set -euo pipefail

JUMP_USER="s184711"
JUMP_HOST="kask.eti.pg.edu.pl"
HOST_SUFFIX=".kask"
START=1
END=16
PARALLEL=1
RETRIES=1
TEST_ONLY=0
NO_CACHE=0
declare -a SELECT_NODES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--parallel) PARALLEL="${2:?}"; shift 2 ;;
    -r|--retries)  RETRIES="${2:?}"; shift 2 ;;
    --test) TEST_ONLY=1; shift ;;
    --no-cache) NO_CACHE=1; shift ;;
    -n|--nodes)
      shift
      while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do SELECT_NODES+=("$1"); shift; done
      ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# //'
      exit 0 ;;
    *) echo "Unknown arg $1" >&2; exit 1 ;;
  esac
done

ssh_opts=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 -o ServerAliveInterval=30 -o ServerAliveCountMax=3)

nodes=()
if ((${#SELECT_NODES[@]})); then
  nodes=("${SELECT_NODES[@]}")
else
  for i in $(seq -f "%02g" "$START" "$END"); do nodes+=("des${i}"); done
fi

timestamp(){ date +"%H:%M:%S"; }

remote_build_script='
set -euo pipefail
SHORT="$(hostname | cut -d. -f1)"
TARGET="$HOME/$SHORT"
if [ ! -d "$TARGET" ]; then
  echo "[ERROR] Directory $TARGET missing" >&2
  exit 2
fi
cd "$TARGET"
echo "[INFO] In $(pwd) on $(hostname)"
if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker not installed" >&2
  exit 3
fi
if docker buildx version >/dev/null 2>&1; then
  export DOCKER_BUILDKIT=1
  echo "[INFO] Using BuildKit"
else
  export DOCKER_BUILDKIT=0
  echo "[INFO] BuildKit not available; falling back"
fi
if [ "${NO_CACHE:-0}" = "1" ]; then
  echo "[INFO] Building with --no-cache"
  NC_FLAG="--no-cache"
else
  NC_FLAG=""
fi
docker build $NC_FLAG -t sort-app .
'

remote_test_script='echo connected_on:$(hostname)'

run_one() {
  local node="${1:-}"
  if [[ -z "$node" ]]; then
    echo "run_one: missing node argument" >&2
    return 2
  fi
  local attempt=1
  local target="${node}${HOST_SUFFIX}"

  while (( attempt <= RETRIES )); do
    echo "[$(timestamp)] ${node}: attempt ${attempt}/${RETRIES}"

    local remote_script
    if (( TEST_ONLY )); then
      remote_script="$remote_test_script"
    else
      remote_script="$remote_build_script"
    fi

    if ssh "${ssh_opts[@]}" -J "${JUMP_USER}@${JUMP_HOST}" "${JUMP_USER}@${target}" NO_CACHE="$NO_CACHE" bash -s <<<"$remote_script"; then
      echo "[$(timestamp)] ${node}: OK"
      return 0
    fi
    echo "[$(timestamp)] ${node}: FAIL attempt ${attempt}" >&2
    ((attempt<RETRIES)) && sleep 2
    ((attempt++))
  done
  return 1
}

tmp_status_dir="$(mktemp -d)"
cleanup(){ rm -rf "$tmp_status_dir"; }
trap cleanup EXIT

if (( PARALLEL > 1 )); then
  echo "Parallel: $PARALLEL"
  fifo="$tmp_status_dir/fifo"; mkfifo "$fifo"; exec 3<>"$fifo"; rm "$fifo"
  for _ in $(seq 1 "$PARALLEL"); do echo >&3; done
  for n in "${nodes[@]}"; do
    read -r -u 3
    {
      if run_one "$n"; then echo 0 >"$tmp_status_dir/$n"; else echo 1 >"$tmp_status_dir/$n"; fi
      echo >&3
    } &
  done
  wait
  exec 3>&-
else
  for n in "${nodes[@]}"; do
    if run_one "$n"; then echo 0 >"$tmp_status_dir/$n"; else echo 1 >"$tmp_status_dir/$n"; fi
  done
fi

fail_count=0
for f in "$tmp_status_dir"/*; do
  [[ -f "$f" ]] || continue
  [[ "$(cat "$f")" == 0 ]] || ((fail_count++))
done

if (( TEST_ONLY )); then
  ((fail_count)) && { echo "Connectivity failed on $fail_count host(s)."; exit 1; }
  echo "Connectivity OK on all hosts."
  exit 0
fi

if (( fail_count )); then
  echo "Builds failed on $fail_count host(s)." >&2
  exit 1
fi
echo "All builds completed