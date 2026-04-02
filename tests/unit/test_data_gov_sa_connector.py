"""Unit tests for the data.gov.sa connector."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from saudi_open_data_mcp.connectors.base import RawPayload, RequestPolicy
from saudi_open_data_mcp.connectors.data_gov_sa import DataGovSaConnector
from saudi_open_data_mcp.connectors.errors import (
    InvalidSourceResponseError,
    SourceAccessPolicyViolationError,
    SourceTimeoutError,
    SourceUnavailableError,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore

SOURCE_LOCATOR = (
    "/ar/datasets/view/104380ce-60b6-46bc-ba0a-6d5e10ac46cb/"
    "preview/parsed/Census%20Marital%20Status%20CSV.json"
)


def _dataset_url() -> str:
    return f"https://open.data.gov.sa{SOURCE_LOCATOR}"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_dataset_payload_returns_raw_payload() -> None:
    route = respx.get(_dataset_url()).mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"status": "single", "count": 10}]},
            headers={"content-type": "application/json"},
        )
    )
    connector = DataGovSaConnector()

    payload = await connector.fetch_dataset_payload(SOURCE_LOCATOR)

    assert route.called
    assert isinstance(payload, RawPayload)
    assert payload.source == "data-gov-sa"
    assert payload.dataset_id == SOURCE_LOCATOR
    assert payload.content["content_type"] == "application/json"
    assert payload.content["body"] == {"rows": [{"status": "single", "count": 10}]}


@pytest.mark.asyncio
async def test_approved_url_enforcement_rejects_unapproved_hosts() -> None:
    connector = DataGovSaConnector()

    with pytest.raises(SourceAccessPolicyViolationError):
        await connector.fetch_dataset_payload(
            "https://example.com/ar/datasets/view/id/preview/parsed/dataset.json"
        )


@pytest.mark.asyncio
@respx.mock
async def test_timeout_maps_to_source_timeout_error() -> None:
    respx.get(_dataset_url()).mock(side_effect=httpx.ReadTimeout("timed out"))
    connector = DataGovSaConnector(
        request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=0)
    )

    with pytest.raises(SourceTimeoutError) as exc_info:
        await connector.fetch_dataset_payload(SOURCE_LOCATOR)

    assert exc_info.value.dataset_id == SOURCE_LOCATOR
    assert exc_info.value.message == "data.gov.sa source request timed out"
    assert SOURCE_LOCATOR not in exc_info.value.message


@pytest.mark.asyncio
@respx.mock
async def test_transient_unavailable_failure_retries_then_succeeds() -> None:
    route = respx.get(_dataset_url()).mock(
        side_effect=[
            httpx.Response(503, text="service unavailable"),
            httpx.Response(
                200,
                json={"rows": [{"status": "single", "count": 10}]},
                headers={"content-type": "application/json"},
            ),
        ]
    )
    connector = DataGovSaConnector(
        request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=1)
    )

    payload = await connector.fetch_dataset_payload(SOURCE_LOCATOR)

    assert payload.content["body"] == {"rows": [{"status": "single", "count": 10}]}
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_retry_budget_exhaustion_preserves_source_unavailable_error() -> None:
    route = respx.get(_dataset_url()).mock(
        side_effect=[
            httpx.Response(503, text="service unavailable"),
            httpx.Response(503, text="service unavailable"),
        ]
    )
    connector = DataGovSaConnector(
        request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=1)
    )

    with pytest.raises(SourceUnavailableError) as exc_info:
        await connector.fetch_dataset_payload(SOURCE_LOCATOR)

    assert exc_info.value.dataset_id == SOURCE_LOCATOR
    assert exc_info.value.message == "data.gov.sa source returned HTTP 503"
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_invalid_source_response_is_not_retried() -> None:
    route = respx.get(_dataset_url()).mock(
        side_effect=[
            httpx.Response(
                200,
                text="not valid json",
                headers={"content-type": "application/json"},
            ),
            httpx.Response(
                200,
                json={"rows": [{"status": "single", "count": 10}]},
                headers={"content-type": "application/json"},
            ),
        ]
    )
    connector = DataGovSaConnector(
        request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=1)
    )

    with pytest.raises(InvalidSourceResponseError):
        await connector.fetch_dataset_payload(SOURCE_LOCATOR)

    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_unavailable_source_maps_to_source_unavailable_error() -> None:
    respx.get(_dataset_url()).mock(return_value=httpx.Response(503, text="service unavailable"))
    connector = DataGovSaConnector()

    with pytest.raises(SourceUnavailableError) as exc_info:
        await connector.fetch_dataset_payload(SOURCE_LOCATOR)

    assert exc_info.value.dataset_id == SOURCE_LOCATOR
    assert exc_info.value.message == "data.gov.sa source returned HTTP 503"
    assert SOURCE_LOCATOR not in exc_info.value.message


@pytest.mark.asyncio
@respx.mock
async def test_invalid_source_response_shape_maps_to_invalid_source_response_error() -> None:
    respx.get(_dataset_url()).mock(
        return_value=httpx.Response(
            200,
            text="not valid json",
            headers={"content-type": "application/json"},
        )
    )
    connector = DataGovSaConnector()

    with pytest.raises(InvalidSourceResponseError):
        await connector.fetch_dataset_payload(SOURCE_LOCATOR)


@pytest.mark.asyncio
@respx.mock
async def test_snapshot_store_is_used_when_provided(tmp_path: Path) -> None:
    respx.get(_dataset_url()).mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"status": "single", "count": 10}]},
            headers={"content-type": "application/json"},
        )
    )
    store = SnapshotStore(tmp_path)
    connector = DataGovSaConnector(snapshot_store=store)

    payload = await connector.fetch_dataset_payload(SOURCE_LOCATOR)

    assert store.snapshot_exists("data-gov-sa", SOURCE_LOCATOR)
    assert store.read_snapshot("data-gov-sa", SOURCE_LOCATOR) == payload
