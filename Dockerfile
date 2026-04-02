FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir .

# Intentionally uses the source-tree CLI for startup validation only.
# This container is not the serving deployment path yet.
CMD ["python", "src/saudi_open_data_mcp/cli.py", "check-startup"]
