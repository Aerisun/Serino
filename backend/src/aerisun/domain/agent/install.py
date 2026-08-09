from __future__ import annotations

import shlex
from urllib.parse import urlsplit

INSTALL_SCHEMA_VERSION = "2026-08-09-install-v4"
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
    return f"""aerisun_codex_home="${{CODEX_HOME:-$HOME/.codex}}"
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

printf '%s\\n' 'Serino MCP API Key updated. Start a new client session if needed.'
"""


def _local_key_updater_install_shell() -> str:
    updater_script = build_mcp_key_update_script().rstrip()
    return f"""aerisun_local_bin="$HOME/.local/bin"
aerisun_key_updater="$aerisun_local_bin/{KEY_UPDATER_NAME}"

if [ -L "$aerisun_local_bin" ] || {{ [ -e "$aerisun_local_bin" ] && [ ! -d "$aerisun_local_bin" ]; }}; then
  echo "Refusing unsafe local executable directory: $aerisun_local_bin" >&2
  exit 1
fi
mkdir -p "$aerisun_local_bin"

if [ -L "$aerisun_key_updater" ] || {{ [ -e "$aerisun_key_updater" ] && [ ! -f "$aerisun_key_updater" ]; }}; then
  echo "Refusing unsafe local key updater: $aerisun_key_updater" >&2
  exit 1
fi
aerisun_tmp_file=$(mktemp "$aerisun_local_bin/.serino-mcp-key.XXXXXX")
cat >"$aerisun_tmp_file" <<'AERISUN_LOCAL_KEY_UPDATER'
{updater_script}
AERISUN_LOCAL_KEY_UPDATER
chmod 700 "$aerisun_tmp_file"
mv -f "$aerisun_tmp_file" "$aerisun_key_updater"
aerisun_tmp_file=''
chmod 700 "$aerisun_key_updater"
"""


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

printf '%s\\n' 'Aerisun MCP and skills installed. Start a new Codex task to load them.'
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
