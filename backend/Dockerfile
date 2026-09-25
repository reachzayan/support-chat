# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HOME=/home/app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/migrate.sh ./docker/migrate.sh

RUN chmod +x /entrypoint.sh /app/docker/migrate.sh \
    && uv sync --frozen --no-dev \
    && uv run playwright install-deps chromium \
    && uv run playwright install chromium \
    && uv run crawl4ai-setup \
    && groupadd --system app \
    && useradd --system --gid app --create-home --home-dir /home/app app \
    && chown -R app:app /app /home/app /ms-playwright

USER app

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
