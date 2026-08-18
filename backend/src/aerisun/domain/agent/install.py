from __future__ import annotations

import shlex
from urllib.parse import urlsplit

INSTALL_SCHEMA_VERSION = "2026-08-09-install-v6"
MCP_PROTOCOL_VERSION = "2026-07-28"
PLUGIN_NAME = "aerisun-mcp"
PLUGIN_VERSION = "0.1.0"
MARKETPLACE_NAME = "aerisun"
REPOSITORY_URL = "https://github.com/Aerisun/Serino.git"
KEY_UPDATER_NAME = "serino-mcp-key"
KEY_UPDATER_COMMAND = f"~/.local/bin/{KEY_UPDATER_NAME}"


def _site_base_url(site_url: str) -> str:
    value = site_url.strip().rstrip("/")
    if not value or any(character.isspace() for character in value) or "\\" in value:
        raise ValueError("Aerisun site URL must be a clean http or https origin")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("Aerisun site URL must be a valid http or https origin") from exc
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise ValueError("Aerisun site URL must use http or https")
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Aerisun site URL must be an origin without credentials, a path, query, or fragment")
    return value


def _url(base_url: str, path: str) -> str:
    return f"{base_url}{path}"


def _credential_bootstrap_shell() -> str:
    return r"""umask 077
: "${HOME:?A user home directory is required.}"

aerisun_config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
aerisun_secret_dir="$aerisun_config_home/aerisun"
aerisun_secret_file="$aerisun_secret_dir/mcp-api-key"
aerisun_tmp_file=''
aerisun_tty_hidden=0

aerisun_restore_tty() {
  if [ "$aerisun_tty_hidden" = '1' ]; then
    stty echo </dev/tty >/dev/null 2>&1 || :
    printf '\n' >/dev/tty
    aerisun_tty_hidden=0
  fi
}

aerisun_cleanup() {
  aerisun_restore_tty
  if [ -n "$aerisun_tmp_file" ] && [ -f "$aerisun_tmp_file" ]; then
    rm -f "$aerisun_tmp_file"
  fi
}

trap 'aerisun_cleanup' EXIT
trap 'exit 1' HUP INT TERM

aerisun_api_key="${AERISUN_MCP_API_KEY:-}"
unset AERISUN_MCP_API_KEY
if [ -z "$aerisun_api_key" ]; then
  if [ ! -r /dev/tty ] || [ ! -w /dev/tty ]; then
    echo 'Interactive terminal required. For automation, set AERISUN_MCP_API_KEY for this installer run.' >&2
    exit 1
  fi
  stty -echo </dev/tty
  aerisun_tty_hidden=1
  printf 'Serino MCP API Key: ' >/dev/tty
  if ! IFS= read -r aerisun_api_key </dev/tty; then
    echo 'Unable to read the Aerisun MCP API Key.' >&2
    exit 1
  fi
  aerisun_restore_tty
fi

case "$aerisun_api_key" in
  ''|*[!A-Za-z0-9_-]*)
    echo 'Invalid Aerisun MCP API Key.' >&2
    exit 1
    ;;
esac
if [ "${#aerisun_api_key}" -lt 32 ]; then
  echo 'Invalid Aerisun MCP API Key.' >&2
  exit 1
fi

if [ -L "$aerisun_secret_dir" ] || { [ -e "$aerisun_secret_dir" ] && [ ! -d "$aerisun_secret_dir" ]; }; then
  echo "Refusing unsafe credential directory: $aerisun_secret_dir" >&2
  exit 1
fi
mkdir -p "$aerisun_secret_dir"
chmod 700 "$aerisun_secret_dir"

if [ -L "$aerisun_secret_file" ] || { [ -e "$aerisun_secret_file" ] && [ ! -f "$aerisun_secret_file" ]; }; then
  echo "Refusing unsafe credential file: $aerisun_secret_file" >&2
  exit 1
fi
aerisun_tmp_file=$(mktemp "$aerisun_secret_dir/.mcp-api-key.XXXXXX")
printf '%s\n' "$aerisun_api_key" >"$aerisun_tmp_file"
chmod 600 "$aerisun_tmp_file"
mv -f "$aerisun_tmp_file" "$aerisun_secret_file"
aerisun_tmp_file=''
chmod 600 "$aerisun_secret_file"
"""


def _codex_credential_shell() -> str:
    return r"""aerisun_codex_home="${CODEX_HOME:-$HOME/.codex}"
aerisun_codex_env="$aerisun_codex_home/.env"

if [ -L "$aerisun_codex_home" ] || { [ -e "$aerisun_codex_home" ] && [ ! -d "$aerisun_codex_home" ]; }; then
  echo "Refusing unsafe Codex home: $aerisun_codex_home" >&2
  exit 1
fi
mkdir -p "$aerisun_codex_home"

if [ -L "$aerisun_codex_env" ] || { [ -e "$aerisun_codex_env" ] && [ ! -f "$aerisun_codex_env" ]; }; then
  echo "Refusing unsafe Codex environment file: $aerisun_codex_env" >&2
  exit 1
fi
aerisun_tmp_file=$(mktemp "$aerisun_codex_home/.aerisun-env.XXXXXX")
if [ -f "$aerisun_codex_env" ]; then
  awk 'index($0, "AERISUN_MCP_API_KEY=") != 1 { print }' "$aerisun_codex_env" >"$aerisun_tmp_file"
fi
printf 'AERISUN_MCP_API_KEY=%s\n' "$aerisun_api_key" >>"$aerisun_tmp_file"
chmod 600 "$aerisun_tmp_file"
mv -f "$aerisun_tmp_file" "$aerisun_codex_env"
aerisun_tmp_file=''
chmod 600 "$aerisun_codex_env"

unset AERISUN_MCP_API_KEY aerisun_api_key
"""


def _refresh_existing_codex_credential_shell() -> str:
    return f"""aerisun_codex_credential_refreshed=0
aerisun_codex_home="${{CODEX_HOME:-$HOME/.codex}}"
aerisun_codex_env="$aerisun_codex_home/.env"

if [ -e "$aerisun_codex_env" ] || [ -L "$aerisun_codex_env" ]; then
  if [ -L "$aerisun_codex_home" ] || [ ! -d "$aerisun_codex_home" ]; then
    echo "Refusing unsafe Codex home: $aerisun_codex_home" >&2
    exit 1
  fi
  if [ -L "$aerisun_codex_env" ] || [ ! -f "$aerisun_codex_env" ]; then
    echo "Refusing unsafe Codex environment file: $aerisun_codex_env" >&2
    exit 1
  fi
  if grep -q '^AERISUN_MCP_API_KEY=' "$aerisun_codex_env"; then
{_codex_credential_shell()}
    aerisun_codex_credential_refreshed=1
  fi
fi

unset AERISUN_MCP_API_KEY aerisun_api_key
"""


def _preflight_existing_codex_credential_shell() -> str:
    return r"""aerisun_codex_home="${CODEX_HOME:-$HOME/.codex}"
aerisun_codex_env="$aerisun_codex_home/.env"

if [ -e "$aerisun_codex_env" ] || [ -L "$aerisun_codex_env" ]; then
  if [ -L "$aerisun_codex_home" ] || [ ! -d "$aerisun_codex_home" ]; then
    echo "Refusing unsafe Codex home: $aerisun_codex_home" >&2
    exit 1
  fi
  if [ -L "$aerisun_codex_env" ] || [ ! -f "$aerisun_codex_env" ]; then
    echo "Refusing unsafe Codex environment file: $aerisun_codex_env" >&2
    exit 1
  fi
fi
"""


def build_mcp_key_update_script() -> str:
    return f"""#!/bin/sh
set -eu

{_preflight_existing_codex_credential_shell()}
{_credential_bootstrap_shell()}
{_refresh_existing_codex_credential_shell()}
if [ "$aerisun_codex_credential_refreshed" = '1' ]; then
{_codex_daemon_reload_shell()}
  printf '%s\\n' 'Serino MCP API Key updated. Codex reconnected automatically.'
else
  printf '%s\\n' 'Serino MCP API Key updated.'
fi
"""


def _codex_daemon_reload_shell() -> str:
    return r"""
umask 077
: "${HOME:?A user home directory is required.}"
unset AERISUN_MCP_API_KEY

aerisun_config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
aerisun_secret_dir="$aerisun_config_home/aerisun"
aerisun_secret_file="$aerisun_secret_dir/mcp-api-key"
aerisun_codex_home="${CODEX_HOME:-$HOME/.codex}"
aerisun_managed_root="$aerisun_codex_home/packages/standalone"
aerisun_managed_releases="$aerisun_managed_root/releases"
aerisun_managed_release="$aerisun_managed_releases/serino-package-manager"
aerisun_managed_current="$aerisun_managed_root/current"
aerisun_managed_codex="$aerisun_managed_current/codex"
aerisun_package_target="$aerisun_managed_release/serino-package-codex-path"
aerisun_package_launcher="$aerisun_managed_release/codex"

command -v codex >/dev/null 2>&1 || {
  echo 'Codex CLI is required.' >&2
  exit 1
}
if [ ! -f "$aerisun_managed_codex" ] || [ ! -x "$aerisun_managed_codex" ]; then
  if [ -e "$aerisun_managed_codex" ] || [ -L "$aerisun_managed_codex" ]; then
    echo "Refusing unsafe managed Codex executable: $aerisun_managed_codex" >&2
    exit 1
  fi

  aerisun_package_codex=$(command -v codex)
  case "$aerisun_package_codex" in
    /*) ;;
    *)
      echo 'Unable to resolve the installed Codex executable.' >&2
      exit 1
      ;;
  esac
  if [ ! -f "$aerisun_package_codex" ] || [ ! -x "$aerisun_package_codex" ]; then
    echo "Refusing unsafe Codex executable: $aerisun_package_codex" >&2
    exit 1
  fi

  set -- \
    "$aerisun_codex_home/packages" \
    "$aerisun_managed_root" \
    "$aerisun_managed_releases" \
    "$aerisun_managed_release"
  for aerisun_managed_dir do
    if [ -L "$aerisun_managed_dir" ] || { [ -e "$aerisun_managed_dir" ] && [ ! -d "$aerisun_managed_dir" ]; }; then
      echo "Refusing unsafe managed Codex directory: $aerisun_managed_dir" >&2
      exit 1
    fi
    if [ ! -d "$aerisun_managed_dir" ]; then
      mkdir "$aerisun_managed_dir"
    fi
  done
  chmod 700 "$aerisun_managed_release"

  if [ -L "$aerisun_managed_current" ]; then
    if [ "$(readlink "$aerisun_managed_current")" != 'releases/serino-package-manager' ]; then
      echo "Refusing to replace an existing Codex release: $aerisun_managed_current" >&2
      exit 1
    fi
  elif [ -e "$aerisun_managed_current" ]; then
    echo "Refusing to replace an existing Codex release: $aerisun_managed_current" >&2
    exit 1
  fi

  if [ -L "$aerisun_package_target" ] || { [ -e "$aerisun_package_target" ] && [ ! -f "$aerisun_package_target" ]; }; then
    echo "Refusing unsafe managed Codex target: $aerisun_package_target" >&2
    exit 1
  fi
  aerisun_tmp_file=$(mktemp "$aerisun_managed_release/.serino-package-codex-path.XXXXXX")
  printf '%s\n' "$aerisun_package_codex" >"$aerisun_tmp_file"
  chmod 600 "$aerisun_tmp_file"
  mv -f "$aerisun_tmp_file" "$aerisun_package_target"
  aerisun_tmp_file=''
  chmod 600 "$aerisun_package_target"

  if [ -L "$aerisun_package_launcher" ] || { [ -e "$aerisun_package_launcher" ] && [ ! -f "$aerisun_package_launcher" ]; }; then
    echo "Refusing unsafe managed Codex launcher: $aerisun_package_launcher" >&2
    exit 1
  fi
  aerisun_tmp_file=$(mktemp "$aerisun_managed_release/.codex.XXXXXX")
  cat >"$aerisun_tmp_file" <<'AERISUN_CODEX_PACKAGE_LAUNCHER'
#!/bin/sh
set -eu

aerisun_launcher_dir=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
aerisun_target_file="$aerisun_launcher_dir/serino-package-codex-path"
if [ -L "$aerisun_target_file" ] || [ ! -f "$aerisun_target_file" ] || [ ! -r "$aerisun_target_file" ]; then
  echo 'Managed Codex package target is unavailable.' >&2
  exit 1
fi
IFS= read -r aerisun_package_codex <"$aerisun_target_file"
case "$aerisun_package_codex" in
  /*) ;;
  *)
    echo 'Managed Codex package target is invalid.' >&2
    exit 1
    ;;
esac
if [ ! -f "$aerisun_package_codex" ] || [ ! -x "$aerisun_package_codex" ]; then
  echo 'Managed Codex package target is unavailable.' >&2
  exit 1
fi
exec "$aerisun_package_codex" "$@"
AERISUN_CODEX_PACKAGE_LAUNCHER
  chmod 700 "$aerisun_tmp_file"
  mv -f "$aerisun_tmp_file" "$aerisun_package_launcher"
  aerisun_tmp_file=''
  chmod 700 "$aerisun_package_launcher"

  if [ ! -e "$aerisun_managed_current" ] && [ ! -L "$aerisun_managed_current" ]; then
    ln -s 'releases/serino-package-manager' "$aerisun_managed_current"
  fi
fi

aerisun_daemon_action='start'
aerisun_daemon_running=0
if codex app-server daemon version >/dev/null 2>&1; then
  aerisun_daemon_running=1
  aerisun_daemon_action='restart'
fi
aerisun_daemon_pid_file="$aerisun_codex_home/app-server-daemon/app-server.pid"
if [ -L "$aerisun_daemon_pid_file" ] || { [ -e "$aerisun_daemon_pid_file" ] && [ ! -f "$aerisun_daemon_pid_file" ]; }; then
  echo "Refusing unsafe Codex daemon state: $aerisun_daemon_pid_file" >&2
  exit 1
fi

if [ "$aerisun_daemon_running" = '1' ] && [ ! -f "$aerisun_daemon_pid_file" ]; then
  aerisun_control_socket="$aerisun_codex_home/app-server-control/app-server-control.sock"
  if [ -L "$aerisun_control_socket" ] || [ ! -S "$aerisun_control_socket" ]; then
    echo "Refusing unsafe Codex control socket: $aerisun_control_socket" >&2
    exit 1
  fi

  aerisun_socket_owners=''
  if command -v lsof >/dev/null 2>&1; then
    aerisun_socket_owners=$(lsof -t -- "$aerisun_control_socket" 2>/dev/null || :)
  elif command -v fuser >/dev/null 2>&1; then
    aerisun_socket_owners=$(fuser "$aerisun_control_socket" 2>/dev/null || :)
  else
    echo 'Unable to identify the existing Codex daemon safely.' >&2
    exit 1
  fi
  set -- $aerisun_socket_owners
  if [ "$#" -ne 1 ]; then
    echo 'Unable to identify exactly one existing Codex daemon.' >&2
    exit 1
  fi
  aerisun_daemon_pid=$1
  case "$aerisun_daemon_pid" in
    ''|*[!0-9]*)
      echo 'Invalid Codex daemon process identifier.' >&2
      exit 1
      ;;
  esac
  if [ "$aerisun_daemon_pid" -le 1 ]; then
    echo 'Invalid Codex daemon process identifier.' >&2
    exit 1
  fi

  aerisun_current_uid=$(id -u)
  aerisun_daemon_uid=$(ps -p "$aerisun_daemon_pid" -o uid= 2>/dev/null | tr -d '[:space:]')
  aerisun_daemon_command=$(ps -p "$aerisun_daemon_pid" -o command= 2>/dev/null || :)
  aerisun_expected_listener="unix://$aerisun_control_socket"
  if [ "$aerisun_daemon_uid" != "$aerisun_current_uid" ]; then
    echo 'Refusing to stop a Codex daemon owned by another user.' >&2
    exit 1
  fi
  case "$aerisun_daemon_command" in
    *codex*app-server*"--listen unix://" | \
      *codex*app-server*"--listen=unix://" | \
      *codex*app-server*"--listen $aerisun_expected_listener" | \
      *codex*app-server*"--listen=$aerisun_expected_listener") ;;
    *)
      echo 'Refusing to stop an unrecognized control-socket owner.' >&2
      exit 1
      ;;
  esac

  aerisun_daemon_is_active() {
    if ! kill -0 "$aerisun_daemon_pid" 2>/dev/null; then
      return 1
    fi
    aerisun_daemon_state=$(ps -p "$aerisun_daemon_pid" -o state= 2>/dev/null | tr -d '[:space:]')
    case "$aerisun_daemon_state" in
      ''|Z*) return 1 ;;
      *) return 0 ;;
    esac
  }

  kill -TERM "$aerisun_daemon_pid"
  aerisun_stop_attempt=0
  while aerisun_daemon_is_active && [ "$aerisun_stop_attempt" -lt 15 ]; do
    aerisun_stop_attempt=$((aerisun_stop_attempt + 1))
    sleep 1
  done
  if aerisun_daemon_is_active; then
    kill -TERM "$aerisun_daemon_pid"
    aerisun_stop_attempt=0
    while aerisun_daemon_is_active && [ "$aerisun_stop_attempt" -lt 5 ]; do
      aerisun_stop_attempt=$((aerisun_stop_attempt + 1))
      sleep 1
    done
  fi
  if aerisun_daemon_is_active; then
    echo 'The existing Codex daemon did not stop.' >&2
    exit 1
  fi
  aerisun_daemon_running=0
  aerisun_daemon_action='start'
fi

if ! codex app-server daemon "$aerisun_daemon_action" --help >/dev/null 2>&1; then
  echo "Update Codex CLI: app-server daemon $aerisun_daemon_action support is required." >&2
  exit 1
fi

if [ -L "$aerisun_secret_dir" ] || { [ -e "$aerisun_secret_dir" ] && [ ! -d "$aerisun_secret_dir" ]; }; then
  echo "Refusing unsafe Aerisun MCP credential directory: $aerisun_secret_dir" >&2
  exit 1
fi
if [ ! -d "$aerisun_secret_dir" ]; then
  echo 'Aerisun MCP credential is unavailable. Re-run the site installer.' >&2
  exit 1
fi
if [ -L "$aerisun_secret_file" ] || { [ -e "$aerisun_secret_file" ] && [ ! -f "$aerisun_secret_file" ]; }; then
  echo "Refusing unsafe Aerisun MCP credential file: $aerisun_secret_file" >&2
  exit 1
fi
if [ ! -r "$aerisun_secret_file" ]; then
  echo 'Aerisun MCP credential is unavailable. Re-run the site installer.' >&2
  exit 1
fi

if ! IFS= read -r aerisun_api_key <"$aerisun_secret_file"; then
  echo 'Aerisun MCP credential is unavailable. Re-run the site installer.' >&2
  exit 1
fi
case "$aerisun_api_key" in
  ''|*[!A-Za-z0-9_-]*)
    unset aerisun_api_key
    echo 'Aerisun MCP credential is invalid. Re-run the site installer.' >&2
    exit 1
    ;;
esac
if [ "${#aerisun_api_key}" -lt 32 ]; then
  unset aerisun_api_key
  echo 'Aerisun MCP credential is invalid. Re-run the site installer.' >&2
  exit 1
fi

if ! AERISUN_MCP_API_KEY="$aerisun_api_key" codex app-server daemon "$aerisun_daemon_action"; then
  unset aerisun_api_key
  echo "Unable to $aerisun_daemon_action the Codex app-server daemon." >&2
  exit 1
fi
unset aerisun_api_key aerisun_daemon_action AERISUN_MCP_API_KEY
"""


def _local_executable_install_shell(
    *,
    executable_name: str,
    variable_name: str,
    unsafe_label: str,
    heredoc_marker: str,
    script: str,
) -> str:
    executable_script = script.rstrip()
    return f"""aerisun_local_bin="$HOME/.local/bin"
{variable_name}="$aerisun_local_bin/{executable_name}"

if [ -L "$aerisun_local_bin" ] || {{ [ -e "$aerisun_local_bin" ] && [ ! -d "$aerisun_local_bin" ]; }}; then
  echo "Refusing unsafe local executable directory: $aerisun_local_bin" >&2
  exit 1
fi
mkdir -p "$aerisun_local_bin"

if [ -L "${variable_name}" ] || {{ [ -e "${variable_name}" ] && [ ! -f "${variable_name}" ]; }}; then
  echo "Refusing unsafe {unsafe_label}: ${variable_name}" >&2
  exit 1
fi
aerisun_tmp_file=$(mktemp "$aerisun_local_bin/.{executable_name}.XXXXXX")
cat >"$aerisun_tmp_file" <<'{heredoc_marker}'
{executable_script}
{heredoc_marker}
chmod 700 "$aerisun_tmp_file"
mv -f "$aerisun_tmp_file" "${variable_name}"
aerisun_tmp_file=''
chmod 700 "${variable_name}"
"""


def _local_key_updater_install_shell() -> str:
    return _local_executable_install_shell(
        executable_name=KEY_UPDATER_NAME,
        variable_name="aerisun_key_updater",
        unsafe_label="local key updater",
        heredoc_marker="AERISUN_LOCAL_KEY_UPDATER",
        script=build_mcp_key_update_script(),
    )


def _claude_credential_shell() -> str:
    return r"""aerisun_headers_helper="$aerisun_secret_dir/mcp-headers"
if [ -L "$aerisun_headers_helper" ] || { [ -e "$aerisun_headers_helper" ] && [ ! -f "$aerisun_headers_helper" ]; }; then
  echo "Refusing unsafe Claude headers helper: $aerisun_headers_helper" >&2
  exit 1
fi
aerisun_tmp_file=$(mktemp "$aerisun_secret_dir/.mcp-headers.XXXXXX")
cat >"$aerisun_tmp_file" <<'AERISUN_HEADERS_HELPER'
#!/bin/sh
set -eu

aerisun_helper_dir=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
aerisun_helper_secret="$aerisun_helper_dir/mcp-api-key"
if [ -L "$aerisun_helper_secret" ] || [ ! -f "$aerisun_helper_secret" ]; then
  echo 'Aerisun MCP credential is unavailable. Re-run the site installer.' >&2
  exit 1
fi
IFS= read -r aerisun_helper_key <"$aerisun_helper_secret"
case "$aerisun_helper_key" in
  ''|*[!A-Za-z0-9_-]*)
    echo 'Aerisun MCP credential is invalid. Re-run the site installer.' >&2
    exit 1
    ;;
esac
printf '{"Authorization":"Bearer %s"}\n' "$aerisun_helper_key"
unset aerisun_helper_key
AERISUN_HEADERS_HELPER
chmod 700 "$aerisun_tmp_file"
mv -f "$aerisun_tmp_file" "$aerisun_headers_helper"
aerisun_tmp_file=''
chmod 700 "$aerisun_headers_helper"

unset AERISUN_MCP_API_KEY aerisun_api_key
"""


def build_claude_marketplace(site_url: str) -> dict[str, object]:
    base_url = _site_base_url(site_url)
    return {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
        "name": MARKETPLACE_NAME,
        "description": "Install Aerisun MCP 2026-07-28 and its focused skills.",
        "owner": {
            "name": "Aerisun",
        },
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "description": "Use this Aerisun site's scoped MCP tools through focused read and write skills.",
                "author": {
                    "name": "Aerisun",
                    "url": "https://github.com/Aerisun",
                },
                "homepage": _url(base_url, "/mcp/install"),
                "repository": REPOSITORY_URL,
                "license": "MIT",
                "category": "productivity",
                "source": {
                    "source": "git-subdir",
                    "url": REPOSITORY_URL,
                    "path": "plugins/aerisun-mcp",
                    "ref": "main",
                },
            }
        ],
    }


def build_codex_install_script(site_url: str) -> str:
    base_url = _site_base_url(site_url)
    mcp_url = shlex.quote(_url(base_url, "/api/mcp/"))
    repository_url = shlex.quote(REPOSITORY_URL)
    return f"""#!/bin/sh
set -eu

command -v codex >/dev/null 2>&1 || {{ echo "Codex CLI is required." >&2; exit 1; }}
{_credential_bootstrap_shell()}
{_codex_credential_shell()}

marketplaces="$(codex plugin marketplace list --json)" || {{
  echo "Update Codex CLI: plugin marketplace support is required." >&2
  exit 1
}}
codex mcp add --help | grep -Fq -- '--bearer-token-env-var' || {{
  echo "Update Codex CLI: Bearer-token environment variables are required." >&2
  exit 1
}}

if printf '%s\\n' "$marketplaces" | grep -Eq '\"name\"[[:space:]]*:[[:space:]]*\"{MARKETPLACE_NAME}\"'; then
  printf '%s\\n' "$marketplaces" | grep -Fq -- {repository_url} || {{
    echo "The '{MARKETPLACE_NAME}' Codex marketplace name is already bound to another source." >&2
    exit 1
  }}
  codex plugin marketplace upgrade {MARKETPLACE_NAME}
else
  codex plugin marketplace add {repository_url} --sparse .agents/plugins --sparse plugins/{PLUGIN_NAME}
fi
codex plugin add {PLUGIN_NAME}@{MARKETPLACE_NAME}

if codex mcp get {PLUGIN_NAME} >/dev/null 2>&1; then
  codex mcp remove {PLUGIN_NAME}
fi
codex mcp add {PLUGIN_NAME} --url {mcp_url} --bearer-token-env-var AERISUN_MCP_API_KEY
{_local_key_updater_install_shell()}
{_codex_daemon_reload_shell()}

printf '%s\\n' 'Aerisun MCP and skills installed. Codex reconnected automatically.'
"""


def build_claude_install_script(site_url: str) -> str:
    base_url = _site_base_url(site_url)
    marketplace_url = shlex.quote(_url(base_url, "/mcp/install/claude-marketplace.json"))
    mcp_url = shlex.quote(_url(base_url, "/api/mcp/"))
    return f"""#!/bin/sh
set -eu

command -v claude >/dev/null 2>&1 || {{ echo "Claude Code is required." >&2; exit 1; }}
{_credential_bootstrap_shell()}
{_claude_credential_shell()}

CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE="${{CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE:-1}}"
export CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE

marketplace_url={marketplace_url}
marketplaces="$(claude plugin marketplace list --json)" || {{
  echo "Update Claude Code: plugin marketplace support is required." >&2
  exit 1
}}
plugins="$(claude plugin list --json)" || {{
  echo "Unable to inspect installed Claude Code plugins." >&2
  exit 1
}}

if printf '%s\\n' "$marketplaces" | grep -Eq '\"name\"[[:space:]]*:[[:space:]]*\"{MARKETPLACE_NAME}\"'; then
  if printf '%s\\n' "$marketplaces" | grep -Fq -- "$marketplace_url"; then
    claude plugin marketplace update {MARKETPLACE_NAME}
  else
    claude plugin marketplace remove {MARKETPLACE_NAME} --scope user
    claude plugin marketplace add "$marketplace_url" --scope user
    plugins='[]'
  fi
else
  claude plugin marketplace add "$marketplace_url" --scope user
fi

if printf '%s\\n' "$plugins" | grep -Eq '{PLUGIN_NAME}@{MARKETPLACE_NAME}|\"name\"[[:space:]]*:[[:space:]]*\"{PLUGIN_NAME}\"'; then
  claude plugin update {PLUGIN_NAME}@{MARKETPLACE_NAME} --scope user
else
  claude plugin install {PLUGIN_NAME}@{MARKETPLACE_NAME} --scope user
fi

aerisun_headers_helper_json=$(printf '%s' "$aerisun_headers_helper" | sed 's/\\\\/\\\\\\\\/g; s/"/\\\\"/g')
aerisun_mcp_json=$(printf '{{"type":"http","url":"%s","headersHelper":"%s"}}' {mcp_url} "$aerisun_headers_helper_json")
claude mcp remove {PLUGIN_NAME} --scope user >/dev/null 2>&1 || :
claude mcp add-json --scope user {PLUGIN_NAME} "$aerisun_mcp_json"
{_local_key_updater_install_shell()}

printf '%s\\n' 'Aerisun MCP and skills installed. Restart Claude Code to load them.'
"""


def build_mcp_install_manifest(site_url: str) -> dict[str, object]:
    base_url = _site_base_url(site_url)
    codex_installer = _url(base_url, "/mcp/install/codex.sh")
    claude_installer = _url(base_url, "/mcp/install/claude.sh")
    claude_marketplace = _url(base_url, "/mcp/install/claude-marketplace.json")
    return {
        "schema_version": INSTALL_SCHEMA_VERSION,
        "name": "Aerisun MCP",
        "plugin_version": PLUGIN_VERSION,
        "protocol_version": MCP_PROTOCOL_VERSION,
        "mcp_endpoint": _url(base_url, "/api/mcp/"),
        "usage_url": _url(base_url, "/api/agent/usage"),
        "credential_input": {
            "mode": "interactive_hidden_prompt",
            "storage": "client_private",
            "automation_environment": "AERISUN_MCP_API_KEY",
            "update_command": KEY_UPDATER_COMMAND,
        },
        "skills": [
            "aerisun-mcp-bootstrap",
            "aerisun-mcp-readonly",
            "aerisun-mcp-guarded-write",
        ],
        "clients": {
            "codex": {
                "install_url": codex_installer,
                "command": f"curl -fsSL {shlex.quote(codex_installer)} | sh",
                "marketplace": f"{PLUGIN_NAME}@{MARKETPLACE_NAME}",
            },
            "claude_code": {
                "install_url": claude_installer,
                "command": f"curl -fsSL {shlex.quote(claude_installer)} | sh",
                "marketplace_url": claude_marketplace,
                "plugin": f"{PLUGIN_NAME}@{MARKETPLACE_NAME}",
            },
        },
    }
