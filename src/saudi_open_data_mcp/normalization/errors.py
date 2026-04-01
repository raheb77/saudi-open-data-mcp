"""Normalization-specific error types."""


class UnknownNormalizationSourceError(ValueError):
    """Raised when no normalization implementation is registered for a source."""
