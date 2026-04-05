"""Unit tests for the Ministry of Finance connector."""

from __future__ import annotations

from typing import cast

import httpx
import pytest
import respx

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.errors import SourceAccessPolicyViolationError
from saudi_open_data_mcp.connectors.mof import MoFConnector

SOURCE_LOCATOR = "/en/financialreport/2025/Pages/default.aspx"


def _reports_page_url() -> str:
    return f"https://www.mof.gov.sa{SOURCE_LOCATOR}"


def _report_url(name: str) -> str:
    return f"https://www.mof.gov.sa/en/financialreport/2025/Documents/{name}"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_dataset_payload_returns_raw_payload_for_approved_reports_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    respx.get(_reports_page_url()).mock(
        return_value=httpx.Response(
            200,
            text="""
                <html><body>
                  <a href="/en/financialreport/2025/Documents/Q1E%202025-%20Final.pdf">Q1</a>
                  <a
                    href="/en/financialreport/2025/Documents/infoE%20Q1-2025%20En%20Final.pdf"
                  >info q1</a>
                  <a href="/en/financialreport/2025/Documents/Q2E%202025-%20Final.pdf">Q2</a>
                  <a
                    href="/en/financialreport/2025/Documents/info%20En%20Q2-2025%20Final.pdf"
                  >info q2</a>
                  <a href="/en/financialreport/2025/Documents/Mid-Bud-E2025.pdf">midyear</a>
                </body></html>
            """,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get(_report_url("Q1E%202025-%20Final.pdf")).mock(
        return_value=httpx.Response(
            200,
            content=b"q1-pdf",
            headers={"content-type": "application/pdf"},
        )
    )
    respx.get(_report_url("Q2E%202025-%20Final.pdf")).mock(
        return_value=httpx.Response(
            200,
            content=b"q2-pdf",
            headers={"content-type": "application/pdf"},
        )
    )

    connector = MoFConnector()

    def _fake_extract_pdf_text(pdf_bytes: bytes, *, dataset_id: str) -> str:
        return pdf_bytes.decode("utf-8") + f"::{dataset_id}"

    monkeypatch.setattr(connector, "_extract_pdf_text", staticmethod(_fake_extract_pdf_text))

    payload = await connector.fetch_dataset_payload(SOURCE_LOCATOR)

    assert isinstance(payload, RawPayload)
    assert payload.source == "mof"
    assert payload.dataset_id == SOURCE_LOCATOR
    assert payload.content["content_type"] == "application/json"
    reports = cast(list[dict[str, str]], payload.content["body"]["reports"])
    assert [report["report_url"] for report in reports] == [
        _report_url("Q1E%202025-%20Final.pdf"),
        _report_url("Q2E%202025-%20Final.pdf"),
    ]
    assert reports[0]["report_text"] == f"q1-pdf::{SOURCE_LOCATOR}"
    assert reports[1]["report_text"] == f"q2-pdf::{SOURCE_LOCATOR}"


@pytest.mark.asyncio
async def test_unapproved_host_is_rejected() -> None:
    connector = MoFConnector()

    with pytest.raises(SourceAccessPolicyViolationError):
        await connector.fetch_dataset_payload(
            "https://example.com/en/financialreport/2025/Pages/default.aspx"
        )


@pytest.mark.asyncio
async def test_unapproved_path_is_rejected() -> None:
    connector = MoFConnector()

    with pytest.raises(SourceAccessPolicyViolationError):
        await connector.fetch_dataset_payload("/en/budget")
