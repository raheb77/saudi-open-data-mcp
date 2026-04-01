"""Unit tests for source-to-connector resolution."""

from saudi_open_data_mcp.connectors.data_gov_sa import DataGovSaConnector
from saudi_open_data_mcp.connectors.resolver import build_default_connector_resolver
from saudi_open_data_mcp.connectors.sama import SAMAConnector


def test_default_connector_resolver_registers_current_sources() -> None:
    resolver = build_default_connector_resolver(sama_base_url="https://www.sama.gov.sa")

    assert isinstance(resolver.resolve("sama"), SAMAConnector)
    assert isinstance(resolver.resolve("data-gov-sa"), DataGovSaConnector)
