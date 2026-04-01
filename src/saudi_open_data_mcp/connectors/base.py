"""Base connector contracts for approved official sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field

from .errors import (
    ConnectorConfigurationError,
    ConnectorNotImplementedError,
    SourceAccessPolicyViolationError,
    SourceTimeoutError,
    SourceUnavailableError,
)


class RequestPolicy(BaseModel):
    """Timeout and retry policy helper for connector source access."""

    timeout_seconds: float = Field(default=10.0, gt=0)
    max_retries: int = Field(default=2, ge=0)

    def to_httpx_timeout(self) -> httpx.Timeout:
        """Convert policy settings into an `httpx` timeout object."""

        return httpx.Timeout(self.timeout_seconds)


class ConnectorIdentity(BaseModel):
    """Required connector identity for approved official source access."""

    source_name: str = Field(min_length=1)
    approved_base_url: str = Field(min_length=1)


class DatasetCatalogEntry(BaseModel):
    """Minimal catalog metadata returned by a connector."""

    dataset_id: str
    source: str
    title: str
    description: str | None = None


class DatasetCatalog(BaseModel):
    """Typed dataset catalog metadata."""

    source: str
    entries: tuple[DatasetCatalogEntry, ...] = ()


class RawPayload(BaseModel):
    """Typed raw connector output."""

    source: str
    dataset_id: str
    content: dict[str, Any] = Field(default_factory=dict)


class RawPayloadSnapshotWriter(Protocol):
    """Minimal protocol for optional raw payload snapshot persistence."""

    def write_snapshot(self, payload: RawPayload) -> object:
        """Persist a raw payload snapshot."""


class Connector(ABC):
    """Base connector abstraction for approved official sources."""

    source_name: str = ""
    approved_base_url: str = ""
    request_policy: RequestPolicy = RequestPolicy()

    @property
    def connector_identity(self) -> ConnectorIdentity:
        """Return the required connector identity with clear configuration errors."""

        source_name = self.source_name.strip()
        if not source_name:
            raise ConnectorConfigurationError(
                source_name="<unconfigured>",
                message="source_name must be configured for connector identity",
            )

        approved_base_url = self.approved_base_url.rstrip("/")
        if not approved_base_url:
            raise ConnectorConfigurationError(
                source_name=source_name,
                message="approved_base_url must be configured for connector identity",
            )

        return ConnectorIdentity(
            source_name=source_name,
            approved_base_url=approved_base_url,
        )

    async def fetch_dataset_catalog_metadata(self) -> DatasetCatalog:
        """Fetch dataset catalog metadata when a source exposes it."""

        raise ConnectorNotImplementedError(
            source_name=self.connector_identity.source_name,
            message="catalog metadata fetching is not implemented for this connector scaffold",
        )

    @abstractmethod
    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        """Fetch a raw dataset payload for a specific dataset identifier."""

    def build_timeout(self) -> httpx.Timeout:
        """Build the `httpx` timeout configuration for this connector."""

        return self.request_policy.to_httpx_timeout()

    def ensure_approved_url(self, url: str) -> str:
        """Ensure that connector access stays within the approved official source."""

        approved_base_url = self.connector_identity.approved_base_url
        if not url.startswith(approved_base_url):
            raise SourceAccessPolicyViolationError(
                source_name=self.connector_identity.source_name,
                message=f"URL '{url}' is outside the approved source boundary",
            )
        return url

    def should_retry(self, error: Exception, retries_used: int) -> bool:
        """Return whether a connector should retry after a source failure.

        This helper exposes timeout and retry policy decisions only. It does not
        perform retry loops or backoff execution.
        """

        if retries_used < 0:
            raise ValueError("retries_used must be greater than or equal to zero")
        retryable = (SourceUnavailableError, SourceTimeoutError)
        return retries_used < self.request_policy.max_retries and isinstance(error, retryable)
