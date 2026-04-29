"""End-to-end HTTP/MCP integration coverage for the real run-http path."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import SecretStr
from starlette.testclient import TestClient

from saudi_open_data_mcp.config import RuntimeConfig, TransportConfig
from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.security.http_auth import build_http_auth_middleware
from saudi_open_data_mcp.security.http_readiness import (
    HTTP_READINESS_PATH,
    HTTP_STARTUP_PATH,
    build_http_readiness_middleware,
)
from saudi_open_data_mcp.server import (
    MCP_SERVER_DESCRIPTION,
    MCP_SERVER_NAME,
    _server_version,
    create_server,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore

HTTP_AUTH_TOKEN = "local-test-auth-token-000000000000"
MCP_PROTOCOL_VERSION = "2025-11-25"
EXCHANGE_RATES_DATASET_ID = "sama-exchange-rates-current"
EXCHANGE_RATES_SOURCE_LOCATOR = "/en-US/FinExc/Pages/Currency.aspx"
EXCHANGE_RATES_BUNDLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "sama"
    / "exchange_rates_current"
    / "exchange-rates-current-2026-04-12-bundle.json"
)


def _runtime_config(tmp_path: Path) -> RuntimeConfig:
    return RuntimeConfig(
        registry_path=tmp_path / "registry.sqlite",
        snapshot_dir=tmp_path / "snapshots",
        cache_dir=tmp_path / "cache",
        transport=TransportConfig(
            http_auth_token=SecretStr(HTTP_AUTH_TOKEN),
        ),
    )


def _run_http_app(config: RuntimeConfig):
    app = create_server(config)
    return app.http_app(
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


def _seed_exchange_rates_snapshot(snapshot_dir: Path) -> None:
    bundle = json.loads(EXCHANGE_RATES_BUNDLE_PATH.read_text(encoding="utf-8"))
    SnapshotStore(snapshot_dir).write_snapshot(
        RawPayload(
            source="sama",
            dataset_id=EXCHANGE_RATES_SOURCE_LOCATOR,
            content={
                "url": "https://www.sama.gov.sa/en-US/FinExc/Pages/Currency.aspx",
                "status_code": 200,
                "content_type": "application/json",
                "body": bundle,
            },
        )
    )


def _mcp_headers(
    *,
    session_id: str | None = None,
    bearer_token: str | None = HTTP_AUTH_TOKEN,
) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if bearer_token is not None:
        headers["Authorization"] = f"Bearer {bearer_token}"
    if session_id is not None:
        headers["mcp-session-id"] = session_id
        headers["mcp-protocol-version"] = MCP_PROTOCOL_VERSION
    return headers


def _initialize_request() -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": "init-1",
        "method": "initialize",
        "params": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": "integration-test-client",
                "version": "0.1.0",
            },
        },
    }


def test_run_http_path_supports_real_mcp_query_dataset_round_trip(
    tmp_path: Path,
) -> None:
    config = _runtime_config(tmp_path)
    _seed_exchange_rates_snapshot(config.snapshot_dir)
    http_app = _run_http_app(config)

    with TestClient(http_app) as client:
        initialize_response = client.post(
            "/mcp",
            headers=_mcp_headers(),
            json=_initialize_request(),
        )

        assert initialize_response.status_code == 200
        assert initialize_response.headers["content-type"].startswith(
            "application/json"
        )
        assert (
            initialize_response.json()["result"]["protocolVersion"]
            == MCP_PROTOCOL_VERSION
        )
        initialize_result = initialize_response.json()["result"]
        assert initialize_result["serverInfo"]["name"] == MCP_SERVER_NAME
        assert initialize_result["serverInfo"]["version"] == _server_version()
        assert initialize_result["instructions"] == MCP_SERVER_DESCRIPTION
        session_id = initialize_response.headers["mcp-session-id"]

        initialized_response = client.post(
            "/mcp",
            headers=_mcp_headers(session_id=session_id),
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
        )

        assert initialized_response.status_code == 202

        query_response = client.post(
            "/mcp",
            headers=_mcp_headers(session_id=session_id),
            json={
                "jsonrpc": "2.0",
                "id": "query-1",
                "method": "tools/call",
                "params": {
                    "name": "query_dataset",
                    "arguments": {
                        "dataset_id": EXCHANGE_RATES_DATASET_ID,
                        "filters": {"currency_code": "USD"},
                    },
                },
            },
        )

        assert query_response.status_code == 200
        assert query_response.headers["content-type"].startswith("application/json")

        query_payload = query_response.json()
        assert query_payload["jsonrpc"] == "2.0"
        assert query_payload["id"] == "query-1"
        assert query_payload["result"]["isError"] is False

        structured_content = query_payload["result"]["structuredContent"]
        assert structured_content["status"] == "success"
        assert structured_content["coverage_status"] == "queryable"
        assert structured_content["dataset_id"] == EXCHANGE_RATES_DATASET_ID
        assert structured_content["total_records_before_filter"] == 73
        assert len(structured_content["matched_records"]) == 1

        matched_record = structured_content["matched_records"][0]
        assert matched_record["dataset_id"] == EXCHANGE_RATES_DATASET_ID
        assert matched_record["source"] == "sama"
        assert matched_record["fields"]["as_of_date"] == "2026-04-12"
        assert matched_record["fields"]["currency_code"] == "USD"
        assert matched_record["fields"]["closing_rate_sar"] == 3.75

        assert json.loads(query_payload["result"]["content"][0]["text"]) == structured_content


def test_run_http_path_rejects_missing_bearer_token_on_mcp_endpoint(
    tmp_path: Path,
) -> None:
    config = _runtime_config(tmp_path)
    http_app = _run_http_app(config)

    with TestClient(http_app) as client:
        response = client.post(
            "/mcp",
            headers=_mcp_headers(bearer_token=None),
            json=_initialize_request(),
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"error": "missing bearer token"}


def test_run_http_path_rejects_invalid_bearer_token_on_mcp_endpoint(
    tmp_path: Path,
) -> None:
    config = _runtime_config(tmp_path)
    http_app = _run_http_app(config)

    with TestClient(http_app) as client:
        response = client.post(
            "/mcp",
            headers=_mcp_headers(bearer_token="wrong-token"),
            json=_initialize_request(),
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"error": "invalid bearer token"}


def test_startup_probe_bypasses_auth_on_real_run_http_middleware_stack(
    tmp_path: Path,
) -> None:
    config = _runtime_config(tmp_path)
    http_app = _run_http_app(config)

    with TestClient(http_app) as client:
        response = client.get(HTTP_STARTUP_PATH)

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["ready"] is True
    assert response.json()["canonical_path"] == HTTP_STARTUP_PATH
    assert response.json()["deprecated_alias"] is False


def test_readyz_alias_bypasses_auth_on_real_run_http_middleware_stack(
    tmp_path: Path,
) -> None:
    config = _runtime_config(tmp_path)
    http_app = _run_http_app(config)

    with TestClient(http_app) as client:
        response = client.get(HTTP_READINESS_PATH)

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["ready"] is True
    assert response.json()["canonical_path"] == HTTP_STARTUP_PATH
    assert response.json()["deprecated_alias"] is True
