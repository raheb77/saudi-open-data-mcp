"""Connector abstractions."""

from .base import Connector, RawPayload
from .data_gov_sa import DataGovSaConnector
from .errors import (
    ConnectorConfigurationError,
    ConnectorNotImplementedError,
    UnknownSourceError,
)
from .resolver import SourceConnectorResolver, build_default_connector_resolver
from .sama import SAMAConnector
from .stats_gov_sa import StatsGovSaConnector

__all__ = [
    "Connector",
    "ConnectorConfigurationError",
    "ConnectorNotImplementedError",
    "DataGovSaConnector",
    "RawPayload",
    "SAMAConnector",
    "SourceConnectorResolver",
    "StatsGovSaConnector",
    "UnknownSourceError",
    "build_default_connector_resolver",
]
