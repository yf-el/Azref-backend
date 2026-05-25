FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY services/agent/pyproject.toml ./services/agent/
COPY services/users-service/pyproject.toml ./services/users-service/
COPY libs/auth_clerk/pyproject.toml ./libs/auth_clerk/
COPY libs/kafka_events/pyproject.toml ./libs/kafka_events/
COPY libs/cache_semantic/pyproject.toml ./libs/cache_semantic/

RUN uv sync --frozen --no-dev --no-install-workspace --package agent

COPY libs ./libs
COPY services/agent ./services/agent

RUN uv sync --frozen --no-dev --package agent

COPY services/agent/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /app/services/agent

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status == 200 else 1)"

CMD ["/entrypoint.sh"]
