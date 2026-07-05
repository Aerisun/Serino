#!/usr/bin/env bash

release_metadata_curl() {
  curl --fail --location --silent --show-error --retry 3 --retry-all-errors \
    --connect-timeout 10 --max-time 45 "$@"
}

release_asset_curl() {
  curl --fail --location --silent --show-error --retry 3 --retry-all-errors \
    --connect-timeout 10 --max-time 180 "$@"
}

sha256_file() {
  local file="$1"

  if command_exists sha256sum; then
    sha256sum "${file}" | awk '{print $1}'
    return 0
  fi

  if command_exists shasum; then
    shasum -a 256 "${file}" | awk '{print $1}'
    return 0
  fi

  return 1
}

verify_file_sha256() {
  local file="$1"
  local expected_sha256="$2"
  local actual_sha256=""

  [[ "${expected_sha256}" =~ ^[A-Fa-f0-9]{64}$ ]] || die "发布清单中的 sha256 格式无效。"
  if ! actual_sha256="$(sha256_file "${file}")"; then
    die "无法计算 ${file} 的 sha256：缺少 sha256sum/shasum。"
  fi

  [[ "${actual_sha256,,}" == "${expected_sha256,,}" ]] || \
    die "${file} sha256 校验失败：expected=${expected_sha256} actual=${actual_sha256}"
}

validate_release_tag() {
  [[ "$1" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "版本号必须是 v1.2.3 这种格式。"
}

current_channel_base_url() {
  if [[ -n "${AERISUN_INSTALL_BASE_URL:-}" ]]; then
    printf '%s' "${AERISUN_INSTALL_BASE_URL}"
    return 0
  fi

  if [[ "${AERISUN_INSTALL_CHANNEL}" == "dev" ]]; then
    printf '%s' "${AERISUN_INSTALL_DEFAULT_DEV_BASE_URL}"
    return 0
  fi

  printf '%s' "${AERISUN_INSTALL_DEFAULT_BASE_URL}"
}

extract_release_tag_from_env_payload() {
  sed -n "s/^[[:space:]]*AERISUN_INSTALL_VERSION[[:space:]]*=[[:space:]]*['\"]\\{0,1\\}\\(v[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" \
    | head -n 1
}

release_download_base_urls() {
  local version="$1"
  local base_url=""
  base_url="$(current_channel_base_url)"
  if [[ -n "${base_url}" ]]; then
    printf '%s\n' "${base_url%/}/${version}"
  fi
  if [[ "${AERISUN_INSTALL_CHANNEL}" == "stable" ]]; then
    printf '%s\n' "https://github.com/${AERISUN_INSTALL_GITHUB_REPO}/releases/download/${version}"
  fi
}

download_release_asset() {
  local version="$1"
  local asset_name="$2"
  local destination="$3"
  local url=""
  local base_urls=()
  local idx=0
  local actual_sha256=""

  while IFS= read -r base_url; do
    base_urls+=("${base_url}")
  done < <(release_download_base_urls "${version}")

  for idx in "${!base_urls[@]}"; do
    url="${base_urls[${idx}]%/}/${asset_name}"
    if release_asset_curl "${url}" -o "${destination}"; then
      if [[ "${asset_name}" == "${AERISUN_INSTALL_BUNDLE_NAME}" ]]; then
        if [[ -n "${AERISUN_INSTALL_BUNDLE_SHA256:-}" ]]; then
          log_info "正在校验 ${asset_name} sha256。"
          [[ "${AERISUN_INSTALL_BUNDLE_SHA256}" =~ ^[A-Fa-f0-9]{64}$ ]] || die "发布清单中的 sha256 格式无效。"
          if ! actual_sha256="$(sha256_file "${destination}")"; then
            die "无法计算 ${destination} 的 sha256：缺少 sha256sum/shasum。"
          fi
          if [[ "${actual_sha256,,}" != "${AERISUN_INSTALL_BUNDLE_SHA256,,}" ]]; then
            if (( idx + 1 < ${#base_urls[@]} )); then
              log_warn "${asset_name} sha256 校验失败：${url}"
              log_warn "正在回退到下一个分发源：${base_urls[$((idx + 1))]%/}/${asset_name}"
              continue
            fi
            die "${destination} sha256 校验失败：expected=${AERISUN_INSTALL_BUNDLE_SHA256} actual=${actual_sha256}"
          fi
        else
          log_warn "发布清单未提供 ${asset_name} sha256，已跳过安装包完整性校验。"
        fi
      fi
      return 0
    fi

    if (( idx + 1 < ${#base_urls[@]} )); then
      log_warn "下载 ${asset_name} 失败：${url}"
      log_warn "正在回退到下一个分发源：${base_urls[$((idx + 1))]%/}/${asset_name}"
    fi
  done

  die "无法下载 ${asset_name}（version=${version}）。已尝试：$(printf '%s ' "${base_urls[@]}")"
}

fetch_latest_release_tag() {
  local api_url="https://api.github.com/repos/${AERISUN_INSTALL_GITHUB_REPO}/releases/latest"
  local tag
  local base_url=""

  base_url="$(current_channel_base_url)"
  if [[ -n "${base_url}" ]]; then
    tag="$(
      release_metadata_curl \
        "${base_url%/}/latest.env" 2>/dev/null \
        | extract_release_tag_from_env_payload \
        || true
    )"
    if [[ -n "${tag}" ]]; then
      validate_release_tag "${tag}"
      printf '%s' "${tag}"
      return 0
    fi
    log_warn "未能从 ${base_url%/}/latest.env 解析版本号。"
  fi

  if [[ "${AERISUN_INSTALL_CHANNEL}" != "stable" ]]; then
    die "渠道 ${AERISUN_INSTALL_CHANNEL} 缺少 latest.env，无法解析当前版本。"
  fi

  log_warn "正在回退到 GitHub Release API 解析 stable 最新版本。"
  tag="$(
    release_metadata_curl "${api_url}" \
      | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\(v[^"]*\)".*/\1/p' \
      | head -n 1
  )"

  [[ -n "${tag}" ]] || die "无法解析最新版本号。"
  validate_release_tag "${tag}"
  printf '%s' "${tag}"
}

resolve_release_tag() {
  if [[ -n "${AERISUN_INSTALL_VERSION}" ]]; then
    validate_release_tag "${AERISUN_INSTALL_VERSION}"
    printf '%s' "${AERISUN_INSTALL_VERSION}"
    return 0
  fi

  fetch_latest_release_tag
}

release_manifest_key_allowed() {
  case "$1" in
    AERISUN_INSTALL_CHANNEL|\
    AERISUN_INSTALL_VERSION|\
    AERISUN_IMAGE_TAG|\
    AERISUN_IMAGE_REGISTRY|\
    AERISUN_API_IMAGE_NAME|\
    AERISUN_WEB_IMAGE_NAME|\
    AERISUN_WALINE_IMAGE_NAME|\
    AERISUN_INSTALL_BUNDLE_SHA256|\
    AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

release_manifest_value_allowed() {
  local key="$1"
  local value="$2"

  case "${key}" in
    AERISUN_INSTALL_CHANNEL)
      [[ "${value}" =~ ^(stable|dev)$ ]]
      ;;
    AERISUN_INSTALL_VERSION)
      [[ "${value}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]
      ;;
    AERISUN_INSTALL_BUNDLE_SHA256)
      [[ "${value}" =~ ^[A-Fa-f0-9]{64}$ ]]
      ;;
    AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64)
      [[ "${value}" =~ ^[A-Za-z0-9+/=]+$ ]]
      ;;
    AERISUN_IMAGE_TAG|AERISUN_IMAGE_REGISTRY|AERISUN_API_IMAGE_NAME|AERISUN_WEB_IMAGE_NAME|AERISUN_WALINE_IMAGE_NAME)
      [[ "${value}" =~ ^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$ ]]
      ;;
    *)
      return 1
      ;;
  esac
}

strip_manifest_quotes() {
  local value="$1"

  if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi

  printf '%s' "${value}"
}

parse_release_manifest() {
  local manifest_file="$1"
  local line=""
  local key=""
  local value=""

  while IFS= read -r line || [[ -n "${line}" ]]; do
    [[ "${line}" =~ ^[[:space:]]*$ ]] && continue
    [[ "${line}" =~ ^[[:space:]]*# ]] && continue

    if ! [[ "${line}" =~ ^[[:space:]]*(export[[:space:]]+)?([A-Z0-9_]+)[[:space:]]*=[[:space:]]*([^[:space:]]+)[[:space:]]*$ ]]; then
      die "发布清单包含不支持的行：${line}"
    fi

    key="${BASH_REMATCH[2]}"
    value="$(strip_manifest_quotes "${BASH_REMATCH[3]}")"

    if ! release_manifest_key_allowed "${key}"; then
      [[ "${value}" =~ ^[A-Za-z0-9][A-Za-z0-9._:/@+,-]*$ ]] || die "发布清单变量 ${key} 的值无效。"
      log_warn "发布清单包含当前安装器未识别的变量，已忽略：${key}"
      continue
    fi

    release_manifest_value_allowed "${key}" "${value}" || die "发布清单变量 ${key} 的值无效。"
    printf -v "${key}" '%s' "${value}"
  done < "${manifest_file}"
}

load_release_manifest() {
  local version="$1"
  local manifest_file="$2"

  download_release_asset "${version}" "${AERISUN_INSTALL_MANIFEST_NAME}" "${manifest_file}"
  AERISUN_IMAGE_TAG=""
  AERISUN_IMAGE_REGISTRY=""
  AERISUN_INSTALL_BUNDLE_SHA256=""
  parse_release_manifest "${manifest_file}"

  [[ -n "${AERISUN_IMAGE_TAG:-}" ]] || die "安装清单缺少 AERISUN_IMAGE_TAG。"
  [[ -n "${AERISUN_IMAGE_REGISTRY:-}" ]] || die "安装清单缺少 AERISUN_IMAGE_REGISTRY。"
  if [[ -n "${AERISUN_EXPECTED_INSTALL_BUNDLE_SHA256:-}" ]]; then
    [[ "${AERISUN_EXPECTED_INSTALL_BUNDLE_SHA256}" =~ ^[A-Fa-f0-9]{64}$ ]] || die "signed release metadata 中的安装包 sha256 格式无效。"
    [[ -n "${AERISUN_INSTALL_BUNDLE_SHA256:-}" ]] || die "安装清单缺少 AERISUN_INSTALL_BUNDLE_SHA256，无法匹配 signed release metadata。"
    if [[ "${AERISUN_INSTALL_BUNDLE_SHA256,,}" != "${AERISUN_EXPECTED_INSTALL_BUNDLE_SHA256,,}" ]]; then
      die "安装清单中的 bundle sha256 与 signed release metadata 不一致。"
    fi
  fi
  if [[ -n "${AERISUN_EXPECTED_UPDATE_TRUSTED_PUBLIC_KEY_B64:-}" ]]; then
    [[ "${AERISUN_EXPECTED_UPDATE_TRUSTED_PUBLIC_KEY_B64}" =~ ^[A-Za-z0-9+/=]+$ ]] || die "signed release metadata 中的 trusted public key 格式无效。"
    [[ -n "${AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64:-}" ]] || die "安装清单缺少 AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64，无法匹配 signed release metadata。"
    if [[ "${AERISUN_UPDATE_TRUSTED_PUBLIC_KEY_B64}" != "${AERISUN_EXPECTED_UPDATE_TRUSTED_PUBLIC_KEY_B64}" ]]; then
      die "安装清单中的 trusted public key 与 signed release metadata 不一致。"
    fi
  fi
  AERISUN_INSTALL_CHANNEL="${AERISUN_INSTALL_CHANNEL:-stable}"
  AERISUN_API_IMAGE_NAME="${AERISUN_API_IMAGE_NAME:-serino-api}"
  AERISUN_WEB_IMAGE_NAME="${AERISUN_WEB_IMAGE_NAME:-serino-web}"
  AERISUN_WALINE_IMAGE_NAME="${AERISUN_WALINE_IMAGE_NAME:-serino-waline}"
}
