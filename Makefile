.PHONY: dev dev-ts dev-pseed dev-smoke dev-stop check-secrets install-git-hooks docker-dev docker-prod docker-smoke setup-ports

DEV_TAILSCALE_SERVE ?= 0

# ── 本地开发（不走 Docker）──────────────────────────────
dev: 
	@if [ "$(DEV_TAILSCALE_SERVE)" = "1" ]; then bash ./scripts/dev-tailscale.sh authorize ./.env.development.local; fi
	@bash ./scripts/setup-ports.sh
	@AERISUN_DEV_TAILSCALE=$(DEV_TAILSCALE_SERVE) AERISUN_SEED_DEV_DATA=true AERISUN_SEED_PROFILE=dev-seed bash ./scripts/dev-start.sh

dev-ts: DEV_TAILSCALE_SERVE=1
dev-ts: dev

dev-pseed:
	@bash ./scripts/setup-ports.sh
	@AERISUN_DEV_TAILSCALE=$(DEV_TAILSCALE_SERVE) AERISUN_SEED_DEV_DATA=false AERISUN_SEED_PROFILE=seed bash ./scripts/dev-start.sh

dev-smoke:
	@bash ./scripts/dev-smoke.sh

dev-stop:
	@bash ./scripts/dev-stop.sh

check-secrets:
	@bash ./scripts/check-secrets-staged.sh --all

install-git-hooks:
	@bash ./scripts/install-git-hooks.sh

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
