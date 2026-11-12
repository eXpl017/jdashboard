# syntax=docker/dockerfile:1
#
# Container image for the Japan Cybersecurity Jobs dashboard.
#
# - Reproducible: dependencies come from the committed uv.lock.
# - Small: runtime dependencies only, no dev tooling, no test fixtures.
# - Non-root: the app runs as an unprivileged user and writes only to /data.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# uv keeps dependency resolution fast and reproducible from the lockfile.
# Pin the tag to the uv version used on the host (see docs/operations.md).
COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/

# Dependency layer: only pyproject.toml/uv.lock/README.md change the install.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project \
    && rm -rf /root/.cache/uv

# Application layer.
COPY app ./app
COPY scripts ./scripts

# /data holds the SQLite database and is the volume mount point.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

# Bind to 0.0.0.0 inside the container; publish to 127.0.0.1 on the host.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
