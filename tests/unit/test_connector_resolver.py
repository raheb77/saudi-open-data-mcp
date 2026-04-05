"""Unit tests for source-to-connector resolution."""

from saudi_open_data_mcp.connectors.data_gov_sa import DataGovSaConnector
from saudi_open_data_mcp.connectors.mof import MoFConnector
from saudi_open_data_mcp.connectors.resolver import build_default_connector_resolver
from saudi_open_data_mcp.connectors.sama import SAMAConnector
from saudi_open_data_mcp.connectors.stats_gov_sa import StatsGovSaConnector


def test_default_connector_resolver_registers_current_sources() -> None:
    resolver = build_default_connector_resolver(
        sama_base_url="https://www.sama.gov.sa",
        data_gov_sa_base_url="https://open.data.gov.sa",
        stats_gov_sa_base_url="https://www.stats.gov.sa",
        mof_base_url="https://www.mof.gov.sa",
    )

    sama_connector = resolver.resolve("sama")
    data_gov_sa_connector = resolver.resolve("data-gov-sa")
    stats_gov_sa_connector = resolver.resolve("stats-gov-sa")
    mof_connector = resolver.resolve("mof")

    assert isinstance(sama_connector, SAMAConnector)
    assert sama_connector.approved_base_url == "https://www.sama.gov.sa"
    assert isinstance(data_gov_sa_connector, DataGovSaConnector)
    assert data_gov_sa_connector.approved_base_url == "https://open.data.gov.sa"
    assert isinstance(stats_gov_sa_connector, StatsGovSaConnector)
    assert stats_gov_sa_connector.approved_base_url == "https://www.stats.gov.sa"
    assert isinstance(mof_connector, MoFConnector)
    assert mof_connector.approved_base_url == "https://www.mof.gov.sa"
