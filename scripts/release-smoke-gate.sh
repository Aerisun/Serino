#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

run_shell_contract_checks() {
  bash -n \
    "${PROJECT_DIR}/installer/bin/sercli" \
    "${PROJECT_DIR}/installer/doctor.sh" \
    "${PROJECT_DIR}/installer/install.sh" \
    "${PROJECT_DIR}/installer/upgrade.sh" \
    "${PROJECT_DIR}/installer/uninstall.sh" \
    "${PROJECT_DIR}/installer/lib/docker.sh" \
    "${PROJECT_DIR}/backend/scripts/bootstrap.sh" \
    "${PROJECT_DIR}/backend/scripts/baseline-prod.sh" \
    "${PROJECT_DIR}/backend/scripts/data-migrate.sh" \
    "${PROJECT_DIR}/backend/scripts/first-admin-prod.sh" \
    "${PROJECT_DIR}/backend/scripts/migrate.sh"
}

run_backend_ops_tests() {
  (
    cd "${PROJECT_DIR}/backend"
    uv run pytest -q \
      tests/test_migrations.py \
      tests/test_bootstrap_seed.py \
      tests/test_data_backfills.py \
      tests/test_runtime_path_contracts.py \
      tests/test_installer_lifecycle.py
  )
}

run_docker_release_smoke() {
  "${PROJECT_DIR}/scripts/docker-smoke.sh"
}

main() {
  local run_shell_checks="true"
  local run_backend_tests="true"
  local run_docker_smoke="true"

  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --skip-shell-checks)
        run_shell_checks="false"
        shift
        ;;
      --skip-backend-tests)
        run_backend_tests="false"
        shift
        ;;
      --skip-docker-smoke)
        run_docker_smoke="false"
        shift
        ;;
      *)
        echo "不支持的参数：$1" >&2
        exit 1
        ;;
    esac
  done

  if [[ "${run_shell_checks}" == "true" ]]; then
    run_shell_contract_checks
  fi
  if [[ "${run_backend_tests}" == "true" ]]; then
    run_backend_ops_tests
  fi
  if [[ "${run_docker_smoke}" == "true" ]]; then
    run_docker_release_smoke
  fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
