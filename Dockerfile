FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HTTP_HOST=0.0.0.0
ENV HTTP_PORT=8000
ENV REGISTRY_PATH=/var/lib/saudi-open-data-mcp/registry.sqlite
ENV SNAPSHOT_DIR=/var/lib/saudi-open-data-mcp/snapshots
ENV CACHE_DIR=/var/lib/saudi-open-data-mcp/cache

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN mkdir -p /var/lib/saudi-open-data-mcp/snapshots /var/lib/saudi-open-data-mcp/cache \
    && pip install --no-cache-dir .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import json,sys,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3)); sys.exit(0 if data.get('ready') is True and data.get('status') == 'ready' else 1)"

# Official internal container entrypoint: long-running MCP streamable HTTP serving.
ENTRYPOINT ["python", "src/saudi_open_data_mcp/cli.py"]
CMD ["run-http"]
