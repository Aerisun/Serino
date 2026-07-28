#!/usr/bin/env bash

normalize_caddy_route_path() {
  local raw_path="$1"

  python3 - "${raw_path}" <<'PY'
import re
import sys

raw_path = sys.argv[1]
if (
    not raw_path
    or raw_path == "/"
    or any(char.isspace() for char in raw_path)
    or any(char in raw_path for char in ("?", "#", "*", "{", "}", "\\"))
):
    raise SystemExit(1)

if not re.fullmatch(r"/[A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~-]+)*/?", raw_path):
    raise SystemExit(1)

parts = [part for part in raw_path.split("/") if part]
if any(part in {".", ".."} for part in parts):
    raise SystemExit(1)

print("/" + "/".join(parts), end="")
PY
}

normalize_caddy_route_upstream() {
  local raw_upstream="$1"

  python3 - "${raw_upstream}" <<'PY'
import sys
from urllib.parse import urlsplit

raw_upstream = sys.argv[1]
if not raw_upstream or any(char.isspace() for char in raw_upstream):
    raise SystemExit(1)

parsed = urlsplit(raw_upstream)
if parsed.scheme.lower() not in {"http", "https"}:
    raise SystemExit(1)
if not parsed.hostname or parsed.username is not None or parsed.password is not None:
    raise SystemExit(1)
if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
    raise SystemExit(1)

try:
    port = parsed.port
except ValueError:
    raise SystemExit(1) from None

host = parsed.hostname.lower()
if ":" in host:
    host = f"[{host}]"
netloc = f"{host}:{port}" if port is not None else host
print(f"{parsed.scheme.lower()}://{netloc}", end="")
PY
}

normalize_caddy_reserved_path() {
  local path="$1"
  path="/${path#/}"
  path="${path%/}"
  [[ -n "${path}" ]] || path="/"
  printf '%s' "${path}"
}

list_serino_reserved_caddy_routes() {
  local api_path=""
  local admin_path=""
  local waline_path=""

  api_path="$(normalize_caddy_reserved_path "${AERISUN_API_BASE_PATH:-/api}")"
  admin_path="$(normalize_caddy_reserved_path "${AERISUN_ADMIN_BASE_PATH:-/admin/}")"
  waline_path="$(normalize_caddy_reserved_path "${AERISUN_WALINE_BASE_PATH:-/waline}")"

  printf 'exact\t/\n'
  printf 'prefix\t%s\n' "${api_path}"
  printf 'prefix\t%s\n' "${admin_path}"
  printf 'prefix\t%s\n' "${waline_path}"
  printf '%s\n' \
    $'prefix\t/media' \
    $'prefix\t/assets' \
    $'prefix\t/fonts' \
    $'prefix\t/posts' \
    $'prefix\t/diary' \
    $'prefix\t/feeds'
  printf '%s\n' \
    $'exact\t/manifest.webmanifest' \
    $'exact\t/bootstrap.js' \
    $'exact\t/friends' \
    $'exact\t/thoughts' \
    $'exact\t/excerpts' \
    $'exact\t/resume' \
    $'exact\t/guestbook' \
    $'exact\t/calendar' \
    $'exact\t/preview' \
    $'exact\t/robots.txt' \
    $'exact\t/llms.txt' \
    $'exact\t/resume.md' \
    $'exact\t/sitemap.xml' \
    $'exact\t/feed.xml' \
    $'exact\t/rss.xml' \
    $'exact\t/feeds.xml' \
    $'exact\t/index.html' \
    $'exact\t/registerSW.js' \
    $'exact\t/sw.js'
}

caddy_route_conflicts_with_serino() {
  local route_path="$1"
  local kind=""
  local reserved_path=""

  while IFS=$'\t' read -r kind reserved_path; do
    [[ -n "${reserved_path}" ]] || continue
    if [[ "${route_path}" == "${reserved_path}" || "${reserved_path}" == "${route_path}/"* ]]; then
      return 0
    fi
    if [[ "${kind}" == "prefix" && "${route_path}" == "${reserved_path}/"* ]]; then
      return 0
    fi
  done < <(list_serino_reserved_caddy_routes)

  return 1
}

caddy_route_id() {
  local route_path="$1"
  printf '%s' "${route_path}" | sha256sum | awk '{ print substr($1, 1, 16) }'
}

caddy_route_conflicts_with_registered() {
  local route_path="$1"
  local registered_path=""
  local upstream=""

  while IFS=$'\t' read -r registered_path upstream; do
    [[ -n "${registered_path}" ]] || continue
    if [[ "${route_path}" == "${registered_path}" || "${route_path}" == "${registered_path}/"* || "${registered_path}" == "${route_path}/"* ]]; then
      return 0
    fi
  done < <(list_caddy_routes)

  return 1
}

caddy_route_file_for_path() {
  local route_path="$1"
  printf '%s/route-%s.caddy' "${SERINO_CADDY_ROUTES_DIR}" "$(caddy_route_id "${route_path}")"
}

render_caddy_route_config() {
  local route_path="$1"
  local upstream="$2"
  local route_id=""

  route_id="$(caddy_route_id "${route_path}")"

  printf '# Managed by sercli. This file is local to this server.\n'
  printf '# serino-route-path: %s\n' "${route_path}"
  printf '# serino-route-upstream: %s\n' "${upstream}"
  printf '@serino_user_route_%s path %s %s/*\n' "${route_id}" "${route_path}" "${route_path}"
  printf 'handle @serino_user_route_%s {\n' "${route_id}"
  printf '    reverse_proxy %s\n' "${upstream}"
  printf '}\n'
}

list_caddy_routes() {
  local route_file=""
  local route_path=""
  local upstream=""

  path_is_dir "${SERINO_CADDY_ROUTES_DIR}" || return 0

  while IFS= read -r route_file; do
    route_path="$(sed -n 's/^# serino-route-path: //p' "${route_file}" | head -n 1)"
    upstream="$(sed -n 's/^# serino-route-upstream: //p' "${route_file}" | head -n 1)"
    if [[ -n "${route_path}" && -n "${upstream}" ]]; then
      printf '%s\t%s\n' "${route_path}" "${upstream}"
    fi
  done < <(find "${SERINO_CADDY_ROUTES_DIR}" -maxdepth 1 -type f -name 'route-*.caddy' -print | sort)
}

validate_registered_caddy_routes() {
  local route_path=""
  local upstream=""

  while IFS=$'\t' read -r route_path upstream; do
    [[ -n "${route_path}" ]] || continue
    if caddy_route_conflicts_with_serino "${route_path}"; then
      die "用户转发路径 ${route_path} 与当前版本的 Serino 固定路由冲突，请先移除或更换该路由。"
    fi
  done < <(list_caddy_routes)
}

ensure_caddy_routes_dir() {
  run_as_root install -d -o root -g root -m 0755 "${SERINO_CADDY_ROUTES_DIR}"
}

caddy_routes_container_is_running() {
  local container_id=""
  container_id="$(compose ps -q caddy 2>/dev/null | sed -n '1p' || true)"
  [[ -n "${container_id}" ]] || return 1
  [[ "$(run_as_root docker inspect --format '{{.State.Running}}' "${container_id}" 2>/dev/null || true)" == "true" ]]
}

validate_caddy_route_configuration() {
  if caddy_routes_container_is_running; then
    compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
    return
  fi

  compose run --rm --no-deps -T --entrypoint caddy caddy \
    validate --config /etc/caddy/Caddyfile --adapter caddyfile
}

reload_caddy_route_configuration_if_running() {
  caddy_routes_container_is_running || return 0
  compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
}
