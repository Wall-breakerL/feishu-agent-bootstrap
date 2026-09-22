#!/usr/bin/env bash
# Validate trusted environment inputs before cc-connect expands its TOML values.
# No login, package installation, shell profile loading, or secret printing.
set +x
set -euo pipefail
umask 077

fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
usage() {
  printf '%s\n' 'Usage: bash scripts/run-bridge.sh {codex-readonly|codex-approval|claude-anthropic|claude-deepseek} [--check]'
}

if [[ $# -lt 1 || $# -gt 2 ]]; then usage; exit 2; fi
profile="$1"
check_only=false
if [[ $# -eq 2 ]]; then
  [[ "$2" == '--check' ]] || { usage; exit 2; }
  check_only=true
fi

case "$profile" in
  codex-readonly|codex-approval) agent_bin=codex ;;
  claude-anthropic|claude-deepseek) agent_bin=claude ;;
  *) usage; exit 2 ;;
esac

required=(PROJECT_NAME PROJECT_DIR BRIDGE_STATE_DIR FEISHU_APP_ID FEISHU_APP_SECRET FEISHU_ALLOW_FROM)
check_variable() {
  local name="$1" value
  value="${!name-}"
  [[ -n "${value//[[:space:]]/}" ]] || fail "Missing required variable: $name"
  [[ "$value" != *REPLACE_WITH* ]] || fail "Replace example placeholder: $name"
  [[ "$value" != *$'\n'* && "$value" != *$'\r'* ]] || fail "Multiline value is not allowed: $name"
}
for name in "${required[@]}"; do
  check_variable "$name"
done

[[ "$PROJECT_NAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]] || fail 'PROJECT_NAME must contain only letters, numbers, hyphens or underscores'
[[ "$PROJECT_DIR" == /* && -d "$PROJECT_DIR" ]] || fail 'PROJECT_DIR must be an existing absolute directory'
[[ "$BRIDGE_STATE_DIR" == /* && "$BRIDGE_STATE_DIR" != / ]] || fail 'BRIDGE_STATE_DIR must be a dedicated absolute directory'
[[ "$FEISHU_APP_ID" =~ ^cli_[a-zA-Z0-9]+$ ]] || fail 'FEISHU_APP_ID must be a Feishu application ID'
[[ "$FEISHU_ALLOW_FROM" =~ ^ou_[a-zA-Z0-9]+(,ou_[a-zA-Z0-9]+)*$ ]] || fail 'FEISHU_ALLOW_FROM must be explicit comma-separated open_ids; empty values and wildcards are forbidden'

command -v cc-connect >/dev/null 2>&1 || fail 'cc-connect is not on PATH'
command -v "$agent_bin" >/dev/null 2>&1 || fail 'Selected agent CLI is not on PATH'
version_output="$(cc-connect --version 2>/dev/null)" || fail 'Cannot read cc-connect version'
version_line="${version_output%%$'\n'*}"
[[ "$version_line" == 'cc-connect v1.5.0' || "$version_line" == 'cc-connect 1.5.0' ]] || fail 'This template requires cc-connect v1.5.0; revalidate before changing the baseline'

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
template_path="$script_dir/../configs/$profile.toml"
config_path="$BRIDGE_STATE_DIR/config.$profile.toml"
[[ -f "$template_path" ]] || fail 'Bundled configuration template is missing'
[[ ! -L "$config_path" ]] || fail 'Runtime configuration must not be a symlink'
if [[ -e "$config_path" ]]; then
  [[ -f "$config_path" && -r "$config_path" && -w "$config_path" ]] || fail 'Runtime configuration must be a readable, writable file'
  config_text="$(<"$config_path")"
  # Generated project names are literal, allowing upstream /model persistence.
  # Model/provider surgical updates preserve this line. Manual restructuring
  # requires review instead of silently selecting another project.
  name_seen=false
  while IFS= read -r line; do
    [[ "$line" != "name = \"$PROJECT_NAME\"" ]] || name_seen=true
  done <<< "$config_text"
  "$name_seen" || fail 'Runtime project name differs; review state directory and PROJECT_NAME'
else
  config_text="$(<"$template_path")"
  config_text="${config_text//'${PROJECT_NAME}'/$PROJECT_NAME}"
fi

# Check the actual reusable runtime config, including extra configured providers.
# Do not expand secrets into a file or require an old model variable after /model
# has replaced it with a literal value.
remaining="$config_text"
env_pattern='\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
while [[ "$remaining" =~ $env_pattern ]]; do
  token="${BASH_REMATCH[0]}"
  check_variable "${BASH_REMATCH[1]}"
  remaining="${remaining#*"$token"}"
done

if "$check_only"; then
  printf '%s\n' 'CONFIG_PREFLIGHT_OK: required inputs and binaries checked; authentication, network and message flow are NOT verified.'
  exit 0
fi

# Existing directories keep their permissions. Provision a private state directory
# per runbook, rather than silently chmod-ing a potentially shared directory.
mkdir -p -- "$BRIDGE_STATE_DIR"
if [[ ! -e "$config_path" ]]; then
  # noclobber refuses a concurrent first launch instead of overwriting its file.
  (set -o noclobber; printf '%s\n' "$config_text" > "$config_path") || fail 'Cannot create runtime configuration; inspect before retrying'
fi
exec cc-connect --config "$config_path"
