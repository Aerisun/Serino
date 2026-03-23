#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"

cd "${BACKEND_DIR}"
export PYTHONPATH="${BACKEND_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

# Source env files in layered order (later overrides earlier).
# In Docker, PROJECT_DIR is /app and these files won't exist —
# env vars are injected via docker-compose environment: directives instead.
_source_if_exists() { [[ -f "$1" ]] && { set -a; source "$1"; set +a; } || true; }

_env="${AERISUN_ENVIRONMENT:-development}"
_source_if_exists "${PROJECT_DIR}/.env"
_source_if_exists "${PROJECT_DIR}/.env.${_env}"
_source_if_exists "${PROJECT_DIR}/.env.local"
_source_if_exists "${PROJECT_DIR}/.env.${_env}.local"

if [[ "$_env" == "development" ]]; then
  # Database preflight: detect schema drift and seed changes
  PREFLIGHT_JSON=$(python - <<'PY'
import json, os
from pathlib import Path
from aerisun.core.settings import get_settings
from aerisun.core.db_preflight import run_preflight

settings = get_settings()
settings.ensure_directories()

backend_dir = Path(os.environ["BACKEND_DIR"])
result = run_preflight(
    db_path=settings.db_path,
    alembic_dir=backend_dir / "alembic",
    seed_path=backend_dir / "src" / "aerisun" / "core" / "seed.py",
)
print(json.dumps(result))
PY
  )
  echo "DB preflight: ${PREFLIGHT_JSON}"

  if echo "$PREFLIGHT_JSON" | python -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get('reseed') else 1)"; then
    export AERISUN_FORCE_RESEED=true
  fi
else
  python - <<'PY'
from aerisun.core.settings import get_settings
get_settings().ensure_directories()
PY
fi

export BACKEND_DIR="${BACKEND_DIR}"
uv run alembic upgrade head

# Ensure Waline SQLite tables exist (Waline may not auto-create them)
uv run python - <<'PY'
from aerisun.domain.waline.service import connect_waline_db, get_waline_db_path

db_path = get_waline_db_path()
with connect_waline_db(db_path):
    pass

print(f"Waline tables ensured in {db_path}")
PY

exec "${SCRIPT_DIR}/serve.sh"
