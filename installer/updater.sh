#!/usr/bin/env bash
set -euo pipefail

UPDATER_READY_TIMEOUT="${SERINO_UPDATER_READY_TIMEOUT:-300}"

updater_now_iso() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

updater_current_version() {
  load_release_env_if_present
  refresh_update_runtime_paths
  resolve_release_version_value 2>/dev/null || printf '%s' "${AERISUN_RELEASE_VERSION:-${AERISUN_IMAGE_TAG:-unknown}}"
}

updater_current_channel() {
  load_release_env_if_present
  case "${AERISUN_INSTALL_CHANNEL:-stable}" in
    dev)
      printf '%s' "dev"
      ;;
    *)
      printf '%s' "stable"
      ;;
  esac
}

updater_latest_default_base_url() {
  if [[ -n "${AERISUN_INSTALL_BASE_URL:-}" ]]; then
    printf '%s' "${AERISUN_INSTALL_BASE_URL%/}"
    return
  fi
  if [[ "${AERISUN_INSTALL_CHANNEL:-stable}" == "dev" ]]; then
    printf '%s' "${AERISUN_INSTALL_DEFAULT_DEV_BASE_URL%/}"
    return
  fi
  printf '%s' "${AERISUN_INSTALL_DEFAULT_BASE_URL%/}"
}

updater_write_json() {
  local path="$1"
  shift
  run_as_root install -d -o "${SERINO_SERVICE_USER}" -g "${SERINO_SERVICE_GROUP}" -m 0750 "$(dirname "${path}")"
  run_as_root python3 - "$path" "$@" <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(sys.argv[2])
tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
try:
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
    except OSError:
        dir_fd = None
    if dir_fd is not None:
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
except Exception:
    try:
        tmp.unlink()
    except OSError:
        pass
    raise
PY
  run_as_root chown "${SERINO_SERVICE_USER}:${SERINO_SERVICE_GROUP}" "${path}"
  run_as_root chmod 0640 "${path}"
}

updater_status_json() {
  refresh_update_runtime_paths
  if [[ -f "${SERINO_UPDATE_STATUS_FILE}" ]]; then
    cat "${SERINO_UPDATE_STATUS_FILE}"
    return
  fi

  python3 - \
    "$(updater_current_version)" \
    "$(updater_current_channel)" \
    "$([[ -f "${SERINO_UPDATE_SUPPORT_MARKER}" ]] && printf true || printf false)" <<'PY'
from __future__ import annotations

import json
import sys

supported = sys.argv[3] == "true"
payload = {
    "schema_version": 1,
    "state": "idle" if supported else "unsupported",
    "current_version": sys.argv[1],
    "latest_version": None,
    "channel": sys.argv[2] or "stable",
    "update_available": False,
    "auto_update_supported": False,
    "auto_update_blocked_reason": None if supported else "宿主机 updater 尚未安装或当前部署不是标准安装器布局。",
    "signature_verified": False,
    "release": None,
    "checked_at": None,
    "request_id": None,
    "run_id": None,
    "last_error": None,
    "recent_log": [],
}
print(json.dumps(payload, ensure_ascii=False))
PY
}

updater_write_status() {
  local payload="$1"
  updater_write_json "${SERINO_UPDATE_STATUS_FILE}" "${payload}"
}

updater_log() {
  local message="$*"
  refresh_update_runtime_paths
  run_as_root mkdir -p "${SERINO_LOG_ROOT}"
  printf '%s %s\n' "$(updater_now_iso)" "${message}" | run_as_root tee -a "${SERINO_UPDATE_LOG_FILE}" >/dev/null
}

updater_recent_log_json() {
  if path_is_file "${SERINO_UPDATE_LOG_FILE}"; then
    run_as_root tail -n 20 "${SERINO_UPDATE_LOG_FILE}" | python3 -c 'import json,sys; print(json.dumps([line.rstrip("\n") for line in sys.stdin], ensure_ascii=False))'
    return
  fi
  printf '[]'
}

updater_state_payload() {
  local state="$1"
  local latest_version="${2:-}"
  local update_available="${3:-false}"
  local signature_verified="${4:-false}"
  local blocked_reason="${5:-}"
  local last_error="${6:-}"
  local release_json="${7:-null}"
  python3 - \
    "${state}" \
    "$(updater_current_version)" \
    "${latest_version}" \
    "$(updater_current_channel)" \
    "${update_available}" \
    "${signature_verified}" \
    "${blocked_reason}" \
    "${last_error}" \
    "$(updater_now_iso)" \
    "$(updater_recent_log_json)" \
    "${release_json}" <<'PY'
from __future__ import annotations

import json
import re
import sys

latest = sys.argv[3] or None
signature_verified = sys.argv[6] == "true"
blocked = sys.argv[7] or None
release = json.loads(sys.argv[11])
bundle_sha256 = release.get("bundle_sha256") if isinstance(release, dict) else None
trusted_public_key_b64 = release.get("trusted_public_key_b64") if isinstance(release, dict) else None
bundle_sha256_valid = isinstance(bundle_sha256, str) and re.fullmatch(r"[A-Fa-f0-9]{64}", bundle_sha256)
trusted_public_key_valid = isinstance(trusted_public_key_b64, str) and re.fullmatch(r"[A-Za-z0-9+/=]+", trusted_public_key_b64)
if signature_verified and sys.argv[5] == "true" and bundle_sha256_valid and not trusted_public_key_valid:
    blocked = blocked or "签名元数据缺少 trusted public key，禁止后台自动升级。"
payload = {
    "schema_version": 1,
    "state": sys.argv[1],
    "current_version": sys.argv[2],
    "latest_version": latest,
    "channel": sys.argv[4] or "stable",
    "update_available": sys.argv[5] == "true",
    "auto_update_supported": bool(
        signature_verified and sys.argv[5] == "true" and bundle_sha256_valid and trusted_public_key_valid
    ),
    "auto_update_blocked_reason": blocked,
    "signature_verified": signature_verified,
    "release": release,
    "checked_at": sys.argv[9],
    "request_id": None,
    "run_id": None,
    "last_error": sys.argv[8] or None,
    "recent_log": json.loads(sys.argv[10]),
}
print(json.dumps(payload, ensure_ascii=False))
PY
}

updater_version_gt() {
  python3 - "$1" "$2" <<'PY'
from __future__ import annotations

import re
import sys

def parse(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?([0-9]+)\.([0-9]+)\.([0-9]+)", value.strip())
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())

raise SystemExit(0 if parse(sys.argv[1]) > parse(sys.argv[2]) else 1)
PY
}

updater_fetch_url() {
  release_metadata_curl "$1"
}

updater_validate_release_signature() {
  local release_file="$1"
  local trusted_key_b64="${AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64:-}"
  local payload_file=""
  local signature_file=""
  local public_key_file=""
  local status=1

  [[ -n "${trusted_key_b64}" ]] || return 1
  command_exists openssl || return 1

  payload_file="$(make_temp_file)"
  signature_file="$(make_temp_file)"
  public_key_file="$(make_temp_file)"
  if ! python3 - "${release_file}" "${payload_file}" "${signature_file}" <<'PY'
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

release = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
signed = release.get("signed")
signature = release.get("signature") or {}
if not isinstance(signed, dict) or not isinstance(signature, dict):
    raise SystemExit(1)
if signature.get("alg") != "rsa-sha256":
    raise SystemExit(1)
value = signature.get("value")
if not isinstance(value, str) or not value:
    raise SystemExit(1)
Path(sys.argv[2]).write_text(
    json.dumps(signed, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    encoding="utf-8",
)
Path(sys.argv[3]).write_bytes(base64.b64decode(value))
PY
  then
    rm -f "${payload_file}" "${signature_file}" "${public_key_file}"
    return 1
  fi
  if ! printf '%s' "${trusted_key_b64}" | base64 -d >"${public_key_file}"; then
    rm -f "${payload_file}" "${signature_file}" "${public_key_file}"
    return 1
  fi
  if openssl dgst -sha256 -verify "${public_key_file}" -signature "${signature_file}" "${payload_file}" >/dev/null 2>&1; then
    status=0
  fi
  rm -f "${payload_file}" "${signature_file}" "${public_key_file}"
  return "${status}"
}

updater_release_status_from_files() {
  local latest_file="$1"
  local release_file="$2"
  local notes_file="$3"
  local signature_verified="$4"
  python3 - "${latest_file}" "${release_file}" "${notes_file}" "${signature_verified}" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

latest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
release = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
signed = release.get("signed") if isinstance(release.get("signed"), dict) else release
notes = Path(sys.argv[3]).read_text(encoding="utf-8") if Path(sys.argv[3]).exists() else ""
signature = release.get("signature") if isinstance(release.get("signature"), dict) else None
payload = {
    "version": signed.get("version") or latest.get("version"),
    "released_at": signed.get("released_at"),
    "notes": notes,
    "notes_format": "markdown",
    "release_json_url": latest.get("release_json_url"),
    "manifest_url": signed.get("manifest_url"),
    "bundle_sha256": signed.get("bundle_sha256"),
    "trusted_public_key_b64": signed.get("trusted_public_key_b64"),
    "signature_key_id": signature.get("key_id") if signature else None,
}
print(json.dumps(payload, ensure_ascii=False))
PY
}

updater_legacy_release_status_from_files() {
  local latest_env_file="$1"
  local manifest_file="$2"
  local manifest_url="$3"
  python3 - "${latest_env_file}" "${manifest_file}" "${manifest_url}" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

latest_env = Path(sys.argv[1]).read_text(encoding="utf-8")
manifest = Path(sys.argv[2]).read_text(encoding="utf-8")

def env_value(text: str, key: str) -> str | None:
    pattern = rf"^\s*(?:export\s+)?{re.escape(key)}\s*=\s*['\"]?([^'\"\s]+)['\"]?\s*$"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return match.group(1)
    return None

version = env_value(latest_env, "AERISUN_INSTALL_VERSION") or env_value(manifest, "AERISUN_INSTALL_VERSION")
bundle_sha256 = env_value(manifest, "AERISUN_INSTALL_BUNDLE_SHA256")
if not version or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", version):
    raise SystemExit(1)
if bundle_sha256 and not re.fullmatch(r"[A-Fa-f0-9]{64}", bundle_sha256):
    raise SystemExit(1)

payload = {
    "version": version,
    "released_at": None,
    "notes": "此发布源仍使用 legacy latest.env/manifest 元数据，可提示新版本，但缺少签名元数据，不能从后台一键升级。",
    "notes_format": "markdown",
    "release_json_url": None,
    "manifest_url": sys.argv[3],
    "bundle_sha256": bundle_sha256,
    "signature_key_id": None,
}
print(json.dumps(payload, ensure_ascii=False))
PY
}

updater_verified_bundle_sha256_for_target() {
  local target_version="$1"
  python3 - "${SERINO_UPDATE_STATUS_FILE}" "${target_version}" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
target_version = sys.argv[2]
release = payload.get("release")
if payload.get("latest_version") != target_version or payload.get("signature_verified") is not True:
    raise SystemExit(1)
if not isinstance(release, dict):
    raise SystemExit(1)
bundle_sha256 = release.get("bundle_sha256")
if not isinstance(bundle_sha256, str) or not re.fullmatch(r"[A-Fa-f0-9]{64}", bundle_sha256):
    raise SystemExit(1)
print(bundle_sha256)
PY
}

updater_verified_trusted_public_key_for_target() {
  local target_version="$1"
  python3 - "${SERINO_UPDATE_STATUS_FILE}" "${target_version}" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
target_version = sys.argv[2]
release = payload.get("release")
if payload.get("latest_version") != target_version or payload.get("signature_verified") is not True:
    raise SystemExit(1)
if not isinstance(release, dict):
    raise SystemExit(1)
trusted_public_key_b64 = release.get("trusted_public_key_b64")
if not isinstance(trusted_public_key_b64, str) or not re.fullmatch(r"[A-Za-z0-9+/=]+", trusted_public_key_b64):
    raise SystemExit(1)
print(trusted_public_key_b64)
PY
}

updater_check_updates_legacy() {
  local base_url="$1"
  local current_version="$2"
  local latest_env_url="${base_url%/}/latest.env"
  local latest_env_file=""
  local manifest_file=""
  local manifest_url=""
  local latest_version=""
  local release_payload="null"
  local state="idle"
  local update_available="false"
  local blocked_reason="legacy latest.env/manifest 元数据缺少签名，禁止后台自动升级。"

  latest_env_file="$(make_temp_file)"
  manifest_file="$(make_temp_file)"

  updater_log "latest.json unavailable; checking legacy ${latest_env_url}"
  if ! updater_fetch_url "${latest_env_url}" >"${latest_env_file}"; then
    updater_write_status "$(updater_state_payload failed "" false false "" "无法下载最新版本元数据。" null)"
    return 1
  fi

  latest_version="$(extract_release_tag_from_env_payload <"${latest_env_file}")"
  if [[ -z "${latest_version}" ]]; then
    updater_write_status "$(updater_state_payload failed "" false false "" "legacy latest.env 缺少有效版本号。" null)"
    return 1
  fi

  manifest_url="${base_url%/}/${latest_version}/${AERISUN_INSTALL_MANIFEST_NAME}"
  if ! updater_fetch_url "${manifest_url}" >"${manifest_file}"; then
    updater_write_status "$(updater_state_payload failed "${latest_version}" false false "" "无法下载 legacy 安装清单。" null)"
    return 1
  fi

  release_payload="$(updater_legacy_release_status_from_files "${latest_env_file}" "${manifest_file}" "${manifest_url}")"
  if updater_version_gt "${latest_version}" "${current_version}"; then
    state="available"
    update_available="true"
  fi

  updater_write_status "$(updater_state_payload "${state}" "${latest_version}" "${update_available}" false "${blocked_reason}" "" "${release_payload}")"
}

updater_check_updates() {
  refresh_update_runtime_paths
  ensure_update_runtime_layout
  load_release_env_if_present

  local base_url=""
  local latest_url=""
  local latest_file=""
  local release_file=""
  local notes_file=""
  local release_json_url=""
  local notes_url=""
  local latest_version=""
  local current_version=""
  local signature_verified="false"
  local release_payload="null"
  local blocked_reason=""
  local state="idle"
  local update_available="false"

  base_url="$(updater_latest_default_base_url)"
  latest_url="${base_url%/}/latest.json"
  latest_file="$(make_temp_file)"
  release_file="$(make_temp_file)"
  notes_file="$(make_temp_file)"
  current_version="$(updater_current_version)"

  updater_log "checking updates from ${latest_url}"
  if ! updater_fetch_url "${latest_url}" >"${latest_file}"; then
    updater_check_updates_legacy "${base_url}" "${current_version}"
    return $?
  fi

  release_json_url="$(python3 - "${latest_file}" <<'PY'
from __future__ import annotations
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
print(payload.get("release_json_url") or "")
PY
)"
  [[ -n "${release_json_url}" ]] || release_json_url="${base_url%/}/release.json"

  if ! updater_fetch_url "${release_json_url}" >"${release_file}"; then
    updater_write_status "$(updater_state_payload failed "" false false "" "无法下载版本元数据。" null)"
    return 1
  fi

  notes_url="$(python3 - "${latest_file}" "${release_file}" <<'PY'
from __future__ import annotations
import json, sys
latest = json.load(open(sys.argv[1], encoding="utf-8"))
release = json.load(open(sys.argv[2], encoding="utf-8"))
signed = release.get("signed") if isinstance(release.get("signed"), dict) else release
print(signed.get("release_notes_url") or latest.get("release_notes_url") or "")
PY
)"
  if [[ -n "${notes_url}" ]]; then
    updater_fetch_url "${notes_url}" >"${notes_file}" || true
  fi

  latest_version="$(python3 - "${latest_file}" "${release_file}" <<'PY'
from __future__ import annotations
import json, sys
latest = json.load(open(sys.argv[1], encoding="utf-8"))
release = json.load(open(sys.argv[2], encoding="utf-8"))
signed = release.get("signed") if isinstance(release.get("signed"), dict) else release
print(signed.get("version") or latest.get("version") or "")
PY
)"

  if updater_validate_release_signature "${release_file}"; then
    signature_verified="true"
  else
    blocked_reason="更新元数据尚未通过签名校验，禁止后台自动升级。"
  fi

  release_payload="$(updater_release_status_from_files "${latest_file}" "${release_file}" "${notes_file}" "${signature_verified}")"
  if updater_version_gt "${latest_version}" "${current_version}"; then
    state="available"
    update_available="true"
  fi

  updater_write_status "$(updater_state_payload "${state}" "${latest_version}" "${update_available}" "${signature_verified}" "${blocked_reason}" "" "${release_payload}")"
}

updater_next_request() {
  find "${SERINO_UPDATE_REQUESTS_DIR}" -maxdepth 1 -type f -name '*.json' 2>/dev/null | sort | sed -n '1p'
}

updater_process_request() {
  local request_file="$1"
  local run_id=""
  local run_file=""
  local action=""
  local target_version=""
  local requested_bundle_sha256=""
  local verified_bundle_sha256=""
  local verified_trusted_public_key_b64=""

  run_id="$(basename "${request_file}" .json)"
  run_file="${SERINO_UPDATE_RUNS_DIR}/${run_id}.json"
  run_as_root install -d -o "${SERINO_SERVICE_USER}" -g "${SERINO_SERVICE_GROUP}" -m 0750 "${SERINO_UPDATE_RUNS_DIR}"
  run_as_root mv "${request_file}" "${run_file}"
  action="$(python3 - "${run_file}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("action") or "")
PY
)"
  target_version="$(python3 - "${run_file}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("target_version") or "")
PY
)"
  requested_bundle_sha256="$(python3 - "${run_file}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("bundle_sha256") or "")
PY
)"

  case "${action}" in
    check)
      updater_write_status "$(updater_state_payload checking "" false false "" "" null)"
      updater_check_updates
      ;;
    upgrade)
      updater_log "starting upgrade request ${run_id} target=${target_version}"
      if ! [[ "${target_version}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        updater_write_status "$(updater_state_payload failed "" false false "" "更新请求中的目标版本号无效。" null)"
        return 1
      fi
      if ! [[ "${requested_bundle_sha256}" =~ ^[A-Fa-f0-9]{64}$ ]]; then
        updater_write_status "$(updater_state_payload failed "${target_version}" true false "" "更新请求缺少已签名的安装包 sha256。" null)"
        return 1
      fi
      updater_write_status "$(updater_state_payload preflight "${target_version}" true true "" "" null)"
      if ! updater_check_updates; then
        updater_write_status "$(updater_state_payload failed "${target_version}" true false "" "升级前重新检查更新元数据失败。" null)"
        return 1
      fi
      if ! verified_bundle_sha256="$(updater_verified_bundle_sha256_for_target "${target_version}")"; then
        updater_write_status "$(updater_state_payload failed "${target_version}" true false "" "目标版本的签名元数据未通过校验。" null)"
        return 1
      fi
      if ! verified_trusted_public_key_b64="$(updater_verified_trusted_public_key_for_target "${target_version}")"; then
        updater_write_status "$(updater_state_payload failed "${target_version}" true false "" "目标版本的签名元数据缺少可信公钥。" null)"
        return 1
      fi
      if [[ "${verified_bundle_sha256,,}" != "${requested_bundle_sha256,,}" ]]; then
        updater_write_status "$(updater_state_payload failed "${target_version}" true false "" "更新请求与最新签名元数据中的安装包 sha256 不一致。" null)"
        return 1
      fi
      updater_write_status "$(updater_state_payload preflight "${target_version}" true true "" "" null)"
      if ! AERISUN_EXPECTED_INSTALL_BUNDLE_SHA256="${verified_bundle_sha256}" AERISUN_EXPECTED_UPDATE_TRUSTED_PUBLIC_KEY_B64="${verified_trusted_public_key_b64}" "${SERINO_BIN_LINK}" upgrade --check "${target_version}" >>"${SERINO_UPDATE_LOG_FILE}" 2>&1; then
        updater_write_status "$(updater_state_payload failed "${target_version}" true true "" "升级预检失败。" null)"
        return 1
      fi
      updater_write_status "$(updater_state_payload running "${target_version}" true true "" "" null)"
      if AERISUN_EXPECTED_INSTALL_BUNDLE_SHA256="${verified_bundle_sha256}" AERISUN_EXPECTED_UPDATE_TRUSTED_PUBLIC_KEY_B64="${verified_trusted_public_key_b64}" "${SERINO_BIN_LINK}" upgrade --ready-timeout "${UPDATER_READY_TIMEOUT}" "${target_version}" >>"${SERINO_UPDATE_LOG_FILE}" 2>&1; then
        updater_write_status "$(updater_state_payload succeeded "${target_version}" false true "" "" null)"
        return 0
      fi
      updater_write_status "$(updater_state_payload rolled_back "${target_version}" true true "" "升级失败，已尝试回滚。" null)"
      return 1
      ;;
    *)
      updater_write_status "$(updater_state_payload failed "" false false "" "未知更新请求类型：${action}" null)"
      return 1
      ;;
  esac
}

updater_cmd_run() {
  refresh_update_runtime_paths
  ensure_update_runtime_layout
  local request_file=""
  request_file="$(updater_next_request)"
  if [[ -n "${request_file}" ]]; then
    updater_process_request "${request_file}"
    return
  fi
  updater_check_updates
}

updater_cmd_check() {
  refresh_update_runtime_paths
  updater_write_status "$(updater_state_payload checking "" false false "" "" null)"
  updater_check_updates
}

updater_cmd_status() {
  refresh_update_runtime_paths
  local json_mode="false"
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --json)
        json_mode="true"
        ;;
      *)
        die "updater status 不支持参数：$1"
        ;;
    esac
    shift
  done

  if [[ "${json_mode}" == "true" ]]; then
    updater_status_json
    return
  fi

  local payload_json=""
  payload_json="$(updater_status_json)"
  python3 - "${payload_json}" <<'PY'
from __future__ import annotations

import json
import sys

payload = json.loads(sys.argv[1])
print("Serino 更新状态")
for key in ("state", "current_version", "latest_version", "channel", "update_available", "auto_update_supported"):
    print(f"  {key}: {payload.get(key)}")
if payload.get("auto_update_blocked_reason"):
    print(f"  blocked: {payload['auto_update_blocked_reason']}")
PY
}

cmd_updater() {
  local subcommand="${1:-status}"
  shift || true

  case "${subcommand}" in
    run)
      [[ "$#" -eq 0 ]] || die "updater run 不支持额外参数。"
      updater_cmd_run
      ;;
    check)
      [[ "$#" -eq 0 ]] || die "updater check 不支持额外参数。"
      updater_cmd_check
      ;;
    status)
      updater_cmd_status "$@"
      ;;
    *)
      die "未知的 updater 子命令：${subcommand}"
      ;;
  esac
}
