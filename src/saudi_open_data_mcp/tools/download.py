"""Typed local artifact lookup over registry metadata and snapshot storage."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from saudi_open_data_mcp.registry.models import DatasetDescriptor, NonEmptyText
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.security.sanitization import sanitize_dataset_id
from saudi_open_data_mcp.storage.freshness import (
    SnapshotFreshnessResult,
    SnapshotFreshnessStatus,
    evaluate_snapshot_freshness,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore


class DatasetDownloadStatus(StrEnum):
    """Local artifact availability state for a dataset."""

    MISSING = "missing"
    ARTIFACT_MISSING = "artifact_missing"
    AVAILABLE = "available"


class DatasetDownloadReason(StrEnum):
    """Explicit reason for the current local artifact state."""

    DATASET_NOT_IN_REGISTRY = "dataset_not_in_registry"
    NO_LOCAL_SNAPSHOT = "no_local_snapshot"
    LOCAL_SNAPSHOT_AVAILABLE = "local_snapshot_available"


class DatasetDownloadResult(BaseModel):
    """Typed local artifact lookup result."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: NonEmptyText
    status: DatasetDownloadStatus
    reason: DatasetDownloadReason
    local_snapshot_exists: bool
    source: NonEmptyText | None = None
    freshness: SnapshotFreshnessResult | None = None

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        if self.status is DatasetDownloadStatus.MISSING:
            if self.reason is not DatasetDownloadReason.DATASET_NOT_IN_REGISTRY:
                raise ValueError("missing results require dataset_not_in_registry")
            if self.local_snapshot_exists:
                raise ValueError("missing results must not claim a local snapshot")
            if self.source is not None or self.freshness is not None:
                raise ValueError("missing results must not include source or freshness")
            return self

        if self.source is None or self.freshness is None:
            raise ValueError("known dataset download results must include source and freshness")

        if self.freshness.dataset_id != self.dataset_id:
            raise ValueError("freshness.dataset_id must match dataset_id")
        if self.freshness.source != self.source:
            raise ValueError("freshness.source must match source")
        if self.freshness.artifact_present != self.local_snapshot_exists:
            raise ValueError("freshness.artifact_present must match local_snapshot_exists")

        if self.status is DatasetDownloadStatus.ARTIFACT_MISSING:
            if self.reason is not DatasetDownloadReason.NO_LOCAL_SNAPSHOT:
                raise ValueError("artifact_missing results require no_local_snapshot reason")
            if self.local_snapshot_exists:
                raise ValueError("artifact_missing results must not claim a local snapshot")
            if self.freshness.status is not SnapshotFreshnessStatus.MISSING:
                raise ValueError("artifact_missing results require missing freshness evidence")
            if self.freshness.artifact_present:
                raise ValueError(
                    "artifact_missing results must not claim freshness artifact evidence"
                )
            return self

        if self.reason is not DatasetDownloadReason.LOCAL_SNAPSHOT_AVAILABLE:
            raise ValueError("available results require local_snapshot_available reason")
        if not self.local_snapshot_exists:
            raise ValueError("available results must claim a local snapshot")
        if self.freshness.status is SnapshotFreshnessStatus.MISSING:
            raise ValueError("available results must not carry missing freshness evidence")
        if not self.freshness.artifact_present:
            raise ValueError("available results must carry positive freshness artifact evidence")
        return self

    @classmethod
    def missing(cls, dataset_id: str) -> Self:
        """Build an explicit missing result for an unknown dataset."""

        return cls(
            dataset_id=dataset_id,
            status=DatasetDownloadStatus.MISSING,
            reason=DatasetDownloadReason.DATASET_NOT_IN_REGISTRY,
            local_snapshot_exists=False,
        )

    @classmethod
    def artifact_missing(
        cls,
        descriptor: DatasetDescriptor,
        freshness: SnapshotFreshnessResult,
    ) -> Self:
        """Build a typed result for a known dataset without a local artifact."""

        return cls(
            dataset_id=descriptor.dataset_id,
            status=DatasetDownloadStatus.ARTIFACT_MISSING,
            reason=DatasetDownloadReason.NO_LOCAL_SNAPSHOT,
            local_snapshot_exists=False,
            source=descriptor.source,
            freshness=freshness,
        )

    @classmethod
    def available(
        cls,
        descriptor: DatasetDescriptor,
        freshness: SnapshotFreshnessResult,
    ) -> Self:
        """Build a typed result for a known dataset with a local artifact."""

        return cls(
            dataset_id=descriptor.dataset_id,
            status=DatasetDownloadStatus.AVAILABLE,
            reason=DatasetDownloadReason.LOCAL_SNAPSHOT_AVAILABLE,
            local_snapshot_exists=True,
            source=descriptor.source,
            freshness=freshness,
        )


class DatasetDownloadTool:
    """Local artifact lookup layer over the registry and snapshot storage."""

    def __init__(
        self,
        repository: RegistryRepository,
        snapshot_store: SnapshotStore | Path,
    ) -> None:
        self._repository = repository
        self._snapshot_store = (
            snapshot_store
            if isinstance(snapshot_store, SnapshotStore)
            else SnapshotStore(snapshot_store)
        )

    def get_dataset_download(
        self,
        dataset_id: str,
        *,
        reference_time: datetime | None = None,
    ) -> DatasetDownloadResult:
        """Return local artifact state for an exact registry dataset identifier."""

        normalized_dataset_id = sanitize_dataset_id(dataset_id)
        descriptor = self._repository.get_dataset(normalized_dataset_id)
        if descriptor is None:
            return DatasetDownloadResult.missing(normalized_dataset_id)

        freshness = evaluate_snapshot_freshness(
            source=descriptor.source,
            dataset_id=descriptor.source_locator,
            snapshot_store=self._snapshot_store,
            reference_time=reference_time,
            update_frequency=descriptor.update_frequency,
        )
        freshness = _bind_canonical_dataset_id(
            descriptor=descriptor,
            freshness=freshness,
        )

        if freshness.status is SnapshotFreshnessStatus.MISSING:
            return DatasetDownloadResult.artifact_missing(descriptor, freshness)

        return DatasetDownloadResult.available(descriptor, freshness)


def _bind_canonical_dataset_id(
    *,
    descriptor: DatasetDescriptor,
    freshness: SnapshotFreshnessResult,
) -> SnapshotFreshnessResult:
    """Rewrite source-locator-based freshness output to the canonical dataset identity."""

    return freshness.model_copy(update={"dataset_id": descriptor.dataset_id})
