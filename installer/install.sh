#!/usr/bin/env bash
set -Eeuo pipefail

bootstrap_log_info() {
  printf '[INFO] %s\n' "$*" >&2
}

bootstrap_log_warn() {
  printf '[WARN] %s\n' "$*" >&2
}

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
      bootstrap_log_info "🎈 正在解析 ${channel} 渠道最新版本：${latest_url}"
      latest_payload="$(
        curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${latest_url}" 2>/dev/null || true
      )"
      if [[ -n "${latest_payload}" ]]; then
        version="$(printf '%s\n' "${latest_payload}" | extract_release_tag_from_env_payload)"
      else
        bootstrap_log_warn "未能从 ${latest_url} 读取版本信息。"
      fi
    fi

    if [[ -z "${version}" && "${channel}" == "stable" ]]; then
      api_url="https://api.github.com/repos/${repo}/releases/latest"
      bootstrap_log_info "正在从 GitHub Release 解析 stable 最新版本。"
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
    bootstrap_log_info "🌟 准备下载 ${channel} 安装包：${release_url}"
    if ! curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${release_url}" -o "${bundle_file}"; then
      if [[ "${channel}" == "stable" ]]; then
        release_url="https://github.com/${repo}/releases/download/${version}/${bundle_name}"
        bootstrap_log_warn "渠道源下载失败，回退到 GitHub Release：${release_url}"
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
    bootstrap_log_info "准备从 GitHub Release 下载安装包：${release_url}"
    if ! curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${release_url}" -o "${bundle_file}"; then
      echo "无法从 GitHub Release 下载安装包：${release_url}" >&2
      exit 1
    fi
  fi

  bootstrap_log_info "👏 正在解压安装包并启动安装器。"
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
  remove_serino_local_images
  purge_installation_paths
  purge_service_account
  log_warn "残留已清理。请根据上面的错误信息修复后重新执行安装。"
}

trap 'cleanup_failed_installation' ERR

prepare_install_target() {
  local legacy_paths=""
  local current_paths=""
  local detected_paths=""

  legacy_paths="$(legacy_installation_paths)"
  current_paths="$(current_installation_paths)"
  detected_paths="$(
    printf '%s\n%s\n' "${legacy_paths}" "${current_paths}" | awk 'NF'
  )"

  [[ -z "${detected_paths}" ]] && return 0

  confirm_overwrite_installation "${detected_paths}" "${legacy_paths}" "${current_paths}"
  log_warn "你已选择覆盖安装，正在彻底清理现有 Serino 安装与残留。"
  stop_serino_service
  teardown_release_stack
  stop_and_remove_serino_units
  remove_serino_local_images
  purge_installation_paths
  purge_service_account
}

main() {
  local version=""
  local manifest_file=""
  local bundle_root="${AERISUN_TEMPLATE_ROOT}"
  local active_registry=""
  local preflight_action=""

  require_supported_linux
  require_root_or_sudo
  prepare_install_target
  ensure_port_available 80
  ensure_port_available 443

  version="$(resolve_release_tag)"
  manifest_file="$(mktemp)"
  load_release_manifest "${version}" "${manifest_file}"
  log_info "准备安装 Serino ${version} ..."

  prompt_access_mode
  prompt_install_host

  while [[ "${AERISUN_INSTALL_ACCESS_MODE}" == "domain" ]]; do
    if preflight_domain_installation "${AERISUN_INSTALL_HOST}"; then
      break
    fi

    preflight_action="$(prompt_domain_preflight_action "${AERISUN_INSTALL_HOST}")"
    case "${preflight_action}" in
      retry)
        prompt_install_host
        ;;
      ip)
        AERISUN_INSTALL_ACCESS_MODE="ip"
        prompt_install_host
        ;;
      continue)
        log_warn "已按你的选择忽略域名预检告警，继续安装。若域名仍未指向本机，后续 HTTPS 就绪检查仍会失败。"
        break
        ;;
      cancel)
        die "安装已取消。"
        ;;
      *)
        die "未知的域名预检处理选项：${preflight_action}"
        ;;
    esac
  done

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
