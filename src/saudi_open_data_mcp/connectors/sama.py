"""SAMA raw payload connector."""

from __future__ import annotations

import asyncio
import http.client
import math
import re
import socket
import ssl
from dataclasses import dataclass
from html import unescape
from io import BytesIO
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

import httpx
from pypdf import PdfReader

from .base import Connector, RawPayload, RawPayloadSnapshotWriter, RequestPolicy
from .errors import (
    InvalidSourceResponseError,
    SourceAccessPolicyViolationError,
)

_POS_PAGE_PATH = "/en-US/Indices/Pages/POS.aspx"
_EXCHANGE_RATES_PAGE_PATH = "/en-US/FinExc/Pages/Currency.aspx"
_POS_REPORTS_PREFIX = "/en-US/Indices/POS_EN/"
_POS_REPORT_LINK_PATTERN = re.compile(
    r"""href=(?:"|')(?P<href>(?:https://www\.sama\.gov\.sa)?/en-US/Indices/POS_EN/[^"']+\.pdf)(?:"|')""",
    flags=re.IGNORECASE,
)
_HTML_INPUT_PATTERN = re.compile(
    r"<input\b(?P<attrs>[^>]*)/?>",
    flags=re.IGNORECASE | re.DOTALL,
)
_HTML_SELECT_PATTERN = re.compile(
    r"<select\b(?P<attrs>[^>]*)>(?P<body>.*?)</select>",
    flags=re.IGNORECASE | re.DOTALL,
)
_HTML_OPTION_PATTERN = re.compile(
    r"<option\b(?P<attrs>[^>]*)>(?P<body>.*?)</option>",
    flags=re.IGNORECASE | re.DOTALL,
)
_HTML_FORM_PATTERN = re.compile(
    r"<form\b(?P<attrs>[^>]*)>",
    flags=re.IGNORECASE | re.DOTALL,
)
_HTML_TABLE_PATTERN = re.compile(
    r"<table\b(?P<attrs>[^>]*)>(?P<body>.*?)</table>",
    flags=re.IGNORECASE | re.DOTALL,
)
_HTML_ROW_PATTERN = re.compile(
    r"<tr\b(?P<attrs>[^>]*)>(?P<body>.*?)</tr>",
    flags=re.IGNORECASE | re.DOTALL,
)
_HTML_CELL_PATTERN = re.compile(
    r"<t[dh]\b(?P<attrs>[^>]*)>(?P<body>.*?)</t[dh]>",
    flags=re.IGNORECASE | re.DOTALL,
)
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_HTML_ATTR_PATTERN = re.compile(
    r"""([A-Za-z_:][-A-Za-z0-9_:.]*)
        (?:\s*=\s*
            (?:
                "([^"]*)"
                |'([^']*)'
                |([^\s>]+)
            )
        )?
    """,
    flags=re.VERBOSE,
)
_RESULTS_COUNT_PATTERN = re.compile(
    r"Number of result is\s*(?P<count>\d+)",
    flags=re.IGNORECASE,
)
_POSTBACK_LINK_PATTERN = re.compile(
    r"""<a\b[^>]*href="javascript:__doPostBack\('(?P<target>[^']+)','[^']*'\)"[^>]*>
        (?P<label>.*?)</a>""",
    flags=re.IGNORECASE | re.DOTALL | re.VERBOSE,
)
_EXCHANGE_RATES_DATE_FIELD_NAME_FRAGMENT = "txtdatepicker"
_EXCHANGE_RATES_CURRENCY_FIELD_NAME_FRAGMENT = "ddlcurrencies"
_EXCHANGE_RATES_SEARCH_BUTTON_NAME_FRAGMENT = "btnsearch"
_MAX_GENERIC_RESPONSE_BYTES = 5 * 1024 * 1024
_MAX_HTML_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_PDF_RESPONSE_BYTES = 10 * 1024 * 1024
_MAX_POS_REPORTS_PER_BUNDLE = 12
_MAX_EXCHANGE_RATES_PAGE_COUNT = 20


@dataclass(frozen=True, slots=True)
class _ExchangeRatesFormState:
    action_url: str
    hidden_fields: dict[str, str]
    currency_field_name: str
    currency_all_value: str
    date_field_name: str
    search_button_name: str
    search_button_value: str


@dataclass(frozen=True, slots=True)
class _ExchangeRatesPageState:
    form_state: _ExchangeRatesFormState
    latest_date_text: str
    row_date_texts: tuple[str, ...]
    total_results_count: int
    page_row_count: int
    pager_targets: dict[str, str]
    ellipsis_target: str | None


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
        path = urlparse(source_url).path
        if path == _POS_PAGE_PATH:
            payload = await self._fetch_pos_report_bundle(
                dataset_locator=dataset_locator,
                source_url=source_url,
            )
        elif path == _EXCHANGE_RATES_PAGE_PATH:
            payload = await self._fetch_exchange_rates_current_bundle(
                dataset_locator=dataset_locator,
                source_url=source_url,
            )
        else:
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

    async def _send_request(
        self,
        url: str,
        dataset_locator: str,
        *,
        method: str = "GET",
        form_data: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Send a timeout-aware request to the approved SAMA URL with bounded retries."""

        timeout = self.build_timeout()

        async def send_with(client_instance: httpx.AsyncClient) -> httpx.Response:
            try:
                return await self.send_request_with_redirect_revalidation(
                    client_instance,
                    method=method,
                    url=url,
                    timeout=timeout,
                    dataset_id=dataset_locator,
                    data=form_data,
                )
            except httpx.RequestError as exc:
                if not self._should_use_standard_library_fallback(exc):
                    raise
                return await self._send_request_via_standard_library(
                    url=url,
                    timeout_seconds=self.request_policy.timeout_seconds,
                    method=method,
                    form_data=form_data,
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
        method: str = "GET",
        form_data: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Use a minimal HTTPS fallback when the current transport is rejected by SAMA."""

        request = httpx.Request(method, url)
        try:
            return await asyncio.to_thread(
                self._send_request_via_standard_library_sync,
                url=url,
                timeout_seconds=timeout_seconds,
                request=request,
                method=method,
                form_data=form_data,
            )
        except httpx.RequestError:
            raise

    def _send_request_via_standard_library_sync(
        self,
        *,
        url: str,
        timeout_seconds: float,
        request: httpx.Request,
        method: str,
        form_data: dict[str, str] | None,
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
            body = None
            headers = dict(self.fallback_request_headers)
            if form_data is not None:
                body = urlencode(form_data).encode("utf-8")
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            connection.request(
                method,
                path,
                body=body,
                headers=headers,
            )
            response = connection.getresponse()
            response_body = response.read()
            return httpx.Response(
                status_code=response.status,
                headers=list(response.getheaders()),
                content=response_body,
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

    async def _fetch_pos_report_bundle(
        self,
        *,
        dataset_locator: str,
        source_url: str,
    ) -> RawPayload:
        """Fetch the POS reports page and the approved linked report PDFs."""

        page_response = await self._send_request(source_url, dataset_locator)
        page_content = self._build_html_response_content(dataset_locator, page_response)
        report_urls = self._extract_pos_report_pdf_urls(
            html=page_content["body"],
            dataset_locator=dataset_locator,
        )
        if len(report_urls) > _MAX_POS_REPORTS_PER_BUNDLE:
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message=(
                    "SAMA POS page exposed more approved report PDFs than the current "
                    f"safety ceiling allows ({_MAX_POS_REPORTS_PER_BUNDLE})"
                ),
            )

        reports = []
        for report_url in report_urls:
            report_response = await self._send_request(report_url, dataset_locator)
            report_body = self._build_pdf_text_response_content(
                dataset_locator,
                report_response,
            )
            reports.append(
                {
                    "report_url": report_body["url"],
                    "report_text": report_body["body"],
                }
            )

        return RawPayload(
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

    async def _fetch_exchange_rates_current_bundle(
        self,
        *,
        dataset_locator: str,
        source_url: str,
    ) -> RawPayload:
        """Fetch the latest-date SAMA exchange-rate rows across all filtered pages."""

        landing_response = await self._send_request(source_url, dataset_locator)
        landing_content = self._build_html_response_content(dataset_locator, landing_response)
        landing_state = self._extract_exchange_rates_page_state(
            html=landing_content["body"],
            page_url=landing_content["url"],
            dataset_locator=dataset_locator,
        )
        current_date_text = landing_state.latest_date_text

        search_response = await self._send_request(
            landing_state.form_state.action_url,
            dataset_locator,
            method="POST",
            form_data=self._build_exchange_rates_search_form_data(
                form_state=landing_state.form_state,
                current_date_text=current_date_text,
            ),
        )
        search_content = self._build_html_response_content(dataset_locator, search_response)
        current_state = self._extract_exchange_rates_page_state(
            html=search_content["body"],
            page_url=search_content["url"],
            dataset_locator=dataset_locator,
        )
        self._validate_exchange_rates_page_dates(
            page_state=current_state,
            current_date_text=current_date_text,
            dataset_locator=dataset_locator,
        )

        pages = [
            {
                "page_number": 1,
                "page_url": search_content["url"],
                "body": search_content["body"],
            }
        ]
        expected_page_count = math.ceil(
            current_state.total_results_count / current_state.page_row_count
        )
        if expected_page_count > _MAX_EXCHANGE_RATES_PAGE_COUNT:
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message=(
                    "SAMA exchange-rates page count exceeded the current safety ceiling "
                    f"({_MAX_EXCHANGE_RATES_PAGE_COUNT})"
                ),
            )
        target_page_number = 2

        while target_page_number <= expected_page_count:
            event_target = self._resolve_exchange_rates_event_target(
                page_state=current_state,
                target_page_number=target_page_number,
            )
            next_response = await self._send_request(
                current_state.form_state.action_url,
                dataset_locator,
                method="POST",
                form_data=self._build_exchange_rates_pager_form_data(
                    form_state=current_state.form_state,
                    current_date_text=current_date_text,
                    event_target=event_target,
                ),
            )
            next_content = self._build_html_response_content(dataset_locator, next_response)
            current_state = self._extract_exchange_rates_page_state(
                html=next_content["body"],
                page_url=next_content["url"],
                dataset_locator=dataset_locator,
            )
            self._validate_exchange_rates_page_dates(
                page_state=current_state,
                current_date_text=current_date_text,
                dataset_locator=dataset_locator,
            )
            pages.append(
                {
                    "page_number": target_page_number,
                    "page_url": next_content["url"],
                    "body": next_content["body"],
                }
            )
            target_page_number += 1

        return RawPayload(
            source=self.source_name,
            dataset_id=dataset_locator,
            content={
                "url": landing_content["url"],
                "status_code": landing_content["status_code"],
                "content_type": "application/json",
                "body": {
                    "results_page_url": landing_content["url"],
                    "current_date_text": current_date_text,
                    "total_results_count": current_state.total_results_count,
                    "pages": pages,
                },
            },
        )

    def _extract_exchange_rates_page_state(
        self,
        *,
        html: str,
        page_url: str,
        dataset_locator: str,
    ) -> _ExchangeRatesPageState:
        form_state = self._extract_exchange_rates_form_state(
            html=html,
            page_url=page_url,
            dataset_locator=dataset_locator,
        )
        table_html = self._extract_exchange_rates_results_table_html(
            html=html,
            dataset_locator=dataset_locator,
        )
        row_dates, pager_targets, ellipsis_target = self._extract_exchange_rates_rows_and_pager(
            table_html=table_html,
            dataset_locator=dataset_locator,
        )
        total_results_count = self._extract_exchange_rates_total_results_count(
            html=html,
            dataset_locator=dataset_locator,
        )
        if total_results_count < len(row_dates):
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA exchange-rates page declared fewer results than visible rows",
            )

        return _ExchangeRatesPageState(
            form_state=form_state,
            latest_date_text=row_dates[0],
            row_date_texts=row_dates,
            total_results_count=total_results_count,
            page_row_count=len(row_dates),
            pager_targets=pager_targets,
            ellipsis_target=ellipsis_target,
        )

    def _extract_exchange_rates_form_state(
        self,
        *,
        html: str,
        page_url: str,
        dataset_locator: str,
    ) -> _ExchangeRatesFormState:
        form_match = _HTML_FORM_PATTERN.search(html)
        if form_match is None:
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA exchange-rates page did not expose the expected form state",
            )

        form_attrs = self._parse_html_attributes(form_match.group("attrs"))
        action = form_attrs.get("action")
        if not isinstance(action, str) or not action.strip():
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA exchange-rates form action is missing",
            )

        hidden_fields: dict[str, str] = {}
        date_field_name: str | None = None
        currency_field_name: str | None = None
        search_button_name: str | None = None
        search_button_value: str | None = None

        for input_match in _HTML_INPUT_PATTERN.finditer(html):
            attrs = self._parse_html_attributes(input_match.group("attrs"))
            input_name = attrs.get("name")
            if not isinstance(input_name, str) or not input_name:
                continue

            input_type = str(attrs.get("type", "")).casefold()
            input_value = str(attrs.get("value", ""))
            name_key = input_name.casefold()

            if input_type == "hidden":
                hidden_fields[input_name] = input_value
            elif _EXCHANGE_RATES_DATE_FIELD_NAME_FRAGMENT in name_key:
                date_field_name = input_name
            elif _EXCHANGE_RATES_SEARCH_BUTTON_NAME_FRAGMENT in name_key:
                search_button_name = input_name
                search_button_value = input_value or "Search"

        currency_field_name, currency_all_value = self._extract_exchange_rates_currency_field(
            html=html,
            dataset_locator=dataset_locator,
        )

        if (
            date_field_name is None
            or search_button_name is None
            or search_button_value is None
        ):
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA exchange-rates page is missing required form inputs",
            )

        return _ExchangeRatesFormState(
            action_url=urljoin(page_url, action),
            hidden_fields=hidden_fields,
            currency_field_name=currency_field_name,
            currency_all_value=currency_all_value,
            date_field_name=date_field_name,
            search_button_name=search_button_name,
            search_button_value=search_button_value,
        )

    def _extract_exchange_rates_currency_field(
        self,
        *,
        html: str,
        dataset_locator: str,
    ) -> tuple[str, str]:
        for select_match in _HTML_SELECT_PATTERN.finditer(html):
            attrs = self._parse_html_attributes(select_match.group("attrs"))
            select_name = attrs.get("name")
            if not isinstance(select_name, str):
                continue
            if _EXCHANGE_RATES_CURRENCY_FIELD_NAME_FRAGMENT not in select_name.casefold():
                continue

            default_value = "-1"
            for option_match in _HTML_OPTION_PATTERN.finditer(select_match.group("body")):
                option_attrs = self._parse_html_attributes(option_match.group("attrs"))
                if option_attrs.get("selected") is not None:
                    selected_value = option_attrs.get("value")
                    if isinstance(selected_value, str):
                        default_value = selected_value
                        break
            return select_name, default_value

        raise InvalidSourceResponseError(
            source_name=self.source_name,
            dataset_id=dataset_locator,
            message="SAMA exchange-rates page did not expose the expected currency selector",
        )

    def _extract_exchange_rates_results_table_html(
        self,
        *,
        html: str,
        dataset_locator: str,
    ) -> str:
        for table_match in _HTML_TABLE_PATTERN.finditer(html):
            attrs = self._parse_html_attributes(table_match.group("attrs"))
            table_id = str(attrs.get("id", ""))
            table_class = str(attrs.get("class", ""))
            if "dgResults" in table_id or "tableCurrency" in table_class:
                return table_match.group("body")

        raise InvalidSourceResponseError(
            source_name=self.source_name,
            dataset_id=dataset_locator,
            message="SAMA exchange-rates page did not expose the expected results table",
        )

    def _extract_exchange_rates_rows_and_pager(
        self,
        *,
        table_html: str,
        dataset_locator: str,
    ) -> tuple[tuple[str, ...], dict[str, str], str | None]:
        row_dates: list[str] = []
        pager_targets: dict[str, str] = {}
        ellipsis_target: str | None = None
        header_seen = False
        unescaped_table_html = unescape(table_html)

        for row_match in _HTML_ROW_PATTERN.finditer(table_html):
            row_attrs = self._parse_html_attributes(row_match.group("attrs"))
            row_html = row_match.group("body")
            cells = self._extract_exchange_rates_row_cells(row_html)
            if not cells:
                continue

            normalized_header = tuple(
                self._normalize_header(cell) for cell in cells[:3]
            )
            if normalized_header == (
                "currency against s r",
                "closing price",
                "last updated date",
            ):
                header_seen = True
                continue

            row_class = str(row_attrs.get("class", "")).casefold()
            if "pagerstyle" in row_class or "javascript:__doPostBack" in unescape(row_html):
                for link_match in _POSTBACK_LINK_PATTERN.finditer(unescaped_table_html):
                    label = self._clean_html_text(link_match.group("label"))
                    if label == "...":
                        ellipsis_target = link_match.group("target")
                    elif label.isdigit():
                        pager_targets[label] = link_match.group("target")
                continue

            if not header_seen or len(cells) < 3:
                continue

            row_dates.append(cells[2])

        if not row_dates:
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA exchange-rates results table did not expose visible rows",
            )

        return tuple(row_dates), pager_targets, ellipsis_target

    def _extract_exchange_rates_total_results_count(
        self,
        *,
        html: str,
        dataset_locator: str,
    ) -> int:
        match = _RESULTS_COUNT_PATTERN.search(self._clean_html_text(html))
        if match is None:
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA exchange-rates page did not expose the total results count",
            )
        count = int(match.group("count"))
        if count < 1:
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA exchange-rates page returned an empty latest-date result set",
            )
        return count

    def _validate_exchange_rates_page_dates(
        self,
        *,
        page_state: _ExchangeRatesPageState,
        current_date_text: str,
        dataset_locator: str,
    ) -> None:
        if any(date_text != current_date_text for date_text in page_state.row_date_texts):
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA exchange-rates pagination drifted outside the latest date",
            )

    def _resolve_exchange_rates_event_target(
        self,
        *,
        page_state: _ExchangeRatesPageState,
        target_page_number: int,
    ) -> str:
        target = page_state.pager_targets.get(str(target_page_number))
        if target is not None:
            return target
        numeric_targets = [int(label) for label in page_state.pager_targets if label.isdigit()]
        if (
            page_state.ellipsis_target is not None
            and numeric_targets
            and target_page_number > max(numeric_targets)
        ):
            return page_state.ellipsis_target
        raise InvalidSourceResponseError(
            source_name=self.source_name,
            dataset_id=_EXCHANGE_RATES_PAGE_PATH,
            message="SAMA exchange-rates pagination did not expose the expected page link",
        )

    def _build_exchange_rates_search_form_data(
        self,
        *,
        form_state: _ExchangeRatesFormState,
        current_date_text: str,
    ) -> dict[str, str]:
        return {
            **form_state.hidden_fields,
            form_state.currency_field_name: form_state.currency_all_value,
            form_state.date_field_name: current_date_text,
            form_state.search_button_name: form_state.search_button_value,
        }

    def _build_exchange_rates_pager_form_data(
        self,
        *,
        form_state: _ExchangeRatesFormState,
        current_date_text: str,
        event_target: str,
    ) -> dict[str, str]:
        return {
            **form_state.hidden_fields,
            "__EVENTTARGET": event_target,
            "__EVENTARGUMENT": "",
            form_state.currency_field_name: form_state.currency_all_value,
            form_state.date_field_name: current_date_text,
        }

    def _extract_exchange_rates_row_cells(self, row_html: str) -> list[str]:
        cells: list[str] = []
        for cell_match in _HTML_CELL_PATTERN.finditer(row_html):
            cells.append(self._clean_html_text(cell_match.group("body")))
        return cells

    def _parse_html_attributes(self, fragment: str) -> dict[str, str | bool]:
        attributes: dict[str, str | bool] = {}
        for match in _HTML_ATTR_PATTERN.finditer(fragment):
            name = match.group(1).casefold()
            value = match.group(2) or match.group(3) or match.group(4)
            attributes[name] = value if value is not None else True
        return attributes

    def _clean_html_text(self, fragment: str) -> str:
        text = unescape(_HTML_TAG_PATTERN.sub(" ", fragment)).replace("\xa0", " ")
        return " ".join(text.split())

    def _normalize_header(self, value: str) -> str:
        return " ".join(
            re.sub(r"[^a-z0-9]+", " ", value.strip().casefold()).split()
        )

    def _extract_pos_report_pdf_urls(self, *, html: str, dataset_locator: str) -> tuple[str, ...]:
        """Extract approved POS report PDF URLs from the reports page HTML."""

        discovered_urls: list[str] = []
        seen_urls: set[str] = set()
        approved_parts = urlparse(self.approved_base_url)

        for match in _POS_REPORT_LINK_PATTERN.finditer(html):
            href = match.group("href")
            candidate = href
            if candidate.startswith("/"):
                candidate = f"{self.approved_base_url}{candidate}"

            approved_url = self.ensure_approved_url(candidate)
            candidate_parts = urlparse(approved_url)
            if (
                candidate_parts.scheme != approved_parts.scheme
                or candidate_parts.netloc != approved_parts.netloc
                or not candidate_parts.path.startswith(_POS_REPORTS_PREFIX)
                or candidate_parts.query
                or candidate_parts.fragment
            ):
                continue

            if approved_url in seen_urls:
                continue

            seen_urls.add(approved_url)
            discovered_urls.append(approved_url)

        if not discovered_urls:
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA POS page did not expose approved POS report PDF links",
            )

        return tuple(discovered_urls)

    def _build_html_response_content(
        self,
        dataset_locator: str,
        response: httpx.Response,
    ) -> dict[str, Any]:
        """Build a raw HTML response body for a supported SAMA page."""

        self._require_response_body_size(
            response,
            dataset_locator=dataset_locator,
            max_body_bytes=_MAX_HTML_RESPONSE_BYTES,
            response_label="HTML",
        )
        content_type = response.headers.get("content-type", "").split(";", maxsplit=1)[0].strip()
        if content_type.lower() != "text/html":
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA page responses must return HTML content",
            )

        body = response.text
        if not body.strip():
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA page returned an empty response body",
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
        """Build extracted text content for an approved SAMA POS report PDF."""

        self._require_response_body_size(
            response,
            dataset_locator=dataset_locator,
            max_body_bytes=_MAX_PDF_RESPONSE_BYTES,
            response_label="PDF",
        )
        content_type = response.headers.get("content-type", "").split(";", maxsplit=1)[0].strip()
        if content_type.lower() != "application/pdf":
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA POS report links must return PDF content",
            )

        body = self._extract_pdf_text(response.content, dataset_id=dataset_locator)
        if not body.strip():
            raise InvalidSourceResponseError(
                source_name=self.source_name,
                dataset_id=dataset_locator,
                message="SAMA POS report PDF did not expose extractable text",
            )

        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "content_type": content_type,
            "body": body,
        }

    @staticmethod
    def _extract_pdf_text(pdf_bytes: bytes, *, dataset_id: str) -> str:
        """Extract text from an approved SAMA POS report PDF."""

        try:
            reader = PdfReader(BytesIO(pdf_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise InvalidSourceResponseError(
                source_name="sama",
                dataset_id=dataset_id,
                message="SAMA POS report PDF text extraction failed",
            ) from exc

    def _build_response_content(
        self,
        dataset_locator: str,
        response: httpx.Response,
    ) -> dict[str, Any]:
        """Build the raw response content without normalization."""

        self._require_response_body_size(
            response,
            dataset_locator=dataset_locator,
            max_body_bytes=_MAX_GENERIC_RESPONSE_BYTES,
            response_label="raw response",
        )
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

    def _require_response_body_size(
        self,
        response: httpx.Response,
        *,
        dataset_locator: str,
        max_body_bytes: int,
        response_label: str,
    ) -> None:
        body_bytes = response.content
        if len(body_bytes) <= max_body_bytes:
            return

        raise InvalidSourceResponseError(
            source_name=self.source_name,
            dataset_id=dataset_locator,
            message=(
                f"SAMA {response_label} exceeded the current safety ceiling of "
                f"{max_body_bytes} bytes"
            ),
        )
