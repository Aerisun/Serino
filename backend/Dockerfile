FROM python:3.13-slim

ARG UV_VERSION=0.9.26

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/aerisun \
    UV_NO_DEV=1 \
    UV_FROZEN=1

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl openssh-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

COPY pyproject.toml ./
COPY uv.lock ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY src ./src

RUN uv sync --frozen --no-dev

RUN groupadd -r aerisun && useradd -m -d /home/aerisun -r -g aerisun -u 1001 aerisun \
    && mkdir -p /home/aerisun/.cache/uv \
    && chown -R aerisun:aerisun /app /home/aerisun

USER aerisun

EXPOSE 8000

CMD ["/bin/bash", "/app/backend/scripts/bootstrap.sh"]
