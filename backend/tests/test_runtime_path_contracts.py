from __future__ import annotations

import json
import subprocess
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
    assert "curl:--fail --silent --show-error http://127.0.0.1:18000/api/v1/site/readyz" in output


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
    assert completed.stdout.strip() == "data-migrate.sh apply --mode blocking --progress"
    assert completed.stderr.strip() == "[INFO] 🛠️ 正在执行版本化数据迁移..."


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
    assert "AERISUN_API_BASE_PATH: ${AERISUN_API_BASE_PATH:-/api}" in compose_text
    assert "AERISUN_ADMIN_BASE_PATH: ${AERISUN_ADMIN_BASE_PATH:-/admin/}" in compose_text
    assert "AERISUN_WALINE_BASE_PATH: ${AERISUN_WALINE_BASE_PATH:-/waline}" in compose_text
    assert "AERISUN_FRONTEND_DIST_DIR: ${AERISUN_FRONTEND_DIST_DIR:-/srv/aerisun/frontend}" in compose_text
    assert "AERISUN_ADMIN_DIST_DIR: ${AERISUN_ADMIN_DIST_DIR:-/srv/aerisun/admin}" in compose_text
    assert '- "127.0.0.1:${AERISUN_PORT:-8000}:${AERISUN_PORT:-8000}"' in compose_text
    assert "{$AERISUN_PORT:8000}" in caddy_text
    assert "{$AERISUN_API_BASE_PATH:/api}" in caddy_text
    assert "{$AERISUN_ADMIN_BASE_PATH:/admin/}" in caddy_text
    assert "{$AERISUN_WALINE_BASE_PATH:/waline}" in caddy_text
    assert "{$AERISUN_FRONTEND_DIST_DIR:/srv/aerisun/frontend}" in caddy_text
    assert "{$AERISUN_ADMIN_DIST_DIR:/srv/aerisun/admin}" in caddy_text
    assert "handle /bootstrap.js" in caddy_text

    assert 'HEALTHCHECK_PATH="${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/readyz}"' in smoke_text
    assert 'ADMIN_BASE_PATH="$(ensure_trailing_slash "${AERISUN_ADMIN_BASE_PATH:-/admin/}")"' in smoke_text
    assert 'WALINE_BASE_PATH="$(strip_trailing_slash "${AERISUN_WALINE_BASE_PATH:-/waline}")"' in smoke_text
    assert "AERISUN_DOMAIN=http://${SITE_HOST}" in smoke_text
    assert 'LOCAL_IMAGE_REGISTRY="${AERISUN_SMOKE_IMAGE_REGISTRY:-serino-smoke-local}"' in smoke_text
    assert "AERISUN_IMAGE_REGISTRY=${LOCAL_IMAGE_REGISTRY}" in smoke_text
    assert "WALINE_JWT_TOKEN=smoke-0123456789abcdef0123456789abcdef" in smoke_text
    assert "AERISUN_DATA_BACKFILL_ENABLED" not in smoke_text

    assert 'healthcheck_path="${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/readyz}"' in dev_smoke_text
    assert 'admin_base_path="${AERISUN_ADMIN_BASE_PATH:-/admin/}"' in dev_smoke_text
    backend_health_url = (
        'backend_health_url="http://127.0.0.1:${AERISUN_PORT:-8000}${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/readyz}"'
    )
    assert backend_health_url in dev_start_text
    assert 'const apiBasePath = stripTrailingSlash(env.AERISUN_API_BASE_PATH ?? "/api");' in frontend_vite_text
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
    package_text = read_project_file("scripts/package-installer.sh")
    runtime_lib_text = read_project_file("backend/scripts/runtime-lib.sh")
    backend_bootstrap_text = read_project_file("backend/scripts/bootstrap.sh")
    backend_serve_text = read_project_file("backend/scripts/serve.sh")
    backend_migrate_text = read_project_file("backend/scripts/migrate.sh")
    backend_baseline_prod_text = read_project_file("backend/scripts/baseline-prod.sh")
    backend_first_admin_prod_text = read_project_file("backend/scripts/first-admin-prod.sh")
    backend_data_migrate_text = read_project_file("backend/scripts/data-migrate.sh")
    backend_bootstrap_prod_text = read_project_file("backend/scripts/bootstrap-prod.sh")
    backend_backfill_text = read_project_file("backend/scripts/backfill.sh")
    backend_site_api_text = read_project_file("backend/src/aerisun/api/site.py")
    backend_bootstrap_core_text = read_project_file("backend/src/aerisun/core/bootstrap.py")
    backend_task_manager_text = read_project_file("backend/src/aerisun/core/task_manager.py")
    dev_compose_text = read_project_file("docker-compose.yml")
    backend_dockerfile_text = read_project_file("backend/Dockerfile")
    waline_dockerfile_text = read_project_file("Dockerfile.waline")

    assert 'SERINO_CONFIG_ROOT="${SERINO_CONFIG_ROOT:-/etc/serino}"' in common_text
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
    assert 'AERISUN_HTTP_PORT="${AERISUN_HTTP_PORT:-80}"' in common_text
    assert 'AERISUN_HTTPS_PORT="${AERISUN_HTTPS_PORT:-443}"' in common_text
    assert "make_temp_file() {" in common_text
    assert "make_root_temp_file_in_dir() {" in common_text
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
    assert 'exec bash "${INSTALLER_ROOT}/doctor.sh" "$@"' in sercli_text
    assert 'main "${SERCLI_MAIN_ARGS[@]}"' in sercli_text
    assert "cmd_migrate() {" in sercli_text
    assert "cmd_ps() {" in sercli_text
    assert "cmd_start() {" in sercli_text
    assert "cmd_stop() {" in sercli_text
    assert 'record_check "fail" "env.bootstrap_cleanup"' in doctor_text
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
    assert 'local channel="${AERISUN_INSTALL_CHANNEL:-stable}"' in install_text
    assert "validate_release_compose_configuration" in install_text
    assert "if ! compose pull; then" in install_text
    assert "if ! run_release_migrations; then" in install_text
    assert "if ! run_release_baseline; then" in install_text
    assert "if ! run_release_data_migrations blocking; then" in install_text
    assert "if ! run_release_admin_bootstrap; then" in install_text
    assert "if ! enable_serino_service; then" in install_text
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
    assert "__SERINO_SYSTEMD_UNIT__" in upgrade_service_text
    assert "__SERINO_BIN_LINK__" in upgrade_service_text
    assert 'cat > "${DIST_DIR}/latest.env" <<EOF' in package_text
    assert "AERISUN_INSTALL_CHANNEL=${INSTALL_CHANNEL}" in package_text
    assert 'render_bootstrap_script "${DIST_DIR}/install.latest.sh"' in package_text
    assert 'render_bootstrap_script "${DIST_DIR}/install.sh"' in package_text
    assert 'API_IMAGE_NAME="serino-dev-api"' in package_text
    assert "run_backend_python()" in runtime_lib_text
    assert "run_backend_alembic()" in runtime_lib_text
    assert "run_backend_uvicorn()" in runtime_lib_text
    assert 'source "${SCRIPT_DIR}/runtime-lib.sh"' in backend_bootstrap_text
    assert "run_backend_alembic upgrade head" in backend_bootstrap_text
    assert "生产运行时不会在应用启动阶段自动执行 baseline 或数据迁移。" in backend_bootstrap_text
    assert 'source "${SCRIPT_DIR}/runtime-lib.sh"' in backend_serve_text
    assert 'run_backend_uvicorn "${UVICORN_ARGS[@]}"' in backend_serve_text
    assert 'command = [sys.executable, "-m", "alembic", "upgrade", "head"]' in backend_migrate_text
    assert 'print(".", end="", flush=True)' in backend_migrate_text
    assert "apply_production_baseline" in backend_baseline_prod_text
    assert "ensure_first_boot_default_admin(is_first_boot=True)" in backend_first_admin_prod_text
    assert "apply_pending_data_migrations" in backend_data_migrate_text
    assert "schedule_pending_background_data_migrations" in backend_data_migrate_text
    assert 'exec /bin/bash "${SCRIPT_DIR}/baseline-prod.sh" "$@"' in backend_bootstrap_prod_text
    assert 'exec /bin/bash "${SCRIPT_DIR}/data-migrate.sh" apply --mode blocking "$@"' in backend_backfill_text
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
    assert "if ! wait_for_release_ready; then" in install_text


def test_dev_channel_does_not_require_a_second_installer_entrypoint():
    assert not (PROJECT_ROOT / "installer/install-dev.sh").exists()


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


def test_installer_systemd_units_switch_to_serino_names():
    assert (PROJECT_ROOT / "installer/systemd/serino.service").exists()
    assert (PROJECT_ROOT / "installer/systemd/serino-upgrade.service").exists()
    assert (PROJECT_ROOT / "installer/systemd/serino-upgrade.timer").exists()
    assert not (PROJECT_ROOT / "installer/systemd/aerisun-upgrade.service").exists()
    assert not (PROJECT_ROOT / "installer/systemd/aerisun-upgrade.timer").exists()


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
