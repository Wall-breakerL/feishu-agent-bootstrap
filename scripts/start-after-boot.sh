#!/usr/bin/env bash
# Called by a verified platform boot hook; independent of interactive shell setup.
set +x
set -euo pipefail
umask 077
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
config_dir="${FEISHU_DEPLOY_CONFIG:-$HOME/.config/feishu-agent}"
[[ -f "$config_dir/deployment.env" ]] || { printf 'Missing deployment.env\n' >&2; exit 1; }
source "$config_dir/deployment.env"
mkdir -p "$DEPLOY_STATE_DIR/logs"

# --close keeps the lock out of the daemon and its children. Repeated boot-hook
# invocations must not start competing supervisors or keep a stale lock alive.
if [[ "${1-}" != --locked ]]; then
  exec /usr/bin/flock --nonblock --close "$DEPLOY_STATE_DIR/boot-start.lock" \
    /bin/bash "$BOOTSTRAP_ROOT/scripts/start-after-boot.sh" --locked
fi
exec >> "$DEPLOY_STATE_DIR/logs/boot-start.log" 2>&1
printf '[%s] Boot recovery started\n' "$(date -Is)"
result=0
for target in mihomo api codex; do
  started=0
  for attempt in 1 2 3; do
    if /usr/bin/timeout 45 /bin/bash "$BOOTSTRAP_ROOT/scripts/agentctl.sh" start "$target"; then
      started=1
      break
    fi
    printf '[%s] %s start failed (attempt %s/3)\n' "$(date -Is)" "$target" "$attempt"
    if [[ "$attempt" != 3 ]]; then sleep 5; fi
  done
  # A proxy failure must not prevent the direct API route from starting.
  if [[ "$started" != 1 ]]; then result=1; fi
done
/bin/bash "$BOOTSTRAP_ROOT/scripts/agentctl.sh" status || result=1
printf '[%s] Boot recovery finished: exit=%s\n' "$(date -Is)" "$result"
exit "$result"
