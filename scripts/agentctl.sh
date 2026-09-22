#!/usr/bin/env bash
# Separate supervisor namespace; does not control AutoDL platform processes.
set +x
set -euo pipefail
umask 077
fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
config_dir="${FEISHU_DEPLOY_CONFIG:-$HOME/.config/feishu-agent}"
[[ -f "$config_dir/deployment.env" ]] || fail 'Missing private deployment.env'
source "$config_dir/deployment.env"
supervisor_config="$config_dir/supervisord.conf"
action="${1-status}"
target="${2-}"
if [[ "$action" != status ]]; then
  case "$target" in mihomo|codex|api) ;; *) fail 'Specify mihomo, codex or api' ;; esac
fi
ctl() { "$SUPERVISORCTL" -c "$supervisor_config" "$@"; }
ensure_manager() {
  if ! ctl pid >/dev/null 2>&1; then
    "$SUPERVISORD" -c "$supervisor_config"
  fi
}
case "$action" in
  status)
    status_code=0
    ctl status || status_code=$?
    [[ "$status_code" == 0 || "$status_code" == 3 ]]
    ;;
  check) exec bash "$BOOTSTRAP_ROOT/scripts/run-service.sh" "$target" check ;;
  login) exec bash "$BOOTSTRAP_ROOT/scripts/run-service.sh" "$target" login ;;
  start)
    bash "$BOOTSTRAP_ROOT/scripts/run-service.sh" "$target" check
    ensure_manager
    if ctl status "$target" | grep -q ' RUNNING '; then
      printf '%s already running\n' "$target"
    else
      ctl start "$target"
    fi
    ;;
  stop) ctl stop "$target" ;;
  *) fail 'Usage: agentctl.sh status | {check|start|stop|login} {mihomo|codex|api}' ;;
esac
