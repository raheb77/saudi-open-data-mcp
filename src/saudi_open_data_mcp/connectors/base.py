"""Base connector contracts for approved official sources."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
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
    retry_backoff_seconds: float = Field(default=0.1, ge=0, le=1.0)

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

    def should_retry_http_status(self, status_code: int) -> bool:
        """Return whether an HTTP status is transient enough to retry."""

        return status_code in {408, 429} or 500 <= status_code <= 599

    def retry_backoff_seconds(self, retries_used: int) -> float:
        """Return the bounded delay applied before the next retry attempt."""

        if retries_used < 0:
            raise ValueError("retries_used must be greater than or equal to zero")
        return self.request_policy.retry_backoff_seconds

    async def sleep_before_retry(self, retries_used: int) -> None:
        """Sleep for the configured deterministic retry backoff."""

        delay_seconds = self.retry_backoff_seconds(retries_used)
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    def build_async_client(self) -> httpx.AsyncClient:
        """Build the default transient HTTP client for a single fetch call."""

        return httpx.AsyncClient()

    async def execute_get_with_retries(
        self,
        *,
        client: httpx.AsyncClient | None,
        url: str,
        dataset_id: str,
        source_label: str,
    ) -> httpx.Response:
        """Execute a GET request with per-call client reuse and bounded retries."""

        timeout = self.build_timeout()

        async def send_with(client_instance: httpx.AsyncClient) -> httpx.Response:
            return await client_instance.get(
                url,
                follow_redirects=True,
                timeout=timeout,
            )

        if client is not None:
            return await self.execute_request_with_retries(
                lambda: send_with(client),
                dataset_id=dataset_id,
                source_label=source_label,
            )

        async with self.build_async_client() as managed_client:
            return await self.execute_request_with_retries(
                lambda: send_with(managed_client),
                dataset_id=dataset_id,
                source_label=source_label,
            )

    async def execute_request_with_retries(
        self,
        send_request: Callable[[], Awaitable[httpx.Response]],
        *,
        dataset_id: str,
        source_label: str,
    ) -> httpx.Response:
        """Execute a connector request with bounded retries for transient failures."""

        retries_used = 0

        while True:
            try:
                response = await send_request()
                response.raise_for_status()
                return response
            except httpx.TimeoutException as exc:
                cause = exc
                error = SourceTimeoutError(
                    source_name=self.source_name,
                    dataset_id=dataset_id,
                    message=f"{source_label} source request timed out",
                )
            except httpx.HTTPStatusError as exc:
                cause = exc
                status_code = exc.response.status_code
                error = SourceUnavailableError(
                    source_name=self.source_name,
                    dataset_id=dataset_id,
                    message=f"{source_label} source returned HTTP {status_code}",
                )
                if not self.should_retry_http_status(status_code):
                    raise error from cause
            except httpx.RequestError as exc:
                cause = exc
                error = SourceUnavailableError(
                    source_name=self.source_name,
                    dataset_id=dataset_id,
                    message=f"{source_label} source request failed",
                )

            if not self.should_retry(error, retries_used):
                raise error from cause

            await self.sleep_before_retry(retries_used)
            retries_used += 1
