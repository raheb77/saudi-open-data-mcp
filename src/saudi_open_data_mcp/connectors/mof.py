"""Ministry of Finance raw payload connector for narrow approved fiscal reports."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from pypdf import PdfReader

from .base import Connector, RawPayload, RawPayloadSnapshotWriter, RequestPolicy
from .errors import InvalidSourceResponseError, SourceAccessPolicyViolationError

_APPROVED_REPORTS_YEAR = "2025"
_REPORT_LINK_PATTERN = re.compile(
    fr'href="(?P<href>/en/financialreport/{_APPROVED_REPORTS_YEAR}/Documents/[^"]+\.pdf)"',
    flags=re.IGNORECASE,
)
_REPORT_BASENAME_PATTERN = re.compile(
    fr"^Q(?P<quarter>[1-4])(?:E)?[\s_-]*{_APPROVED_REPORTS_YEAR}.*\.pdf$",
    flags=re.IGNORECASE,
)


class MoFConnector(Connector):
    """Connector for the current narrow Ministry of Finance fiscal surface.

    This connector is intentionally pinned to the currently approved 2025
    quarterly budget-performance page and linked quarterly report PDFs.
    Future annual rollover is expected to be explicit rather than automatic.
    """

    source_name = "mof"
    approved_base_url = "https://www.mof.gov.sa"
    approved_reports_page_path = f"/en/financialreport/{_APPROVED_REPORTS_YEAR}/Pages/default.aspx"
    approved_documents_prefix = f"/en/financialreport/{_APPROVED_REPORTS_YEAR}/Documents/"

    def __init__(
        self,
        base_url: str = "https://www.mof.gov.sa",
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
        """Fetch the approved MoF reports page and the linked quarterly report PDFs."""

        dataset_locator = dataset_id
        page_url = self._build_source_url(dataset_locator)
        page_response = await self._send_request(page_url, dataset_locator)
        page_content = self._build_html_response_content(dataset_locator, page_response)
        report_urls = self._extract_report_pdf_urls(
            html=page_content["body"],
            dataset_locator=dataset_locator,
        )

        reports = []
        for report_url in report_urls:
            report_response = await self._send_request(report_url, dataset_locator)
            report_body = self._build_pdf_text_response_content(dataset_locator, report_response)
            reports.append(
                {
                    "report_url": str(report_response.url),
                    "report_text": report_body["body"],
                }
            )

        payload = RawPayload(
            source=self.source_name,
            dataset_id=dataset_locator,
            content={
                "url": page_content["url"],
                "status_code": page_content["status_code"],
                "content_type": "application/json",
                "body": {
                    "reports_page_url": page_content["url"],
                    "reports": reports,
                },
            },
        )

        if self.snapshot_store is not None:
            self.snapshot_store.write_snapshot(payload)

        return payload

    def _build_source_url(self, dataset_locator: str) -> str:
        """Build and validate the approved MoF reports page URL."""

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
                message="Ministry of Finance connector URL must resolve to the approved host",
                dataset_id=dataset_locator,
            )

        if candidate_parts.path != self.approved_reports_page_path:
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message=(
                    "Ministry of Finance connector only fetches the current approved "
                    f"{_APPROVED_REPORTS_YEAR} quarterly budget performance page; "
                    "future annual rollover must be explicit"
                ),
                dataset_id=dataset_locator,
            )

        if candidate_parts.query or candidate_parts.fragment:
            raise SourceAccessPolicyViolationError(
                source_name=self.source_name,
                message=(
                    "Ministry of Finance quarterly budget performance requests must not "
                    "include query or fragment data"
                ),
                dataset_id=dataset_locator,
            )

        return approved_url

    def _extract_report_pdf_urls(self, *, html: str, dataset_locator: str) -> tuple[str, ...]:
        """Extract approved quarterly report PDF URLs from the reports page HTML."""

        discovered_urls: dict[int, str] = {}
        for match in _REPORT_LINK_PATTERN.finditer(html):
            href = match.group("href")
            basename = href.rsplit("/", maxsplit=1)[-1]
            report_match = _REPORT_BASENAME_PATTERN.match(unquote(basename))
            if report_match is None:
                continue
            quarter = int(report_match.group("quarter"))
            discovered_urls[quarter] = f"{self.approved_base_url}{href}"

        if not discovered_urls:
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message=(
                    "Ministry of Finance reports page did not expose approved "
                    f"{_APPROVED_REPORTS_YEAR} quarterly report PDF links"
                ),
            )

        return tuple(discovered_urls[quarter] for quarter in sorted(discovered_urls))

    async def _send_request(self, url: str, dataset_locator: str) -> httpx.Response:
        """Send a timeout-aware request to the approved MoF URL with retries."""

        return await self.execute_get_with_retries(
            client=self._client,
            url=url,
            dataset_id=dataset_locator,
            source_label="Ministry of Finance",
        )

    def _build_html_response_content(
        self,
        dataset_locator: str,
        response: httpx.Response,
    ) -> dict[str, Any]:
        """Build the raw HTML response content for the MoF reports page."""

        content_type = response.headers.get("content-type", "").split(";", maxsplit=1)[0].strip()
        if content_type.lower() != "text/html":
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="Ministry of Finance reports page must return HTML content",
            )

        body = response.text
        if not body.strip():
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="Ministry of Finance reports page returned an empty response body",
            )

        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "content_type": content_type,
            "body": body,
        }

    def _build_pdf_text_response_content(
        self,
        dataset_locator: str,
        response: httpx.Response,
    ) -> dict[str, Any]:
        """Build extracted text content for an approved MoF quarterly report PDF."""

        content_type = response.headers.get("content-type", "").split(";", maxsplit=1)[0].strip()
        if content_type.lower() != "application/pdf":
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="Ministry of Finance quarterly report links must return PDF content",
            )

        body = self._extract_pdf_text(response.content, dataset_id=dataset_locator)
        if not body.strip():
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="Ministry of Finance quarterly report PDF did not expose extractable text",
            )

        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "content_type": content_type,
            "body": body,
        }

    @staticmethod
    def _extract_pdf_text(pdf_bytes: bytes, *, dataset_id: str) -> str:
        """Extract text from a quarterly report PDF using a narrow built-in reader."""

        try:
            reader = PdfReader(BytesIO(pdf_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise InvalidSourceResponseError(
                source_name="mof",
                dataset_id=dataset_id,
                message="Ministry of Finance quarterly report PDF text extraction failed",
            ) from exc
