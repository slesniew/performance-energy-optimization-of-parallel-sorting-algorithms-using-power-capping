#!/usr/bin/env bash
set -euo pipefail

PROXY_USER="${PROXY_USER:-s184711}"
PROXY_HOST="${PROXY_HOST:-kask.eti.pg.gda.pl}"
TARGET_PREFIX="${TARGET_PREFIX:-des}"
TARGET_DOMAIN="${TARGET_DOMAIN:-kask}"
START="${START:-1}"
END="${END:-16}"

echo "[INFO] Connecting to proxy ${PROXY_USER}@${PROXY_HOST} to refresh host keys (${TARGET_PREFIX}{${START}..${END}}.${TARGET_DOMAIN})"

ssh -o BatchMode=no -o StrictHostKeyChecking=accept-new "${PROXY_USER}@${PROXY_HOST}" bash -s <<'EOF'
set -euo pipefail
TARGET_PREFIX="${TARGET_PREFIX:-des}"
TARGET_DOMAIN="${TARGET_DOMAIN:-kask}"
START="${START:-1}"
END="${END:-16}"
REMOTE_KNOWN_HOSTS="$HOME/.ssh/known_hosts"

timestamp() { date +'%Y-%m-%d_%H-%M-%S'; }

mkdir -p "$HOME/.ssh"
[[ -f "$REMOTE_KNOWN_HOSTS" ]] || touch "$REMOTE_KNOWN_HOSTS"

BACKUP="${REMOTE_KNOWN_HOSTS}.bak.$(timestamp)"
cp "$REMOTE_KNOWN_HOSTS" "$BACKUP"
echo "[INFO] Backup created: $BACKUP"

TMP_FILE="${REMOTE_KNOWN_HOSTS}.tmp.$$"
cp "$REMOTE_KNOWN_HOSTS" "$TMP_FILE"

pad() { printf "%02d" "$1"; }

for n in $(seq "$START" "$END"); do
  idx=$(pad "$n")
  host_short="${TARGET_PREFIX}${idx}"
  host_fqdn="${host_short}.${TARGET_DOMAIN}"
  echo "[INFO] Removing old keys: $host_fqdn / $host_short"
  ssh-keygen -f "$TMP_FILE" -R "$host_fqdn" >/dev/null 2>&1 || true
  ssh-keygen -f "$TMP_FILE" -R "$host_short"  >/devnull 2>&1 || true
done

mv "$TMP_FILE" "$REMOTE_KNOWN_HOSTS"

echo "[INFO] Re-learning host keys"
errors=0

supports_accept_new=1
ssh -o StrictHostKeyChecking=accept-new -G localhost >/dev/null 2>&1 || supports_accept_new=0
key_add_opts="-o StrictHostKeyChecking=no"
[[ $supports_accept_new -eq 1 ]] && key_add_opts="-o StrictHostKeyChecking=accept-new"

for n in $(seq "$START" "$END"); do
  idx=$(pad "$n")
  host_fqdn="${TARGET_PREFIX}${idx}.${TARGET_DOMAIN}"
  if ssh -o ConnectTimeout=5 $key_add_opts "$host_fqdn" true < /dev/null 2>/dev/null; then
    echo "[OK ] $host_fqdn"
  else
    echo "[FAIL] $host_fqdn" >&2
    errors=$((errors+1))
  fi
done

if [[ $errors -ne 0 ]]; then
  echo "[WARN] Completed with $errors failures. Backup: $BACKUP"
  exit 1
fi

echo "[INFO] Success. Backup: $BACKUP"
EOF

rc=$?
if [[ $rc -ne 0 ]]; then
  echo "[ERROR] Remote operation failed (exit $rc)"
  exit $rc
fi
echo "[DONE] Host key refresh operation completed."