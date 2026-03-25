.PHONY: dev dev-smoke dev-stop docker-dev docker-prod docker-smoke setup-ports

# ── 本地开发（不走 Docker）──────────────────────────────
dev: 
	@bash ./scripts/setup-ports.sh
	@bash ./scripts/dev-start.sh

dev-smoke:
	@bash ./scripts/dev-smoke.sh

dev-stop:
	@bash ./scripts/dev-stop.sh

# ── Docker 开发 ─────────────────────────────────────────
docker-dev:
	docker compose --env-file .env --env-file .env.development up --build

# ── Docker 生产 ─────────────────────────────────────────
docker-prod:
	docker compose --env-file .env --env-file .env.production --env-file .env.production.local up -d --build

docker-smoke:
	@bash ./scripts/docker-smoke.sh

# ── Worktree 端口自动检测 ───────────────────────────────
setup-ports:
	./scripts/setup-ports.sh
