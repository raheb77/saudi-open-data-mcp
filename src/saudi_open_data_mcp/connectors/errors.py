"""Connector error taxonomy."""


class ConnectorError(Exception):
    """Base connector error."""

    def __init__(
        self,
        *,
        source_name: str,
        message: str,
        dataset_id: str | None = None,
    ) -> None:
        self.source_name = source_name
        self.dataset_id = dataset_id
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        context = [f"source={self.source_name}"]
        if self.dataset_id is not None:
            context.append(f"dataset_id={self.dataset_id}")
        return f"{self.message} ({', '.join(context)})"


class ConnectorConfigurationError(ConnectorError):
    """Raised when connector configuration is invalid."""


class ConnectorNotImplementedError(ConnectorError):
    """Raised when a scaffold connector is invoked."""


class UnknownSourceError(ConnectorError):
    """Raised when no connector is registered for a requested source."""


class SourceUnavailableError(ConnectorError):
    """Raised when an approved source is unavailable."""


class SourceTimeoutError(ConnectorError):
    """Raised when source access exceeds the configured timeout."""


class InvalidSourceResponseError(ConnectorError):
    """Raised when a source response shape does not match expectations."""


class SourceAccessPolicyViolationError(ConnectorError):
    """Raised when a connector attempts to access an unapproved source."""
