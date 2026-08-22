#!/usr/bin/env bash
set -Eeuo pipefail

INSTALL_SCRIPT_SELF_PATH="${BASH_SOURCE[0]-}"

bootstrap_log_info() {
  printf '[INFO] %s\n' "$*" >&2
}

bootstrap_log_warn() {
  printf '[WARN] %s\n' "$*" >&2
}

bootstrap_metadata_curl() {
  curl --fail --location --silent --show-error --retry 3 --retry-all-errors \
    --connect-timeout 10 --max-time 45 "$@"
}

bootstrap_asset_curl() {
  curl --fail --location --silent --show-error --retry 3 --retry-all-errors \
    --connect-timeout 10 --max-time 180 "$@"
}

bootstrap_sha256_file() {
  local file="$1"

  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${file}" | awk '{print $1}'
    return 0
  fi

  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${file}" | awk '{print $1}'
    return 0
  fi

  return 1
}

bootstrap_extract_bundle_sha256_from_env_payload() {
  sed -n "s/^[[:space:]]*AERISUN_INSTALL_BUNDLE_SHA256[[:space:]]*=[[:space:]]*['\"]\\{0,1\\}\\([A-Fa-f0-9]\\{64\\}\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" \
    | head -n 1
}

bootstrap_payload_declares_bundle_sha256() {
  grep -Eq "^[[:space:]]*AERISUN_INSTALL_BUNDLE_SHA256[[:space:]]*="
}

bootstrap_bundle_sha256_from_payload() {
  local payload="$1"
  local source_name="$2"
  local bundle_sha256=""

  if ! printf '%s\n' "${payload}" | bootstrap_payload_declares_bundle_sha256; then
    return 1
  fi

  bundle_sha256="$(printf '%s\n' "${payload}" | bootstrap_extract_bundle_sha256_from_env_payload)"
  if [[ -z "${bundle_sha256}" ]]; then
    echo "${source_name} 中的 AERISUN_INSTALL_BUNDLE_SHA256 不是有效的 sha256。" >&2
    return 2
  fi

  printf '%s' "${bundle_sha256}"
}

bootstrap_fetch_bundle_sha256() {
  local manifest_url="$1"
  local manifest_payload=""

  manifest_payload="$(
    bootstrap_metadata_curl "${manifest_url}" 2>/dev/null || true
  )"
  [[ -n "${manifest_payload}" ]] || return 1

  bootstrap_bundle_sha256_from_payload "${manifest_payload}" "${manifest_url}"
}

bootstrap_verify_bundle_sha256() {
  local file="$1"
  local expected_sha256="$2"
  local actual_sha256=""

  if ! actual_sha256="$(bootstrap_sha256_file "${file}")"; then
    echo "无法计算安装包 sha256：缺少 sha256sum/shasum。" >&2
    return 1
  fi

  if [[ "${actual_sha256,,}" != "${expected_sha256,,}" ]]; then
    echo "安装包 sha256 校验失败：expected=${expected_sha256} actual=${actual_sha256}" >&2
    return 1
  fi
}

bootstrap_from_release() {
  local version="${AERISUN_INSTALL_VERSION:-}"
  local repo="${AERISUN_INSTALL_GITHUB_REPO:-Aerisun/Serino}"
  local channel="${AERISUN_INSTALL_CHANNEL:-stable}"
  local default_base_url="${AERISUN_INSTALL_DEFAULT_BASE_URL:-https://install.aerisun.top/serino}"
  local default_dev_base_url="${AERISUN_INSTALL_DEFAULT_DEV_BASE_URL:-https://install.aerisun.top/serino/dev}"
  local base_url="${AERISUN_INSTALL_BASE_URL:-}"
  local manifest_name="${AERISUN_INSTALL_MANIFEST_NAME:-aerisun-installer-manifest.env}"
  local bundle_name="${AERISUN_INSTALL_BUNDLE_NAME:-aerisun-installer-bundle.tar.gz}"
  local tmp_dir=""
  local bundle_file=""
  local release_url=""
  local api_url=""
  local latest_url=""
  local latest_payload=""
  local expected_bundle_sha256=""

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
        bootstrap_metadata_curl "${latest_url}" 2>/dev/null || true
      )"
      if [[ -n "${latest_payload}" ]]; then
        version="$(printf '%s\n' "${latest_payload}" | extract_release_tag_from_env_payload)"
        if expected_bundle_sha256="$(bootstrap_bundle_sha256_from_payload "${latest_payload}" "${latest_url}")"; then
          :
        else
          case "$?" in
            1)
              expected_bundle_sha256=""
              ;;
            *)
              exit 1
              ;;
          esac
        fi
      else
        bootstrap_log_warn "未能从 ${latest_url} 读取版本信息，正在准备回退。"
      fi
    fi

    if [[ -z "${version}" && "${channel}" == "stable" ]]; then
      api_url="https://api.github.com/repos/${repo}/releases/latest"
      bootstrap_log_warn "渠道版本解析失败，正在回退到 GitHub Release API：${api_url}"
      version="$(
        bootstrap_metadata_curl "${api_url}" \
          | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\(v[^"]*\)".*/\1/p' \
          | head -n 1
      )"
    fi
  fi

  [[ "${version}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    echo "安装器无法解析目标版本（channel=${channel}）。" >&2
    exit 1
  }

  if [[ -z "${expected_bundle_sha256}" && -n "${base_url}" ]]; then
    if expected_bundle_sha256="$(bootstrap_fetch_bundle_sha256 "${base_url%/}/${version}/${manifest_name}")"; then
      :
    else
      case "$?" in
        1)
          expected_bundle_sha256=""
          ;;
        *)
          exit 1
          ;;
      esac
    fi
  fi

  if [[ -z "${expected_bundle_sha256}" && "${channel}" == "stable" ]]; then
    if expected_bundle_sha256="$(bootstrap_fetch_bundle_sha256 "https://github.com/${repo}/releases/download/${version}/${manifest_name}")"; then
      :
    else
      case "$?" in
        1)
          expected_bundle_sha256=""
          ;;
        *)
          exit 1
          ;;
      esac
    fi
  fi

  tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/aerisun-bootstrap.XXXXXX")"
  bundle_file="${tmp_dir}/${bundle_name}"
  if [[ -n "${base_url}" ]]; then
    release_url="${base_url%/}/${version}/${bundle_name}"
    bootstrap_log_info "🌟 准备下载 ${channel} 安装包：${release_url}"
    if ! bootstrap_asset_curl "${release_url}" -o "${bundle_file}"; then
      if [[ "${channel}" == "stable" ]]; then
        release_url="https://github.com/${repo}/releases/download/${version}/${bundle_name}"
        bootstrap_log_warn "渠道源下载失败，回退到 GitHub Release：${release_url}"
        if ! bootstrap_asset_curl "${release_url}" -o "${bundle_file}"; then
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
    if ! bootstrap_asset_curl "${release_url}" -o "${bundle_file}"; then
      echo "无法从 GitHub Release 下载安装包：${release_url}" >&2
      exit 1
    fi
  fi

  if [[ -n "${expected_bundle_sha256}" ]]; then
    bootstrap_log_info "正在校验安装包 sha256。"
    bootstrap_verify_bundle_sha256 "${bundle_file}" "${expected_bundle_sha256}"
  else
    bootstrap_log_warn "当前发布清单未提供安装包 sha256，已跳过安装包完整性校验。"
  fi

  bootstrap_log_info "👏 正在解压安装包并启动安装器。"
  tar -xzf "${bundle_file}" -C "${tmp_dir}"
  export AERISUN_INSTALL_VERSION="${version}"
  export AERISUN_INSTALL_CHANNEL="${channel}"
  export AERISUN_INSTALL_BASE_URL="${base_url}"
  exec "${tmp_dir}/installer/install.sh" --bundled "$@"
}

INSTALL_SCRIPT_IS_EXECUTED="false"
if [[ -z "${INSTALL_SCRIPT_SELF_PATH}" || "${INSTALL_SCRIPT_SELF_PATH}" == "$0" ]]; then
  INSTALL_SCRIPT_IS_EXECUTED="true"
  if [[ "${1:-}" != "--bundled" ]]; then
    bootstrap_from_release "$@"
  fi
  if [[ "${1:-}" == "--bundled" ]]; then
    shift
  fi
fi

if [[ -z "${INSTALL_SCRIPT_SELF_PATH}" ]]; then
  echo "安装器在 --bundled 模式下必须以文件方式执行，不能通过标准输入继续运行。" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${INSTALL_SCRIPT_SELF_PATH}")" && pwd)"
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
  if ! stop_and_remove_serino_units; then
    log_error "后台数据迁移仍在运行或无法确认已经停止；为保护数据，已保留当前安装现场。"
    AERISUN_INSTALL_CLEANUP_ARMED=0
    return 1
  fi
  if ! teardown_release_stack; then
    log_error "Serino 容器未能全部停止并移除；为保护数据，已保留当前安装现场。"
    AERISUN_INSTALL_CLEANUP_ARMED=0
    return 1
  fi
  remove_serino_local_images
  purge_service_account
  purge_installation_paths
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
  if ! stop_and_remove_serino_units; then
    die "后台数据迁移仍在运行或无法确认已经停止，已取消覆盖安装以保护数据。"
  fi
  if ! teardown_release_stack; then
    die "Serino 容器未能全部停止并移除，已取消覆盖安装以保护数据。"
  fi
  remove_serino_local_images
  purge_service_account
  purge_installation_paths
}

main() {
  local version=""
  local manifest_file=""
  local bundle_root="${AERISUN_TEMPLATE_ROOT}"
  local active_registry=""
  local preflight_action=""
  local summary_site_url=""
  local summary_site_probe_url=""
  local summary_admin_url=""

  require_supported_linux
  require_root_or_sudo
  prepare_install_target
  ensure_port_available "${AERISUN_HTTP_PORT}"
  ensure_port_available "${AERISUN_HTTPS_PORT}"

  version="$(resolve_release_tag)"
  manifest_file="$(make_temp_file)"
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

  normalize_release_registry_strategy
  ensure_docker_installed
  configure_local_firewall
  ensure_service_user
  AERISUN_INSTALL_CLEANUP_ARMED=1
  log_info "🤔 正在确认镜像源配置..."
  active_registry="$(
    resolve_active_registry \
      "${AERISUN_IMAGE_REGISTRY}" \
      "${AERISUN_IMAGE_TAG}"
  )"

  log_info "🤯 正在生成生产环境配置..."
  build_runtime_configuration \
    "${AERISUN_INSTALL_ACCESS_MODE}" \
    "${AERISUN_INSTALL_HOST}" \
    "${active_registry}" \
    "${AERISUN_IMAGE_TAG}"

  log_info "💪 正在安装运行载荷..."
  install_release_payload "${bundle_root}"
  write_production_env "${AERISUN_ENV_FILE}"
  normalize_production_env_file "${AERISUN_ENV_FILE}"
  daemon_reload
  log_info "🧪 正在校验安装配置..."
  validate_release_compose_configuration
  log_info "📦 正在拉取镜像，这一步可能需要几分钟..."
  if ! compose pull; then
    print_service_start_failure_diagnostics
    cleanup_failed_installation
    AERISUN_INSTALL_CLEANUP_ARMED=0
    die "镜像拉取失败，安装已中止。可根据上面的报错信息修复后重试。"
  fi
  if ! run_release_migrations; then
    print_service_start_failure_diagnostics
    cleanup_failed_installation
    AERISUN_INSTALL_CLEANUP_ARMED=0
    die "数据库迁移失败，安装已中止。可根据上面的报错信息修复后重试。"
  fi
  if ! run_release_baseline; then
    print_service_start_failure_diagnostics
    cleanup_failed_installation
    AERISUN_INSTALL_CLEANUP_ARMED=0
    die "生产 baseline 初始化失败，安装已中止。可根据上面的报错信息修复后重试。"
  fi
  if ! run_release_data_migrations blocking; then
    print_service_start_failure_diagnostics
    cleanup_failed_installation
    AERISUN_INSTALL_CLEANUP_ARMED=0
    die "阻塞式数据迁移失败，安装已中止。可根据上面的报错信息修复后重试。"
  fi
  if ! run_release_admin_bootstrap; then
    print_service_start_failure_diagnostics
    cleanup_failed_installation
    AERISUN_INSTALL_CLEANUP_ARMED=0
    die "首次管理员初始化失败，安装已中止。可根据上面的报错信息修复后重试。"
  fi
  log_info "🥳 正在启动站点服务..."
  if ! enable_serino_service; then
    print_service_start_failure_diagnostics
    cleanup_failed_installation
    AERISUN_INSTALL_CLEANUP_ARMED=0
    die "服务启动失败，安装已中止。可根据上面的报错信息修复后重试。"
  fi
  log_info "🎊 正在等待站点服务就绪..."
  if ! wait_for_release_ready; then
    print_service_start_failure_diagnostics
    cleanup_failed_installation
    AERISUN_INSTALL_CLEANUP_ARMED=0
    die "站点服务在预期时间内未就绪，安装已中止。可根据上面的报错信息修复后重试。"
  fi
  verify_default_admin_login || die "服务已启动，但安装时设置的管理员登录检查失败。"
  schedule_release_background_data_migrations || true
  unset_env_value "${AERISUN_ENV_FILE}" "AERISUN_BOOTSTRAP_ADMIN_USERNAME_B64"
  unset_env_value "${AERISUN_ENV_FILE}" "AERISUN_BOOTSTRAP_ADMIN_PASSWORD_B64"

  if [[ "${AERISUN_INSTALL_ACCESS_MODE}" == "domain" ]]; then
    summary_site_url="${AERISUN_SITE_URL_VALUE}"
    summary_site_probe_url="${AERISUN_SITE_URL_VALUE}/"
  else
    summary_site_url="${AERISUN_SITE_URL_VALUE}/"
    summary_site_probe_url="${summary_site_url}"
  fi
  summary_admin_url="${AERISUN_SITE_URL_VALUE}${AERISUN_ADMIN_BASE_PATH:-/admin/}"

  if ! verify_install_summary_endpoints "${summary_site_probe_url}" "${summary_admin_url}"; then
    print_service_start_failure_diagnostics
    cleanup_failed_installation
    AERISUN_INSTALL_CLEANUP_ARMED=0
    if [[ "${AERISUN_INSTALL_ACCESS_MODE}" == "ip" ]]; then
      die "安装完成前的最终访问校验失败：当前填写的 IPv4 绑定有误，常见原因是把代理出口地址填成了服务器 IP。请改填这台服务器真实 IPv4（优先公网 IPv4，没有公网再用内网）后重新安装。"
    fi
    die "安装完成前的最终访问校验失败，网站首页或网站管理台仍不可访问。可根据上面的报错信息修复后重试。"
  fi

  AERISUN_INSTALL_CLEANUP_ARMED=0
  print_install_summary \
    "${summary_site_url}" \
    "${summary_admin_url}" \
    "${AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE}" \
    "${AERISUN_BOOTSTRAP_ADMIN_PASSWORD_VALUE}"
}

if [[ "${INSTALL_SCRIPT_IS_EXECUTED}" == "true" ]]; then
  main "$@"
fi
