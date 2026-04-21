"""Unit tests for minimal HTTP bearer auth."""

from __future__ import annotations

import json
import logging

import httpx
import pytest
from pydantic import SecretStr
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from saudi_open_data_mcp.observability import build_token_fingerprint, get_metrics
from saudi_open_data_mcp.security.http_auth import (
    MAX_HTTP_AUTH_REQUEST_BODY_BYTES,
    HTTPAuthCapability,
    HTTPAuthRole,
    HTTPBearerAuthMiddleware,
    build_http_auth_middleware,
    capabilities_for_http_auth_role,
)


async def _ok(_) -> JSONResponse:
    return JSONResponse({"ok": True})


def _app(
    capabilities: frozenset[HTTPAuthCapability] | None = None,
    role: HTTPAuthRole = HTTPAuthRole.OPERATOR,
) -> Starlette:
    return Starlette(
        routes=[Route("/mcp", endpoint=_ok, methods=["GET", "POST"])],
        middleware=build_http_auth_middleware(
            "internal-test-token",
            capabilities
            if capabilities is not None
            else frozenset(HTTPAuthCapability),
            role,
        ),
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


@pytest.mark.asyncio
async def test_bearer_token_whitespace_is_normalized() -> None:
    app = Starlette(
        routes=[Route("/mcp", endpoint=_ok, methods=["GET", "POST"])],
        middleware=build_http_auth_middleware(
            SecretStr("  internal-test-token  "),
            frozenset(HTTPAuthCapability),
            HTTPAuthRole.OPERATOR,
        ),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/mcp",
            headers={"Authorization": "Bearer   internal-test-token   "},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_oversized_request_body_with_content_length_is_rejected() -> None:
    oversized_body = b"x" * (MAX_HTTP_AUTH_REQUEST_BODY_BYTES + 1)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
            content=oversized_body,
        )

    assert response.status_code == 413
    assert response.json() == {"error": "request body exceeds the maximum allowed size"}
    assert get_metrics().get("http.auth.requests") == 1
    assert get_metrics().get("http.auth.accepted") == 0
    assert get_metrics().get("http.auth.rejected") == 1


@pytest.mark.asyncio
async def test_oversized_streamed_request_body_is_rejected_without_content_length() -> None:
    async def oversized_stream():
        yield b"x" * MAX_HTTP_AUTH_REQUEST_BODY_BYTES
        yield b"x"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
            content=oversized_stream(),
        )

    assert response.status_code == 413
    assert response.json() == {"error": "request body exceeds the maximum allowed size"}
    assert get_metrics().get("http.auth.requests") == 1
    assert get_metrics().get("http.auth.accepted") == 0
    assert get_metrics().get("http.auth.rejected") == 1


def test_role_bundles_are_explicit() -> None:
    assert capabilities_for_http_auth_role(HTTPAuthRole.VIEWER) == frozenset(
        {HTTPAuthCapability.READ}
    )
    assert capabilities_for_http_auth_role(HTTPAuthRole.OPERATOR) == frozenset(
        HTTPAuthCapability
    )
    assert capabilities_for_http_auth_role(HTTPAuthRole.ADMIN) == frozenset(
        HTTPAuthCapability
    )


@pytest.mark.asyncio
async def test_read_capability_allows_local_query_tool_call() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=_app(frozenset({HTTPAuthCapability.READ}))
        ),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer internal-test-token",
                "X-Request-ID": "req-authz-1",
            },
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {"name": "query_dataset", "arguments": {"dataset_id": "x"}},
            },
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_initialize_method_is_explicitly_allowed_without_read_capability() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=_app(frozenset({HTTPAuthCapability.MATERIALIZE}))
        ),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
            json={
                "jsonrpc": "2.0",
                "id": "init-1",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "unit-test-client", "version": "0.1.0"},
                },
            },
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_refresh_capability_is_required_for_preview_tool_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=_app(frozenset({HTTPAuthCapability.READ}))
        ),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer internal-test-token",
                "X-Request-ID": "req-authz-1",
            },
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {"name": "preview_dataset", "arguments": {"dataset_id": "x"}},
            },
        )

    assert response.status_code == 403
    assert response.json() == {"error": "insufficient capability: refresh"}
    assert get_metrics().get("http.auth.requests") == 1
    assert get_metrics().get("http.auth.accepted") == 1
    assert get_metrics().get("http.authz.rejected") == 1
    assert get_metrics().get("http.authz.rejected.insufficient_capability") == 1
    assert any(
        json.loads(record.getMessage())["required_capability"] == "refresh"
        and json.loads(record.getMessage())["target"] == "preview_dataset"
        for record in caplog.records
    )
    assert any(
        json.loads(record.getMessage())["event"] == "audit.authorization_denied"
        and json.loads(record.getMessage())["required_capability"] == "refresh"
        and json.loads(record.getMessage())["actor_role"] == "operator"
        and json.loads(record.getMessage())["request_id"] == "req-authz-1"
        and json.loads(record.getMessage())["actor_token_fingerprint"]
        == build_token_fingerprint("internal-test-token")
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_viewer_role_rejects_preview_tool_call() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=_app(
                capabilities=capabilities_for_http_auth_role(HTTPAuthRole.VIEWER),
                role=HTTPAuthRole.VIEWER,
            )
        ),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {"name": "preview_dataset", "arguments": {"dataset_id": "x"}},
            },
        )

    assert response.status_code == 403
    assert response.json() == {"error": "insufficient capability: refresh"}


@pytest.mark.asyncio
async def test_materialize_capability_is_required_for_materialize_tool_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=_app(frozenset({HTTPAuthCapability.READ}))
        ),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {"name": "materialize_hot_set", "arguments": {}},
            },
        )

    assert response.status_code == 403
    assert response.json() == {"error": "insufficient capability: materialize"}
    assert any(
        json.loads(record.getMessage())["required_capability"] == "materialize"
        and json.loads(record.getMessage())["target"] == "materialize_hot_set"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_operator_role_allows_materialize_tool_call() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=_app(
                capabilities=capabilities_for_http_auth_role(HTTPAuthRole.OPERATOR),
                role=HTTPAuthRole.OPERATOR,
            )
        ),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {"name": "materialize_hot_set", "arguments": {}},
            },
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_role_is_recorded_on_authorization_denial(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=_app(
                capabilities=frozenset({HTTPAuthCapability.READ}),
                role=HTTPAuthRole.ADMIN,
            )
        ),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {"name": "preview_dataset", "arguments": {"dataset_id": "x"}},
            },
        )

    assert response.status_code == 403
    assert any(
        json.loads(record.getMessage())["event"] == "audit.authorization_denied"
        and json.loads(record.getMessage())["actor_role"] == "admin"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_read_capability_is_required_for_resource_reads() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=_app(frozenset({HTTPAuthCapability.MATERIALIZE}))
        ),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "resources/read",
                "params": {"uri": "resource://catalog"},
            },
        )

    assert response.status_code == 403
    assert response.json() == {"error": "insufficient capability: read"}


@pytest.mark.asyncio
async def test_read_capability_is_required_for_tools_list_method() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=_app(frozenset({HTTPAuthCapability.REFRESH}))
        ),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/list",
                "params": {},
            },
        )

    assert response.status_code == 403
    assert response.json() == {"error": "insufficient capability: read"}
    assert get_metrics().get("http.authz.rejected") == 1
    assert get_metrics().get("http.authz.rejected.insufficient_capability") == 1


@pytest.mark.asyncio
async def test_unmapped_tool_calls_fail_closed_with_internal_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {"name": "future_tool", "arguments": {}},
            },
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": "authorization coverage missing for tool: future_tool"
    }
    assert get_metrics().get("http.authz.coverage_missing") == 1
    assert any(
        json.loads(record.getMessage())["event"] == "audit.authorization_coverage_missing"
        and json.loads(record.getMessage())["target"] == "future_tool"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_unmapped_resource_reads_fail_closed_with_internal_error() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "resources/read",
                "params": {"uri": "resource://future"},
            },
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": "authorization coverage missing for resource: resource://future"
    }
    assert get_metrics().get("http.authz.coverage_missing") == 1


@pytest.mark.asyncio
async def test_unclassified_mcp_methods_are_denied_by_default(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer internal-test-token"},
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "future/method",
                "params": {},
            },
        )

    assert response.status_code == 403
    assert response.json() == {
        "error": "unclassified MCP method denied by default: future/method"
    }
    assert get_metrics().get("http.authz.rejected") == 1
    assert get_metrics().get("http.authz.rejected.unclassified_method") == 1
    assert any(
        json.loads(record.getMessage())["event"] == "audit.authorization_denied"
        and json.loads(record.getMessage())["denial_reason"] == "unclassified_mcp_method"
        and json.loads(record.getMessage())["mcp_method"] == "future/method"
        for record in caplog.records
    )


def test_middleware_builder_keeps_token_masked_in_repr() -> None:
    middleware = build_http_auth_middleware(
        SecretStr("internal-test-token"),
        frozenset({HTTPAuthCapability.READ}),
        HTTPAuthRole.VIEWER,
    )

    assert len(middleware) == 1
    assert "internal-test-token" not in repr(middleware[0])
    assert "**********" in repr(middleware[0])
    assert "viewer" in repr(middleware[0])
    assert "read" in repr(middleware[0])


@pytest.mark.asyncio
async def test_non_http_scope_passes_through_without_auth_enforcement() -> None:
    calls: list[str] = []

    async def downstream_app(scope, receive, send) -> None:
        calls.append(scope["type"])

    middleware = HTTPBearerAuthMiddleware(
        downstream_app,
        bearer_token=SecretStr("internal-test-token"),
        capabilities=frozenset({HTTPAuthCapability.READ}),
        role=HTTPAuthRole.VIEWER,
    )

    async def receive():
        return {"type": "websocket.connect"}

    async def send(_message) -> None:
        return None

    await middleware(
        {"type": "websocket", "path": "/mcp", "headers": []},
        receive,
        send,
    )

    assert calls == ["websocket"]
    assert get_metrics().snapshot() == {}
