# Asseta API + workers image (same image, different commands). Dependencies pinned by uv.lock.
FROM ghcr.io/astral-sh/uv:0.9.7 AS uv
FROM python:3.13.9-slim-bookworm AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

FROM python:3.13.9-slim-bookworm
RUN useradd --system --uid 10001 asseta
WORKDIR /app
COPY --from=build --chown=asseta:asseta /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER asseta
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=2)" || exit 1
CMD ["uvicorn", "asseta.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
