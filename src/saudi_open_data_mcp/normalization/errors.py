"""Normalization-specific error types."""


class UnknownNormalizationSourceError(ValueError):
    """Raised when no normalization implementation is registered for a source."""


class ExtractedValueValidationError(ValueError):
    """Raised when extracted source values fail explicit sanity checks."""

    def __init__(self, *, limitation_code: str, message: str) -> None:
        super().__init__(message)
        self.limitation_code = limitation_code
