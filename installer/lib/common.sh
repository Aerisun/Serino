#!/usr/bin/env bash

AERISUN_INSTALLER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AERISUN_TEMPLATE_ROOT="$(cd "${AERISUN_INSTALLER_ROOT}/.." && pwd)"

AERISUN_APP_ROOT="${AERISUN_APP_ROOT:-/opt/aerisun}"
AERISUN_DATA_DIR="${AERISUN_DATA_DIR:-/var/lib/aerisun}"
AERISUN_COMPOSE_PROJECT_NAME="${AERISUN_COMPOSE_PROJECT_NAME:-aerisun}"
AERISUN_COMPOSE_FILE="${AERISUN_COMPOSE_FILE:-${AERISUN_APP_ROOT}/docker-compose.release.yml}"
AERISUN_ENV_FILE="${AERISUN_ENV_FILE:-${AERISUN_APP_ROOT}/.env.production.local}"
AERISUN_ENV_EXAMPLE_FILE="${AERISUN_ENV_EXAMPLE_FILE:-${AERISUN_APP_ROOT}/.env.production.local.example}"
AERISUN_INSTALLER_DEST="${AERISUN_INSTALLER_DEST:-${AERISUN_APP_ROOT}/installer}"
AERISUN_BACKUP_ROOT="${AERISUN_BACKUP_ROOT:-${AERISUN_APP_ROOT}/backups}"
AERISUN_INSTALL_BASE_URL="${AERISUN_INSTALL_BASE_URL:-https://install.aerisun.com/releases}"
AERISUN_INSTALL_GITHUB_REPO="${AERISUN_INSTALL_GITHUB_REPO:-Aerisun/Serino}"
AERISUN_INSTALL_CHANNEL="${AERISUN_INSTALL_CHANNEL:-stable}"
AERISUN_INSTALL_VERSION="${AERISUN_INSTALL_VERSION:-}"
AERISUN_INSTALL_MANIFEST_NAME="${AERISUN_INSTALL_MANIFEST_NAME:-aerisun-installer-manifest.env}"
AERISUN_INSTALL_BUNDLE_NAME="${AERISUN_INSTALL_BUNDLE_NAME:-aerisun-installer-bundle.tar.gz}"
AERISUN_INSTALL_ACCESS_MODE="${AERISUN_INSTALL_ACCESS_MODE:-}"
AERISUN_INSTALL_HOST="${AERISUN_INSTALL_HOST:-}"
AERISUN_INSTALL_ARCH=""
AERISUN_INSTALL_DISTRO=""
AERISUN_INSTALL_PRETTY_NAME=""

log_info() {
  printf '[INFO] %s\n' "$*" >&2
}

log_warn() {
  printf '[WARN] %s\n' "$*" >&2
}

log_error() {
  printf '[ERROR] %s\n' "$*" >&2
}

die() {
  log_error "$*"
  exit 1
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

require_root_or_sudo() {
  if [[ "$(id -u)" -eq 0 ]]; then
    return 0
  fi
  command_exists sudo || die "需要 root 或可用的 sudo。"
}

run_as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
    return
  fi
  sudo "$@"
}

make_temp_dir() {
  mktemp -d "${TMPDIR:-/tmp}/aerisun-installer.XXXXXX"
}

cleanup_temp_dir() {
  local dir="$1"
  [[ -n "${dir}" && -d "${dir}" ]] && rm -rf "${dir}"
}

detect_arch() {
  case "$(uname -m)" in
    x86_64|amd64)
      AERISUN_INSTALL_ARCH="amd64"
      ;;
    aarch64|arm64)
      AERISUN_INSTALL_ARCH="arm64"
      ;;
    *)
      die "当前架构 $(uname -m) 不在 v1 支持范围内。"
      ;;
  esac
}

detect_distro() {
  [[ -f /etc/os-release ]] || die "缺少 /etc/os-release，无法识别 Linux 发行版。"
  # shellcheck disable=SC1091
  source /etc/os-release
  AERISUN_INSTALL_DISTRO="${ID:-unknown}"
  AERISUN_INSTALL_PRETTY_NAME="${PRETTY_NAME:-${ID:-Linux}}"
}

require_supported_linux() {
  [[ "$(uname -s)" == "Linux" ]] || die "安装器仅支持 Linux。"
  detect_distro
  detect_arch

  case " ${ID:-} ${ID_LIKE:-} " in
    *" ubuntu "*|*" debian "*|*" rhel "*|*" centos "*|*" rocky "*|*" almalinux "*|*" fedora "*)
      ;;
    *)
      die "当前发行版 ${AERISUN_INSTALL_PRETTY_NAME} 不在 v1 支持范围内。"
      ;;
  esac

  [[ -d /run/systemd/system ]] || die "当前系统不是 systemd 环境，v1 安装器暂不支持。"
  command_exists systemctl || die "缺少 systemctl，无法管理 Docker 服务。"
  command_exists curl || die "缺少 curl。"
  command_exists tar || die "缺少 tar。"
  command_exists base64 || die "缺少 base64。"
}

port_in_use() {
  local port="$1"

  if command_exists ss; then
    ss -ltnH | awk '{print $4}' | grep -Eq "(^|:|\\])${port}$"
    return
  fi

  if command_exists netstat; then
    netstat -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:|\\])${port}$"
    return
  fi

  return 1
}

ensure_port_available() {
  local port="$1"
  if port_in_use "${port}"; then
    die "端口 ${port} 已被占用，请先释放后再安装。"
  fi
}

install_release_payload() {
  local source_root="${1:-${AERISUN_TEMPLATE_ROOT}}"

  run_as_root mkdir -p "${AERISUN_APP_ROOT}" "${AERISUN_DATA_DIR}" "${AERISUN_BACKUP_ROOT}"
  run_as_root install -m 0644 "${source_root}/docker-compose.release.yml" "${AERISUN_COMPOSE_FILE}"
  run_as_root install -m 0644 "${source_root}/.env.production.local.example" "${AERISUN_ENV_EXAMPLE_FILE}"
  run_as_root rm -rf "${AERISUN_INSTALLER_DEST}"
  run_as_root mkdir -p "${AERISUN_INSTALLER_DEST}"
  run_as_root cp -a "${source_root}/installer/." "${AERISUN_INSTALLER_DEST}/"
  run_as_root chmod 0755 \
    "${AERISUN_INSTALLER_DEST}/install.sh" \
    "${AERISUN_INSTALLER_DEST}/upgrade.sh" \
    "${AERISUN_INSTALLER_DEST}/bin/aerisunctl"
  run_as_root ln -sf "${AERISUN_INSTALLER_DEST}/bin/aerisunctl" /usr/local/bin/aerisunctl
}

print_install_summary() {
  local site_url="$1"
  local admin_url="$2"
  local admin_username="$3"
  cat >&2 <<EOF

安装完成。
前台地址：${site_url}
后台地址：${admin_url}
后台管理员：${admin_username}
后台密码：安装过程中设置的密码

常用命令：
  aerisunctl status
  aerisunctl logs
  aerisunctl restart
  aerisunctl upgrade
EOF
}
