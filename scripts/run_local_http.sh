#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  exec "${ROOT_DIR}/.venv/bin/python" src/saudi_open_data_mcp/cli.py run-http "$@"
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run python src/saudi_open_data_mcp/cli.py run-http "$@"
fi

exec "${PYTHON:-python}" src/saudi_open_data_mcp/cli.py run-http "$@"
