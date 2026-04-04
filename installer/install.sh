#!/usr/bin/env bash
set -euo pipefail

bootstrap_from_release() {
  local version="${AERISUN_INSTALL_VERSION:-}"
  local repo="${AERISUN_INSTALL_GITHUB_REPO:-Aerisun/Serino}"
  local base_url="${AERISUN_INSTALL_BASE_URL:-https://install.aerisun.com/releases}"
  local bundle_name="${AERISUN_INSTALL_BUNDLE_NAME:-aerisun-installer-bundle.tar.gz}"
  local tmp_dir=""
  local bundle_file=""
  local release_url=""
  local api_url=""

  if [[ -z "${version}" ]]; then
    api_url="https://api.github.com/repos/${repo}/releases/latest"
    version="$(
      curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${api_url}" \
        | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\(v[^"]*\)".*/\1/p' \
        | head -n 1
    )"
  fi

  [[ "${version}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    echo "安装器无法解析目标版本。" >&2
    exit 1
  }

  tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/aerisun-bootstrap.XXXXXX")"
  bundle_file="${tmp_dir}/${bundle_name}"
  release_url="${base_url%/}/${version}/${bundle_name}"

  if ! curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${release_url}" -o "${bundle_file}"; then
    release_url="https://github.com/${repo}/releases/download/${version}/${bundle_name}"
    curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 "${release_url}" -o "${bundle_file}"
  fi

  tar -xzf "${bundle_file}" -C "${tmp_dir}"
  export AERISUN_INSTALL_VERSION="${version}"
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

main() {
  local version=""
  local manifest_file=""
  local bundle_root="${AERISUN_TEMPLATE_ROOT}"
  local active_registry=""

  require_supported_linux
  require_root_or_sudo
  ensure_port_available 80
  ensure_port_available 443

  version="$(resolve_release_tag)"
  log_info "准备安装 Aerisun ${version}。"

  manifest_file="$(mktemp)"
  load_release_manifest "${version}" "${manifest_file}"

  ensure_docker_installed
  configure_local_firewall
  prompt_access_mode
  prompt_install_host
  prompt_bootstrap_admin_credentials
  confirm_install_settings

  active_registry="$(
    resolve_active_registry \
      "${AERISUN_IMAGE_PRIMARY_REGISTRY:-}" \
      "${AERISUN_IMAGE_FALLBACK_REGISTRY}" \
      "${AERISUN_IMAGE_TAG}"
  )"

  build_runtime_configuration \
    "${AERISUN_INSTALL_ACCESS_MODE}" \
    "${AERISUN_INSTALL_HOST}" \
    "${active_registry}" \
    "${AERISUN_IMAGE_PRIMARY_REGISTRY:-}" \
    "${AERISUN_IMAGE_FALLBACK_REGISTRY}" \
    "${AERISUN_IMAGE_TAG}"

  install_release_payload "${bundle_root}"
  write_production_env "${AERISUN_ENV_FILE}"
  compose_up_release
  wait_for_release_ready
  verify_default_admin_login || die "服务已启动，但安装时设置的管理员登录检查失败。"
  unset_env_value "${AERISUN_ENV_FILE}" "AERISUN_BOOTSTRAP_ADMIN_USERNAME_B64"
  unset_env_value "${AERISUN_ENV_FILE}" "AERISUN_BOOTSTRAP_ADMIN_PASSWORD_B64"

  if [[ "${AERISUN_INSTALL_ACCESS_MODE}" == "domain" ]]; then
    print_install_summary \
      "${AERISUN_SITE_URL_VALUE}" \
      "${AERISUN_SITE_URL_VALUE}${AERISUN_ADMIN_BASE_PATH:-/admin/}" \
      "${AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE}"
  else
    print_install_summary \
      "${AERISUN_SITE_URL_VALUE}/" \
      "${AERISUN_SITE_URL_VALUE}${AERISUN_ADMIN_BASE_PATH:-/admin/}" \
      "${AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE}"
  fi
}

main "$@"
