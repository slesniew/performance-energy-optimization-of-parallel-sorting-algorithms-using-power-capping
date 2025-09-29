#!/usr/bin/env bash

set -euo pipefail

PLAN="${1:-}"
if [[ -z "$PLAN" || "$PLAN" == "--"* ]]; then
  if [[ "$PLAN" == "--plan" ]]; then
    shift
    PLAN="${1:-}"
  fi
fi
if [[ -z "$PLAN" ]]; then
  grep '^# ' "$0" | sed 's/^# //'
  exit 1
fi
shift || true

BASE_PLAN=""
MAX_NODES=16
EXCLUDE_LIST=""
NODES_LIST=""
FORCE_SPLIT=0
DRY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-plan) BASE_PLAN="$2"; shift 2 ;;
    --nodes) MAX_NODES="$2"; shift 2 ;;
    --exclude) EXCLUDE_LIST="$2"; shift 2 ;;
    --nodes-list) NODES_LIST="$2"; shift 2 ;;
    --force-split) FORCE_SPLIT=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) grep '^# ' "$0" | sed 's/^# //'; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

[[ $MAX_NODES -gt 16 ]] && { echo "--nodes cannot exceed 16"; exit 1; }

PLAN_DIR="scripts/experiments/test_plans/${PLAN}"
SPLITTER="scripts/experiments/test_plans/split_test_plan.py"

declare -A EXCLUDED
IFS=',' read -r -a __ex <<< "$EXCLUDE_LIST"
for e in "${__ex[@]}"; do [[ -n "$e" ]] && EXCLUDED["$e"]=1; done

SELECTED=()
if [[ -n "$NODES_LIST" ]]; then
  IFS=',' read -r -a __nl <<< "$NODES_LIST"
  for n in "${__nl[@]}"; do
    [[ -z "$n" ]] && continue
    if [[ ! "$n" =~ ^des[0-9]{2}$ ]]; then
      echo "Invalid node name: $n" >&2
      exit 1
    fi
    SELECTED+=("$n")
  done
else
  for i in $(seq -f "%02g" 1 16); do
    n="des${i}"
    [[ ${EXCLUDED[$n]+x} ]] && continue
    SELECTED+=("$n")
    [[ ${#SELECTED[@]} -ge $MAX_NODES ]] && break
  done
fi

[[ ${#SELECTED[@]} -eq 0 ]] && { echo "No nodes selected"; exit 1; }

if [[ ! -d "$PLAN_DIR" ]]; then
  if [[ -z "$BASE_PLAN" ]]; then
    echo "Plan directory '$PLAN_DIR' missing and no --base-plan provided." >&2
    exit 1
  fi
else
  if [[ -z "$BASE_PLAN" ]]; then
    echo "Using existing split directory: $PLAN_DIR"
  elif [[ $FORCE_SPLIT -eq 0 ]]; then
    echo "Split directory '$PLAN_DIR' exists (use --force-split to overwrite)."
    exit 0
  fi
fi

if [[ -n "$BASE_PLAN" && ! -f "$BASE_PLAN" ]]; then
  echo "Base plan file not found: $BASE_PLAN" >&2
  exit 1
fi

echo "Split-only mode"
echo "Plan name:        $PLAN"
[[ -n "$BASE_PLAN" ]] && echo "Base plan file:   $BASE_PLAN"
echo "Output dir:       $PLAN_DIR"
echo "Selected nodes:   ${SELECTED[*]}"
echo "Excluded nodes:   ${EXCLUDE_LIST:-<none>}"
echo "Force split:      $([[ $FORCE_SPLIT -eq 1 ]] && echo yes || echo no)"
echo "Dry run:          $([[ $DRY -eq 1 ]] && echo yes || echo no)"

if [[ $DRY -eq 1 ]]; then
  if [[ -n "$BASE_PLAN" ]]; then
    echo "[DRY] Would (re)create: $PLAN_DIR"
    echo "[DRY] Would run splitter:"
    echo "python3 $SPLITTER --plan $BASE_PLAN --output-dir $PLAN_DIR --nodes $(IFS=','; echo "${SELECTED[*]}")"
  else
    echo "[DRY] No --base-plan provided; assuming existing splits reused."
  fi
  exit 0
fi

if [[ -n "$BASE_PLAN" ]]; then
  [[ -d "$PLAN_DIR" ]] && rm -rf "$PLAN_DIR"
  mkdir -p "$PLAN_DIR"
  NODES_CSV=$(IFS=','; echo "${SELECTED[*]}")
  echo "Splitting..."
  set -x
  python3 "$SPLITTER" \
    --plan "$BASE_PLAN" \
    --output-dir "$PLAN_DIR" \
    --nodes "$NODES_CSV"
  set +x
  echo "Done."
else
  echo "No splitting performed (no --base-plan); existing files retained."
fi

if [[ -d "$PLAN_DIR" ]]; then
  count=$(ls -1 "$PLAN_DIR"/split_test_plan_*.json 2>/dev/null | wc -l || true)
  echo "Split files present: $count"
  ls -1 "$PLAN_DIR"/split_test_plan_*.json 2>/dev/null