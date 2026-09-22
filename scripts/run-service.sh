#!/usr/bin/env bash
# Private deployment.env supplies absolute paths, never credentials on argv.
set +x
set -euo pipefail
umask 077
fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
target="${1-}"
action="${2-run}"
case "$target" in mihomo|codex|api) ;; *) fail 'Expected mihomo, codex or api' ;; esac
case "$action" in check|run|login) ;; *) fail 'Expected check, run or login' ;; esac
config_dir="${FEISHU_DEPLOY_CONFIG:-$HOME/.config/feishu-agent}"
[[ -f "$config_dir/deployment.env" ]] || fail 'Missing private deployment.env'
source "$config_dir/deployment.env"
export PATH="$TOOL_ROOT/bin:$PATH"
export DISABLE_AUTOUPDATER=1

if [[ "$target" == mihomo ]]; then
  [[ -s "$config_dir/mihomo/config.yaml" ]] || fail 'Missing Mihomo config.yaml with user-supplied nodes'
  mkdir -p "$DEPLOY_STATE_DIR/logs"
  # Mihomo validation may include node/subscription URLs; keep output private.
  if ! mihomo -t -d "$config_dir/mihomo" -f "$config_dir/mihomo/config.yaml" > "$DEPLOY_STATE_DIR/logs/mihomo-check.log" 2>&1; then
    fail 'Mihomo configuration failed; inspect the private mihomo-check.log'
  fi
  [[ "$action" != login ]] || fail 'login is only for Codex'
  if [[ "$action" == check ]]; then printf 'MIHOMO_CONFIG_OK\n'; exit 0; fi
  exec mihomo -d "$config_dir/mihomo" -f "$config_dir/mihomo/config.yaml"
fi

[[ -f "$config_dir/$target.env" ]] || fail "Missing private $target.env"
source "$config_dir/$target.env"
case "$target:${BRIDGE_PROFILE-}" in
  codex:codex-readonly|codex:codex-approval|api:claude-anthropic|api:claude-deepseek) ;;
  *) fail 'BRIDGE_PROFILE does not match the selected authentication route' ;;
esac
if [[ "${USE_SERVER_PROXY:-0}" == 1 ]]; then
  [[ -f "$config_dir/proxy.env" ]] || fail 'Missing private proxy.env'
  source "$config_dir/proxy.env"
  "$DEPLOY_PYTHON" - <<'PY'
import socket,sys
try:
    with socket.create_connection(('127.0.0.1',7890),timeout=2):pass
except OSError:
    sys.exit('ERROR: Expected server proxy on 127.0.0.1:7890; start Mihomo first')
PY
fi

if [[ "$target" == codex ]]; then
  [[ -z "${OPENAI_API_KEY-}" ]] || fail 'Codex route uses ChatGPT; remove inherited OPENAI_API_KEY'
  if [[ "$action" == login ]]; then exec codex login --device-auth; fi
else
  [[ "$action" != login ]] || fail 'API credentials are provided in api.env, not via subscription login'
fi

bash "$BOOTSTRAP_ROOT/scripts/run-bridge.sh" "$BRIDGE_PROFILE" --check
if [[ "$target" == codex ]]; then
  login_status="$(codex login status 2>&1)" || fail 'Codex login is missing; use agentctl.sh login codex'
  [[ "$login_status" == *ChatGPT* ]] || fail 'Expected Codex ChatGPT authentication; review target auth configuration'
fi
if [[ "$action" == check ]]; then exit 0; fi
exec bash "$BOOTSTRAP_ROOT/scripts/run-bridge.sh" "$BRIDGE_PROFILE"
