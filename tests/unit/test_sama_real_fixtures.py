"""Regression tests backed by real recorded SAMA fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.sama import SAMAConnector
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationPipeline,
    NormalizationPipelineStatus,
)

POS_PAGE_LOCATOR = "/en-US/Indices/Pages/POS.aspx"
EXCHANGE_RATES_PAGE_LOCATOR = "/en-US/FinExc/Pages/Currency.aspx"
REPO_RATE_PAGE_LOCATOR = "/en-US/MonetaryOperations/Pages/OfficialRepoRate.aspx"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "sama"
POS_FIXTURES_DIR = FIXTURES_DIR / "pos_weekly"
EXCHANGE_RATES_FIXTURES_DIR = FIXTURES_DIR / "exchange_rates_current"
REPO_RATE_FIXTURES_DIR = FIXTURES_DIR / "repo_rate"


def _fixture_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _fixture_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _exchange_rates_bundle_fixture() -> dict[str, object]:
    return json.loads(
        _fixture_text(
            EXCHANGE_RATES_FIXTURES_DIR / "exchange-rates-current-2026-04-12-bundle.json"
        )
    )


def _page_url(locator: str) -> str:
    return f"https://www.sama.gov.sa{locator}"


def _records_by_field(records, field_name: str) -> dict[str, dict[str, object]]:
    return {record.fields[field_name]: record.fields for record in records}


@pytest.mark.asyncio
@respx.mock
async def test_real_pos_pdf_fixtures_round_trip_to_known_good_canonical_rows() -> None:
    report_21_mar_url = (
        "https://www.sama.gov.sa/en-US/Indices/POS_EN/"
        "Weekly_Points_of_Sale_Transactions_Report_21-Mar-2026.pdf"
    )
    report_04_apr_url = (
        "https://www.sama.gov.sa/en-US/Indices/POS_EN/"
        "Weekly_Points_of_Sale_Transactions_Report_04-Apr-2026.pdf"
    )
    respx.get(_page_url(POS_PAGE_LOCATOR)).mock(
        return_value=httpx.Response(
            200,
            text=(
                "<html><body>"
                f'<a href="{report_04_apr_url}">04 Apr</a>'
                f'<a href="{report_21_mar_url}">21 Mar</a>'
                "</body></html>"
            ),
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get(report_21_mar_url).mock(
        return_value=httpx.Response(
            200,
            content=_fixture_bytes(
                POS_FIXTURES_DIR / "Weekly_Points_of_Sale_Transactions_Report_21-Mar-2026.pdf"
            ),
            headers={"content-type": "application/pdf"},
        )
    )
    respx.get(report_04_apr_url).mock(
        return_value=httpx.Response(
            200,
            content=_fixture_bytes(
                POS_FIXTURES_DIR / "Weekly_Points_of_Sale_Transactions_Report_04-Apr-2026.pdf"
            ),
            headers={"content-type": "application/pdf"},
        )
    )
    connector = SAMAConnector()

    payload = await connector.fetch_dataset_payload(POS_PAGE_LOCATOR)
    assert "Total 210,534 14,533,498" in payload.content["body"]["reports"][1]["report_text"]
    assert "Total 226,928 16,149,247" in payload.content["body"]["reports"][0]["report_text"]

    result = NormalizationPipeline().normalize(
        payload,
        canonical_dataset_id="sama-pos-weekly",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert len(result.records) == 6
    rows_by_period = {
        (record.fields["week_start_date"], record.fields["week_end_date"]): record.fields
        for record in result.records
    }

    # Manually verified from the real 21-Mar-2026 report Total row:
    # "Total 210,534 14,533,498 ..."
    assert rows_by_period[("2026-02-22", "2026-02-28")] == {
        "week_start_date": "2026-02-22",
        "week_end_date": "2026-02-28",
        "transaction_count": 210534000,
        "transaction_value_sar": 14533498000.0,
        "average_ticket_sar": 69.03,
        "source_locator": POS_PAGE_LOCATOR,
        "source_url": _page_url(POS_PAGE_LOCATOR),
        "source_period_text": "22 Feb,26 - 28 Feb,26",
        "source_table_title": "Table 1: By Activities",
        "source_report_url": report_21_mar_url,
        "source_release_title": "Weekly Points of Sale Transactions",
    }
    # Manually verified from the real 04-Apr-2026 report Total row:
    # "... 246,506 14,707,441 ..."
    assert rows_by_period[("2026-03-29", "2026-04-04")] == {
        "week_start_date": "2026-03-29",
        "week_end_date": "2026-04-04",
        "transaction_count": 246506000,
        "transaction_value_sar": 14707441000.0,
        "average_ticket_sar": 59.66,
        "source_locator": POS_PAGE_LOCATOR,
        "source_url": _page_url(POS_PAGE_LOCATOR),
        "source_period_text": "29 Mar,26 - 04 Apr,26",
        "source_table_title": "Table 1: By Activities",
        "source_report_url": report_04_apr_url,
        "source_release_title": "Weekly Points of Sale Transactions",
    }


def test_real_exchange_rates_page_one_fixture_exposes_expected_page_state() -> None:
    connector = SAMAConnector()
    page_one_html = _fixture_text(
        EXCHANGE_RATES_FIXTURES_DIR / "exchange-rates-current-2026-04-12-page-1.html"
    )

    state = connector._extract_exchange_rates_page_state(
        html=page_one_html,
        page_url=_page_url(EXCHANGE_RATES_PAGE_LOCATOR),
        dataset_locator=EXCHANGE_RATES_PAGE_LOCATOR,
    )

    assert state.form_state.action_url == _page_url(EXCHANGE_RATES_PAGE_LOCATOR)
    assert state.form_state.currency_all_value == "-1"
    assert "ddlCurrencies" in state.form_state.currency_field_name
    assert "txtDatePicker" in state.form_state.date_field_name
    assert "btnSearch" in state.form_state.search_button_name
    assert state.latest_date_text == "12/04/2026"
    assert state.row_date_texts == ("12/04/2026",) * 10
    assert state.total_results_count == 73
    assert state.page_row_count == 10
    assert state.pager_targets["2"] == (
        "ctl00$ctl50$g_b855f717_2242_4bec_96ce_cdebc8416f16$ctl00$dgResults$ctl14$ctl01"
    )


def test_real_exchange_rates_bundle_fixture_normalizes_to_known_good_rows() -> None:
    bundle_fixture = _exchange_rates_bundle_fixture()
    raw_payload = RawPayload(
        source="sama",
        dataset_id=EXCHANGE_RATES_PAGE_LOCATOR,
        content={
            "url": _page_url(EXCHANGE_RATES_PAGE_LOCATOR),
            "status_code": 200,
            "content_type": "application/json",
            "body": bundle_fixture,
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="sama-exchange-rates-current",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert len(result.records) == 73
    records_by_code = _records_by_field(result.records, "currency_code")

    # Manually verified against the recorded 12/04/2026 exchange-rates pages.
    assert records_by_code["USD"] == {
        "as_of_date": "2026-04-12",
        "currency_code": "USD",
        "currency_name": "US DOLLAR",
        "quote_currency_code": "SAR",
        "quote_currency_name": "Saudi Riyal",
        "closing_rate_sar": 3.75,
        "source_locator": EXCHANGE_RATES_PAGE_LOCATOR,
        "source_url": _page_url(EXCHANGE_RATES_PAGE_LOCATOR),
        "source_currency_text": "US DOLLAR",
        "source_last_updated_date_text": "12/04/2026",
        "source_page_number": 1,
    }
    assert records_by_code["EUR"] == {
        "as_of_date": "2026-04-12",
        "currency_code": "EUR",
        "currency_name": "EURO",
        "quote_currency_code": "SAR",
        "quote_currency_name": "Saudi Riyal",
        "closing_rate_sar": 4.39818,
        "source_locator": EXCHANGE_RATES_PAGE_LOCATOR,
        "source_url": _page_url(EXCHANGE_RATES_PAGE_LOCATOR),
        "source_currency_text": "EURO",
        "source_last_updated_date_text": "12/04/2026",
        "source_page_number": 1,
    }
    assert records_by_code["AED"] == {
        "as_of_date": "2026-04-12",
        "currency_code": "AED",
        "currency_name": "UAE DIRHAM",
        "quote_currency_code": "SAR",
        "quote_currency_name": "Saudi Riyal",
        "closing_rate_sar": 1.02088,
        "source_locator": EXCHANGE_RATES_PAGE_LOCATOR,
        "source_url": _page_url(EXCHANGE_RATES_PAGE_LOCATOR),
        "source_currency_text": "UAE DIRHAM",
        "source_last_updated_date_text": "12/04/2026",
        "source_page_number": 1,
    }
    assert records_by_code["JPY"] == {
        "as_of_date": "2026-04-12",
        "currency_code": "JPY",
        "currency_name": "JAPANESE YEN",
        "quote_currency_code": "SAR",
        "quote_currency_name": "Saudi Riyal",
        "closing_rate_sar": 0.02356,
        "source_locator": EXCHANGE_RATES_PAGE_LOCATOR,
        "source_url": _page_url(EXCHANGE_RATES_PAGE_LOCATOR),
        "source_currency_text": "JAPANESE YEN",
        "source_last_updated_date_text": "12/04/2026",
        "source_page_number": 2,
    }


def test_real_repo_rate_fixture_normalizes_to_known_good_policy_rate_rows() -> None:
    raw_payload = RawPayload(
        source="sama",
        dataset_id=REPO_RATE_PAGE_LOCATOR,
        content={
            "url": _page_url(REPO_RATE_PAGE_LOCATOR),
            "status_code": 200,
            "content_type": "text/html",
            "body": _fixture_text(
                REPO_RATE_FIXTURES_DIR / "official-repo-rate-page.html"
            ),
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="sama-repo-rate",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert len(result.records) == 15
    records_by_effective_date = _records_by_field(result.records, "effective_date")

    # Manually verified against the recorded "Official Repo Rate" SharePoint table.
    # The canonical effective_date intentionally derives from the source Publish Date.
    assert records_by_effective_date["2025-12-10"] == {
        "effective_date": "2025-12-10",
        "policy_rate_code": "repo_rate",
        "policy_rate_name": "Official Repo Rate",
        "rate_percent": 4.25,
        "source_locator": REPO_RATE_PAGE_LOCATOR,
        "source_url": _page_url(REPO_RATE_PAGE_LOCATOR),
        "source_publish_date_text": "10/12/2025",
        "source_rate_text": "4.25",
        "source_change_points_text": "-25",
    }
    assert records_by_effective_date["2024-09-18"] == {
        "effective_date": "2024-09-18",
        "policy_rate_code": "repo_rate",
        "policy_rate_name": "Official Repo Rate",
        "rate_percent": 5.5,
        "source_locator": REPO_RATE_PAGE_LOCATOR,
        "source_url": _page_url(REPO_RATE_PAGE_LOCATOR),
        "source_publish_date_text": "18/09/2024",
        "source_rate_text": "5.5",
        "source_change_points_text": "-50",
    }
    assert records_by_effective_date["2022-06-15"] == {
        "effective_date": "2022-06-15",
        "policy_rate_code": "repo_rate",
        "policy_rate_name": "Official Repo Rate",
        "rate_percent": 2.25,
        "source_locator": REPO_RATE_PAGE_LOCATOR,
        "source_url": _page_url(REPO_RATE_PAGE_LOCATOR),
        "source_publish_date_text": "15/06/2022",
        "source_rate_text": "2.25",
        "source_change_points_text": "50",
    }
