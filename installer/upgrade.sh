#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/download.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/env.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/docker.sh"

UPTIME_STARTED_AT_FILENAME=".serino-uptime-started-at"

backup_current_installation() {
  local backup_dir="$1"
  run_as_root mkdir -p "${backup_dir}"
  path_is_file "${AERISUN_ENV_FILE}" && run_as_root cp -a "${AERISUN_ENV_FILE}" "${backup_dir}/serino.env"
  path_is_file "${AERISUN_COMPOSE_FILE}" && run_as_root cp -a "${AERISUN_COMPOSE_FILE}" "${backup_dir}/docker-compose.release.yml"
  path_is_file "${AERISUN_RENDERED_COMPOSE_FILE}" && run_as_root cp -a "${AERISUN_RENDERED_COMPOSE_FILE}" "${backup_dir}/docker-compose.runtime.yml"
  path_is_dir "${AERISUN_INSTALLER_DEST}" && run_as_root cp -a "${AERISUN_INSTALLER_DEST}" "${backup_dir}/installer"
  if path_is_dir "${AERISUN_DATA_DIR}"; then
    run_as_root tar -czf "${backup_dir}/data.tar.gz" -C "${AERISUN_DATA_DIR%/*}" "$(basename "${AERISUN_DATA_DIR}")"
  fi
}

restore_current_installation() {
  local backup_dir="$1"

  if [[ -f "${backup_dir}/serino.env" ]]; then
    run_as_root cp -a "${backup_dir}/serino.env" "${AERISUN_ENV_FILE}"
  fi
  if [[ -f "${backup_dir}/docker-compose.release.yml" ]]; then
    run_as_root cp -a "${backup_dir}/docker-compose.release.yml" "${AERISUN_COMPOSE_FILE}"
  fi
  if [[ -f "${backup_dir}/docker-compose.runtime.yml" ]]; then
    run_as_root cp -a "${backup_dir}/docker-compose.runtime.yml" "${AERISUN_RENDERED_COMPOSE_FILE}"
  else
    run_as_root rm -f "${AERISUN_RENDERED_COMPOSE_FILE}"
  fi
  if [[ -d "${backup_dir}/installer" ]]; then
    run_as_root rm -rf "${AERISUN_INSTALLER_DEST}"
    run_as_root cp -a "${backup_dir}/installer" "${AERISUN_INSTALLER_DEST}"
    run_as_root chown -R root:root "${AERISUN_INSTALLER_DEST}"
    run_as_root ln -sf "${AERISUN_INSTALLER_DEST}/bin/sercli" "${SERINO_BIN_LINK}"
    install_systemd_units "${backup_dir}"
  fi
  if [[ -f "${backup_dir}/data.tar.gz" ]]; then
    run_as_root rm -rf "${AERISUN_DATA_DIR}"
    run_as_root install -d -o "${SERINO_SERVICE_USER}" -g "${SERINO_SERVICE_GROUP}" -m 0750 "${AERISUN_DATA_DIR%/*}"
    run_as_root tar -xzf "${backup_dir}/data.tar.gz" -C "${AERISUN_DATA_DIR%/*}"
    run_as_root chown -R "${SERINO_SERVICE_USER}:${SERINO_SERVICE_GROUP}" "${AERISUN_DATA_DIR}"
  fi
  daemon_reload
}

run_upgrade_preflight() {
  bash "${SCRIPT_DIR}/doctor.sh"
}

current_api_started_at_epoch() {
  local container_id=""
  local started_at=""

  container_id="$(compose ps -q api 2>/dev/null | sed -n '1p' || true)"
  [[ -n "${container_id}" ]] || return 1

  started_at="$(run_as_root docker inspect --format '{{.State.StartedAt}}' "${container_id}" 2>/dev/null || true)"
  [[ -n "${started_at}" && "${started_at}" != "<no value>" ]] || return 1

  python3 - "${started_at}" <<'PY'
from __future__ import annotations

import sys
from datetime import datetime

raw = sys.argv[1].strip()
if raw.endswith("Z"):
    raw = f"{raw[:-1]}+00:00"
started_at = datetime.fromisoformat(raw).timestamp()
if started_at <= 0:
    raise SystemExit(1)
print(f"{started_at:.6f}")
PY
}

seed_persistent_uptime_marker() {
  local marker_path="${AERISUN_DATA_DIR}/${UPTIME_STARTED_AT_FILENAME}"
  local started_at_epoch=""

  if run_as_root test -s "${marker_path}"; then
    return 0
  fi

  started_at_epoch="$(current_api_started_at_epoch || true)"
  if [[ -z "${started_at_epoch}" ]]; then
    started_at_epoch="$(python3 - <<'PY'
from __future__ import annotations

import time

print(f"{time.time():.6f}")
PY
)"
  fi

  run_as_root install -d -o "${SERINO_SERVICE_USER}" -g "${SERINO_SERVICE_GROUP}" -m 0750 "${AERISUN_DATA_DIR}"
  run_as_root bash -lc '
    set -euo pipefail
    marker_path="$1"
    started_at_epoch="$2"
    service_user="$3"
    service_group="$4"

    if [[ -s "${marker_path}" ]]; then
      exit 0
    fi

    umask 027
    printf "%s\n" "${started_at_epoch}" > "${marker_path}"
    chown "${service_user}:${service_group}" "${marker_path}"
    chmod 0640 "${marker_path}"
  ' bash "${marker_path}" "${started_at_epoch}" "${SERINO_SERVICE_USER}" "${SERINO_SERVICE_GROUP}"
}

main() {
  local version=""
  local check_only="false"
  local manifest_file=""
  local bundle_dir=""
  local bundle_file=""
  local backup_dir=""
  local active_registry=""
  local target_registry=""
  local target_image_tag=""

  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --check)
        check_only="true"
        shift
        ;;
      --ready-timeout)
        [[ "$#" -ge 2 ]] || die "缺少 --ready-timeout 的参数值。"
        export AERISUN_RELEASE_READY_TIMEOUT="$2"
        shift 2
        ;;
      -*)
        die "upgrade 不支持参数：$1"
        ;;
      *)
        if [[ -n "${version}" ]]; then
          die "upgrade 只接受一个目标版本参数。"
        fi
        version="$1"
        shift
        ;;
    esac
  done

  require_supported_linux
  require_root_or_sudo
  ensure_supported_existing_installation
  ensure_service_user
  load_env_file "${AERISUN_ENV_FILE}"

  run_upgrade_preflight

  if [[ -n "${version}" ]]; then
    AERISUN_INSTALL_VERSION="${version}"
  fi

  version="$(resolve_release_tag)"
  manifest_file="$(make_temp_file)"
  load_release_manifest "${version}" "${manifest_file}"
  normalize_release_registry_strategy
  target_registry="${AERISUN_IMAGE_REGISTRY}"
  target_image_tag="${AERISUN_IMAGE_TAG}"

  if [[ "${check_only}" == "true" ]]; then
    log_info "升级预检通过，目标版本：${version}"
    return 0
  fi

  bundle_dir="$(make_temp_dir)"
  bundle_file="${bundle_dir}/${AERISUN_INSTALL_BUNDLE_NAME}"
  download_release_asset "${version}" "${AERISUN_INSTALL_BUNDLE_NAME}" "${bundle_file}"
  tar -xzf "${bundle_file}" -C "${bundle_dir}"

  backup_dir="${AERISUN_BACKUP_ROOT}/upgrade-$(date +%Y%m%d%H%M%S)"
  seed_persistent_uptime_marker || true
  stop_serino_service
  backup_current_installation "${backup_dir}"

  active_registry="$(
    resolve_active_registry \
      "${target_registry}" \
      "${target_image_tag}"
  )"

  install_release_payload "${bundle_dir}"
  set_env_value "${AERISUN_ENV_FILE}" "AERISUN_IMAGE_REGISTRY" "${active_registry}"
  set_env_value "${AERISUN_ENV_FILE}" "AERISUN_IMAGE_TAG" "${target_image_tag}"
  set_env_value "${AERISUN_ENV_FILE}" "AERISUN_RELEASE_VERSION" "${target_image_tag}"
  set_env_value "${AERISUN_ENV_FILE}" "AERISUN_DOCKER_REGISTRY_MIRRORS" "${AERISUN_DOCKER_REGISTRY_MIRRORS}"
  normalize_production_env_file "${AERISUN_ENV_FILE}"
  validate_release_compose_configuration

  if ! compose pull || ! run_release_migrations || ! run_release_data_migrations blocking || ! enable_serino_service || ! wait_for_release_ready; then
    log_warn "升级失败，正在回滚。"
    print_service_start_failure_diagnostics
    stop_serino_service
    restore_current_installation "${backup_dir}"
    compose pull || true
    enable_serino_service || true
    wait_for_release_ready || true
    die "升级失败，已回滚到旧版本。可执行 sercli doctor 与 sercli logs api waline caddy 查看诊断信息。"
  fi

  schedule_release_background_data_migrations || true

  log_info "升级完成：${version}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
