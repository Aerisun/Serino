#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${PROJECT_DIR}/dist/installer"
RELEASE_TAG="${AERISUN_RELEASE_TAG:?AERISUN_RELEASE_TAG is required}"
VERSION="${AERISUN_RELEASE_VERSION:?AERISUN_RELEASE_VERSION is required}"
PRIMARY_REGISTRY="${AERISUN_IMAGE_PRIMARY_REGISTRY:-}"
FALLBACK_REGISTRY="${AERISUN_IMAGE_FALLBACK_REGISTRY:?AERISUN_IMAGE_FALLBACK_REGISTRY is required}"

mkdir -p "${DIST_DIR}"
rm -rf "${DIST_DIR:?}/"*

cat > "${DIST_DIR}/aerisun-installer-manifest.env" <<EOF
AERISUN_INSTALL_VERSION=${RELEASE_TAG}
AERISUN_IMAGE_TAG=${VERSION}
AERISUN_IMAGE_PRIMARY_REGISTRY=${PRIMARY_REGISTRY}
AERISUN_IMAGE_FALLBACK_REGISTRY=${FALLBACK_REGISTRY}
EOF

cp "${PROJECT_DIR}/installer/install.sh" "${DIST_DIR}/install.sh"
cp "${PROJECT_DIR}/docker-compose.release.yml" "${DIST_DIR}/docker-compose.release.yml"
cp "${PROJECT_DIR}/.env.production.local.example" "${DIST_DIR}/.env.production.local.example"

tar -czf "${DIST_DIR}/aerisun-installer-bundle.tar.gz" \
  -C "${PROJECT_DIR}" \
  docker-compose.release.yml \
  .env.production.local.example \
  installer
