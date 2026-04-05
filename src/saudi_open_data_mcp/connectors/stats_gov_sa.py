"""stats.gov.sa raw payload connector for the narrow inflation news surface."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from .base import Connector, RawPayload, RawPayloadSnapshotWriter, RequestPolicy
from .errors import (
    InvalidSourceResponseError,
    SourceAccessPolicyViolationError,
)


class StatsGovSaConnector(Connector):
    """Connector for the current narrow official stats.gov.sa inflation news surface."""

    source_name = "stats-gov-sa"
    approved_base_url = "https://www.stats.gov.sa"
    approved_news_path = "/en/news"

    def __init__(
        self,
        base_url: str = "https://www.stats.gov.sa",
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
        """Fetch a raw stats.gov.sa payload from the approved inflation news locator."""

        dataset_locator = dataset_id
        source_url = self._build_source_url(dataset_locator)
        response = await self._send_request(source_url, dataset_locator)
        payload = self._build_raw_payload(dataset_locator, response)

        if self.snapshot_store is not None:
            self.snapshot_store.write_snapshot(payload)

        return payload

    def _build_source_url(self, dataset_locator: str) -> str:
        """Build and validate the approved stats.gov.sa inflation news URL."""

        normalized = dataset_locator.strip()
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
                message=(
                    "stats.gov.sa connector URL must resolve to the approved official host"
                ),
                dataset_id=dataset_locator,
            )

        if candidate_parts.path != self.approved_news_path:
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message=(
                    "stats.gov.sa connector only fetches the approved inflation news route"
                ),
                dataset_id=dataset_locator,
            )

        if candidate_parts.fragment:
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message="stats.gov.sa news requests must not include fragment data",
                dataset_id=dataset_locator,
            )

        query = parse_qs(candidate_parts.query, keep_blank_values=True)
        if set(query) - {"q", "delta", "page", "start"}:
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message=(
                    "stats.gov.sa inflation news requests may only use q, delta, page, and "
                    "start query parameters"
                ),
                dataset_id=dataset_locator,
            )

        q_values = tuple(value.strip().lower() for value in query.get("q", ()))
        if q_values != ("inflation",):
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message=(
                    "stats.gov.sa connector only fetches the official inflation-filtered "
                    "news route"
                ),
                dataset_id=dataset_locator,
            )

        for parameter in ("delta", "page", "start"):
            for value in query.get(parameter, ()):
                if not value.isdigit():
                    raise SourceAccessPolicyViolationError(
                        source_name=self.source_name,
                        message=(
                            f"stats.gov.sa inflation news parameter '{parameter}' must be a "
                            "positive integer"
                        ),
                        dataset_id=dataset_locator,
                    )

        return approved_url

    async def _send_request(self, url: str, dataset_locator: str) -> httpx.Response:
        """Send a timeout-aware request to the approved stats.gov.sa URL with retries."""

        return await self.execute_get_with_retries(
            client=self._client,
            url=url,
            dataset_id=dataset_locator,
            source_label="stats.gov.sa",
        )

    def _build_raw_payload(self, dataset_locator: str, response: httpx.Response) -> RawPayload:
        """Convert an HTTP response into a typed raw payload."""

        content = self._build_response_content(dataset_locator, response)
        return RawPayload(
            source=self.source_name,
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
                    message="stats.gov.sa source returned invalid JSON content",
                ) from exc
            if not isinstance(body, (dict, list)):
                raise InvalidSourceResponseError(
                    source_name=self.source_name,
                    dataset_id=dataset_locator,
                    message="stats.gov.sa JSON payload must be an object or array",
                )
        else:
            body = response.text
            if not body.strip():
                raise InvalidSourceResponseError(
                    source_name=self.source_name,
                    dataset_id=dataset_locator,
                    message="stats.gov.sa source returned an empty response body",
                )

        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "content_type": content_type,
            "body": body,
        }
