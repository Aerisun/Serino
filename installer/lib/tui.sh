#!/usr/bin/env bash

is_private_ipv4_literal() {
  local value="$1"
  [[ "${value}" =~ ^0\. ]] && return 0
  [[ "${value}" =~ ^10\. ]] && return 0
  [[ "${value}" =~ ^127\. ]] && return 0
  [[ "${value}" =~ ^192\.168\. ]] && return 0
  [[ "${value}" =~ ^172\.(1[6-9]|2[0-9]|3[0-1])\. ]] && return 0
  [[ "${value}" =~ ^100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\. ]] && return 0
  [[ "${value}" =~ ^169\.254\. ]] && return 0
  [[ "${value}" =~ ^192\.0\.0\. ]] && return 0
  [[ "${value}" =~ ^192\.0\.2\. ]] && return 0
  [[ "${value}" =~ ^192\.88\.99\. ]] && return 0
  [[ "${value}" =~ ^198\.(18|19)\. ]] && return 0
  [[ "${value}" =~ ^198\.51\.100\. ]] && return 0
  [[ "${value}" =~ ^203\.0\.113\. ]] && return 0
  [[ "${value}" =~ ^2(2[4-9]|3[0-9])\. ]] && return 0
  [[ "${value}" =~ ^24[0-9]\. ]] && return 0
  [[ "${value}" =~ ^25[0-5]\. ]] && return 0
  return 1
}

is_public_ipv4_literal() {
  local value="$1"
  value="$(normalize_host_input "${value}")"

  is_ipv4_literal "${value}" || return 1

  if command_exists python3; then
    python3 - "${value}" <<'PY' >/dev/null 2>&1
from ipaddress import ip_address
import sys

try:
    addr = ip_address(sys.argv[1])
except ValueError:
    raise SystemExit(1)

raise SystemExit(0 if addr.version == 4 and addr.is_global else 1)
PY
    return $?
  fi

  ! is_private_ipv4_literal "${value}"
}

list_local_ip_candidates_by_family() {
  local family="$1"
  local candidates=""

  if command_exists ip; then
    if [[ "${family}" == "4" ]]; then
      candidates="$(
        ip -o -4 addr show scope global up 2>/dev/null \
        | awk '$2 !~ /^(lo|docker|br-|veth|virbr|cni|flannel|tailscale|zt)/ {print $4}' \
        | cut -d/ -f1
      )"
    else
      candidates="$(
        ip -o -6 addr show scope global up 2>/dev/null \
        | awk '$2 !~ /^(lo|docker|br-|veth|virbr|cni|flannel|tailscale|zt)/ {print $4}' \
        | cut -d/ -f1
      )"
    fi
    if [[ -n "${candidates}" ]]; then
      printf '%s\n' "${candidates}"
      return 0
    fi
  fi

  if command_exists hostname; then
    hostname -I 2>/dev/null | tr ' ' '\n'
  fi
}

pick_first_ip_by_family() {
  local family="$1"
  local candidate=""

  while IFS= read -r candidate; do
    candidate="$(trim_input "${candidate}")"
    [[ -n "${candidate}" ]] || continue
    candidate="$(normalize_host_input "${candidate}")"
    if [[ "${family}" == "4" ]] && is_ipv4_literal "${candidate}"; then
      printf '%s' "${candidate}"
      return 0
    fi
    if [[ "${family}" == "6" ]] && is_ipv6_literal "${candidate}"; then
      printf '%s' "${candidate}"
      return 0
    fi
  done

  return 1
}

pick_first_public_ipv4() {
  local candidate=""

  while IFS= read -r candidate; do
    candidate="$(trim_input "${candidate}")"
    [[ -n "${candidate}" ]] || continue
    candidate="$(normalize_host_input "${candidate}")"
    if is_public_ipv4_literal "${candidate}"; then
      printf '%s' "${candidate}"
      return 0
    fi
  done

  return 1
}

pick_first_private_ipv4() {
  local candidate=""

  while IFS= read -r candidate; do
    candidate="$(trim_input "${candidate}")"
    [[ -n "${candidate}" ]] || continue
    candidate="$(normalize_host_input "${candidate}")"
    if is_ipv4_literal "${candidate}" && ! is_public_ipv4_literal "${candidate}"; then
      printf '%s' "${candidate}"
      return 0
    fi
  done

  return 1
}

list_local_ipv4_candidates() {
  list_local_ip_candidates_by_family 4 | while IFS= read -r candidate; do
    candidate="$(trim_input "${candidate}")"
    [[ -n "${candidate}" ]] || continue
    candidate="$(normalize_host_input "${candidate}")"
    is_ipv4_literal "${candidate}" || continue
    printf '%s\n' "${candidate}"
  done | awk 'NF && !seen[$0]++'
}

sanitize_public_ipv4_probe_result() {
  local value="$1"

  value="$(printf '%s' "${value}" | tr -d '\r' | awk 'NR == 1 { gsub(/^[[:space:]]+|[[:space:]]+$/, ""); print }')"
  if [[ -n "${value}" ]] && is_public_ipv4_literal "${value}"; then
    printf '%s' "${value}"
    return 0
  fi

  return 1
}

pick_best_public_ipv4_probe_candidate() {
  awk '
    NF && !seen[$0]++ {
      order[++n] = $0
    }
    NF {
      count[$0]++
    }
    END {
      if (n == 0) {
        exit 1
      }
      best = order[1]
      for (i = 2; i <= n; i++) {
        if (count[order[i]] > count[best]) {
          best = order[i]
        }
      }
      print best
    }
  '
}

detect_public_ipv4_without_proxy() {
  local candidate=""
  local endpoint=""
  local candidates=""

  for endpoint in \
    "https://api.ipify.org" \
    "https://ipv4.icanhazip.com" \
    "https://ifconfig.me/ip" \
    "https://api.ip.sb/ip" \
    "https://4.ipw.cn"
  do
    candidate="$(
      curl --fail --location --noproxy '*' --silent --show-error \
        --connect-timeout 3 --max-time 8 -4 "${endpoint}" 2>/dev/null || true
    )"
    candidate="$(sanitize_public_ipv4_probe_result "${candidate}" || true)"
    if [[ -n "${candidate}" ]]; then
      candidates+="${candidate}"$'\n'
    fi
  done

  printf '%s' "${candidates}" | pick_best_public_ipv4_probe_candidate
}

detect_public_ipv4_with_proxy() {
  local candidate=""

  candidate="$(
    curl --fail --location --silent --show-error \
      --connect-timeout 3 --max-time 8 -4 https://api.ipify.org 2>/dev/null || true
  )"
  candidate="$(sanitize_public_ipv4_probe_result "${candidate}" || true)"
  if [[ -n "${candidate}" ]]; then
    printf '%s' "${candidate}"
    return 0
  fi

  return 1
}

guess_host_for_ip_mode() {
  local host=""

  if [[ "${AERISUN_INSTALL_IP_MODE:-}" == "private" ]]; then
    guess_private_host_for_ip_mode
    return
  fi
  if [[ "${AERISUN_INSTALL_IP_MODE:-}" == "public" ]]; then
    guess_public_host_for_ip_mode
    return
  fi

  host="$(list_local_ipv4_candidates | pick_first_public_ipv4 || true)"
  if [[ -z "${host}" ]]; then
    host="$(detect_public_ipv4_without_proxy || true)"
  fi
  if [[ -z "${host}" ]]; then
    host="$(list_local_ipv4_candidates | pick_first_ip_by_family 4 || true)"
  fi
  printf '%s' "${host}"
}

guess_public_host_for_ip_mode() {
  local host=""

  host="$(list_local_ipv4_candidates | pick_first_public_ipv4 || true)"
  if [[ -z "${host}" ]]; then
    host="$(detect_public_ipv4_without_proxy || true)"
  fi
  printf '%s' "${host}"
}

guess_private_host_for_ip_mode() {
  list_local_ipv4_candidates | pick_first_private_ipv4 || true
}

AERISUN_INSTALL_HOST_VALIDATION_ERROR=""

validate_ip_mode_host() {
  local value="$1"
  local mode="${AERISUN_INSTALL_IP_MODE:-}"
  local local_ipv4s=""
  local detected_public_ipv4=""
  local proxy_public_ipv4=""

  AERISUN_INSTALL_HOST_VALIDATION_ERROR=""
  value="$(normalize_host_input "${value}")"

  if [[ -z "${value}" ]]; then
    AERISUN_INSTALL_HOST_VALIDATION_ERROR="地址不能为空。"
    return 1
  fi

  if ! is_ipv4_literal "${value}"; then
    AERISUN_INSTALL_HOST_VALIDATION_ERROR="IP 模式仅支持这台服务器的真实 IPv4 地址，请不要填写域名、IPv6 或主机名。"
    return 1
  fi

  local_ipv4s="$(list_local_ipv4_candidates)"
  if [[ "${mode}" == "private" ]]; then
    if [[ -n "${local_ipv4s}" ]] && grep -Fxq "${value}" <<<"${local_ipv4s}"; then
      if is_public_ipv4_literal "${value}"; then
        AERISUN_INSTALL_HOST_VALIDATION_ERROR="你选择了内网 IPv4，但填写的是公网 IPv4。请填写本机网卡上的内网 IPv4，例如校园网或 clab 环境里的 10.x/172.16-31.x/192.168.x 地址。"
        return 1
      fi
      printf '%s' "${value}"
      return 0
    fi

    AERISUN_INSTALL_HOST_VALIDATION_ERROR="内网 IPv4 模式要求填写本机网卡上的内网 IPv4。请使用 hostname -I 看到的内网地址，不要填写 NAT 出口、公网 EIP、域名或其他机器地址。"
    return 1
  fi

  if [[ "${mode}" == "public" ]]; then
    if [[ -n "${local_ipv4s}" ]] && grep -Fxq "${value}" <<<"${local_ipv4s}"; then
      if ! is_public_ipv4_literal "${value}"; then
        AERISUN_INSTALL_HOST_VALIDATION_ERROR="你选择了公网 IPv4，但填写的是本机内网 IPv4。腾讯云、阿里云等云服务器请填写绑定到该机器的公网 IPv4 / EIP；如果只是校园网内网访问，请返回选择内网 IPv4。"
        return 1
      fi
      printf '%s' "${value}"
      return 0
    fi

    detected_public_ipv4="$(detect_public_ipv4_without_proxy || true)"
    if [[ -n "${detected_public_ipv4}" && "${value}" == "${detected_public_ipv4}" ]]; then
      printf '%s' "${value}"
      return 0
    fi

    proxy_public_ipv4="$(detect_public_ipv4_with_proxy || true)"
    if [[ -n "${proxy_public_ipv4}" && "${value}" == "${proxy_public_ipv4}" && "${value}" != "${detected_public_ipv4}" ]]; then
      AERISUN_INSTALL_HOST_VALIDATION_ERROR="当前填写的 IPv4 看起来是代理出口地址，不是这台服务器的公网 IPv4 / EIP。请关闭代理后重试，或确认云厂商控制台里绑定到本机的公网 IPv4。"
      return 1
    fi

    AERISUN_INSTALL_HOST_VALIDATION_ERROR="公网 IPv4 模式要求填写绑定到这台服务器的公网 IPv4 / EIP。适合腾讯云、阿里云等云服务器；如果是校园网、clab 或仅内网访问，请返回选择内网 IPv4。"
    return 1
  fi

  # Backward-compatible validation for scripts/tests that set only AERISUN_INSTALL_ACCESS_MODE=ip.
  if [[ -n "${local_ipv4s}" ]] && grep -Fxq "${value}" <<<"${local_ipv4s}"; then
    printf '%s' "${value}"
    return 0
  fi

  detected_public_ipv4="$(detect_public_ipv4_without_proxy || true)"
  if [[ -n "${detected_public_ipv4}" && "${value}" == "${detected_public_ipv4}" ]]; then
    printf '%s' "${value}"
    return 0
  fi

  proxy_public_ipv4="$(detect_public_ipv4_with_proxy || true)"
  if [[ -n "${proxy_public_ipv4}" && "${value}" == "${proxy_public_ipv4}" && "${value}" != "${detected_public_ipv4}" ]]; then
    AERISUN_INSTALL_HOST_VALIDATION_ERROR="当前填写的 IPv4 看起来是代理出口地址，不是这台服务器的真实 IP。请优先填写本机公网 IPv4；如果没有公网 IPv4，再填写本机内网 IPv4。"
    return 1
  fi

  AERISUN_INSTALL_HOST_VALIDATION_ERROR="IP 模式要求填写这台服务器的真实 IPv4 地址。请优先填写本机公网 IPv4；如果没有公网 IPv4，再填写本机内网 IPv4。不能填写代理出口地址或其他机器的地址。"
  return 1
}

prompt_validation_error() {
  local message="$1"

  if command_exists whiptail; then
    local width=""
    width="$(dialog_width 72 54)"
    whiptail --title "输入有误" --msgbox "${message}" 10 "${width}" </dev/tty || true
    return 0
  fi

  printf '[WARN] %s\n' "${message}" >&2
}

ip_mode_label() {
  case "${1:-}" in
    public)
      printf '公网访问'
      ;;
    private)
      printf '内网访问'
      ;;
    *)
      printf '未选择'
      ;;
  esac
}

public_ip_requires_mapping_confirmation() {
  local value="$1"
  local local_ipv4s=""

  [[ "${AERISUN_INSTALL_ACCESS_MODE:-}" == "ip" ]] || return 1
  [[ "${AERISUN_INSTALL_IP_MODE:-}" == "public" ]] || return 1
  is_public_ipv4_literal "${value}" || return 1

  local_ipv4s="$(list_local_ipv4_candidates)"
  if [[ -n "${local_ipv4s}" ]] && grep -Fxq "${value}" <<<"${local_ipv4s}"; then
    return 1
  fi

  return 0
}

confirm_public_ip_mapping() {
  local value="$1"
  local message=""

  public_ip_requires_mapping_confirmation "${value}" || return 0

  message="$(cat <<EOF
你填写的公网 IPv4 ${value} 没有出现在本机网卡地址里。

如果这是腾讯云、阿里云等云服务器控制台里绑定到本机的公网 IP，这通常是正常的。

如果这是校园网、实验室、办公室网络里自动检测出来的出口 IP，它通常不能从外面访问到这台机器。此时请取消，返回选择内网访问。

只有确认外部用户能通过 ${value} 访问这台服务器时，才继续。
EOF
)"

  if command_exists whiptail; then
    local width=""
    local height=""
    width="$(dialog_width 76 58)"
    height="$(dialog_height 17 13)"
    whiptail --title "确认公网访问地址" --yesno "${message}" "${height}" "${width}" </dev/tty
    return $?
  fi

  printf '%s\n' "${message}" >&2
  read -r -p "确认外部用户能通过这个 IP 访问本机？[y/N]: " answer </dev/tty
  [[ "${answer}" =~ ^[Yy]$ ]]
}

trim_input() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "${value}"
}

tty_cols() {
  local cols=""
  cols="$(tput cols 2>/dev/null || true)"
  if [[ -z "${cols}" || ! "${cols}" =~ ^[0-9]+$ ]]; then
    cols="$(stty size 2>/dev/null | awk '{print $2}' || true)"
  fi
  if [[ -z "${cols}" || ! "${cols}" =~ ^[0-9]+$ ]]; then
    cols=80
  fi
  printf '%s' "${cols}"
}

tty_lines() {
  local lines=""
  lines="$(tput lines 2>/dev/null || true)"
  if [[ -z "${lines}" || ! "${lines}" =~ ^[0-9]+$ ]]; then
    lines="$(stty size 2>/dev/null | awk '{print $1}' || true)"
  fi
  if [[ -z "${lines}" || ! "${lines}" =~ ^[0-9]+$ ]]; then
    lines=24
  fi
  printf '%s' "${lines}"
}

dialog_width() {
  local preferred="${1:-68}"
  local minimum="${2:-54}"
  local cols=""
  cols="$(tty_cols)"
  if (( cols <= minimum + 6 )); then
    printf '%s' "${minimum}"
    return 0
  fi
  if (( preferred > cols - 6 )); then
    printf '%s' "$(( cols - 6 ))"
    return 0
  fi
  printf '%s' "${preferred}"
}

dialog_height() {
  local preferred="${1:-16}"
  local minimum="${2:-10}"
  local lines=""
  lines="$(tty_lines)"
  if (( lines <= minimum + 4 )); then
    printf '%s' "${minimum}"
    return 0
  fi
  if (( preferred > lines - 4 )); then
    printf '%s' "$(( lines - 4 ))"
    return 0
  fi
  printf '%s' "${preferred}"
}

prompt_access_mode() {
  [[ -e /dev/tty ]] || die "当前终端不可交互，无法执行安装向导。"

  if command_exists whiptail; then
    local width=""
    local height=""
    width="$(dialog_width 60 48)"
    height="$(dialog_height 14 12)"
    AERISUN_INSTALL_ACCESS_MODE="$(
        whiptail --title "Aerisun 安装" --menu "选择接入方式" "${height}" "${width}" 2 \
        domain "域名模式（正式 HTTPS）" \
        ip "IPv4 模式（下一步选择公网或内网）" \
        3>&1 1>&2 2>&3 </dev/tty
    )" || die "安装已取消。"
    return 0
  fi

  cat >&2 <<'EOF'
请选择接入方式：
  1) 域名模式（正式 HTTPS）
  2) IPv4 模式（下一步选择公网或内网）
EOF
  read -r -p "输入 1 或 2: " selection </dev/tty
  case "${selection}" in
    1) AERISUN_INSTALL_ACCESS_MODE="domain" ;;
    2) AERISUN_INSTALL_ACCESS_MODE="ip" ;;
    *) die "无效的接入方式。" ;;
  esac
}

prompt_ip_mode() {
  [[ "${AERISUN_INSTALL_ACCESS_MODE}" == "ip" ]] || return 0
  [[ -z "${AERISUN_INSTALL_IP_MODE:-}" ]] || return 0

  if command_exists whiptail; then
    local width=""
    local height=""
    width="$(dialog_width 78 58)"
    height="$(dialog_height 14 12)"
    AERISUN_INSTALL_IP_MODE="$(
        whiptail --title "Aerisun 安装" --menu "选择 IPv4 类型" "${height}" "${width}" 2 \
        public "公网 IPv4（腾讯云、阿里云等云服务器厂商）" \
        private "内网 IPv4（例如校园网中的 clab）" \
        3>&1 1>&2 2>&3 </dev/tty
    )" || die "安装已取消。"
    return 0
  fi

cat >&2 <<'EOF'
选择 IPv4 类型：
  1) 公网 IPv4（腾讯云、阿里云等云服务器厂商）
  2) 内网 IPv4（例如校园网中的 clab）
EOF
  read -r -p "输入 1 或 2: " selection </dev/tty
  case "${selection}" in
    1) AERISUN_INSTALL_IP_MODE="public" ;;
    2) AERISUN_INSTALL_IP_MODE="private" ;;
    *) die "无效的 IPv4 类型。" ;;
  esac
}

prompt_install_host() {
  local prompt=""
  local default_value=""
  local value=""

  if [[ "${AERISUN_INSTALL_ACCESS_MODE}" == "domain" ]]; then
    prompt="请输入已经解析到本机公网 IP 的域名"
  else
    prompt_ip_mode
    default_value="$(guess_host_for_ip_mode)"
    if [[ "${AERISUN_INSTALL_IP_MODE:-}" == "public" ]]; then
      prompt="请输入外部用户访问这台服务器用的公网 IPv4（云服务器控制台里的公网 IP）"
    else
      prompt="请输入内网里访问这台服务器用的 IPv4（通常是 hostname -I 里看到的 10.x/172.x/192.168.x）"
    fi
  fi

  while true; do
    if command_exists whiptail; then
      local width=""
      local height=""
      width="$(dialog_width 72 54)"
      height="$(dialog_height 11 10)"
      value="$(
        whiptail --title "Aerisun 安装" --inputbox "${prompt}" "${height}" "${width}" "${default_value}" 3>&1 1>&2 2>&3 </dev/tty
      )" || die "安装已取消。"
    else
      if [[ -n "${default_value}" ]]; then
        read -r -p "${prompt} [${default_value}]: " value </dev/tty
        value="${value:-${default_value}}"
      else
        read -r -p "${prompt}: " value </dev/tty
      fi
    fi

    value="$(normalize_host_input "${value}")"
    if [[ "${AERISUN_INSTALL_ACCESS_MODE}" == "ip" ]]; then
      if ! value="$(validate_ip_mode_host "${value}")"; then
        prompt_validation_error "${AERISUN_INSTALL_HOST_VALIDATION_ERROR}"
        continue
      fi
      if ! confirm_public_ip_mapping "${value}"; then
        prompt_validation_error "已取消使用该公网 IPv4。请重新输入；如果只是校园网、实验室或 clab 访问，请重新运行安装并选择内网访问。"
        continue
      fi
    elif [[ -z "${value}" ]]; then
      prompt_validation_error "地址不能为空。"
      continue
    fi

    AERISUN_INSTALL_HOST="${value}"
    return 0
  done
}

validate_bootstrap_admin_username() {
  local value="$1"
  [[ -n "${value}" ]] || return 1
  [[ "${value}" =~ ^[A-Za-z0-9._-]{3,120}$ ]]
}

prompt_bootstrap_admin_credentials() {
  local username=""
  local password=""
  local confirm_password=""

  while true; do
    if command_exists whiptail; then
      local width=""
      width="$(dialog_width 68 52)"
      username="$(
        whiptail --title "Aerisun 安装" --inputbox "请输入网站管理台登录名（3-120 位，仅支持字母、数字、点、下划线、横线）。请务必记录好。" 12 "${width}" "${AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE:-admin}" 3>&1 1>&2 2>&3 </dev/tty
      )" || die "安装已取消。"
      password="$(
        whiptail --title "Aerisun 安装" --passwordbox "请输入网站管理台登录密码（至少 8 位）。请务必记录好。" 12 "${width}" 3>&1 1>&2 2>&3 </dev/tty
      )" || die "安装已取消。"
      confirm_password="$(
        whiptail --title "Aerisun 安装" --passwordbox "请再次输入网站管理台登录密码" 10 "${width}" 3>&1 1>&2 2>&3 </dev/tty
      )" || die "安装已取消。"
    else
      read -r -p "请输入网站管理台登录名（请务必记录好）: " username </dev/tty
      read -r -s -p "请输入网站管理台登录密码（请务必记录好）: " password </dev/tty
      printf '\n' >&2
      read -r -s -p "请再次输入网站管理台登录密码: " confirm_password </dev/tty
      printf '\n' >&2
    fi

    username="$(trim_input "${username}")"
    if ! validate_bootstrap_admin_username "${username}"; then
      log_warn "网站管理台登录名格式无效，只能使用 3-120 位字母、数字、点、下划线或横线。"
      continue
    fi
    if [[ ${#password} -lt 8 ]]; then
      log_warn "网站管理台登录密码至少需要 8 位。"
      continue
    fi
    if [[ "${password}" != "${confirm_password}" ]]; then
      log_warn "两次输入的网站管理台登录密码不一致。"
      continue
    fi

    AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE="${username}"
    AERISUN_BOOTSTRAP_ADMIN_PASSWORD_VALUE="${password}"
    return 0
  done
}

confirm_install_settings() {
  local summary
  summary=$(
    cat <<EOF
安装目录：${AERISUN_APP_ROOT}
数据目录：${AERISUN_DATA_DIR}
接入方式：${AERISUN_INSTALL_ACCESS_MODE}
$(if [[ "${AERISUN_INSTALL_ACCESS_MODE}" == "ip" ]]; then printf '访问范围：%s\n' "$(ip_mode_label "${AERISUN_INSTALL_IP_MODE:-}")"; fi)
站点地址：${AERISUN_INSTALL_HOST}
网站管理台登录名：${AERISUN_BOOTSTRAP_ADMIN_USERNAME_VALUE}
提示：请确认你已经记录好网站管理台登录密码
EOF
  )

  if command_exists whiptail; then
    local width=""
    local height=""
    width="$(dialog_width 66 52)"
    height="$(dialog_height 16 12)"
    whiptail --title "确认安装" --yesno "${summary}" "${height}" "${width}" </dev/tty || die "安装已取消。"
    return 0
  fi

  printf '%s\n' "${summary}" >&2
  read -r -p "继续安装？[y/N]: " answer </dev/tty
  [[ "${answer}" =~ ^[Yy]$ ]] || die "安装已取消。"
}

confirm_overwrite_installation() {
  local existing_paths="$1"
  local has_legacy="$2"
  local has_current="$3"
  local summary=""

  summary="$(
    cat <<EOF
检测到这台机器上已存在 Serino 安装或残留：
${existing_paths}

取消：保留现有安装；如需保留数据并升级，请使用 sercli upgrade。
覆盖安装：删除现有服务、配置、数据、日志、备份、本地镜像与服务账号，然后重新安装。

覆盖安装不可恢复。
EOF
  )"

  if command_exists whiptail; then
    local title="检测到已有安装"
    local width=""
    local height=""
    if [[ -n "${has_legacy}" && -n "${has_current}" ]]; then
      title="检测到旧布局和现有安装"
    elif [[ -n "${has_legacy}" ]]; then
      title="检测到旧布局残留"
    elif [[ -n "${has_current}" ]]; then
      title="检测到已有安装"
    fi
    width="$(dialog_width 72 54)"
    height="$(dialog_height 20 14)"
    whiptail \
      --title "${title}" \
      --yes-button "覆盖安装" \
      --no-button "取消" \
      --yesno "${summary}" "${height}" "${width}" </dev/tty || die "已取消安装。"
    return 0
  fi

  printf '%s\n' "${summary}" >&2
  local answer=""
  read -r -p "如确认彻底覆盖并重装，请输入 OVERWRITE: " answer </dev/tty
  [[ "${answer}" == "OVERWRITE" ]] || die "已取消安装。"
}

prompt_domain_preflight_action() {
  local host="$1"
  local prompt="域名 ${host} 似乎没有稳定解析到本机器。可能是域名输入有误，或当前网络/代理影响了检测。"
  prompt="${prompt}"$'\n\n'"请选择下一步操作："

  if command_exists whiptail; then
    local width=""
    local height=""
    width="$(dialog_width 72 54)"
    height="$(dialog_height 18 14)"
    whiptail --title "域名预检未通过" --menu "${prompt}" "${height}" "${width}" 4 \
      continue "${host} 已绑定本机，继续安装" \
      retry "重新输入域名并重新检查" \
      ip "改为 IP/主机名模式继续安装" \
      cancel "取消安装" \
      3>&1 1>&2 2>&3 </dev/tty || die "安装已取消。"
    return 0
  fi

  cat >&2 <<EOF
${prompt}
  1) ${host} 确实已经绑定到本机器，继续安装
  2) 重新输入域名并重新检查
  3) 改为 IP/主机名模式继续安装
  4) 取消安装
EOF

  local selection=""
  read -r -p "输入 1、2、3 或 4: " selection </dev/tty
  case "${selection}" in
    1) printf 'continue\n' ;;
    2) printf 'retry\n' ;;
    3) printf 'ip\n' ;;
    4) printf 'cancel\n' ;;
    *) die "无效的选择。" ;;
  esac
}
