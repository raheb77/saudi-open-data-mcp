"""Unit tests for the SAMA connector."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from saudi_open_data_mcp.connectors.base import RawPayload, RequestPolicy
from saudi_open_data_mcp.connectors.errors import (
    InvalidSourceResponseError,
    SourceAccessPolicyViolationError,
    SourceTimeoutError,
    SourceUnavailableError,
)
from saudi_open_data_mcp.connectors.sama import SAMAConnector
from saudi_open_data_mcp.storage.snapshots import SnapshotStore

REPORT_LOCATOR = "report.aspx?cid=55"


def _report_url() -> str:
    return f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{REPORT_LOCATOR}"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_dataset_payload_returns_raw_payload() -> None:
    route = respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official sama payload</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    connector = SAMAConnector()

    payload = await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert route.called
    assert isinstance(payload, RawPayload)
    assert payload.source == "sama"
    assert payload.dataset_id == REPORT_LOCATOR
    assert payload.content["content_type"] == "text/html"
    assert "official sama payload" in payload.content["body"]


@pytest.mark.asyncio
async def test_approved_url_enforcement_rejects_unapproved_hosts() -> None:
    connector = SAMAConnector()

    with pytest.raises(SourceAccessPolicyViolationError):
        await connector.fetch_dataset_payload("https://example.com/report.aspx?cid=55")


@pytest.mark.asyncio
@respx.mock
async def test_timeout_maps_to_source_timeout_error() -> None:
    respx.get(_report_url()).mock(side_effect=httpx.ReadTimeout("timed out"))
    connector = SAMAConnector(request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=0))

    with pytest.raises(SourceTimeoutError) as exc_info:
        await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert exc_info.value.dataset_id == REPORT_LOCATOR
    assert exc_info.value.message == "SAMA source request timed out"
    assert REPORT_LOCATOR not in exc_info.value.message


@pytest.mark.asyncio
@respx.mock
async def test_transient_unavailable_failure_retries_then_succeeds() -> None:
    route = respx.get(_report_url()).mock(
        side_effect=[
            httpx.Response(503, text="service unavailable"),
            httpx.Response(
                200,
                json={"rows": [{"period": "2026-01", "value": 1}]},
                headers={"content-type": "application/json"},
            ),
        ]
    )
    connector = SAMAConnector(request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=1))

    payload = await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert payload.content["body"] == {"rows": [{"period": "2026-01", "value": 1}]}
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_retry_budget_exhaustion_preserves_source_unavailable_error() -> None:
    route = respx.get(_report_url()).mock(
        side_effect=[
            httpx.Response(503, text="service unavailable"),
            httpx.Response(503, text="service unavailable"),
        ]
    )
    connector = SAMAConnector(request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=1))

    with pytest.raises(SourceUnavailableError) as exc_info:
        await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert exc_info.value.dataset_id == REPORT_LOCATOR
    assert exc_info.value.message == "SAMA source returned HTTP 503"
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_non_retryable_http_status_is_not_retried() -> None:
    route = respx.get(_report_url()).mock(
        side_effect=[
            httpx.Response(404, text="not found"),
            httpx.Response(
                200,
                json={"rows": [{"period": "2026-01", "value": 1}]},
                headers={"content-type": "application/json"},
            ),
        ]
    )
    connector = SAMAConnector(request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=1))

    with pytest.raises(SourceUnavailableError) as exc_info:
        await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert exc_info.value.message == "SAMA source returned HTTP 404"
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_invalid_source_response_is_not_retried() -> None:
    route = respx.get(_report_url()).mock(
        side_effect=[
            httpx.Response(
                200,
                text="not valid json",
                headers={"content-type": "application/json"},
            ),
            httpx.Response(
                200,
                json={"rows": [{"period": "2026-01", "value": 1}]},
                headers={"content-type": "application/json"},
            ),
        ]
    )
    connector = SAMAConnector(request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=1))

    with pytest.raises(InvalidSourceResponseError):
        await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_unavailable_source_maps_to_source_unavailable_error() -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(503, text="service unavailable")
    )
    connector = SAMAConnector()

    with pytest.raises(SourceUnavailableError) as exc_info:
        await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert exc_info.value.dataset_id == REPORT_LOCATOR
    assert exc_info.value.message == "SAMA source returned HTTP 503"
    assert REPORT_LOCATOR not in exc_info.value.message


@pytest.mark.asyncio
@respx.mock
async def test_invalid_source_response_shape_maps_to_invalid_source_response_error() -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            text="not valid json",
            headers={"content-type": "application/json"},
        )
    )
    connector = SAMAConnector()

    with pytest.raises(InvalidSourceResponseError):
        await connector.fetch_dataset_payload(REPORT_LOCATOR)


@pytest.mark.asyncio
@respx.mock
async def test_snapshot_store_is_used_when_provided(tmp_path: Path) -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"period": "2026-01", "value": 1}]},
            headers={"content-type": "application/json"},
        )
    )
    store = SnapshotStore(tmp_path)
    connector = SAMAConnector(snapshot_store=store)

    payload = await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert store.snapshot_exists("sama", REPORT_LOCATOR)
    assert store.read_snapshot("sama", REPORT_LOCATOR) == payload
