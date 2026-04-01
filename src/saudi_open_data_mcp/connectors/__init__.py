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

__all__ = [
    "Connector",
    "ConnectorConfigurationError",
    "ConnectorNotImplementedError",
    "DataGovSaConnector",
    "RawPayload",
    "SAMAConnector",
    "SourceConnectorResolver",
    "UnknownSourceError",
    "build_default_connector_resolver",
]
