"""Contract tests for container runtime configuration files."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_dockerfile_pins_runtime_base_image() -> None:
    dockerfile = (_repo_root() / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.splitlines()[0] == "FROM python:3.12.13-slim-bookworm"


def test_compose_defaults_keep_internal_runtime_contract_explicit() -> None:
    compose = (_repo_root() / "docker-compose.yml").read_text(encoding="utf-8")

    assert "init: true" in compose
    assert (
        "HTTP_AUTH_CAPABILITIES: ${HTTP_AUTH_CAPABILITIES:-read,refresh,materialize}"
        in compose
    )
    assert "healthcheck:" in compose
    assert "http://127.0.0.1:8000/readyz" in compose
