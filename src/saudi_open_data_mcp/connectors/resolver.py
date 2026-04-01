"""Resolve source identifiers to configured connectors."""

from __future__ import annotations

from collections.abc import Mapping

from .base import Connector
from .errors import UnknownSourceError


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
