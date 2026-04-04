#!/usr/bin/env bash
set -Eeuo pipefail

bootstrap_from_release() {
  local version="${AERISUN_INSTALL_VERSION:-}"
  local repo="${AERISUN_INSTALL_GITHUB_REPO:-Aerisun/Serino}"
  local channel="${AERISUN_INSTALL_CHANNEL:-stable}"
  local default_base_url="${AERISUN_INSTALL_DEFAULT_BASE_URL:-https://install.aerisun.com}"
  local default_dev_base_url="${AERISUN_INSTALL_DEFAULT_DEV_BASE_URL:-https://install.aerisun.com/dev}"
  local base_url="${AERISUN_INSTALL_BASE_URL:-}"
  local bundle_name="${AERISUN_INSTALL_BUNDLE_NAME:-aerisun-installer-bundle.tar.gz}"
  local tmp_dir=""
  local bundle_file=""
  local release_url=""
  local api_url=""
  local latest_url=""
  local latest_payload=""

  extract_release_tag_from_env_payload() {
    sed -n "s/^[[:space:]]*AERISUN_INSTALL_VERSION[[:space:]]*=[[:space:]]*['\"]\\{0,1\\}\\(v[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" \
      | head -n 1
  }

  if [[ -z "${base_url}" ]]; then
    if [[ "${channel}" == "dev" ]]; then
      base_url="${default_dev_base_url}"
    else
      base_url="${default_base_url}"
    fi
  fi

  if [[ -z "${version}" ]]; then
    if [[ -n "${base_url}" ]]; then
      latest_url="${base_url%/}/latest.env"
      latest_payload="$(
        curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${latest_url}" 2>/dev/null || true
      )"
      if [[ -n "${latest_payload}" ]]; then
        version="$(printf '%s\n' "${latest_payload}" | extract_release_tag_from_env_payload)"
      fi
    fi

    if [[ -z "${version}" && "${channel}" == "stable" ]]; then
      api_url="https://api.github.com/repos/${repo}/releases/latest"
      version="$(
        curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${api_url}" \
          | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\(v[^"]*\)".*/\1/p' \
          | head -n 1
      )"
    fi
  fi

  [[ "${version}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    echo "安装器无法解析目标版本（channel=${channel}）。" >&2
    exit 1
  }

  tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/aerisun-bootstrap.XXXXXX")"
  bundle_file="${tmp_dir}/${bundle_name}"
  if [[ -n "${base_url}" ]]; then
    release_url="${base_url%/}/${version}/${bundle_name}"
    if ! curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${release_url}" -o "${bundle_file}"; then
      if [[ "${channel}" == "stable" ]]; then
        release_url="https://github.com/${repo}/releases/download/${version}/${bundle_name}"
        if ! curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${release_url}" -o "${bundle_file}"; then
          echo "无法下载安装包：${base_url%/}/${version}/${bundle_name}" >&2
          exit 1
        fi
      else
        echo "无法下载安装包：${base_url%/}/${version}/${bundle_name}" >&2
        exit 1
      fi
    fi
  else
    release_url="https://github.com/${repo}/releases/download/${version}/${bundle_name}"
    if ! curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${release_url}" -o "${bundle_file}"; then
      echo "无法从 GitHub Release 下载安装包：${release_url}" >&2
      exit 1
    fi
  fi

  tar -xzf "${bundle_file}" -C "${tmp_dir}"
  export AERISUN_INSTALL_VERSION="${version}"
  export AERISUN_INSTALL_CHANNEL="${channel}"
  export AERISUN_INSTALL_BASE_URL="${base_url}"
  exec "${tmp_dir}/installer/install.sh" --bundled "$@"
}

if [[ "${1:-}" != "--bundled" ]]; then
  bootstrap_from_release "$@"
fi
shift

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/download.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/env.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/tui.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/firewall.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/docker.sh"

AERISUN_INSTALL_CLEANUP_ARMED=0
AERISUN_INSTALL_CLEANUP_RUNNING=0

cleanup_failed_installation() {
  [[ "${AERISUN_INSTALL_CLEANUP_ARMED}" == "1" ]] || return 0
  [[ "${AERISUN_INSTALL_CLEANUP_RUNNING}" == "0" ]] || return 0

  AERISUN_INSTALL_CLEANUP_RUNNING=1
  set +e

  log_warn "安装未完成，正在清理本次安装留下的残留。"
  stop_serino_service
  teardown_release_stack
  stop_and_remove_serino_units
  run_as_root rm -rf \
    "${AERISUN_APP_ROOT}" \
    "${SERINO_CONFIG_ROOT}" \
    "${AERISUN_DATA_DIR}" \
    "${SERINO_LOG_ROOT}" \
    "${AERISUN_BACKUP_ROOT}"
  run_as_root rm -f /usr/local/bin/sercli
  if id -u "${SERINO_SERVICE_USER}" >/dev/null 2>&1; then
    run_as_root userdel "${SERINO_SERVICE_USER}" >/dev/null 2>&1 || true
  fi
  if getent group "${SERINO_SERVICE_GROUP}" >/dev/null 2>&1; then
    run_as_root groupdel "${SERINO_SERVICE_GROUP}" >/dev/null 2>&1 || true
  fi
  log_warn "残留已清理。请根据上面的错误信息修复后重新执行安装。"
}

trap 'cleanup_failed_installation' ERR

main() {
  local version=""
  local manifest_file=""
  local bundle_root="${AERISUN_TEMPLATE_ROOT}"
  local active_registry=""

  require_supported_linux
  require_root_or_sudo
  ensure_no_legacy_installation
  ensure_fresh_install_target
  ensure_port_available 80
  ensure_port_available 443

  version="$(resolve_release_tag)"
  manifest_file="$(mktemp)"
  load_release_manifest "${version}" "${manifest_file}"
  log_info "准备安装 Serino ${version} ..."

  prompt_access_mode
  prompt_install_host

  if [[ "${AERISUN_INSTALL_ACCESS_MODE}" == "domain" ]]; then
    preflight_domain_installation "${AERISUN_INSTALL_HOST}" || exit 1
  fi

  prompt_bootstrap_admin_credentials
  confirm_install_settings

  ensure_docker_installed
  configure_local_firewall
  ensure_service_user
  AERISUN_INSTALL_CLEANUP_ARMED=1
  active_registry="$(
    resolve_active_registry \
      "${AERISUN_IMAGE_REGISTRY}" \
      "${AERISUN_IMAGE_TAG}"
  )"

  build_runtime_configuration \
    "${AERISUN_INSTALL_ACCESS_MODE}" \
    "${AERISUN_INSTALL_HOST}" \
    "${active_registry}" \
    "${AERISUN_IMAGE_TAG}"

  install_release_payload "${bundle_root}"
  write_production_env "${AERISUN_ENV_FILE}"
  normalize_production_env_file "${AERISUN_ENV_FILE}"
  daemon_reload
  compose_up_release
  wait_for_release_ready
  verify_default_admin_login || die "服务已启动，但安装时设置的管理员登录检查失败。"
  unset_env_value "${AERISUN_ENV_FILE}" "AERISUN_BOOTSTRAP_ADMIN_USERNAME_B64"
  unset_env_value "${AERISUN_ENV_FILE}" "AERISUN_BOOTSTRAP_ADMIN_PASSWORD_B64"
  AERISUN_INSTALL_CLEANUP_ARMED=0

  if [[ "${AERISUN_INSTALL_ACCESS_MODE}" == "domain" ]]; then
    print_install_summary \
      "${AERISUN_SITE_URL_VALUE}" \
      "${AERISUN_SITE_URL_VALUE}${AERISUN_ADMIN_BASE_PATH:-/admin/}" \
      "${AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE}" \
      "${AERISUN_BOOTSTRAP_ADMIN_PASSWORD_VALUE}"
  else
    print_install_summary \
      "${AERISUN_SITE_URL_VALUE}/" \
      "${AERISUN_SITE_URL_VALUE}${AERISUN_ADMIN_BASE_PATH:-/admin/}" \
      "${AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE}" \
      "${AERISUN_BOOTSTRAP_ADMIN_PASSWORD_VALUE}"
  fi
}

main "$@"
