# syntax=docker/dockerfile:1.7

# ─── Stage 1: build venv with uv ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

# uv pins itself; copy the binary in instead of pip-installing.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_NO_INSTALLER_METADATA=1

WORKDIR /app

# Lock-only install first so the layer caches across source changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Now bring source and install the project itself.
COPY src/ ./src/
COPY migrations/ ./migrations/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ─── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# curl for HEALTHCHECK; tini for PID 1 signal handling.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl tini \
 && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    APP_WORKERS=1 \
    VOLUME_PATH=/data

WORKDIR /app

# Non-root.
RUN groupadd --system --gid 1000 app \
 && useradd  --system --uid 1000 --gid app --home-dir /app --shell /usr/sbin/nologin app \
 && mkdir -p /data \
 && chown -R app:app /app /data

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app src/         /app/src/
COPY --chown=app:app migrations/  /app/migrations/

# Build-time git metadata (pass via --build-arg in CI).
ARG GIT_COMMIT_SHA=unknown
ARG GIT_BRANCH=unknown
ARG GIT_DIRTY=0
ENV GIT_COMMIT_SHA=${GIT_COMMIT_SHA} \
    GIT_BRANCH=${GIT_BRANCH} \
    GIT_DIRTY=${GIT_DIRTY}

USER app

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${APP_PORT}/health" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["start_litestar"]
