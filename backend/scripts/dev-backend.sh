#!/usr/bin/env bash
# DEPRECATED: This script is not part of the main development workflow.
# Use 'make dev' (which calls scripts/dev-start.sh) instead.
# This file is retained for reference and may be removed in a future cleanup.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=./process-env.sh
source "${SCRIPT_DIR}/process-env.sh"

exec "${SCRIPT_DIR}/bootstrap.sh"
