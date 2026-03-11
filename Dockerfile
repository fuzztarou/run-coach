# Stage 1: ビルド
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY run_coach/ run_coach/
COPY alembic/ alembic/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

# Stage 2: ランタイム
FROM python:3.11-slim-bookworm AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY run_coach/ run_coach/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY config/settings.example.yaml config/settings.yaml
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
CMD ["./entrypoint.sh"]
