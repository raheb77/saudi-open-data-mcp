"""Unit tests for the stats.gov.sa connector."""

from __future__ import annotations

import httpx
import pytest
import respx

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.connectors.errors import SourceAccessPolicyViolationError
from saudi_open_data_mcp.connectors.stats_gov_sa import StatsGovSaConnector

INFLATION_NEWS_LOCATOR = "/en/news?q=inflation&delta=20&start=0"
GDP_NEWS_LOCATOR = "/en/news?q=gdp&delta=20&start=0"
LABOR_NEWS_LOCATOR = "/en/news?q=unemployment&delta=20&start=0"


def _news_url() -> str:
    return f"https://www.stats.gov.sa{INFLATION_NEWS_LOCATOR}"


def _gdp_news_url() -> str:
    return f"https://www.stats.gov.sa{GDP_NEWS_LOCATOR}"


def _labor_news_url() -> str:
    return f"https://www.stats.gov.sa{LABOR_NEWS_LOCATOR}"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_dataset_payload_returns_raw_payload_for_approved_inflation_news_route(
) -> None:
    route = respx.get(_news_url()).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official stats inflation news</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    connector = StatsGovSaConnector()

    payload = await connector.fetch_dataset_payload(INFLATION_NEWS_LOCATOR)

    assert route.called
    assert isinstance(payload, RawPayload)
    assert payload.source == "stats-gov-sa"
    assert payload.dataset_id == INFLATION_NEWS_LOCATOR
    assert payload.content["url"] == _news_url()
    assert payload.content["content_type"] == "text/html"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_dataset_payload_returns_raw_payload_for_approved_gdp_news_route() -> None:
    route = respx.get(_gdp_news_url()).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official stats gdp news</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    connector = StatsGovSaConnector()

    payload = await connector.fetch_dataset_payload(GDP_NEWS_LOCATOR)

    assert route.called
    assert isinstance(payload, RawPayload)
    assert payload.source == "stats-gov-sa"
    assert payload.dataset_id == GDP_NEWS_LOCATOR
    assert payload.content["url"] == _gdp_news_url()
    assert payload.content["content_type"] == "text/html"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_dataset_payload_returns_raw_payload_for_approved_labor_news_route() -> None:
    route = respx.get(_labor_news_url()).mock(
        return_value=httpx.Response(
            200,
            text="<html><body>official stats labor news</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    connector = StatsGovSaConnector()

    payload = await connector.fetch_dataset_payload(LABOR_NEWS_LOCATOR)

    assert route.called
    assert isinstance(payload, RawPayload)
    assert payload.source == "stats-gov-sa"
    assert payload.dataset_id == LABOR_NEWS_LOCATOR
    assert payload.content["url"] == _labor_news_url()
    assert payload.content["content_type"] == "text/html"


@pytest.mark.asyncio
async def test_unapproved_host_is_rejected() -> None:
    connector = StatsGovSaConnector()

    with pytest.raises(SourceAccessPolicyViolationError):
        await connector.fetch_dataset_payload("https://example.com/en/news?q=inflation")


@pytest.mark.asyncio
async def test_unapproved_stats_gov_sa_news_query_is_rejected() -> None:
    connector = StatsGovSaConnector()

    with pytest.raises(SourceAccessPolicyViolationError):
        await connector.fetch_dataset_payload("/en/news?q=housing&delta=20&start=0")


@pytest.mark.asyncio
async def test_unapproved_path_is_rejected() -> None:
    connector = StatsGovSaConnector()

    with pytest.raises(SourceAccessPolicyViolationError):
        await connector.fetch_dataset_payload("/en/w/cpi-1")
