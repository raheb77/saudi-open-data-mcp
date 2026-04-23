"""Resolve source identifiers to configured connectors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from ..config import SourceConfig
from .base import Connector
from .data_gov_sa import DataGovSaConnector
from .errors import UnknownSourceError
from .mof import MoFConnector
from .sama import SAMAConnector
from .stats_gov_sa import StatsGovSaConnector


class _ConnectorFactory(Protocol):
    """Typed factory for the configured connector constructors."""

    def __call__(self, base_url: str) -> Connector: ...


@dataclass(frozen=True)
class _DefaultConnectorRegistration:
    """Static default connector registration for one current source family."""

    source: str
    base_url_field: str
    connector_type: _ConnectorFactory


_DEFAULT_CONNECTOR_REGISTRATIONS: tuple[_DefaultConnectorRegistration, ...] = (
    _DefaultConnectorRegistration(
        source="sama",
        base_url_field="sama_base_url",
        connector_type=SAMAConnector,
    ),
    _DefaultConnectorRegistration(
        source="data-gov-sa",
        base_url_field="data_gov_sa_base_url",
        connector_type=DataGovSaConnector,
    ),
    _DefaultConnectorRegistration(
        source="stats-gov-sa",
        base_url_field="stats_gov_sa_base_url",
        connector_type=StatsGovSaConnector,
    ),
    _DefaultConnectorRegistration(
        source="mof",
        base_url_field="mof_base_url",
        connector_type=MoFConnector,
    ),
)

DEFAULT_CONNECTOR_SOURCE_IDS: tuple[str, ...] = tuple(
    registration.source for registration in _DEFAULT_CONNECTOR_REGISTRATIONS
)


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
    source_config: SourceConfig,
) -> SourceConnectorResolver:
    """Build the current source-to-connector resolver for live preview access."""

    return SourceConnectorResolver(
        {
            registration.source: registration.connector_type(
                getattr(source_config, registration.base_url_field)
            )
            for registration in _DEFAULT_CONNECTOR_REGISTRATIONS
        }
    )
