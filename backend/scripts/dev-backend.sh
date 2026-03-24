#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=./process-env.sh
source "${SCRIPT_DIR}/process-env.sh"

exec "${SCRIPT_DIR}/bootstrap.sh"
