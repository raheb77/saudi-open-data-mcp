"""Targeted tests for the current HTTP MCP serving path."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from starlette.testclient import TestClient

from saudi_open_data_mcp.config import RuntimeConfig, TransportConfig
from saudi_open_data_mcp.security.http_auth import build_http_auth_middleware
from saudi_open_data_mcp.security.http_readiness import build_http_readiness_middleware
from saudi_open_data_mcp.server import create_server

VALID_HTTP_AUTH_TOKEN = "0123456789abcdef0123456789abcdef"


def _runtime_config(tmp_path: Path) -> RuntimeConfig:
    return RuntimeConfig(
        registry_path=tmp_path / "registry.sqlite",
        snapshot_dir=tmp_path / "snapshots",
        cache_dir=tmp_path / "cache",
        transport=TransportConfig(
            http_auth_token=SecretStr(VALID_HTTP_AUTH_TOKEN),
        ),
    )


def test_streamable_http_initialize_and_resource_read_return_json_for_dashboard_flow(
    tmp_path: Path,
) -> None:
    config = _runtime_config(tmp_path)
    app = create_server(config)
    http_app = app.http_app(
        transport="streamable-http",
        json_response=True,
        stateless_http=False,
        middleware=build_http_readiness_middleware(config.app_name)
        + build_http_auth_middleware(
            config.transport.http_auth_token,
            config.transport.http_auth_capabilities,
            config.transport.http_auth_role,
        ),
    )

    initialize_request = {
        "jsonrpc": "2.0",
        "id": "init-1",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {
                "name": "dashboard-test-client",
                "version": "0.1.0",
            },
        },
    }

    with TestClient(http_app) as client:
        initialize_response = client.post(
            "/mcp",
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {VALID_HTTP_AUTH_TOKEN}",
            },
            json=initialize_request,
        )

        assert initialize_response.status_code == 200
        assert initialize_response.headers["content-type"].startswith(
            "application/json"
        )
        session_id = initialize_response.headers.get("mcp-session-id")
        assert session_id
        initialize_payload = initialize_response.json()
        assert initialize_payload["result"]["protocolVersion"] == "2025-11-25"

        initialized_response = client.post(
            "/mcp",
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {VALID_HTTP_AUTH_TOKEN}",
                "mcp-session-id": session_id,
                "mcp-protocol-version": "2025-11-25",
            },
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
        )

        assert initialized_response.status_code == 202

        resource_response = client.post(
            "/mcp",
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {VALID_HTTP_AUTH_TOKEN}",
                "mcp-session-id": session_id,
                "mcp-protocol-version": "2025-11-25",
            },
            json={
                "jsonrpc": "2.0",
                "id": "resource-1",
                "method": "resources/read",
                "params": {"uri": "resource://catalog"},
            },
        )

        assert resource_response.status_code == 200
        assert resource_response.headers["content-type"].startswith(
            "application/json"
        )
        resource_payload = resource_response.json()
        assert resource_payload["result"]["contents"][0]["uri"] == "resource://catalog"
