.PHONY: dev docker-dev docker-prod setup-ports

# ── 本地开发（不走 Docker）──────────────────────────────
dev:
	@echo "Starting backend + frontend + admin..."
	AERISUN_ENVIRONMENT=development bash backend/scripts/bootstrap.sh &
	cd frontend && npx vite --mode development &
	cd admin && npx vite --mode development &
	@wait

# ── Docker 开发 ─────────────────────────────────────────
docker-dev:
	docker compose --env-file .env --env-file .env.development up --build

# ── Docker 生产 ─────────────────────────────────────────
docker-prod:
	docker compose --env-file .env --env-file .env.production --env-file .env.production.local up -d --build

# ── Worktree 端口自动检测 ───────────────────────────────
setup-ports:
	./scripts/setup-ports.sh
