"""SAMA raw payload connector."""

from __future__ import annotations

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
    approved_page_paths = frozenset(
        {
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
                    "approved Wave 1 page locators"
                ),
                dataset_id=dataset_locator,
            )

        return approved_url

    async def _send_request(self, url: str, dataset_locator: str) -> httpx.Response:
        """Send a timeout-aware request to the approved SAMA URL with bounded retries."""

        return await self.execute_get_with_retries(
            client=self._client,
            url=url,
            dataset_id=dataset_locator,
            source_label="SAMA",
        )

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
