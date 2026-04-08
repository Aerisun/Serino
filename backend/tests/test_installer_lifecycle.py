from __future__ import annotations

import os
import subprocess
import tarfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_project_bash(script: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", script],
        cwd=PROJECT_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def test_installer_scripts_are_source_safe() -> None:
    completed = run_project_bash(
        """
source installer/install.sh
source installer/upgrade.sh
source installer/uninstall.sh
source scripts/release-smoke-gate.sh
printf 'ok\\n'
"""
    )

    assert completed.stdout.strip() == "ok"


def test_install_script_supports_stdin_bootstrap_execution(tmp_path: Path) -> None:
    bootstrap_root = tmp_path / "bootstrap"
    installer_root = tmp_path / "bundle" / "installer"
    installer_root.mkdir(parents=True)

    (bootstrap_root / "v9.9.9").mkdir(parents=True)
    (bootstrap_root / "latest.env").write_text(
        "AERISUN_INSTALL_VERSION=v9.9.9\n",
        encoding="utf-8",
    )
    bundled_install = installer_root / "install.sh"
    bundled_install.write_text(
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        'if [[ "${1:-}" == "--bundled" ]]; then\n'
        "  shift\n"
        "fi\n"
        "printf 'bundled-ok\\n'\n",
        encoding="utf-8",
    )
    bundled_install.chmod(0o755)

    with tarfile.open(bootstrap_root / "v9.9.9" / "aerisun-installer-bundle.tar.gz", "w:gz") as archive:
        archive.add(installer_root, arcname="installer")

    env = os.environ.copy()
    env["AERISUN_INSTALL_BASE_URL"] = f"file://{bootstrap_root}"
    env["AERISUN_INSTALL_CHANNEL"] = "stable"
    env["AERISUN_INSTALL_BUNDLE_NAME"] = "aerisun-installer-bundle.tar.gz"

    install_script = (PROJECT_ROOT / "installer" / "install.sh").read_text(encoding="utf-8")
    completed = subprocess.run(
        ["bash"],
        cwd=PROJECT_ROOT,
        input=install_script,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.stdout.strip() == "bundled-ok"


def test_install_main_runs_schema_baseline_and_background_pipeline_in_order() -> None:
    completed = run_project_bash(
        """
source installer/install.sh

record() {
  printf '%s\\n' "$1"
}

require_supported_linux() { :; }
require_root_or_sudo() { :; }
prepare_install_target() { record prepare_install_target; }
ensure_port_available() { record "ensure_port_available:$1"; }
resolve_release_tag() { printf 'v1.2.3'; }
make_temp_file() { printf '/tmp/manifest'; }
load_release_manifest() {
  record "load_release_manifest:$1"
  AERISUN_IMAGE_REGISTRY='registry.example.com/serino'
  AERISUN_IMAGE_TAG='v1.2.3'
}
prompt_access_mode() { AERISUN_INSTALL_ACCESS_MODE='ip'; record prompt_access_mode; }
prompt_install_host() { AERISUN_INSTALL_HOST='127.0.0.1'; record prompt_install_host; }
prompt_bootstrap_admin_credentials() {
  AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE='admin'
  AERISUN_BOOTSTRAP_ADMIN_PASSWORD_VALUE='pass'
  record prompt_bootstrap_admin_credentials
}
confirm_install_settings() { record confirm_install_settings; }
ensure_docker_installed() { record ensure_docker_installed; }
configure_local_firewall() { record configure_local_firewall; }
ensure_service_user() { record ensure_service_user; }
resolve_active_registry() { printf '%s' "$1"; }
build_runtime_configuration() {
  record "build_runtime_configuration:$1:$2:$4"
  AERISUN_DOMAIN_VALUE='http://127.0.0.1'
  AERISUN_SITE_URL_VALUE='http://127.0.0.1'
  AERISUN_WALINE_SERVER_URL_VALUE='http://127.0.0.1/waline'
}
install_release_payload() { record install_release_payload; }
write_production_env() { record write_production_env; }
normalize_production_env_file() { record normalize_production_env_file; }
daemon_reload() { record daemon_reload; }
validate_release_compose_configuration() { record validate_release_compose_configuration; }
compose() { record "compose:$*"; }
run_release_migrations() { record run_release_migrations; }
run_release_baseline() { record run_release_baseline; }
run_release_data_migrations() { record "run_release_data_migrations:$1"; }
run_release_admin_bootstrap() { record run_release_admin_bootstrap; }
enable_serino_service() { record enable_serino_service; }
wait_for_release_ready() { record wait_for_release_ready; }
verify_default_admin_login() { record verify_default_admin_login; }
schedule_release_background_data_migrations() { record schedule_release_background_data_migrations; }
unset_env_value() { record "unset_env_value:$2"; }
print_install_summary() { record "print_install_summary:$1"; }

main
"""
    )

    assert completed.stdout.strip().splitlines() == [
        "prepare_install_target",
        "ensure_port_available:80",
        "ensure_port_available:443",
        "load_release_manifest:v1.2.3",
        "prompt_access_mode",
        "prompt_install_host",
        "prompt_bootstrap_admin_credentials",
        "confirm_install_settings",
        "ensure_docker_installed",
        "configure_local_firewall",
        "ensure_service_user",
        "build_runtime_configuration:ip:127.0.0.1:v1.2.3",
        "install_release_payload",
        "write_production_env",
        "normalize_production_env_file",
        "daemon_reload",
        "validate_release_compose_configuration",
        "compose:pull",
        "run_release_migrations",
        "run_release_baseline",
        "run_release_data_migrations:blocking",
        "run_release_admin_bootstrap",
        "enable_serino_service",
        "wait_for_release_ready",
        "verify_default_admin_login",
        "schedule_release_background_data_migrations",
        "unset_env_value:AERISUN_BOOTSTRAP_ADMIN_USERNAME_B64",
        "unset_env_value:AERISUN_BOOTSTRAP_ADMIN_PASSWORD_B64",
        "print_install_summary:http://127.0.0.1/",
    ]


def test_install_main_cleans_up_when_blocking_data_migration_fails() -> None:
    completed = run_project_bash(
        """
source installer/install.sh

record() {
  printf '%s\\n' "$1"
}

require_supported_linux() { :; }
require_root_or_sudo() { :; }
prepare_install_target() { :; }
ensure_port_available() { :; }
resolve_release_tag() { printf 'v1.2.3'; }
make_temp_file() { printf '/tmp/manifest'; }
load_release_manifest() {
  AERISUN_IMAGE_REGISTRY='registry.example.com/serino'
  AERISUN_IMAGE_TAG='v1.2.3'
}
prompt_access_mode() { AERISUN_INSTALL_ACCESS_MODE='ip'; }
prompt_install_host() { AERISUN_INSTALL_HOST='127.0.0.1'; }
prompt_bootstrap_admin_credentials() {
  AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE='admin'
  AERISUN_BOOTSTRAP_ADMIN_PASSWORD_VALUE='pass'
}
confirm_install_settings() { :; }
ensure_docker_installed() { :; }
configure_local_firewall() { :; }
ensure_service_user() { :; }
resolve_active_registry() { printf '%s' "$1"; }
build_runtime_configuration() {
  AERISUN_DOMAIN_VALUE='http://127.0.0.1'
  AERISUN_SITE_URL_VALUE='http://127.0.0.1'
  AERISUN_WALINE_SERVER_URL_VALUE='http://127.0.0.1/waline'
}
install_release_payload() { :; }
write_production_env() { :; }
normalize_production_env_file() { :; }
daemon_reload() { :; }
validate_release_compose_configuration() { :; }
compose() { :; }
run_release_migrations() { record run_release_migrations; }
run_release_baseline() { record run_release_baseline; }
run_release_data_migrations() {
  record "run_release_data_migrations:$1"
  return 1
}
print_service_start_failure_diagnostics() { record print_service_start_failure_diagnostics; }
cleanup_failed_installation() { record cleanup_failed_installation; }
die() {
  record "die:$*"
  exit 1
}

main
""",
        check=False,
    )

    assert completed.returncode == 1
    lines = completed.stdout.strip().splitlines()
    assert lines[:6] == [
        "run_release_migrations",
        "run_release_baseline",
        "run_release_data_migrations:blocking",
        "print_service_start_failure_diagnostics",
        "cleanup_failed_installation",
        "die:阻塞式数据迁移失败，安装已中止。可根据上面的报错信息修复后重试。",
    ]
    assert lines[6:] in ([], ["cleanup_failed_installation"])


def test_upgrade_check_only_runs_preflight_without_mutation() -> None:
    completed = run_project_bash(
        """
source installer/upgrade.sh

record() {
  printf '%s\\n' "$1"
}

require_supported_linux() { :; }
require_root_or_sudo() { :; }
ensure_supported_existing_installation() { :; }
ensure_service_user() { :; }
load_env_file() {
  AERISUN_IMAGE_REGISTRY='registry.example.com/current'
  AERISUN_IMAGE_TAG='v1.0.0'
}
run_upgrade_preflight() { record run_upgrade_preflight; }
resolve_release_tag() { printf '%s' "${AERISUN_INSTALL_VERSION:-v2.0.0}"; }
make_temp_file() { printf '/tmp/manifest'; }
load_release_manifest() {
  record "load_release_manifest:$1"
  AERISUN_IMAGE_REGISTRY='registry.example.com/next'
  AERISUN_IMAGE_TAG='v2.0.0'
}
download_release_asset() { record download_release_asset; }
stop_serino_service() { record stop_serino_service; }
backup_current_installation() { record backup_current_installation; }
install_release_payload() { record install_release_payload; }
set_env_value() { record "set_env_value:$2=$3"; }
normalize_production_env_file() { record normalize_production_env_file; }
validate_release_compose_configuration() { record validate_release_compose_configuration; }

main --check v2.0.0
"""
    )

    assert completed.stdout.strip().splitlines() == [
        "run_upgrade_preflight",
        "load_release_manifest:v2.0.0",
    ]


def test_upgrade_main_rolls_back_and_restarts_previous_release_on_failure() -> None:
    completed = run_project_bash(
        """
source installer/upgrade.sh

record() {
  printf '%s\\n' "$1"
}

require_supported_linux() { :; }
require_root_or_sudo() { :; }
ensure_supported_existing_installation() { :; }
ensure_service_user() { :; }
load_env_file() {
  AERISUN_IMAGE_REGISTRY='registry.example.com/current'
  AERISUN_IMAGE_TAG='v1.0.0'
}
run_upgrade_preflight() { record run_upgrade_preflight; }
resolve_release_tag() { printf '%s' "${AERISUN_INSTALL_VERSION:-v2.0.0}"; }
make_temp_file() { printf '/tmp/manifest'; }
make_temp_dir() { printf '/tmp/bundle'; }
load_release_manifest() {
  record "load_release_manifest:$1"
  AERISUN_IMAGE_REGISTRY='registry.example.com/next'
  AERISUN_IMAGE_TAG='v2.0.0'
}
download_release_asset() { record "download_release_asset:$1"; }
tar() { record "tar:$*"; }
date() { printf '20260408112233'; }
    stop_serino_service() { record stop_serino_service; }
    backup_current_installation() { record "backup_current_installation:$1"; }
    resolve_active_registry() {
      printf '%s' "$1"
    }
install_release_payload() { record install_release_payload; }
set_env_value() { record "set_env_value:$2=$3"; }
normalize_production_env_file() { record normalize_production_env_file; }
validate_release_compose_configuration() { record validate_release_compose_configuration; }
compose() {
  record "compose:$*"
}
run_release_migrations() { record run_release_migrations; }
run_release_data_migrations() {
  record "run_release_data_migrations:$1"
  return 1
}
enable_serino_service() { record enable_serino_service; }
wait_for_release_ready() { record wait_for_release_ready; }
print_service_start_failure_diagnostics() { record print_service_start_failure_diagnostics; }
restore_current_installation() { record "restore_current_installation:$1"; }
log_warn() { record "log_warn:$*"; }
die() {
  record "die:$*"
  exit 1
}

main v2.0.0
""",
        check=False,
    )

    assert completed.returncode == 1
    assert completed.stdout.strip().splitlines() == [
        "run_upgrade_preflight",
        "load_release_manifest:v2.0.0",
        "download_release_asset:v2.0.0",
        "tar:-xzf /tmp/bundle/aerisun-installer-bundle.tar.gz -C /tmp/bundle",
        "stop_serino_service",
        "backup_current_installation:/var/backups/serino/upgrade-20260408112233",
        "install_release_payload",
        "set_env_value:AERISUN_IMAGE_REGISTRY=registry.example.com/next",
        "set_env_value:AERISUN_IMAGE_TAG=v2.0.0",
        "normalize_production_env_file",
        "validate_release_compose_configuration",
        "compose:pull",
        "run_release_migrations",
        "run_release_data_migrations:blocking",
        "log_warn:升级失败，正在回滚。",
        "print_service_start_failure_diagnostics",
        "stop_serino_service",
        "restore_current_installation:/var/backups/serino/upgrade-20260408112233",
        "compose:pull",
        "enable_serino_service",
        "wait_for_release_ready",
        "die:升级失败，已回滚到旧版本。可执行 sercli doctor 与 sercli logs api waline caddy 查看诊断信息。",
    ]


def test_release_smoke_gate_runs_shell_backend_and_docker_steps_in_order() -> None:
    completed = run_project_bash(
        """
source scripts/release-smoke-gate.sh

run_shell_contract_checks() { printf 'shell\\n'; }
run_backend_ops_tests() { printf 'backend\\n'; }
run_docker_release_smoke() { printf 'docker\\n'; }

main
"""
    )

    assert completed.stdout.strip().splitlines() == ["shell", "backend", "docker"]
