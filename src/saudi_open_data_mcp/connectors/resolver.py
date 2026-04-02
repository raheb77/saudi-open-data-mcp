"""Resolve source identifiers to configured connectors."""

from __future__ import annotations

from collections.abc import Mapping

from .base import Connector
from .data_gov_sa import DataGovSaConnector
from .errors import UnknownSourceError
from .sama import SAMAConnector


class SourceConnectorResolver:
    """Small source-to-connector resolver for live source access seams."""

    def __init__(self, connectors: Mapping[str, Connector]) -> None:
        self._connectors = {
            source_name.strip(): connector
            for source_name, connector in connectors.items()
        }

    def resolve(self, source: str) -> Connector:
        """Return the configured connector for a registry descriptor source."""

        normalized_source = source.strip()
        connector = self._connectors.get(normalized_source)
        if connector is None:
            raise UnknownSourceError(
                source_name=normalized_source,
                message=f"No connector configured for source '{source}'",
            )
        return connector


def build_default_connector_resolver(
    *,
    sama_base_url: str,
    data_gov_sa_base_url: str,
) -> SourceConnectorResolver:
    """Build the current source-to-connector resolver for live preview access."""

    return SourceConnectorResolver(
        {
            "sama": SAMAConnector(base_url=sama_base_url),
            "data-gov-sa": DataGovSaConnector(base_url=data_gov_sa_base_url),
        }
    )
