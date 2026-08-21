from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def read_project_file(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def run_installer_bash(script: str) -> str:
    completed = subprocess.run(
        ["bash", "-lc", script],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def run_installer_bash_result(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", script],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_installer_ip_helpers_prefer_ipv4_and_bracket_ipv6_urls():
    output = (
        run_installer_bash(
            """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/tui.sh

curl() {
  case " $* " in
    *" -4 "*)
      return 1
      ;;
    *)
      return 1
      ;;
  esac
}

ip() {
  if [[ "${1:-}" == "-o" && "${2:-}" == "-4" ]]; then
    cat <<'EOF'
2: eth0    inet 10.129.246.67/24 brd 10.129.246.255 scope global dynamic eth0
3: docker0 inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
EOF
    return 0
  fi
  if [[ "${1:-}" == "-o" && "${2:-}" == "-6" ]]; then
    cat <<'EOF'
2: eth0    inet6 2001:db8::20/64 scope global dynamic
EOF
    return 0
  fi
  return 1
}

hostname() {
  if [[ "${1:-}" == "-I" ]]; then
    printf '2001:db8::30 10.0.0.2 198.51.100.5'
    return 0
  fi
  return 1
}

printf '%s\\n' "$(guess_host_for_ip_mode)"
printf '%s\\n' "$(normalize_host_input 'http://[2001:db8::40]/demo')"
printf '%s\\n' "$(build_url_from_host 'http' '2001:db8::40')"
build_runtime_configuration ip '2001:db8::40' 'registry.example.com/ns' '0.1.19'
printf '%s\\n' "${AERISUN_DOMAIN_VALUE}"
printf '%s\\n' "${AERISUN_SITE_URL_VALUE}"
printf '%s\\n' "${AERISUN_WALINE_SERVER_URL_VALUE}"
printf '%s\\n' "${AERISUN_WALINE_SECURE_DOMAINS_VALUE}"
"""
        )
        .strip()
        .splitlines()
    )

    assert output == [
        "10.129.246.67",
        "2001:db8::40",
        "http://[2001:db8::40]",
        "http://[2001:db8::40]",
        "http://[2001:db8::40]",
        "http://[2001:db8::40]/waline",
        "2001:db8::40",
    ]


def test_guess_host_for_ip_mode_prefers_non_proxy_public_ipv4():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/tui.sh

curl() {
  if [[ " $* " == *" --noproxy "* ]]; then
    printf '8.8.8.8'
    return 0
  fi
  printf '1.1.1.1'
  return 0
}

printf '%s\\n' "$(guess_host_for_ip_mode)"
"""
    ).strip()

    assert output == "8.8.8.8"


def test_guess_host_for_ip_mode_falls_back_to_second_public_probe_before_private_ipv4():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/tui.sh

curl() {
  case "$*" in
    *"https://api.ipify.org"*)
      return 1
      ;;
    *"https://ipv4.icanhazip.com"*)
      printf '8.8.4.4\\n'
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

list_local_ipv4_candidates() {
  printf '10.2.4.17\\n'
}

printf '%s\\n' "$(guess_host_for_ip_mode)"
"""
    ).strip()

    assert output == "8.8.4.4"


def test_public_ipv4_probe_sanitizes_dirty_outputs_and_prefers_majority():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/tui.sh

curl() {
  case "$*" in
    *"https://api.ipify.org"*)
      printf 'not an ip\\n'
      return 0
      ;;
    *"https://ipv4.icanhazip.com"*)
      printf '101.42.135.92\\r\\n'
      return 0
      ;;
    *"https://ifconfig.me/ip"*)
      printf '8.8.8.8\\n'
      return 0
      ;;
    *"https://api.ip.sb/ip"*)
      printf '101.42.135.92'
      return 0
      ;;
    *"https://4.ipw.cn"*)
      printf '<html>bad gateway</html>'
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

printf '%s\\n' "$(detect_public_ipv4_without_proxy)"
"""
    ).strip()

    assert output == "101.42.135.92"


def test_public_ipv4_probe_returns_empty_when_only_proxy_or_invalid_results_exist():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/tui.sh

curl() {
  if [[ " $* " == *" --noproxy "* ]]; then
    printf '10.2.4.17\\n'
    return 0
  fi
  printf '101.42.135.92\\n'
  return 0
}

printf '<%s>\\n' "$(detect_public_ipv4_without_proxy)"
"""
    ).strip()

    assert output == "<>"


def test_private_ip_mode_prefers_local_ipv4_over_nat_exit_ipv4():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/tui.sh

AERISUN_INSTALL_IP_MODE='private'

curl() {
  if [[ " $* " == *" --noproxy "* ]]; then
    printf '115.27.214.28'
    return 0
  fi
  return 1
}

list_local_ipv4_candidates() {
  printf '10.129.241.9\\n'
}

printf '%s\\n' "$(guess_host_for_ip_mode)"
"""
    ).strip()

    assert output == "10.129.241.9"


def test_private_ip_mode_does_not_default_to_local_public_ipv4():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/tui.sh

AERISUN_INSTALL_IP_MODE='private'

list_local_ipv4_candidates() {
  printf '8.8.8.8\\n10.129.241.9\\n'
}

printf '<%s>\\n' "$(guess_host_for_ip_mode)"
"""
    ).strip()

    assert output == "<10.129.241.9>"


def test_local_ip_candidates_ignore_hostname_fallback_when_ip_command_finds_primary_nic():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/tui.sh

ip() {
  if [[ "${1:-}" == "-o" && "${2:-}" == "-4" ]]; then
    cat <<'EOF'
2: eth0    inet 10.2.4.17/22 metric 100 brd 10.2.7.255 scope global eth0
4: br-915aa694f86a    inet 172.18.0.1/16 brd 172.18.255.255 scope global br-915aa694f86a
5: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
6: tailscale0    inet 100.102.9.79/32 scope global tailscale0
EOF
    return 0
  fi
  return 1
}

hostname() {
  if [[ "${1:-}" == "-I" ]]; then
    printf '10.2.4.17 172.18.0.1 172.17.0.1 100.102.9.79'
    return 0
  fi
  return 1
}

list_local_ipv4_candidates
"""
    ).strip()

    assert output == "10.2.4.17"


def test_public_ip_mode_prefers_public_probe_for_cloud_eip_style_hosts():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/tui.sh

AERISUN_INSTALL_IP_MODE='public'

curl() {
  if [[ " $* " == *" --noproxy "* ]]; then
    printf '115.27.214.28'
    return 0
  fi
  return 1
}

list_local_ipv4_candidates() {
  printf '10.129.241.9\\n'
}

printf '%s\\n' "$(guess_host_for_ip_mode)"
"""
    ).strip()

    assert output == "115.27.214.28"


def test_ip_mode_prompt_asks_for_public_or_private_ipv4_type():
    tui = read_project_file("installer/lib/tui.sh")

    assert "IPv4 模式（下一步选择公网或内网）" in tui
    assert "选择 IPv4 类型" in tui
    assert "公网 IPv4（腾讯云、阿里云等云服务器厂商）" in tui
    assert "内网 IPv4（例如校园网中的 clab）" in tui
    assert "请输入外部用户访问这台服务器用的公网 IPv4（云服务器控制台里的公网 IP）" in tui
    assert "请输入内网里访问这台服务器用的 IPv4（通常是 hostname -I 里看到的 10.x/172.x/192.168.x）" in tui
    assert "没有出现在本机网卡地址里" in tui
    assert "请取消，返回选择内网访问" in tui
    assert "访问范围：%s" in tui


def test_validate_ip_mode_host_respects_public_and_private_ipv4_type():
    output = (
        run_installer_bash(
            """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/tui.sh

list_local_ipv4_candidates() {
  printf '10.0.0.8\\n'
}

detect_public_ipv4_without_proxy() {
  printf '8.8.8.8'
}

detect_public_ipv4_with_proxy() {
  printf '1.1.1.1'
}

if validate_ip_mode_host 'example.com' >/dev/null; then
  printf 'unexpected-domain-ok\\n'
else
  printf '%s\\n' "${AERISUN_INSTALL_HOST_VALIDATION_ERROR}"
fi

AERISUN_INSTALL_IP_MODE='private'
if validate_ip_mode_host '10.0.0.8' >/dev/null; then
  printf 'private-local-ok\\n'
else
  printf '%s\\n' "${AERISUN_INSTALL_HOST_VALIDATION_ERROR}"
fi

AERISUN_INSTALL_IP_MODE='public'
if validate_ip_mode_host '10.0.0.8' >/dev/null; then
  printf 'unexpected-private-as-public-ok\\n'
else
  printf '%s\\n' "${AERISUN_INSTALL_HOST_VALIDATION_ERROR}"
fi

if validate_ip_mode_host '1.1.1.1' >/dev/null; then
  printf 'unexpected-proxy-ok\\n'
else
  printf '%s\\n' "${AERISUN_INSTALL_HOST_VALIDATION_ERROR}"
fi

public_value="$(validate_ip_mode_host '8.8.8.8')"
public_status="$?"
printf '%s\\n' "${public_value}"
printf '%s\\n' "${public_status}"
"""
        )
        .strip()
        .splitlines()
    )

    assert output == [
        "IP 模式仅支持这台服务器的真实 IPv4 地址，请不要填写域名、IPv6 或主机名。",
        "private-local-ok",
        "你选择了公网 IPv4，但填写的是本机内网 IPv4。腾讯云、阿里云等云服务器请填写绑定到该机器的公网 IPv4 / EIP；如果只是校园网内网访问，请返回选择内网 IPv4。",
        "当前填写的 IPv4 看起来是代理出口地址，不是这台服务器的公网 IPv4 / EIP。请关闭代理后重试，或确认云厂商控制台里绑定到本机的公网 IPv4。",
        "8.8.8.8",
        "0",
    ]


def test_public_ip_mapping_confirmation_only_needed_for_public_ip_not_on_local_nic():
    output = (
        run_installer_bash(
            """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/tui.sh

AERISUN_INSTALL_ACCESS_MODE='ip'
AERISUN_INSTALL_IP_MODE='public'

list_local_ipv4_candidates() {
  printf '8.8.8.8\\n10.0.0.8\\n'
}

if public_ip_requires_mapping_confirmation '8.8.8.8'; then
  printf 'unexpected-local-public-confirm\\n'
else
  printf 'local-public-no-confirm\\n'
fi

if public_ip_requires_mapping_confirmation '1.1.1.1'; then
  printf 'remote-public-confirm\\n'
else
  printf 'unexpected-remote-public-no-confirm\\n'
fi

printf '%s\\n' "$(ip_mode_label public)"
printf '%s\\n' "$(ip_mode_label private)"
"""
        )
        .strip()
        .splitlines()
    )

    assert output == [
        "local-public-no-confirm",
        "remote-public-confirm",
        "公网访问",
        "内网访问",
    ]


def test_domain_preflight_ignores_proxy_public_ip_candidates_by_default():
    output = (
        run_installer_bash(
            """
source installer/lib/common.sh
source installer/lib/docker.sh

resolve_host_ips() {
  printf '203.0.113.10\\n'
}

list_local_ip_candidates() {
  printf '10.0.0.8\\n'
}

curl() {
  if [[ " $* " == *" --noproxy "* ]]; then
    return 1
  fi
  printf '203.0.113.10\\n'
  return 0
}

port_in_use() {
  return 1
}

preflight_domain_installation 'example.com'
printf 'status=%s\\n' "$?"
"""
        )
        .strip()
        .splitlines()
    )

    assert output == ["status=1"]


def test_domain_preflight_public_ip_probe_uses_direct_ipv4_and_ignores_proxy_by_default():
    output = (
        run_installer_bash(
            """
source installer/lib/common.sh
source installer/lib/docker.sh

curl() {
  if [[ " $* " == *" --noproxy "* ]]; then
    case "$*" in
      *"https://api.ipify.org"*)
        printf 'not an ip\\n'
        return 0
        ;;
      *"https://ipv4.icanhazip.com"*)
        printf '101.42.135.92\\r\\n'
        return 0
        ;;
      *"https://ifconfig.me/ip"*)
        printf '8.8.8.8\\n'
        return 0
        ;;
      *"https://api.ip.sb/ip"*)
        printf '101.42.135.92'
        return 0
        ;;
      *)
        return 1
        ;;
    esac
  fi
  printf '1.1.1.1\\n'
  return 0
}

detect_public_ip_candidates
"""
        )
        .strip()
        .splitlines()
    )

    assert output == ["101.42.135.92"]


def test_domain_preflight_can_include_proxy_public_ip_candidates_when_explicitly_enabled():
    output = (
        run_installer_bash(
            """
source installer/lib/common.sh
source installer/lib/docker.sh

AERISUN_INSTALL_ALLOW_PROXY_IP_CHECK=true

resolve_host_ips() {
  printf '1.1.1.1\\n'
}

list_local_ip_candidates() {
  printf '10.0.0.8\\n'
}

curl() {
  if [[ " $* " == *" --noproxy "* ]]; then
    return 1
  fi
  printf '1.1.1.1\\n'
  return 0
}

port_in_use() {
  return 1
}

preflight_domain_installation 'example.com'
printf 'status=%s\\n' "$?"
"""
        )
        .strip()
        .splitlines()
    )

    assert output == ["status=0"]


def test_settings_normalize_runtime_paths_under_store_dir():
    from aerisun.core.settings import (
        PROJECT_ROOT as SETTINGS_PROJECT_ROOT,
    )
    from aerisun.core.settings import (
        Settings,
    )

    store_dir = Path("/srv/aerisun/store")
    settings = Settings(
        _env_file=None,
        store_dir=store_dir,
        data_dir=SETTINGS_PROJECT_ROOT / ".store",
        media_dir=SETTINGS_PROJECT_ROOT / ".store" / "media",
        secrets_dir=SETTINGS_PROJECT_ROOT / ".store" / "secrets",
        db_path=SETTINGS_PROJECT_ROOT / ".store" / "aerisun.db",
        waline_db_path=SETTINGS_PROJECT_ROOT / ".store" / "waline.db",
        workflow_db_path=SETTINGS_PROJECT_ROOT / ".store" / "langgraph.db",
        backup_sync_tmp_dir=SETTINGS_PROJECT_ROOT / ".store" / ".backup-sync-tmp",
    )

    assert settings.data_dir == store_dir
    assert settings.media_dir == store_dir / "media"
    assert settings.secrets_dir == store_dir / "secrets"
    assert settings.db_path == store_dir / "aerisun.db"
    assert settings.waline_db_path == store_dir / "waline.db"
    assert settings.workflow_db_path == store_dir / "langgraph.db"
    assert settings.backup_sync_tmp_dir == store_dir / ".backup-sync-tmp"


def test_sercli_status_uses_readyz_fallback_and_release_summary():
    output = run_installer_bash(
        """
source installer/bin/sercli

ensure_supported_existing_installation() {
  :
}

path_is_file() {
  return 0
}

load_env_file() {
  AERISUN_SITE_URL="https://example.test"
  AERISUN_INSTALL_CHANNEL="stable"
  AERISUN_IMAGE_REGISTRY="registry.example.com/serino"
  AERISUN_IMAGE_TAG="v9.9.9"
  AERISUN_RELEASE_VERSION="v9.9.9"
  AERISUN_PORT="18000"
  unset AERISUN_HEALTHCHECK_PATH
}

run_as_root() {
  if [[ "${1:-}" == "systemctl" && "${2:-}" == "is-active" ]]; then
    printf 'active\\n'
    return 0
  fi
  if [[ "${1:-}" == "systemctl" && "${2:-}" == "is-enabled" ]]; then
    printf 'enabled\\n'
    return 0
  fi
  "$@"
}

compose() {
  printf 'compose:%s\\n' "$*"
}

curl() {
  SERCLI_CURL_ARGS="$*"
  return 0
}

cmd_status
printf 'curl:%s\\n' "${SERCLI_CURL_ARGS}"
"""
    )

    assert "Serino 状态" in output
    assert "发布版本" in output and "v9.9.9" in output
    assert "健康检查" in output and "http://127.0.0.1:18000/api/v1/site/readyz" in output
    assert "后端就绪" in output and "正常" in output
    assert "容器服务" in output
    assert "compose:ps" in output
    assert (
        "curl:--noproxy * --fail --silent --show-error --connect-timeout 5 --max-time 10 http://127.0.0.1:18000/api/v1/site/readyz"
        in output
    )


def test_sercli_version_prints_human_readable_summary():
    output = run_installer_bash(
        """
source installer/bin/sercli

path_is_file() {
  return 0
}

load_env_file() {
  AERISUN_INSTALL_CHANNEL='stable'
  AERISUN_IMAGE_REGISTRY='registry.example.com/serino'
  AERISUN_IMAGE_TAG='v9.9.9'
  AERISUN_RELEASE_VERSION='v9.9.9'
}

cmd_version
"""
    )

    assert "Serino 版本" in output
    assert "发布版本" in output and "v9.9.9" in output
    assert "发布渠道" in output and "stable" in output
    assert "镜像版本" in output and "registry.example.com/serino:v9.9.9" in output
    assert "安装器目录" in output
    assert "sercli 路径" in output


def test_validate_release_compose_configuration_accepts_env_urls_without_install_value_vars():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/docker.sh

AERISUN_APP_ROOT='/tmp/serino-app'
AERISUN_IMAGE_REGISTRY='registry.example.com/serino'
AERISUN_API_IMAGE_NAME='serino-api'
AERISUN_WEB_IMAGE_NAME='serino-web'
AERISUN_WALINE_IMAGE_NAME='serino-waline'
AERISUN_IMAGE_TAG='v9.9.9'
AERISUN_SITE_URL='https://example.test'
AERISUN_WALINE_SERVER_URL='https://example.test/waline'
AERISUN_RENDERED_COMPOSE_FILE='/tmp/serino-runtime.yml'

run_as_root() {
  "$@"
}

make_root_temp_file_in_dir() {
  mktemp /tmp/serino-compose.XXXXXX.yml
}

render_release_compose_configuration() {
  cat > "$1" <<'EOF'
services:
  api:
    image: registry.example.com/serino/serino-api:v9.9.9
    environment:
      AERISUN_SITE_URL: https://example.test
      AERISUN_WALINE_SERVER_URL: https://example.test/waline
  caddy:
    image: registry.example.com/serino/serino-web:v9.9.9
  waline:
    image: registry.example.com/serino/serino-waline:v9.9.9
    environment:
      SITE_URL: https://example.test
      SERVER_URL: https://example.test/waline
EOF
}

validate_release_compose_configuration
printf 'ok\\n'
"""
    ).strip()

    assert output == "ok"


def test_sercli_status_supports_json_output_for_automation():
    output = run_installer_bash(
        """
source installer/bin/sercli

ensure_supported_existing_installation() {
  :
}

path_is_file() {
  return 0
}

load_env_file() {
  AERISUN_SITE_URL="https://example.test"
  AERISUN_INSTALL_CHANNEL="stable"
  AERISUN_IMAGE_REGISTRY="registry.example.com/serino"
  AERISUN_IMAGE_TAG="v9.9.9"
  AERISUN_RELEASE_VERSION="v9.9.9"
  AERISUN_PORT="18000"
}

run_as_root() {
  if [[ "${1:-}" == "systemctl" && "${2:-}" == "is-active" ]]; then
    printf 'active\\n'
    return 0
  fi
  if [[ "${1:-}" == "systemctl" && "${2:-}" == "is-enabled" ]]; then
    printf 'enabled\\n'
    return 0
  fi
  "$@"
}

curl() {
  return 0
}

cmd_status --json
"""
    )

    payload = json.loads(output)
    assert payload == {
        "systemd_active": "active",
        "systemd_enabled": "enabled",
        "release_version": "v9.9.9",
        "channel": "stable",
        "site_url": "https://example.test",
        "image_registry": "registry.example.com/serino",
        "image_tag": "v9.9.9",
        "backend_health_url": "http://127.0.0.1:18000/api/v1/site/readyz",
        "backend_health": "ok",
    }


def test_sercli_logs_defaults_to_core_services_and_preserves_options():
    output = run_installer_bash(
        """
source installer/bin/sercli

ensure_supported_existing_installation() {
  :
}

compose() {
  printf '%s\\n' "$*"
}

cmd_logs --follow --since 15m
"""
    ).strip()

    assert output == "logs --tail 120 --follow --since 15m api waline caddy"


def test_sercli_maintenance_lock_only_wraps_destructive_commands():
    output = (
        run_installer_bash(
            """
source installer/bin/sercli

ensure_supported_existing_installation() {
  :
}

sercli_known_runtime_services() {
  printf 'api\\nwaline\\ncaddy\\n'
}

run_with_maintenance_lock() {
  local action="$1"
  local command_path="$2"
  shift 2
  printf 'lock:%s:%s:%s\\n' "${action}" "$(basename "${command_path}")" "$*"
}

cmd_logs --list-services
cmd_upgrade --check
cmd_uninstall --force
"""
        )
        .strip()
        .splitlines()
    )

    assert output == [
        "api",
        "waline",
        "caddy",
        "lock:upgrade:upgrade.sh:--check",
        "lock:uninstall:uninstall.sh:--force",
    ]


def test_sercli_route_commands_use_the_maintenance_lock():
    output = (
        run_installer_bash(
            """
source installer/bin/sercli

run_with_maintenance_lock() {
  local action="$1"
  local command_path="$2"
  shift 2
  printf 'lock:%s:%s:%s\\n' "${action}" "$(basename "${command_path}")" "$*"
}

cmd_route add /files http://127.0.0.1:9000
cmd_route list
cmd_route remove /files
"""
        )
        .strip()
        .splitlines()
    )

    assert output == [
        "lock:route:route.sh:add /files http://127.0.0.1:9000",
        "lock:route:route.sh:list",
        "lock:route:route.sh:remove /files",
    ]


def test_sercli_updater_status_reads_persistent_status(tmp_path: Path):
    status_dir = tmp_path / "data" / "update"
    status_dir.mkdir(parents=True)
    (status_dir / "status.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "state": "available",
                "current_version": "v1.0.0",
                "latest_version": "v1.2.3",
                "channel": "stable",
                "update_available": True,
                "auto_update_supported": True,
                "signature_verified": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = run_installer_bash(
        f"""
source installer/bin/sercli

AERISUN_DATA_DIR='{tmp_path}/data'
cmd_updater status --json
"""
    )

    payload = json.loads(output)
    assert payload["state"] == "available"
    assert payload["latest_version"] == "v1.2.3"


def test_release_manifest_rejects_bundle_sha_mismatch_with_signed_metadata(tmp_path: Path):
    manifest = tmp_path / "manifest.env"
    manifest.write_text(
        "\n".join(
            [
                "AERISUN_INSTALL_CHANNEL=stable",
                "AERISUN_INSTALL_VERSION=v9.9.9",
                "AERISUN_IMAGE_TAG=9.9.9",
                "AERISUN_IMAGE_REGISTRY=registry.example.com/serino",
                "AERISUN_API_IMAGE_NAME=serino-api",
                "AERISUN_WEB_IMAGE_NAME=serino-web",
                "AERISUN_WALINE_IMAGE_NAME=serino-waline",
                f"AERISUN_INSTALL_BUNDLE_SHA256={'b' * 64}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_installer_bash_result(
        f"""
source installer/lib/common.sh
source installer/lib/download.sh

download_release_asset() {{
  cp '{manifest}' "$3"
}}

AERISUN_EXPECTED_INSTALL_BUNDLE_SHA256='{"a" * 64}'
load_release_manifest v9.9.9 '{tmp_path}/resolved.env'
"""
    )

    assert result.returncode != 0
    assert "signed release metadata" in result.stderr


def test_release_manifest_rejects_trusted_public_key_mismatch_with_signed_metadata(tmp_path: Path):
    manifest = tmp_path / "manifest.env"
    manifest.write_text(
        "\n".join(
            [
                "AERISUN_INSTALL_CHANNEL=stable",
                "AERISUN_INSTALL_VERSION=v9.9.9",
                "AERISUN_IMAGE_TAG=9.9.9",
                "AERISUN_IMAGE_REGISTRY=registry.example.com/serino",
                "AERISUN_API_IMAGE_NAME=serino-api",
                "AERISUN_WEB_IMAGE_NAME=serino-web",
                "AERISUN_WALINE_IMAGE_NAME=serino-waline",
                f"AERISUN_INSTALL_BUNDLE_SHA256={'a' * 64}",
                "AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64=QUJDRA==",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_installer_bash_result(
        f"""
source installer/lib/common.sh
source installer/lib/download.sh

download_release_asset() {{
  cp '{manifest}' "$3"
}}

AERISUN_EXPECTED_INSTALL_BUNDLE_SHA256='{"a" * 64}'
AERISUN_EXPECTED_UPDATE_TRUSTED_PUBLIC_KEY_B64='RUZHSA=='
load_release_manifest v9.9.9 '{tmp_path}/resolved.env'
"""
    )

    assert result.returncode != 0
    assert "trusted public key" in result.stderr


def test_updater_check_falls_back_to_legacy_latest_env_for_unsigned_notification(tmp_path: Path):
    output = run_installer_bash(
        f"""
source installer/bin/sercli

AERISUN_DATA_DIR='{tmp_path}/data'
SERINO_LOG_ROOT='{tmp_path}/log'
SERINO_SERVICE_USER="$(command id -un)"
SERINO_SERVICE_GROUP="$(command id -gn)"
AERISUN_RELEASE_VERSION='0.1.60'
AERISUN_IMAGE_TAG='0.1.60'

run_as_root() {{
  if [[ "$1" == chown ]]; then
    return 0
  fi
  "$@"
}}

id() {{
  if [[ "$1" == "-u" ]]; then
    printf '1000\\n'
    return 0
  fi
  command id "$@"
}}

release_metadata_curl() {{
  case "$1" in
    */latest.json)
      return 22
      ;;
    */latest.env)
      printf 'AERISUN_INSTALL_VERSION=v0.1.61\\n'
      return 0
      ;;
    */v0.1.61/aerisun-installer-manifest.env)
      cat <<'EOF'
AERISUN_INSTALL_CHANNEL=stable
AERISUN_INSTALL_VERSION=v0.1.61
AERISUN_IMAGE_TAG=0.1.61
AERISUN_IMAGE_REGISTRY=registry.example.com/serino
AERISUN_API_IMAGE_NAME=serino-api
AERISUN_WEB_IMAGE_NAME=serino-web
AERISUN_WALINE_IMAGE_NAME=serino-waline
AERISUN_INSTALL_BUNDLE_SHA256={"c" * 64}
EOF
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

cmd_updater check >/dev/null
cmd_updater status --json
"""
    )

    payload = json.loads(output)
    assert payload["state"] == "available"
    assert payload["latest_version"] == "v0.1.61"
    assert payload["update_available"] is True
    assert payload["signature_verified"] is False
    assert payload["auto_update_supported"] is False
    assert "legacy latest.env" in payload["auto_update_blocked_reason"]


def test_updater_check_uses_dev_channel_base_url_from_env_file(tmp_path: Path):
    env_file = tmp_path / "serino.env"
    url_log = tmp_path / "urls.log"
    env_file.write_text(
        "\n".join(
            [
                "AERISUN_INSTALL_CHANNEL=dev",
                "AERISUN_INSTALL_BASE_URL=https://updates.example.test/serino/dev",
                "AERISUN_RELEASE_VERSION=0.1.60",
                "AERISUN_IMAGE_TAG=0.1.60",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output = run_installer_bash(
        f"""
source installer/bin/sercli

AERISUN_ENV_FILE='{env_file}'
AERISUN_DATA_DIR='{tmp_path}/data'
SERINO_LOG_ROOT='{tmp_path}/log'
SERINO_SERVICE_USER="$(command id -un)"
SERINO_SERVICE_GROUP="$(command id -gn)"

run_as_root() {{
  if [[ "$1" == chown ]]; then
    return 0
  fi
  "$@"
}}

id() {{
  if [[ "$1" == "-u" ]]; then
    printf '1000\\n'
    return 0
  fi
  command id "$@"
}}

release_metadata_curl() {{
  printf '%s\\n' "$1" >> '{url_log}'
  case "$1" in
    https://updates.example.test/serino/dev/latest.json)
      return 22
      ;;
    https://updates.example.test/serino/dev/latest.env)
      printf 'AERISUN_INSTALL_VERSION=v0.1.61\\n'
      return 0
      ;;
    https://updates.example.test/serino/dev/v0.1.61/aerisun-installer-manifest.env)
      cat <<'EOF'
AERISUN_INSTALL_CHANNEL=dev
AERISUN_INSTALL_VERSION=v0.1.61
AERISUN_IMAGE_TAG=0.1.61
AERISUN_IMAGE_REGISTRY=registry.example.com/serino-dev
AERISUN_API_IMAGE_NAME=serino-dev-api
AERISUN_WEB_IMAGE_NAME=serino-dev-web
AERISUN_WALINE_IMAGE_NAME=serino-dev-waline
AERISUN_INSTALL_BUNDLE_SHA256={"d" * 64}
EOF
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

cmd_updater check >/dev/null
cmd_updater status --json
printf '%s\\n' '--- urls ---'
cat '{url_log}'
"""
    )

    status_text, urls_text = output.split("--- urls ---\n", maxsplit=1)
    payload = json.loads(status_text)
    urls = urls_text.strip().splitlines()
    assert payload["state"] == "available"
    assert payload["channel"] == "dev"
    assert payload["latest_version"] == "v0.1.61"
    assert payload["release"]["manifest_url"] == (
        "https://updates.example.test/serino/dev/v0.1.61/aerisun-installer-manifest.env"
    )
    assert urls == [
        "https://updates.example.test/serino/dev/latest.json",
        "https://updates.example.test/serino/dev/latest.env",
        "https://updates.example.test/serino/dev/v0.1.61/aerisun-installer-manifest.env",
    ]


def test_systemd_updater_units_are_rendered_with_path_and_timer(tmp_path: Path):
    systemd_dir = tmp_path / "systemd"
    systemd_dir.mkdir()

    completed = run_installer_bash(
        f"""
source installer/lib/common.sh

AERISUN_APP_ROOT='{tmp_path}/app'
AERISUN_DATA_DIR='{tmp_path}/data'
AERISUN_RENDERED_COMPOSE_FILE='{tmp_path}/app/docker-compose.runtime.yml'
SERINO_BIN_LINK='{tmp_path}/bin/sercli'
SERINO_SYSTEMD_UNIT='serino.service'
SERINO_SYSTEMD_UPDATER_SERVICE='serino-updater.service'
SERINO_SYSTEMD_UPDATER_TIMER='serino-updater.timer'
SERINO_SYSTEMD_UPDATER_PATH='serino-updater.path'

run_as_root() {{
  if [[ "$1" == install ]]; then
    if [[ "$2" == "-m" ]]; then
      cp "$4" '{systemd_dir}'/"$(basename "$5")"
      return 0
    fi
    "$@"
    return $?
  fi
  if [[ "$1" == systemctl && "$2" == daemon-reload ]]; then
    return 0
  fi
  "$@"
}}

install_proxy_firewall_systemd_dropin() {{ :; }}
install_systemd_units '{PROJECT_ROOT}'
printf '%s\\n' "==service=="
cat '{systemd_dir}/serino-updater.service'
printf '%s\\n' "==timer=="
cat '{systemd_dir}/serino-updater.timer'
printf '%s\\n' "==path=="
cat '{systemd_dir}/serino-updater.path'
"""
    )

    assert "ExecStart=" + str(tmp_path / "bin" / "sercli") + " updater run" in completed
    assert "OnCalendar=hourly" in completed
    assert f"DirectoryNotEmpty={tmp_path}/data/update/requests" in completed


def test_sercli_help_surfaces_common_ops_before_help_footer():
    output = run_installer_bash(
        """
source installer/bin/sercli

cmd_help
"""
    )

    assert output.index("sercli status [--verbose|--json]") < output.index("sercli help")
    assert output.index("sercli doctor [--json]") < output.index("sercli help")
    assert output.index("sercli upgrade [--check] [--ready-timeout SEC] [vX.Y.Z]") < output.index("sercli help")
    assert output.index("sercli uninstall [--force]") < output.index("sercli help")


def test_maintenance_lock_rejects_concurrent_destructive_tasks():
    output = (
        run_installer_bash(
            """
source installer/lib/common.sh

lock_dir="$(mktemp -d)"
SERINO_MAINTENANCE_LOCK_FILE="${lock_dir}/maintenance.lock"

run_as_root() {
  "$@"
}

run_with_maintenance_lock first bash -c 'printf "first\\n"'

exec 9>"${SERINO_MAINTENANCE_LOCK_FILE}"
flock -n 9
( run_with_maintenance_lock second bash -c 'printf "unexpected\\n"' ) || printf 'blocked\\n'
flock -u 9
exec 9>&-
rm -rf "${lock_dir}"
"""
        )
        .strip()
        .splitlines()
    )

    assert output == ["first", "blocked"]


def test_compose_api_task_hides_ephemeral_compose_progress_noise():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/docker.sh

compose() {
  printf '[+] Running 1/1\\n'
  printf ' ✔ Network serino_default Created\\n'
  printf 'Container serino-api-run-abc123 Creating\\n'
  printf 'Container serino-api-run-abc123 Created\\n'
  printf '生产 baseline 已完成。\\n'
}

compose_api_task baseline-prod.sh
"""
    ).strip()

    assert output == "生产 baseline 已完成。"


def test_compose_api_task_hides_ansi_wrapped_ephemeral_compose_progress_noise():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/docker.sh

compose() {
  printf ' \033[32mNetwork serino_default Creating\033[0m\\n'
  printf ' \033[32mNetwork serino_default Created\033[0m\\n'
  printf ' \033[32mContainer serino-api-run-abc123 Creating\033[0m\\n'
  printf ' \033[32mContainer serino-api-run-abc123 Created\033[0m\\n'
  printf '已创建生产环境首次管理员账号。\\n'
}

compose_api_task first-admin-prod.sh
"""
    ).strip()

    assert output == "已创建生产环境首次管理员账号。"


def test_wait_for_release_ready_bypasses_proxy_for_ip_mode_urls():
    output = (
        run_installer_bash(
            """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/docker.sh

AERISUN_ENV_FILE="$(mktemp /tmp/serino-env.XXXXXX)"
SERINO_CURL_LOG="$(mktemp /tmp/serino-curl.XXXXXX)"
cat > "${AERISUN_ENV_FILE}" <<'EOF'
AERISUN_DOMAIN=http://198.51.100.42
AERISUN_SITE_URL=http://198.51.100.42
AERISUN_WALINE_SERVER_URL=http://198.51.100.42/waline
AERISUN_PORT=18000
EOF

curl() {
  printf '%s\\n' "$*" >> "${SERINO_CURL_LOG}"
  return 0
}

cleanup_release_data_migrations() {
  :
}

wait_for_release_ready 3
cat "${SERINO_CURL_LOG}"
"""
        )
        .strip()
        .splitlines()
    )

    assert output == [
        "--noproxy * --fail --silent --show-error --connect-timeout 5 --max-time 10 http://127.0.0.1:18000/api/v1/site/readyz",
        "--noproxy * --fail --silent --show-error --connect-timeout 5 --max-time 10 http://198.51.100.42/",
        "--noproxy * --fail --silent --show-error --connect-timeout 5 --max-time 10 http://198.51.100.42/admin/",
        "--noproxy * --fail --silent --show-error --connect-timeout 5 --max-time 10 http://198.51.100.42/waline/",
    ]


def test_release_ready_does_not_trigger_old_upgrade_rollback_when_post_health_cleanup_fails():
    completed = run_installer_bash_result(
        """
source installer/lib/common.sh
source installer/lib/docker.sh

load_env_file() {
  AERISUN_DOMAIN='http://198.51.100.42'
  AERISUN_SITE_URL='http://198.51.100.42'
  AERISUN_WALINE_SERVER_URL='http://198.51.100.42/waline'
}
resolve_backend_healthcheck_url() { printf 'http://127.0.0.1/readyz'; }
wait_for_url() { return 0; }
cleanup_release_data_migrations() { return 1; }

wait_for_release_ready 3
"""
    )

    assert completed.returncode == 0
    assert "站点保持新版本" in completed.stderr


def test_current_upgrade_can_defer_ready_cleanup_to_its_single_explicit_cleanup_step():
    completed = run_installer_bash_result(
        """
source installer/lib/common.sh
source installer/lib/docker.sh

AERISUN_DEFER_READY_CLEANUP_TO_CALLER='true'
load_env_file() {
  AERISUN_DOMAIN='http://198.51.100.42'
  AERISUN_SITE_URL='http://198.51.100.42'
  AERISUN_WALINE_SERVER_URL='http://198.51.100.42/waline'
}
resolve_backend_healthcheck_url() { printf 'http://127.0.0.1/readyz'; }
wait_for_url() { return 0; }
cleanup_release_data_migrations() { printf 'unexpected-compat-cleanup\n'; }

wait_for_release_ready 3
"""
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == ""


def test_release_readiness_failure_reverts_deferred_external_copies_before_old_script_rolls_back():
    completed = run_installer_bash_result(
        """
source installer/lib/common.sh
source installer/lib/docker.sh

AERISUN_RELEASE_DATA_MIGRATION_DEFERRED='true'
rollback_release_data_migration_external_copies() {
  printf 'external-rollback:%s\n' "${1:-}"
}

fail_release_readiness 'not ready'
"""
    )

    assert completed.returncode == 1
    assert completed.stdout.strip() == "external-rollback:blocking"
    assert "not ready" in completed.stderr


def test_wait_for_domain_url_bypasses_proxy_for_local_https_ready_checks():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/env.sh
source installer/lib/docker.sh

SERINO_CURL_LOG="$(mktemp /tmp/serino-curl-domain.XXXXXX)"

curl() {
  printf '%s\\n' "$*" >> "${SERINO_CURL_LOG}"
  return 0
}

wait_for_domain_url example.test / 3
cat "${SERINO_CURL_LOG}"
"""
    ).strip()

    assert (
        output
        == "--noproxy * --fail --silent --show-error --connect-timeout 5 --max-time 10 --insecure --resolve example.test:443:127.0.0.1 https://example.test/"
    )


def test_compose_api_task_quiet_success_suppresses_normal_success_output():
    output = run_installer_bash(
        """
source installer/lib/common.sh
source installer/lib/docker.sh

compose() {
  printf 'Container serino-api-run-abc123 Creating\\n'
  printf 'Container serino-api-run-abc123 Created\\n'
  printf '已创建生产环境首次管理员账号。\\n'
}

compose_api_task_quiet_success first-admin-prod.sh
"""
    ).strip()

    assert output == ""


def test_run_release_data_migrations_uses_progress_mode_for_installer_output():
    completed = run_installer_bash_result(
        """
source installer/lib/common.sh
source installer/lib/docker.sh

compose_api_task() {
  printf '%s\\n' "$*"
}

run_release_data_migrations blocking
"""
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "data-migrate.sh apply --mode blocking --progress --defer-cleanup"
    assert completed.stderr.strip() == "[INFO] 🛠️ 正在执行版本化数据迁移..."


def test_release_upgrade_can_defer_cleanup_and_exposes_explicit_cleanup_hooks():
    completed = run_installer_bash_result(
        """
source installer/lib/common.sh
source installer/lib/docker.sh

compose_api_task() {
  printf '%s\n' "$*"
}

run_release_data_migrations blocking --defer-cleanup
cleanup_release_data_migrations blocking
rollback_release_data_migration_external_copies blocking
"""
    )

    assert completed.returncode == 0
    assert completed.stdout.strip().splitlines() == [
        "data-migrate.sh apply --mode blocking --progress --defer-cleanup",
        "data-migrate.sh cleanup --mode blocking",
        "data-migrate.sh rollback-external --mode blocking",
    ]


def test_upgrade_cleans_legacy_assets_only_after_new_release_is_ready():
    upgrade_text = read_project_file("installer/upgrade.sh")

    deferred = "run_release_data_migrations blocking --defer-cleanup"
    ready = "wait_for_release_ready"
    cleanup = "cleanup_release_data_migrations blocking"
    rollback_external = "rollback_deferred_release_data_migration"
    rollback_local = "rollback_failed_upgrade"
    deferred_index = upgrade_text.index(deferred)
    ready_index = upgrade_text.index(ready, deferred_index)
    cleanup_index = upgrade_text.index(cleanup, ready_index)
    assert deferred_index < ready_index < cleanup_index
    assert upgrade_text.index("AERISUN_DEFER_READY_CLEANUP_TO_CALLER=true", deferred_index) < ready_index
    assert upgrade_text.index(rollback_external, deferred_index) < upgrade_text.index(rollback_local, deferred_index)
    assert "站点保持在新版本" in upgrade_text


def test_upgrade_pull_failure_rolls_back_locally_without_invoking_external_data_rollback():
    completed = run_installer_bash_result(
        """
source installer/lib/common.sh
source installer/lib/docker.sh

compose() {
  printf 'pull-failed\n'
  return 1
}
run_release_data_migrations() {
  printf 'data-migration-must-not-run\n'
}
rollback_release_data_migration_external_copies() {
  printf 'external-rollback-must-not-run\n'
}
rollback_failed_upgrade() {
  printf 'local-rollback\n'
}

if ! (compose pull && run_release_data_migrations blocking); then
  if deferred_release_data_migration_is_armed; then
    rollback_deferred_release_data_migration
  fi
  rollback_failed_upgrade
fi
"""
    )

    assert completed.returncode == 0
    assert completed.stdout.strip().splitlines() == ["pull-failed", "local-rollback"]


def test_blocking_data_migration_arms_external_rollback_only_when_it_starts(tmp_path: Path):
    marker_root = tmp_path / "upgrade-backup"
    marker_root.mkdir()
    completed = run_installer_bash_result(
        f"""
source installer/lib/common.sh
source installer/lib/docker.sh

UPGRADE_ROLLBACK_BACKUP_DIR='{marker_root}'
run_as_root() {{ "$@"; }}
compose_api_task() {{ printf '%s\n' "$*"; }}

run_release_data_migrations blocking
deferred_release_data_migration_is_armed
printf 'armed\n'
commit_deferred_release_data_migration
if deferred_release_data_migration_is_armed; then
  printf 'still-armed\n'
else
  printf 'disarmed\n'
fi
"""
    )

    assert completed.returncode == 0
    assert completed.stdout.strip().splitlines() == [
        "data-migrate.sh apply --mode blocking --progress --defer-cleanup",
        "armed",
        "disarmed",
    ]
    assert not (marker_root / ".target-data-migration-runner-ready").exists()


def test_sercli_logs_can_list_known_runtime_services():
    output = (
        run_installer_bash(
            """
source installer/bin/sercli

ensure_supported_existing_installation() {
  :
}

list_runtime_compose_services() {
  printf 'api\\nwaline\\ncaddy\\n'
}

cmd_logs --list-services
"""
        )
        .strip()
        .splitlines()
    )

    assert output == ["api", "waline", "caddy"]


def test_sercli_logs_rejects_unknown_service_names_early():
    completed = run_installer_bash_result(
        """
source installer/bin/sercli

ensure_supported_existing_installation() {
  :
}

list_runtime_compose_services() {
  printf 'api\\nwaline\\ncaddy\\n'
}

cmd_logs web
"""
    )

    assert completed.returncode == 1
    assert "未知服务：web。可用服务：api, waline, caddy" in completed.stderr


def test_sercli_migrate_data_forwards_mode_to_release_runner():
    output = run_installer_bash(
        """
source installer/bin/sercli

ensure_supported_existing_installation() {
  :
}

run_release_data_migrations() {
  printf 'mode:%s\\n' "${1:-}"
}

cmd_migrate data --mode background
"""
    ).strip()

    assert output == "mode:background"


def test_sercli_blocking_migrate_finishes_deferred_cleanup_explicitly():
    output = (
        run_installer_bash(
            """
source installer/bin/sercli

ensure_supported_existing_installation() {
  :
}

run_release_data_migrations() {
  printf 'apply:%s\n' "${1:-}"
}

cleanup_release_data_migrations() {
  printf 'cleanup:%s\n' "${1:-}"
}

cmd_migrate data --mode blocking
"""
        )
        .strip()
        .splitlines()
    )

    assert output == ["apply:blocking", "cleanup:blocking"]


def test_sercli_migrate_status_uses_data_migration_script():
    output = run_installer_bash(
        """
source installer/bin/sercli

ensure_supported_existing_installation() {
  :
}

compose_api_task() {
  printf '%s %s %s\\n' "$1" "$2" "$3"
}

cmd_migrate status --json
"""
    ).strip()

    assert output == "data-migrate.sh status --json"


def test_sercli_wait_forwards_custom_timeout():
    output = run_installer_bash(
        """
source installer/bin/sercli

ensure_supported_existing_installation() {
  :
}

wait_for_release_ready() {
  printf 'timeout:%s\\n' "${1:-<default>}"
}

cmd_wait --timeout 42
"""
    ).strip()

    assert output == "timeout:42"


def test_doctor_migration_summary_reports_baseline_and_background_lanes():
    output = (
        run_installer_bash(
            """
source installer/doctor.sh
payload='{"current_revision":"0001_production_baseline","head_revisions":["0001_production_baseline"],"baseline":{"migration_key":"2026_04_production_baseline_v1","schema_revision":"0001_production_baseline","status":"applied"},"blocking":{"applied":[],"pending":[],"failed":[]},"background":{"applied":[],"pending":["0002_rehash_assets"],"scheduled":[],"running":[],"failed":[]}}'
summarize_migration_report_json "${payload}"
"""
        )
        .strip()
        .splitlines()
    )

    assert output == [
        "ok\tdata.schema_revision\t当前 schema revision=0001_production_baseline，已对齐 head=0001_production_baseline。\t",
        "ok\tdata.baseline\t生产 baseline 已应用：2026_04_production_baseline_v1。\t",
        "ok\tdata.migrations.blocking\t阻塞式数据迁移已对齐。\t",
        "warn\tdata.migrations.background\t存在待调度的后台数据迁移：0002_rehash_assets\tsercli migrate data --mode background",
    ]


def test_doctor_migration_summary_reports_interrupted_blocking_lane():
    output = (
        run_installer_bash(
            """
source installer/doctor.sh
payload='{"current_revision":"0019_asset_storage_layout","head_revisions":["0019_asset_storage_layout"],"baseline":{"migration_key":"2026_04_production_baseline_v1","status":"applied"},"blocking":{"applied":[],"pending":[],"running":["2026_08_asset_storage_layout_v1"],"failed":[]},"background":{"applied":[],"pending":[],"scheduled":[],"running":[],"failed":[]}}'
summarize_migration_report_json "${payload}"
"""
        )
        .strip()
        .splitlines()
    )

    assert any(
        line
        == "fail\tdata.migrations.blocking\t存在中断后待恢复的阻塞式数据迁移：2026_08_asset_storage_layout_v1\tsercli migrate data --mode blocking"
        for line in output
    )


def test_doctor_migration_summary_reports_pending_post_release_cleanup():
    output = run_installer_bash(
        """
source installer/doctor.sh
payload='{"current_revision":"0019_asset_storage_layout","head_revisions":["0019_asset_storage_layout"],"baseline":{"migration_key":"2026_04_production_baseline_v1","status":"applied"},"blocking":{"applied":["2026_08_asset_storage_layout_v1"],"pending":[],"running":[],"failed":[],"cleanup_pending":["2026_08_asset_storage_layout_v1"]},"background":{"applied":[],"pending":[],"scheduled":[],"running":[],"failed":[],"cleanup_pending":[]}}'
summarize_migration_report_json "${payload}"
"""
    )

    assert (
        "fail\tdata.migrations.blocking\t阻塞式数据迁移仍有待确认清理的旧副本："
        "2026_08_asset_storage_layout_v1\tsercli migrate data --mode blocking"
    ) in output


def test_doctor_text_report_uses_icons_for_statuses():
    output = (
        run_installer_bash(
            """
source installer/doctor.sh
: > "${DOCTOR_TMP}"
record_check ok layout.legacy '未检测到旧版安装布局残留。' ''
record_check fail serino.service 'serino.service 已启用但当前未运行。' 'sudo systemctl restart serino.service'
record_check warn data.migrations.background '存在待调度的后台数据迁移。' 'sercli migrate data --mode background'
emit_text_report
"""
        )
        .strip()
        .splitlines()
    )

    assert output == [
        "✅ layout.legacy: 未检测到旧版安装布局残留。",
        "❌ serino.service: serino.service 已启用但当前未运行。",
        "  修复建议：sudo systemctl restart serino.service",
        "⚠️ data.migrations.background: 存在待调度的后台数据迁移。",
        "  修复建议：sercli migrate data --mode background",
    ]


def test_doctor_checks_systemd_unit_content_without_hard_failing_legacy_units():
    output = (
        run_installer_bash(
            """
source installer/doctor.sh
: > "${DOCTOR_TMP}"

unit_dir="$(mktemp -d)"
primary_unit="${unit_dir}/serino.service"
upgrade_unit="${unit_dir}/serino-upgrade.service"
legacy_upgrade_unit="${unit_dir}/legacy-upgrade.service"

cat > "${primary_unit}" <<EOF
[Service]
ExecStart=/bin/bash -lc 'export COMPOSE_PROJECT_NAME=${AERISUN_COMPOSE_PROJECT_NAME}; exec docker compose -f ${AERISUN_RENDERED_COMPOSE_FILE} up -d --remove-orphans'
ExecStop=/bin/bash -lc 'export COMPOSE_PROJECT_NAME=${AERISUN_COMPOSE_PROJECT_NAME}; exec docker compose -f ${AERISUN_RENDERED_COMPOSE_FILE} down'
EOF

cat > "${upgrade_unit}" <<EOF
[Service]
ExecStart=${SERINO_BIN_LINK} upgrade --check
EOF

cat > "${legacy_upgrade_unit}" <<EOF
[Service]
ExecStart=${SERINO_BIN_LINK} upgrade
EOF

check_primary_service_unit_content "${primary_unit}"
check_upgrade_service_unit_content "${upgrade_unit}"
check_upgrade_service_unit_content "${legacy_upgrade_unit}"
cut -f1-2 "${DOCTOR_TMP}"
rm -rf "${unit_dir}"
"""
        )
        .strip()
        .splitlines()
    )

    assert output == [
        "ok\tsystemd.serino.service.content",
        "ok\tsystemd.serino-upgrade.service.content",
        "warn\tsystemd.serino-upgrade.service.content",
    ]


def test_production_settings_default_runtime_paths_point_to_srv_store():
    from aerisun.core.settings import Settings

    settings = Settings(_env_file=None, environment="production")

    assert settings.store_dir == Path("/srv/aerisun/store")
    assert settings.data_dir == Path("/srv/aerisun/store")
    assert settings.media_dir == Path("/srv/aerisun/store/media")
    assert settings.secrets_dir == Path("/srv/aerisun/store/secrets")
    assert settings.db_path == Path("/srv/aerisun/store/aerisun.db")
    assert settings.waline_db_path == Path("/srv/aerisun/store/waline.db")
    assert settings.workflow_db_path == Path("/srv/aerisun/store/langgraph.db")
    assert settings.backup_sync_tmp_dir == Path("/srv/aerisun/store/.backup-sync-tmp")


def test_shared_path_defaults_are_tracked_in_root_env():
    env_text = read_project_file(".env")

    assert "AERISUN_API_BASE_PATH=/api" in env_text
    assert "AERISUN_ADMIN_BASE_PATH=/admin/" in env_text
    assert "AERISUN_WALINE_BASE_PATH=/waline" in env_text
    assert "AERISUN_HEALTHCHECK_PATH=/api/v1/site/readyz" in env_text
    assert "AERISUN_FRONTEND_DIST_DIR=/srv/aerisun/frontend" in env_text
    assert "AERISUN_ADMIN_DIST_DIR=/srv/aerisun/admin" in env_text


def test_deploy_contract_reuses_shared_env_keys():
    compose_text = read_project_file("docker-compose.yml")
    release_compose_text = read_project_file("docker-compose.release.yml")
    caddy_text = read_project_file("Caddyfile")
    smoke_text = read_project_file("scripts/docker-smoke.sh")
    dev_smoke_text = read_project_file("scripts/dev-smoke.sh")
    dev_start_text = read_project_file("scripts/dev-start.sh")
    frontend_index_text = read_project_file("frontend/index.html")
    frontend_vite_text = read_project_file("frontend/vite.config.ts")
    admin_vite_text = read_project_file("admin/vite.config.ts")

    assert "AERISUN_PORT: ${AERISUN_PORT:-8000}" in compose_text
    assert "AERISUN_WORKFLOW_DB_PATH: ${AERISUN_WORKFLOW_DB_PATH:-/srv/aerisun/store/langgraph.db}" in compose_text
    assert (
        "AERISUN_BACKUP_SYNC_TMP_DIR: ${AERISUN_BACKUP_SYNC_TMP_DIR:-/srv/aerisun/store/.backup-sync-tmp}"
        in compose_text
    )
    assert "AERISUN_HEALTHCHECK_PATH: ${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/readyz}" in compose_text
    healthcheck_curl = (
        'curl", "-f", "http://localhost:${AERISUN_PORT:-8000}${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/readyz}'
    )
    assert healthcheck_curl in compose_text
    assert "WALINE_JWT_TOKEN: ${WALINE_JWT_TOKEN}" in compose_text
    assert "AERISUN_SEED_REFERENCE_DATA" not in release_compose_text
    assert "AERISUN_DATA_BACKFILL_ENABLED" not in release_compose_text
    release_api_block = release_compose_text.split("  api:\n", 1)[1].split("\n  waline:\n", 1)[0]
    assert "    healthcheck:" in release_api_block
    assert "      retries: 10" in release_api_block
    assert "      start_period: 90s" in release_api_block
    assert "AERISUN_API_BASE_PATH: ${AERISUN_API_BASE_PATH:-/api}" in compose_text
    assert "AERISUN_ADMIN_BASE_PATH: ${AERISUN_ADMIN_BASE_PATH:-/admin/}" in compose_text
    assert "AERISUN_WALINE_BASE_PATH: ${AERISUN_WALINE_BASE_PATH:-/waline}" in compose_text
    assert "AERISUN_FRONTEND_DIST_DIR: ${AERISUN_FRONTEND_DIST_DIR:-/srv/aerisun/frontend}" in compose_text
    assert "AERISUN_ADMIN_DIST_DIR: ${AERISUN_ADMIN_DIST_DIR:-/srv/aerisun/admin}" in compose_text
    assert "no-new-privileges" not in compose_text
    assert "no-new-privileges" not in release_compose_text
    assert "AERISUN_FRONTEND_INDEX_URL: ${AERISUN_FRONTEND_INDEX_URL:-http://caddy:8081/index.html}" in compose_text
    assert "AERISUN_FRONTEND_INDEX_URL: http://127.0.0.1:8081/index.html" in release_compose_text
    assert '- "127.0.0.1:${AERISUN_PORT:-8000}:${AERISUN_PORT:-8000}"' in compose_text
    assert "{$AERISUN_API_UPSTREAM:api:8000}" in caddy_text
    assert "{$AERISUN_WALINE_UPSTREAM:waline:8360}" in caddy_text
    assert "{$AERISUN_API_BASE_PATH:/api}" in caddy_text
    assert "{$AERISUN_ADMIN_BASE_PATH:/admin/}" in caddy_text
    assert "{$AERISUN_WALINE_BASE_PATH:/waline}" in caddy_text
    assert "{$AERISUN_FRONTEND_DIST_DIR:/srv/aerisun/frontend}" in caddy_text
    assert "{$AERISUN_ADMIN_DIST_DIR:/srv/aerisun/admin}" in caddy_text
    assert "http://127.0.0.1:8081" in caddy_text
    assert "handle /bootstrap.js" in caddy_text
    assert "@seoHtml" in caddy_text
    assert "path / /resume" in caddy_text
    assert "@seoContentCrawler" in caddy_text
    assert "header_regexp User-Agent" in caddy_text
    assert "path /posts /posts/* /notes /notes/* /diary /diary/* /thoughts /excerpts /friends /guestbook" in caddy_text
    for crawler_token in (
        "oai-searchbot",
        "chatgpt-user",
        "claude-searchbot",
        "claude-user",
        "googlebot",
        "googleother",
        "google-inspectiontool",
        "google-agent",
        "google-notebooklm",
        "google-read-aloud",
        "bingbot",
        "baiduspider",
        "bytespider",
        "doubaobot",
    ):
        assert crawler_token in caddy_text.casefold()
        assert crawler_token in frontend_vite_text.casefold()
    assert "query seo=1" not in caddy_text
    assert "handle /robots.txt" in caddy_text
    assert "handle /llms.txt" in caddy_text
    assert "handle /resume.md" in caddy_text

    assert 'HEALTHCHECK_PATH="${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/readyz}"' in smoke_text
    assert 'ADMIN_BASE_PATH="$(ensure_trailing_slash "${AERISUN_ADMIN_BASE_PATH:-/admin/}")"' in smoke_text
    assert 'WALINE_BASE_PATH="$(strip_trailing_slash "${AERISUN_WALINE_BASE_PATH:-/waline}")"' in smoke_text
    assert "AERISUN_DOMAIN=http://${SITE_HOST}" in smoke_text
    assert 'LOCAL_IMAGE_REGISTRY="${AERISUN_SMOKE_IMAGE_REGISTRY:-serino-smoke-local}"' in smoke_text
    assert "AERISUN_IMAGE_REGISTRY=${LOCAL_IMAGE_REGISTRY}" in smoke_text
    assert "WALINE_JWT_TOKEN=smoke-0123456789abcdef0123456789abcdef" in smoke_text
    assert "AERISUN_DATA_BACKFILL_ENABLED" not in smoke_text
    assert 'TMP_STORE_DIR="$(mktemp -d "${PROJECT_DIR}/.docker-smoke-store.XXXXXX")"' in smoke_text
    assert (
        'mkdir -p "${TMP_STORE_DIR}/media" "${TMP_STORE_DIR}/secrets" "${TMP_STORE_DIR}/.backup-sync-tmp"' in smoke_text
    )
    assert 'chmod -R 0777 "${TMP_STORE_DIR}"' in smoke_text

    assert 'healthcheck_path="${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/readyz}"' in dev_smoke_text
    assert 'admin_base_path="${AERISUN_ADMIN_BASE_PATH:-/admin/}"' in dev_smoke_text
    backend_health_url = (
        'backend_health_url="http://127.0.0.1:${AERISUN_PORT:-8000}${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/readyz}"'
    )
    assert backend_health_url in dev_start_text
    assert 'const apiBasePath = stripTrailingSlash(env.AERISUN_API_BASE_PATH ?? "/api");' in frontend_vite_text
    assert "seoHtmlDevProxyPlugin(apiProxyTarget)" in frontend_vite_text
    assert "isAlwaysSeoHtmlPath(url.pathname)" in frontend_vite_text
    assert "isCrawlerOnlySeoHtmlPath(url.pathname)" in frontend_vite_text
    assert "isCrawlerRequest(req.headers)" in frontend_vite_text
    assert "server.transformIndexHtml(url.pathname, html)" in frontend_vite_text
    assert "seoHtmlDevProxyBlockedResponseHeaders" in frontend_vite_text
    assert 'SMOKE_BROWSER_UA="Mozilla/5.0 (SerinoDockerSmoke)"' in smoke_text
    assert 'SMOKE_CRAWLER_UA="OAI-SearchBot/1.0 (SerinoDockerSmoke)"' in smoke_text
    assert 'curl --noproxy \'*\' -A "${SMOKE_BROWSER_UA}" -fsS "${url}" -o "${body_file}"' in smoke_text
    assert 'curl --noproxy \'*\' -A "${SMOKE_CRAWLER_UA}" -fsS "${url}" -o "${body_file}"' in smoke_text
    assert '"content-security-policy"' in frontend_vite_text
    assert '"content-length"' in frontend_vite_text
    assert '"/robots.txt": {' in frontend_vite_text
    assert '"/llms.txt": {' in frontend_vite_text
    assert '"/resume.md": {' in frontend_vite_text
    assert 'rel="alternate"' not in frontend_index_text
    assert "aerisun.top" not in frontend_index_text
    assert 'const walineBasePath = stripTrailingSlash(env.AERISUN_WALINE_BASE_PATH ?? "/waline");' in frontend_vite_text
    assert 'const adminBasePath = normalizeBasePath(env.AERISUN_ADMIN_BASE_PATH || "", "/admin/");' in admin_vite_text
    assert 'const apiBasePath = (env.AERISUN_API_BASE_PATH || "/api").replace(/\\/+$/, "");' in admin_vite_text


def test_production_defaults_do_not_track_dev_only_upstreams():
    production_text = read_project_file(".env.production")
    dockerignore_text = read_project_file(".dockerignore")
    production_local_example_text = read_project_file(".env.production.local.example")

    assert "AERISUN_FRONTEND_UPSTREAM" not in production_text
    assert "AERISUN_ADMIN_UPSTREAM" not in production_text
    assert ".env.*.local" in dockerignore_text
    assert (
        "AERISUN_IMAGE_REGISTRY=crpi-hwvtw8db2uk7bil0.cn-beijing.personal.cr.aliyuncs.com/serino"
        in production_local_example_text
    )
    assert "AERISUN_UBUNTU_APT_MIRROR_URL=https://your-mirror.example.com/ubuntu/" in production_local_example_text
    assert "AERISUN_DEBIAN_APT_MIRROR_URL=https://your-mirror.example.com/debian/" in production_local_example_text
    assert "AERISUN_APT_MIRROR_URL=https://your-shared-mirror.example.com/" in production_local_example_text
    assert "/etc/serino/serino.env" in production_local_example_text
    assert "/var/lib/serino" in production_local_example_text
    assert "AERISUN_WORKFLOW_DB_PATH=/srv/aerisun/store/langgraph.db" in production_local_example_text
    assert "AERISUN_BACKUP_SYNC_TMP_DIR=/srv/aerisun/store/.backup-sync-tmp" in production_local_example_text
    assert "AERISUN_SEED_REFERENCE_DATA" not in production_local_example_text
    assert "AERISUN_DATA_BACKFILL_ENABLED" not in production_local_example_text


def test_caddy_routes_serino_before_local_extensions_and_returns_real_404():
    caddy_text = read_project_file("Caddyfile")
    release_compose_text = read_project_file("docker-compose.release.yml")
    web_dockerfile_text = read_project_file("Dockerfile.caddy")

    assert "route {" in caddy_text
    assert "import /etc/caddy/routes.d/active/*.caddy" in caddy_text
    assert "import /etc/caddy/routes.d/*.caddy" not in caddy_text
    assert "respond 404" in caddy_text
    assert caddy_text.count("try_files {path} /index.html") == 1
    assert "try_files /index.html" in caddy_text
    assert "@frontendSpa" in caddy_text
    assert "@previewPage" in caddy_text
    assert 'header X-Robots-Tag "noindex, nofollow"' in caddy_text
    assert "redir /admin /admin/ 308" in caddy_text
    assert "path /assets/* /fonts/* /index.html /registerSW.js /sw.js" in caddy_text
    assert (
        "path / /posts /posts/* /notes /notes/* /friends /thoughts /diary /diary/* /excerpts /resume /guestbook /calendar"
        in caddy_text
    )
    assert "path /preview" in caddy_text
    assert caddy_text.index("@apiRoutes") < caddy_text.index("import /etc/caddy/routes.d/active/*.caddy")
    assert caddy_text.index("import /etc/caddy/routes.d/active/*.caddy") < caddy_text.index("respond 404")

    assert "${SERINO_CADDY_ROUTES_DIR:-/etc/serino/routes.d}:/etc/caddy/routes.d:ro" in release_compose_text
    api_block = release_compose_text.split("  api:\n", 1)[1].split("\n  waline:\n", 1)[0]
    caddy_block = release_compose_text.split("  caddy:\n", 1)[1]
    assert "    network_mode: host" in api_block
    assert "      AERISUN_HOST: 127.0.0.1" in api_block
    assert "${AERISUN_HOST" not in api_block
    assert "    ports:" not in api_block
    assert "    network_mode: host" in caddy_block
    assert "    ports:" not in caddy_block
    assert "      AERISUN_HTTP_PORT: ${AERISUN_HTTP_PORT:-80}" in caddy_block
    assert "      AERISUN_HTTPS_PORT: ${AERISUN_HTTPS_PORT:-443}" in caddy_block
    assert "      AERISUN_API_UPSTREAM: 127.0.0.1:${AERISUN_PORT:-8000}" in caddy_block
    assert "      AERISUN_WALINE_UPSTREAM: 127.0.0.1:${WALINE_PORT:-8360}" in caddy_block
    assert "mkdir -p /etc/caddy/routes.d" in web_dockerfile_text


def test_service_forward_runtime_uses_private_caddy_admin_reload():
    development_compose_text = read_project_file("docker-compose.yml")
    release_compose_text = read_project_file("docker-compose.release.yml")
    web_dockerfile_text = read_project_file("Dockerfile.caddy")
    common_text = read_project_file("installer/lib/common.sh")
    service_text = read_project_file("backend/src/aerisun/domain/service_forwards/service.py")

    release_api_block = release_compose_text.split("  api:\n", 1)[1].split("\n  waline:\n", 1)[0]
    release_caddy_block = release_compose_text.split("  caddy:\n", 1)[1]
    assert "AERISUN_CADDY_ROUTES_DIR: /srv/aerisun/caddy-routes" in release_api_block
    assert "AERISUN_CADDY_ADMIN_URL: http://127.0.0.1:2019" in release_api_block
    assert "${SERINO_CADDY_ROUTES_DIR:-/etc/serino/routes.d}:/srv/aerisun/caddy-routes" in release_api_block
    assert "${SERINO_CADDY_ROUTES_DIR:-/etc/serino/routes.d}:/etc/caddy/routes.d:ro" in release_caddy_block
    assert "2019:2019" not in release_compose_text

    development_api_block = development_compose_text.split("  api:\n", 1)[1].split("\n  waline:\n", 1)[0]
    development_caddy_block = development_compose_text.split("  caddy:\n", 1)[1]
    assert "AERISUN_CADDY_ADMIN_URL: http://caddy:2019" in development_api_block
    assert "caddy_routes:/srv/aerisun/caddy-routes" in development_api_block
    assert "source: caddy_routes" in development_caddy_block
    assert "target: /etc/caddy/routes.d" in development_caddy_block
    assert "nocopy: true" in development_caddy_block
    assert "CADDY_ADMIN: 0.0.0.0:2019" in development_caddy_block
    assert "2019:2019" not in development_compose_text

    assert "COPY scripts/caddy-entrypoint.sh" not in web_dockerfile_text
    assert 'admin_url.rstrip("/") + "/load"' in service_text
    assert 'content="import /etc/caddy/Caddyfile\\n"' in service_text
    assert '"Content-Type": "text/caddyfile"' in service_text
    assert '"Cache-Control": "must-revalidate"' in service_text
    assert "mkdir -p /srv/aerisun/caddy-routes" in read_project_file("backend/Dockerfile")
    assert (
        'run_as_root install -d -o root -g "${SERINO_SERVICE_GROUP}" -m 0770 "${SERINO_CADDY_ROUTES_DIR}"'
        in common_text
    )


def test_local_caddy_route_library_validates_and_renders_routes(tmp_path: Path):
    routes_lib = PROJECT_ROOT / "installer/lib/routes.sh"
    assert routes_lib.exists()

    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    output = (
        run_installer_bash(
            f"""
source installer/lib/common.sh
source installer/lib/routes.sh

SERINO_CADDY_ROUTES_DIR='{routes_dir}'
AERISUN_API_BASE_PATH='/api'
AERISUN_ADMIN_BASE_PATH='/admin/'
AERISUN_WALINE_BASE_PATH='/waline'

printf 'path=%s\\n' "$(normalize_caddy_route_path '/files/')"
printf 'upstream=%s\\n' "$(normalize_caddy_route_upstream 'http://127.0.0.1:9000')"
if caddy_route_conflicts_with_serino '/api/v1'; then
  printf 'reserved=/api/v1\\n'
fi
if caddy_route_conflicts_with_serino '/mcp/install'; then
  printf 'reserved=/mcp/install\\n'
fi
if ! caddy_route_conflicts_with_serino '/postscript'; then
  printf 'available=/postscript\\n'
fi

render_caddy_route_config '/files' 'http://127.0.0.1:9000'
"""
        )
        .strip()
        .splitlines()
    )

    assert output[:5] == [
        "path=/files",
        "upstream=http://127.0.0.1:9000",
        "reserved=/api/v1",
        "reserved=/mcp/install",
        "available=/postscript",
    ]
    rendered = "\n".join(output[5:])
    assert "# serino-route-path: /files" in rendered
    assert "# serino-route-upstream: http://127.0.0.1:9000" in rendered
    assert "path /files /files/*" in rendered
    assert "reverse_proxy http://127.0.0.1:9000" in rendered
    assert "strip_prefix" not in rendered


def test_local_caddy_route_library_rejects_unsafe_inputs(tmp_path: Path):
    routes_lib = PROJECT_ROOT / "installer/lib/routes.sh"
    assert routes_lib.exists()

    result = run_installer_bash_result(
        f"""
source installer/lib/common.sh
source installer/lib/routes.sh

SERINO_CADDY_ROUTES_DIR='{tmp_path}/routes'

for path in '/' 'relative' '/with space' '/files?download=1' '/files#top' '/files/*' '/files/../admin'; do
  if normalize_caddy_route_path "${{path}}" >/dev/null 2>&1; then
    printf 'accepted-path:%s\\n' "${{path}}"
  fi
done

for upstream in 'ftp://127.0.0.1:9000' 'http://user:pass@127.0.0.1:9000' \
  'http://127.0.0.1:9000/base' 'http://127.0.0.1:9000?x=1'; do
  if normalize_caddy_route_upstream "${{upstream}}" >/dev/null 2>&1; then
    printf 'accepted-upstream:%s\\n' "${{upstream}}"
  fi
done
"""
    )

    assert result.returncode == 0
    assert result.stdout == ""


def test_route_command_adds_lists_and_removes_local_route(tmp_path: Path):
    routes_script = PROJECT_ROOT / "installer/route.sh"
    assert routes_script.exists()

    routes_dir = tmp_path / "routes"
    output = (
        run_installer_bash(
            f"""
source installer/route.sh

SERINO_CADDY_ROUTES_DIR='{routes_dir}'
AERISUN_SITE_URL='https://example.com'

run_as_root() {{
  if [[ "$1" == "install" ]]; then
    shift
    local -a args=()
    while [[ "$#" -gt 0 ]]; do
      case "$1" in
        -o|-g)
          shift 2
          ;;
        *)
          args+=("$1")
          shift
          ;;
      esac
    done
    command install "${{args[@]}}"
    return
  fi
  "$@"
}}
validate_caddy_route_configuration() {{
  if grep -q '# serino-route-path: /files' "${{SERINO_CADDY_ROUTES_DIR}}/active/routes.caddy" 2>/dev/null; then
    printf 'validate:files\\n'
  else
    printf 'validate:empty\\n'
  fi
}}
reload_caddy_route_configuration_if_running() {{
  printf 'reload\\n'
}}

cmd_route_add /files http://127.0.0.1:9000
cmd_route_list
cmd_route_remove /files
cmd_route_list
"""
        )
        .strip()
        .splitlines()
    )

    assert output == [
        "validate:files",
        "reload",
        "- https://example.com/files → http://127.0.0.1:9000",
        "validate:empty",
        "reload",
        "未配置其他服务转发。",
    ]
    assert not list(routes_dir.glob("route-*.caddy"))


def test_route_command_restores_dispatcher_snapshot_when_rollback_rebuild_fails(tmp_path: Path):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    (routes_dir / "route-existing.caddy").write_text(
        "# serino-route-path: /files\nhandle @files {\n    reverse_proxy http://127.0.0.1:9000\n}\n",
        encoding="utf-8",
    )
    failed_dispatcher = tmp_path / "failed-dispatcher.caddy"
    failed_dispatcher.write_text(
        "# serino-route-path: /other\nhandle @other {\n    reverse_proxy http://127.0.0.1:9001\n}\n"
        "# serino-route-path: /files\nhandle @files {\n    reverse_proxy http://127.0.0.1:9000\n}\n",
        encoding="utf-8",
    )

    output = run_installer_bash(
        f"""
source installer/route.sh

SERINO_CADDY_ROUTES_DIR='{routes_dir}'
AERISUN_SITE_URL='https://example.com'
run_as_root() {{
  if [[ "$1" == "install" ]]; then
    shift
    local -a args=()
    while [[ "$#" -gt 0 ]]; do
      case "$1" in
        -o|-g)
          shift 2
          ;;
        *)
          args+=("$1")
          shift
          ;;
      esac
    done
    command install "${{args[@]}}"
    return
  fi
  "$@"
}}

rebuild_caddy_route_dispatcher
rebuild_calls=0
rebuild_caddy_route_dispatcher() {{
  rebuild_calls=$((rebuild_calls + 1))
  if [[ "${{rebuild_calls}}" -gt 1 ]]; then
    touch "${{SERINO_CADDY_ROUTES_DIR}}/rollback-rebuild-failed"
    return 1
  fi
  command cp '{failed_dispatcher}' "${{SERINO_CADDY_ROUTES_DIR}}/active/routes.caddy"
}}
validate_caddy_route_configuration() {{ :; }}
reload_caddy_route_configuration_if_running() {{ return 1; }}

( cmd_route_add /other http://127.0.0.1:9001 ) || true
cat "${{SERINO_CADDY_ROUTES_DIR}}/active/routes.caddy"
"""
    )

    assert "# serino-route-path: /files" in output
    assert "# serino-route-path: /other" not in output
    assert not (routes_dir / "rollback-rebuild-failed").exists()
    assert [path.name for path in routes_dir.glob("route-*.caddy")] == ["route-existing.caddy"]


def test_route_command_rejects_reserved_and_duplicate_paths(tmp_path: Path):
    routes_script = PROJECT_ROOT / "installer/route.sh"
    assert routes_script.exists()

    result = run_installer_bash_result(
        f"""
source installer/route.sh

SERINO_CADDY_ROUTES_DIR='{tmp_path}/routes'
AERISUN_SITE_URL='https://example.com'

run_as_root() {{
  if [[ "$1" == "install" ]]; then
    shift
    local -a args=()
    while [[ "$#" -gt 0 ]]; do
      case "$1" in
        -o|-g)
          shift 2
          ;;
        *)
          args+=("$1")
          shift
          ;;
      esac
    done
    command install "${{args[@]}}"
    return
  fi
  "$@"
}}
validate_caddy_route_configuration() {{
  :
}}
reload_caddy_route_configuration_if_running() {{
  :
}}

( cmd_route_add /api http://127.0.0.1:9000 ) || printf 'reserved\\n'
cmd_route_add /files http://127.0.0.1:9000
( cmd_route_add /files http://127.0.0.1:9001 ) || printf 'duplicate\\n'
( cmd_route_add /files/private http://127.0.0.1:9002 ) || printf 'overlap\\n'
"""
    )

    assert result.returncode == 0
    assert result.stdout.strip().splitlines() == ["reserved", "duplicate", "overlap"]


def test_installer_runtime_paths_follow_serino_system_layout():
    common_text = read_project_file("installer/lib/common.sh")
    compose_text = read_project_file("docker-compose.release.yml")
    sercli_text = read_project_file("installer/bin/sercli")
    doctor_text = read_project_file("installer/doctor.sh")
    uninstall_text = read_project_file("installer/uninstall.sh")
    install_text = read_project_file("installer/install.sh")
    upgrade_text = read_project_file("installer/upgrade.sh")
    download_text = read_project_file("installer/lib/download.sh")
    docker_text = read_project_file("installer/lib/docker.sh")
    env_text = read_project_file("installer/lib/env.sh")
    service_text = read_project_file("installer/systemd/serino.service")
    upgrade_service_text = read_project_file("installer/systemd/serino-upgrade.service")
    updater_text = read_project_file("installer/updater.sh")
    updater_service_text = read_project_file("installer/systemd/serino-updater.service")
    updater_timer_text = read_project_file("installer/systemd/serino-updater.timer")
    updater_path_text = read_project_file("installer/systemd/serino-updater.path")
    package_text = read_project_file("scripts/package-installer.sh")
    upload_text = read_project_file("scripts/upload-bitiful-installer-assets.py")
    workflow_text = read_project_file(".github/workflows/ci.yml")
    runtime_lib_text = read_project_file("backend/scripts/runtime-lib.sh")
    backend_bootstrap_text = read_project_file("backend/scripts/bootstrap.sh")
    backend_serve_text = read_project_file("backend/scripts/serve.sh")
    backend_migrate_text = read_project_file("backend/scripts/migrate.sh")
    backend_baseline_prod_text = read_project_file("backend/scripts/baseline-prod.sh")
    backend_first_admin_prod_text = read_project_file("backend/scripts/first-admin-prod.sh")
    backend_data_migrate_text = read_project_file("backend/scripts/data-migrate.sh")
    backend_site_api_text = read_project_file("backend/src/aerisun/api/site.py")
    backend_bootstrap_core_text = read_project_file("backend/src/aerisun/core/bootstrap.py")
    backend_task_manager_text = read_project_file("backend/src/aerisun/core/task_manager.py")
    dev_compose_text = read_project_file("docker-compose.yml")
    backend_dockerfile_text = read_project_file("backend/Dockerfile")
    waline_dockerfile_text = read_project_file("Dockerfile.waline")

    assert 'SERINO_CONFIG_ROOT="${SERINO_CONFIG_ROOT:-/etc/serino}"' in common_text
    assert 'SERINO_CADDY_ROUTES_DIR="${SERINO_CADDY_ROUTES_DIR:-${SERINO_CONFIG_ROOT}/routes.d}"' in common_text
    assert 'SERINO_LOG_ROOT="${SERINO_LOG_ROOT:-/var/log/serino}"' in common_text
    assert 'SERINO_SERVICE_USER="${SERINO_SERVICE_USER:-serino}"' in common_text
    assert 'AERISUN_APP_ROOT="${AERISUN_APP_ROOT:-/opt/serino}"' in common_text
    assert 'AERISUN_DATA_DIR="${AERISUN_DATA_DIR:-/var/lib/serino}"' in common_text
    assert 'AERISUN_COMPOSE_PROJECT_NAME="${AERISUN_COMPOSE_PROJECT_NAME:-serino}"' in common_text
    assert 'AERISUN_ENV_FILE="${AERISUN_ENV_FILE:-${SERINO_CONFIG_ROOT}/serino.env}"' in common_text
    assert (
        'AERISUN_RENDERED_COMPOSE_FILE="${AERISUN_RENDERED_COMPOSE_FILE:-${AERISUN_APP_ROOT}/docker-compose.runtime.yml}"'
        in common_text
    )
    assert 'AERISUN_BIN_ROOT="${AERISUN_BIN_ROOT:-${AERISUN_APP_ROOT}/bin}"' in common_text
    assert 'AERISUN_BACKUP_ROOT="${AERISUN_BACKUP_ROOT:-/var/backups/serino}"' in common_text
    assert 'SERINO_SYSTEMD_UPDATER_SERVICE="${SERINO_SYSTEMD_UPDATER_SERVICE:-serino-updater.service}"' in common_text
    assert 'SERINO_SYSTEMD_UPDATER_TIMER="${SERINO_SYSTEMD_UPDATER_TIMER:-serino-updater.timer}"' in common_text
    assert 'SERINO_SYSTEMD_UPDATER_PATH="${SERINO_SYSTEMD_UPDATER_PATH:-serino-updater.path}"' in common_text
    assert 'SERINO_UPDATE_DIR="${SERINO_UPDATE_DIR:-${AERISUN_DATA_DIR}/update}"' in common_text
    assert 'SERINO_UPDATE_REQUESTS_DIR="${SERINO_UPDATE_REQUESTS_DIR:-${SERINO_UPDATE_DIR}/requests}"' in common_text
    assert 'SERINO_UPDATE_STATUS_FILE="${SERINO_UPDATE_STATUS_FILE:-${SERINO_UPDATE_DIR}/status.json}"' in common_text
    assert (
        'SERINO_UPDATE_SUPPORT_MARKER="${SERINO_UPDATE_SUPPORT_MARKER:-${SERINO_UPDATE_DIR}/updater-supported.json}"'
        in common_text
    )
    assert 'AERISUN_HTTP_PORT="${AERISUN_HTTP_PORT:-80}"' in common_text
    assert 'AERISUN_HTTPS_PORT="${AERISUN_HTTPS_PORT:-443}"' in common_text
    assert "make_temp_file() {" in common_text
    assert "make_root_temp_file_in_dir() {" in common_text
    assert (
        'SERINO_MAINTENANCE_LOCK_FILE="${SERINO_MAINTENANCE_LOCK_FILE:-/run/lock/serino-maintenance.lock}"'
        in common_text
    )
    assert "run_with_maintenance_lock() {" in common_text
    assert (
        'SERINO_BIN_LINK="${SERINO_BIN_LINK:-$([[ "${AERISUN_APP_ROOT}" == "/opt/serino" ]] && printf \'%s\' \'/usr/local/bin/sercli\' || printf \'%s\' "${AERISUN_BIN_ROOT}/sercli")}"'
        in common_text
    )
    assert (
        'AERISUN_INSTALL_DEFAULT_BASE_URL="${AERISUN_INSTALL_DEFAULT_BASE_URL:-https://install.aerisun.top/serino}"'
        in common_text
    )
    assert (
        'AERISUN_INSTALL_DEFAULT_DEV_BASE_URL="${AERISUN_INSTALL_DEFAULT_DEV_BASE_URL:-https://install.aerisun.top/serino/dev}"'
        in common_text
    )
    assert 'AERISUN_APT_MIRROR_URL="${AERISUN_APT_MIRROR_URL:-}"' in common_text
    assert (
        'AERISUN_UBUNTU_APT_MIRROR_URL="${AERISUN_UBUNTU_APT_MIRROR_URL:-https://mirrors.aliyun.com/ubuntu/,https://mirrors.tuna.tsinghua.edu.cn/ubuntu/,https://mirrors.ustc.edu.cn/ubuntu/}"'
        in common_text
    )
    assert (
        'AERISUN_DEBIAN_APT_MIRROR_URL="${AERISUN_DEBIAN_APT_MIRROR_URL:-https://mirrors.aliyun.com/debian/,https://mirrors.tuna.tsinghua.edu.cn/debian/,https://mirrors.ustc.edu.cn/debian/}"'
        in common_text
    )
    assert 'AERISUN_DOCKER_REGISTRY_MIRRORS="${AERISUN_DOCKER_REGISTRY_MIRRORS:-}"' in common_text
    assert 'AERISUN_API_IMAGE_NAME="${AERISUN_API_IMAGE_NAME:-serino-api}"' in common_text
    assert 'AERISUN_WEB_IMAGE_NAME="${AERISUN_WEB_IMAGE_NAME:-serino-web}"' in common_text
    assert 'AERISUN_WALINE_IMAGE_NAME="${AERISUN_WALINE_IMAGE_NAME:-serino-waline}"' in common_text
    assert "run_as_root chown -R root:root" in common_text
    assert "ensure_update_runtime_layout() {" in common_text
    assert "resolve_backend_healthcheck_url() {" in env_text
    assert "resolve_release_version_value() {" in env_text

    assert (
        "image: ${AERISUN_IMAGE_REGISTRY:-crpi-hwvtw8db2uk7bil0.cn-beijing.personal.cr.aliyuncs.com/serino}/${AERISUN_API_IMAGE_NAME:-serino-api}:${AERISUN_IMAGE_TAG:-latest}"
        in compose_text
    )
    assert (
        "image: ${AERISUN_IMAGE_REGISTRY:-crpi-hwvtw8db2uk7bil0.cn-beijing.personal.cr.aliyuncs.com/serino}/${AERISUN_WALINE_IMAGE_NAME:-serino-waline}:${AERISUN_IMAGE_TAG:-latest}"
        in compose_text
    )
    assert (
        "image: ${AERISUN_IMAGE_REGISTRY:-crpi-hwvtw8db2uk7bil0.cn-beijing.personal.cr.aliyuncs.com/serino}/${AERISUN_WEB_IMAGE_NAME:-serino-web}:${AERISUN_IMAGE_TAG:-latest}"
        in compose_text
    )
    api_block = compose_text.split("  api:\n", 1)[1].split("\n\n  waline:\n", 1)[0]
    assert 'user: "${SERINO_RUNTIME_UID:-1001}:${SERINO_RUNTIME_GID:-1001}"' in api_block
    assert "HOME: /srv/aerisun/store" in compose_text
    assert "AERISUN_WORKFLOW_DB_PATH: ${AERISUN_WORKFLOW_DB_PATH:-/srv/aerisun/store/langgraph.db}" in compose_text
    assert "AERISUN_INSTALL_CHANNEL: ${AERISUN_INSTALL_CHANNEL:-stable}" in compose_text
    assert "AERISUN_INSTALL_BASE_URL: ${AERISUN_INSTALL_BASE_URL:-}" in compose_text
    assert "AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64: ${AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64:-}" in compose_text
    assert (
        "AERISUN_BACKUP_SYNC_TMP_DIR: ${AERISUN_BACKUP_SYNC_TMP_DIR:-/srv/aerisun/store/.backup-sync-tmp}"
        in compose_text
    )
    assert "${AERISUN_STORE_BIND_DIR:-/var/lib/serino}:/srv/aerisun/store" in compose_text

    assert "sercli help" in sercli_text
    assert "sercli version" in sercli_text
    assert "sercli doctor [--json]" in sercli_text
    assert "sercli migrate schema" in sercli_text
    assert "sercli migrate data [--mode blocking|background|all]" in sercli_text
    assert "sercli migrate status [--json]" in sercli_text
    assert "sercli ps [compose-ps-args...]" in sercli_text
    assert "sercli start [--no-wait]" in sercli_text
    assert "sercli stop" in sercli_text
    assert "sercli updater run|check|status [--json]" in sercli_text
    assert "sercli route add <path> <upstream>" in sercli_text
    assert "sercli route list" in sercli_text
    assert "sercli route remove <path>" in sercli_text
    assert 'source "${INSTALLER_ROOT}/updater.sh"' in sercli_text
    assert 'exec bash "${INSTALLER_ROOT}/doctor.sh" "$@"' in sercli_text
    assert 'run_with_maintenance_lock "upgrade" "${INSTALLER_ROOT}/upgrade.sh" "$@"' in sercli_text
    assert 'run_with_maintenance_lock "uninstall" "${INSTALLER_ROOT}/uninstall.sh" "$@"' in sercli_text
    assert 'run_with_maintenance_lock "route" "${INSTALLER_ROOT}/route.sh" "$@"' in sercli_text
    assert 'main "${SERCLI_MAIN_ARGS[@]}"' in sercli_text
    assert "cmd_migrate() {" in sercli_text
    assert "cmd_ps() {" in sercli_text
    assert "cmd_start() {" in sercli_text
    assert "cmd_stop() {" in sercli_text
    assert "cmd_updater() {" in updater_text
    assert 'record_check "fail" "env.bootstrap_cleanup"' in doctor_text
    assert "check_updater_service_unit_content() {" in doctor_text
    assert "check_updater_timer_unit_content() {" in doctor_text
    assert "check_updater_path_unit_content() {" in doctor_text
    assert 'record_check "fail" "data.migrations"' in doctor_text
    assert "run_doctor_api_script() {" in doctor_text
    assert 'compose run --rm --no-deps -T api /bin/bash "/app/backend/scripts/${script_name}" "$@"' in doctor_text
    assert "data.schema_revision" in doctor_text
    assert "data.baseline" in doctor_text
    assert "data.migrations.blocking" in doctor_text
    assert "data.migrations.background" in doctor_text
    assert 'backend_url="$(resolve_backend_healthcheck_url)"' in doctor_text
    assert 'log_info "卸载前状态摘要（仅供参考，不影响继续卸载）："' in uninstall_text
    assert 'log_warn "上面的诊断失败项不会阻止彻底卸载。"' in uninstall_text
    assert "print_caddy_route_uninstall_warning" in uninstall_text
    assert "validate_registered_caddy_routes" in upgrade_text
    upgrade_main_text = upgrade_text.split("main() {", 1)[1]
    assert upgrade_main_text.index('validate_target_registered_caddy_routes "${bundle_dir}"') < upgrade_main_text.index(
        'backup_dir="$('
    )
    assert upgrade_text.index("install_release_payload") < upgrade_text.index("validate_registered_caddy_routes")
    assert (
        "SERINO_CADDY_ROUTES_DIR"
        not in upgrade_text.split("backup_current_installation() {", 1)[1].split("\n}\n", 1)[0]
    )
    assert '"${AERISUN_INSTALLER_DEST}/route.sh"' in common_text
    assert 'local channel="${AERISUN_INSTALL_CHANNEL:-stable}"' in install_text
    assert "validate_release_compose_configuration" in install_text
    assert "if ! compose pull; then" in install_text
    assert "if ! run_release_migrations; then" in install_text
    assert "if ! run_release_baseline; then" in install_text
    assert "if ! run_release_data_migrations blocking; then" in install_text
    assert "if ! run_release_admin_bootstrap; then" in install_text
    assert "if ! enable_serino_service; then" in install_text
    assert (
        'if ! verify_install_summary_endpoints "${summary_site_probe_url}" "${summary_admin_url}"; then' in install_text
    )
    assert "run_release_migrations" in install_text
    assert "run_release_baseline" in install_text
    assert "run_release_data_migrations blocking" in install_text
    assert "run_release_admin_bootstrap" in install_text
    assert "schedule_release_background_data_migrations || true" in install_text
    assert "print_service_start_failure_diagnostics" in install_text
    assert (
        'local default_dev_base_url="${AERISUN_INSTALL_DEFAULT_DEV_BASE_URL:-https://install.aerisun.top/serino/dev}"'
        in install_text
    )
    assert "compose_with_env() {" in docker_text
    assert "compose_api_task() {" in docker_text
    assert "compose_api_task_background() {" in docker_text
    assert 'compose run --rm --no-deps -T api /bin/bash "/app/backend/scripts/${task}" "$@"' in docker_text
    assert "run_release_migrations() {" in docker_text
    assert "run_release_baseline() {" in docker_text
    assert "run_release_admin_bootstrap() {" in docker_text
    assert "run_release_data_migrations() {" in docker_text
    assert "schedule_release_background_data_migrations() {" in docker_text
    assert "verify_install_summary_endpoints() {" in docker_text
    assert "resolve_compose_runner() {" in docker_text
    assert "runtime_compose_file() {" in docker_text
    assert "render_release_compose_configuration() {" in docker_text
    assert 'backend_url="$(resolve_backend_healthcheck_url)"' in docker_text
    assert 'source "${env_file}"' in docker_text
    assert "validate_release_compose_configuration() {" in docker_text
    assert (
        'rendered_file="$(make_root_temp_file_in_dir "${AERISUN_APP_ROOT}" ".docker-compose.rendered.XXXXXX.yml")"'
        in docker_text
    )
    assert 'run_as_root mktemp "${AERISUN_APP_ROOT}/.docker-compose.rendered.XXXXXX.yml"' not in docker_text
    assert "print_service_start_failure_diagnostics() {" in docker_text
    assert "managed_file_exists() {" in env_text
    assert 'path_is_file "${file}"' in env_text
    assert '[[ -f "${file}" ]]' not in env_text
    assert "AERISUN_APT_MIRROR_URL=${AERISUN_APT_MIRROR_URL}" in env_text
    assert "AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64=${AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64}" in env_text
    assert "AERISUN_UBUNTU_APT_MIRROR_URL=${AERISUN_UBUNTU_APT_MIRROR_URL}" in env_text
    assert "AERISUN_DEBIAN_APT_MIRROR_URL=${AERISUN_DEBIAN_APT_MIRROR_URL}" in env_text
    assert 'AERISUN_DOCKER_REGISTRY_MIRRORS=$(quote_env_literal "${AERISUN_DOCKER_REGISTRY_MIRRORS}")' in env_text
    assert "run_as_root chown -R root:root" in upgrade_text
    assert "yaml.safe_dump" in docker_text
    assert "probe_release_image" not in docker_text
    assert "run_as_root_quiet() {" in docker_text
    assert "run_as_root_with_dots() {" in docker_text
    assert "run_as_root_with_dots_timeout() {" in docker_text
    assert "printf '.' >&2" in docker_text
    assert "resolve_system_apt_mirror_url() {" in docker_text
    assert "install_docker_prerequisites_with_optional_mirror() {" in docker_text
    assert "install_docker_prerequisites_from_apt() {" in docker_text
    assert 'apt-get "${apt_args[@]}" install -y ca-certificates curl gnupg lsb-release' in docker_text
    assert (
        "deb http://security.ubuntu.com/ubuntu ${codename}-security main restricted universe multiverse" in docker_text
    )
    assert "install_docker_from_aliyun_apt() {" in docker_text
    assert "configure_docker_aliyun_apt_repository() {" in docker_text
    assert "remove_conflicting_docker_packages() {" in docker_text
    assert "https://mirrors.aliyun.com/docker-ce/linux/${distro}/gpg" in docker_text
    assert "https://mirrors.aliyun.com/docker-ce/linux/${distro}" in docker_text
    assert "\\$(lsb_release -cs) stable" in docker_text
    assert "docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin" in docker_text
    assert "configure_docker_registry_mirrors() {" in docker_text
    assert '"registry-mirrors"' in docker_text
    assert "install_docker_from_convenience_script() {" in docker_text
    assert "--retry 5 --retry-all-errors --connect-timeout 10" in docker_text
    assert "--max-time 60 https://mirrors.aliyun.com/docker-ce/linux/${distro}/gpg" in docker_text
    assert "release_metadata_curl() {" in download_text
    assert "release_asset_curl() {" in download_text
    assert "AERISUN_EXPECTED_INSTALL_BUNDLE_SHA256" in download_text
    assert "AERISUN_EXPECTED_UPDATE_TRUSTED_PUBLIC_KEY_B64" in download_text
    assert "AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64" in download_text
    assert "--connect-timeout 10 --max-time 45" in download_text
    assert "--connect-timeout 10 --max-time 180" in download_text
    assert 'log_warn "下载 ${asset_name} 失败：${url}"' in download_text
    assert 'log_warn "正在回退到下一个分发源：${base_urls[$((idx + 1))]%/}/${asset_name}"' in download_text
    assert "bootstrap_metadata_curl() {" in install_text
    assert "bootstrap_asset_curl() {" in install_text
    assert "--connect-timeout 10 --max-time 45" in install_text
    assert "--connect-timeout 10 --max-time 180" in install_text
    assert "正在准备回退" in install_text
    assert "正在回退到 GitHub Release API" in install_text
    assert "__AERISUN_APP_ROOT__" in service_text
    assert "__AERISUN_COMPOSE_PROJECT_NAME__" in service_text
    assert "__AERISUN_RENDERED_COMPOSE_FILE__" in service_text
    assert (
        'SERINO_PROXY_FIREWALL_UNIT="${SERINO_PROXY_FIREWALL_UNIT:-mihomo-docker-proxy-firewall.service}"'
        in common_text
    )
    assert (
        'SERINO_PROXY_FIREWALL_DROPIN_NAME="${SERINO_PROXY_FIREWALL_DROPIN_NAME:-proxy-firewall.conf}"' in common_text
    )
    assert "install_proxy_firewall_systemd_dropin" in common_text
    assert "ExecStartPost=/bin/systemctl restart %s" in common_text
    assert "__SERINO_SYSTEMD_UNIT__" in upgrade_service_text
    assert "__SERINO_BIN_LINK__" in upgrade_service_text
    assert "ExecStart=__SERINO_BIN_LINK__ upgrade --check" in upgrade_service_text
    assert "ExecStart=__SERINO_BIN_LINK__ upgrade\n" not in upgrade_service_text
    assert "ExecStart=__SERINO_BIN_LINK__ updater run" in updater_service_text
    assert "OnCalendar=hourly" in updater_timer_text
    assert "Persistent=true" in updater_timer_text
    assert "DirectoryNotEmpty=__SERINO_UPDATE_REQUESTS_DIR__" in updater_path_text
    assert "Unit=__SERINO_SYSTEMD_UPDATER_SERVICE__" in updater_path_text
    assert '"alg": "rsa-sha256"' in package_text
    assert "AERISUN_UPDATE_SIGNING_REQUIRED" in package_text
    assert "AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64" in package_text
    assert "AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64" in package_text
    assert '"trusted_public_key_b64": trusted_public_key_b64 or None' in package_text
    assert "update-trusted-public-key.b64" in package_text
    assert '"-verify"' in package_text
    assert '"latest.json"' in package_text
    assert '"release.json"' in package_text
    assert '"release-notes.md"' in package_text
    assert "update-trusted-public-key.b64" in upload_text
    assert "Resolve GitHub release notes" in workflow_text
    assert 'gh api "repos/${GITHUB_REPOSITORY}/releases/tags/${RELEASE_TAG}"' in workflow_text
    assert 'if notes_body="$(gh api "repos/${GITHUB_REPOSITORY}/releases/tags/${RELEASE_TAG}"' in workflow_text
    assert 'echo "GitHub Release ${RELEASE_TAG} not found; continuing without release notes."' in workflow_text
    assert "AERISUN_RELEASE_NOTES_FILE" in workflow_text
    assert 'AERISUN_UPDATE_SIGNING_REQUIRED: "true"' in workflow_text
    assert "secrets.AERISUN_UPDATE_SIGNING_PRIVATE_KEY_B64" in workflow_text
    assert "vars.AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64" in workflow_text
    assert "vars.AERISUN_UPDATE_SIGNATURE_KEY_ID" in workflow_text
    assert "${DEV_INSTALL_BASE_URL}/update-trusted-public-key.b64" in workflow_text
    assert "${BINFEN_INSTALL_BASE_URL}/update-trusted-public-key.b64" in workflow_text
    assert 'cat > "${DIST_DIR}/latest.env" <<EOF' in package_text
    assert "AERISUN_INSTALL_CHANNEL=${INSTALL_CHANNEL}" in package_text
    assert 'render_bootstrap_script "${DIST_DIR}/install.latest.sh"' in package_text
    assert 'render_bootstrap_script "${DIST_DIR}/install.sh"' in package_text
    assert 'API_IMAGE_NAME="serino-dev-api"' in package_text
    assert "run_backend_python()" in runtime_lib_text
    assert "run_backend_alembic()" in runtime_lib_text
    assert "run_backend_uvicorn()" in runtime_lib_text
    assert "ensure_runtime_identity()" in runtime_lib_text
    assert "NSS_WRAPPER_PASSWD" in runtime_lib_text
    assert "LD_PRELOAD" in runtime_lib_text
    assert 'source "${SCRIPT_DIR}/runtime-lib.sh"' in backend_bootstrap_text
    assert "run_backend_alembic upgrade head" in backend_bootstrap_text
    assert 'bash "${SCRIPT_DIR}/data-migrate.sh" apply --mode blocking --progress' in backend_bootstrap_text
    assert "生产运行时不会在应用启动阶段自动执行 baseline 或数据迁移。" in backend_bootstrap_text
    assert 'source "${SCRIPT_DIR}/runtime-lib.sh"' in backend_serve_text
    assert 'run_backend_uvicorn "${UVICORN_ARGS[@]}"' in backend_serve_text
    assert 'command = [sys.executable, "-m", "alembic", "upgrade", "head"]' in backend_migrate_text
    assert 'print(".", end="", flush=True)' in backend_migrate_text
    assert "apply_production_baseline" in backend_baseline_prod_text
    assert "ensure_first_boot_default_admin(is_first_boot=True)" in backend_first_admin_prod_text
    assert "apply_pending_data_migrations" in backend_data_migrate_text
    assert "schedule_pending_background_data_migrations" in backend_data_migrate_text
    assert not (PROJECT_ROOT / "backend/scripts/bootstrap-prod.sh").exists()
    assert not (PROJECT_ROOT / "backend/scripts/backfill.sh").exists()
    assert '@base_router.get("/livez"' in backend_site_api_text
    assert '@base_router.get("/readyz"' in backend_site_api_text
    assert '@base_router.get("/healthz"' in backend_site_api_text
    assert "background_task = asyncio.create_task(background_services.start()" in backend_bootstrap_core_text
    assert "await start_visit_record_worker()" in backend_bootstrap_core_text
    assert "run_pending_backfills()" not in backend_bootstrap_core_text
    assert "duration_ms=" not in backend_bootstrap_core_text
    assert 'logger.info("Application infrastructure ready in %.2fms"' in backend_bootstrap_core_text
    assert 'logger.info("Background services started in %.2fms"' in backend_bootstrap_core_text
    settings_text = read_project_file("backend/src/aerisun/core/settings.py")
    assert 'if self.environment == "production" and store_dir == legacy_store_dir:' in settings_text
    assert "self.store_dir = PRODUCTION_STORE_ROOT" in settings_text
    assert 'self.workflow_db_path = under_store(self.workflow_db_path, "langgraph.db")' in settings_text
    assert 'self.backup_sync_tmp_dir = under_store(self.backup_sync_tmp_dir, ".backup-sync-tmp")' in settings_text
    start_block = backend_task_manager_text.split("async def start(self) -> None:", 1)[1].split(
        "def _snapshot_daily_traffic", 1
    )[0]
    assert "record_daily_traffic_snapshot(session)" not in start_block
    assert "uv sync --frozen --no-dev --no-editable" in backend_dockerfile_text
    assert "libnss-wrapper" in backend_dockerfile_text
    assert 'CMD ["/bin/bash", "/app/backend/scripts/bootstrap.sh"]' in backend_dockerfile_text
    assert 'command: ["/bin/bash", "/app/backend/scripts/bootstrap.sh"]' not in compose_text
    assert 'command: ["/bin/bash", "/app/backend/scripts/serve.sh"]' not in compose_text
    assert 'command: ["/bin/bash", "/app/backend/scripts/bootstrap.sh"]' not in dev_compose_text
    assert "mkdir -p /app/node_modules/@waline/vercel/runtime/config" in waline_dockerfile_text
    assert "touch /app/node_modules/@waline/vercel/runtime/config/production.json" in waline_dockerfile_text
    assert "chmod 0777 /app/node_modules/@waline/vercel/runtime/config" in waline_dockerfile_text
    assert "chmod 0666 /app/node_modules/@waline/vercel/runtime/config/production.json" in waline_dockerfile_text
    assert "chown -R 1001:1001 /app" in waline_dockerfile_text
    waline_block = compose_text.split("  waline:\n", 1)[1].split("\n  caddy:\n", 1)[0]
    assert 'user: "${SERINO_RUNTIME_UID:-1001}:${SERINO_RUNTIME_GID:-1001}"' not in waline_block
    assert 'run_as_root systemctl enable "${SERINO_SYSTEMD_UNIT}" >/dev/null 2>&1' in docker_text
    assert 'run_as_root systemctl start "${SERINO_SYSTEMD_UNIT}" >/dev/null 2>&1' in docker_text
    assert 'run_as_root systemctl is-active --quiet "${SERINO_SYSTEMD_UNIT}"' in docker_text
    assert "run_as_root systemctl enable --now docker >/dev/null 2>&1" in docker_text
    assert 'run_as_root systemctl enable --now "${SERINO_SYSTEMD_UPDATER_TIMER}"' in docker_text
    assert 'run_as_root systemctl enable --now "${SERINO_SYSTEMD_UPDATER_PATH}"' in docker_text
    assert '"${SERINO_SYSTEMD_UPDATER_SERVICE}"' in docker_text
    assert '"${SERINO_SYSTEMD_UPDATER_TIMER}"' in docker_text
    assert '"${SERINO_SYSTEMD_UPDATER_PATH}"' in docker_text
    assert 'upgrade --ready-timeout "${UPDATER_READY_TIMEOUT}" "${target_version}"' in updater_text
    assert 'upgrade --check "${target_version}"' in updater_text
    assert 'AERISUN_EXPECTED_INSTALL_BUNDLE_SHA256="${verified_bundle_sha256}"' in updater_text
    assert 'AERISUN_EXPECTED_UPDATE_TRUSTED_PUBLIC_KEY_B64="${verified_trusted_public_key_b64}"' in updater_text
    assert "updater_verified_trusted_public_key_for_target() {" in updater_text
    assert "if ! wait_for_release_ready; then" in install_text


def test_dev_channel_does_not_require_a_second_installer_entrypoint():
    assert not (PROJECT_ROOT / "installer/install-dev.sh").exists()


def test_systemd_upgrade_job_renders_check_only_upgrade_command(tmp_path: Path):
    systemd_dir = tmp_path / "systemd"
    systemd_dir.mkdir()

    completed = run_installer_bash(
        f"""
source installer/lib/common.sh

SERINO_BIN_LINK='{tmp_path}/bin/sercli'
SERINO_SYSTEMD_UNIT='serino.service'
SERINO_SYSTEMD_UPGRADE_SERVICE='serino-upgrade.service'
SERINO_SYSTEMD_UPGRADE_TIMER='serino-upgrade.timer'

make_temp_file() {{
  mktemp '{tmp_path}/unit.XXXXXX'
}}

run_as_root() {{
  if [[ "$1" == systemctl && "$2" == cat ]]; then
    return 1
  fi
  if [[ "$1" == rm && "$2" == "-f" ]]; then
    return 0
  fi
  if [[ "$1" == install && "$2" == "-m" && "$3" == "0644" ]]; then
    cp "$4" '{systemd_dir}'/"$(basename "$5")"
    return 0
  fi
  if [[ "$1" == systemctl && "$2" == "daemon-reload" ]]; then
    return 0
  fi
  "$@"
}}

install_systemd_units '{PROJECT_ROOT}'
cat '{systemd_dir}/serino-upgrade.service'
"""
    )

    assert f"ExecStart={tmp_path}/bin/sercli upgrade --check" in completed
    assert f"ExecStart={tmp_path}/bin/sercli upgrade\n" not in completed


def test_proxy_firewall_dropin_restarts_firewall_unit_after_serino_start(tmp_path: Path):
    systemd_dir = tmp_path / "systemd"
    systemd_dir.mkdir()

    completed = run_installer_bash(
        f"""
source installer/lib/common.sh

SERINO_SYSTEMD_UNIT='serino.service'
SERINO_PROXY_FIREWALL_UNIT='mihomo-docker-proxy-firewall.service'
SERINO_PROXY_FIREWALL_DROPIN_NAME='proxy-firewall.conf'

make_temp_file() {{
  mktemp '{tmp_path}/dropin.XXXXXX'
}}

map_systemd_path() {{
  local target="$1"
  printf '%s/%s' '{systemd_dir}' "${{target#/etc/systemd/system/}}"
}}

run_as_root() {{
  if [[ "$1" == systemctl && "$2" == cat && "$3" == "${{SERINO_PROXY_FIREWALL_UNIT}}" ]]; then
    return 0
  fi
  if [[ "$1" == install && "$2" == "-d" ]]; then
    mkdir -p "$(map_systemd_path "${{@: -1}}")"
    return 0
  fi
  if [[ "$1" == install && "$2" == "-m" && "$3" == "0644" ]]; then
    mkdir -p "$(dirname "$(map_systemd_path "$5")")"
    cp "$4" "$(map_systemd_path "$5")"
    return 0
  fi
  printf 'unexpected run_as_root call: %s\\n' "$*" >&2
  return 1
}}

install_proxy_firewall_systemd_dropin
cat '{systemd_dir}/serino.service.d/proxy-firewall.conf'
"""
    ).strip()

    assert completed == "[Service]\nExecStartPost=/bin/systemctl restart mihomo-docker-proxy-firewall.service"


def test_proxy_firewall_dropin_is_removed_when_firewall_unit_is_missing(tmp_path: Path):
    systemd_dir = tmp_path / "systemd"
    stale_dropin = systemd_dir / "serino.service.d" / "proxy-firewall.conf"
    stale_dropin.parent.mkdir(parents=True)
    stale_dropin.write_text("[Service]\nExecStartPost=/bin/systemctl restart stale.service\n", encoding="utf-8")

    run_installer_bash(
        f"""
source installer/lib/common.sh

SERINO_SYSTEMD_UNIT='serino.service'
SERINO_PROXY_FIREWALL_UNIT='mihomo-docker-proxy-firewall.service'
SERINO_PROXY_FIREWALL_DROPIN_NAME='proxy-firewall.conf'

run_as_root() {{
  if [[ "$1" == systemctl && "$2" == cat && "$3" == "${{SERINO_PROXY_FIREWALL_UNIT}}" ]]; then
    return 1
  fi
  if [[ "$1" == rm && "$2" == "-f" ]]; then
    local target="$3"
    rm -f '{systemd_dir}'/"${{target#/etc/systemd/system/}}"
    return 0
  fi
  printf 'unexpected run_as_root call: %s\\n' "$*" >&2
  return 1
}}

install_proxy_firewall_systemd_dropin
"""
    )

    assert not stale_dropin.exists()


def test_release_workflow_refreshes_bitiful_installer_cache():
    workflow_text = read_project_file(".github/workflows/ci.yml")
    refresh_script_text = read_project_file("scripts/refresh-bitiful-cdn.sh")

    assert (
        'BINFEN_CDN_API_ENDPOINT="${BINFEN_CDN_API_ENDPOINT:-https://api.bitiful.com/cdn/cache/refresh}"'
        in refresh_script_text
    )
    assert 'BINFEN_CDN_API_TOKEN="${BINFEN_CDN_API_TOKEN:?BINFEN_CDN_API_TOKEN is required}"' in refresh_script_text
    assert "curl --fail-with-body --silent --show-error \\" in refresh_script_text
    assert "bash ./scripts/refresh-bitiful-cdn.sh \\" in workflow_text
    assert '"${BINFEN_INSTALL_BASE_URL}/install.sh"' in workflow_text
    assert '"${BINFEN_INSTALL_BASE_URL}/latest.env"' in workflow_text
    assert '"${DEV_INSTALL_BASE_URL}/install.sh"' in workflow_text
    assert '"${DEV_INSTALL_BASE_URL}/latest.env"' in workflow_text
    assert "if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')" in workflow_text
    assert (
        "if: ${{ always() && (github.event_name == 'workflow_dispatch' || github.event_name == 'release') && needs.release-readiness.result == 'success' && needs.docker-build.result == 'success' }}"
        in workflow_text
    )
    assert (
        "if: ${{ always() && (github.event_name == 'workflow_dispatch' || github.event_name == 'release') && needs.docker-smoke.result == 'success' }}"
        in workflow_text
    )
    assert (
        "if: ${{ always() && (github.event_name == 'workflow_dispatch' || github.event_name == 'release') && needs.docker-publish.result == 'success' }}"
        in workflow_text
    )


def test_installer_systemd_units_switch_to_serino_names():
    assert (PROJECT_ROOT / "installer/systemd/serino.service").exists()
    assert (PROJECT_ROOT / "installer/systemd/serino-upgrade.service").exists()
    assert (PROJECT_ROOT / "installer/systemd/serino-upgrade.timer").exists()
    assert (PROJECT_ROOT / "installer/systemd/serino-updater.service").exists()
    assert (PROJECT_ROOT / "installer/systemd/serino-updater.timer").exists()
    assert (PROJECT_ROOT / "installer/systemd/serino-updater.path").exists()
    assert not (PROJECT_ROOT / "installer/systemd/aerisun-upgrade.service").exists()
    assert not (PROJECT_ROOT / "installer/systemd/aerisun-upgrade.timer").exists()


def test_project_readme_and_backend_metadata_do_not_keep_scaffold_values():
    readme_text = read_project_file("README.md")
    backend_metadata = tomllib.loads(read_project_file("backend/pyproject.toml"))
    frontend_package = json.loads(read_project_file("frontend/package.json"))
    admin_package = json.loads(read_project_file("admin/package.json"))

    assert frontend_package["dependencies"]["react"].startswith("^19.")
    assert admin_package["dependencies"]["react"].startswith("^19.")
    assert "Frontend-React_19-blue.svg" in readme_text
    assert "Frontend-React_18-blue.svg" not in readme_text
    assert "raw.githubusercontent.com/Aerisun/Serino/main/docker-compose.release.yml" in readme_text
    assert "raw.githubusercontent.com/Aerisun/Serino/main/.env.production.local.example" in readme_text
    assert "raw.githubusercontent.com/Aerisun/Aerisun" not in readme_text
    assert backend_metadata["project"]["description"] == "Serino FastAPI backend service"


def test_legacy_backend_process_scripts_are_removed():
    assert not (PROJECT_ROOT / "backend/scripts/dev-backend.sh").exists()
    assert not (PROJECT_ROOT / "backend/scripts/dev-waline.sh").exists()
    assert not (PROJECT_ROOT / "backend/scripts/process-env.sh").exists()
    assert not (PROJECT_ROOT / "backend/scripts/backup.sh").exists()
    assert not (PROJECT_ROOT / "backend/scripts/restore.sh").exists()
    assert not (PROJECT_ROOT / "backend/litestream.yml.template").exists()

    tracked_texts = [
        read_project_file("README.md"),
        read_project_file("Makefile"),
        read_project_file("scripts/dev-start.sh"),
        read_project_file("scripts/dev-smoke.sh"),
        read_project_file("scripts/sync-orval.sh"),
        read_project_file("backend/scripts/bootstrap.sh"),
    ]

    for text in tracked_texts:
        assert "dev-backend.sh" not in text
        assert "dev-waline.sh" not in text
        assert "process-env.sh" not in text
