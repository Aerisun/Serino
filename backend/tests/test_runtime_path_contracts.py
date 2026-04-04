from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def read_project_file(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_shared_path_defaults_are_tracked_in_root_env():
    env_text = read_project_file(".env")

    assert "AERISUN_API_BASE_PATH=/api" in env_text
    assert "AERISUN_ADMIN_BASE_PATH=/admin/" in env_text
    assert "AERISUN_WALINE_BASE_PATH=/waline" in env_text
    assert "AERISUN_HEALTHCHECK_PATH=/api/v1/site/healthz" in env_text
    assert "AERISUN_FRONTEND_DIST_DIR=/srv/aerisun/frontend" in env_text
    assert "AERISUN_ADMIN_DIST_DIR=/srv/aerisun/admin" in env_text


def test_deploy_contract_reuses_shared_env_keys():
    compose_text = read_project_file("docker-compose.yml")
    release_compose_text = read_project_file("docker-compose.release.yml")
    caddy_text = read_project_file("Caddyfile")
    smoke_text = read_project_file("scripts/docker-smoke.sh")
    dev_smoke_text = read_project_file("scripts/dev-smoke.sh")
    dev_start_text = read_project_file("scripts/dev-start.sh")
    frontend_vite_text = read_project_file("frontend/vite.config.ts")
    admin_vite_text = read_project_file("admin/vite.config.ts")

    assert "AERISUN_PORT: ${AERISUN_PORT:-8000}" in compose_text
    assert "AERISUN_HEALTHCHECK_PATH: ${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/healthz}" in compose_text
    healthcheck_curl = (
        'curl", "-f", "http://localhost:${AERISUN_PORT:-8000}${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/healthz}'
    )
    assert healthcheck_curl in compose_text
    assert "WALINE_JWT_TOKEN: ${WALINE_JWT_TOKEN}" in compose_text
    assert "AERISUN_SEED_REFERENCE_DATA: ${AERISUN_SEED_REFERENCE_DATA:-true}" in release_compose_text
    assert "AERISUN_DATA_BACKFILL_ENABLED: ${AERISUN_DATA_BACKFILL_ENABLED:-true}" in release_compose_text
    assert "AERISUN_API_BASE_PATH: ${AERISUN_API_BASE_PATH:-/api}" in compose_text
    assert "AERISUN_ADMIN_BASE_PATH: ${AERISUN_ADMIN_BASE_PATH:-/admin/}" in compose_text
    assert "AERISUN_WALINE_BASE_PATH: ${AERISUN_WALINE_BASE_PATH:-/waline}" in compose_text
    assert "AERISUN_FRONTEND_DIST_DIR: ${AERISUN_FRONTEND_DIST_DIR:-/srv/aerisun/frontend}" in compose_text
    assert "AERISUN_ADMIN_DIST_DIR: ${AERISUN_ADMIN_DIST_DIR:-/srv/aerisun/admin}" in compose_text
    assert '- "127.0.0.1:${AERISUN_PORT:-8000}:${AERISUN_PORT:-8000}"' in compose_text
    assert "{$AERISUN_PORT:8000}" in caddy_text
    assert "{$AERISUN_API_BASE_PATH:/api}" in caddy_text
    assert "{$AERISUN_ADMIN_BASE_PATH:/admin/}" in caddy_text
    assert "{$AERISUN_WALINE_BASE_PATH:/waline}" in caddy_text
    assert "{$AERISUN_FRONTEND_DIST_DIR:/srv/aerisun/frontend}" in caddy_text
    assert "{$AERISUN_ADMIN_DIST_DIR:/srv/aerisun/admin}" in caddy_text

    assert 'HEALTHCHECK_PATH="${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/healthz}"' in smoke_text
    assert 'ADMIN_BASE_PATH="$(ensure_trailing_slash "${AERISUN_ADMIN_BASE_PATH:-/admin/}")"' in smoke_text
    assert 'WALINE_BASE_PATH="$(strip_trailing_slash "${AERISUN_WALINE_BASE_PATH:-/waline}")"' in smoke_text
    assert "AERISUN_DOMAIN=http://${SITE_HOST}" in smoke_text
    assert 'LOCAL_IMAGE_REGISTRY="${AERISUN_SMOKE_IMAGE_REGISTRY:-serino-smoke-local}"' in smoke_text
    assert "AERISUN_IMAGE_REGISTRY=${LOCAL_IMAGE_REGISTRY}" in smoke_text
    assert "WALINE_JWT_TOKEN=smoke-0123456789abcdef0123456789abcdef" in smoke_text
    assert "AERISUN_DATA_BACKFILL_ENABLED=true" in smoke_text

    assert 'healthcheck_path="${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/healthz}"' in dev_smoke_text
    assert 'admin_base_path="${AERISUN_ADMIN_BASE_PATH:-/admin/}"' in dev_smoke_text
    backend_health_url = (
        'backend_health_url="http://127.0.0.1:${AERISUN_PORT:-8000}${AERISUN_HEALTHCHECK_PATH:-/api/v1/site/healthz}"'
    )
    assert backend_health_url in dev_start_text
    assert 'const apiBasePath = stripTrailingSlash(env.AERISUN_API_BASE_PATH ?? "/api");' in frontend_vite_text
    assert 'const walineBasePath = stripTrailingSlash(env.AERISUN_WALINE_BASE_PATH ?? "/waline");' in frontend_vite_text
    assert 'const adminBasePath = normalizeBasePath(env.AERISUN_ADMIN_BASE_PATH || "", "/admin/");' in admin_vite_text
    assert 'const apiBasePath = (env.AERISUN_API_BASE_PATH || "/api").replace(/\\/+$/, "");' in admin_vite_text


def test_production_defaults_do_not_track_dev_only_upstreams():
    production_text = read_project_file(".env.production")
    dockerignore_text = read_project_file(".dockerignore")
    production_local_example_text = read_project_file(".env.production.local.example")

    assert "AERISUN_FRONTEND_UPSTREAM" not in production_text
    assert "AERISUN_ADMIN_UPSTREAM" not in production_text
    assert ".env.*.local" in dockerignore_text
    assert (
        "AERISUN_IMAGE_REGISTRY=crpi-hwvtw8db2uk7bil0.cn-beijing.personal.cr.aliyuncs.com/serino"
        in production_local_example_text
    )
    assert "AERISUN_SEED_REFERENCE_DATA=true" in production_local_example_text
    assert "AERISUN_DATA_BACKFILL_ENABLED=true" in production_local_example_text


def test_legacy_backend_process_scripts_are_removed():
    assert not (PROJECT_ROOT / "backend/scripts/dev-backend.sh").exists()
    assert not (PROJECT_ROOT / "backend/scripts/dev-waline.sh").exists()
    assert not (PROJECT_ROOT / "backend/scripts/process-env.sh").exists()
    assert not (PROJECT_ROOT / "backend/scripts/backup.sh").exists()
    assert not (PROJECT_ROOT / "backend/scripts/restore.sh").exists()
    assert not (PROJECT_ROOT / "backend/litestream.yml.template").exists()

    tracked_texts = [
        read_project_file("README.md"),
        read_project_file("Makefile"),
        read_project_file("scripts/dev-start.sh"),
        read_project_file("scripts/dev-smoke.sh"),
        read_project_file("scripts/sync-orval.sh"),
        read_project_file("backend/scripts/bootstrap.sh"),
    ]

    for text in tracked_texts:
        assert "dev-backend.sh" not in text
        assert "dev-waline.sh" not in text
        assert "process-env.sh" not in text
