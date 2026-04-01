"""SAMA raw payload connector.

In v0.1, the public `dataset_id` argument is currently treated as a
SAMA-specific report locator rather than a canonical semantic dataset identifier.
That canonical identity is expected to be resolved later at the registry and
normalization boundary.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from ..storage.snapshots import SnapshotStore
from .base import Connector, RawPayload, RequestPolicy
from .errors import (
    InvalidSourceResponseError,
    SourceAccessPolicyViolationError,
    SourceTimeoutError,
    SourceUnavailableError,
)


class SAMAConnector(Connector):
    """Connector for raw payload retrieval from the official SAMA open-data portal."""

    source_name = "sama"
    approved_base_url = "https://www.sama.gov.sa"

    def __init__(
        self,
        base_url: str = "https://www.sama.gov.sa",
        *,
        request_policy: RequestPolicy | None = None,
        snapshot_store: SnapshotStore | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.approved_base_url = base_url.rstrip("/")
        self.snapshot_store = snapshot_store
        self._client = client
        if request_policy is not None:
            self.request_policy = request_policy

    async def fetch_dataset_payload(self, dataset_id: str) -> RawPayload:
        """Fetch a raw SAMA report payload from the approved report route.

        In v0.1, `dataset_id` is treated as a report locator such as
        `report.aspx?cid=55`, not as a canonical registry identifier.
        """

        dataset_locator = dataset_id
        report_url = self._build_report_url(dataset_locator)
        response = await self._send_request(report_url, dataset_locator)
        payload = self._build_raw_payload(dataset_locator, response)

        if self.snapshot_store is not None:
            self.snapshot_store.write_snapshot(payload)

        return payload

    def _build_report_url(self, dataset_locator: str) -> str:
        """Build and validate the approved SAMA report URL for a report locator."""

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

        if candidate_parts.path != "/en-US/EconomicReports/Pages/report.aspx":
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message="SAMA connector only fetches report.aspx payload routes in v0.1",
                dataset_id=dataset_locator,
            )

        if not candidate_parts.query:
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message="SAMA report payload requests must include a dataset query string",
                dataset_id=dataset_locator,
            )

        return approved_url

    async def _send_request(self, url: str, dataset_locator: str) -> httpx.Response:
        """Send a single timeout-aware request to the approved SAMA URL."""

        try:
            if self._client is None:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        url,
                        follow_redirects=True,
                        timeout=self.build_timeout(),
                    )
            else:
                response = await self._client.get(
                    url,
                    follow_redirects=True,
                    timeout=self.build_timeout(),
                )
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise SourceTimeoutError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA source request timed out",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise SourceUnavailableError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message=f"SAMA source returned HTTP {exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            raise SourceUnavailableError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA source request failed",
            ) from exc

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
