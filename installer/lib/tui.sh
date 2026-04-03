#!/usr/bin/env bash

guess_host_for_ip_mode() {
  local host=""
  host="$(curl --silent --show-error --max-time 5 https://api64.ipify.org 2>/dev/null || true)"
  if [[ -z "${host}" ]] && command_exists hostname; then
    host="$(hostname -I 2>/dev/null | awk '{print $1}')"
  fi
  printf '%s' "${host}"
}

prompt_access_mode() {
  [[ -e /dev/tty ]] || die "当前终端不可交互，无法执行安装向导。"

  if command_exists whiptail; then
    AERISUN_INSTALL_ACCESS_MODE="$(
      whiptail --title "Aerisun 安装" --menu "选择接入方式" 15 72 2 \
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
    value="$(
      whiptail --title "Aerisun 安装" --inputbox "${prompt}" 10 72 "${default_value}" 3>&1 1>&2 2>&3 </dev/tty
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

confirm_install_settings() {
  local summary
  summary=$(
    cat <<EOF
安装目录：${AERISUN_APP_ROOT}
数据目录：${AERISUN_DATA_DIR}
接入方式：${AERISUN_INSTALL_ACCESS_MODE}
站点地址：${AERISUN_INSTALL_HOST}
EOF
  )

  if command_exists whiptail; then
    whiptail --title "确认安装" --yesno "${summary}" 14 72 </dev/tty || die "安装已取消。"
    return 0
  fi

  printf '%s\n' "${summary}" >&2
  read -r -p "继续安装？[y/N]: " answer </dev/tty
  [[ "${answer}" =~ ^[Yy]$ ]] || die "安装已取消。"
}
