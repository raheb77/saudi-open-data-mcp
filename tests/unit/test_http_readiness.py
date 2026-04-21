"""Unit tests for the internal HTTP readiness surface."""

from __future__ import annotations

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from saudi_open_data_mcp.security.http_auth import build_http_auth_middleware
from saudi_open_data_mcp.security.http_readiness import (
    HTTP_READINESS_PATH,
    HTTPReadinessMiddleware,
    build_http_readiness_middleware,
)

VALID_HTTP_AUTH_TOKEN = "0123456789abcdef0123456789abcdef"


async def _ok(_) -> JSONResponse:
    return JSONResponse({"ok": True})


def _app() -> Starlette:
    return Starlette(
        routes=[Route("/mcp", endpoint=_ok, methods=["GET", "POST"])],
        middleware=build_http_readiness_middleware("saudi-open-data-mcp")
        + build_http_auth_middleware(VALID_HTTP_AUTH_TOKEN),
    )


@pytest.mark.asyncio
async def test_readiness_path_is_served_without_bearer_auth() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.get(HTTP_READINESS_PATH)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "ready": True,
        "scope": "internal_runtime_readiness",
        "app_name": "saudi-open-data-mcp",
        "checks": {
            "process_running": True,
            "startup_validated": True,
            "runtime_storage_prepared": True,
            "app_wiring_completed": True,
        },
    }


@pytest.mark.asyncio
async def test_readiness_middleware_does_not_bypass_auth_for_mcp_path() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/mcp")

    assert response.status_code == 401
    assert response.json() == {"error": "missing bearer token"}


@pytest.mark.asyncio
async def test_readiness_path_supports_head_without_auth() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.head(HTTP_READINESS_PATH)

    assert response.status_code == 200
    assert response.text == ""


@pytest.mark.asyncio
async def test_non_get_readyz_request_does_not_bypass_auth() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.post(HTTP_READINESS_PATH)

    assert response.status_code == 401
    assert response.json() == {"error": "missing bearer token"}


def test_readiness_middleware_stack_is_explicit() -> None:
    middleware = build_http_readiness_middleware("saudi-open-data-mcp")

    assert isinstance(middleware, list)
    assert len(middleware) == 1
    assert middleware[0].cls is HTTPReadinessMiddleware
    assert middleware[0].kwargs["app_name"] == "saudi-open-data-mcp"
