FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir .

# Intentionally uses the supported source-tree CLI path for the current repo workflow, rather than an installed-package entrypoint.
CMD ["python", "src/saudi_open_data_mcp/cli.py", "check-startup"]
