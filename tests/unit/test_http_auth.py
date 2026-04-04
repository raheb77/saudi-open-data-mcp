"""Unit tests for minimal HTTP bearer auth."""

from __future__ import annotations

import json
import logging

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from saudi_open_data_mcp.observability import get_metrics
from saudi_open_data_mcp.security.http_auth import build_http_auth_middleware


async def _ok(_) -> JSONResponse:
    return JSONResponse({"ok": True})


def _app() -> Starlette:
    return Starlette(
        routes=[Route("/mcp", endpoint=_ok, methods=["GET"])],
        middleware=build_http_auth_middleware("internal-test-token"),
    )


@pytest.mark.asyncio
async def test_missing_bearer_token_is_rejected(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/mcp")

    assert response.status_code == 401
    assert response.json() == {"error": "missing bearer token"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert get_metrics().get("http.auth.requests") == 1
    assert get_metrics().get("http.auth.rejected") == 1
    assert get_metrics().get("http.auth.rejected.missing") == 1
    assert any(
        json.loads(record.getMessage())["reason"] == "missing_bearer_token"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_invalid_bearer_token_is_rejected(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/mcp",
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert response.status_code == 401
    assert response.json() == {"error": "invalid bearer token"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert get_metrics().get("http.auth.requests") == 1
    assert get_metrics().get("http.auth.rejected") == 1
    assert get_metrics().get("http.auth.rejected.invalid") == 1
    assert any(
        json.loads(record.getMessage())["reason"] == "invalid_bearer_token"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_valid_bearer_token_is_accepted() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert get_metrics().get("http.auth.requests") == 1
    assert get_metrics().get("http.auth.accepted") == 1
    assert get_metrics().get("http.auth.rejected") == 0
