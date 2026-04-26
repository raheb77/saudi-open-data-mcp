"""Shared raw payload contracts for connectors, storage, and normalization."""

from __future__ import annotations

from typing import Any, Protocol, Self

from pydantic import BaseModel, Field, model_validator


class SnapshotMetadata(BaseModel):
    """Versioned snapshot metadata persisted alongside raw payload content."""

    storage_schema_version: int = Field(default=1, ge=0)
    raw_format_id: str | None = None
    raw_format_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validate_format_version_pairing(self) -> Self:
        if (self.raw_format_id is None) != (self.raw_format_version is None):
            raise ValueError(
                "snapshot raw_format_id and raw_format_version must be set together"
            )
        return self


class RawPayload(BaseModel):
    """Typed raw connector output."""

    source: str
    dataset_id: str
    content: dict[str, Any] = Field(default_factory=dict)
    snapshot_metadata: SnapshotMetadata | None = None


class RawPayloadSnapshotWriter(Protocol):
    """Minimal protocol for optional raw payload snapshot persistence."""

    def write_snapshot(self, payload: RawPayload) -> object:
        """Persist a raw payload snapshot."""
