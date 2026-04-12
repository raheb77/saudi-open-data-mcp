"""Unit tests for the data.gov.sa connector."""

from __future__ import annotations

from pathlib import Path
from typing import cast

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
    class RecordingConnector(DataGovSaConnector):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.backoff_delays: list[float] = []

        async def sleep_before_retry(self, retries_used: int) -> None:
            self.backoff_delays.append(self.retry_backoff_seconds(retries_used))

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
    connector = RecordingConnector(
        request_policy=RequestPolicy(
            timeout_seconds=0.1,
            max_retries=1,
            retry_backoff_seconds=0.2,
        )
    )

    payload = await connector.fetch_dataset_payload(SOURCE_LOCATOR)

    assert payload.content["body"] == {"rows": [{"status": "single", "count": 10}]}
    assert route.call_count == 2
    assert connector.backoff_delays == [0.2]


@pytest.mark.asyncio
async def test_retries_reuse_one_transient_client_per_fetch_call() -> None:
    class FakeAsyncClient:
        def __init__(self, responses: list[httpx.Response]) -> None:
            self._responses = iter(responses)
            self.get_call_count = 0
            self.closed = False

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            self.closed = True

        async def get(
            self,
            url: str,
            *,
            follow_redirects: bool,
            timeout: httpx.Timeout,
        ) -> httpx.Response:
            self.get_call_count += 1
            return next(self._responses)

    class RecordingConnector(DataGovSaConnector):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.backoff_delays: list[float] = []
            self.created_clients: list[FakeAsyncClient] = []

        def build_async_client(self) -> httpx.AsyncClient:
            client = FakeAsyncClient(
                [
                    httpx.Response(
                        503,
                        request=httpx.Request("GET", _dataset_url()),
                        text="service unavailable",
                    ),
                    httpx.Response(
                        200,
                        request=httpx.Request("GET", _dataset_url()),
                        json={"rows": [{"status": "single", "count": 10}]},
                        headers={"content-type": "application/json"},
                    ),
                ]
            )
            self.created_clients.append(client)
            return cast(httpx.AsyncClient, client)

        async def sleep_before_retry(self, retries_used: int) -> None:
            self.backoff_delays.append(self.retry_backoff_seconds(retries_used))

    connector = RecordingConnector(
        request_policy=RequestPolicy(
            timeout_seconds=0.1,
            max_retries=1,
            retry_backoff_seconds=0.2,
        )
    )

    payload = await connector.fetch_dataset_payload(SOURCE_LOCATOR)

    assert payload.content["body"] == {"rows": [{"status": "single", "count": 10}]}
    assert connector.backoff_delays == [0.2]
    assert len(connector.created_clients) == 1
    assert connector.created_clients[0].get_call_count == 2
    assert connector.created_clients[0].closed is True


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
async def test_non_retryable_http_status_is_not_retried() -> None:
    route = respx.get(_dataset_url()).mock(
        side_effect=[
            httpx.Response(404, text="not found"),
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

    with pytest.raises(SourceUnavailableError) as exc_info:
        await connector.fetch_dataset_payload(SOURCE_LOCATOR)

    assert exc_info.value.message == "data.gov.sa source returned HTTP 404"
    assert route.call_count == 1


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
    loaded = store.read_snapshot("data-gov-sa", SOURCE_LOCATOR)
    assert loaded.model_dump(mode="json", exclude={"snapshot_metadata"}) == payload.model_dump(
        mode="json",
        exclude={"snapshot_metadata"},
    )
    assert loaded.snapshot_metadata is not None
