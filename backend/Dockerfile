FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl rsync openssh-client sqlite3 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY src ./src

RUN uv sync --no-dev

EXPOSE 8000

CMD ["/bin/bash", "/app/backend/scripts/bootstrap.sh"]
