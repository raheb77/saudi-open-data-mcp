"""data.gov.sa raw payload connector for one narrow parsed-preview dataset path."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from .base import Connector, RawPayload, RawPayloadSnapshotWriter, RequestPolicy
from .errors import (
    InvalidSourceResponseError,
    SourceAccessPolicyViolationError,
)


class DataGovSaConnector(Connector):
    """Connector for a narrow data.gov.sa parsed-preview payload path."""

    source_name = "data-gov-sa"
    approved_base_url = "https://open.data.gov.sa"

    def __init__(
        self,
        base_url: str = "https://open.data.gov.sa",
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
        """Fetch a raw parsed-preview payload from the approved data.gov.sa route."""

        source_locator = dataset_id
        dataset_url = self._build_dataset_url(source_locator)
        response = await self._send_request(dataset_url, source_locator)
        payload = self._build_raw_payload(source_locator, response)

        if self.snapshot_store is not None:
            self.snapshot_store.write_snapshot(payload)

        return payload

    def _build_dataset_url(self, source_locator: str) -> str:
        """Build and validate the approved data.gov.sa parsed-preview URL."""

        normalized = source_locator.strip()
        if not normalized:
            raise ValueError("dataset_id must not be empty")

        if normalized.startswith(("http://", "https://")):
            candidate = normalized
        elif normalized.startswith("/"):
            candidate = f"{self.approved_base_url}{normalized}"
        else:
            candidate = f"{self.approved_base_url}/{normalized}"

        approved_url = self.ensure_approved_url(candidate)
        approved_parts = urlparse(self.approved_base_url)
        candidate_parts = urlparse(approved_url)

        if (
            candidate_parts.scheme != approved_parts.scheme
            or candidate_parts.netloc != approved_parts.netloc
        ):
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message="data.gov.sa connector URL must resolve to the approved official host",
                dataset_id=source_locator,
            )

        if "/datasets/view/" not in candidate_parts.path:
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message="data.gov.sa connector only fetches dataset preview routes in v0.2",
                dataset_id=source_locator,
            )

        if "/preview/parsed/" not in candidate_parts.path:
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message="data.gov.sa connector only fetches parsed preview routes in v0.2",
                dataset_id=source_locator,
            )

        if not candidate_parts.path.endswith(".json"):
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message="data.gov.sa parsed preview requests must target a JSON resource",
                dataset_id=source_locator,
            )

        return approved_url

    async def _send_request(self, url: str, source_locator: str) -> httpx.Response:
        """Send a timeout-aware request to the approved data.gov.sa URL with retries."""

        return await self.execute_get_with_retries(
            client=self._client,
            url=url,
            dataset_id=source_locator,
            source_label="data.gov.sa",
        )

    def _build_raw_payload(self, source_locator: str, response: httpx.Response) -> RawPayload:
        """Convert an HTTP response into a typed raw payload."""

        content = self._build_response_content(source_locator, response)
        return RawPayload(
            source=self.source_name,
            dataset_id=source_locator,
            content=content,
        )

    def _build_response_content(
        self,
        source_locator: str,
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
                    dataset_id=source_locator,
                    message="data.gov.sa source returned invalid JSON content",
                ) from exc
            if not isinstance(body, (dict, list)):
                raise InvalidSourceResponseError(
                    source_name=self.source_name,
                    dataset_id=source_locator,
                    message="data.gov.sa JSON payload must be an object or array",
                )
        else:
            body = response.text
            if not body.strip():
                raise InvalidSourceResponseError(
                    source_name=self.source_name,
                    dataset_id=source_locator,
                    message="data.gov.sa source returned an empty response body",
                )

        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "content_type": content_type,
            "body": body,
        }
