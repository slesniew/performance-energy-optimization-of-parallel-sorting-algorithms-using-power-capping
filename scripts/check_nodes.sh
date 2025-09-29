#!/usr/bin/env bash

set -euo pipefail

START=${START:-1}
END=${END:-16}
MAX_RETRIES=${MAX_RETRIES:-2}
CONNECT_TIMEOUT=${CONNECT_TIMEOUT:-8}
PARALLEL=${PARALLEL:-1} 
JOBS=${JOBS:-8}

PROXY_USER=${PROXY_USER:-s184711}
PROXY_HOST=${PROXY_HOST:-kask.eti.pg.gda.pl}

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

JUMP_OPT="-J ${PROXY_USER}@${PROXY_HOST}"
if hostname 2>/dev/null | grep -qi '^kask'; then
  JUMP_OPT=""
fi

SSH_BASE_OPTS="-o ConnectTimeout=${CONNECT_TIMEOUT} -o ServerAliveInterval=5 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=accept-new -o BatchMode=no ${JUMP_OPT}"

NODE_INFO_FILE=$(mktemp)
echo "Node,Load1m,Users,Status,Score" > "${NODE_INFO_FILE}"

pad() { printf "%02d" "$1"; }

remote_collect() {
  local node="$1"
  ssh ${SSH_BASE_OPTS} "${node}" 'bash -s' <<'RS'
set -e
LOAD_1=$(cut -d' ' -f1 /proc/loadavg 2>/dev/null || echo 999)
LOAD_1=$(echo "$LOAD_1" | sed 's/,*$//')
USERS=$(who 2>/dev/null | wc -l || echo 0)

status="HEAVY"
score=0
if awk -v l="$LOAD_1" 'BEGIN{exit !(l+0 < 1.0)}'; then
  if [ "$USERS" -lt 2 ]; then
    status="AVAILABLE"
    score=100
  fi
fi

if [ "$status" = "HEAVY" ]; then
  if awk -v l="$LOAD_1" 'BEGIN{exit !(l+0 < 5.0)}'; then
    status="MODERATE"
    score=$(awk -v l="$LOAD_1" -v u="$USERS" 'BEGIN{ s = 90 - (l*10 + u*5); if (s<0) s=0; printf "%d", s }')
  else
    score=$(awk -v l="$LOAD_1" -v u="$USERS" 'BEGIN{ s = 50 - (l*5 + u*2); if (s<0) s=0; printf "%d", s }')
  fi
fi

echo "NODE_RESULT:$LOAD_1:$USERS:$status:$score"
echo "----"
echo "Load1m: $LOAD_1"
echo "Users : $USERS"
echo "Status: $status (score $score)"
ps aux --sort=-%cpu | head -6 2>/dev/null || true
RS
}

process_node() {
  local idx="$1"
  local host="des${idx}.kask"
  echo -e "\n${YELLOW}Checking node ${host}...${NC}"

  local attempt=1
  while [ $attempt -le $MAX_RETRIES ]; do
    [ $attempt -gt 1 ] && echo -e "${YELLOW}Retry attempt $attempt for ${host}...${NC}" && sleep 2

    if OUTPUT=$(remote_collect "$host" 2>&1); then
      echo -e "${GREEN}Connected to ${host}${NC}"
      echo "$OUTPUT"
      RESULT_LINE=$(echo "$OUTPUT" | grep '^NODE_RESULT:' || true)
      if [ -n "$RESULT_LINE" ]; then
        LOAD=$(echo "$RESULT_LINE"  | cut -d: -f2)
        USERS=$(echo "$RESULT_LINE" | cut -d: -f3)
        STATUS=$(echo "$RESULT_LINE"| cut -d: -f4)
        SCORE=$(echo "$RESULT_LINE" | cut -d: -f5)
        echo "${host},${LOAD},${USERS},${STATUS},${SCORE}" >> "${NODE_INFO_FILE}"
        return 0
      fi
      echo -e "${RED}Malformed data from ${host}${NC}"
    else
      echo -e "${RED}SSH failure (${host}):${NC} $OUTPUT"
    fi
    attempt=$((attempt+1))
  done

  echo -e "${RED}Failed to connect to ${host} after ${MAX_RETRIES} attempts${NC}"
  echo "${host},999,N/A,UNREACHABLE,0" >> "${NODE_INFO_FILE}"
  return 1
}

if [ "${PARALLEL}" -eq 1 ]; then
  echo -e "${YELLOW}Parallel mode enabled (JOBS=${JOBS})${NC}"
  export -f process_node remote_collect
  export SSH_BASE_OPTS NODE_INFO_FILE MAX_RETRIES YELLOW GREEN RED NC
  seq -f "%02g" "${START}" "${END}" | xargs -P "${JOBS}" -I{} bash -c 'process_node "$@" || true' _ {}
else
  for n in $(seq "${START}" "${END}"); do
    process_node "$(pad "$n")" || true
  done
fi

echo -e "\n\n${GREEN}========== NODE AVAILABILITY SUMMARY ==========${NC}"
echo -e "${YELLOW}Nodes ranked from best to worst:${NC}\n"
echo -e "Rank\tNode\t\tLoad\tUsers\tStatus\t\tScore"
echo -e "----\t----\t\t----\t-----\t------\t\t-----"

if [ "$(wc -l < "${NODE_INFO_FILE}")" -le 1 ]; then
  echo -e "${RED}No node data collected.${NC}"
else
  tail -n +2 "${NODE_INFO_FILE}" | \
    sort -t, -k5,5nr -k2,2g -k3,3n | \
    awk -F, '{
      printf "%d\t%-12s\t%-4s\t%-5s\t%-10s\t%s\n", NR, $1, $2, $3, $4, $5
    }'
fi

rm -f "${NODE_INFO_FILE}"

echo -e "\n${GREEN}======== End of Node Availability Report ========${NC}"