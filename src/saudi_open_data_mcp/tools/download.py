"""Typed local artifact lookup over registry metadata and snapshot storage."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from saudi_open_data_mcp.observability import log_audit_event
from saudi_open_data_mcp.registry.models import DatasetDescriptor, NonEmptyText
from saudi_open_data_mcp.registry.repository import RegistryRepository
from saudi_open_data_mcp.security.sanitization import sanitize_dataset_id
from saudi_open_data_mcp.storage.freshness import (
    SnapshotFreshnessResult,
    SnapshotFreshnessStatus,
    evaluate_snapshot_freshness,
)
from saudi_open_data_mcp.storage.snapshots import SnapshotStore
from saudi_open_data_mcp.tools.result_metadata import ResultDataOrigin


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
    data_origin: ResultDataOrigin | None = None
    freshness_status: SnapshotFreshnessStatus | None = None
    freshness: SnapshotFreshnessResult | None = None

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        if self.status is DatasetDownloadStatus.MISSING:
            if self.reason is not DatasetDownloadReason.DATASET_NOT_IN_REGISTRY:
                raise ValueError("missing results require dataset_not_in_registry")
            if self.local_snapshot_exists:
                raise ValueError("missing results must not claim a local snapshot")
            if (
                self.source is not None
                or self.data_origin is not None
                or self.freshness_status is not None
                or self.freshness is not None
            ):
                raise ValueError(
                    "missing results must not include source, data_origin, freshness_status, "
                    "or freshness"
                )
            return self

        if self.source is None or self.freshness is None or self.freshness_status is None:
            raise ValueError(
                "known dataset download results must include source, freshness_status, "
                "and freshness"
            )

        if self.freshness.dataset_id != self.dataset_id:
            raise ValueError("freshness.dataset_id must match dataset_id")
        if self.freshness.source != self.source:
            raise ValueError("freshness.source must match source")
        if self.freshness_status is not self.freshness.status:
            raise ValueError("freshness_status must match freshness.status")
        if self.freshness.artifact_present != self.local_snapshot_exists:
            raise ValueError("freshness.artifact_present must match local_snapshot_exists")

        if self.status is DatasetDownloadStatus.ARTIFACT_MISSING:
            if self.reason is not DatasetDownloadReason.NO_LOCAL_SNAPSHOT:
                raise ValueError("artifact_missing results require no_local_snapshot reason")
            if self.local_snapshot_exists:
                raise ValueError("artifact_missing results must not claim a local snapshot")
            if self.data_origin is not None:
                raise ValueError("artifact_missing results must not include data_origin")
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
        if self.data_origin is not ResultDataOrigin.LOCAL_SNAPSHOT:
            raise ValueError("available results must expose local_snapshot data_origin")
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
            freshness_status=freshness.status,
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
            data_origin=ResultDataOrigin.LOCAL_SNAPSHOT,
            freshness_status=freshness.status,
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
            result = DatasetDownloadResult.missing(normalized_dataset_id)
            _audit_download_result(result)
            return result

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
            result = DatasetDownloadResult.artifact_missing(descriptor, freshness)
            _audit_download_result(result)
            return result

        result = DatasetDownloadResult.available(descriptor, freshness)
        _audit_download_result(result)
        return result


def _bind_canonical_dataset_id(
    *,
    descriptor: DatasetDescriptor,
    freshness: SnapshotFreshnessResult,
) -> SnapshotFreshnessResult:
    """Rewrite source-locator-based freshness output to the canonical dataset identity."""

    return freshness.model_copy(update={"dataset_id": descriptor.dataset_id})


def _audit_download_result(result: DatasetDownloadResult) -> None:
    """Emit one audit event for local artifact availability lookup."""

    log_audit_event(
        "download_dataset",
        result_status=result.status.value,
        dataset_id=result.dataset_id,
        source=result.source,
        data_origin=(
            result.data_origin.value
            if result.data_origin is not None
            else None
        ),
        reason=result.reason.value,
        local_snapshot_exists=result.local_snapshot_exists,
        freshness_status=(
            result.freshness_status.value
            if result.freshness_status is not None
            else None
        ),
    )
