#!/usr/bin/env bash
set -euo pipefail

echo "==> 正在设置开发环境的端口号..."

# 参数解释：
# $1: 起始端口号
# $剩下的所有参数: 需要跳过的端口列表（可选）
find_free_port() {
  if [[ $# -lt 1 ]]; then
    echo "find_free_port: 没有指定起始的端口号" >&2
    return 1
  fi
  local port=$1
  shift || true
  local -A skip=()
  for p in "$@"; do skip[$p]=1; done
  # 端口已被占用 || 端口在跳过列表里
  while ss -tlnH "sport = :$port" | grep -q . || [[ -n "${skip[$port]:-}" ]]; do
    port=$((port + 1))
  done
  echo "$port"
}

BACKEND_PORT=$(find_free_port 8000)
FRONTEND_PORT=$(find_free_port 8080 "$BACKEND_PORT")
ADMIN_PORT=$(find_free_port 3001 "$BACKEND_PORT" "$FRONTEND_PORT")

ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.env.development.local"

BEGIN_MARKER="# ── AUTO:setup-ports ──"
END_MARKER="# ── /AUTO:setup-ports ──"

BLOCK="${BEGIN_MARKER}
AERISUN_PORT=$BACKEND_PORT
AERISUN_FRONTEND_PORT=$FRONTEND_PORT
AERISUN_ADMIN_PORT=$ADMIN_PORT
AERISUN_SITE_URL=http://localhost:$FRONTEND_PORT
VITE_FRONTEND_URL=http://localhost:$FRONTEND_PORT
AERISUN_FRONTEND_UPSTREAM=host.docker.internal:$FRONTEND_PORT
AERISUN_ADMIN_UPSTREAM=host.docker.internal:$ADMIN_PORT
${END_MARKER}"

if [[ -f "$ENV_FILE" ]] && grep -qF "$BEGIN_MARKER" "$ENV_FILE"; then
  # 替换已有的 auto 区块，保留文件其余内容
  tmp="$(mktemp)"
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" -v block="$BLOCK" '
    $0 == begin { skip=1; if (!printed) { print block; printed=1 } next }
    $0 == end   { skip=0; next }
    !skip
  ' "$ENV_FILE" > "$tmp"
  mv "$tmp" "$ENV_FILE"
else
  # 文件不存在或无标记 → 追加
  [[ -f "$ENV_FILE" ]] && echo "" >> "$ENV_FILE"
  echo "$BLOCK" >> "$ENV_FILE"
fi

echo "👉 进程端口已选定   backend:$BACKEND_PORT  frontend:$FRONTEND_PORT  admin:$ADMIN_PORT"
echo "👉 进程端口已写入到 $ENV_FILE"
