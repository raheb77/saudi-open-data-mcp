"""Connector abstractions."""

from .base import Connector, RawPayload
from .errors import ConnectorConfigurationError, ConnectorNotImplementedError
from .sama import SAMAConnector

__all__ = [
    "Connector",
    "ConnectorConfigurationError",
    "ConnectorNotImplementedError",
    "RawPayload",
    "SAMAConnector",
]
