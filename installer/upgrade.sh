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

backup_current_installation() {
  local backup_dir="$1"
  run_as_root mkdir -p "${backup_dir}"
  [[ -f "${AERISUN_ENV_FILE}" ]] && run_as_root cp -a "${AERISUN_ENV_FILE}" "${backup_dir}/.env.production.local"
  [[ -f "${AERISUN_COMPOSE_FILE}" ]] && run_as_root cp -a "${AERISUN_COMPOSE_FILE}" "${backup_dir}/docker-compose.release.yml"
  [[ -d "${AERISUN_INSTALLER_DEST}" ]] && run_as_root cp -a "${AERISUN_INSTALLER_DEST}" "${backup_dir}/installer"
  if [[ -d "${AERISUN_DATA_DIR}" ]]; then
    run_as_root tar -czf "${backup_dir}/data.tar.gz" -C "${AERISUN_DATA_DIR%/*}" "$(basename "${AERISUN_DATA_DIR}")"
  fi
}

restore_current_installation() {
  local backup_dir="$1"

  if [[ -f "${backup_dir}/.env.production.local" ]]; then
    run_as_root cp -a "${backup_dir}/.env.production.local" "${AERISUN_ENV_FILE}"
  fi
  if [[ -f "${backup_dir}/docker-compose.release.yml" ]]; then
    run_as_root cp -a "${backup_dir}/docker-compose.release.yml" "${AERISUN_COMPOSE_FILE}"
  fi
  if [[ -d "${backup_dir}/installer" ]]; then
    run_as_root rm -rf "${AERISUN_INSTALLER_DEST}"
    run_as_root cp -a "${backup_dir}/installer" "${AERISUN_INSTALLER_DEST}"
    run_as_root ln -sf "${AERISUN_INSTALLER_DEST}/bin/aerisunctl" /usr/local/bin/aerisunctl
  fi
  if [[ -f "${backup_dir}/data.tar.gz" ]]; then
    run_as_root rm -rf "${AERISUN_DATA_DIR}"
    run_as_root mkdir -p "${AERISUN_DATA_DIR%/*}"
    run_as_root tar -xzf "${backup_dir}/data.tar.gz" -C "${AERISUN_DATA_DIR%/*}"
  fi
}

main() {
  require_supported_linux
  require_root_or_sudo

  local version="${1:-}"
  local manifest_file=""
  local bundle_dir=""
  local bundle_file=""
  local backup_dir=""
  local active_registry=""
  local target_registry=""
  local target_image_tag=""

  if [[ -n "${version}" ]]; then
    AERISUN_INSTALL_VERSION="${version}"
  fi

  version="$(resolve_release_tag)"
  manifest_file="$(mktemp)"
  load_release_manifest "${version}" "${manifest_file}"
  target_registry="${AERISUN_IMAGE_REGISTRY}"
  target_image_tag="${AERISUN_IMAGE_TAG}"

  load_env_file "${AERISUN_ENV_FILE}"
  bundle_dir="$(make_temp_dir)"
  bundle_file="${bundle_dir}/${AERISUN_INSTALL_BUNDLE_NAME}"
  download_release_asset "${version}" "${AERISUN_INSTALL_BUNDLE_NAME}" "${bundle_file}"
  tar -xzf "${bundle_file}" -C "${bundle_dir}"

  backup_dir="${AERISUN_BACKUP_ROOT}/upgrade-$(date +%Y%m%d%H%M%S)"
  compose down
  backup_current_installation "${backup_dir}"

  active_registry="$(
    resolve_active_registry \
      "${target_registry}" \
      "${target_image_tag}"
  )"

  install_release_payload "${bundle_dir}"
  set_env_value "${AERISUN_ENV_FILE}" "AERISUN_IMAGE_REGISTRY" "${active_registry}"
  set_env_value "${AERISUN_ENV_FILE}" "AERISUN_IMAGE_TAG" "${target_image_tag}"

  if ! compose_up_release || ! wait_for_release_ready; then
    log_warn "升级失败，正在回滚。"
    restore_current_installation "${backup_dir}"
    compose_up_release
    wait_for_release_ready
    die "升级失败，已回滚到旧版本。"
  fi

  log_info "升级完成：${version}"
}

main "$@"
