"""Contract tests for container runtime configuration files."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_dockerfile_pins_reproducible_runtime_build_path() -> None:
    dockerfile = (_repo_root() / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.splitlines()[0] == "FROM ghcr.io/astral-sh/uv:0.11.2 AS uv"
    assert dockerfile.count("FROM python:3.12.13-slim-bookworm") == 2
    assert "uv export \\" in dockerfile
    assert "--frozen \\" in dockerfile
    assert (
        "/opt/venv/bin/pip install --no-cache-dir --require-hashes "
        "-r /app/requirements-runtime.txt"
    ) in dockerfile
    assert 'ENTRYPOINT ["saudi-open-data-mcp"]' in dockerfile


def test_compose_defaults_keep_internal_runtime_contract_explicit() -> None:
    compose = (_repo_root() / "docker-compose.yml").read_text(encoding="utf-8")

    assert "init: true" in compose
    assert "HTTP_AUTH_ROLE: ${HTTP_AUTH_ROLE:-operator}" in compose
    assert (
        "HTTP_AUTH_CAPABILITIES: ${HTTP_AUTH_CAPABILITIES:-read,refresh,materialize}"
        in compose
    )
    assert "healthcheck:" in compose
    assert "http://127.0.0.1:8000/startupz" in compose
