#!/usr/bin/env bash

guess_host_for_ip_mode() {
  local host=""
  host="$(curl --noproxy '*' --silent --show-error --max-time 5 https://api.ipify.org 2>/dev/null || true)"
  if [[ -z "${host}" ]]; then
    host="$(curl --noproxy '*' --silent --show-error --max-time 5 https://api64.ipify.org 2>/dev/null || true)"
  fi
  if [[ -z "${host}" ]]; then
    host="$(curl --silent --show-error --max-time 5 https://api.ipify.org 2>/dev/null || true)"
  fi
  if [[ -z "${host}" ]]; then
    host="$(curl --silent --show-error --max-time 5 https://api64.ipify.org 2>/dev/null || true)"
  fi
  if [[ -z "${host}" ]] && command_exists hostname; then
    host="$(hostname -I 2>/dev/null | awk '{print $1}')"
  fi
  printf '%s' "${host}"
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
        ip "IP/主机名模式（先用 HTTP 跑起来）" \
        3>&1 1>&2 2>&3 </dev/tty
    )" || die "安装已取消。"
    return 0
  fi

  cat >&2 <<'EOF'
请选择接入方式：
  1) 域名模式（正式 HTTPS）
  2) IP/主机名模式（先用 HTTP 跑起来）
EOF
  read -r -p "输入 1 或 2: " selection </dev/tty
  case "${selection}" in
    1) AERISUN_INSTALL_ACCESS_MODE="domain" ;;
    2) AERISUN_INSTALL_ACCESS_MODE="ip" ;;
    *) die "无效的接入方式。" ;;
  esac
}

prompt_install_host() {
  local prompt=""
  local default_value=""
  local value=""

  if [[ "${AERISUN_INSTALL_ACCESS_MODE}" == "domain" ]]; then
    prompt="请输入已经解析到本机公网 IP 的域名"
  else
    default_value="$(guess_host_for_ip_mode)"
    prompt="请输入服务器公网 IP 或主机名"
  fi

  if command_exists whiptail; then
    local width=""
    local height=""
    width="$(dialog_width 66 50)"
    height="$(dialog_height 10 10)"
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
  [[ -n "${value}" ]] || die "地址不能为空。"
  AERISUN_INSTALL_HOST="${value}"
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
