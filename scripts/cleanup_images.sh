#!/usr/bin/env bash

set -euo pipefail
JUMP_USER="s184711"
JUMP_HOST="kask.eti.pg.edu.pl"
HOST_SUFFIX=".kask"
PARALLEL=1
DRY=0
AGGRESSIVE=0
ALL_UNTAGGED=0
SYSTEM_PRUNE=0
declare -a SELECT_NODES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--parallel) PARALLEL="$2"; shift 2 ;;
    -n|--nodes) shift; while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do SELECT_NODES+=("$1"); shift; done ;;
    --dry) DRY=1; shift ;;
    --aggressive) AGGRESSIVE=1; shift ;;
    --all-untagged) ALL_UNTAGGED=1; shift ;;
    --system-prune) SYSTEM_PRUNE=1; AGGRESSIVE=1; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# //'; exit 0 ;;
    *) echo "Unknown arg $1" >&2; exit 1 ;;
  esac
done

nodes=()
if ((${#SELECT_NODES[@]})); then
  nodes=("${SELECT_NODES[@]}")
else
  for i in $(seq -f "%02g" 1 16); do nodes+=("des${i}"); done
fi

ssh_opts=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 -o ServerAliveInterval=30 -o ServerAliveCountMax=3)

remote_script_base='
set -euo pipefail
log(){ echo "[INFO] $1"; }
err(){ echo "[ERR ] $1" >&2; }

if ! command -v docker >/dev/null 2>&1; then
  err "docker missing"
  exit 2
fi

show_stats(){
  echo "[STATS] Images:"
  docker images --format "{{.Repository}}|{{.Tag}}|{{.ID}}|{{.Size}}" | sed "s/^/[STATS] /"
  echo "[STATS] Containers (stopped):"
  docker ps -a -f status=exited --format "{{.ID}} {{.Image}}" | sed "s/^/[STATS] /"
}

DRY=${DRY:-0}
AGGR=${AGGR:-0}
ALL_UNTAGGED=${ALL_UNTAGGED:-0}
SYSTEM_PRUNE=${SYSTEM_PRUNE:-0}

log "Initial state"
show_stats

# Collect candidate images
if (( ALL_UNTAGGED )); then
  # Any image whose repo OR tag is <none>
  mapfile -t CAND < <(docker images --format "{{.ID}} {{.Repository}} {{.Tag}}" | awk '\''$2=="<none>" || $3=="<none>" {print $1}'\'' | sort -u)
else
  # Strict dangling (no tag refs)
  mapfile -t CAND < <(docker images -f dangling=true -q | sort -u)
fi

if ((${#CAND[@]}==0)); then
  log "No candidate images"
else
  log "Candidate image IDs: ${CAND[*]}"
fi

if (( DRY )); then
  log "(dry-run) Would remove images: ${CAND[*]:-<none>}"
  (( AGGR )) && log "(dry-run) Would prune build cache & stopped containers"
  (( SYSTEM_PRUNE )) && log "(dry-run) Would run: docker system prune -f"
  exit 0
fi

if (( AGGR )); then
  # Remove stopped containers blocking deletes
  mapfile -t STOPPED < <(docker ps -a -q -f status=exited || true)
  if ((${#STOPPED[@]})); then
    log "Removing exited containers (${#STOPPED[@]})"
    docker rm "${STOPPED[@]}" >/dev/null 2>&1 || true
  fi
fi

removed_any=0
if ((${#CAND[@]})); then
  for img in "${CAND[@]}"; do
    if docker rmi "$img"; then
      log "Removed image $img"
      removed_any=1
    else
      log "Could not remove $img (in use?)"
      if (( AGGR )); then
        # Find containers referencing it (running)
        mapfile -t CONT < <(docker ps -q --filter ancestor="$img" || true)
        if ((${#CONT[@]})); then
          log "Stopping containers using $img: ${CONT[*]}"
          docker stop "${CONT[@]}" >/dev/null 2>&1 || true
          log "Removing containers using $img"
          docker rm "${CONT[@]}" >/dev/null 2>&1 || true
          docker rmi "$img" && log "Removed image $img after stopping containers"
        fi
      fi
    fi
  done
fi

if (( AGGR )); then
  log "docker image prune -f (dangling layers)"
  docker image prune -f || true
  log "docker builder prune -f (build cache)"
  docker builder prune -f || true
fi

if (( SYSTEM_PRUNE )); then
  log "docker system prune -f (aggressive)"
  docker system prune -f || true
fi

log "Final state"
show_stats
if (( removed_any )); then
  log "Cleanup completed (some images removed)."
else
  log "No images removed."
fi
'

run_one() {
  local n="$1"
  local t="${n}${HOST_SUFFIX}"
  echo "[*] $n"
  ssh "${ssh_opts[@]}" -J "${JUMP_USER}@${JUMP_HOST}" "${JUMP_USER}@${t}" \
    DRY="$DRY" AGGR="$AGGRESSIVE" ALL_UNTAGGED="$ALL_UNTAGGED" SYSTEM_PRUNE="$SYSTEM_PRUNE" \
    bash -s <<<"$remote_script_base" || echo "[WARN] $n failed"
}

if (( PARALLEL > 1 )); then
  for n in "${nodes[@]}"; do run_one "$n" & done
  wait
else
  for n in "${nodes[@]}"; do run_one "$n"; done
fi
echo "Cleanup complete."