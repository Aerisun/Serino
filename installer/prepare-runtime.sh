#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/routes.sh"

main() {
  require_root_or_sudo
  ensure_system_layout
  rebuild_caddy_route_dispatcher
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
