#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${PROJECT_DIR}/dist/installer"
RELEASE_TAG="${AERISUN_RELEASE_TAG:?AERISUN_RELEASE_TAG is required}"
VERSION="${AERISUN_RELEASE_VERSION:?AERISUN_RELEASE_VERSION is required}"
INSTALL_CHANNEL="${AERISUN_INSTALL_CHANNEL:-stable}"
DOCKERHUB_NAMESPACE="${AERISUN_INSTALL_DOCKERHUB_NAMESPACE:-aerisun}"
IMAGE_REGISTRY="${AERISUN_IMAGE_REGISTRY:-}"
API_IMAGE_NAME="serino-api"
WEB_IMAGE_NAME="serino-web"
WALINE_IMAGE_NAME="serino-waline"
INSTALL_BASE_URL="${AERISUN_INSTALL_BASE_URL:-}"

render_bootstrap_script() {
  local target_file="$1"
  local channel="$2"
  local base_url="$3"
  local install_version="${4:-}"

  {
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' 'set -euo pipefail'
    printf '\n'
    printf 'export AERISUN_INSTALL_CHANNEL="${AERISUN_INSTALL_CHANNEL:-%s}"\n' "${channel}"
    if [[ -n "${base_url}" ]]; then
      printf 'export AERISUN_INSTALL_BASE_URL="${AERISUN_INSTALL_BASE_URL:-%s}"\n' "${base_url}"
    fi
    if [[ -n "${install_version}" ]]; then
      printf 'export AERISUN_INSTALL_VERSION="${AERISUN_INSTALL_VERSION:-%s}"\n' "${install_version}"
    fi
    printf '\n'
    tail -n +4 "${PROJECT_DIR}/installer/install.sh"
  } > "${target_file}"

  chmod 0755 "${target_file}"
}

case "${INSTALL_CHANNEL}" in
  stable)
    IMAGE_REGISTRY="${IMAGE_REGISTRY:?AERISUN_IMAGE_REGISTRY is required for stable channel}"
    if [[ -z "${INSTALL_BASE_URL}" ]]; then
      INSTALL_BASE_URL="https://install.aerisun.top/serino"
    fi
    ;;
  dev)
    if [[ -z "${IMAGE_REGISTRY}" ]]; then
      IMAGE_REGISTRY="docker.io/${DOCKERHUB_NAMESPACE}"
    fi
    API_IMAGE_NAME="serino-dev-api"
    WEB_IMAGE_NAME="serino-dev-web"
    WALINE_IMAGE_NAME="serino-dev-waline"
    if [[ -z "${INSTALL_BASE_URL}" ]]; then
      INSTALL_BASE_URL="https://install.aerisun.top/serino/dev"
    fi
    ;;
  *)
    echo "Unsupported AERISUN_INSTALL_CHANNEL=${INSTALL_CHANNEL}" >&2
    exit 1
    ;;
esac

mkdir -p "${DIST_DIR}"
find "${DIST_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

cat > "${DIST_DIR}/latest.env" <<EOF
AERISUN_INSTALL_VERSION=${RELEASE_TAG}
EOF

cat > "${DIST_DIR}/aerisun-installer-manifest.env" <<EOF
AERISUN_INSTALL_CHANNEL=${INSTALL_CHANNEL}
AERISUN_INSTALL_VERSION=${RELEASE_TAG}
AERISUN_IMAGE_TAG=${VERSION}
AERISUN_IMAGE_REGISTRY=${IMAGE_REGISTRY}
AERISUN_API_IMAGE_NAME=${API_IMAGE_NAME}
AERISUN_WEB_IMAGE_NAME=${WEB_IMAGE_NAME}
AERISUN_WALINE_IMAGE_NAME=${WALINE_IMAGE_NAME}
EOF

render_bootstrap_script "${DIST_DIR}/install.latest.sh" "${INSTALL_CHANNEL}" "${INSTALL_BASE_URL}"
render_bootstrap_script "${DIST_DIR}/install.sh" "${INSTALL_CHANNEL}" "${INSTALL_BASE_URL}" "${RELEASE_TAG}"
cp "${PROJECT_DIR}/docker-compose.release.yml" "${DIST_DIR}/docker-compose.release.yml"
cp "${PROJECT_DIR}/.env.production.local.example" "${DIST_DIR}/.env.production.local.example"

tar -czf "${DIST_DIR}/aerisun-installer-bundle.tar.gz" \
  -C "${PROJECT_DIR}" \
  docker-compose.release.yml \
  .env.production.local.example \
  installer
