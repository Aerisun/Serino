#!/usr/bin/env bash

configure_local_firewall() {
  if command_exists ufw; then
    if run_as_root ufw status | grep -q "Status: active"; then
      log_info "检测到 ufw，正在放行 80/443。"
      run_as_root ufw allow 80/tcp >/dev/null
      run_as_root ufw allow 443/tcp >/dev/null
    fi
  fi

  if command_exists firewall-cmd && run_as_root systemctl is-active --quiet firewalld; then
    log_info "检测到 firewalld，正在放行 HTTP/HTTPS。"
    run_as_root firewall-cmd --permanent --add-service=http >/dev/null
    run_as_root firewall-cmd --permanent --add-service=https >/dev/null
    run_as_root firewall-cmd --reload >/dev/null
  fi

  log_warn "如果你使用了云服务器，请确认安全组也已放行 80/443。"
}
