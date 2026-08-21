FROM node:24-bookworm-slim AS codex-runtime

ARG CODEX_VERSION=0.147.0

RUN npm install --global --omit=dev "@openai/codex@${CODEX_VERSION}" \
    && codex --version \
    && codex_binary="$(find /usr/local/lib/node_modules/@openai -type f -path '*/vendor/*/bin/codex' -print -quit)" \
    && test -n "${codex_binary}" \
    && install -D -m 0755 "${codex_binary}" /opt/codex/codex \
    && /opt/codex/codex --version

FROM python:3.13-slim

ARG UV_VERSION=0.9.26

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/aerisun \
    UV_NO_DEV=1 \
    UV_FROZEN=1 \
    PATH=/app/backend/.venv/bin:$PATH

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl libnss-wrapper openssh-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

COPY --from=codex-runtime /opt/codex/codex /usr/local/bin/codex

COPY pyproject.toml ./
COPY uv.lock ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable

RUN groupadd -r aerisun && useradd -m -d /home/aerisun -r -g aerisun -u 1001 aerisun \
    && mkdir -p /home/aerisun/.cache/uv \
    && mkdir -p /srv/aerisun/caddy-routes \
    && chown -R aerisun:aerisun /app /home/aerisun /srv/aerisun/caddy-routes

USER aerisun

EXPOSE 8000

CMD ["/bin/bash", "/app/backend/scripts/bootstrap.sh"]
