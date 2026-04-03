#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
EXAMPLE_FILE="${ROOT_DIR}/.env.example"

if [[ ! -f "${EXAMPLE_FILE}" ]]; then
  echo "Missing ${EXAMPLE_FILE}" >&2
  exit 1
fi

if [[ -f "${ENV_FILE}" ]]; then
  echo ".env already exists at ${ENV_FILE}"
  exit 0
fi

cp "${EXAMPLE_FILE}" "${ENV_FILE}"
echo "Created ${ENV_FILE}"
echo "Next: edit the API key in ${ENV_FILE}, then run:"
echo "  python3 ${ROOT_DIR}/scripts/prepare_ai_bundle.py"
