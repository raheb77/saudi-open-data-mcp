"""SAMA raw payload connector."""

from __future__ import annotations

import asyncio
import http.client
import socket
import ssl
from typing import Any
from urllib.parse import urlparse

import httpx

from .base import Connector, RawPayload, RawPayloadSnapshotWriter, RequestPolicy
from .errors import (
    InvalidSourceResponseError,
    SourceAccessPolicyViolationError,
)


class SAMAConnector(Connector):
    """Connector for raw payload retrieval from the official SAMA open-data portal."""

    source_name = "sama"
    approved_base_url = "https://www.sama.gov.sa"
    fallback_request_headers = {
        "Accept": "*/*",
        "Connection": "close",
        "User-Agent": "saudi-open-data-mcp/0.1",
    }
    approved_page_paths = frozenset(
        {
            "/en-US/FinExc/Pages/Currency.aspx",
            "/en-US/Indices/Pages/POS.aspx",
            "/en-US/Indices/Pages/WeeklyMoneySupply.aspx",
            "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx",
            "/en-US/MonetaryOperations/Pages/ReverseRepoRate.aspx",
        }
    )

    def __init__(
        self,
        base_url: str = "https://www.sama.gov.sa",
        *,
        request_policy: RequestPolicy | None = None,
        snapshot_store: RawPayloadSnapshotWriter | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.approved_base_url = base_url.rstrip("/")
        self.snapshot_store = snapshot_store
        self._client = client
        if request_policy is not None:
            self.request_policy = request_policy

    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        """Fetch a raw SAMA payload from an approved report or page locator."""

        dataset_locator = dataset_id
        source_url = self._build_source_url(dataset_locator)
        response = await self._send_request(source_url, dataset_locator)
        payload = self._build_raw_payload(dataset_locator, response)

        if self.snapshot_store is not None:
            self.snapshot_store.write_snapshot(payload)

        return payload

    def _build_source_url(self, dataset_locator: str) -> str:
        """Build and validate the approved SAMA source URL for a locator."""

        normalized = dataset_locator.strip()
        if not normalized:
            raise ValueError("dataset_id must not be empty")

        if normalized.startswith(("http://", "https://")):
            candidate = normalized
        elif normalized.startswith("/"):
            candidate = f"{self.approved_base_url}{normalized}"
        elif normalized.startswith("en-US/"):
            candidate = f"{self.approved_base_url}/{normalized}"
        else:
            candidate = f"{self.approved_base_url}/en-US/EconomicReports/Pages/{normalized}"

        approved_url = self.ensure_approved_url(candidate)
        approved_parts = urlparse(self.approved_base_url)
        candidate_parts = urlparse(approved_url)

        if (
            candidate_parts.scheme != approved_parts.scheme
            or candidate_parts.netloc != approved_parts.netloc
        ):
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message="SAMA connector URL must resolve to the approved official host",
                dataset_id=dataset_locator,
            )

        if candidate_parts.path == "/en-US/EconomicReports/Pages/report.aspx":
            if not candidate_parts.query:
                raise SourceAccessPolicyViolationError(
                    source_name=self.source_name,
                    message=(
                        "SAMA report payload requests must include a dataset query string"
                    ),
                    dataset_id=dataset_locator,
                )
            return approved_url

        if candidate_parts.query or candidate_parts.fragment:
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message="SAMA page payload requests must not include query or fragment data",
                dataset_id=dataset_locator,
            )

        if candidate_parts.path not in self.approved_page_paths:
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message=(
                    "SAMA connector only fetches report.aspx payload routes and the "
                    "approved page locators"
                ),
                dataset_id=dataset_locator,
            )

        return approved_url

    async def _send_request(self, url: str, dataset_locator: str) -> httpx.Response:
        """Send a timeout-aware request to the approved SAMA URL with bounded retries."""

        timeout = self.build_timeout()

        async def send_with(client_instance: httpx.AsyncClient) -> httpx.Response:
            try:
                return await client_instance.get(
                    url,
                    follow_redirects=True,
                    timeout=timeout,
                )
            except httpx.RequestError as exc:
                if not self._should_use_standard_library_fallback(exc):
                    raise
                return await self._send_request_via_standard_library(
                    url=url,
                    timeout_seconds=self.request_policy.timeout_seconds,
                )

        if self._client is not None:
            return await self.execute_request_with_retries(
                lambda: send_with(self._client),
                dataset_id=dataset_locator,
                source_label="SAMA",
            )

        async with self.build_async_client() as managed_client:
            return await self.execute_request_with_retries(
                lambda: send_with(managed_client),
                dataset_id=dataset_locator,
                source_label="SAMA",
            )

    def _should_use_standard_library_fallback(self, error: httpx.RequestError) -> bool:
        """Return whether the current transport error should try the SAMA fallback."""

        return isinstance(error, (httpx.ReadError, httpx.RemoteProtocolError))

    async def _send_request_via_standard_library(
        self,
        *,
        url: str,
        timeout_seconds: float,
    ) -> httpx.Response:
        """Use a minimal HTTPS fallback when the current transport is rejected by SAMA."""

        request = httpx.Request("GET", url)
        try:
            return await asyncio.to_thread(
                self._send_request_via_standard_library_sync,
                url=url,
                timeout_seconds=timeout_seconds,
                request=request,
            )
        except httpx.RequestError:
            raise

    def _send_request_via_standard_library_sync(
        self,
        *,
        url: str,
        timeout_seconds: float,
        request: httpx.Request,
    ) -> httpx.Response:
        """Send one direct HTTPS request using the standard library."""

        parsed = urlparse(url)
        host = parsed.netloc
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        connection = http.client.HTTPSConnection(
            host,
            timeout=timeout_seconds,
            context=ssl.create_default_context(),
        )
        try:
            connection.request(
                "GET",
                path,
                headers=self.fallback_request_headers,
            )
            response = connection.getresponse()
            body = response.read()
            return httpx.Response(
                status_code=response.status,
                headers=list(response.getheaders()),
                content=body,
                request=request,
            )
        except (socket.timeout, TimeoutError) as exc:
            raise httpx.ReadTimeout(
                "SAMA standard-library fallback timed out",
                request=request,
            ) from exc
        except (http.client.HTTPException, OSError, ssl.SSLError) as exc:
            raise httpx.ReadError(
                "SAMA standard-library fallback failed",
                request=request,
            ) from exc
        finally:
            connection.close()

    def _build_raw_payload(self, dataset_locator: str, response: httpx.Response) -> RawPayload:
        """Convert an HTTP response into a typed raw payload."""

        content = self._build_response_content(dataset_locator, response)
        return RawPayload(
            source=self.source_name,
            # v0.1 preserves the incoming SAMA locator as the raw payload ID.
            dataset_id=dataset_locator,
            content=content,
        )

    def _build_response_content(
        self,
        dataset_locator: str,
        response: httpx.Response,
    ) -> dict[str, Any]:
        """Build the raw response content without normalization."""

        content_type = response.headers.get("content-type", "").split(";", maxsplit=1)[0].strip()
        body: Any

        if "json" in content_type.lower():
            try:
                body = response.json()
            except ValueError as exc:
                raise InvalidSourceResponseError(
                    source_name=self.source_name,
                    dataset_id=dataset_locator,
                    message="SAMA source returned invalid JSON content",
                ) from exc
            if not isinstance(body, (dict, list)):
                raise InvalidSourceResponseError(
                    source_name=self.source_name,
                    dataset_id=dataset_locator,
                    message="SAMA JSON payload must be an object or array",
                )
        else:
            body = response.text
            if not body.strip():
                raise InvalidSourceResponseError(
                    source_name=self.source_name,
                    dataset_id=dataset_locator,
                    message="SAMA source returned an empty response body",
                )

        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "content_type": content_type,
            "body": body,
        }
