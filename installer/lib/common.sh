#!/usr/bin/env bash

AERISUN_INSTALLER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AERISUN_TEMPLATE_ROOT="$(cd "${AERISUN_INSTALLER_ROOT}/.." && pwd)"

AERISUN_APP_ROOT="${AERISUN_APP_ROOT:-/opt/serino}"
AERISUN_DATA_DIR="${AERISUN_DATA_DIR:-/var/lib/serino}"
AERISUN_COMPOSE_PROJECT_NAME="${AERISUN_COMPOSE_PROJECT_NAME:-serino}"
AERISUN_COMPOSE_FILE="${AERISUN_COMPOSE_FILE:-${AERISUN_APP_ROOT}/docker-compose.release.yml}"
AERISUN_RENDERED_COMPOSE_FILE="${AERISUN_RENDERED_COMPOSE_FILE:-${AERISUN_APP_ROOT}/docker-compose.runtime.yml}"
AERISUN_BIN_ROOT="${AERISUN_BIN_ROOT:-${AERISUN_APP_ROOT}/bin}"
SERINO_CONFIG_ROOT="${SERINO_CONFIG_ROOT:-/etc/serino}"
SERINO_LOG_ROOT="${SERINO_LOG_ROOT:-/var/log/serino}"
SERINO_SERVICE_USER="${SERINO_SERVICE_USER:-serino}"
SERINO_SERVICE_GROUP="${SERINO_SERVICE_GROUP:-serino}"
SERINO_SYSTEMD_UNIT="${SERINO_SYSTEMD_UNIT:-serino.service}"
SERINO_SYSTEMD_UPGRADE_SERVICE="${SERINO_SYSTEMD_UPGRADE_SERVICE:-serino-upgrade.service}"
SERINO_SYSTEMD_UPGRADE_TIMER="${SERINO_SYSTEMD_UPGRADE_TIMER:-serino-upgrade.timer}"
SERINO_BIN_LINK="${SERINO_BIN_LINK:-$([[ "${AERISUN_APP_ROOT}" == "/opt/serino" ]] && printf '%s' '/usr/local/bin/sercli' || printf '%s' "${AERISUN_BIN_ROOT}/sercli")}"
SERINO_RUNTIME_UID=""
SERINO_RUNTIME_GID=""
AERISUN_ENV_FILE="${AERISUN_ENV_FILE:-${SERINO_CONFIG_ROOT}/serino.env}"
AERISUN_ENV_EXAMPLE_FILE="${AERISUN_ENV_EXAMPLE_FILE:-${AERISUN_APP_ROOT}/.env.production.local.example}"
AERISUN_INSTALLER_DEST="${AERISUN_INSTALLER_DEST:-${AERISUN_APP_ROOT}/installer}"
AERISUN_BACKUP_ROOT="${AERISUN_BACKUP_ROOT:-/var/backups/serino}"
AERISUN_INSTALL_BASE_URL="${AERISUN_INSTALL_BASE_URL:-}"
AERISUN_INSTALL_GITHUB_REPO="${AERISUN_INSTALL_GITHUB_REPO:-Aerisun/Serino}"
AERISUN_INSTALL_CHANNEL="${AERISUN_INSTALL_CHANNEL:-stable}"
AERISUN_INSTALL_VERSION="${AERISUN_INSTALL_VERSION:-}"
AERISUN_APT_MIRROR_URL="${AERISUN_APT_MIRROR_URL:-}"
AERISUN_UBUNTU_APT_MIRROR_URL="${AERISUN_UBUNTU_APT_MIRROR_URL:-https://mirrors.aliyun.com/ubuntu/,https://mirrors.tuna.tsinghua.edu.cn/ubuntu/,https://mirrors.ustc.edu.cn/ubuntu/}"
AERISUN_DEBIAN_APT_MIRROR_URL="${AERISUN_DEBIAN_APT_MIRROR_URL:-https://mirrors.aliyun.com/debian/,https://mirrors.tuna.tsinghua.edu.cn/debian/,https://mirrors.ustc.edu.cn/debian/}"
AERISUN_DOCKER_REGISTRY_MIRRORS="${AERISUN_DOCKER_REGISTRY_MIRRORS:-}"
AERISUN_HTTP_PORT="${AERISUN_HTTP_PORT:-80}"
AERISUN_HTTPS_PORT="${AERISUN_HTTPS_PORT:-443}"
AERISUN_PORT="${AERISUN_PORT:-8000}"
WALINE_PORT="${WALINE_PORT:-8360}"
AERISUN_INSTALL_DOCKERHUB_NAMESPACE="${AERISUN_INSTALL_DOCKERHUB_NAMESPACE:-aerisun}"
AERISUN_INSTALL_DEFAULT_BASE_URL="${AERISUN_INSTALL_DEFAULT_BASE_URL:-https://install.aerisun.top/serino}"
AERISUN_INSTALL_DEFAULT_DEV_BASE_URL="${AERISUN_INSTALL_DEFAULT_DEV_BASE_URL:-https://install.aerisun.top/serino/dev}"
AERISUN_INSTALL_DEBUG="${AERISUN_INSTALL_DEBUG:-false}"
AERISUN_INSTALL_MANIFEST_NAME="${AERISUN_INSTALL_MANIFEST_NAME:-aerisun-installer-manifest.env}"
AERISUN_INSTALL_BUNDLE_NAME="${AERISUN_INSTALL_BUNDLE_NAME:-aerisun-installer-bundle.tar.gz}"
AERISUN_INSTALL_ACCESS_MODE="${AERISUN_INSTALL_ACCESS_MODE:-}"
AERISUN_INSTALL_HOST="${AERISUN_INSTALL_HOST:-}"
SERINO_DOCKER_DAEMON_FILE="${SERINO_DOCKER_DAEMON_FILE:-/etc/docker/daemon.json}"
AERISUN_API_IMAGE_NAME="${AERISUN_API_IMAGE_NAME:-serino-api}"
AERISUN_WEB_IMAGE_NAME="${AERISUN_WEB_IMAGE_NAME:-serino-web}"
AERISUN_WALINE_IMAGE_NAME="${AERISUN_WALINE_IMAGE_NAME:-serino-waline}"
AERISUN_DOMAIN_PREFLIGHT_SUMMARY="${AERISUN_DOMAIN_PREFLIGHT_SUMMARY:-}"
AERISUN_DOMAIN_PREFLIGHT_DEBUG_DETAILS="${AERISUN_DOMAIN_PREFLIGHT_DEBUG_DETAILS:-}"
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

install_debug_enabled() {
  case "${AERISUN_INSTALL_DEBUG,,}" in
    1|true|yes|y|debug|on)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
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

path_exists() {
  local path="$1"
  [[ -e "${path}" ]] && return 0
  run_as_root test -e "${path}"
}

path_is_file() {
  local path="$1"
  [[ -f "${path}" ]] && return 0
  run_as_root test -f "${path}"
}

path_is_dir() {
  local path="$1"
  [[ -d "${path}" ]] && return 0
  run_as_root test -d "${path}"
}

make_temp_dir() {
  mktemp -d "${TMPDIR:-/tmp}/serino-installer.XXXXXX"
}

make_temp_file() {
  mktemp "${TMPDIR:-/tmp}/serino-installer.XXXXXX"
}

make_root_temp_file_in_dir() {
  local dir="$1"
  local pattern="$2"

  run_as_root install -d -o root -g root -m 0755 "${dir}"
  run_as_root mktemp "${dir%/}/${pattern}"
}

cleanup_temp_dir() {
  local dir="$1"
  [[ -n "${dir}" && -d "${dir}" ]] && rm -rf "${dir}"
}

cleanup_temp_file() {
  local file="$1"
  [[ -n "${file}" && -f "${file}" ]] && rm -f "${file}"
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

describe_port_usage() {
  local port="$1"
  local details=""

  if command_exists ss; then
    details="$(
      run_as_root ss -ltnpH 2>/dev/null \
        | awk -v port="${port}" '$4 ~ ("(^|:|\\])" port "$") { print }'
    )"
    if [[ -n "${details}" ]]; then
      printf '%s' "${details}"
      return 0
    fi
  fi

  if command_exists lsof; then
    details="$(run_as_root lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "${details}" ]]; then
      printf '%s' "${details}"
      return 0
    fi
  fi

  return 1
}

ensure_port_available() {
  local port="$1"
  local usage_details=""
  if port_in_use "${port}"; then
    usage_details="$(describe_port_usage "${port}" || true)"
    die "$(cat <<EOF
端口 ${port} 已被占用，安装器无法继续。

常见原因：
- 机器上已有 Caddy / Nginx / Apache 在监听该端口
- 之前启动过其他 Docker 容器并映射了该端口
- 已存在旧的站点或反向代理服务

$(if [[ -n "${usage_details}" ]]; then printf '当前监听详情：\n%s\n\n' "${usage_details}"; fi)请先停止占用该端口的服务后再安装。
EOF
)"
  fi
}

resolve_nologin_shell() {
  local candidate=""
  for candidate in /usr/sbin/nologin /sbin/nologin /usr/bin/false /bin/false; do
    if [[ -x "${candidate}" ]]; then
      printf '%s' "${candidate}"
      return 0
    fi
  done
  die "当前系统缺少可用的 nologin shell。"
}

ensure_service_user() {
  local shell_path=""

  if ! getent group "${SERINO_SERVICE_GROUP}" >/dev/null 2>&1; then
    run_as_root groupadd --system "${SERINO_SERVICE_GROUP}"
  fi

  if ! id -u "${SERINO_SERVICE_USER}" >/dev/null 2>&1; then
    shell_path="$(resolve_nologin_shell)"
    run_as_root useradd \
      --system \
      --gid "${SERINO_SERVICE_GROUP}" \
      --home-dir "${AERISUN_DATA_DIR}" \
      --create-home \
      --shell "${shell_path}" \
      "${SERINO_SERVICE_USER}"
  fi

  SERINO_RUNTIME_UID="$(id -u "${SERINO_SERVICE_USER}")"
  SERINO_RUNTIME_GID="$(id -g "${SERINO_SERVICE_USER}")"
}

legacy_installation_paths() {
  local path=""
  for path in \
    /opt/aerisun \
    /var/lib/aerisun \
    /usr/local/bin/aerisunctl \
    /etc/systemd/system/aerisun-upgrade.service \
    /etc/systemd/system/aerisun-upgrade.timer \
    /etc/systemd/system/aerisun.service; do
    path_exists "${path}" && printf '%s\n' "${path}"
  done
  return 0
}

current_installation_paths() {
  local path=""
  for path in \
    "${AERISUN_APP_ROOT}" \
    "${SERINO_CONFIG_ROOT}" \
    "${AERISUN_DATA_DIR}" \
    "${SERINO_LOG_ROOT}" \
    "${AERISUN_BACKUP_ROOT}" \
    /etc/systemd/system/"${SERINO_SYSTEMD_UNIT}" \
    "${SERINO_BIN_LINK}"; do
    path_exists "${path}" && printf '%s\n' "${path}"
  done
  return 0
}

ensure_no_legacy_installation() {
  local legacy_paths=""
  legacy_paths="$(legacy_installation_paths)"
  [[ -z "${legacy_paths}" ]] && return 0

  die "$(cat <<EOF
检测到旧版安装布局，当前工业级安装器不兼容旧模型：
${legacy_paths}

请先彻底清理旧布局后再重装。
EOF
)"
}

ensure_fresh_install_target() {
  local existing_paths=""
  existing_paths="$(current_installation_paths)"
  [[ -z "${existing_paths}" ]] && return 0

  die "$(cat <<EOF
检测到当前机器已经存在 Serino 安装或残留：
${existing_paths}

请先执行 sercli uninstall --force，或手工清理后再重装。
EOF
)"
}

purge_installation_paths() {
  cd /
  run_as_root rm -rf \
    "${AERISUN_APP_ROOT}" \
    "${SERINO_CONFIG_ROOT}" \
    "${AERISUN_DATA_DIR}" \
    "${SERINO_LOG_ROOT}" \
    "${AERISUN_BACKUP_ROOT}" \
    /opt/aerisun \
    /var/lib/aerisun \
    /var/backups/aerisun
  run_as_root rm -f "${SERINO_BIN_LINK}"
  run_as_root rm -f /usr/local/bin/aerisunctl
}

purge_service_account() {
  if id -u "${SERINO_SERVICE_USER}" >/dev/null 2>&1; then
    run_as_root userdel "${SERINO_SERVICE_USER}" >/dev/null 2>&1 || true
  fi
  if getent group "${SERINO_SERVICE_GROUP}" >/dev/null 2>&1; then
    run_as_root groupdel "${SERINO_SERVICE_GROUP}" >/dev/null 2>&1 || true
  fi
}

ensure_supported_existing_installation() {
  ensure_no_legacy_installation
  path_is_file "${AERISUN_ENV_FILE}" || die "未检测到新模型安装的配置文件：${AERISUN_ENV_FILE}"
  path_is_file "${AERISUN_COMPOSE_FILE}" || die "未检测到新模型安装的 compose 文件：${AERISUN_COMPOSE_FILE}"
  path_is_dir "${AERISUN_INSTALLER_DEST}" || die "未检测到新模型安装的 installer 目录：${AERISUN_INSTALLER_DEST}"
}

ensure_system_layout() {
  ensure_service_user

  run_as_root install -d -o root -g root -m 0755 "${AERISUN_APP_ROOT}"
  run_as_root install -d -o root -g "${SERINO_SERVICE_GROUP}" -m 0750 "${SERINO_CONFIG_ROOT}"
  run_as_root install -d -o "${SERINO_SERVICE_USER}" -g "${SERINO_SERVICE_GROUP}" -m 0750 "${AERISUN_DATA_DIR}"
  run_as_root install -d -o root -g root -m 0755 "${SERINO_LOG_ROOT}"
  run_as_root install -d -o root -g root -m 0700 "${AERISUN_BACKUP_ROOT}"
}

install_systemd_units() {
  local source_root="${1:-${AERISUN_TEMPLATE_ROOT}}"
  local service_template="${source_root}/installer/systemd/serino.service"
  local upgrade_service_template="${source_root}/installer/systemd/serino-upgrade.service"
  local timer_template="${source_root}/installer/systemd/serino-upgrade.timer"
  local service_tmp=""
  local upgrade_service_tmp=""
  local timer_tmp=""

  service_tmp="$(make_temp_file)"
  upgrade_service_tmp="$(make_temp_file)"
  timer_tmp="$(make_temp_file)"

  python3 - "${service_template}" "${service_tmp}" "${AERISUN_APP_ROOT}" "${AERISUN_COMPOSE_PROJECT_NAME}" "${AERISUN_RENDERED_COMPOSE_FILE}" <<'PY'
from pathlib import Path
import sys

template = Path(sys.argv[1]).read_text(encoding="utf-8")
replacements = {
    "__AERISUN_APP_ROOT__": sys.argv[3],
    "__AERISUN_COMPOSE_PROJECT_NAME__": sys.argv[4],
    "__AERISUN_RENDERED_COMPOSE_FILE__": sys.argv[5],
}

for key, value in replacements.items():
    template = template.replace(key, value)

Path(sys.argv[2]).write_text(template, encoding="utf-8")
PY

  python3 - "${upgrade_service_template}" "${upgrade_service_tmp}" "${SERINO_SYSTEMD_UNIT}" "${SERINO_BIN_LINK}" <<'PY'
from pathlib import Path
import sys

template = Path(sys.argv[1]).read_text(encoding="utf-8")
replacements = {
    "__SERINO_SYSTEMD_UNIT__": sys.argv[3],
    "__SERINO_BIN_LINK__": sys.argv[4],
}

for key, value in replacements.items():
    template = template.replace(key, value)

Path(sys.argv[2]).write_text(template, encoding="utf-8")
PY

  cp "${timer_template}" "${timer_tmp}"

  run_as_root install -m 0644 "${service_tmp}" "/etc/systemd/system/${SERINO_SYSTEMD_UNIT}"
  run_as_root install -m 0644 "${upgrade_service_tmp}" "/etc/systemd/system/${SERINO_SYSTEMD_UPGRADE_SERVICE}"
  run_as_root install -m 0644 "${timer_tmp}" "/etc/systemd/system/${SERINO_SYSTEMD_UPGRADE_TIMER}"
  rm -f "${service_tmp}" "${upgrade_service_tmp}" "${timer_tmp}"
  run_as_root systemctl daemon-reload
}

install_release_payload() {
  local source_root="${1:-${AERISUN_TEMPLATE_ROOT}}"

  ensure_system_layout
  run_as_root install -m 0644 "${source_root}/docker-compose.release.yml" "${AERISUN_COMPOSE_FILE}"
  run_as_root rm -f "${AERISUN_RENDERED_COMPOSE_FILE}"
  run_as_root install -m 0644 "${source_root}/.env.production.local.example" "${AERISUN_ENV_EXAMPLE_FILE}"
  run_as_root rm -rf "${AERISUN_INSTALLER_DEST}"
  run_as_root install -d -o root -g root -m 0755 "${AERISUN_INSTALLER_DEST}"
  run_as_root install -d -o root -g root -m 0755 "${AERISUN_BIN_ROOT}"
  run_as_root cp -a "${source_root}/installer/." "${AERISUN_INSTALLER_DEST}/"
  run_as_root chown -R root:root "${AERISUN_INSTALLER_DEST}"
  run_as_root chmod 0755 \
    "${AERISUN_INSTALLER_DEST}/install.sh" \
    "${AERISUN_INSTALLER_DEST}/doctor.sh" \
    "${AERISUN_INSTALLER_DEST}/uninstall.sh" \
    "${AERISUN_INSTALLER_DEST}/upgrade.sh" \
    "${AERISUN_INSTALLER_DEST}/bin/sercli"
  run_as_root ln -sf "${AERISUN_INSTALLER_DEST}/bin/sercli" "${SERINO_BIN_LINK}"
  install_systemd_units "${source_root}"
}

print_install_completion_card() {
  local term_cols="${COLUMNS:-}"

  if ! [[ "${term_cols}" =~ ^[0-9]+$ ]] || [[ "${term_cols}" -le 0 ]]; then
    term_cols="$(tput cols 2>/dev/null || true)"
  fi
  if ! [[ "${term_cols}" =~ ^[0-9]+$ ]] || [[ "${term_cols}" -le 0 ]]; then
    term_cols=80
  fi

  python3 - "${term_cols}" >&2 <<'PY'
import sys
import unicodedata


def char_display_width(ch: str) -> int:
    if not ch:
        return 0
    if ch in "\t\r\n":
        return 0
    if unicodedata.combining(ch):
        return 0
    if unicodedata.east_asian_width(ch) in {"F", "W"}:
        return 2
    # Most terminals render emoji-like symbols as double width.
    if ord(ch) >= 0x1F300:
        return 2
    return 1


def text_display_width(text: str) -> int:
    return sum(char_display_width(ch) for ch in text)


def wrap_line(text: str, width: int) -> list[str]:
  text = text.strip()
  if text == "":
    return [""]

  out = []
  current = ""
  current_width = 0

  for ch in text:
    ch_width = char_display_width(ch)
    if current and current_width + ch_width > width:
      out.append(current.rstrip())
      current = ch
      current_width = ch_width
      continue
    current += ch
    current_width += ch_width

  if current:
    out.append(current.rstrip())

  return out or [""]


def align_center(text: str, width: int) -> str:
  tw = text_display_width(text)
  left = max(0, (width - tw) // 2)
  return (" " * left) + text


def align_right(text: str, width: int) -> str:
  tw = text_display_width(text)
  left = max(0, width - tw)
  return (" " * left) + text


term_cols = int(sys.argv[1]) if len(sys.argv) > 1 else 80
content_width = max(28, min(92, term_cols - 4))
side_padding = 3
first_line_indent = 4
inner_width = max(18, content_width - (side_padding * 2))
side_pad_text = " " * side_padding
first_indent_text = " " * first_line_indent

title = "🎉 恭喜你，Serino 部署完成！"
paragraphs = [
  "谢谢你愿意来到这里！作为一名业余开发者，能在茫茫人海中与你相遇，是我最珍贵的缘分。你选择安装并使用我的作品，这份信任与陪伴，是我继续打磨它最大的动力。",
  "感谢你让 Serino 有机会参与和见证你的生活点滴。愿这里成为你心灵短暂停靠的港湾，也愿你无论喜悦还是低落，都能被温柔以待✨",
]
signature = "—— 开发者 Aerisun 敬上"

wrapped = [side_pad_text + title + side_pad_text, " " * content_width]
for paragraph in paragraphs:
  wrap_slack = 1 if content_width < 64 else 0
  para_wrap_width = max(12, inner_width - first_line_indent - wrap_slack)
  para_lines = wrap_line(paragraph, para_wrap_width)
  for idx, line in enumerate(para_lines):
    if idx == 0:
      body_line = first_indent_text + line
    else:
      body_line = line
    wrapped.append(side_pad_text + body_line + side_pad_text)
  wrapped.append(" " * content_width)
wrapped.append(side_pad_text + align_right(signature, inner_width) + side_pad_text)

top = "┌" + ("─" * content_width) + "┐"
bottom = "└" + ("─" * content_width) + "┘"
print(top)
for line in wrapped:
    pad = max(0, content_width - text_display_width(line))
    print("│" + line + (" " * pad) + "│")
print(bottom)
PY
}

print_install_summary() {
  local site_url="$1"
  local admin_url="$2"
  local admin_username="$3"
  local admin_password="$4"
  cat >&2 <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
安装完成后可通过以下地址访问：
- 网站首页：${site_url}
- 网站管理台：${admin_url}
- 管理台登录名：${admin_username}，登录密码：${admin_password}（此处最后一次显示，之后所有密码明文将彻底清除）
- 后续查看状态、诊断、升级、重启、彻底卸载等操作，可以使用终端命令 sercli 进行 ~
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF

  print_install_completion_card
}
