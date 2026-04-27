FROM ghcr.io/astral-sh/uv:0.11.2 AS uv

FROM python:3.12.13-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV UV_CACHE_DIR=/tmp/uv-cache
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never

COPY --from=uv /uv /usr/local/bin/uv
COPY --from=uv /uvx /usr/local/bin/uvx

WORKDIR /app

COPY pyproject.toml uv.lock README.md /app/
COPY src /app/src

RUN uv export \
        --format requirements.txt \
        --frozen \
        --no-dev \
        --no-emit-project \
        --output-file /app/requirements-runtime.txt \
    && uv build --wheel --out-dir /app/dist \
    && python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes -r /app/requirements-runtime.txt \
    && /opt/venv/bin/pip install --no-cache-dir --no-deps /app/dist/*.whl \
    && rm -rf /tmp/uv-cache

FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/saudi-open-data-mcp
ENV HTTP_HOST=0.0.0.0
ENV HTTP_PORT=8000
ENV REGISTRY_PATH=/var/lib/saudi-open-data-mcp/registry.sqlite
ENV SNAPSHOT_DIR=/var/lib/saudi-open-data-mcp/snapshots
ENV CACHE_DIR=/var/lib/saudi-open-data-mcp/cache
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

RUN addgroup --gid 10001 saudi-open-data-mcp \
    && adduser --uid 10001 --gid 10001 --home /home/saudi-open-data-mcp --disabled-password --gecos "" saudi-open-data-mcp \
    && mkdir -p /var/lib/saudi-open-data-mcp/snapshots /var/lib/saudi-open-data-mcp/cache \
    && chown -R saudi-open-data-mcp:saudi-open-data-mcp /var/lib/saudi-open-data-mcp /home/saudi-open-data-mcp /opt/venv

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import json,sys,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/startupz', timeout=3)); sys.exit(0 if data.get('ready') is True and data.get('status') == 'ready' else 1)"

# Starts as root only to repair mounted state-volume ownership, then drops to uid/gid 10001.
ENTRYPOINT ["python", "-m", "saudi_open_data_mcp.docker_entrypoint"]
CMD ["run-http"]
