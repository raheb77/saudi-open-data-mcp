"""Unit tests for connector contracts."""

from __future__ import annotations

import pytest

from saudi_open_data_mcp.connectors.base import (
    Connector,
    ConnectorIdentity,
    DatasetCatalog,
    RawPayload,
    RequestPolicy,
)
from saudi_open_data_mcp.connectors.errors import (
    ConnectorConfigurationError,
    ConnectorNotImplementedError,
    InvalidSourceResponseError,
    SourceAccessPolicyViolationError,
    SourceTimeoutError,
    SourceUnavailableError,
)


class DummyConnector(Connector):
    """Test connector that exercises the shared contract."""

    source_name = "dummy"
    approved_base_url = "https://data.example.gov.sa"
    request_policy = RequestPolicy(timeout_seconds=7.5, max_retries=2)

    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        return RawPayload(source=self.source_name, dataset_id=dataset_id, content={})


@pytest.mark.asyncio
async def test_fetch_dataset_payload_returns_typed_raw_payload() -> None:
    connector = DummyConnector()

    payload = await connector.fetch_dataset_payload("catalog-1")

    assert payload.source == "dummy"
    assert payload.dataset_id == "catalog-1"


def test_connector_identity_is_explicit() -> None:
    connector = DummyConnector()

    identity = connector.connector_identity

    assert identity == ConnectorIdentity(
        source_name="dummy",
        approved_base_url="https://data.example.gov.sa",
    )


@pytest.mark.asyncio
async def test_catalog_metadata_defaults_to_not_implemented() -> None:
    connector = DummyConnector()

    with pytest.raises(ConnectorNotImplementedError) as exc_info:
        await connector.fetch_dataset_catalog_metadata()

    assert exc_info.value.source_name == "dummy"
    assert "catalog metadata fetching" in str(exc_info.value)


def test_build_timeout_uses_request_policy() -> None:
    connector = DummyConnector()

    timeout = connector.build_timeout()

    assert timeout.connect == pytest.approx(7.5)
    assert timeout.read == pytest.approx(7.5)
    assert timeout.write == pytest.approx(7.5)
    assert timeout.pool == pytest.approx(7.5)


def test_ensure_approved_url_accepts_official_source() -> None:
    connector = DummyConnector()

    approved = connector.ensure_approved_url("https://data.example.gov.sa/catalog")

    assert approved == "https://data.example.gov.sa/catalog"


def test_ensure_approved_url_rejects_unapproved_source() -> None:
    connector = DummyConnector()

    with pytest.raises(SourceAccessPolicyViolationError) as exc_info:
        connector.ensure_approved_url("https://unapproved.example.org/catalog")

    assert exc_info.value.source_name == "dummy"
    assert exc_info.value.dataset_id is None


def test_ensure_approved_url_requires_base_url_configuration() -> None:
    class MisconfiguredConnector(DummyConnector):
        approved_base_url = ""

    connector = MisconfiguredConnector()

    with pytest.raises(ConnectorConfigurationError):
        connector.ensure_approved_url("https://data.example.gov.sa/catalog")


def test_connector_identity_requires_source_name() -> None:
    class MisconfiguredConnector(DummyConnector):
        source_name = ""

    connector = MisconfiguredConnector()

    with pytest.raises(ConnectorConfigurationError) as exc_info:
        _ = connector.connector_identity

    assert "<unconfigured>" in str(exc_info.value)


def test_retry_policy_only_retries_expected_connector_failures() -> None:
    connector = DummyConnector()

    assert connector.should_retry(SourceUnavailableError(source_name="dummy", message="down"), 0)
    assert connector.should_retry(SourceTimeoutError(source_name="dummy", message="slow"), 1)
    assert not connector.should_retry(
        InvalidSourceResponseError(source_name="dummy", message="shape mismatch"),
        0,
    )
    assert not connector.should_retry(
        SourceUnavailableError(source_name="dummy", message="down"),
        2,
    )


def test_retry_policy_rejects_negative_retry_count() -> None:
    connector = DummyConnector()

    with pytest.raises(ValueError):
        connector.should_retry(SourceTimeoutError(source_name="dummy", message="slow"), -1)


def test_catalog_model_defaults_are_typed() -> None:
    catalog = DatasetCatalog(source="dummy")

    assert catalog.entries == ()


def test_connector_error_string_includes_context() -> None:
    error = SourceTimeoutError(
        source_name="dummy",
        dataset_id="dataset-1",
        message="request timed out",
    )

    assert "request timed out" in str(error)
    assert "source=dummy" in str(error)
    assert "dataset_id=dataset-1" in str(error)
