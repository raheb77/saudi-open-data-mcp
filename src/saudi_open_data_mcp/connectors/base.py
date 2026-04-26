"""Base connector contracts for approved official sources."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from urllib.parse import urljoin, urlsplit

import httpx
from pydantic import BaseModel, Field

from saudi_open_data_mcp.contracts import (
    RawPayload,
    RawPayloadSnapshotWriter,
    SnapshotMetadata,
)
from saudi_open_data_mcp.observability import get_logger, get_metrics, log_event

from .errors import (
    ConnectorConfigurationError,
    ConnectorNotImplementedError,
    InvalidSourceResponseError,
    SourceAccessPolicyViolationError,
    SourceTimeoutError,
    SourceUnavailableError,
)

LOGGER = get_logger(__name__)
_FOLLOWABLE_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
_MAX_SAFE_REDIRECT_HOPS = 5
__all__ = [
    "Connector",
    "ConnectorIdentity",
    "DatasetCatalog",
    "DatasetCatalogEntry",
    "RawPayload",
    "RawPayloadSnapshotWriter",
    "RequestPolicy",
    "SnapshotMetadata",
]


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
            message="catalog metadata fetching is not implemented for this connector",
        )

    @abstractmethod
    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        """Fetch a raw dataset payload for a specific dataset identifier."""

    def build_timeout(self) -> httpx.Timeout:
        """Build the `httpx` timeout configuration for this connector."""

        return self.request_policy.to_httpx_timeout()

    def ensure_approved_url(self, url: str, *, dataset_id: str | None = None) -> str:
        """Ensure that connector access stays within the approved official source."""

        approved_parts = urlsplit(self.connector_identity.approved_base_url)
        candidate_parts = urlsplit(url)
        approved_path = approved_parts.path.rstrip("/")
        candidate_path = candidate_parts.path or "/"

        if (
            candidate_parts.scheme.lower() != approved_parts.scheme.lower()
            or _normalized_port(candidate_parts) != _normalized_port(approved_parts)
            or (candidate_parts.hostname or "").casefold()
            != (approved_parts.hostname or "").casefold()
            or candidate_parts.username is not None
            or candidate_parts.password is not None
            or (
                approved_path
                and candidate_path != approved_path
                and not candidate_path.startswith(f"{approved_path}/")
            )
        ):
            raise SourceAccessPolicyViolationError(
                source_name=self.connector_identity.source_name,
                message=f"URL '{url}' is outside the approved source boundary",
                dataset_id=dataset_id,
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
            return await self.send_request_with_redirect_revalidation(
                client_instance,
                method="GET",
                url=url,
                timeout=timeout,
                dataset_id=dataset_id,
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
        metrics = get_metrics()

        while True:
            metrics.increment(f"connector.request_attempts.{self.source_name}")
            cause: httpx.TimeoutException | httpx.HTTPStatusError | httpx.RequestError
            error: SourceTimeoutError | SourceUnavailableError
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
                metrics.increment("connector.failures")
                metrics.increment(f"connector.request_failures.{self.source_name}")
                log_event(
                    LOGGER,
                    logging.WARNING,
                    "connector.request.failed",
                    source=self.source_name,
                    dataset_id=dataset_id,
                    error_type=type(error).__name__,
                    message=error.message,
                    retries_used=retries_used,
                )
                raise error from cause

            backoff_seconds = self.retry_backoff_seconds(retries_used)
            metrics.increment("connector.retries")
            metrics.increment(f"connector.request_retries.{self.source_name}")
            log_event(
                LOGGER,
                logging.INFO,
                "connector.request.retry_scheduled",
                source=self.source_name,
                dataset_id=dataset_id,
                error_type=type(error).__name__,
                message=error.message,
                retries_used=retries_used,
                backoff_seconds=backoff_seconds,
            )
            await self.sleep_before_retry(retries_used)
            retries_used += 1

    async def send_request_with_redirect_revalidation(
        self,
        client_instance: httpx.AsyncClient,
        *,
        method: str,
        url: str,
        timeout: httpx.Timeout,
        dataset_id: str,
        data: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Send one request and manually re-validate each followed redirect target."""

        current_method = method.upper()
        current_url = self.ensure_approved_url(url, dataset_id=dataset_id)
        current_data = data
        redirects_followed = 0

        while True:
            response = await self._send_one_http_request(
                client_instance,
                method=current_method,
                url=current_url,
                timeout=timeout,
                data=current_data,
            )
            if response.status_code not in _FOLLOWABLE_REDIRECT_STATUS_CODES:
                return response

            if redirects_followed >= _MAX_SAFE_REDIRECT_HOPS:
                raise InvalidSourceResponseError(
                    source_name=self.source_name,
                    dataset_id=dataset_id,
                    message="source redirect chain exceeded the maximum safe hop count",
                )

            location = response.headers.get("location")
            if not location:
                raise InvalidSourceResponseError(
                    source_name=self.source_name,
                    dataset_id=dataset_id,
                    message="source redirect response is missing a location header",
                )

            current_url = self.ensure_approved_url(
                urljoin(current_url, location),
                dataset_id=dataset_id,
            )
            redirects_followed += 1

            if response.status_code == 303 or (
                response.status_code in {301, 302}
                and current_method not in {"GET", "HEAD"}
            ):
                current_method = "GET"
                current_data = None

    async def _send_one_http_request(
        self,
        client_instance: httpx.AsyncClient,
        *,
        method: str,
        url: str,
        timeout: httpx.Timeout,
        data: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Send one HTTP request without automatic redirect following."""

        if method == "GET" and data is None and hasattr(client_instance, "get"):
            return await client_instance.get(
                url,
                follow_redirects=False,
                timeout=timeout,
            )

        return await client_instance.request(
            method,
            url,
            data=data,
            follow_redirects=False,
            timeout=timeout,
        )


def _normalized_port(parts) -> int | None:
    """Return the explicit or default port for a parsed URL."""

    if parts.port is not None:
        return parts.port
    if parts.scheme.lower() == "https":
        return 443
    if parts.scheme.lower() == "http":
        return 80
    return None
