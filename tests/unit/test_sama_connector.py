"""Unit tests for the SAMA connector."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import httpx
import pytest
import respx

from saudi_open_data_mcp.connectors.base import RawPayload, RequestPolicy
from saudi_open_data_mcp.connectors.errors import (
    InvalidSourceResponseError,
    SourceAccessPolicyViolationError,
    SourceTimeoutError,
    SourceUnavailableError,
)
from saudi_open_data_mcp.connectors.sama import SAMAConnector
from saudi_open_data_mcp.normalization.field_mapping import get_field_mapping
from saudi_open_data_mcp.storage.snapshots import SnapshotStore

REPORT_LOCATOR = "report.aspx?cid=55"
POS_PAGE_LOCATOR = "/en-US/Indices/Pages/POS.aspx"
EXCHANGE_RATES_PAGE_LOCATOR = "/en-US/FinExc/Pages/Currency.aspx"
UNAPPROVED_PAGE_LOCATOR = "/en-US/FinExc/Pages/Unsupported.aspx"


def _report_url() -> str:
    return f"https://www.sama.gov.sa/en-US/EconomicReports/Pages/{REPORT_LOCATOR}"


def _page_url(locator: str) -> str:
    return f"https://www.sama.gov.sa{locator}"


def _pos_report_url(name: str) -> str:
    return f"https://www.sama.gov.sa/en-US/Indices/POS_EN/{name}"


def _pos_reports_page_html() -> str:
    return """
        <html><body>
          <a
            href="https://www.sama.gov.sa/en-US/Indices/POS_EN/Weekly_Points_of_Sale_Transactions_Report_28-Mar-2026.pdf"
          >28 Mar</a>
          <a
            href="https://www.sama.gov.sa/en-US/Indices/POS_EN/Weekly_Points_of_Sale_Transactions_Report_21-Mar-2026.pdf"
          >21 Mar</a>
        </body></html>
    """


def _build_text_pdf_bytes(lines: list[str]) -> bytes:
    def _escape_pdf_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content_lines = ["BT", "/F1 10 Tf", "14 TL", "72 720 Td"]
    for index, line in enumerate(lines):
        if index:
            content_lines.append("T*")
        content_lines.append(f"({_escape_pdf_text(line)}) Tj")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
    ]

    pdf_bytes = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf_bytes))
        pdf_bytes.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf_bytes.extend(obj)
        pdf_bytes.extend(b"\nendobj\n")

    xref_offset = len(pdf_bytes)
    pdf_bytes.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf_bytes.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf_bytes.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf_bytes.extend(b"trailer\n")
    pdf_bytes.extend(f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii"))
    pdf_bytes.extend(b"startxref\n")
    pdf_bytes.extend(f"{xref_offset}\n".encode("ascii"))
    pdf_bytes.extend(b"%%EOF\n")
    return bytes(pdf_bytes)


@pytest.mark.asyncio
@respx.mock
async def test_fetch_dataset_payload_returns_raw_payload() -> None:
    route = respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official sama payload</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    connector = SAMAConnector()

    payload = await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert route.called
    assert isinstance(payload, RawPayload)
    assert payload.source == "sama"
    assert payload.dataset_id == REPORT_LOCATOR
    assert payload.content["content_type"] == "text/html"
    assert "official sama payload" in payload.content["body"]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_dataset_payload_allows_approved_wave_one_page_locator() -> None:
    respx.get(_page_url(POS_PAGE_LOCATOR)).mock(
        return_value=httpx.Response(
            200,
            text=_pos_reports_page_html(),
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get(
        _pos_report_url("Weekly_Points_of_Sale_Transactions_Report_28-Mar-2026.pdf")
    ).mock(
        return_value=httpx.Response(
            200,
            content=b"report-28",
            headers={"content-type": "application/pdf"},
        )
    )
    respx.get(
        _pos_report_url("Weekly_Points_of_Sale_Transactions_Report_21-Mar-2026.pdf")
    ).mock(
        return_value=httpx.Response(
            200,
            content=b"report-21",
            headers={"content-type": "application/pdf"},
        )
    )
    connector = SAMAConnector()
    connector._extract_pdf_text = staticmethod(  # type: ignore[method-assign]
        lambda pdf_bytes, *, dataset_id: pdf_bytes.decode("utf-8") + f"::{dataset_id}"
    )

    payload = await connector.fetch_dataset_payload(POS_PAGE_LOCATOR)

    assert payload.dataset_id == POS_PAGE_LOCATOR
    assert payload.content["url"] == _page_url(POS_PAGE_LOCATOR)
    assert payload.content["content_type"] == "application/json"
    reports = cast(list[dict[str, str]], payload.content["body"]["reports"])
    assert [report["report_url"] for report in reports] == [
        _pos_report_url("Weekly_Points_of_Sale_Transactions_Report_28-Mar-2026.pdf"),
        _pos_report_url("Weekly_Points_of_Sale_Transactions_Report_21-Mar-2026.pdf"),
    ]
    assert reports[0]["report_text"] == f"report-28::{POS_PAGE_LOCATOR}"
    assert reports[1]["report_text"] == f"report-21::{POS_PAGE_LOCATOR}"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_dataset_payload_round_trips_realistic_pos_pdf_text_into_queryable_rows(
) -> None:
    pdf_bytes = _build_text_pdf_bytes(
        [
            "Weekly Points of Sale Transactions",
            "Table 1: By Activities",
            "Value of Transactions: In Thousand",
            "Number of Transactions: In Thousand",
            "8 Mar,26 - 14 Mar,26 15 Mar,26 - 21 Mar,26",
            "22 Mar,26 - 28 Mar,26 29 Mar,26 - 04 Apr,26",
            "Total 226,928 16,149,247 223,899 14,793,365",
            "219,827 12,969,718 246,506 14,707,441 12.1 13.4",
            "Table 2.1: By Cities",
        ]
    )
    respx.get(_page_url(POS_PAGE_LOCATOR)).mock(
        return_value=httpx.Response(
            200,
            text="""
                <html><body>
                  <a href="https://www.sama.gov.sa/en-US/Indices/POS_EN/Weekly.pdf">Latest</a>
                </body></html>
            """,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get("https://www.sama.gov.sa/en-US/Indices/POS_EN/Weekly.pdf").mock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
        )
    )
    connector = SAMAConnector()

    payload = await connector.fetch_dataset_payload(POS_PAGE_LOCATOR)
    result = get_field_mapping(payload, canonical_dataset_id="sama-pos-weekly")

    assert result.can_derive_records is True
    rows = result.canonical_fields["structured_body"]["rows"]
    assert len(rows) == 4
    assert rows[-1]["week_start_date"] == "2026-03-29"
    assert rows[-1]["week_end_date"] == "2026-04-04"
    assert rows[-1]["transaction_count"] == 246506000
    assert rows[-1]["transaction_value_sar"] == 14707441000.0


@pytest.mark.asyncio
@respx.mock
async def test_fetch_dataset_payload_fails_when_any_pos_pdf_cannot_be_extracted() -> None:
    valid_pdf_bytes = _build_text_pdf_bytes(
        [
            "Weekly Points of Sale Transactions",
            "Table 1: By Activities",
            "Value of Transactions: In Thousand",
            "Number of Transactions: In Thousand",
            "8 Mar,26 - 14 Mar,26 15 Mar,26 - 21 Mar,26",
            "22 Mar,26 - 28 Mar,26 29 Mar,26 - 04 Apr,26",
            "Total 226,928 16,149,247 223,899 14,793,365",
            "219,827 12,969,718 246,506 14,707,441 12.1 13.4",
            "Table 2.1: By Cities",
        ]
    )
    respx.get(_page_url(POS_PAGE_LOCATOR)).mock(
        return_value=httpx.Response(
            200,
            text=_pos_reports_page_html(),
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get(
        _pos_report_url("Weekly_Points_of_Sale_Transactions_Report_28-Mar-2026.pdf")
    ).mock(
        return_value=httpx.Response(
            200,
            content=valid_pdf_bytes,
            headers={"content-type": "application/pdf"},
        )
    )
    respx.get(
        _pos_report_url("Weekly_Points_of_Sale_Transactions_Report_21-Mar-2026.pdf")
    ).mock(
        return_value=httpx.Response(
            200,
            content=b"not-a-real-pdf",
            headers={"content-type": "application/pdf"},
        )
    )
    connector = SAMAConnector()

    with pytest.raises(InvalidSourceResponseError, match="PDF text extraction failed"):
        await connector.fetch_dataset_payload(POS_PAGE_LOCATOR)


@pytest.mark.asyncio
@respx.mock
async def test_fetch_dataset_payload_allows_approved_exchange_rates_page_locator() -> None:
    route = respx.get(_page_url(EXCHANGE_RATES_PAGE_LOCATOR)).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official exchange rates page</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    connector = SAMAConnector()

    payload = await connector.fetch_dataset_payload(EXCHANGE_RATES_PAGE_LOCATOR)

    assert route.called
    assert payload.dataset_id == EXCHANGE_RATES_PAGE_LOCATOR
    assert payload.content["url"] == _page_url(EXCHANGE_RATES_PAGE_LOCATOR)
    assert payload.content["content_type"] == "text/html"


@pytest.mark.asyncio
async def test_approved_url_enforcement_rejects_unapproved_hosts() -> None:
    connector = SAMAConnector()

    with pytest.raises(SourceAccessPolicyViolationError):
        await connector.fetch_dataset_payload("https://example.com/report.aspx?cid=55")


@pytest.mark.asyncio
async def test_unapproved_page_locator_is_rejected() -> None:
    connector = SAMAConnector()

    with pytest.raises(SourceAccessPolicyViolationError):
        await connector.fetch_dataset_payload(UNAPPROVED_PAGE_LOCATOR)


@pytest.mark.asyncio
async def test_transport_disconnect_uses_standard_library_fallback() -> None:
    class DisconnectingAsyncClient:
        async def get(
            self,
            url: str,
            *,
            follow_redirects: bool,
            timeout: httpx.Timeout,
        ) -> httpx.Response:
            raise httpx.RemoteProtocolError(
                "Server disconnected without sending a response.",
                request=httpx.Request("GET", url),
            )

    class FallbackConnector(SAMAConnector):
        def __init__(self) -> None:
            super().__init__(client=DisconnectingAsyncClient())
            self.fallback_urls: list[str] = []

        def _send_request_via_standard_library_sync(
            self,
            *,
            url: str,
            timeout_seconds: float,
            request: httpx.Request,
        ) -> httpx.Response:
            self.fallback_urls.append(url)
            if url == _page_url(POS_PAGE_LOCATOR):
                return httpx.Response(
                    200,
                    headers={"content-type": "text/html; charset=utf-8"},
                    text=_pos_reports_page_html(),
                    request=request,
                )
            return httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=b"report-pdf",
                request=request,
            )

    connector = FallbackConnector()
    connector._extract_pdf_text = staticmethod(  # type: ignore[method-assign]
        lambda pdf_bytes, *, dataset_id: pdf_bytes.decode("utf-8") + f"::{dataset_id}"
    )

    payload = await connector.fetch_dataset_payload(POS_PAGE_LOCATOR)

    assert connector.fallback_urls == [
        _page_url(POS_PAGE_LOCATOR),
        _pos_report_url("Weekly_Points_of_Sale_Transactions_Report_28-Mar-2026.pdf"),
        _pos_report_url("Weekly_Points_of_Sale_Transactions_Report_21-Mar-2026.pdf"),
    ]
    assert payload.content["url"] == _page_url(POS_PAGE_LOCATOR)
    assert payload.content["content_type"] == "application/json"
    reports = cast(list[dict[str, str]], payload.content["body"]["reports"])
    assert reports[0]["report_text"] == f"report-pdf::{POS_PAGE_LOCATOR}"


@pytest.mark.asyncio
async def test_connect_error_does_not_use_standard_library_fallback() -> None:
    class ConnectingAsyncClient:
        async def get(
            self,
            url: str,
            *,
            follow_redirects: bool,
            timeout: httpx.Timeout,
        ) -> httpx.Response:
            raise httpx.ConnectError(
                "dns failed",
                request=httpx.Request("GET", url),
            )

    class RecordingConnector(SAMAConnector):
        def __init__(self) -> None:
            super().__init__(
                client=ConnectingAsyncClient(),
                request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=0),
            )
            self.used_fallback = False

        def _send_request_via_standard_library_sync(
            self,
            *,
            url: str,
            timeout_seconds: float,
            request: httpx.Request,
        ) -> httpx.Response:
            self.used_fallback = True
            raise AssertionError("fallback should not be used for connect errors")

    connector = RecordingConnector()

    with pytest.raises(SourceUnavailableError) as exc_info:
        await connector.fetch_dataset_payload(POS_PAGE_LOCATOR)

    assert exc_info.value.message == "SAMA source request failed"
    assert connector.used_fallback is False


@pytest.mark.asyncio
@respx.mock
async def test_timeout_maps_to_source_timeout_error() -> None:
    respx.get(_report_url()).mock(side_effect=httpx.ReadTimeout("timed out"))
    connector = SAMAConnector(request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=0))

    with pytest.raises(SourceTimeoutError) as exc_info:
        await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert exc_info.value.dataset_id == REPORT_LOCATOR
    assert exc_info.value.message == "SAMA source request timed out"
    assert REPORT_LOCATOR not in exc_info.value.message


@pytest.mark.asyncio
@respx.mock
async def test_transient_unavailable_failure_retries_then_succeeds() -> None:
    class RecordingConnector(SAMAConnector):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.backoff_delays: list[float] = []

        async def sleep_before_retry(self, retries_used: int) -> None:
            self.backoff_delays.append(self.retry_backoff_seconds(retries_used))

    route = respx.get(_report_url()).mock(
        side_effect=[
            httpx.Response(503, text="service unavailable"),
            httpx.Response(
                200,
                json={"rows": [{"period": "2026-01", "value": 1}]},
                headers={"content-type": "application/json"},
            ),
        ]
    )
    connector = RecordingConnector(
        request_policy=RequestPolicy(
            timeout_seconds=0.1,
            max_retries=1,
            retry_backoff_seconds=0.2,
        )
    )

    payload = await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert payload.content["body"] == {"rows": [{"period": "2026-01", "value": 1}]}
    assert route.call_count == 2
    assert connector.backoff_delays == [0.2]


@pytest.mark.asyncio
@respx.mock
async def test_retryable_http_429_retries_then_succeeds() -> None:
    route = respx.get(_report_url()).mock(
        side_effect=[
            httpx.Response(429, text="too many requests"),
            httpx.Response(
                200,
                json={"rows": [{"period": "2026-01", "value": 1}]},
                headers={"content-type": "application/json"},
            ),
        ]
    )
    connector = SAMAConnector(request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=1))

    payload = await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert payload.content["body"] == {"rows": [{"period": "2026-01", "value": 1}]}
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_retries_reuse_one_transient_client_per_fetch_call() -> None:
    class FakeAsyncClient:
        def __init__(self, responses: list[httpx.Response]) -> None:
            self._responses = iter(responses)
            self.get_call_count = 0
            self.closed = False

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            self.closed = True

        async def get(
            self,
            url: str,
            *,
            follow_redirects: bool,
            timeout: httpx.Timeout,
        ) -> httpx.Response:
            self.get_call_count += 1
            return next(self._responses)

    class RecordingConnector(SAMAConnector):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.backoff_delays: list[float] = []
            self.created_clients: list[FakeAsyncClient] = []

        def build_async_client(self) -> httpx.AsyncClient:
            client = FakeAsyncClient(
                [
                    httpx.Response(
                        503,
                        request=httpx.Request("GET", _report_url()),
                        text="service unavailable",
                    ),
                    httpx.Response(
                        200,
                        request=httpx.Request("GET", _report_url()),
                        json={"rows": [{"period": "2026-01", "value": 1}]},
                        headers={"content-type": "application/json"},
                    ),
                ]
            )
            self.created_clients.append(client)
            return cast(httpx.AsyncClient, client)

        async def sleep_before_retry(self, retries_used: int) -> None:
            self.backoff_delays.append(self.retry_backoff_seconds(retries_used))

    connector = RecordingConnector(
        request_policy=RequestPolicy(
            timeout_seconds=0.1,
            max_retries=1,
            retry_backoff_seconds=0.2,
        )
    )

    payload = await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert payload.content["body"] == {"rows": [{"period": "2026-01", "value": 1}]}
    assert connector.backoff_delays == [0.2]
    assert len(connector.created_clients) == 1
    assert connector.created_clients[0].get_call_count == 2
    assert connector.created_clients[0].closed is True


@pytest.mark.asyncio
@respx.mock
async def test_retry_budget_exhaustion_preserves_source_unavailable_error() -> None:
    route = respx.get(_report_url()).mock(
        side_effect=[
            httpx.Response(503, text="service unavailable"),
            httpx.Response(503, text="service unavailable"),
        ]
    )
    connector = SAMAConnector(request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=1))

    with pytest.raises(SourceUnavailableError) as exc_info:
        await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert exc_info.value.dataset_id == REPORT_LOCATOR
    assert exc_info.value.message == "SAMA source returned HTTP 503"
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_non_retryable_http_status_is_not_retried() -> None:
    route = respx.get(_report_url()).mock(
        side_effect=[
            httpx.Response(404, text="not found"),
            httpx.Response(
                200,
                json={"rows": [{"period": "2026-01", "value": 1}]},
                headers={"content-type": "application/json"},
            ),
        ]
    )
    connector = SAMAConnector(request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=1))

    with pytest.raises(SourceUnavailableError) as exc_info:
        await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert exc_info.value.message == "SAMA source returned HTTP 404"
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_invalid_source_response_is_not_retried() -> None:
    route = respx.get(_report_url()).mock(
        side_effect=[
            httpx.Response(
                200,
                text="not valid json",
                headers={"content-type": "application/json"},
            ),
            httpx.Response(
                200,
                json={"rows": [{"period": "2026-01", "value": 1}]},
                headers={"content-type": "application/json"},
            ),
        ]
    )
    connector = SAMAConnector(request_policy=RequestPolicy(timeout_seconds=0.1, max_retries=1))

    with pytest.raises(InvalidSourceResponseError):
        await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_unavailable_source_maps_to_source_unavailable_error() -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(503, text="service unavailable")
    )
    connector = SAMAConnector()

    with pytest.raises(SourceUnavailableError) as exc_info:
        await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert exc_info.value.dataset_id == REPORT_LOCATOR
    assert exc_info.value.message == "SAMA source returned HTTP 503"
    assert REPORT_LOCATOR not in exc_info.value.message


@pytest.mark.asyncio
@respx.mock
async def test_invalid_source_response_shape_maps_to_invalid_source_response_error() -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            text="not valid json",
            headers={"content-type": "application/json"},
        )
    )
    connector = SAMAConnector()

    with pytest.raises(InvalidSourceResponseError):
        await connector.fetch_dataset_payload(REPORT_LOCATOR)


@pytest.mark.asyncio
@respx.mock
async def test_snapshot_store_is_used_when_provided(tmp_path: Path) -> None:
    respx.get(_report_url()).mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"period": "2026-01", "value": 1}]},
            headers={"content-type": "application/json"},
        )
    )
    store = SnapshotStore(tmp_path)
    connector = SAMAConnector(snapshot_store=store)

    payload = await connector.fetch_dataset_payload(REPORT_LOCATOR)

    assert store.snapshot_exists("sama", REPORT_LOCATOR)
    assert store.read_snapshot("sama", REPORT_LOCATOR) == payload
